"""Collect daily OHLCV candles from Upstox into `stock_prices` (and `index_prices`).

Usage (from the ml/ folder):
    python3 -m market_data.collect_prices                        # incremental, whole universe
    python3 -m market_data.collect_prices --symbols RELIANCE DIXON
    python3 -m market_data.collect_prices --limit 50
    python3 -m market_data.collect_prices --from 2016-01-01      # force a start date (re-fetch)
    python3 -m market_data.collect_prices --no-index             # skip the benchmark indices
    python3 -m market_data.collect_prices --index-only

Universe: companies with series EQ/BE and an upstox_instrument_key.

Incremental: each company is fetched from (latest stored price_date + 1 day), or from
DEFAULT_START when it has no rows, up to today. Rows are upserted in large batches
(TiDB bills per request unit), so re-running over an overlapping range is safe.

Upstox v3 historical candles need no access token. One request may span at most
~10 years (3652 days incl. both ends), so longer ranges are chunked, newest first;
older chunks are skipped once a chunk shows where the listing history starts.

NOTE: Upstox daily candles are already split/bonus ADJUSTED (e.g. RELIANCE 2016
closes ~250, not ~1,000). Prices are stored as returned. The split/bonus detector
below therefore only flags gaps Upstox did not adjust; they are logged and counted,
not corrected.
"""

import argparse
import fcntl
import logging
import sys
import threading
import time
import traceback
from contextlib import contextmanager
from datetime import date, datetime, timedelta
from logging.handlers import RotatingFileHandler
from pathlib import Path
from urllib.parse import quote
from zoneinfo import ZoneInfo

import requests

from news_pipeline.db import get_connection

log = logging.getLogger("market_data.prices")

ML_DIR = Path(__file__).resolve().parent.parent
LOG_DIR = ML_DIR / "logs"
LOG_FILE = LOG_DIR / "prices_collect.log"
LOCK_FILE = LOG_DIR / "prices_collect.lock"

TIMEZONE = "Asia/Kolkata"
DEFAULT_START = date(2016, 1, 1)
URL = "https://api.upstox.com/v3/historical-candle/{key}/days/1/{to}/{frm}"
MAX_SPAN_DAYS = 3650          # verified: 3652 days inclusive works, a bit more fails
MIN_INTERVAL = 0.2            # <= 5 requests / second
MAX_RETRIES = 5
FLUSH_ROWS = 5000
SERIES = ("EQ", "BE")

# Benchmark indices (keys verified against the candle API)
INDICES = {
    "NSE_INDEX|Nifty 50": "NIFTY 50",
    "NSE_INDEX|NIFTY SMLCAP 250": "NIFTY SMALLCAP 250",
}
BENCHMARK_KEY = "NSE_INDEX|NIFTY SMLCAP 250"

# Overnight open/prev-close ratios typical of splits and bonuses
SPLIT_RATIOS = {
    "1:2": 1 / 2, "1:3": 1 / 3, "1:4": 1 / 4, "1:5": 1 / 5, "1:10": 1 / 10,
    "2:3": 2 / 3, "3:4": 3 / 4, "2:5": 2 / 5, "1:20": 1 / 20,
}
SPLIT_TOLERANCE = 0.04        # relative distance from the ideal ratio
INDEX_CRASH = 0.95            # index open/prev close below this = market crash day

INDEX_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS index_prices (
    id BIGINT NOT NULL AUTO_INCREMENT PRIMARY KEY,
    index_key VARCHAR(64) NOT NULL,
    index_name VARCHAR(100) NOT NULL,
    price_date DATETIME NOT NULL,
    open_price DECIMAL(12,2) NULL,
    high_price DECIMAL(12,2) NULL,
    low_price DECIMAL(12,2) NULL,
    close_price DECIMAL(12,2) NULL,
    UNIQUE KEY uq_index_prices (index_key, price_date)
)
"""

STOCK_UPSERT = """
INSERT INTO stock_prices (company_id, price_date, open_price, high_price, low_price, close_price, volume)
VALUES (%s, %s, %s, %s, %s, %s, %s)
ON DUPLICATE KEY UPDATE open_price = VALUES(open_price), high_price = VALUES(high_price),
    low_price = VALUES(low_price), close_price = VALUES(close_price), volume = VALUES(volume)
"""

INDEX_UPSERT = """
INSERT INTO index_prices (index_key, index_name, price_date, open_price, high_price, low_price, close_price)
VALUES (%s, %s, %s, %s, %s, %s, %s)
ON DUPLICATE KEY UPDATE open_price = VALUES(open_price), high_price = VALUES(high_price),
    low_price = VALUES(low_price), close_price = VALUES(close_price)
"""


# ---------------------------------------------------------------------------
# Plumbing (same conventions as news_pipeline.run)
# ---------------------------------------------------------------------------

def setup_logging():
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    fmt = logging.Formatter("%(asctime)s %(levelname)s %(message)s", "%Y-%m-%d %H:%M:%S")
    file_handler = RotatingFileHandler(LOG_FILE, maxBytes=1_000_000, backupCount=5)
    file_handler.setFormatter(fmt)
    handlers = [file_handler]
    if sys.stdout.isatty():
        stream_handler = logging.StreamHandler(sys.stdout)
        stream_handler.setFormatter(fmt)
        handlers.append(stream_handler)
    root = logging.getLogger()
    root.setLevel(logging.INFO)
    root.handlers = handlers
    logging.getLogger("urllib3").setLevel(logging.WARNING)


@contextmanager
def single_instance():
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    with open(LOCK_FILE, "w") as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            yield False
            return
        try:
            yield True
        finally:
            fcntl.flock(lock, fcntl.LOCK_UN)


def parse_date(value):
    return datetime.strptime(value, "%Y-%m-%d").date()


# ---------------------------------------------------------------------------
# Upstox client
# ---------------------------------------------------------------------------

class NoData(Exception):
    """Upstox rejected the instrument/range (4xx other than 429): not retryable."""


class UpstoxCandles:
    def __init__(self):
        self.session = requests.Session()
        self.session.headers["Accept"] = "application/json"
        self._last = 0.0
        self._lock = threading.Lock()
        self.requests = 0

    def _throttle(self):
        with self._lock:
            wait = self._last + MIN_INTERVAL - time.monotonic()
            if wait > 0:
                time.sleep(wait)
            self._last = time.monotonic()

    def _get(self, key, frm, to):
        url = URL.format(key=quote(key, safe=""), to=to.isoformat(), frm=frm.isoformat())
        for attempt in range(MAX_RETRIES + 1):
            self._throttle()
            self.requests += 1
            try:
                resp = self.session.get(url, timeout=30)
            except requests.RequestException as exc:
                err = f"network: {exc}"
            else:
                if resp.status_code == 200:
                    return resp.json().get("data", {}).get("candles") or []
                if resp.status_code != 429 and resp.status_code < 500:
                    raise NoData(f"HTTP {resp.status_code}: {resp.text[:200]}")
                err = f"HTTP {resp.status_code}"
            if attempt == MAX_RETRIES:
                raise RuntimeError(f"{key} {frm}->{to}: giving up after retries ({err})")
            delay = min(60, 2 ** attempt * (3 if "429" in err else 1))
            log.warning("%s %s->%s: %s, retrying in %ss", key, frm, to, err, delay)
            time.sleep(delay)

    def daily(self, key, start, end):
        """All candles in [start, end], oldest first, as (date, o, h, l, c, v)."""
        out = []
        to = end
        while to >= start:
            frm = max(start, to - timedelta(days=MAX_SPAN_DAYS - 1))
            candles = self._get(key, frm, to)
            out.extend(candles)
            # History begins inside this chunk (listing date): no need to go further back
            if not candles or date.fromisoformat(candles[-1][0][:10]) > frm + timedelta(days=30):
                break
            to = frm - timedelta(days=1)
        rows = {}
        for ts, o, h, l, c, v, *_ in out:
            rows[date.fromisoformat(ts[:10])] = (o, h, l, c, v)
        return [(d, *rows[d]) for d in sorted(rows)]


# ---------------------------------------------------------------------------
# DB helpers
# ---------------------------------------------------------------------------

def load_universe(conn, symbols, limit):
    sql = f"""SELECT id, symbol, upstox_instrument_key FROM companies
              WHERE series IN ({",".join(["%s"] * len(SERIES))}) AND upstox_instrument_key IS NOT NULL"""
    params = list(SERIES)
    if symbols:
        sql += f" AND symbol IN ({','.join(['%s'] * len(symbols))})"
        params += [s.upper() for s in symbols]
    sql += " ORDER BY symbol"
    if limit:
        sql += f" LIMIT {int(limit)}"
    cur = conn.cursor()
    cur.execute(sql, params)
    return cur.fetchall()


def latest_dates(conn, table, key_col):
    cur = conn.cursor()
    cur.execute(f"SELECT {key_col}, MAX(price_date) FROM {table} GROUP BY {key_col}")
    return {k: d.date() for k, d in cur.fetchall() if d}


def last_close_before(conn, company_id, day):
    cur = conn.cursor()
    cur.execute("""SELECT close_price FROM stock_prices WHERE company_id = %s AND price_date < %s
                   ORDER BY price_date DESC LIMIT 1""", (company_id, day))
    row = cur.fetchone()
    return float(row[0]) if row and row[0] is not None else None


class BatchWriter:
    def __init__(self, conn, sql):
        self.conn, self.sql, self.buf, self.written = conn, sql, [], 0

    def add(self, rows):
        self.buf.extend(rows)
        if len(self.buf) >= FLUSH_ROWS:
            self.flush()

    def flush(self):
        if not self.buf:
            return
        cur = self.conn.cursor()
        for i in range(0, len(self.buf), FLUSH_ROWS):
            cur.executemany(self.sql, self.buf[i:i + FLUSH_ROWS])
        self.conn.commit()
        self.written += len(self.buf)
        self.buf = []


# ---------------------------------------------------------------------------
# Split / bonus detection (log only)
# ---------------------------------------------------------------------------

def load_index_moves(conn):
    """{date: open / previous close} for the benchmark index."""
    cur = conn.cursor()
    cur.execute("SELECT price_date, open_price, close_price FROM index_prices WHERE index_key = %s ORDER BY price_date",
                (BENCHMARK_KEY,))
    moves, prev = {}, None
    for d, o, c in cur.fetchall():
        if prev and o:
            moves[d.date()] = float(o) / prev
        prev = float(c) if c else prev
    return moves


def split_candidates(rows, prev_close, index_moves):
    found = []
    for d, o, h, l, c, v in rows:
        if prev_close and o and prev_close > 0:
            ratio = o / prev_close
            if ratio < 0.8:
                for label, ideal in SPLIT_RATIOS.items():
                    if abs(ratio - ideal) / ideal <= SPLIT_TOLERANCE:
                        if index_moves.get(d, 1.0) >= INDEX_CRASH:
                            found.append((d, label, prev_close, o))
                        break
        prev_close = c or prev_close
    return found


# ---------------------------------------------------------------------------
# Runs
# ---------------------------------------------------------------------------

def collect_indices(conn, client, args, today, stats):
    conn.cursor().execute(INDEX_TABLE_SQL)
    conn.commit()
    latest = latest_dates(conn, "index_prices", "index_key")
    writer = BatchWriter(conn, INDEX_UPSERT)
    for key, name in INDICES.items():
        start = args.from_date or (latest[key] + timedelta(days=1) if key in latest else DEFAULT_START)
        if start > today:
            continue
        try:
            rows = client.daily(key, start, today)
        except Exception as exc:
            log.error("Index %s failed: %s", name, exc)
            stats["index_errors"] += 1
            continue
        writer.add([(key, name, d, o, h, l, c) for d, o, h, l, c, v in rows])
        log.info("Index %s: %d rows %s -> %s", name, len(rows),
                 rows[0][0] if rows else "-", rows[-1][0] if rows else "-")
    writer.flush()
    stats["index_rows"] = writer.written


def collect_stocks(conn, client, args, today, stats):
    universe = load_universe(conn, args.symbols, args.limit)
    latest = latest_dates(conn, "stock_prices", "company_id")
    index_moves = load_index_moves(conn)
    writer = BatchWriter(conn, STOCK_UPSERT)
    log.info("Universe: %d companies (%d already have prices)", len(universe),
             sum(1 for cid, *_ in universe if cid in latest))
    t0 = time.monotonic()

    for n, (cid, symbol, key) in enumerate(universe, 1):
        start = args.from_date or (latest[cid] + timedelta(days=1) if cid in latest else DEFAULT_START)
        if start > today:
            stats["up_to_date"] += 1
            continue
        try:
            rows = client.daily(key, start, today)
        except Exception as exc:
            stats["failed"] += 1
            stats["failed_symbols"].append(symbol)
            log.error("%s (%s): %s", symbol, key, exc)
            continue

        if not rows:
            stats["empty"] += 1
            log.info("[%d/%d] %s: no candles %s -> %s", n, len(universe), symbol, start, today)
            continue

        prev_close = last_close_before(conn, cid, rows[0][0]) if cid in latest else None
        for d, label, pc, o in split_candidates(rows, prev_close, index_moves):
            stats["split_candidates"] += 1
            log.warning("SPLIT? %s %s ratio~%s prev_close=%.2f open=%.2f", symbol, d, label, pc, o)

        writer.add([(cid, d, o, h, l, c, v) for d, o, h, l, c, v in rows])
        stats["ok"] += 1
        stats["rows"] += len(rows)
        log.info("[%d/%d] %s: %d rows %s -> %s", n, len(universe), symbol, len(rows), rows[0][0], rows[-1][0])

        if n % 100 == 0:
            writer.flush()
            rate = (time.monotonic() - t0) / n
            log.info("Progress %d/%d, %d rows, ~%.0f min left", n, len(universe), stats["rows"],
                     rate * (len(universe) - n) / 60)
    writer.flush()


def main(argv=None):
    parser = argparse.ArgumentParser(description="InvestIQ daily price collector (Upstox)")
    parser.add_argument("--symbols", nargs="+", help="Only these NSE symbols")
    parser.add_argument("--limit", type=int, help="Only the first N companies (by symbol)")
    parser.add_argument("--from", dest="from_date", type=parse_date,
                        help="Force start date (YYYY-MM-DD) instead of incremental")
    parser.add_argument("--no-index", action="store_true", help="Skip benchmark indices")
    parser.add_argument("--index-only", action="store_true", help="Only update benchmark indices")
    args = parser.parse_args(argv)

    setup_logging()
    with single_instance() as acquired:
        if not acquired:
            log.info("Another price collection is in progress; skipping")
            return 0

        today = datetime.now(ZoneInfo(TIMEZONE)).date()
        stats = {"ok": 0, "rows": 0, "empty": 0, "failed": 0, "failed_symbols": [], "up_to_date": 0,
                 "split_candidates": 0, "index_rows": 0, "index_errors": 0}
        client = UpstoxCandles()
        conn = get_connection()
        t0 = time.monotonic()
        try:
            if not args.no_index:
                collect_indices(conn, client, args, today, stats)
            if not args.index_only:
                collect_stocks(conn, client, args, today, stats)
        except Exception:
            log.error("Run failed:\n%s", traceback.format_exc())
            conn.rollback()
            return 1
        finally:
            conn.close()

        log.info("Done in %.1f min: companies ok=%d empty=%d up_to_date=%d failed=%d rows=%d "
                 "index_rows=%d index_errors=%d split_candidates=%d requests=%d%s",
                 (time.monotonic() - t0) / 60, stats["ok"], stats["empty"], stats["up_to_date"],
                 stats["failed"], stats["rows"], stats["index_rows"], stats["index_errors"],
                 stats["split_candidates"], client.requests,
                 f" failed_symbols={','.join(stats['failed_symbols'][:50])}" if stats["failed_symbols"] else "")
        return 0 if not stats["failed"] else 2


if __name__ == "__main__":
    sys.exit(main())
