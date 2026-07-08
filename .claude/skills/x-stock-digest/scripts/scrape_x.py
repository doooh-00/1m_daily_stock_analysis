#!/usr/bin/env python3
"""
x-stock-digest: scrape stock-related tweets from X/Twitter via an already
logged-in Chrome (attached over the Chrome DevTools Protocol), then emit a
structured digest the agent can summarize.

DESIGN
------
- We attach to YOUR real, logged-in Chrome over CDP. No passwords are handled
  here; we reuse the existing session. Start Chrome first like this (Windows):

    & "C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe" `
        --remote-debugging-port=9222 `
        --user-data-dir="$env:LOCALAPPDATA\\x-digest-chrome"

  Log into x.com once in that window, then run this script.
  (See references/setup-chrome-cdp.md for the full guide.)

- For each handle in references/accounts.txt (or --handles), we open
  https://x.com/<handle>, scroll, and collect tweets. We also support the home
  timeline with --home.

EVIDENCE DISCIPLINE
-------------------
Raw tweets are LEADS ONLY (same rule as serenity-skill's evidence ladder).
This script never decides anything; it structures what was posted so the agent
can summarize and then verify every claim against primary sources.

OUTPUT (written to ../output/ by default)
- x-digest-<timestamp>.json : full structured records
- x-digest-<timestamp>.csv  : flat table (matches serenity-corpus columns where possible)
- x-digest-<timestamp>.md   : human-readable digest grouped by account + top cashtags

USAGE
  python scrape_x.py                         # all accounts in accounts.txt
  python scrape_x.py --handles aleabitoreddit elonmusk --scrolls 8
  python scrape_x.py --home --scrolls 12     # scrape the logged-in home feed
  python scrape_x.py --cdp http://localhost:9222 --max-per-account 60
"""
from __future__ import annotations

import argparse
import csv
import json
import re
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

try:
    from playwright.sync_api import sync_playwright
except ImportError:
    sys.exit(
        "playwright is not installed. Run:\n"
        "  pip install playwright\n"
        "  python -m playwright install chromium\n"
        "(chromium download is optional when attaching to your own Chrome over CDP)"
    )

CASHTAG_RE = re.compile(r"\$[A-Za-z]{1,6}(?:\.[A-Za-z]{1,2})?\b")
SKILL_DIR = Path(__file__).resolve().parent.parent
DEFAULT_ACCOUNTS = SKILL_DIR / "references" / "accounts.txt"
DEFAULT_OUTDIR = SKILL_DIR / "output"

# words that suggest a tweet is about markets even without a cashtag
STOCK_HINTS = re.compile(
    r"\b(earnings|guidance|revenue|margin|EPS|valuation|forward\s*pe|p/?e|"
    r"upgrade|downgrade|price\s*target|buyback|short|squeeze|catalyst|"
    r"semis?|chips?|datacenter|data\s*center|capex|hyperscaler|bullish|bearish|"
    r"calls?|puts?|breakout|support|resistance|float|dilut)\b",
    re.IGNORECASE,
)


def read_accounts(path: Path) -> list[str]:
    if not path.exists():
        return []
    out = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        out.append(line.lstrip("@").strip())
    return out


def extract_tweets_from_page(page, source: str, max_items: int, scrolls: int):
    """Scroll and collect tweet article nodes. Returns list of dicts."""
    seen = {}
    for _ in range(scrolls):
        articles = page.query_selector_all('article[data-testid="tweet"]')
        for a in articles:
            try:
                rec = parse_article(a, source)
            except Exception:
                continue
            if rec and rec["tweet_id"] and rec["tweet_id"] not in seen:
                seen[rec["tweet_id"]] = rec
        if len(seen) >= max_items:
            break
        page.mouse.wheel(0, 3200)
        page.wait_for_timeout(1200)
    return list(seen.values())[:max_items]


def parse_article(a, source: str) -> dict | None:
    text_node = a.query_selector('div[data-testid="tweetText"]')
    text = text_node.inner_text().strip() if text_node else ""

    # permalink + tweet id + author handle
    tweet_id, author, url = "", "", ""
    for link in a.query_selector_all('a[href*="/status/"]'):
        href = link.get_attribute("href") or ""
        m = re.search(r"/([^/]+)/status/(\d+)", href)
        if m:
            author, tweet_id = m.group(1), m.group(2)
            url = "https://x.com" + href.split("?")[0]
            break

    when = ""
    time_node = a.query_selector("time")
    if time_node:
        when = time_node.get_attribute("datetime") or ""

    def metric(testid: str) -> str:
        n = a.query_selector(f'[data-testid="{testid}"]')
        return n.inner_text().strip() if n else ""

    cashtags = sorted({c.upper() for c in CASHTAG_RE.findall(text)})
    return {
        "tweet_id": tweet_id,
        "author": author or source,
        "source": source,
        "created_at": when,
        "text": text,
        "cashtags": cashtags,
        "is_stock": bool(cashtags) or bool(STOCK_HINTS.search(text)),
        "reply": metric("reply"),
        "retweet": metric("retweet"),
        "like": metric("like"),
        "url": url,
    }


def scrape(cdp_url: str, handles: list[str], use_home: bool, scrolls: int, max_per: int):
    records = []
    with sync_playwright() as p:
        browser = p.chromium.connect_over_cdp(cdp_url)
        ctx = browser.contexts[0] if browser.contexts else browser.new_context()
        page = ctx.new_page()

        targets = []
        if use_home:
            targets.append(("__home__", "https://x.com/home"))
        for h in handles:
            targets.append((h, f"https://x.com/{h}"))

        for name, url in targets:
            try:
                print(f"[scrape] {name} -> {url}")
                page.goto(url, wait_until="domcontentloaded", timeout=45000)
                try:
                    page.wait_for_selector('article[data-testid="tweet"]', timeout=20000)
                except Exception:
                    # X can be slow to hydrate; give it a beat and proceed anyway
                    page.wait_for_timeout(5000)
                recs = extract_tweets_from_page(page, name, max_per, scrolls)
                print(f"         collected {len(recs)} tweets "
                      f"({sum(r['is_stock'] for r in recs)} stock-related)")
                records.extend(recs)
            except Exception as e:
                print(f"         [warn] {name}: {e}")
        page.close()
    return records


def write_outputs(records: list[dict], outdir: Path) -> dict[str, Path]:
    outdir.mkdir(parents=True, exist_ok=True)
    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    stock = [r for r in records if r["is_stock"]]

    json_path = outdir / f"x-digest-{ts}.json"
    json_path.write_text(json.dumps(records, ensure_ascii=False, indent=2), encoding="utf-8")

    csv_path = outdir / f"x-digest-{ts}.csv"
    cols = ["tweet_id", "author", "source", "created_at", "text",
            "cashtags", "is_stock", "reply", "retweet", "like", "url"]
    with csv_path.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=cols)
        w.writeheader()
        for r in records:
            row = dict(r)
            row["cashtags"] = " ".join(r["cashtags"])
            w.writerow(row)

    # markdown digest
    from collections import Counter
    cash = Counter()
    for r in stock:
        cash.update(r["cashtags"])
    md = [f"# X stock digest — {ts}",
          f"\nAccounts scraped: {len({r['source'] for r in records})} | "
          f"tweets: {len(records)} | stock-related: {len(stock)}",
          "\n> Raw tweets are LEADS ONLY. Verify every claim against primary "
          "sources before acting.",
          "\n## Top cashtags (stock-related tweets)"]
    if cash:
        for tag, n in cash.most_common(25):
            md.append(f"- {tag}: {n}")
    else:
        md.append("- (none found)")

    md.append("\n## Stock tweets by account")
    by_src: dict[str, list[dict]] = {}
    for r in stock:
        by_src.setdefault(r["source"], []).append(r)
    for src, items in by_src.items():
        md.append(f"\n### @{src} ({len(items)})")
        items.sort(key=lambda r: r["created_at"], reverse=True)
        for r in items[:40]:
            tags = " ".join(r["cashtags"])
            head = f"- [{r['created_at']}] {tags}".rstrip()
            md.append(head)
            text = r["text"].replace("\n", " ").strip()
            md.append(f"  {text[:400]}")
            if r["url"]:
                md.append(f"  {r['url']}")
    md_path = outdir / f"x-digest-{ts}.md"
    md_path.write_text("\n".join(md), encoding="utf-8")

    return {"json": json_path, "csv": csv_path, "md": md_path}


def main() -> None:
    ap = argparse.ArgumentParser(description="Scrape stock tweets from X via logged-in Chrome (CDP).")
    ap.add_argument("--cdp", default="http://localhost:9222", help="Chrome DevTools endpoint")
    ap.add_argument("--accounts", type=Path, default=DEFAULT_ACCOUNTS)
    ap.add_argument("--handles", nargs="*", help="override account list (space separated, no @)")
    ap.add_argument("--home", action="store_true", help="also scrape the logged-in home timeline")
    ap.add_argument("--scrolls", type=int, default=6)
    ap.add_argument("--max-per-account", type=int, default=50)
    ap.add_argument("--outdir", type=Path, default=DEFAULT_OUTDIR)
    args = ap.parse_args()

    handles = args.handles if args.handles else read_accounts(args.accounts)
    if not handles and not args.home:
        sys.exit(f"No accounts. Add @handles to {args.accounts} or pass --handles / --home.")

    print(f"[x-stock-digest] CDP={args.cdp} handles={handles} home={args.home}")
    records = scrape(args.cdp, handles, args.home, args.scrolls, args.max_per_account)
    if not records:
        sys.exit("No tweets collected. Is Chrome running with --remote-debugging-port and logged into x.com?")
    paths = write_outputs(records, args.outdir)
    print("\n[done] wrote:")
    for k, v in paths.items():
        print(f"  {k}: {v}")
    print("\nNext: ask the agent to summarize the .md digest using serenity-skill evidence rules.")


if __name__ == "__main__":
    main()
