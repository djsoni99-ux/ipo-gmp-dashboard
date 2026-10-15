# Operations manual

## Architecture
```
GitHub Actions (UTC cron, no LLM)
  refresh.yml  hourly 02:00-17:00 UTC (07:30-22:30 IST) + 20:30 UTC (02:00 IST)
     fetch_ipo.py  -> ipo.json, history.json   (InvestorGain JSON + Chittorgarh JSON + IPO Watch HTML)
     insights.py   -> insights.json            (Chittorgarh detail + subscription pages)
     commit only if data changed (git pull --rebase --autostash before push)
  archive.yml  daily 16:00 UTC (21:30 IST), manual run accepts lo/hi id range for backfill
     node test_backtest.js && node test_decide.js
     build_archive.py -> archive.json         (InvestorGain per-IPO pages, rolling 13 months)
GitHub Pages (main branch root, public)
  index.html     Decision Desk: Today brief, Live calls list + analysis drawer, Plan, Track record (30 days)
  backtest.html  report: verdict + 5 chapters + method
  guide.html / IPO-Desk-Guide.pdf  plain-English guide
  ui.css         shared design system; backtest.js + decide.js shared engine
Browser: live overlay from InvestorGain every 3 min while visible; Refresh button forces it; snapshot re-read every 5 min.
```
Repository is flat: scripts, pages and data files at the root; `.github/workflows/`; this skill in `skills/ipo-decision-desk/`.

## Costs and limits
Free: public repo means unlimited Actions minutes and free Pages; no Claude tokens. GitHub cron is best-effort (runs can start 5-20 minutes late or be skipped). Scheduled workflows on a repo with no activity for 60 days can be paused; data commits keep it active; re-enable from the Actions tab if needed. Making the repo private needs GitHub Pro, and Pages would still be public unless on Enterprise.

## Local commands (Windows, from the repo folder)
```bash
python -X utf8 fetch_ipo.py              # snapshot
python -X utf8 insights.py               # fundamentals for active + last 35 days
python -X utf8 build_archive.py          # incremental archive
python -X utf8 build_archive.py --range 1350 2450 --workers 4   # rebuild the 13-month window
python -X utf8 build_archive.py --refresh                       # re-parse every record after a parser change
node test_backtest.js && node test_decide.js
python -m http.server 8630               # preview at http://localhost:8630 (Claude preview entry "ipo-gmp-dashboard" in the parent .claude/launch.json)
node skills/ipo-decision-desk/scripts/ipo_report.js --repo .   # calls in the terminal
```
Manual cloud run: GitHub > Actions > "Refresh IPO data" or "Update backtest archive" > Run workflow (or `gh workflow run refresh.yml`).

## Common changes
- **Schedule:** edit the cron lines in `.github/workflows/refresh.yml` (UTC; IST = UTC + 5:30). Every 2 hours: `"0 2-16/2 * * *"`.
- **Weights or thresholds:** `decide.js` (`W`, `PILLARS`, rules); update `references/methodology.md`, tests, and copy the engine into `skills/ipo-decision-desk/scripts/engine/`.
- **Cost assumptions:** `backtest.js` `DEFAULTS`; the backtest page also lets the user override them (stored in browser localStorage key `ipo-bt-prefs2`, which the Desk reads too).
- **History window:** `KEEP_MONTHS` in build_archive.py.
- **New data field:** parse in insights.py or fetch_ipo.py, use in decide.js, show in the drawer (`drawerIPO` / `researchHtml` in index.html).
- **Guide PDF:** edit guide.html, then print with Edge headless:
  `msedge --headless=new --disable-gpu --no-pdf-header-footer --user-data-dir=%TEMP%\pdfprof --print-to-pdf="...\IPO-Desk-Guide.pdf" file:///.../guide.html` (via PowerShell Start-Process -Wait).
- **GitHub About text / topics:** `gh repo edit djsoni99-ux/ipo-gmp-dashboard --description ... --add-topic ...`.

## Design system (ui.css)
Private-bank palette: cool off-white canvas `#F2F4F7` (the user rejected warm cream), white surfaces, navy ink `#0E1A2B`, muted gold accent `#A8844F`, emerald `#1D6B52` for good, burgundy `#9A2F2F` for bad, navy-blue for Consider, muted plum for SME/Lottery; dark mode tokens under `prefers-color-scheme`. Source Serif 4 for headlines and big figures, Inter with tabular figures for everything else. Hairlines instead of shadowed cards, sentence-case labels, verdict shown as a small coloured square plus a word, inline SVG line icons, no em-dashes in UI copy. Sticky app bar with section tracking, ranked list rows, slide-in analysis drawer (Esc closes, focus trap, `#ipo=<id>` deep links), Plan drawer, report layout with a contents rail on the backtest page. Muted text `#626A77` passes WCAG AA (4.95:1).

## Verification checklist after any change
1. Both test suites pass.
2. Preview locally: no console errors; desktop, 375 px mobile (no horizontal scroll), dark mode.
3. Push; Pages build "built"; run the relevant workflow manually and confirm green and the expected log lines ("wrote N IPOs", "insights: ... fetching N", "archive: N records").
4. Load the live page and confirm the new behaviour.
