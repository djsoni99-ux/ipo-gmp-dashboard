# Data sources and parsing notes

All sources are public pages or the JSON the sites use themselves. They are unofficial and can change. Keep request volume low (one request per source per run, about 3 concurrent detail fetches) and send a descriptive User-Agent (`ipo-gmp-dashboard/1.0`). No logins, no cookies needed.

## Contents
1. InvestorGain live GMP report (JSON)
2. InvestorGain per-IPO pages (history)
3. Chittorgarh FY list (JSON)
4. Chittorgarh IPO detail and subscription pages (HTML)
5. IPO Watch (HTML, second GMP opinion)
6. Output files and their fields
7. Known gotchas
8. Repairing a broken source

## 1. InvestorGain report 331 (primary live GMP)
`https://webnodejs.investorgain.com/cloud/v2/report/data-read/331/1/{month}/{year}/{FY e.g. 2026-27}/0/all?search=&v=1`
- Returns `msg: 1` and `reportTableData` (about 50 rows: upcoming, open, closed and IPOs listed in the last ~3 weeks). CORS is open (`Access-Control-Allow-Origin: *`), so the browser fetches it directly for the live overlay.
- **Ignores month/year/FY**: always the same rolling window. It is not an archive.
- Fields: `~id` (InvestorGain id, used as the join key `ig_id`), `~ipo_name`, `~ipo_category1` (IPO or SME), `~ipo_status1` (U upcoming, O open, C closed, LP/LN listed positive/negative), `GMP` HTML ("Rs 85 (12.27%) 83 down / 85 up" gives GMP and its low/high range), `~gmp_percent_calc`, `Sub` ("4.01x"), `Price (Rs)`, `Lot`, `IPO Size`, `~P/E`, fire-emoji rating, `Anchor` tick, `~Srt_Open/Close/BoA_Dt`, `~Str_Listing`, `Updated-On`. Listed rows carry "L@111.00 (-6.40%)" in the name text (listing price and gain). Open/Close/Listing cells may embed "GMP: 500" (GMP at that phase).

## 2. InvestorGain per-IPO pages (backtest archive)
`https://www.investorgain.com/gmp/ipo/{id}/` (slug-agnostic, server-rendered)
- Table 0 "GMP Date": daily GMP rows; date cell has markers `O` (open), `C` (close), `A` (allotment), `LP@Rs145.00(10.69%)` / `LN@...` (listing result) and on recent pages `Sub: 131.73x`. Header carries the issue price ("on upper price- Rs131.00").
- **Older pages are paywalled to the last 3 rows** ("Preview Limited to max 3 Records"): those IPOs have the listing result but no close-day GMP. Flag them `limited`; never treat their rows as open/close GMP.
- Row dates have no year: anchor on JSON-LD "Grey Market Premium - YYYY-MM-DD" (or the header's Listed date) and walk backwards.
- Header text gives exact dates: "Opened - 25th Sep 2025 Closed - 29th Sep 2025 Listed - 3rd Oct 2025".
- Narrative (present even when paywalled): "The IPO was subscribed 2.99x" (final total subscription), sector ("... Today & History Civil Construction | SME IPO | BSE SME |"), "Rated 3 /5", "listed at a price of Rs108.10, which is 2.95% higher". Metrics table: First GMP, Latest GMP, GMP Range, Positive/Negative Sessions, Trend Slope.
- Segment: "NSE SME" / "BSE SME" on SME pages, "BSE, NSE" on mainboard.
- IDs with no GMP table are placeholders (announced, never opened); IPOs with a single GMP row are real and must be kept (dropping them biased results upward).
- ID to date, roughly: 700 Dec 2023, 1000 Sep 2024, 1300 Jun 2025, 1600 Jan 2026, 2370 Oct 2026.

## 3. Chittorgarh FY list (report 82)
`https://webnodejs.chittorgarh.com/cloud/report/data-read/82/1/{month}/{year}/{FY}/0/all?search=&v=1`
- Full current FY (about 290 rows by October); older FYs return only 5 rows. Fields: Company link (Chittorgarh id in the URL), Issue Category, Opening/Closing/Listing dates (`~Issue_Open_Date`, `~IssueCloseDate`, `~ListingDate`), Issue Price ("660.00 to 693.00"), Issue Amount, Fresh Capital, Offer for sale, Listing at, Left Lead Manager.
- Once anchors are allotted the price column collapses to the final price; take the band from the detail page instead.
- Report 7 (basis of allotment list) only gives names and dates; reports 21/22/25 reject these parameters.

## 4. Chittorgarh detail and subscription pages (insights.py)
Detail `https://www.chittorgarh.com/ipo/{slug}/{id}/`, subscription `.../ipo_subscription/{slug}/{id}/` (server-rendered tables):
- Basics: Price Band ("Rs665 to Rs700"), Lot Size, Sale Type (OFS only / Fresh capital only / both).
- Issue size, fresh issue, offer for sale (Rs Cr), share holding pre/post.
- Investor category table with retail shares and Max Allottees.
- Financials table ("Period Ended": Assets, Total Income, Profit After Tax, EBITDA, NET Worth, Reserves, Total Borrowing; newest first; first column may be an interim period).
- KPI table (ROE, ROCE, RoNW, PAT Margin, EBITDA Margin, NAV, P/B, sometimes Debt/Equity); latest interim and latest full year columns.
- Valuation (EPS and P/E pre/post, market cap; "-ve" means loss-making), promoter holding pre/post, broker review counts (Subscribe / May Apply / Neutral / Avoid).
- **Precedents table** (recent same-sector IPOs: issue type, size, price, P/E, listing-day close, listing gain, LTP): used for valuation and for post-listing checks.
- "Objects of the Issue" text: classified into debt, capex, working capital, acquisition, general, ofs_only.
- Subscription page: category subscription (Qualified Institutional, Non Institutional, Retail Individual or Individual Investors, Total; some pages show only Total), anchor bid table, **anchor book** (anchor, group entity, % allocated: mutual fund share, insurer share, marquee foreign share), timetable (allotment, refund, listing).
- No published retail application counts, so odds are 1 / retail subscription.

## 5. IPO Watch
`https://ipowatch.in/ipo-grey-market-premium-latest-ipo-gmp/`: two HTML tables (mainboard, SME) with company link, status, GMP, price, est. listing "(xx%)", dates. Used as a second GMP opinion; disagreement over 20% (and over Rs 5) is flagged.

## 6. Output files

| File | Built by | Contents |
|---|---|---|
| `ipo.json` | fetch_ipo.py (hourly) | `generated_at`, per-source health, IPOs: ids (`ig_id`, `ch_id`), status, prices, band, lot, GMP, low/high, phase GMPs, subscription, size, fresh/OFS, dates, `gmp_alt` (IPO Watch), listing result, URLs |
| `history.json` | fetch_ipo.py | `{id: [[timestamp, gmp], ...]}` on change; trend arrows |
| `insights.json` | insights.py (hourly, active IPOs; listed cached 35 days) | keyed by Chittorgarh id; fields in section 4; `ig_id` link |
| `archive.json` | build_archive.py (daily) | rolling 13 months of IPOs: dates, price, GMP at open/close/post/listing eve, first GMP, series, sub_close, sub_final, sector, rating, listing price and gain, `limited`, `dates_exact` |

fetch_ipo.py and insights.py rewrite files only when content changes (timestamps excluded), so commits happen only on real changes.

## 7. Known gotchas
- Windows: run Python with `-X utf8` for the rupee sign; `python -I` ignores `PYTHONIOENCODING`.
- Name matching across sources uses token prefixes with Ltd/Limited stripped and plural endings normalised ("Ultrasonics" = "Ultrasonic"), with segment and open date as tie-breakers.
- Compute dates in IST explicitly (runners are UTC).
- InvestorGain "Sub" is total subscription; use Chittorgarh's retail figure for odds when available.
- Browsers cache `archive.json` / `insights.json` for up to 10 minutes (the page buckets its cache-buster by 10 minutes).

## 8. Repairing a source
1. Open the failing Actions run; the `[warn]` line names the source and URL.
2. Fetch the URL once locally and inspect the new shape (JSON keys or table headers).
3. Patch only that source's function (`fetch_investorgain`, `fetch_chittorgarh`, `fetch_ipowatch`, `parse_detail`, `parse_subscription`, `parse`).
4. Run the script locally twice (second run should report "no change"), run both test files, push, run the workflow manually, confirm green.
A single failed source shows a banner on the page; the run only fails when no GMP source answers, and the previous snapshot is kept.
