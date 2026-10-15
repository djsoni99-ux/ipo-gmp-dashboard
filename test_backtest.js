// node test_backtest.js : hand-computed golden cases for the backtest engine
"use strict";
const assert = require("node:assert/strict");
const B = require("./backtest.js");

const near = (a, b, tol = 1e-6, msg = "") => assert.ok(Math.abs(a - b) <= tol, `${msg} expected ${b}, got ${a}`);
let passed = 0;
const t = (name, fn) => { fn(); passed++; console.log("ok  " + name); };

// IPO A: Rs100, lot ticket 15,000 -> 150 shares, lists at 130; bid Mon 5 Jan 2026, lists Thu 8 Jan
const A = { id: 1, name: "A", segment: "Mainboard", price: 100, close: "2026-01-05", listing: "2026-01-08",
  listing_price: 130, listing_gain_pct: 30, gmp_close: 20, sub_final: 4, sub_close: 3, issue_size_cr: 600 };
const clean = { slippagePct: 0, applyTax: false, mcRuns: 0 };

// hand arithmetic for A (slippage 0): sell 19,500; brokerage 20; exch 19500*0.00325% = 0.63375; sebi 0.0195;
// gst 18% of (20+0.63375+0.0195) = 3.717585; stt 19.5; dp 15.93  -> charges 59.800835
const A_CHARGES = 20 + 0.63375 + 0.0195 + 3.717585 + 19.5 + 15.93;
const A_NET = 4500 - A_CHARGES;

t("ledger: shares, charges, net per allotment", () => {
  const [r] = B.ledger([A], clean);
  assert.equal(r.shares, 150);
  assert.equal(r.invested, 15000);
  near(r.charges, A_CHARGES, 1e-6, "charges");
  near(r.netAllot, A_NET, 1e-6, "net");
  near(r.p, 0.25, 1e-12, "p from subscription 4x");
});

t("timing: refund T+2, release listing+1 (weekday arithmetic)", () => {
  const [r] = B.ledger([A], clean);
  assert.equal(r.refund, "2026-01-07");
  assert.equal(r.release, "2026-01-09");
  assert.equal(r.dRefund, 2);
  assert.equal(r.dAllot, 4);
  assert.equal(B.addWd("2026-01-09", 1), "2026-01-12"); // Fri -> Mon
});

t("run: expected value, capital-days, blocked period, peak", () => {
  const out = B.run(B.ledger([A], clean), {}, clean);
  near(out.preTax, 0.25 * A_NET, 1e-6, "EV net");
  near(out.capitalDays, 2 * 15000 + 2 * 3750, 1e-6, "capital-days");
  near(out.avgBlockedDays, 2.5, 1e-9, "avg days blocked (2 + p*2)");
  near(out.peakCapital, 15000, 1e-9, "peak");
  near(out.annReturnPct, 0.25 * A_NET / 37500 * 365 * 100, 1e-6, "annualised");
});

t("tax: 20.8% on positive net, netted per financial year", () => {
  const cfg = { slippagePct: 0, mcRuns: 0 };
  const sure = Object.assign({}, A, { id: 2, sub_final: 1 }); // p = 1
  const lose = Object.assign({}, A, { id: 3, sub_final: 1, listing_price: 80, listing_gain_pct: -20, close: "2026-02-02", listing: "2026-02-05" });
  const rows = B.ledger([sure, lose], cfg);
  const net = rows.reduce((s, r) => s + r.netAllot, 0);
  const out = B.run(rows, {}, cfg);
  near(out.tax, Math.max(0, net) * 0.208, 1e-6, "tax on netted FY");
  assert.ok(net > 0 && out.tax < 0.208 * rows[0].netAllot, "loss reduces taxable base");
});

t("strategy filter: close-day GMP only, T+1 GMP only when allowed", () => {
  const hi = Object.assign({}, A, { id: 4, gmp_close: 20 });
  const lo = Object.assign({}, A, { id: 5, gmp_close: 5 });
  const none = Object.assign({}, A, { id: 6, gmp_close: null, gmp_post: 15, limited: true });
  const s = { minGmpPct: 10 };
  assert.deepEqual(B.run(B.ledger([hi, lo, none], clean), s, clean).n, 1);
  const allow = Object.assign({}, clean, { allowPost: true });
  assert.deepEqual(B.run(B.ledger([hi, lo, none], allow), s, allow).n, 2);
  assert.equal(B.run(B.ledger([hi, lo, none], clean), {}, clean).n, 3); // apply-to-all keeps limited pages
});

t("overlapping applications stack capital", () => {
  const x = Object.assign({}, A, { id: 7 }), y = Object.assign({}, A, { id: 8 });
  near(B.run(B.ledger([x, y], clean), {}, clean).peakCapital, 30000, 1e-9);
});

t("accounts scale capital and expected allotments", () => {
  const c2 = Object.assign({}, clean, { accounts: 3 });
  const o = B.run(B.ledger([A], c2), {}, c2);
  near(o.peakCapital, 45000, 1e-9);
  near(o.expAllotments, 0.75, 1e-12);
  near(o.preTax, 3 * 0.25 * A_NET, 1e-6);
});

t("Monte Carlo mean converges to expected value", () => {
  const recs = Array.from({ length: 40 }, (_, i) => Object.assign({}, A, { id: 100 + i }));
  const cfg = Object.assign({}, clean, { mcRuns: 20000 });
  const o = B.run(B.ledger(recs, cfg), {}, cfg);
  near(o.mc.mean / o.net, 1, 0.02, "MC/EV");
  assert.ok(o.mc.p10 < o.mc.p50 && o.mc.p50 < o.mc.p90);
  assert.equal(o.mc.pLoss, 0);
});

t("calibration: perfect linear GMP -> corr 1, bias 0", () => {
  const rows = [10, 20, 30, 40].map((g, i) => ({ id: i, price: 100, gmpList: g, gainPct: g, segment: "SME", sigKind: null }));
  const c = B.calibration(rows, "list");
  near(c.corr, 1, 1e-9); near(c.bias, 0, 1e-9); near(c.mae, 0, 1e-9);
  assert.equal(c.buckets.reduce((s, b) => s + b.n, 0), 4);
});

t("financial year labels", () => {
  assert.equal(B.fyOf("2026-03-31"), "FY25-26");
  assert.equal(B.fyOf("2026-04-01"), "FY26-27");
});

t("per-segment slippage: SME exits lower than mainboard on the same listing", () => {
  const sme = Object.assign({}, A, { id: 20, segment: "SME" });
  const cfg = { applyTax: false, mcRuns: 0 }; // defaults: Mainboard 0.5%, SME 2%
  const [m, s] = [B.ledger([A], cfg)[0], B.ledger([sme], cfg)[0]];
  near(m.sell / m.shares, 130 * 0.995, 1e-9);
  near(s.sell / s.shares, 130 * 0.98, 1e-9);
});

t("distribution + buckets + monthly partition the listed IPOs", () => {
  const mk = (id, gain, gmp, sub, close, listing) => Object.assign({}, A, { id, listing_price: 100 * (1 + gain / 100), listing_gain_pct: gain,
    gmp_list: gmp, sub_final: sub, close, listing });
  const rows = B.ledger([mk(30, -25, 0, 0.8, "2026-01-05", "2026-01-08"), mk(31, 5, 8, 2, "2026-01-12", "2026-01-15"),
    mk(32, 40, 30, 20, "2026-02-02", "2026-02-05"), mk(33, 120, 60, 150, "2026-02-09", "2026-02-12")], { mcRuns: 0 });
  const d = B.distribution(rows);
  assert.equal(d.reduce((s, b) => s + b.n, 0), 4);
  assert.equal(d.find((b) => b.label === "< -20%").n, 1);
  assert.equal(d.find((b) => b.label === "> 100%").n, 1);
  assert.equal(B.byBucket(rows, "gmp").reduce((s, b) => s + b.n, 0), 4);
  assert.equal(B.byBucket(rows, "sub").reduce((s, b) => s + b.n, 0), 4);
  const mo = B.monthly(rows);
  assert.deepEqual(mo.map((x) => x.label), ["2026-01", "2026-02"]);
  near(mo[0].avgGain, (-25 + 5) / 2, 1e-9);
  near(mo[0].posRate, 0.5, 1e-12);
});

t("similar(): widens tolerance until enough comparables, flags thin samples", () => {
  const recs = Array.from({ length: 10 }, (_, i) => Object.assign({}, A, { id: 40 + i, gmp_list: 10 + i, listing_gain_pct: 10 + i }));
  const rows = B.ledger(recs, { mcRuns: 0 });
  const s = B.similar(rows, "Mainboard", 14, 8);
  assert.ok(s.n >= 8 && !s.thin);
  assert.equal(B.similar(rows, "SME", 14, 8).n, 0);
});

t("loss-rate metrics on the selected strategy", () => {
  const mk = (id, gain) => Object.assign({}, A, { id, sub_final: 1, listing_price: 100 * (1 + gain / 100), listing_gain_pct: gain });
  const cfg = { mcRuns: 0, applyTax: false };
  const o = B.run(B.ledger([mk(50, -20), mk(51, 10), mk(52, 30), mk(53, 0)], cfg), {}, cfg);
  near(o.lossRate, 0.25, 1e-12); near(o.deepLossRate, 0.25, 1e-12); near(o.bigWinRate, 0.25, 1e-12);
});

t("odds-weighted gain exposes adverse selection", () => {
  const mk = (id, sub, gain) => Object.assign({}, A, { id, sub_final: sub, listing_price: 100 * (1 + gain / 100), listing_gain_pct: gain });
  const cfg = { mcRuns: 0, applyTax: false };
  const o = B.run(B.ledger([mk(60, 1, 0), mk(61, 10, 100)], cfg), {}, cfg); // p = 1 and 0.1
  near(o.avgGainPct, 50, 1e-9);                       // simple average flatters
  near(o.weightedGainPct, (1 * 0 + 0.1 * 100) / 1.1, 1e-9); // what you would actually get
});

console.log(`\n${passed} tests passed`);
