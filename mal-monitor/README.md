# Mal Monitoring Dashboard

Free, automated media-monitoring stack for **Mal (mal.ai)** — an AI-native Islamic
finance startup heading into its 2026 launch — and its CEO. Tracks regional
press (The National, Gulf News, Khaleej Times, Arabian Business), MENA
tech press (Wamda, MENAbytes), global tech press (TechCrunch, Sifted),
Islamic-finance trade press (Salaam Gateway, IFN), LinkedIn company
updates, and X/Twitter mentions.

Outputs:

- **Daily email digest** — every new mention across all sources, deduped.
- **Monthly PDF report** — sentiment trend, keyword frequencies, share of
  voice across Islamic-finance vs AI-native positioning narratives.

## Architecture

```
                 ┌─────────────────────────────────────┐
                 │  Source layer (all free)            │
                 │  - Google Alerts → email-to-RSS      │
                 │  - Google News RSS (per query)       │
                 │  - Publisher RSS (The National etc.) │
                 │  - Nitter RSS (X mentions)           │
                 │  - LinkedIn via Google Alerts        │
                 └──────────────┬──────────────────────┘
                                │
                                ▼
                 ┌─────────────────────────────────────┐
                 │  scripts/aggregate.py                │
                 │  Fetch all feeds, normalise,         │
                 │  dedupe (URL + title hash),          │
                 │  persist to reports/mentions.jsonl   │
                 └──────────────┬──────────────────────┘
                                │
                ┌───────────────┴────────────────┐
                ▼                                ▼
   ┌─────────────────────────┐     ┌────────────────────────────┐
   │ scripts/digest_email.py  │     │ scripts/monthly_report.py  │
   │ Daily digest (SMTP)      │     │ VADER sentiment +          │
   │ Triggered by GH Actions  │     │ keyword trends + PDF       │
   │                          │     │ (reportlab + matplotlib)   │
   └─────────────────────────┘     └────────────────────────────┘
```

## What's in this directory

| Path                           | Purpose                                                      |
| ------------------------------ | ------------------------------------------------------------ |
| `feeds/sources.yaml`           | Machine-readable list of every RSS feed and query            |
| `feeds/feeds.opml`             | Importable OPML — drop into Feedly/Inoreader for manual read |
| `feeds/google-alerts.md`       | Exact Google Alert queries to create (one-time setup)        |
| `scripts/aggregate.py`         | Fetch + dedupe + persist                                     |
| `scripts/digest_email.py`      | Daily digest via SMTP                                        |
| `scripts/monthly_report.py`    | Monthly sentiment PDF                                        |
| `scripts/requirements.txt`     | Python deps                                                  |
| `zapier/daily-digest.md`       | Zapier setup (as you originally specified)                   |
| `make/scenario.md`             | Make.com alternative — fits better on the free tier          |
| `reports/`                     | Persistent state: `mentions.jsonl`, PDF outputs              |
| `../.github/workflows/`        | Daily + monthly cron workflows                               |

## Setup — first time

1. **Create Google Alerts** — follow `feeds/google-alerts.md`. Set each alert
   to deliver to an `alerts@…` mailbox (or your personal inbox) "as it
   happens." We funnel them via [Kill the Newsletter](https://kill-the-newsletter.com/)
   which converts an email address into an RSS feed. Add the generated
   feed URLs to `feeds/sources.yaml` under `google_alerts:`.

2. **Configure GitHub Action secrets** (Settings → Secrets → Actions):

   - `DIGEST_SMTP_HOST` (e.g. `smtp.gmail.com`)
   - `DIGEST_SMTP_PORT` (`587`)
   - `DIGEST_SMTP_USER`
   - `DIGEST_SMTP_PASS` (Gmail app password)
   - `DIGEST_FROM` (e.g. `mal-monitor@yourdomain`)
   - `DIGEST_TO` (where the digest lands)

3. **Enable the workflows** — `.github/workflows/mal-monitor-daily.yml`
   runs `08:00 UTC` (noon Gulf), `.github/workflows/mal-monitor-monthly.yml`
   runs on the 1st of each month.

4. *(Optional)* If you also want a Zapier or Make.com path running in
   parallel (e.g. real-time push notifications), see `zapier/` and
   `make/`. The GitHub Actions cron is the canonical free path; the
   no-code platforms are documented for completeness.

## Why these choices

| Original ask           | What we built                          | Why                                                                                        |
| ---------------------- | -------------------------------------- | ------------------------------------------------------------------------------------------ |
| Twitter API scraper    | Nitter RSS + Google Alerts `site:x.com` | X API free tier no longer permits read; Nitter instances rotate (we list 4 fallbacks)      |
| Zapier automation      | GitHub Actions cron (Zapier docs too)  | Zapier free tier is 100 tasks/mo, single-step — won't fit multi-source daily digest        |
| LinkedIn company feed  | Google Alerts `site:linkedin.com/…`    | LinkedIn killed public RSS in 2013; this is the only free, ToS-clean path                  |
| Monthly PDF            | VADER + reportlab in CI                | Free, deterministic, version-controlled. No external PDF service dependency                |

## Costs

Everything in the canonical path runs on the GitHub Actions free tier
(2 000 minutes/month for private repos, unlimited for public). The daily
job uses ~30s, the monthly job ~90s. Effective cost: $0.

## Maintenance

- **Nitter instances die.** When the X feeds go quiet for >3 days,
  rotate to the next instance in `feeds/sources.yaml` (`nitter_instances`).
- **Google News RSS query syntax changes occasionally.** If a feed
  starts returning HTTP 200 with empty `<item>` list, regenerate the
  query URL via `news.google.com`.
- **The `reports/mentions.jsonl` file grows.** It's append-only, deduped
  on read. Truncate or archive yearly.

## Disclaimers

This stack monitors **publicly published** content only. RSS, Google
Alerts on public web pages, and Nitter (which scrapes public X posts)
are all standard OSINT techniques used by communications teams. No
private data, no credential-based scraping, no platform ToS violations
beyond the well-documented Nitter grey area (rotate instances if any
single one explicitly objects).
