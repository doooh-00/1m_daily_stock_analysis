# Setup: attach to your logged-in Chrome over CDP

This skill does **not** handle your X/Twitter password. It attaches to a Chrome
instance you already control and have logged into, and reuses that session. This
is the most reliable way past X's login wall and the least fragile against
anti-bot checks.

## 1. Close other Chrome windows (optional but recommended)
The remote-debugging port only attaches cleanly when Chrome starts with the flag.
Using a dedicated `--user-data-dir` keeps this separate from your normal profile.

## 2. Launch Chrome with the debugging port (Windows PowerShell)

```powershell
& "C:\Program Files\Google\Chrome\Application\chrome.exe" `
    --remote-debugging-port=9222 `
    --user-data-dir="$env:LOCALAPPDATA\x-digest-chrome"
```

If Chrome is installed elsewhere, adjust the path (common alt:
`C:\Program Files (x86)\Google\Chrome\Application\chrome.exe`).

## 3. Log into x.com in that window
A fresh `--user-data-dir` starts logged out. Sign in once; the session persists
in that folder for future runs, so you only do this the first time (until the
cookie expires).

## 4. Verify the port is up
Open <http://localhost:9222/json/version> in any browser — you should see JSON
with a `webSocketDebuggerUrl`. That confirms Playwright can attach.

## 5. Run the scraper

```powershell
# from the repo root, using the project venv
.\venv\Scripts\python.exe `
  .\.claude\skills\x-stock-digest\scripts\scrape_x.py --scrolls 6
```

Outputs land in `.claude/skills/x-stock-digest/output/`.

## Troubleshooting
- **"No tweets collected"** — Chrome isn't running with the flag, or you're not
  logged into x.com in that window, or the port differs (pass `--cdp`).
- **Empty for a handle** — the account may be protected, suspended, or renamed.
- **Rate limiting / blank timeline** — slow down: fewer `--scrolls`, fewer
  accounts per run, and space runs out. Scraping aggressively risks an X block.
- **Selectors changed** — X updates its DOM; if `article[data-testid="tweet"]`
  stops matching, the selectors in `scripts/scrape_x.py` need updating.

## Compliance note
Respect X's Terms of Service and rate limits. Use this only for personal
research on accounts you can already view while logged in. Treat every scraped
tweet as a **lead**, never as proof.
