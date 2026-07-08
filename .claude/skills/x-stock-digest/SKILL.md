---
name: x-stock-digest
description: Browse X/Twitter through a logged-in Chrome (attached over the Chrome DevTools Protocol with Playwright), scrape recent tweets from many uploaders or the home timeline, filter for stock/market content, extract cashtags ($TICKER), and produce a structured digest grouped by account with top tickers. Use when the user wants to monitor or summarize what specific X accounts are posting about stocks, build a watchlist of tickers being discussed, or turn a Twitter feed into source-tagged leads for further research. Pairs with serenity-skill: scraped tweets are LEADS ONLY and must be verified against primary sources before any conclusion.
---

# X Stock Digest

Turn a logged-in X/Twitter session into a structured, source-tagged digest of
what many accounts are saying about stocks.

## What this skill does
1. Attaches to a Chrome you already launched and logged into (over CDP — no
   passwords handled here).
2. Visits each account in `references/accounts.txt` (and/or the home timeline),
   scrolls, and collects recent tweets.
3. Flags stock-related tweets (any `$TICKER` cashtag, or market keywords like
   earnings/guidance/price target/breakout) and extracts the tickers.
4. Writes three artifacts to `output/`: full JSON, a flat CSV (columns aligned
   with `serenity-skill`'s corpus), and a Markdown digest grouped by account
   with a top-cashtag leaderboard.
5. The agent then summarizes the Markdown digest — especially the stock signal.

## Evidence discipline (read this first)
Raw tweets are **leads only**. They tell you *what was discussed and how often*,
never whether it is true. This mirrors `serenity-skill`'s evidence ladder:
before drawing any conclusion or making any call, verify every claim against
primary filings, transcripts, and live market data. Never cite a tweet as proof.

## One-time setup
Read `references/setup-chrome-cdp.md`. In short:

```powershell
& "C:\Program Files\Google\Chrome\Application\chrome.exe" `
    --remote-debugging-port=9222 `
    --user-data-dir="$env:LOCALAPPDATA\x-digest-chrome"
```

Log into x.com in that window once. Install deps once:

```powershell
.\venv\Scripts\python.exe -m pip install -r .claude\skills\x-stock-digest\scripts\requirements.txt
```

(Chromium download via `python -m playwright install chromium` is optional when
attaching to your own Chrome.)

## Run

```powershell
# all accounts in references/accounts.txt
.\venv\Scripts\python.exe .\.claude\skills\x-stock-digest\scripts\scrape_x.py --scrolls 6

# specific handles, deeper scroll
.\venv\Scripts\python.exe .\.claude\skills\x-stock-digest\scripts\scrape_x.py --handles aleabitoreddit unusual_whales --scrolls 10

# the logged-in home feed
.\venv\Scripts\python.exe .\.claude\skills\x-stock-digest\scripts\scrape_x.py --home --scrolls 12
```

## Summarize (agent workflow)
After a run, open the newest `output/x-digest-*.md` and produce:
1. **Top tickers** — the cashtag leaderboard = what the feed is most focused on
   right now (leads to investigate, not buy signals).
2. **Per-account read** — for each uploader, 2–4 bullets on their stock stance,
   with the tweet URL as citation.
3. **Cross-account convergence** — tickers multiple accounts mention
   independently are stronger leads; flag them for verification.
4. **Hand-off to research** — route promising tickers into `serenity-skill`
   (bottleneck/valuation) and `us-equity-tactical-analysis` (timing), and
   verify against primary sources before any judgment.

## Configuration
- `references/accounts.txt` — one `@handle` per line; `#` comments. Edit to
  control who gets scraped.
- Flags: `--cdp` (DevTools endpoint, default `http://localhost:9222`),
  `--scrolls`, `--max-per-account`, `--home`, `--handles`, `--outdir`.

## Bundled resources
- `scripts/scrape_x.py` — CDP-attach scraper + digest writer (JSON/CSV/MD).
- `scripts/requirements.txt` — Playwright dependency.
- `references/accounts.txt` — editable account watchlist.
- `references/setup-chrome-cdp.md` — how to launch Chrome with remote debugging
  and troubleshoot.
- `output/` — generated digests (git-ignored by intent; personal research data).

## Limits & compliance
- Respect X's Terms of Service and rate limits; scrape gently (fewer scrolls/
  accounts, space out runs) to avoid blocks.
- X changes its DOM often; if `article[data-testid="tweet"]` stops matching,
  update the selectors in `scripts/scrape_x.py`.
- Personal-research use on accounts you can already view while logged in.
