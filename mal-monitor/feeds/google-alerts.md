# Google Alerts — one-time setup

Google Alerts has no API. Set these up manually at
<https://www.google.com/alerts>. For each alert below:

1. Paste the query into the search box.
2. Set **How often** = *As-it-happens*.
3. Set **Sources** = *Automatic*.
4. Set **Language** = *English* (add Arabic alerts later if useful).
5. Set **Region** = *Any region*.
6. Set **How many** = *All results*.
7. Set **Deliver to** = an inbox you've registered with
   [Kill the Newsletter](https://kill-the-newsletter.com/) — that service
   gives you a per-feed email address that converts inbound mail to an
   RSS endpoint. Paste the resulting RSS URL back into
   `feeds/sources.yaml` and flip `enabled: true`.

## Alerts to create

| Purpose                       | Query                                                                                                |
| ----------------------------- | ---------------------------------------------------------------------------------------------------- |
| Company — broad               | `"mal.ai" OR "Mal AI"`                                                                               |
| Company + Islamic finance     | `"mal.ai" "Islamic finance"`                                                                         |
| Company + AI-native framing   | `"mal.ai" ("AI native" OR "AI-first")`                                                               |
| Company on LinkedIn           | `"mal.ai" site:linkedin.com`                                                                         |
| CEO on LinkedIn               | `"<CEO_NAME>" site:linkedin.com`                                                                     |
| Company on X                  | `"mal.ai" site:x.com OR site:twitter.com`                                                            |
| Regional press — Gulf-only    | `"mal.ai" (site:thenationalnews.com OR site:gulfnews.com OR site:khaleejtimes.com OR site:arabianbusiness.com)` |
| Islamic-finance trade press   | `"mal.ai" (site:salaamgateway.com OR site:islamicfinancenews.com OR site:zawya.com)`                 |
| Launch tracker                | `"mal.ai" ("launch" OR "go-live" OR "general availability" OR "GA")`                                 |
| Funding tracker               | `"mal.ai" ("seed" OR "Series A" OR "raised" OR "funding")`                                           |

Replace `<CEO_NAME>` with the actual name once confirmed (LinkedIn /
Crunchbase / press release).
