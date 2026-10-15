---
name: ipo-decision-desk
description: Evaluate Indian IPOs (NSE/BSE mainboard and SME) the way the IPO Decision Desk does - live grey market premium (GMP), realistic allotment odds, Apply / Lottery / Consider / Skip listing calls with reasons, bear/base/bull outcomes per lot, a CRISIL-style long-term research grade, and a backtest that counts the allotment lottery. Also the operating manual for the djsoni99-ux/ipo-gmp-dashboard project (GitHub Actions + Pages, zero LLM tokens). Use this skill whenever the user asks about an Indian IPO, GMP, "should I apply", allotment chances, subscription status, SME IPOs, listing gains, anchor investors, IPO valuation versus peers, which IPOs to apply for today, backtesting IPO strategies, or anything about the IPO dashboard, its data, its refresh schedule, its decision engine or its backtest, even if they do not name the dashboard.
---

# IPO Decision Desk

A decision system for retail investors in Indian IPOs. It answers two different questions, the way good broker research notes do:

1. **Listing view (short term):** should I apply, given that I will sell on listing day? Output: Apply, Lottery bid, Consider, Skip, Await GMP, or Closed, with a 0-100 score, confidence, allotment odds, expected rupees per application, and a bear/base/bull range.
2. **Research view (long term):** is this a good business at a fair price, worth holding after listing? Output: a fundamental grade 1-5 (relative to recent IPOs of the same segment), a valuation verdict, and a long-term view (Positive, Neutral, Cautious).

The single most important idea behind everything here is **adverse selection**: allotment odds are roughly 1 / retail subscription, so you mostly get shares in weak IPOs and rarely in hot ones. Average listing gains (around +12%) look attractive, but the gain on shares a retail applicant actually receives was about +1% over the last 13 months, and applying to every IPO lost money after charges and tax. Selectivity is where the edge is. Never present "if allotted every time" profit as what a person would really have made.

## Project at a glance

| Item | Value |
|---|---|
| Live dashboard | https://djsoni99-ux.github.io/ipo-gmp-dashboard/ (Today / Live calls / Track record) |
| Backtest report | https://djsoni99-ux.github.io/ipo-gmp-dashboard/backtest.html |
| Plain-English guide | .../guide.html and IPO-Desk-Guide.pdf in the repo |
| Repository | github.com/djsoni99-ux/ipo-gmp-dashboard (public; local checkout `D:\Dhaval\AI Projects\ipo-gmp-dashboard`) |
| Refresh | GitHub Actions hourly 07:30-22:30 IST + 02:00 IST; archive daily 21:30 IST; browser pulls live GMP every 3 min; nothing runs on a laptop; no Claude tokens; free on a public repo |
| Engine | `decide.js` (listing call + research view), `backtest.js` (ledger, costs, odds, Monte Carlo, analytics); 26 tests (`node test_backtest.js`, `node test_decide.js`) |
| Data | `ipo.json` (live snapshot), `insights.json` (fundamentals, anchors, category subscription), `archive.json` (13-month history), `history.json` (GMP change log) |

## Pick the mode

| The user wants... | Do this |
|---|---|
| A call on today's IPOs, or one IPO ("should I apply for X?") | **Mode A** below |
| To understand the dashboard or a number on it (layman) | **Mode B** |
| Strategy / research questions ("does GMP work?", "is SME worth it?") | **Mode C**, read `references/backtest.md` |
| To change, fix or extend the project | **Mode D**, read `references/operations.md` and `references/data-sources.md` |
| Why something was built a certain way | `references/project-history.md` |

Exact formulas, weights and thresholds live in `references/methodology.md`. Read it before explaining or changing any score; do not paraphrase numbers from memory.

## Mode A: make the call

1. **Get fresh numbers, never invent them.** GMP and subscription move hourly. Run the bundled report:
   ```bash
   node scripts/ipo_report.js --live                    # all live IPOs, data from the public site + live GMP
   node scripts/ipo_report.js --live --ipo "tonbo"      # one IPO in full detail
   node scripts/ipo_report.js --repo "D:\Dhaval\AI Projects\ipo-gmp-dashboard"   # local checkout + current engine
   node scripts/ipo_report.js --json                    # structured output for further work
   ```
   It applies the same engine as the dashboard (`decide.js`, `backtest.js`), so its calls match what the user sees. If Node or network is unavailable, open the dashboard and read the call, or fetch `ipo.json` / `insights.json` from the site and follow `references/methodology.md` by hand. Always state the data time in IST.
2. **Check timing.** Status comes from dates in IST: upcoming, open, closes today (UPI mandates by 5 PM), closed (awaiting listing), listed. On day 1-2 of an open issue, subscription is "so far" and odds will fall as demand arrives on the last day; say so.
3. **Read both views.** A common and useful split: Apply for listing but Cautious long-term (e.g. strong GMP, loss-making, pure OFS) means apply for the listing gain and sell on listing day, do not hold.
4. **Explain the range.** Bear and bull are the worst and best 10% of similar past listings; base blends today's GMP with how similar IPOs actually listed. Rupee figures are per minimum application, after charges, and only if allotted. Expected per application = odds x base case net.
5. **SME caution.** SME tickets are 2 lots (often Rs 1-3 lakh), circuits and thin books make exits harder (2% slippage assumed), and fundamentals carried no signal in the backtest. Lean on GMP and demand for SME.
6. **Write the note** using the template below.

### Decision note template

Use this structure so notes are comparable day to day. Plain words; no hype; avoid em-dashes.

```markdown
## <IPO name> · <Call> (score <n>/100, confidence <c>%)
<Segment> · band Rs <lo>-<hi> · <closes / opens / lists date> · data as of <time> IST

**Listing view:** <one sentence on the call and the main reason>
| GMP | Allotment odds | Expected per application | Minimum application | Bear / Base / Bull (if allotted) |
|---|---|---|---|---|
| Rs <g> (<pct>) | 1 in <n> (<basis>) | Rs <ev> | Rs <ticket> | <bear>% / <base>% / <bull>% |

**For:** <top 2-3 positive reasons>
**Against:** <top 2-3 negative reasons>
**Research view:** Grade <g>/5 (<label>, vs recent <segment> IPOs), valuation <label> (P/E <x> vs sector <y>, EV/EBITDA <z>), long-term <Positive/Neutral/Cautious>.
**What would change the call:** <e.g. QIB below 1x on the last day, GMP falling under 8%>
```

For several IPOs, lead with a slate table (Call, IPO, Score, GMP, Odds, Expected/app, Bear/Base/Bull, Grade, Long-term), ranked Apply, Lottery, Consider, Skip, and name what closes today. Add the cash needed for the Apply and Lottery bids if the user is planning.

## Mode B: explain the dashboard

The user is a finance professional but new to IPO mechanics; explain in plain English with a worked number. The repo's `guide.html` / `IPO-Desk-Guide.pdf` is the canonical layman guide (12 sections: idea, refresh, glossary, navigation, analysis panel, outcome range, research view, plan, track record, backtest, 5-minute routine, limits). Key answers people ask:

- **Refresh:** nothing to do. GitHub refreshes data hourly even with the laptop off; the page pulls live GMP every 3 minutes while open; the Refresh button fetches immediately. Green "Live" dot = fresh, amber = showing last snapshot.
- **Cost:** free. Public repo means unlimited GitHub Actions minutes and free Pages; no Claude tokens are used after setup. Private would need GitHub Pro and Pages would still be public.
- **Outcome range:** three dots on a line; the thin vertical line is 0%; dots left of it mean a loss; figures are rupees per application if allotted.
- **Navigation:** top bar Today, Live calls, Track record, Backtest, Guide; Plan pill shows cash blocked and refund dates; click any row for the analysis panel (Esc closes; links like `#ipo=ig2369` are shareable).

## Mode C: research and backtest questions

Use the backtest page or `backtest.js` (see `references/backtest.md`). Ground rules that make answers honest:
- Count the lottery: report "gain you'd get" (odds-weighted) and realistic P&L, not just average listing gain.
- Point-in-time only: decisions may use closing-day GMP, first quoted GMP and final subscription (known as bidding closes); listing-eve GMP is for calibration, not for strategy rules.
- Keep SME and mainboard separate; they behave differently.
- Always give sample sizes and say when they are small; the window is a rolling 13 months, one market phase.

Headline findings (as of 16 Oct 2026; re-check on the page because they move daily) are listed in `references/backtest.md`.

## Mode D: change or fix the project

Read `references/operations.md` first (architecture, workflows, local run, verification). Principles the user cares about:
- **No LLM in the refresh loop.** The project exists because an earlier Artifact refreshed by an hourly Claude routine burned the user's tokens. Data work stays in stdlib Python + JS on GitHub Actions.
- **Engine changes need tests.** Edit `decide.js` / `backtest.js`, add or update cases in `test_decide.js` / `test_backtest.js`, run both, then copy the two engine files into `skills/ipo-decision-desk/scripts/engine/` so this skill's report stays in sync.
- **Verify in the browser** after UI changes (desktop, 375 px mobile, dark mode, no console errors, no horizontal scroll) and confirm the GitHub Actions run and Pages build after pushing.
- **Commit style:** descriptive message ending with the co-author trailer the session requires; pull with `--rebase --autostash` before pushing because the bot commits data every hour.

## Guardrails

- This is descriptive analysis, not investment advice. Say so once, plainly; do not lecture.
- GMP is unofficial and off-exchange; it can vanish overnight. Treat it as a direction signal (it was right on direction about 70% of the time) with a typical miss of 8-11 points on size.
- Never fabricate GMP, subscription, odds or financials. If a source is down, say which one and use the last snapshot with its timestamp.
- Respect the sources: low request volume, a descriptive User-Agent, no hammering. These are unofficial endpoints and can change; `references/data-sources.md` explains how to repair a parser.
- Allotment odds are estimates (application counts are not published); 1 / retail subscription is conservative.
- The tool cannot read the full prospectus (litigation, related-party dealings, management quality). For large bets, point the user to the RHP via the "Prospectus details" link.

## Reference files

| File | Read when |
|---|---|
| `references/methodology.md` | Explaining or changing any score, verdict, odds, scenario, grade or valuation rule |
| `references/data-sources.md` | Fetching data, a source broke, adding a field |
| `references/backtest.md` | Strategy, history, validation and findings questions |
| `references/operations.md` | Running, deploying, scheduling, UI/design system, maintenance tasks |
| `references/project-history.md` | Why decisions were made, user preferences, what was tried and rejected |
| `scripts/ipo_report.js` | Producing calls; `scripts/engine/` holds a snapshot of the engine |
