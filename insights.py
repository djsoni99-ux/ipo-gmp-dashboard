#!/usr/bin/env python3
"""Build insights.json: per-IPO fundamentals, valuation, precedents and category-wise demand.

Source: Chittorgarh IPO detail + subscription pages (server-rendered HTML).
Covers every active IPO (open / upcoming / closed, refreshed each run) and every IPO listed in the
last RECENT_DAYS days (fetched once, then cached because listed data no longer changes).

Feeds the decision engine (decide.js): valuation vs precedent IPOs, demand quality (QIB / NII / retail),
offer structure (fresh vs OFS, promoter dilution), fundamentals and retail allotment odds.
Stdlib only.
"""
from __future__ import annotations

import html
import json
import re
import sys
import time
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import fetch_ipo as F

ROOT = Path(__file__).resolve().parent
OUT = ROOT / "insights.json"
IST = timezone(timedelta(hours=5, minutes=30))
RECENT_DAYS = 35
TAG = re.compile(r"<[^>]+>")


def txt(s: str) -> str:
    return re.sub(r"\s+", " ", html.unescape(TAG.sub(" ", s or ""))).strip()


def num(s):
    if s is None:
        return None
    s = str(s)
    if "-ve" in s:
        return None
    m = re.search(r"-?\d[\d,]*\.?\d*", s)
    return float(m.group().replace(",", "")) if m else None


def tables(h: str) -> list[list[list[str]]]:
    out = []
    for t in re.findall(r"<table\b.*?</table>", h, re.S):
        rows = [[txt(c) for c in re.findall(r"<t[dh]\b.*?</t[dh]>", tr, re.S)] for tr in re.findall(r"<tr\b.*?</tr>", t, re.S)]
        out.append([r for r in rows if r])
    return out


def find(tabs, key):
    return next((t for t in tabs if t and any(key in c for c in t[0])), None)


def kv(t) -> dict:
    return {r[0]: r[1] for r in (t or []) if len(r) >= 2}


def parse_detail(h: str) -> dict:
    tabs = tables(h)
    d: dict = {}
    basics = kv(find(tabs, "IPO Date") or next((t for t in tabs if any(r and r[0] == "Price Band" for r in t)), None))
    d["lot"] = num(basics.get("Lot Size"))
    d["sale_type"] = basics.get("Sale Type")
    size = kv(next((t for t in tabs if any(r and r[0].startswith("Total Issue Size") for r in t)), None))
    amt = lambda s: num((re.search(r"₹\s*([\d,.]+)\s*Cr", s or "") or [None, None])[1])  # noqa: E731
    d["issue_size_cr"] = amt(size.get("Total Issue Size"))
    pick = lambda pre: next((amt(v) for k, v in size.items() if k.startswith(pre) and amt(v) is not None), None)  # noqa: E731
    d["fresh_cr"], d["ofs_cr"] = pick("Fresh") or 0.0, pick("Offer for Sale") or 0.0
    st = (d["sale_type"] or "").lower()
    if d["issue_size_cr"] and "fresh" in st and "ofs" not in st:
        d["fresh_cr"], d["ofs_cr"] = d["issue_size_cr"], 0.0
    elif d["issue_size_cr"] and "ofs only" in st:
        d["fresh_cr"], d["ofs_cr"] = 0.0, d["issue_size_cr"]

    cat = find(tabs, "Investor Category")
    if cat:
        for r in cat[1:]:
            if r[0].startswith("Retail") and len(r) >= 5:
                d["retail_shares"], d["retail_max_allottees"] = num(r[1]), num(r[4])
                d["retail_pct"] = num(r[2])

    fin = find(tabs, "Period Ended")
    if fin:
        periods = fin[0][1:]
        rows = {r[0]: [num(x) for x in r[1:]] for r in fin[1:]}
        d["financials"] = {"periods": periods, **{k: rows.get(k) for k in ("Total Income", "Profit After Tax", "EBITDA", "NET Worth", "Total Borrowing", "Assets")}}

    peers = find(tabs, "Listing Gain/Loss")
    if peers:
        d["precedents"] = [{"name": r[0], "segment": "SME" if r[1] == "SME" else "Mainboard", "size_cr": num(r[2]), "price": num(r[3]),
                            "pe": num(r[4]), "listing_close": num(r[5]), "listing_gain_pct": num(r[6]), "ltp": num(r[7]) if len(r) > 7 else None}
                           for r in peers[1:] if len(r) >= 7]

    k = find(tabs, "KPI")
    if k:
        d["kpi"] = {r[0]: num(r[-1] if len(r) == 2 else r[1]) for r in k[1:] if len(r) >= 2}
        # first data column is the latest period; keep the latest full-year column too
        d["kpi_fy"] = {r[0]: num(r[2]) for r in k[1:] if len(r) >= 3}

    v = find(tabs, "Valuation Metric")
    if v:
        vv = {r[0]: r[1:] for r in v[1:]}
        g = lambda key, i: num(vv.get(key, [None, None])[i]) if vv.get(key) and len(vv[key]) > i else None  # noqa: E731
        d["eps_pre"], d["eps_post"] = g("EPS (₹)", 0), g("EPS (₹)", 1)
        d["pe_pre"], d["pe_post"] = g("P/E (x)", 0), g("P/E (x)", 1)
        d["mcap_cr"] = num((re.search(r"([\d,.]+)", (vv.get("Market Cap at Offer Price") or [""])[0] or "") or [None, None])[1])
        d["loss_making"] = "-ve" in " ".join(vv.get("EPS (₹)", []) + vv.get("P/E (x)", []))

    p = find(tabs, "Pre IPO")
    if p:
        for r in p[1:]:
            if r[0].startswith("Promoter") and len(r) >= 3:
                d["promoter_pre"], d["promoter_post"] = num(r[1]), num(r[2])

    rv = find(tabs, "Review By")
    if rv:
        for r in rv[1:]:
            if r[0] == "Brokers" and len(r) >= 5:
                d["reviews"] = {"subscribe": num(r[1]), "may_apply": num(r[2]), "neutral": num(r[3]), "avoid": num(r[4])}
    return d


def parse_subscription(h: str) -> dict:
    tabs = tables(h)
    d: dict = {}
    s = find(tabs, "Subscription (times)")
    if s:
        m = {r[0]: num(r[1]) for r in s[1:] if len(r) >= 2}
        ind = next((v for k, v in m.items() if "Individual" in k or k.startswith("Retail")), None)
        d["sub"] = {"qib": m.get("Qualified Institutional"), "nii": m.get("Non Institutional"),
                    "retail": ind, "total": m.get("Total Subscription") or m.get("Total")}
    a = next((t for t in tabs if any(r and r[0] == "Bid Date" for r in t)), None)
    if a:
        d["anchor"] = True
    dates = next((t for t in tabs if any(r and "Basis of Allotment" in r[0] for r in t)), None)
    if dates:
        for r in dates:
            if len(r) >= 2:
                try:
                    dt = datetime.strptime(r[1].split(", ", 1)[1], "%B %d, %Y").date().isoformat()
                except (IndexError, ValueError):
                    continue
                key = {"IPO opens On": "open", "IPO Closes On": "close", "Finalisation of Basis of Allotment": "allotment",
                       "Initiation of Refunds": "refund", "IPO Listing Date": "listing"}.get(r[0])
                if key:
                    d[key] = dt
    return d


def get(url: str) -> str | None:
    try:
        return F.http_get(url, attempts=2)
    except Exception as e:  # noqa: BLE001
        print(f"[warn] {url}: {e}", file=sys.stderr)
        return None


def build(ch_url: str) -> dict | None:
    h = get(ch_url)
    if not h:
        return None
    d = parse_detail(h)
    s = get(ch_url.replace("/ipo/", "/ipo_subscription/"))
    if s:
        d.update(parse_subscription(s))
    time.sleep(0.3)
    return d


def main() -> int:
    now = datetime.now(IST)
    today = now.date()
    old = json.loads(OUT.read_text("utf-8")) if OUT.exists() else {"ipos": {}}
    cache = old.get("ipos", {})
    prev = json.loads(json.dumps(cache))  # untouched copy for the change check
    snap = json.loads((ROOT / "ipo.json").read_text("utf-8")).get("ipos", []) if (ROOT / "ipo.json").exists() else []
    try:
        ch = F.fetch_chittorgarh(today)
    except Exception as e:  # noqa: BLE001
        print(f"[warn] chittorgarh list: {e}", file=sys.stderr)
        ch = []

    targets: dict[str, dict] = {}
    for p in snap:  # live window: active ones always refreshed
        if p.get("ch_url") and p.get("ch_id"):
            targets[str(p["ch_id"])] = {"name": p["name"], "segment": p["segment"], "ig_id": p.get("ig_id"),
                                        "ch_url": p["ch_url"], "active": p["status"] != "listed", "listing": p.get("listing")}
    cut = (today - timedelta(days=RECENT_DAYS)).isoformat()
    for c in ch:  # recently listed (and upcoming) from the Chittorgarh FY list
        if c.get("ch_id") and c.get("listing") and c["listing"] >= cut:
            targets.setdefault(str(c["ch_id"]), {"name": c["name"], "segment": c["segment"], "ig_id": None, "ch_url": c["ch_url"],
                                                 "active": c["listing"] > today.isoformat(), "listing": c["listing"]})

    todo = [k for k, t in targets.items() if t["active"] or k not in cache or not cache[k].get("final")]
    print(f"insights: {len(targets)} IPOs in scope, fetching {len(todo)}", flush=True)
    with ThreadPoolExecutor(3) as ex:
        for k, d in zip(todo, ex.map(lambda k: build(targets[k]["ch_url"]), todo)):
            if d:
                t = targets[k]
                d.update(name=t["name"], segment=t["segment"], ig_id=t["ig_id"], ch_id=int(k), ch_url=t["ch_url"],
                         final=bool(t["listing"]) and t["listing"] <= today.isoformat(), fetched_at=now.isoformat(timespec="seconds"))
                cache[k] = d
    keep = {k: v for k, v in cache.items() if k in targets}
    arch = json.loads((ROOT / "archive.json").read_text("utf-8")).get("records", []) if (ROOT / "archive.json").exists() else []
    for v in keep.values():  # link to InvestorGain ids so the dashboard can join with the archive
        if v.get("ig_id") or not v.get("listing"):
            continue
        L = date.fromisoformat(v["listing"])
        hit = next((r for r in arch if r.get("listing") and abs((date.fromisoformat(r["listing"]) - L).days) <= 3
                    and F.same_company(r["name"], v["name"])), None)
        if hit:
            v["ig_id"] = hit["id"]
    strip = lambda d: {k: {kk: vv for kk, vv in v.items() if kk != "fetched_at"} for k, v in d.items()}  # noqa: E731
    if strip(keep) == strip(prev):
        print(f"no change ({len(keep)} insight records)")
        return 0
    OUT.write_text(json.dumps({"generated_at": now.isoformat(timespec="seconds"), "ipos": keep}, ensure_ascii=False, separators=(",", ":")), "utf-8")
    print(f"wrote {len(keep)} insight records")
    return 0


if __name__ == "__main__":
    sys.exit(main())
