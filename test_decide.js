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

console.log(`\n${passed} tests passed`);
