// node test_decide.js : verdict engine behaviour on hand-built cases
"use strict";
const assert = require("node:assert/strict");
const B = require("./backtest.js");
const D = require("./decide.js");

let passed = 0;
const t = (name, fn) => { fn(); passed++; console.log("ok  " + name); };
const cfg = Object.assign({}, B.DEFAULTS, { mcRuns: 0 });
// archive: 20 mainboard IPOs whose listing tracked GMP, all positive
const hist = B.ledger(Array.from({ length: 20 }, (_, i) => ({ id: i, name: "H" + i, segment: "Mainboard", price: 100, close: "2026-01-05",
  listing: "2026-01-08", gmp_list: 20 + i, listing_price: 120 + i, listing_gain_pct: 20 + i, sub_final: 30 })), cfg);
const peers = [{ pe: 30 }, { pe: 32 }, { pe: 28 }];
const fin = { periods: ["31 Mar 2026", "31 Mar 2025", "31 Mar 2024"], "Total Income": [130, 100, 80], "Profit After Tax": [15, 10, 8],
  "NET Worth": [100, 85, 75], "Total Borrowing": [20, 25, 30] };
const strongIns = { sub: { qib: 80, nii: 60, retail: 25, total: 50 }, pe_post: 22, precedents: peers, financials: fin, issue_size_cr: 800, fresh_cr: 600 };
const base = { name: "X", segment: "Mainboard", price: 100, gmp: 30, lot: 150, st: "open", close: "2026-10-16" };

t("strong IPO with low odds -> LOTTERY, with reasons and scenarios", () => {
  const d = D.decide(base, strongIns, hist, cfg, "2026-10-16");
  assert.equal(d.verdict, "LOTTERY");                 // retail 25x -> 4% odds
  assert.ok(d.score >= 62, "score " + d.score);
  assert.ok(Math.abs(d.odds.p - 1 / 25) < 1e-9);
  assert.ok(d.scenarios.bear.pct <= d.scenarios.base.pct && d.scenarios.base.pct <= d.scenarios.bull.pct);
  assert.ok(d.reasons.some((r) => r.kind === "+"));
});

t("same IPO with retail barely subscribed -> APPLY", () => {
  const ins = Object.assign({}, strongIns, { sub: { qib: 80, nii: 60, retail: 2, total: 20 } });
  assert.equal(D.decide(base, ins, hist, cfg, "2026-10-16").verdict, "APPLY");
});

t("no premium -> SKIP", () => {
  assert.equal(D.decide(Object.assign({}, base, { gmp: 0 }), strongIns, hist, cfg, "2026-10-16").verdict, "SKIP");
});

t("rich, loss-making, OFS-only, weak QIB -> SKIP or CONSIDER, never APPLY", () => {
  const weak = { sub: { qib: 0.6, nii: 1.2, retail: 1.5, total: 1.1 }, loss_making: true, precedents: peers, issue_size_cr: 500, fresh_cr: 0,
    financials: { periods: ["31 Mar 2026", "31 Mar 2025"], "Total Income": [80, 100], "Profit After Tax": [-5, 2], "NET Worth": [50, 55], "Total Borrowing": [90, 60] } };
  const d = D.decide(Object.assign({}, base, { gmp: 6 }), weak, hist, cfg, "2026-10-16");
  assert.ok(["SKIP", "CONSIDER"].includes(d.verdict), d.verdict);
  assert.ok(d.reasons.filter((r) => r.kind === "-").length >= 3);
});

t("no GMP yet -> WAIT; closed -> CLOSED", () => {
  assert.equal(D.decide(Object.assign({}, base, { gmp: null }), strongIns, hist, cfg, "2026-10-16").verdict, "WAIT");
  assert.equal(D.decide(Object.assign({}, base, { st: "closed" }), strongIns, hist, cfg, "2026-10-16").verdict, "CLOSED");
});

t("missing factors drop out and lower confidence", () => {
  const d = D.decide(base, {}, [], cfg, "2026-10-16");
  assert.ok(d.confidence < 0.6, "confidence " + d.confidence);
  assert.ok(d.score != null);
});

t("valuation discount to precedents scores higher than premium", () => {
  const cheap = D.decide(base, Object.assign({}, strongIns, { pe_post: 20 }), hist, cfg, "2026-10-16").factors.valuation.s;
  const rich = D.decide(base, Object.assign({}, strongIns, { pe_post: 60 }), hist, cfg, "2026-10-16").factors.valuation.s;
  assert.ok(cheap > rich);
});

t("research: strong compounder at a discount -> high grade, Positive", () => {
  const ins = Object.assign({}, strongIns, { kpi_fy: { ROE: 24, ROCE: 30, "PAT Margin": 14, "EBITDA Margin": 22 }, promoter_post: 62, uses: ["capex"], mcap_cr: 2000,
    financials: { periods: ["31 Mar 2026", "31 Mar 2025", "31 Mar 2024"], "Total Income": [160, 125, 100], "Profit After Tax": [24, 17, 12], EBITDA: [36, 27, 20],
      "NET Worth": [120, 95, 80], "Total Borrowing": [10, 15, 20] } });
  const r = D.research(base, ins);
  assert.ok(r.grade >= 4, "grade " + r.grade);
  assert.equal(r.longTerm.call, "Positive");
  assert.equal(r.valuation.label, "Discount to peers");
  assert.ok(Math.abs(r.valuation.evEbitda - (2000 + 10) / 36) < 1e-9);
});

t("research: profit surge into the IPO is flagged, not rewarded", () => {
  const ins = { financials: { periods: ["31 Mar 2026", "31 Mar 2025"], "Total Income": [100, 90], "Profit After Tax": [12, 2], "NET Worth": [40, 30], "Total Borrowing": [5, 5] },
    kpi_fy: { ROE: 30, ROCE: 35, "PAT Margin": 12 }, pe_post: 14 };
  const r = D.research(base, ins);
  assert.ok(r.notes.some((n) => n.kind === "-" && /check it is sustainable/.test(n.t)));
  assert.ok(r.pillars.growth.s <= 0.6);
  assert.equal(r.valuation.peg, null);
});

t("research: loss-making, OFS-only, leveraged -> Cautious; December year-ends recognised", () => {
  const ins = { loss_making: true, issue_size_cr: 500, fresh_cr: 0, uses: ["ofs_only"], promoter_post: 30,
    financials: { periods: ["30 Jun 2026", "31 Dec 2025", "31 Dec 2024"], "Total Income": [20, 90, 100], "Profit After Tax": [-4, -8, 2], "NET Worth": [40, 45, 50], "Total Borrowing": [90, 80, 60] } };
  assert.deepEqual(D.fyCols(ins.financials), [1, 2]);
  const r = D.research(base, ins);
  assert.equal(r.longTerm.call, "Cautious");
  assert.equal(r.valuation.label, "Loss-making");
});

t("research: relative grades use per-segment quintiles", () => {
  const mk = (g) => ({ segment: "SME", kpi_fy: { ROE: g, ROCE: g, "PAT Margin": g / 2 }, financials: { periods: ["31 Mar 2026", "31 Mar 2025"], "Total Income": [100 + g, 100], "Profit After Tax": [10 + g / 4, 10], "NET Worth": [50, 45], "Total Borrowing": [10, 10] } });
  const list = Array.from({ length: 20 }, (_, i) => mk(i * 2));
  const cuts = D.gradeCuts(list);
  assert.ok(cuts.SME && !cuts.Mainboard);
  const grades = list.map((v) => D.research({ segment: "SME" }, v, cuts).grade);
  assert.ok(new Set(grades).size >= 3 && Math.min(...grades) === 1, "grades " + grades.join(","));
});

console.log(`\n${passed} tests passed`);
