#!/usr/bin/env python3
"""Pull live IPO / GMP data from public sources and write ipo.json + history.json.

Standard library only, so a GitHub Actions run needs no pip install and uses
no LLM tokens.  Sources (the same JSON / HTML the sites render for themselves):

  investorgain  GMP, GMP range, subscription, lot size, rating, P/E   (JSON)
  chittorgarh   dates, price band, issue size, lead manager, venue     (JSON)
  ipowatch      a second, independent GMP opinion                      (HTML)

A source that fails is recorded in ipo.json["sources"] and skipped; the run only
fails (exit 1, previous snapshot kept) when no GMP source answered at all.
"""
from __future__ import annotations

import html
import json
import re
import sys
import time
import urllib.request
from datetime import date, datetime, timedelta, timezone
from difflib import SequenceMatcher
from pathlib import Path

ROOT = Path(__file__).resolve().parent
OUT = ROOT / "ipo.json"
HIST = ROOT / "history.json"

IST = timezone(timedelta(hours=5, minutes=30))
UA = "Mozilla/5.0 (compatible; ipo-gmp-dashboard/1.0; personal dashboard)"
LISTED_KEEP_DAYS = 14      # keep recently listed IPOs on the board this long
HIST_MAX_POINTS = 150      # GMP history points kept per IPO
HIST_KEEP_DAYS = 30        # drop history of IPOs not seen for this long

TAG = re.compile(r"<[^>]+>")


# ---------------------------------------------------------------- helpers
def http_get(url: str, referer: str | None = None, attempts: int = 3) -> str:
    headers = {"User-Agent": UA, "Accept": "*/*"}
    if referer:
        headers["Referer"] = referer
    last: Exception | None = None
    for i in range(attempts):
        try:
            req = urllib.request.Request(url, headers=headers)
            with urllib.request.urlopen(req, timeout=30) as r:
                return r.read().decode("utf-8", "replace")
        except Exception as e:  # noqa: BLE001 - any network failure is retried
            last = e
            time.sleep(2 * (i + 1))
    raise RuntimeError(f"{url} -> {last}")


def text(s: str | None) -> str:
    return re.sub(r"\s+", " ", html.unescape(TAG.sub(" ", s or ""))).strip()


def num(s) -> float | None:
    m = re.search(r"-?\d[\d,]*\.?\d*", str(s or ""))
    return float(m.group().replace(",", "")) if m else None


def iso(s: str | None) -> str | None:
    m = re.match(r"(\d{4}-\d{2}-\d{2})", s or "")
    return m.group(1) if m else None


def fy_label(d: date) -> str:
    y = d.year if d.month >= 4 else d.year - 1
    return f"{y}-{str(y + 1)[2:]}"


def clean(d: dict) -> dict:
    return {k: v for k, v in d.items() if v is not None}


# ---------------------------------------------------------------- sources
def fetch_investorgain(today: date) -> list[dict]:
    url = (
        "https://webnodejs.investorgain.com/cloud/v2/report/data-read/331/1/"
        f"{today.month}/{today.year}/{fy_label(today)}/0/all?search=&v=1"
    )
    d = json.loads(http_get(url, "https://www.investorgain.com/"))
    if d.get("msg") != 1:
        raise RuntimeError(f"unexpected response: {str(d)[:120]}")
    rows = []
    for r in d["reportTableData"]:
        gtxt = text(r.get("GMP"))
        m_gmp = re.search(r"₹\s*(-?[\d,.]+)", gtxt)
        rng = re.search(r"(-?[\d.]+)\s*↓\s*/\s*(-?[\d.]+)\s*↑", gtxt)
        badges = [text(b) for b in re.findall(r'<span class="badge[^>]*>(.*?)</span>', r.get("Name", ""))]
        code = r.get("~ipo_status1") or ""
        listed = re.search(r"L@\s*([\d.]+)\s*\(\s*([-+]?[\d.]+)\s*%", text(r.get("Name")))
        rows.append(clean({
            "ig_id": r.get("~id"),
            "name": r.get("~ipo_name") or text(r.get("Name")),
            "segment": "SME" if r.get("~ipo_category1") == "SME" else "Mainboard",
            "exchange": badges[0] if badges and badges[0] != "IPO" else None,
            "code": code,
            "gmp": num(m_gmp.group(1)) if m_gmp else 0.0,
            "gmp_pct": num(r.get("~gmp_percent_calc")),
            "gmp_low": float(rng.group(1)) if rng else None,
            "gmp_high": float(rng.group(2)) if rng else None,
            "gmp_open": next(iter(re.findall(r"GMP:\s*(-?[\d.]+)", r.get("Open", ""))), None),
            "gmp_close": next(iter(re.findall(r"GMP:\s*(-?[\d.]+)", r.get("Close", ""))), None),
            "subscription_x": num(r.get("Sub")),
            "price": num(r.get("Price (₹)")),
            "lot": int(num(r.get("Lot"))) if num(r.get("Lot")) else None,
            "issue_size_cr": num(r.get("IPO Size")),
            "pe": num(r.get("~P/E")),
            "rating": text(r.get("&#128293;Rating") or r.get("🔥Rating")).count("🔥") or None,
            "anchor": True if "✅" in (r.get("Anchor") or "") else None,
            "open": iso(r.get("~Srt_Open")),
            "close": iso(r.get("~Srt_Close")),
            "allotment": iso(r.get("~Srt_BoA_Dt")),
            "listing": iso(r.get("~Str_Listing")),
            "gmp_updated": text(r.get("Updated-On")),
            "listing_price": float(listed.group(1)) if listed else None,
            "listing_gain_pct": float(listed.group(2)) if listed else None,
            "ig_url": ("https://www.investorgain.com" + r["~urlrewrite_folder_name"])
            if r.get("~urlrewrite_folder_name") else None,
        }))
    for r in rows:  # phase GMPs come out of regex as strings
        for k in ("gmp_open", "gmp_close"):
            if k in r:
                r[k] = float(r[k])
    return rows


def fetch_chittorgarh(today: date) -> list[dict]:
    url = (
        "https://webnodejs.chittorgarh.com/cloud/report/data-read/82/1/"
        f"{today.month}/{today.year}/{fy_label(today)}/0/all?search=&v=1"
    )
    d = json.loads(http_get(url, "https://www.chittorgarh.com/"))
    if d.get("msg") == -1:  # no rows yet in this financial year
        return []
    if d.get("msg") != 1:
        raise RuntimeError(f"unexpected response: {str(d)[:120]}")
    rows = []
    for r in d["reportTableData"]:
        a = re.search(r'<a [^>]*href="([^"]+)"[^>]*>(.*?)</a>', r.get("Company", ""), re.S)
        if not a:
            continue
        link, name = a.group(1), text(a.group(2))
        nums = re.findall(r"\d+(?:\.\d+)?", r.get("Issue Price (Rs.)", ""))
        ch_id = re.search(r"/(\d+)/?$", link)
        rows.append(clean({
            "ch_id": int(ch_id.group(1)) if ch_id else None,
            "name": name,
            "segment": "SME" if r.get("Issue Category") == "SME" else "Mainboard",
            "price_low": float(nums[0]) if nums else None,
            "price_high": float(nums[-1]) if nums else None,
            "issue_size_cr": num(r.get("Issue Amount (Rs.cr.)")),
            "fresh_cr": num(r.get("Fresh Capital (Rs.cr.)")),
            "ofs_cr": num(r.get("Offer for sale (Rs.cr.)")),
            "pricing": r.get("Pricing Method") or None,
            "venue": r.get("Listing at") or None,
            "lead_manager": text(r.get("Left Lead Manager")) or None,
            "open": iso(r.get("~Issue_Open_Date")),
            "close": iso(r.get("~IssueCloseDate")),
            "listing": iso(r.get("~ListingDate")),
            "ch_url": link,
        }))
    return rows


def fetch_ipowatch() -> list[dict]:
    h = http_get("https://ipowatch.in/ipo-grey-market-premium-latest-ipo-gmp/")
    rows = []
    for t in re.finditer(r"<table\b.*?</table>", h, re.S):
        if "GMP" not in t.group():
            continue
        before = text(h[max(0, t.start() - 600):t.start()])
        segment = "SME" if before.rfind("SME") > before.rfind("Mainboard") else "Mainboard"
        for tr in re.findall(r"<tr\b.*?</tr>", t.group(), re.S):
            tds = re.findall(r"<td\b.*?</td>", tr, re.S)
            if len(tds) < 6:
                continue
            a = re.search(r'<a [^>]*href="([^"]+)"[^>]*>(.*?)</a>', tds[0], re.S)
            if not a:
                continue
            est = re.search(r"\(([-\d.]+)\s*%\)", text(tds[4]))
            rows.append(clean({
                "name": text(a.group(2)),
                "segment": segment,
                "status_text": text(tds[0].replace(a.group(0), "")),
                "gmp": num(text(tds[1])) or 0.0,
                "price": num(text(tds[3])),
                "gmp_pct": float(est.group(1)) if est else None,
                "dates_text": text(tds[5]),
                "url": a.group(1),
            }))
    return rows


# ---------------------------------------------------------------- merge
STOP = {"ipo", "ltd", "limited", "pvt", "private", "public", "co", "corp", "corporation", "inc"}


def tokens(name: str) -> list[str]:
    s = html.unescape(name).lower().replace("&", " and ")
    words = [t for t in re.sub(r"[^a-z0-9 ]+", " ", s).split() if t not in STOP]
    return [w[:-1] if len(w) > 4 and w.endswith("s") else w for w in words]  # ultrasonics ~ ultrasonic


def same_company(a: str, b: str) -> bool:
    ta, tb = tokens(a), tokens(b)
    if not ta or not tb:
        return False
    short, long_ = (ta, tb) if len(ta) <= len(tb) else (tb, ta)
    return long_[: len(short)] == short


def find_match(name: str, segment: str, pool: list[dict], used: set[int], open_date: str | None = None):
    best, best_score = None, None
    for i, c in enumerate(pool):
        if i in used or not same_company(name, c["name"]):
            continue
        score = (
            int(c.get("segment") == segment) * 2 + int(bool(open_date) and c.get("open") == open_date),
            SequenceMatcher(None, " ".join(tokens(name)), " ".join(tokens(c["name"]))).ratio(),
        )
        if best_score is None or score > best_score:
            best, best_score = i, score
    return best


def status_of(p: dict, today: date) -> str:
    code = p.get("code", "")
    if code.startswith("L"):
        return "listed"
    o, c, l = (date.fromisoformat(p[k]) if p.get(k) else None for k in ("open", "close", "listing"))
    if l and today >= l:
        return "listed"
    if o and today < o:
        return "upcoming"
    if c and today <= c:
        return "open" if o else "upcoming"
    if c and today > c:
        return "closed"
    return {"U": "upcoming", "O": "open", "C": "closed"}.get(code, "upcoming")


def slug(name: str) -> str:
    return "-".join(tokens(name)) or "ipo"


def merge(ig: list[dict], ch: list[dict], iw: list[dict], today: date) -> list[dict]:
    used_ch: set[int] = set()
    used_iw: set[int] = set()
    out: list[dict] = []

    for r in ig:
        p = dict(r)
        j = find_match(p["name"], p["segment"], ch, used_ch, p.get("open"))
        if j is not None:
            used_ch.add(j)
            c = ch[j]
            for k in ("ch_id", "ch_url", "price_low", "price_high", "fresh_cr", "ofs_cr", "pricing", "venue", "lead_manager"):
                if k in c:
                    p[k] = c[k]
            for k in ("open", "close", "listing", "issue_size_cr"):  # Chittorgarh is authoritative
                if c.get(k):
                    p[k] = c[k]
            if c.get("price_high"):
                p["price"] = c["price_high"]
        out.append(p)

    for i, c in enumerate(ch):  # on Chittorgarh but not (yet) on InvestorGain
        if i in used_ch:
            continue
        keep = bool(c.get("close")) and date.fromisoformat(c["close"]) >= today - timedelta(days=1)
        if c.get("listing"):
            keep = keep or today - timedelta(days=LISTED_KEEP_DAYS) <= date.fromisoformat(c["listing"]) <= today
        if keep:
            p = dict(c)
            p["price"] = c.get("price_high")
            out.append(p)

    for p in out:  # second GMP opinion
        j = find_match(p["name"], p["segment"], iw, used_iw)
        if j is not None:
            used_iw.add(j)
            w = iw[j]
            p["gmp_alt"] = clean({"gmp": w["gmp"], "pct": w.get("gmp_pct"), "source": "IPO Watch"})
            p["iw_url"] = w.get("url")
            if "gmp" not in p:  # InvestorGain missing -> promote the alt as primary
                p["gmp"], p["gmp_pct"] = w["gmp"], w.get("gmp_pct")
                p["gmp_source"] = "IPO Watch"
            if not p.get("price") and w.get("price"):
                p["price"] = w["price"]

    for i, w in enumerate(iw):  # on IPO Watch only (typically very early upcoming issues)
        if i in used_iw or w.get("status_text", "").lower().startswith(("listed", "closed")):
            continue
        out.append(clean({
            "name": w["name"], "segment": w["segment"], "gmp": w["gmp"], "gmp_pct": w.get("gmp_pct"),
            "gmp_source": "IPO Watch", "price": w.get("price"), "iw_url": w.get("url"),
            "dates_text": w.get("dates_text"), "code": "U" if "upcoming" in w.get("status_text", "").lower() else "O",
        }))

    final = []
    for p in out:
        p["status"] = status_of(p, today)
        if p["status"] == "listed" and p.get("listing"):
            if date.fromisoformat(p["listing"]) < today - timedelta(days=LISTED_KEEP_DAYS):
                continue
        p["id"] = f"ig{p['ig_id']}" if p.get("ig_id") else f"ch{p['ch_id']}" if p.get("ch_id") else slug(p["name"])
        p.pop("code", None)
        final.append(p)

    order = {"open": 0, "upcoming": 1, "closed": 2, "listed": 3}
    final.sort(key=lambda p: (order[p["status"]], -(p.get("gmp_pct") or -999), p["name"]))
    return final


# ---------------------------------------------------------------- history
def update_history(ipos: list[dict], now: datetime) -> dict:
    hist = json.loads(HIST.read_text("utf-8")) if HIST.exists() else {}
    stamp = now.strftime("%Y-%m-%dT%H:%M")
    for p in ipos:
        if p.get("gmp") is None:
            continue
        pts = hist.setdefault(p["id"], [])
        if not pts or pts[-1][1] != p["gmp"]:
            pts.append([stamp, p["gmp"]])
        del pts[:-HIST_MAX_POINTS]
    cutoff = (now - timedelta(days=HIST_KEEP_DAYS)).strftime("%Y-%m-%dT%H:%M")
    live = {p["id"] for p in ipos}
    return {k: v for k, v in hist.items() if k in live or (v and v[-1][0] >= cutoff)}


# ---------------------------------------------------------------- output
def volatile_stripped(payload: dict) -> dict:
    q = json.loads(json.dumps(payload))
    q.pop("generated_at", None)
    for s in q.get("sources", {}).values():
        s.pop("fetched_at", None)
    return q


def write_payload(payload: dict) -> None:
    lines = [json.dumps(p, ensure_ascii=False, separators=(",", ":")) for p in payload["ipos"]]
    head = json.dumps({k: v for k, v in payload.items() if k != "ipos"}, ensure_ascii=False, indent=1)
    OUT.write_text(head[:-2] + ',\n "ipos": [\n' + ",\n".join(lines) + "\n ]\n}\n", "utf-8")


def main() -> int:
    now = datetime.now(IST)
    today = now.date()
    sources, data = {}, {"investorgain": [], "chittorgarh": [], "ipowatch": []}
    for key, fn in (
        ("investorgain", lambda: fetch_investorgain(today)),
        ("chittorgarh", lambda: fetch_chittorgarh(today)),
        ("ipowatch", fetch_ipowatch),
    ):
        try:
            data[key] = fn()
            sources[key] = {"ok": True, "rows": len(data[key]), "fetched_at": now.isoformat(timespec="seconds")}
        except Exception as e:  # noqa: BLE001
            sources[key] = {"ok": False, "rows": 0, "error": str(e)[:200], "fetched_at": now.isoformat(timespec="seconds")}
            print(f"[warn] {key}: {e}", file=sys.stderr)

    if not (sources["investorgain"]["ok"] or sources["ipowatch"]["ok"]):
        print("[error] no GMP source answered; keeping previous snapshot", file=sys.stderr)
        return 1

    ipos = merge(data["investorgain"], data["chittorgarh"], data["ipowatch"], today)
    if not ipos:
        print("[error] merge produced no IPOs; keeping previous snapshot", file=sys.stderr)
        return 1

    payload = {"generated_at": now.isoformat(timespec="seconds"), "sources": sources, "ipos": ipos}
    if OUT.exists():
        try:
            old = json.loads(OUT.read_text("utf-8"))
            if volatile_stripped(old) == volatile_stripped(payload):
                print(f"no change ({len(ipos)} IPOs)")
                return 0
        except json.JSONDecodeError:
            pass

    hist = update_history(ipos, now)
    HIST.write_text(json.dumps(hist, ensure_ascii=False, separators=(",", ":")), "utf-8")
    write_payload(payload)
    by = {s: sum(1 for p in ipos if p["status"] == s) for s in ("open", "upcoming", "closed", "listed")}
    print(f"wrote {len(ipos)} IPOs {by} @ {now:%d %b %H:%M} IST")
    return 0


if __name__ == "__main__":
    sys.exit(main())
