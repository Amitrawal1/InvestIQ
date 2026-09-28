"""Daily prices for the growth model, loaded from TiDB and cached in ml/data/processed/.

The full `stock_prices` table (~4.3M rows) takes a few minutes to pull, so it is cached as a pickle
and reused until `refresh=True` (or the cache is older than the newest trading day the caller needs).
Upstox candles are split-adjusted, so closes can be compared across dates directly.
"""

import time
from pathlib import Path

import pandas as pd

from news_pipeline.db import get_connection

CACHE_DIR = Path(__file__).resolve().parent.parent / "data" / "processed"
STOCK_CACHE = CACHE_DIR / "growth_stock_prices.pkl"
INDEX_CACHE = CACHE_DIR / "growth_index_prices.pkl"

BENCHMARK = "NSE_INDEX|NIFTY SMLCAP 250"
CHUNK = 150          # company ids per query (keeps each TiDB result set small)


def _fetch_stock_prices(conn):
    cur = conn.cursor()
    cur.execute("SELECT MIN(company_id), MAX(company_id) FROM stock_prices")
    lo, hi = cur.fetchone()
    frames = []
    for start in range(lo, hi + 1, CHUNK):
        cur.execute(
            """SELECT company_id, price_date, close_price, volume FROM stock_prices
               WHERE company_id >= %s AND company_id < %s""",
            (start, start + CHUNK),
        )
        rows = cur.fetchall()
        if rows:
            frames.append(pd.DataFrame(rows, columns=["company_id", "price_date", "close", "volume"]))
        print(f"  stock_prices: company ids < {start + CHUNK} ({sum(len(f) for f in frames):,} rows)", end="\r")
    print()
    df = pd.concat(frames, ignore_index=True)
    df["price_date"] = pd.to_datetime(df["price_date"])
    df["close"] = df["close"].astype(float)
    df["volume"] = pd.to_numeric(df["volume"], errors="coerce").astype(float)
    return df


def _fetch_index_prices(conn):
    cur = conn.cursor()
    cur.execute("SELECT index_key, price_date, close_price FROM index_prices")
    df = pd.DataFrame(cur.fetchall(), columns=["index_key", "price_date", "close"])
    df["price_date"] = pd.to_datetime(df["price_date"])
    df["close"] = df["close"].astype(float)
    return df


def load_prices(refresh=False):
    """-> (stock_prices df [company_id, price_date, close, volume], index_prices df)."""
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    if not refresh and STOCK_CACHE.exists() and INDEX_CACHE.exists():
        return pd.read_pickle(STOCK_CACHE), pd.read_pickle(INDEX_CACHE)

    t0 = time.time()
    conn = get_connection()
    try:
        stocks = _fetch_stock_prices(conn)
        index = _fetch_index_prices(conn)
    finally:
        conn.close()
    stocks.to_pickle(STOCK_CACHE)
    index.to_pickle(INDEX_CACHE)
    print(f"  loaded {len(stocks):,} stock rows, {len(index):,} index rows in {time.time() - t0:.0f}s")
    return stocks, index


def load_companies():
    """company_id -> symbol, name, sector (for reports)."""
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute(
            """SELECT c.id, c.symbol, c.name, s.name FROM companies c
               LEFT JOIN sectors s ON s.id = c.sector_id"""
        )
        return pd.DataFrame(cur.fetchall(), columns=["company_id", "symbol", "name", "sector"])
    finally:
        conn.close()
