#!/usr/bin/env node
/* IPO Decision Desk report: reproduces the dashboard's calls from its published data, no browser needed.
 *
 *   node ipo_report.js                       # data from the live GitHub Pages site
 *   node ipo_report.js --repo <path>         # data + engine from a local checkout of ipo-gmp-dashboard
 *   node ipo_report.js --live                # overlay fresh GMP / subscription straight from InvestorGain
 *   node ipo_report.js --ipo "tonbo"         # one IPO, full detail
 *   node ipo_report.js --json                # machine-readable output
 *   node ipo_report.js --segment SME         # filter: All | Mainboard | SME
 *
 * Engine: uses <repo>/decide.js + backtest.js when --repo is given (always current), otherwise the copies
 * bundled in ./engine (snapshot; refresh them after changing the engine).
 * Data is JSON only; no remote code is executed. Requires Node 18+ (global fetch).
 */
"use strict";
const fs = require("fs"), path = require("path");

const args = process.argv.slice(2);
const opt = (k, d) => { const i = args.indexOf(k); return i >= 0 && args[i + 1] && !args[i + 1].startsWith("--") ? args[i + 1] : d; };
const has = (k) => args.includes(k);
const REPO_ARG = opt("--repo", process.env.IPO_DESK_REPO || null), REPO = REPO_ARG ? path.resolve(REPO_ARG) : null;
const BASE = opt("--base-url", "https://djsoni99-ux.github.io/ipo-gmp-dashboard/");
const SEG = opt("--segment", "All"), ONE = (opt("--ipo", "") || "").toLowerCase();

const engineDir = REPO && fs.existsSync(path.join(REPO, "decide.js")) ? REPO : path.join(__dirname, "engine");
const B = require(path.join(engineDir, "backtest.js"));
const D = require(path.join(engineDir, "decide.js"));

async function load(name) {
  if (REPO) return JSON.parse(fs.readFileSync(path.join(REPO, name), "utf8"));
  const r = await fetch(BASE + name + "?t=" + Date.now(), { headers: { "User-Agent": "ipo-decision-desk-skill" } });
  if (!r.ok) throw new Error(name + " HTTP " + r.status);
  return r.json();
}
const IST = "Asia/Kolkata";
const todayIST = () => new Intl.DateTimeFormat("en-CA", { timeZone: IST }).format(new Date());
const strip = (h) => String(h || "").replace(/<[^>]+>/g, " ").replace(/&#8377;/g, "₹").replace(/&amp;/g, "&").replace(/\s+/g, " ").trim();
const num = (s) => { const m = String(s ?? "").match(/-?\d[\d,]*\.?\d*/); return m ? parseFloat(m[0].replace(/,/g, "")) : null; };
const inr = (n) => n == null || isNaN(n) ? "-" : (n < 0 ? "-" : "") + "Rs " + Math.abs(Math.round(n)).toLocaleString("en-IN");
const pc = (n, d = 0) => n == null || isNaN(n) ? "-" : (n > 0 ? "+" : "") + n.toFixed(d) + "%";

async function liveOverlay(ipos) {
  const t = todayIST(), [y, m] = t.split("-").map(Number), fy = m >= 4 ? `${y}-${String(y + 1).slice(2)}` : `${y - 1}-${String(y).slice(2)}`;
  const r = await fetch(`https://webnodejs.investorgain.com/cloud/v2/report/data-read/331/1/${m}/${y}/${fy}/0/all?search=&v=1`, { headers: { "User-Agent": "ipo-decision-desk-skill" } });
  const j = await r.json();
  if (j.msg !== 1) throw new Error("InvestorGain: unexpected response");
  const byId = new Map(ipos.filter((p) => p.ig_id).map((p) => [p.ig_id, p]));
  for (const row of j.reportTableData) {
    const p = byId.get(row["~id"]); if (!p) continue;
    const g = strip(row.GMP), mg = g.match(/₹\s*(-?[\d,.]+)/), rng = g.match(/(-?[\d.]+)\s*↓\s*\/\s*(-?[\d.]+)\s*↑/);
    if (mg) p.gmp = num(mg[1]);
    if (rng) { p.gmp_low = +rng[1]; p.gmp_high = +rng[2]; }
    const sub = num(row.Sub); if (sub != null) p.subscription_x = sub;
  }
  return j.reportTableData.length;
}
function statusOf(p, t) {
  if (p.listing_price != null || (p.listing && t >= p.listing)) return "listed";
  if (p.open && t < p.open) return "upcoming";
  if (p.close && t <= p.close) return p.open ? "open" : "upcoming";
  if (p.close && t > p.close) return "closed";
  return p.status || "upcoming";
}

(async () => {
  const [snap, hist, arch, insJ] = await Promise.all([load("ipo.json"), load("history.json").catch(() => ({})), load("archive.json"), load("insights.json").catch(() => ({ ipos: {} }))]);
  const ipos = snap.ipos || [];
  let liveRows = null;
  if (has("--live")) { try { liveRows = await liveOverlay(ipos); } catch (e) { liveRows = "failed: " + e.message; } }
  const t = todayIST(), cfg = Object.assign({}, B.DEFAULTS, { applyTax: false, mcRuns: 0 });
  const rows = B.ledger(arch.records || [], cfg), insList = Object.values(insJ.ipos || {}), cuts = D.gradeCuts(insList);
  const byIg = new Map(insList.filter((v) => v.ig_id).map((v) => [v.ig_id, v]));
  const ORDER = { APPLY: 0, LOTTERY: 1, CONSIDER: 2, WAIT: 3, SKIP: 4, CLOSED: 5 };
  const out = [];
  for (const p of ipos) {
    p.st = statusOf(p, t);
    if (p.st === "listed" || (SEG !== "All" && p.segment !== SEG)) continue;
    if (ONE && !p.name.toLowerCase().includes(ONE)) continue;
    const pts = hist[p.id] || [], prev = pts.slice().reverse().find((x) => x[1] !== p.gmp); p.trend = prev ? p.gmp - prev[1] : 0;
    const ins = byIg.get(p.ig_id) || (insJ.ipos || {})[String(p.ch_id)] || {};
    const c = D.decide(p, ins, rows, cfg, t), r = D.research(p, ins, cuts);
    out.push({ name: p.name, segment: p.segment, status: p.st, open: p.open, close: p.close, listing: p.listing,
      band: [ins.price_low || p.price_low, ins.price_high || p.price_high || p.price], gmp: p.gmp, gmpPct: p.price && p.gmp != null ? p.gmp / p.price * 100 : null, trend: p.trend,
      call: c.verdict, label: D.LABEL[c.verdict], score: c.score, confidence: c.confidence, odds: c.odds, ev: c.ev, invested: c.invested,
      scenarios: c.scenarios, factors: c.factors, reasons: c.reasons,
      research: { grade: r.grade, gradeLabel: r.grade ? D.GRADE[r.grade] : null, relative: r.relative, longTerm: r.longTerm, valuation: r.valuation, pillars: r.pillars, notes: r.notes, sponsorship: r.sponsorship },
      subscription: ins.sub || (p.subscription_x != null ? { total: p.subscription_x } : null), uses: ins.uses, objects: ins.objects });
  }
  out.sort((a, b) => ORDER[a.call] - ORDER[b.call] || (b.score || 0) - (a.score || 0));
  const meta = { date_ist: t, snapshot: snap.generated_at, live_overlay: liveRows, engine: engineDir === path.join(__dirname, "engine") ? "bundled copy" : engineDir, history_ipos: rows.length, analysed_ipos: insList.length };
  if (has("--json")) { console.log(JSON.stringify({ meta, ipos: out }, null, 2)); return; }

  console.log(`IPO Decision Desk report · ${t} IST · snapshot ${meta.snapshot}${liveRows != null ? " · live overlay: " + liveRows : ""}`);
  console.log(`History ${rows.length} listed IPOs · ${insList.length} analysed in depth · engine: ${meta.engine}\n`);
  if (!out.length) { console.log("No open, upcoming or closed-awaiting-listing IPOs match."); return; }
  console.log("| Call | IPO | Seg | Score | GMP | Odds | Expected/app | Bear / Base / Bull | Grade | Long-term |");
  console.log("|---|---|---|---|---|---|---|---|---|---|");
  for (const o of out) {
    const s = o.scenarios;
    console.log(`| ${o.label} | ${o.name} | ${o.segment === "SME" ? "SME" : "Main"} | ${o.score ?? "-"} | ${o.gmp == null ? "-" : inr(o.gmp) + " (" + pc(o.gmpPct) + ")"} | ${o.odds.p >= 0.995 ? "~certain" : "1 in " + o.odds.oneIn} (${o.odds.basis}) | ${inr(o.ev)} | ${s ? [s.bear, s.base, s.bull].map((x) => pc(x.pct)).join(" / ") : "-"} | ${o.research.grade ?? "-"}/5 | ${o.research.longTerm.call} |`);
  }
  for (const o of out) {
    if (!ONE && out.length > 3) break;
    const s = o.scenarios, v = o.research.valuation;
    console.log(`\n## ${o.name} · ${o.label} (score ${o.score}/100, confidence ${Math.round(o.confidence * 100)}%)`);
    console.log(`Status ${o.status}; open ${o.open} close ${o.close} listing ${o.listing}; band ${o.band.filter(Boolean).join("-")}`);
    if (s) console.log(`If allotted: bear ${pc(s.bear.pct)} (${inr(s.bear.net)}), base ${pc(s.base.pct)} (${inr(s.base.net)}), bull ${pc(s.bull.pct)} (${inr(s.bull.net)}) on ${inr(o.invested)}`);
    console.log("Factors: " + Object.entries(o.factors).map(([k, f]) => `${k} ${f.s.toFixed(2)} (${f.note})`).join("; "));
    console.log("Reasons: " + o.reasons.map((r) => r.kind + " " + r.t).join("; "));
    console.log(`Research: grade ${o.research.grade}/5 ${o.research.gradeLabel || ""}${o.research.relative ? " (relative to segment)" : ""}; valuation ${v.label || "-"} (P/E ${v.pe ?? "-"}, sector ${v.peerMed ? v.peerMed.toFixed(0) : "-"}, EV/EBITDA ${v.evEbitda ? v.evEbitda.toFixed(1) : "-"}, PEG ${v.peg ? v.peg.toFixed(2) : "-"}); long-term ${o.research.longTerm.call}: ${o.research.longTerm.why}`);
    if (o.research.notes.length) console.log("Research notes: " + o.research.notes.map((n) => n.kind + " " + n.t).join("; "));
  }
})().catch((e) => { console.error("ipo_report failed:", e.message); process.exit(1); });
