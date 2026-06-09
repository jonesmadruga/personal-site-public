"""
Monthly PDF report. Reads mentions.jsonl, restricts to the previous
calendar month (UTC), computes:

  - Volume by source category
  - VADER sentiment distribution (positive / neutral / negative)
  - Sentiment trend by week
  - Share of voice between the two positioning narratives:
        "Islamic finance"  vs  "AI native"
  - Top keywords (simple frequency over title+summary, with stopwords)
  - Headline list per category

…and writes a PDF to reports/mal-monitor-YYYY-MM.pdf.
"""

from __future__ import annotations

import json
import re
import sys
from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import cm
from reportlab.platypus import (
    Image, PageBreak, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle,
)
from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer

ROOT = Path(__file__).resolve().parent.parent
STATE = ROOT / "reports" / "mentions.jsonl"
OUT_DIR = ROOT / "reports"

ISLAMIC_KEYWORDS = [
    "islamic", "sharia", "shariah", "halal", "sukuk", "takaful",
    "musharaka", "murabaha", "zakat",
]
AI_KEYWORDS = [
    "ai-native", "ai native", "ai-first", "ai first", "agentic",
    "llm", "machine learning", "generative ai", "artificial intelligence",
]

STOPWORDS = {
    "the", "a", "an", "and", "or", "of", "to", "in", "on", "for", "with",
    "is", "are", "was", "were", "be", "been", "being", "by", "at", "from",
    "this", "that", "these", "those", "as", "it", "its", "into", "but",
    "has", "have", "had", "will", "would", "could", "should", "can",
    "new", "says", "said", "after", "before", "over", "more", "than",
    "their", "they", "we", "our", "you", "your", "i", "he", "she", "his",
    "her", "him", "them", "us", "about", "also", "one", "two", "first",
    "year", "years", "day", "days", "week", "weeks", "month", "months",
    "company", "companies", "startup", "startups", "firm", "firms",
    "mal", "mal.ai", "ceo", "uae", "ae", "gcc",
}


def previous_month_bounds() -> tuple[datetime, datetime, str]:
    now = datetime.now(timezone.utc)
    first_this = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    last_prev = first_this - timedelta(seconds=1)
    first_prev = last_prev.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    return first_prev, first_this, first_prev.strftime("%Y-%m")


def load_window(start: datetime, end: datetime) -> list[dict]:
    if not STATE.exists():
        return []
    rows: list[dict] = []
    with STATE.open() as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                row = json.loads(line)
                pub = datetime.fromisoformat(row.get("published") or row["first_seen"])
                if start <= pub < end:
                    rows.append(row)
            except (json.JSONDecodeError, KeyError, ValueError):
                continue
    return rows


def score_sentiment(rows: list[dict]) -> list[dict]:
    sia = SentimentIntensityAnalyzer()
    for r in rows:
        text = f"{r.get('title','')}. {r.get('summary','')}"
        s = sia.polarity_scores(text)
        r["_sentiment"] = s["compound"]
        if s["compound"] >= 0.05:
            r["_sentiment_label"] = "positive"
        elif s["compound"] <= -0.05:
            r["_sentiment_label"] = "negative"
        else:
            r["_sentiment_label"] = "neutral"
    return rows


def tag_narrative(rows: list[dict]) -> list[dict]:
    for r in rows:
        text = f"{r.get('title','')} {r.get('summary','')}".lower()
        r["_islamic"] = any(k in text for k in ISLAMIC_KEYWORDS)
        r["_ai_native"] = any(k in text for k in AI_KEYWORDS)
    return rows


def top_keywords(rows: list[dict], n: int = 20) -> list[tuple[str, int]]:
    counter: Counter[str] = Counter()
    word_re = re.compile(r"[a-zA-Z][a-zA-Z\-]{2,}")
    for r in rows:
        text = f"{r.get('title','')} {r.get('summary','')}".lower()
        for w in word_re.findall(text):
            if w in STOPWORDS or len(w) < 3:
                continue
            counter[w] += 1
    return counter.most_common(n)


def chart_volume_by_category(rows: list[dict], out: Path) -> Path:
    counts: Counter[str] = Counter(r["category"] for r in rows)
    if not counts:
        return _empty_chart("No mentions in window", out)
    labels, values = zip(*counts.most_common())
    fig, ax = plt.subplots(figsize=(6, 3.2))
    ax.barh(labels, values, color="#3a6ea5")
    ax.invert_yaxis()
    ax.set_xlabel("Mentions")
    ax.set_title("Volume by source category")
    fig.tight_layout()
    fig.savefig(out, dpi=140)
    plt.close(fig)
    return out


def chart_sentiment_distribution(rows: list[dict], out: Path) -> Path:
    counts = Counter(r["_sentiment_label"] for r in rows)
    if not counts:
        return _empty_chart("No mentions in window", out)
    order = ["positive", "neutral", "negative"]
    values = [counts.get(k, 0) for k in order]
    fig, ax = plt.subplots(figsize=(4, 3.2))
    ax.pie(values, labels=order, colors=["#3aa55a", "#888888", "#c04848"],
           autopct="%1.0f%%", startangle=90)
    ax.set_title("Sentiment distribution")
    fig.tight_layout()
    fig.savefig(out, dpi=140)
    plt.close(fig)
    return out


def chart_sentiment_by_week(rows: list[dict], out: Path) -> Path:
    by_week: dict[str, list[float]] = defaultdict(list)
    for r in rows:
        try:
            d = datetime.fromisoformat(r["published"])
            wk = d.strftime("%Y-W%W")
            by_week[wk].append(r["_sentiment"])
        except (KeyError, ValueError):
            continue
    if not by_week:
        return _empty_chart("No mentions in window", out)
    weeks = sorted(by_week)
    means = [sum(by_week[w]) / len(by_week[w]) for w in weeks]
    fig, ax = plt.subplots(figsize=(6, 3.2))
    ax.plot(weeks, means, marker="o", color="#3a6ea5")
    ax.axhline(0, color="#aaa", linewidth=0.7)
    ax.set_ylim(-1, 1)
    ax.set_ylabel("Mean VADER compound")
    ax.set_title("Sentiment trend (weekly mean)")
    fig.autofmt_xdate(rotation=30)
    fig.tight_layout()
    fig.savefig(out, dpi=140)
    plt.close(fig)
    return out


def chart_narrative_share(rows: list[dict], out: Path) -> Path:
    n_islamic = sum(1 for r in rows if r["_islamic"])
    n_ai = sum(1 for r in rows if r["_ai_native"])
    n_both = sum(1 for r in rows if r["_islamic"] and r["_ai_native"])
    n_neither = sum(1 for r in rows if not r["_islamic"] and not r["_ai_native"])
    fig, ax = plt.subplots(figsize=(5, 3.2))
    labels = ["Islamic finance only", "AI-native only", "Both", "Neither"]
    values = [n_islamic - n_both, n_ai - n_both, n_both, n_neither]
    ax.bar(labels, values,
           color=["#3a6ea5", "#a55a3a", "#6a3aa5", "#999999"])
    ax.set_ylabel("Mentions")
    ax.set_title("Positioning narrative share of voice")
    fig.autofmt_xdate(rotation=20)
    fig.tight_layout()
    fig.savefig(out, dpi=140)
    plt.close(fig)
    return out


def _empty_chart(msg: str, out: Path) -> Path:
    fig, ax = plt.subplots(figsize=(6, 3))
    ax.text(0.5, 0.5, msg, ha="center", va="center", color="#888")
    ax.axis("off")
    fig.tight_layout()
    fig.savefig(out, dpi=140)
    plt.close(fig)
    return out


def build_pdf(rows: list[dict], period_label: str, out_path: Path) -> None:
    styles = getSampleStyleSheet()
    h1 = styles["Heading1"]
    h2 = styles["Heading2"]
    body = styles["BodyText"]
    small = ParagraphStyle("small", parent=body, fontSize=8, textColor=colors.grey)

    img_dir = OUT_DIR / "_charts"
    img_dir.mkdir(exist_ok=True)
    c_vol = chart_volume_by_category(rows, img_dir / f"{period_label}_vol.png")
    c_sent = chart_sentiment_distribution(rows, img_dir / f"{period_label}_sent.png")
    c_trend = chart_sentiment_by_week(rows, img_dir / f"{period_label}_trend.png")
    c_share = chart_narrative_share(rows, img_dir / f"{period_label}_share.png")

    doc = SimpleDocTemplate(
        str(out_path), pagesize=A4,
        leftMargin=2 * cm, rightMargin=2 * cm,
        topMargin=2 * cm, bottomMargin=2 * cm,
    )
    story = []
    story.append(Paragraph(f"Mal (mal.ai) — Monthly Monitoring Report", h1))
    story.append(Paragraph(f"Period: {period_label}", small))
    story.append(Spacer(1, 0.4 * cm))

    n_total = len(rows)
    n_pos = sum(1 for r in rows if r["_sentiment_label"] == "positive")
    n_neg = sum(1 for r in rows if r["_sentiment_label"] == "negative")
    avg = sum(r["_sentiment"] for r in rows) / n_total if n_total else 0
    summary_t = (
        f"<b>{n_total}</b> mentions captured. "
        f"<b>{n_pos}</b> positive, <b>{n_neg}</b> negative, "
        f"mean compound sentiment <b>{avg:+.2f}</b>. "
        f"<b>{sum(1 for r in rows if r['_islamic'])}</b> mentions reference "
        f"Islamic-finance language; "
        f"<b>{sum(1 for r in rows if r['_ai_native'])}</b> reference AI-native language."
    )
    story.append(Paragraph(summary_t, body))
    story.append(Spacer(1, 0.4 * cm))

    story.append(Paragraph("Volume by source category", h2))
    story.append(Image(str(c_vol), width=15 * cm, height=8 * cm))
    story.append(Spacer(1, 0.3 * cm))

    story.append(Paragraph("Sentiment", h2))
    story.append(Image(str(c_sent), width=10 * cm, height=8 * cm))
    story.append(Spacer(1, 0.2 * cm))
    story.append(Image(str(c_trend), width=15 * cm, height=8 * cm))
    story.append(PageBreak())

    story.append(Paragraph("Positioning narratives", h2))
    story.append(Paragraph(
        "Share of voice between the two strategic narratives Mal is leaning on "
        "into its 2026 launch. \"Both\" is the magic quadrant — coverage that "
        "lands the AI-native frame inside the Islamic-finance context.",
        body))
    story.append(Image(str(c_share), width=14 * cm, height=8 * cm))
    story.append(Spacer(1, 0.3 * cm))

    story.append(Paragraph("Top keywords", h2))
    kws = top_keywords(rows, 20)
    if kws:
        tbl = Table(
            [["Keyword", "Count"]] + [[k, str(v)] for k, v in kws],
            colWidths=[10 * cm, 3 * cm],
        )
        tbl.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.lightgrey),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("GRID", (0, 0), (-1, -1), 0.25, colors.grey),
            ("FONTSIZE", (0, 0), (-1, -1), 9),
        ]))
        story.append(tbl)
    else:
        story.append(Paragraph("No keywords extracted.", body))
    story.append(PageBreak())

    story.append(Paragraph("Headlines by category", h2))
    by_cat: dict[str, list[dict]] = defaultdict(list)
    for r in rows:
        by_cat[r["category"]].append(r)
    for cat, items in sorted(by_cat.items()):
        story.append(Paragraph(f"<b>{cat}</b> ({len(items)})", body))
        items.sort(key=lambda r: r.get("published", ""), reverse=True)
        for r in items[:15]:
            tag = r["_sentiment_label"][:3].upper()
            line = (
                f"[{tag}] {r['title']} "
                f"<font color='grey'>— {r['source_label']}</font><br/>"
                f"<font size=7 color='grey'>{r['url']}</font>"
            )
            story.append(Paragraph(line, body))
        if len(items) > 15:
            story.append(Paragraph(
                f"<i>+ {len(items) - 15} more</i>", small))
        story.append(Spacer(1, 0.2 * cm))

    doc.build(story)


def main() -> int:
    start, end, label = previous_month_bounds()
    rows = load_window(start, end)
    print(f"Building report for {label} — {len(rows)} mentions", file=sys.stderr)

    rows = score_sentiment(rows)
    rows = tag_narrative(rows)

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    out_path = OUT_DIR / f"mal-monitor-{label}.pdf"
    build_pdf(rows, label, out_path)
    print(f"Wrote {out_path}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
