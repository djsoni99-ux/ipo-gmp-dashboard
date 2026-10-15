# Methodology (exact rules from decide.js and backtest.js)

All numbers below are copied from the code. If the code changes, update this file and the engine copy in `scripts/engine/`.

## Contents
1. Inputs and status
2. Listing view: six factors, score, confidence
3. Allotment odds
4. Bear / base / bull and expected value
5. Verdict rules
6. Research view: grade, valuation, long-term view, sponsorship
7. Trade, cost and tax model (shared with the backtest)
8. Where the method comes from

## 1. Inputs and status

Per IPO: `price` (upper band), `gmp` (Rs), `lot`, `segment` (Mainboard / SME), `open`, `close`, `listing`, `subscription_x`, GMP `trend` (current GMP minus the previous distinct value in `history.json`), plus the Chittorgarh insight record (`sub.qib/nii/retail/total`, `anchor_book`, `reviews`, `financials`, `kpi`, `kpi_fy`, `pe_pre/pe_post`, `eps`, `mcap_cr`, `precedents`, `issue_size_cr`, `fresh_cr`, `ofs_cr`, `promoter_pre/post`, `uses`, `objects`, `price_low/high`).

GMP % = gmp / price x 100. Status (IST date t): listed if a listing price exists or t >= listing; upcoming if t < open; open if open <= t <= close; closed if t > close. "Early" = open and today is not the closing day; early demand numbers are dampened and labelled "so far".

## 2. Listing view

Weights `W = { signal 30, history 20, demand 20, valuation 15, fundamentals 10, structure 5 }`. Each factor gives s in [0,1]. Missing factors are dropped and weights renormalised. Score = round(100 x weighted mean). Confidence = (sum of available weights / 100) x 0.85 if the history sample is thin x 0.9 if early.

**Signal (30).** s = clamp(GMP% / 30) minus 0.1 if GMP is falling. Reasons: GMP <= 0 "No grey-market premium" (-); GMP >= 25% "implies a strong listing" (+); GMP < 8% "thin cushion after costs" (-); falling (-).

**History (20).** `similar(rows, segment, GMP%, minN 8)`: listed IPOs of the same segment whose listing-eve GMP% is within a tolerance of today's GMP%, widening 4 -> 8 -> 15 -> 30 points until at least 8 match. Needs n >= 3. s = 0.5 x posRate + 0.5 x clamp((avg gain + 10) / 40); if thin (n < 8) s is pulled halfway to 0.5. Reasons: posRate >= 75% and not thin (+); posRate < 50% (-).

**Demand (20).** Mainboard with QIB data: s = 0.6 x lg(QIB, 50) + 0.4 x lg(NII, 50), where lg(x, top) = clamp(log10(x+1) / log10(top+1)). SME or no QIB: s = 0.5 x lg(total, 100) + 0.5 x lg(NII or total, 100). Early: s = 0.5 + (s - 0.5) x 0.5. Anchor book: long-only share (mutual funds + insurers) >= 60% adds 0.08 (+), < 20% subtracts 0.05 (-). Broker reviews: more avoid than subscribe + may apply subtracts 0.05 (-); >= 3 subscribe and no avoid (+ reason only). Reasons (not early): QIB >= 20x (+), QIB < 1x (-), total < 1.5x (-).

**Valuation (15).** P/E = post-issue if positive, else pre-issue. Precedents = recent same-sector IPOs from the Chittorgarh page with 0 < P/E < 300; use same-segment precedents if at least 2 exist. Loss-making: s = 0.15 (-). With >= 2 peers: ratio = P/E / median peer P/E; s = 1 if <= 0.85 (discount, +), 0.65 if <= 1.15, 0.35 if <= 1.5, 0.1 above (rich, -). Without peers: P/E < 20 -> 0.8, < 40 -> 0.6, < 70 -> 0.35, else 0.15 (P/E >= 70 is a - reason).

**Fundamentals (10).** Needs two full financial years. Full years = periods with the same year-end as the oldest period (handles March and December year-ends). Average of: revenue growth (>= 20% 1, >= 0 0.6, else 0.2), PAT margin (>= 10% 1, >= 0 0.5, else 0), ROE (>= 15 1, >= 8 0.6, else 0.3), debt/equity (< 0.5 1, < 1.5 0.6, else 0.2). Reasons: revenue fell (-); growth >= 30% with margin > 5% (+); loss in the latest interim period (-).

**Structure (5).** Fresh share = fresh / issue size: >= 50% 1, >= 25% 0.6, else 0.3 (unknown 0.5); SME issue < Rs 25 Cr subtracts 0.2. Pure OFS (< 10% fresh) is a - reason.

## 3. Allotment odds

Order of preference: retail subscription (p = min(1, 1/retail)); else total subscription; else (upcoming) 1 / median final subscription of same-segment IPOs whose listing-eve GMP was within 10 points (needs 5); else the default `allot` (Mainboard 0.25, SME 0.08). The basis label says which ("retail so far" when early). True odds may be a little better because big retail bids take several lots; application counts are not published.

## 4. Scenarios and expected value

With at least 5 similar IPOs: base = 0.5 x GMP% + 0.5 x similar average; bear = min(similar P10, base); bull = max(GMP%, similar P90). Otherwise base = 0.85 x GMP%, bear = min(-10%, base), bull = 1.2 x GMP%. Each scenario is converted to net rupees for one minimum application via the cost model (section 7), using 1 lot (mainboard) or 2 lots (SME) at the upper band. Expected per application = base net x odds.

## 5. Verdict rules (in order)

1. Status closed -> CLOSED. 2. No GMP -> WAIT.
3. GMP <= 0, or base <= 3%, or (history not thin and posRate < 45%) -> SKIP.
4. Score >= 62 and base >= 8% -> LOTTERY if odds < 0.1 (worse than 1 in 10), else APPLY.
5. Score >= 45 -> CONSIDER. 6. Otherwise SKIP.
7. SME downgrade: APPLY becomes CONSIDER if the bear case is below -10% and the score is under 70.

Labels shown: Apply, Lottery bid (engine label "Apply · lottery odds"), Consider, Skip, Await GMP, Closed.

## 6. Research view (`research()`)

Pillars `{ growth 30, profitability 30, balance 15, governance 25 }`; needs at least 2 pillars.

- **Growth:** revenue CAGR over the full years available: >= 25% 1, >= 15 0.8, >= 8 0.6, >= 0 0.35, else 0.1 (unknown 0.3). +0.05 if profit CAGR >= revenue CAGR; -0.1 if profit CAGR negative. Pre-IPO surge: profit CAGR > 100% (or else revenue CAGR > 100%) caps the pillar at 0.6 with a "check it is sustainable" flag. Latest-year loss -0.15. Momentum: latest interim period annualised; below 85% of last year's pace -0.15 (-), above 115% a + note.
- **Profitability:** average of ROCE (>= 20 1, >= 12 0.65, >= 0 0.3, else 0), ROE (>= 18 1, >= 10 0.6, >= 0 0.3, else 0), PAT margin (>= 12 1, >= 5 0.6, >= 0 0.3, else 0); uses the latest full-year KPI column. ROCE >= 25 (+), < 10 (-).
- **Balance sheet:** debt/equity < 0.3 1, < 1 0.7, < 2 0.4, else 0.15; >= 1.5 flagged.
- **Governance and issue:** average of fresh share (>= 60% 1, >= 30% 0.75, > 5% 0.55, else 0.4), promoter holding after the issue (>= 50% 1, >= 35% 0.65, else 0.35), use of proceeds (capex or debt 0.9, working capital 0.7, general 0.5; ignored for pure OFS so it is not double-counted). Notes for pure OFS, promoters < 35%, debt repayment, capex.

**Grade:** composite = weighted pillar mean x 100. Relative grading like CRISIL: cut points are the 20/40/60/80th percentiles of all analysed IPOs of the same segment (`gradeCuts`, needs 12+ per segment); grade = 1 + number of cuts exceeded. Absolute fallback: >= 0.86 5, >= 0.72 4, >= 0.56 3, >= 0.4 2, else 1. Labels: 5 Strong, 4 Above average, 3 Average, 2 Below average, 1 Weak.

**Valuation verdict:** premium = P/E / sector median - 1. Loss-making; else premium <= -15% "Discount to peers", <= 15% "In line", <= 50% "Premium to peers", above "Stretched". Without peers: PEG (P/E / profit CAGR, only if CAGR 0-100%) < 1 "Reasonable for its growth", <= 2 "Fully priced", else "Stretched"; or P/E < 20 "Undemanding", < 40 "Fully priced", else "Stretched". Premium or Stretched becomes ", growth-justified" when PEG < 1.2 and ROCE >= 20%. Also reported: EV/EBITDA = (market cap + debt) / last full-year EBITDA, P/B.

**Long-term view:** no grade -> No view. Grade >= 4 and not rich -> Positive. Grade <= 2, or rich (Stretched or loss-making, not justified) with grade <= 3 -> Cautious. Otherwise Neutral.

**Sponsorship:** anchor count, long-only share (mutual funds + insurers), marquee foreign share, fund houses, broker consensus counts.

## 7. Trade, cost and tax model (`backtest.js` DEFAULTS)

- Ticket: Mainboard Rs 15,000, SME Rs 1,20,000 when the lot is unknown (shares = floor(ticket / price)); with a known lot the dashboard uses 1 lot (mainboard) or 2 lots (SME).
- Exit at listing price less slippage: Mainboard 0.5%, SME 2%.
- Charges on sale: brokerage Rs 20, exchange 0.00325%, SEBI 0.0001%, GST 18% on those, STT 0.1%, DP Rs 15.93; stamp duty on buy 0.
- Tax: 20.8% (STCG 20% + 4% cess) on positive net, netted per financial year (the live per-application figures are before tax).
- Cash blocked: bid on closing day; refund two working days later if not allotted; if allotted, released the working day after listing. Weekdays only, no holiday calendar.
- Benchmark 6.5% a year (liquid fund) for return on blocked capital. Monte Carlo 3,000 runs (2,000 on the page), seed 42.

## 8. Sources of the method

- CRISIL IPO grading: 1-5 grade on business and financial prospects, management and governance, relative to listed equities, explicitly not a price opinion.
- Renaissance Capital IPO research: fundamentals, governance, valuation against listed peers, insider cash-outs.
- Indian broker IPO notes (Ventura, SBI Securities, Anand Rathi, Centrum, Antique as reported): a premium to peers is the main avoid trigger; growth and ROCE justify a premium; use of proceeds and promoter exits are scrutinised.
- CaseMark "analyzing IPO valuation and pricing" skill: comps, precedent IPOs, IPO discount, demand, bear/base/bull, adapted for a retail applicant.
- Academic work on Indian IPOs: anchor participation certifies institutional demand; anchor oversubscription lifts initial returns; GMP and subscription drive retail demand; SME issues are more speculative.
- Reviewed but not reused (US issuer focus): mcpmarket pre-IPO readiness assessment, q32llc ipogrid IPO research skill. Their method of stating sample sizes and separating high and low signal was adopted.
