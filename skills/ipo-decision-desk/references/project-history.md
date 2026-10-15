# Project history, decisions and user preferences

How the project evolved in the build conversation (15-16 Oct 2026), so future work respects what was decided and why.

## Timeline
1. **Problem:** an "IPO GMP Tracker" Claude Artifact was refreshed by an hourly cloud routine in which Claude scraped three sites and rewrote the HTML. It burned the user's tokens. The routine was already disabled.
2. **Rebuild:** stdlib Python fetcher + static page on GitHub Pages + GitHub Actions cron. InvestorGain JSON (GMP), Chittorgarh JSON (dates, sizes), IPO Watch HTML (second opinion). Browser overlays InvestorGain live because its API allows CORS.
3. **Backtest v1:** the user asked to "apply and take listing gain", consider cost, time frame, capital blocked and average blocking period. Built the ledger, costs, capital timeline, Monte Carlo and strategy comparison.
4. **13-month window** chosen by the user. Discovered InvestorGain's report has no archive and per-IPO pages are paywalled to 3 readings; used page narratives for final subscription, sector, rating and exact dates.
5. **SME vs mainboard separately** at the user's request; found adverse selection (gain you'd actually get about +1%) and fixed an upward bias from dropping single-row IPOs.
6. **Decision desk:** the user said the dashboard was "boring" and should be a decision maker. Added the six-factor engine, verdicts, odds, bear/base/bull, last-30-days GMP vs reality, Chittorgarh financials, precedents and category subscription.
7. **Palette:** private-equity / premium advisor look; later the warm cream canvas was replaced by a cool off-white at the user's request ("just improve, don't redesign everything").
8. **Backtest page** rebuilt to show meaningful analysis only: verdict plus answered questions.
9. **Full redesign** after "looks machine created": shared design system, app bar, ranked list with slide-in panel, report layout.
10. **Research view:** studied how CRISIL, Renaissance Capital and broker desks evaluate IPOs; added grade, valuation verdict, anchor-book quality, broker consensus and long-term view; validated on recent IPOs.
11. **Guide** (web + PDF) for laymen; price band restored on cards; refresh moved from 30 minutes to hourly with a labelled Refresh button; GitHub About section rewritten.

## Decisions and why
- **No LLM in any refresh loop.** Cost was the original problem.
- **Public repo** so Actions and Pages are free; data is public anyway.
- **Point-in-time discipline** in validation; listing-eve GMP only for calibration.
- **Relative grades within segment**, because absolute thresholds rated 70% of IPOs 4-5 (SME financials are flattered before listing) and mixed segments penalised mainboard issuers.
- **Pre-IPO profit or revenue surges are capped**, matching how research desks treat window dressing.
- **Pure OFS is a caution, not a disqualifier**, and is counted once (it was double-counted at first).
- **Band from the Chittorgarh detail page**, because the FY list collapses to the final price after anchors.
- **Day-1 subscription** is labelled "so far" and not used to flag under-subscription until the last day.
- **Research grade kept separate from the listing call**: it helps mainboard listing outcomes but not SME and not post-listing drift yet.

## User preferences learned
- Finance professional (Cisco Finance, CA-adjacent), not a developer; wants decisions and plain-English explanations, not data dumps.
- Prefers flat project structures, concise answers, and evidence over claims.
- Wants premium, clean, restrained design (private-bank register); dislikes generic AI-looking UI and warm cream backgrounds; prefers improving over redesigning when asked.
- Cost-sensitive about tokens and subscriptions; wants things to run without the laptop.
- May dismiss multi-question prompts; ask at most one question and otherwise act.

## Things tried and rejected
- InvestorGain month/FY parameters for history (ignored by the API).
- Chittorgarh reports 21/22/25 for subscription and listing history (wrong parameter shape).
- Flat allotment probability for history (overstated hot IPOs; replaced by 1 / subscription).
- Comparing strategies on "net per allotment" (ignores adverse selection; replaced by odds-weighted gain).
- Cards-everywhere UI, glyph icons, uppercase micro-labels (read as machine-made).
