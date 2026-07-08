#!/usr/bin/env python3
"""
Query the Serenity tweet corpus (references/sources/serenity-corpus.csv).

This is RAW PRIMARY-SOURCE social data (5,963 tweets, 2025-07-02 .. 2026-06-06)
from the Serenity account. Per the skill's evidence ladder it is LEAD-GENERATION
ONLY: use it to surface what Serenity discussed and how often, then verify every
claim against primary filings/transcripts before drawing any conclusion. Do NOT
cite raw tweets as proof.

Cross-platform: defaults to the CSV bundled next to this skill, no hardcoded paths.

Usage:
  python query_corpus.py                 # overview: stats + top cashtags
  python query_corpus.py --ticker AXTI   # raw tweets mentioning $AXTI (leads)
  python query_corpus.py --ticker MU --limit 30
"""
import argparse
import re
import sys
from collections import Counter
from pathlib import Path

import pandas as pd

DEFAULT_CSV = Path(__file__).resolve().parent.parent / "references" / "sources" / "serenity-corpus.csv"


def load(csv_path: Path) -> pd.DataFrame:
    if not csv_path.exists():
        sys.exit(f"[error] corpus not found: {csv_path}")
    df = pd.read_csv(csv_path, encoding="utf-8", dtype={"tweet_id": str})
    df["tweet_id"] = df["tweet_id"].astype(str).str.strip("'\" ")
    if "created_at" in df.columns:
        df["created_at"] = pd.to_datetime(df["created_at"], errors="coerce")
    return df


def overview(df: pd.DataFrame) -> None:
    print(f"rows: {len(df)}")
    if "created_at" in df.columns:
        d = df["created_at"].dropna()
        if len(d):
            print(f"date range: {d.min()} -> {d.max()} ({(d.max() - d.min()).days} days)")
    if "language" in df.columns:
        print("languages:", df["language"].value_counts().head(5).to_dict())
    cashtags = Counter()
    for t in df.get("text", pd.Series(dtype=str)).astype(str):
        cashtags.update(re.findall(r"\$[A-Za-z]{1,5}", t))
    print("\ntop cashtags (leads only, verify before use):")
    for tag, n in cashtags.most_common(15):
        print(f"  {tag}: {n}")


def by_ticker(df: pd.DataFrame, ticker: str, limit: int) -> None:
    tag = "$" + ticker.upper().lstrip("$")
    mask = df["text"].astype(str).str.contains(re.escape(tag), case=False, regex=True)
    hits = df[mask].copy()
    print(f"{tag}: {len(hits)} tweets (showing up to {limit}, newest first)")
    if "created_at" in hits.columns:
        hits = hits.sort_values("created_at", ascending=False)
    for _, r in hits.head(limit).iterrows():
        when = r.get("created_at", "")
        print(f"\n[{when}] id={r.get('tweet_id', '')}")
        print(r.get("text", ""))


def main() -> None:
    ap = argparse.ArgumentParser(description="Query the Serenity tweet corpus (leads only).")
    ap.add_argument("--csv", type=Path, default=DEFAULT_CSV)
    ap.add_argument("--ticker", help="cashtag to filter, e.g. AXTI")
    ap.add_argument("--limit", type=int, default=20)
    args = ap.parse_args()

    df = load(args.csv)
    if args.ticker:
        by_ticker(df, args.ticker, args.limit)
    else:
        overview(df)


if __name__ == "__main__":
    main()
