"""Fetch new NSE announcements, store them, and score their sentiment.

Usage (from the ml/ folder):
    python3 -m news_pipeline.run                     # normal scheduled run
    python3 -m news_pipeline.run --from 2026-09-01   # backfill from a date
    python3 -m news_pipeline.run --no-fetch --score-limit 0   # score the whole backlog
    python3 -m news_pipeline.run --retention-days 0  # skip deleting old news this run

"Never miss" rules:
  * The fetch window starts from the newest stored announcement (minus an overlap),
    not from "today", so downtime is caught up automatically.
  * Days are processed oldest -> newest and committed one by one. If a day fails the
    run stops there, so the next run resumes from that day and no gap is left behind.
  * Sentiment is computed for every row that doesn't have it yet, so rows missed by
    a crashed run are scored next time.

Retention: news published more than RETENTION_DAYS ago is permanently deleted each
run (before scoring, so no time is spent on rows about to go). A --from backfill
older than that window is therefore removed again at the end of the same run.
"""

import argparse
import fcntl
import logging
import os
import sys
import time
import traceback
from contextlib import contextmanager
from datetime import datetime, timedelta
from logging.handlers import RotatingFileHandler
from zoneinfo import ZoneInfo

from . import db
from .config import (
    DEFAULT_LOOKBACK_DAYS,
    LOCK_FILE,
    LOG_DIR,
    LOG_FILE,
    OVERLAP_DAYS,
    REQUEST_PAUSE_SECONDS,
    RETENTION_DAYS,
    SCORE_LIMIT_PER_RUN,
    TIMEZONE,
)
from .nse import NSEClient
from .transform import to_news_rows

log = logging.getLogger("news_pipeline")


def setup_logging():
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    fmt = logging.Formatter("%(asctime)s %(levelname)s %(message)s", "%Y-%m-%d %H:%M:%S")

    file_handler = RotatingFileHandler(LOG_FILE, maxBytes=1_000_000, backupCount=5)
    file_handler.setFormatter(fmt)
    handlers = [file_handler]

    # Echo to the terminal for manual runs and to the GitHub Actions log (CI=true);
    # launchd runs on the Mac only write the log file
    if sys.stdout.isatty() or os.getenv("CI") == "true":
        stream_handler = logging.StreamHandler(sys.stdout)
        stream_handler.setFormatter(fmt)
        handlers.append(stream_handler)

    root = logging.getLogger()
    root.setLevel(logging.INFO)
    root.handlers = handlers

    # Library request logs (Hugging Face / httpx) only add noise
    for name in ("httpx", "huggingface_hub", "urllib3"):
        logging.getLogger(name).setLevel(logging.WARNING)


@contextmanager
def single_instance():
    """Skip this run if another one is still going (e.g. a long backfill)."""

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


def fetch_window(conn, args):
    today = datetime.now(ZoneInfo(TIMEZONE)).date()
    end = args.to or today

    if args.from_date:
        start = args.from_date
    else:
        latest = db.latest_announcement_time(conn)
        start = (latest.date() - timedelta(days=OVERLAP_DAYS)) if latest else today - timedelta(days=DEFAULT_LOOKBACK_DAYS)

    return min(start, end), end


def run_fetch(conn, args, stats):
    start, end = fetch_window(conn, args)
    stats["from_date"], stats["to_date"] = start, end
    log.info("Fetching NSE announcements %s -> %s", start, end)

    isin_map, symbol_map, isin_by_id = db.load_company_maps(conn)
    client = NSEClient()

    day = start
    while day <= end:
        records = client.fetch_day(day)
        rows, unmapped = to_news_rows(records, isin_map, symbol_map, isin_by_id)
        inserted, existing = db.upsert_news(conn, rows)

        stats["fetched"] += len(records)
        stats["inserted"] += inserted
        stats["existing"] += existing
        stats["unmapped"] += len(unmapped)
        stats["unmapped_symbols"].update(unmapped)
        stats["day_counts"][day.isoformat()] = len(records)

        log.info("%s: %d announcements (%d new, %d already stored, %d unmapped)",
                 day, len(records), inserted, existing, len(unmapped))

        # A trading day with zero announcements is unusual: worth a look in the log
        if not records and day.weekday() < 5 and day < end:
            log.warning("%s is a weekday with no announcements (holiday, or NSE issue?)", day)

        day += timedelta(days=1)
        if day <= end:
            time.sleep(REQUEST_PAUSE_SECONDS)


def run_purge(conn, days, stats):
    deleted = db.purge_old_news(conn, days)
    stats["deleted"] = deleted
    if deleted:
        log.info("Retention: deleted %d announcements older than %d days", deleted, days)


def run_scoring(conn, limit, stats):
    pending = db.count_pending_sentiment(conn)
    if not pending:
        log.info("Sentiment: nothing to score")
        stats["pending_sentiment"] = 0
        return

    from .sentiment import FinBertScorer, build_text  # heavy import only when needed

    rows = db.fetch_pending_sentiment(conn, limit)
    log.info("Sentiment: scoring %d of %d pending announcements", len(rows), pending)

    scorer = FinBertScorer()
    chunk = 512  # commit progress regularly

    for i in range(0, len(rows), chunk):
        part = rows[i:i + chunk]
        predictions = scorer.predict([build_text(r["event_type"], r["content"]) for r in part])
        db.save_sentiment(conn, [(r["id"], p) for r, p in zip(part, predictions)], scorer.model_name)
        stats["scored"] += len(part)
        log.info("Sentiment: %d / %d scored", stats["scored"], len(rows))

    stats["pending_sentiment"] = db.count_pending_sentiment(conn)


def main(argv=None):
    parser = argparse.ArgumentParser(description="InvestIQ NSE news pipeline")
    parser.add_argument("--from", dest="from_date", type=parse_date, help="Backfill start date (YYYY-MM-DD)")
    parser.add_argument("--to", type=parse_date, help="End date (YYYY-MM-DD), default today")
    parser.add_argument("--no-fetch", action="store_true", help="Skip fetching, only score sentiment")
    parser.add_argument("--no-score", action="store_true", help="Skip sentiment scoring")
    parser.add_argument("--score-limit", type=int, default=SCORE_LIMIT_PER_RUN,
                        help=f"Max announcements to score this run (0 = all, default {SCORE_LIMIT_PER_RUN})")
    parser.add_argument("--retention-days", type=int, default=RETENTION_DAYS,
                        help=f"Delete news older than this many days (0 = keep all, default {RETENTION_DAYS})")
    args = parser.parse_args(argv)

    setup_logging()

    with single_instance() as acquired:
        if not acquired:
            log.info("Another pipeline run is in progress; skipping")
            return 0

        conn = db.get_connection()
        db.ensure_schema(conn)
        run_id = db.start_run(conn)

        stats = {"fetched": 0, "inserted": 0, "existing": 0, "unmapped": 0,
                 "unmapped_symbols": set(), "scored": 0, "deleted": 0, "day_counts": {}}

        try:
            if not args.no_fetch:
                run_fetch(conn, args, stats)
            if args.retention_days > 0:
                run_purge(conn, args.retention_days, stats)
            if not args.no_score:
                run_scoring(conn, args.score_limit, stats)

            db.finish_run(conn, run_id, "success", stats)
            log.info("Run %d done: fetched=%d new=%d existing=%d unmapped=%d deleted=%d scored=%d pending=%s",
                     run_id, stats["fetched"], stats["inserted"], stats["existing"],
                     stats["unmapped"], stats["deleted"], stats["scored"], stats.get("pending_sentiment"))
            return 0

        except Exception:
            error = traceback.format_exc()
            log.error("Run %d failed:\n%s", run_id, error)
            conn.rollback()
            db.finish_run(conn, run_id, "failed", stats, error=error[-5000:])
            return 1

        finally:
            conn.close()


if __name__ == "__main__":
    sys.exit(main())
