"""
Fetch every RSS feed listed in feeds/sources.yaml, normalise into a single
schema, dedupe against everything we've seen before (URL canonicalisation
+ title hash), and append new items to reports/mentions.jsonl.

Designed to be safe to run repeatedly — idempotent. Soft-fails on
individual feed errors so a single dead source doesn't stop the job.

Usage:
    python aggregate.py                       # writes new rows to mentions.jsonl
    python aggregate.py --since-hours 24      # also prints new items to stdout
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
import time
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import urlparse, urlunparse

import feedparser
import requests
import yaml

ROOT = Path(__file__).resolve().parent.parent
SOURCES = ROOT / "feeds" / "sources.yaml"
STATE = ROOT / "reports" / "mentions.jsonl"

USER_AGENT = "mal-monitor/1.0 (+github actions; rss aggregator)"
TIMEOUT_S = 20


@dataclass
class Mention:
    id: str            # sha256(canonical_url | normalised_title)
    source_id: str
    source_label: str
    category: str
    title: str
    url: str
    published: str     # ISO 8601 UTC
    summary: str
    first_seen: str    # ISO 8601 UTC


def load_sources() -> dict:
    with SOURCES.open() as f:
        return yaml.safe_load(f)


def load_seen_ids() -> set[str]:
    if not STATE.exists():
        return set()
    ids: set[str] = set()
    with STATE.open() as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                ids.add(json.loads(line)["id"])
            except (json.JSONDecodeError, KeyError):
                continue
    return ids


def canonicalise_url(url: str) -> str:
    """Drop common tracking params and fragments so the same article fetched
    from two paths still dedupes."""
    if not url:
        return ""
    parsed = urlparse(url)
    drop_prefixes = ("utm_", "gclid", "fbclid", "mc_", "ref")
    kept = []
    for kv in parsed.query.split("&"):
        if not kv:
            continue
        k = kv.split("=", 1)[0].lower()
        if any(k.startswith(p) for p in drop_prefixes):
            continue
        kept.append(kv)
    return urlunparse(parsed._replace(query="&".join(kept), fragment=""))


def normalise_title(title: str) -> str:
    t = re.sub(r"\s+", " ", (title or "")).strip().lower()
    # Google News appends " - Publisher" to every title; strip for dedupe.
    t = re.sub(r"\s+-\s+[^-]+$", "", t)
    return t


def mention_id(url: str, title: str) -> str:
    key = f"{canonicalise_url(url)}|{normalise_title(title)}"
    return hashlib.sha256(key.encode()).hexdigest()[:16]


def matches_entity(text: str, entity: dict) -> bool:
    """Used for feeds where `filter_required: true` (whole-publisher RSS)."""
    if not text:
        return False
    lc = text.lower()
    needles = [h.lower() for h in entity["company"]["handles"]]
    needles.append(entity["company"]["name"].lower())
    if entity["ceo"]["name"] and entity["ceo"]["name"] != "<CEO_NAME>":
        needles.append(entity["ceo"]["name"].lower())
        needles.extend(h.lower() for h in entity["ceo"]["handles"])
    return any(n in lc for n in needles)


def resolve_nitter_url(template: str, instances: list[str]) -> str | None:
    """Try each Nitter instance until one responds. Returns the resolved URL
    or None if all are dead."""
    for inst in instances:
        url = template.replace("{nitter}", inst)
        try:
            r = requests.head(
                url, timeout=TIMEOUT_S, allow_redirects=True,
                headers={"User-Agent": USER_AGENT},
            )
            if r.status_code < 400:
                return url
        except requests.RequestException:
            continue
    return None


def fetch_feed(url: str) -> feedparser.FeedParserDict | None:
    try:
        r = requests.get(
            url, timeout=TIMEOUT_S,
            headers={"User-Agent": USER_AGENT},
        )
        r.raise_for_status()
        return feedparser.parse(r.content)
    except requests.RequestException as e:
        print(f"  [warn] fetch failed: {e}", file=sys.stderr)
        return None


def entry_published(entry) -> str:
    for k in ("published_parsed", "updated_parsed"):
        v = entry.get(k)
        if v:
            return datetime(*v[:6], tzinfo=timezone.utc).isoformat()
    return datetime.now(timezone.utc).isoformat()


def collect() -> list[Mention]:
    cfg = load_sources()
    seen = load_seen_ids()
    entity = cfg["entity"]
    nitter_instances = cfg.get("nitter_instances", [])
    now_iso = datetime.now(timezone.utc).isoformat()

    fresh: list[Mention] = []

    for src in cfg["feeds"]:
        if src.get("enabled") is False:
            continue
        if "REPLACE_WITH" in src["url"]:
            continue

        url = src["url"]
        if "{nitter}" in url:
            resolved = resolve_nitter_url(url, nitter_instances)
            if not resolved:
                print(f"[{src['id']}] all Nitter instances unreachable; skipping",
                      file=sys.stderr)
                continue
            url = resolved

        print(f"[{src['id']}] fetching {url}", file=sys.stderr)
        parsed = fetch_feed(url)
        if not parsed:
            continue

        kept_in_feed = 0
        for entry in parsed.entries:
            title = entry.get("title", "")
            link = entry.get("link", "")
            summary = entry.get("summary", entry.get("description", ""))

            if src.get("filter_required"):
                if not matches_entity(f"{title} {summary}", entity):
                    continue

            mid = mention_id(link, title)
            if mid in seen:
                continue
            seen.add(mid)

            fresh.append(Mention(
                id=mid,
                source_id=src["id"],
                source_label=src["label"],
                category=src["category"],
                title=title.strip(),
                url=link,
                published=entry_published(entry),
                summary=re.sub(r"<[^>]+>", "", summary).strip()[:500],
                first_seen=now_iso,
            ))
            kept_in_feed += 1

        print(f"[{src['id']}] kept {kept_in_feed} new", file=sys.stderr)
        # Friendly to Google News
        time.sleep(0.5)

    return fresh


def persist(new: list[Mention]) -> None:
    STATE.parent.mkdir(parents=True, exist_ok=True)
    with STATE.open("a") as f:
        for m in new:
            f.write(json.dumps(asdict(m)) + "\n")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--since-hours", type=float, default=None,
                    help="Also print mentions newer than N hours to stdout")
    args = ap.parse_args()

    fresh = collect()
    persist(fresh)
    print(f"\nAppended {len(fresh)} new mentions to {STATE}", file=sys.stderr)

    if args.since_hours is not None:
        cutoff = datetime.now(timezone.utc) - timedelta(hours=args.since_hours)
        recent = [m for m in fresh
                  if datetime.fromisoformat(m.first_seen) >= cutoff]
        for m in recent:
            print(f"- [{m.category}] {m.title} — {m.url}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
