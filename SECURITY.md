# Security policy

IPO Decision Desk is a personal, open-source project: a static site on GitHub Pages fed by
scheduled GitHub Actions. It has no server, no user accounts, no database, no cookies and no
stored secrets. Even so, reports that help keep the site and its visitors safe are welcome.

## Supported versions

Only the `main` branch, which is what the live site at
https://djsoni99-ux.github.io/ipo-gmp-dashboard/ serves, is supported. Older commits do not
receive fixes.

## Reporting a vulnerability

**Please do not open a public issue for security problems.**

1. Go to the repository's **Security** tab and choose **Report a vulnerability**
   (https://github.com/djsoni99-ux/ipo-gmp-dashboard/security/advisories/new).
   This opens a private advisory that only the maintainer can see.
2. If that option is not available to you, open a short public issue titled
   "Security contact request" **without any details**, and the maintainer will reply with a
   private channel.

Please include:
- what is affected (page, script, workflow or skill file) and the commit or date you tested;
- steps to reproduce, or a proof of concept;
- the impact you expect (for example, script running in a visitor's browser).

## What to expect

This project is maintained by one person in their spare time, so timelines are best effort:

| Step | Target |
|---|---|
| Acknowledge your report | within 7 days |
| Initial assessment | within 14 days |
| Fix or mitigation for confirmed issues | as soon as practical, usually within 30 days |

You will be told when a fix is published, and credited in the advisory unless you prefer not to be.

## Scope

In scope:
- **Pages** (`index.html`, `backtest.html`, `guide.html`): for example cross-site scripting through
  scraped text (IPO names, sectors, objects of the issue) that reaches the page unescaped.
- **Data pipeline** (`fetch_ipo.py`, `insights.py`, `build_archive.py`): parsing that could be
  abused by a hostile response from a data source.
- **GitHub Actions workflows** (`.github/workflows/`): script injection, over-broad permissions
  (they use only the built-in `GITHUB_TOKEN` with `contents: write`), or anything that could let
  a third party push to the repository.
- **The Claude skill** (`skills/ipo-decision-desk/`): for example the report script executing
  untrusted content.

Out of scope:
- Accuracy of GMP, subscription, financial or listing data. These come from third-party sites and
  are unofficial; please open a normal issue instead.
- Vulnerabilities in the third-party sites themselves (InvestorGain, Chittorgarh, IPO Watch) or in
  GitHub's own platform. Report those to their owners.
- Denial-of-service, rate-limit testing, or automated scanning of the live site or its data sources.
- Findings that need a compromised device or browser.

## Safe harbour

Good-faith research that follows this policy, avoids privacy violations and service disruption,
and gives reasonable time to fix before public disclosure will not be pursued or reported.

## Not financial advice

Nothing on this site is investment advice. Security fixes do not change that.
