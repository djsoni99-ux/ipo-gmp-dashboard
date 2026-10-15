# IPO GMP Dashboard

Live grey-market-premium board for Indian mainboard + SME IPOs. Static page on GitHub Pages,
data refreshed by a GitHub Actions cron. **Zero LLM tokens in steady state.**

```
index.html        the dashboard (vanilla JS, no build step)
ipo.json          latest merged snapshot  (written by the Action)
history.json      GMP change log for the trend line  (written by the Action)
fetch_ipo.py      stdlib-only fetcher / merger
.github/workflows/refresh.yml   cron: every 30 min, 07:30-23:30 IST
```

## How "live" works

| Layer | What | Freshness |
|---|---|---|
| Browser overlay | `index.html` calls InvestorGain's JSON feed directly (CORS is open) and overlays GMP, range, subscription, listing result | on load + every 3 min while the tab is visible |
| Snapshot | `fetch_ipo.py` merges InvestorGain + Chittorgarh + IPO Watch into `ipo.json` | every 30 min via Actions |

If the browser feed is blocked the page falls back to the snapshot, and vice versa, so one broken
source never blanks the board. Source health is shown top-right and in `ipo.json["sources"]`.

## Sources

- **InvestorGain** `webnodejs.investorgain.com/cloud/v2/report/data-read/331/...` - GMP, range, subscription, lot, rating
- **Chittorgarh** `webnodejs.chittorgarh.com/cloud/report/data-read/82/...` - dates, price band, issue size, lead manager
- **IPO Watch** `ipowatch.in/ipo-grey-market-premium-latest-ipo-gmp/` - second GMP opinion (HTML table)

These are the sites' own unofficial JSON/HTML endpoints, so they can change without notice.
Fetches are low-volume (one request per source per run) and identify as `ipo-gmp-dashboard`.

## Run locally

```bash
python fetch_ipo.py          # writes ipo.json + history.json
python -m http.server 8630   # open http://localhost:8630
```

## If a source breaks

The Action goes red only when *no* GMP source answers; a single broken source just shows a
warning banner. To fix a changed endpoint, open the failing run log, copy the `[warn]` line and
patch the matching `fetch_*` function in `fetch_ipo.py` - it is one function per source.

## Disclaimer

GMP is an unofficial, off-exchange sentiment indicator, not recognised by SEBI/NSE/BSE.
Nothing here is investment advice.
