#!/usr/bin/env python3
"""Build archive.json: one record per IPO with point-in-time GMP and the real listing result.

Source: InvestorGain per-IPO pages (server-rendered, slug-agnostic):
    https://www.investorgain.com/gmp/ipo/{id}/
Each page has a daily GMP table whose date cell carries markers
(O=open, C=close, A=allotment, LP@/LN@=listing result) and, on recent pages, `Sub: 12.3x`.
Row text has no year, so it is anchored on the JSON-LD "Grey Market Premium - YYYY-MM-DD" dates.

    python build_archive.py                  incremental: unfinished ids + new ids above the max seen
    python build_archive.py --range 700 2400 full / resumable backfill (skips ids already final or known-empty)

Stdlib only.  Lot size / issue size / final subscription are merged from ipo.json (rolling window) when present.
"""
from __future__ import annotations

import argparse
import html
import json
import re
import sys
import time
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent
ARCH, SNAP = ROOT / "archive.json", ROOT / "ipo.json"
URL = "https://www.investorgain.com/gmp/ipo/{}/"
UA = "Mozilla/5.0 (compatible; ipo-gmp-dashboard/1.0; personal dashboard)"
IST = timezone(timedelta(hours=5, minutes=30))
MON = {m: i + 1 for i, m in enumerate("Jan Feb Mar Apr May Jun Jul Aug Sep Oct Nov Dec".split())}
TAG = re.compile(r"<[^>]+>")
HEADER = re.compile(r"Opened - (\d{1,2})\w{2} ([A-Za-z]{3}) (\d{4}).{0,40}?Closed - (\d{1,2})\w{2} ([A-Za-z]{3}) (\d{4})"
                    r"(?:.{0,40}?Listed - (\d{1,2})\w{2} ([A-Za-z]{3}) (\d{4}))?")


def txt(s: str) -> str:
    return re.sub(r"\s+", " ", html.unescape(TAG.sub(" ", s or ""))).strip()


def fnum(s) -> float | None:
    m = re.search(r"-?\d[\d,]*\.?\d*", str(s or ""))
    return float(m.group().replace(",", "")) if m else None


def fetch(i: int) -> str | None:
    for k in range(3):
        try:
            req = urllib.request.Request(URL.format(i), headers={"User-Agent": UA})
            with urllib.request.urlopen(req, timeout=30) as r:
                return r.read().decode("utf-8", "replace")
        except urllib.error.HTTPError as e:
            if e.code == 404:
                return None
        except Exception:  # noqa: BLE001
            pass
        time.sleep(2 * (k + 1))
    return None


KEEP_MONTHS = 13  # rolling window: older IPOs are pruned on every run


def window_start(today: date | None = None) -> str:
    t = today or datetime.now(IST).date()
    m = t.month - KEEP_MONTHS
    return date(t.year + (m - 1) // 12, (m - 1) % 12 + 1, min(t.day, 28)).isoformat()


def in_window(r: dict, cut: str) -> bool:
    return max((v for v in (r.get("listing"), r.get("close"), r.get("open")) if v), default="") >= cut


def add_wd(d: date, n: int) -> date:  # weekday arithmetic (no holiday calendar)
    step = 1 if n >= 0 else -1
    while n:
        d += timedelta(days=step)
        if d.weekday() < 5:
            n -= step
    return d


def parse(i: int, h: str):
    """-> (record | None, skip_reason | None)"""
    title = re.search(r"<title>(.*?)</title>", h, re.S)
    name = re.sub(r"\s+IPO GMP.*$", "", txt(title.group(1))) if title else f"IPO {i}"
    tabs = re.findall(r"<table\b.*?</table>", h, re.S)
    t0 = next((t for t in tabs if "GMP Date" in t), None)
    if not t0:
        return None, "no-table"
    price = fnum((re.search(r"upper price-\s*₹\s*([\d,.]+)", txt(t0)) or [None, None])[1])
    anchors = sorted(set(re.findall(r"Grey Market Premium — (\d{4}-\d{2}-\d{2})", h)))
    body = TAG.sub(" ", re.sub(r"<script.*?</script>", "", h, flags=re.S))
    seg = "SME" if re.search(r"\b(?:NSE|BSE) SME\b", body) else "Mainboard" if re.search(r"\bBSE, NSE\b|\bNSE, BSE\b", body) else None
    raw = []
    for tr in re.findall(r"<tr\b.*?</tr>", t0, re.S)[1:]:
        c = [txt(x) for x in re.findall(r"<t[dh]\b.*?</t[dh]>", tr, re.S)]
        m = re.match(r"(\d{1,2})-([A-Za-z]{3})\s+\d{1,2}:\d{2}\s*(.*)$", c[0]) if c else None
        if not m or m.group(2) not in MON:
            continue
        g = re.search(r"₹\s*(-?[\d,.]+)", c[1]) if len(c) > 1 else None
        rest = m.group(3)
        lst = re.search(r"L[PN]?@?\s*₹?\s*([\d.,]+)\s*\(\s*(-?[\d.]+)\s*%\)", rest)
        sub = re.search(r"Sub:\s*([\d.]+)x", rest)
        raw.append(dict(d=int(m.group(1)), m=MON[m.group(2)], gmp=fnum(g.group(1)) if g else None,
                        mk=set(re.findall(r"\b([OCA])\b", rest)), lp=lst, sub=float(sub.group(1)) if sub else None))
    if len(raw) < 2 or price is None or seg is None or not anchors:
        return None, "no-rows" if len(raw) < 2 else "no-price/segment/year"
    # year anchoring: newest row == latest JSON-LD date; walk back, month increase => previous year
    a = date.fromisoformat(anchors[-1])
    y = a.year if (raw[0]["m"], raw[0]["d"]) <= (a.month, a.day) else a.year - 1
    prev_m = raw[0]["m"]
    rows = []
    for r in raw:
        if r["m"] > prev_m:
            y -= 1
        prev_m = r["m"]
        try:
            rows.append({**r, "date": date(y, r["m"], r["d"])})
        except ValueError:
            continue
    rows.sort(key=lambda r: r["date"])
    by_day = {}
    for r in rows:  # last update of each day wins
        by_day[r["date"]] = r
    days = sorted(by_day)
    mk = lambda k: next((r["date"] for r in rows if k in r["mk"]), None)  # noqa: E731
    lp = next((r for r in rows if r["lp"]), None)
    listing = lp["date"] if lp else None
    close = mk("C") or (add_wd(mk("A"), -1) if mk("A") else None) or (add_wd(listing, -3) if listing else None)
    opened = mk("O") or (days[0] if days else None)
    # The page header states exact dates ("Opened - 25th Sep 2025 Closed - 29th Sep 2025 Listed - 3rd Oct 2025"),
    # even on paywalled pages; prefer them to the marker-derived ones.
    hd = HEADER.search(re.sub(r"\s+", " ", body))
    if hd:
        g = hd.groups()
        dt = lambda d, m, y: date(int(y), MON[m], int(d))  # noqa: E731
        try:
            opened, close = dt(*g[0:3]), dt(*g[3:6])
            if g[6]:
                listing = dt(*g[6:9])
        except (KeyError, ValueError):
            hd = None
    # Old pages are paywalled to the last 3 readings ("Preview Limited"): never pretend those are open/close-day GMPs.
    limited = "Preview Limited" in t0
    exact = lambda d: by_day[d]["gmp"] if d in by_day else None  # noqa: E731
    upto = lambda d: next((by_day[x]["gmp"] for x in reversed(days) if x <= d and by_day[x]["gmp"] is not None), None)  # noqa: E731
    gmp_at = exact if limited else upto
    post = next((x for x in days if close and x > close and by_day[x]["gmp"] is not None), None)
    rec = {
        "id": i, "name": name, "segment": seg, "price": price, "limited": limited,
        "open": opened.isoformat() if opened and (hd or mk("O") or not limited) else None,
        "close": close.isoformat() if close else None,
        "listing": listing.isoformat() if listing else None,
        "dates_exact": bool(hd),
        "gmp_open": gmp_at(opened) if opened and (hd or mk("O") or not limited) else None,
        "gmp_close": gmp_at(close) if close else None,
        "gmp_post": by_day[post]["gmp"] if post else None,
        "gmp_list": by_day[listing]["gmp"] if listing in by_day else None,
        "sub_close": by_day[close]["sub"] if close in by_day else None,
        "listing_price": float(lp["lp"].group(1).replace(",", "")) if lp else None,
        "listing_gain_pct": float(lp["lp"].group(2)) if lp else None,
        "series": [[d.isoformat(), by_day[d]["gmp"]] for d in days],
    }
    return rec, None


def merge_snapshot(recs: dict) -> None:
    """Enrich with lot / issue size / final subscription from the live snapshot (ig_id keyed)."""
    if not SNAP.exists():
        return
    for p in json.loads(SNAP.read_text("utf-8")).get("ipos", []):
        r = recs.get(p.get("ig_id"))
        if r:
            for src, dst in (("lot", "lot"), ("issue_size_cr", "issue_size_cr"), ("subscription_x", "sub_final"), ("exchange", "exchange")):
                if p.get(src) is not None:
                    r[dst] = p[src]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--range", nargs=2, type=int, metavar=("LO", "HI"))
    ap.add_argument("--workers", type=int, default=3)
    ap.add_argument("--refresh", action="store_true", help="re-fetch records that are not paywalled or lack exact dates")
    a = ap.parse_args()

    db = json.loads(ARCH.read_text("utf-8")) if ARCH.exists() else {"records": [], "skipped": {}}
    recs = {r["id"]: r for r in db["records"]}
    skipped = {int(k): v for k, v in db.get("skipped", {}).items()}
    top = max(list(recs) + list(skipped) + [0])
    cut = window_start()
    recs = {i: r for i, r in recs.items() if in_window(r, cut)}
    low = min(recs) if recs else 0
    skipped = {i: v for i, v in skipped.items() if i >= low - 100}

    def save():
        merge_snapshot(recs)
        out = sorted(recs.values(), key=lambda r: r["id"])
        head = {"generated_at": datetime.now(IST).isoformat(timespec="seconds"), "max_id": top,
                "skipped": {str(k): v for k, v in sorted(skipped.items())}}
        lines = [json.dumps(r, ensure_ascii=False, separators=(",", ":")) for r in out]
        ARCH.write_text(json.dumps(head, ensure_ascii=False)[:-1] + ',"records":[\n' + ",\n".join(lines) + "\n]}\n", "utf-8")

    def work(i):
        h = fetch(i)
        time.sleep(0.3)
        return i, (parse(i, h) if h else (None, "http"))

    def scan(ids):
        nonlocal top
        got = new = 0
        with ThreadPoolExecutor(a.workers) as ex:
            for n, (i, (rec, why)) in enumerate(ex.map(work, ids), 1):
                top = max(top, i)
                if rec and not in_window(rec, cut):
                    skipped[i] = "old"
                elif rec:
                    recs[i] = rec
                    skipped.pop(i, None)
                    new += 1
                else:
                    skipped[i] = why
                got += 1
                if n % 100 == 0:
                    save()
                    print(f"  ..{n}/{len(ids)} scanned, {len(recs)} records", flush=True)
        return got, new

    if a.range:
        lo, hi = a.range
        ids = [i for i in range(lo, hi + 1) if not (i in recs and recs[i].get("listing_price") is not None) and i not in skipped]
        print(f"backfill {lo}-{hi}: {len(ids)} ids to scan", flush=True)
    elif a.refresh:
        ids = sorted(i for i, r in recs.items() if not r.get("limited") or not r.get("dates_exact"))
        print(f"refresh: {len(ids)} records", flush=True)
    else:
        unfinished = [i for i, r in recs.items() if r.get("listing_price") is None]
        recent_skips = [i for i in skipped if i > top - 80]
        ids = sorted(set(unfinished + recent_skips))
        print(f"incremental: {len(ids)} unfinished/recent ids", flush=True)
    scanned, new = scan(ids)
    if not a.range:  # walk forward from the highest id until 12 consecutive empties
        i, misses = top + 1, 0
        while misses < 12:
            _, (rec, why) = work(i)
            top = max(top, i)
            if rec:
                recs[i], misses, new = rec, 0, new + 1
            else:
                skipped[i], misses = why, misses + 1
            i += 1
    save()
    fin = sum(1 for r in recs.values() if r.get("listing_price") is not None)
    print(f"archive: {len(recs)} records ({fin} with listing result), {len(skipped)} skipped ids, max_id {top}; this run +{new}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
