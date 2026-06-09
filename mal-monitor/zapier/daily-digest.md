# Zapier — daily digest (alternative path)

You asked for Zapier specifically. The GitHub Actions cron in
`.github/workflows/mal-monitor-daily.yml` is the canonical fully-free
path; this doc covers Zapier for completeness or if you'd rather operate
no-code.

## Cost reality check

- **Free plan:** 100 tasks/mo, single-step Zaps only.
- **Each RSS feed item that flows through counts as one task.** With ~12
  feeds and even modest mention volume you will exhaust the free tier in
  the first week of a launch news cycle.
- **Multi-step Zaps** (which you need for "aggregate + dedupe + send one
  daily email") require the Starter plan: **$29.99/mo** at time of writing.
- If "free" is a hard constraint, use **Make.com** (`mal-monitor/make/`)
  or the GitHub Actions path. Make's free tier (1000 ops/mo, multi-step)
  comfortably fits this workload.

If you still want Zapier:

## Architecture

```
[RSS by Zapier] ──┐
[RSS by Zapier] ──┤
        …         ├──► [Digest by Zapier] ──► [Gmail]
[RSS by Zapier] ──┘    (every day, 08:00 GST)
```

Zapier ships a built-in **"Digest by Zapier"** action that's purpose-
built for this: each trigger appends to a named digest, and a scheduled
release flushes the digest as a single email.

## Step-by-step

### 1. One Zap per source category (so the digest is grouped sensibly)

For each category in `mal-monitor/feeds/sources.yaml` create:

- **Trigger:** *RSS by Zapier — New Item in Multiple Feeds*
- **Feed URLs:** paste every URL from that category (Zapier supports
  multiple feed URLs per trigger as a comma-separated list — counts as
  one trigger).
- **Action:** *Digest by Zapier — Append Entry*
  - **Title of Digest:** `Mal monitor — <category>`
  - **Entry:**
    ```
    • {{title}}
      {{link}}
      {{summary}}
    ```
  - **Frequency:** *Manual* (we release on schedule, not per-entry).

### 2. One Zap to release all digests at 08:00 UTC

- **Trigger:** *Schedule by Zapier — Every Day*, 08:00 UTC.
- **Action 1–N:** *Digest by Zapier — Release Existing Digest* for each
  category. Use **Continue if Empty: yes** so missing categories don't
  break the chain.
- **Action N+1:** *Gmail — Send Email* (or *Email by Zapier*).
  - **To:** your inbox
  - **Subject:** `[Mal monitor] Daily digest — {{zap_meta_human_now}}`
  - **Body:** concatenate the released digest payloads with category
    headers.

### 3. Dedupe

Zapier deduplicates by item GUID per RSS feed automatically, but the
same article will appear across multiple Google News country/site feeds.
Add a *Formatter → Utilities → Deduplicate* step before *Append Entry*,
keyed on `link`.

### 4. LinkedIn coverage

Same trick as the canonical path:

1. Create a Google Alert for `site:linkedin.com "mal.ai"`.
2. Deliver to a [Kill the Newsletter](https://kill-the-newsletter.com/)
   address.
3. Add the resulting RSS URL to the **linkedin** category Zap.

### 5. X/Twitter coverage

Zapier's built-in Twitter integration was deprecated when X locked down
the API. Options:

- *(Free, fragile)* — Same Nitter RSS trick: feed
  `https://nitter.net/search/rss?f=tweets&q=%22mal.ai%22` into another
  *RSS by Zapier* trigger. Expect breakage when instances rotate.
- *(Paid)* — Subscribe to X API Basic ($200/mo) and use a community
  X integration on Zapier.
- *(Free, manual)* — Skip Zapier for X and rely on the Google Alert
  `site:x.com "mal.ai"` flowing in via Kill-the-Newsletter.

## Monthly PDF

Zapier cannot natively generate PDFs. Options:

- *PDF.co* integration (free tier: 200 docs/mo) — feed it an HTML template.
- *Google Docs → Export PDF* via Zapier — templated doc, less control over layout.
- *(Recommended)* — Run the monthly PDF on GitHub Actions
  (`mal-monitor-monthly.yml`) regardless of which platform handles the
  daily digest. The PDF needs sentiment scoring + matplotlib charts,
  which are far cleaner in Python than in Zapier's no-code surface.
