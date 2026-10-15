# Backtest: model, page structure, findings

## What a "trade" is
Apply at the upper band on the closing day; if allotted, sell on listing day at the listing price less slippage; nothing is held. Allotment odds = 1 / final subscription (retail where known), capped at 100%. Costs, tax and blocked-cash rules are in `methodology.md` section 7. Window: rolling 13 months (`KEEP_MONTHS` in build_archive.py), pruned on every daily run. SME and mainboard are always reported separately; "Both" is a convenience view.

## Engine API (backtest.js)
- `ledger(records, cfg)`: one row per listed IPO with shares, invested, sell, charges, gross, `netAllot`, odds `p`, signal timing, gmpPct, gmpList, subClose, size, sector, rating, month, dAllot / dRefund.
- `run(rows, strategy, cfg)`: expected value (odds-weighted) totals, tax per financial year, capital-days, average days blocked, peak and average capital, annualised return on blocked capital vs benchmark, win/loss rates, `weightedGainPct` ("gain you'd get"), equity curve, blocked-capital series, Monte Carlo P10/P50/P90 and P(loss).
- Strategy filters: `segment`, `from/to`, `minGmpPct` (closing-day GMP), `minFirstGmpPct` (first quoted GMP), `minSub` / `maxSub` (final subscription), `minSize`, `minRating`.
- Analytics: `calibration` (GMP vs actual: correlation, bias, MAE, buckets), `distribution`, `byBucket` (gmp, sub, size, rating), `byKey` (sector), `monthly`, `similar`, `csv`.

## Page structure (backtest.html)
Verdict hero with four figures (net result applying to all, average odds, share listed 10%+ down, typical GMP miss), then a report with a contents rail:
1. Did the Decision Desk's calls work? Point-in-time test: each recent IPO with fundamentals is scored using only history listed before its bid date; GMP is closing-day where available, else listing-eve (counted separately).
2. Which rules would have paid? Preset rules per segment ranked by realistic net profit; click for the track record (equity curve, allotments, cash blocked, chance of loss, luck range).
3. What actually drives the listing gain? Factors ranked by spread between best and worst bucket, each bucket with "you'd get".
4. How far can GMP be trusted? Buckets of listing-eve GMP vs actual, plus monthly regime.
5. Does the research grade help? Grade groups and long-term views vs listing outcome and post-listing move (latest price vs listing-day close, from Chittorgarh precedent tables).
6. Method and settings (assumptions editable, CSV download).

## Findings as of 16 October 2026 (re-check the live page; numbers move daily)
- 432 listed IPOs in the window (Sep 2025 to Oct 2026): 279 SME, 153 mainboard.
- Applying to every SME IPO: average listing +12.2%, median +2.1%, but gain on shares received about +0.9%; net about -Rs 1.39 lakh. Mainboard: average +11.1%, gain received about -2.0%, net about -Rs 14,000. Both: about -Rs 1.54 lakh.
- Last 30 days: "allotted every time" would have made about Rs 6.4 lakh, realistic odds-weighted P&L about -Rs 1,500.
- Decision Desk calls, 81 recent IPOs scored point-in-time: Apply/Lottery listed higher about 93% (avg +38.7%), Skip about 40% (avg -1%); bidding on the Skips would have lost about Rs 68,000-73,000 at realistic odds. SME: 85% vs 41%. Mainboard: 100% vs 33%.
- Best simple rules: SME "first GMP above zero" (+Rs 68,985 vs -Rs 1.39 lakh for all); mainboard "final subscription at least 5x" (+Rs 3,071 vs -Rs 14,219).
- GMP: correlation about 0.84 with listing gain, typical miss 8-11 points, direction right about 70%; at 25%+ GMP 96-100% listed higher, at zero or below about 40%.
- Strongest single driver: GMP before listing (75-point spread in SME). Subscription next for mainboard.
- Research grade: mainboard grade 4-5 listed higher 92% (avg +20%) vs 60% (avg +10%) for grade 1-2; SME no edge (52% vs 50%); after listing no group separated yet (small samples, a few weeks).

## Honesty rules
- Report n with every rate; flag n < 15.
- Final subscription is a mild look-ahead (known only as bidding closes); listing-eve GMP is not tradable.
- Survivorship: only IPOs that listed. Exits at listing price are optimistic for SME.
- One market phase; results can flip in a weak market.
