# Make.com — daily digest (recommended no-code path)

Why Make over Zapier here: free tier is **1 000 ops/mo with multi-step
scenarios**, which fits the multi-source aggregate-and-digest pattern
without breaking $0/mo.

## Scenario outline

```
[Schedule: daily 08:00 UTC]
        │
        ▼
[Iterator over feed URLs ─ from sources.yaml]   (static text input, JSON array)
        │
        ▼
[RSS — Retrieve feed items]                     (filter: published > now-24h)
        │
        ▼
[Array aggregator]                              (gather all items)
        │
        ▼
[Tools → Set Variable: dedupe]                  (Map by link)
        │
        ▼
[Text aggregator: build HTML per category]
        │
        ▼
[Email: send digest]
```

## Modules to add (in order)

1. **Schedule** — Every day, 08:00 UTC.
2. **Tools › Set Multiple Variables** — paste the feed URLs from
   `feeds/sources.yaml` as a JSON array literal. Easier than reading
   the YAML from GitHub in a no-code surface.
3. **Iterator** — input = the array from step 2.
4. **RSS › Retrieve feed items** — URL = the iterator output. Filter:
   *Published* > *now minus 1 day*.
5. **Array aggregator** — Source = step 4. Target structure: collect
   `title, link, summary, source, category`.
6. **Tools › Set Variable** — name `seen`, value = empty map.
   Use it in a *Filter* downstream to drop items whose link is already
   in the map; in the same flow add a *Set Variable* that adds each
   processed link.
7. **Text aggregator** — group by `category`, produce HTML `<ul>` per
   group.
8. **Email › Send an Email** — HTML body = step 7. Subject = `Mal
   monitor — {{formatDate(now; "YYYY-MM-DD")}}`.

## Importable blueprint

Make.com exports scenarios as JSON blueprints. The full one is too long
to maintain by hand here — recommended path is:

1. Build the scenario once following the outline above.
2. Export it via the scenario menu → *Export Blueprint*.
3. Commit the resulting `blueprint.json` into this directory so
   re-imports are reproducible.

## Monthly PDF

Make has a *PDF.co* integration on the free tier (200 docs/mo). For
the layout we need — sentiment charts, keyword tables, headlines per
category — it's still easier to use the Python script in
`scripts/monthly_report.py` triggered by the GitHub Actions cron, and
just deliver via Make if you prefer Make controlling delivery.
