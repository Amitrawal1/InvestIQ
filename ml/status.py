"""One-screen status of InvestIQ's data jobs and tables.

Run from ml/:   python3 status.py
"""

import re
import subprocess
from datetime import datetime
from pathlib import Path

from news_pipeline.db import get_connection

LOGS = Path(__file__).resolve().parent / "logs"
PROGRESS = re.compile(r"^(\S+ \S+) INFO \[(\d+)/(\d+)\] ([^:\s]+)")


def job_progress(log_name, process_pattern):
    """(done, total, last symbol, ETA text) from a collector's log, and whether it's running."""

    running = subprocess.run(["pgrep", "-f", process_pattern], capture_output=True).returncode == 0
    path = LOGS / log_name
    if not path.exists():
        return running, None

    lines = path.read_text(errors="ignore").splitlines()
    # Only the latest run: progress lines after the last "Collecting ..." / start line
    starts = [i for i, line in enumerate(lines) if " INFO Collecting " in line or " INFO Starting" in line]
    run = lines[starts[-1]:] if starts else lines
    marks = [m for m in (PROGRESS.match(line) for line in run) if m]
    if not marks:
        return running, None

    first, last = marks[0], marks[-1]
    done, total = int(last.group(2)), int(last.group(3))
    t0 = datetime.strptime(first.group(1), "%Y-%m-%d %H:%M:%S")
    t1 = datetime.strptime(last.group(1), "%Y-%m-%d %H:%M:%S")
    per = (t1 - t0).total_seconds() / max(done - int(first.group(2)), 1)
    eta_h = per * (total - done) / 3600
    return running, (done, total, last.group(4), f"{per:.0f}s/company, ~{eta_h:.1f}h left")


def main():
    print(f"InvestIQ status  {datetime.now():%Y-%m-%d %H:%M}\n")

    print("Background jobs")
    for name, log, pattern in [
        ("Financial filings (NSE XBRL)", "financials_collect.log", "financials.collect"),
        ("Daily prices (Upstox)", "prices_collect.log", "market_data.collect_prices"),
    ]:
        running, progress = job_progress(log, pattern)
        state = "RUNNING" if running else "stopped"
        if progress:
            done, total, symbol, eta = progress
            detail = f"{done}/{total} ({done / total:.0%}), last {symbol}" + (f", {eta}" if running else "")
        else:
            detail = "no progress logged yet"
        print(f"  {name:30} {state:8} {detail}")

    conn = get_connection()
    cur = conn.cursor()

    print("\nFinancial filings (financial_filings)")
    cur.execute("SELECT COUNT(*), COUNT(DISTINCT symbol), MIN(period_end), MAX(period_end) FROM financial_filings")
    rows, companies, first, last = cur.fetchone()
    print(f"  {rows:,} filings from {companies:,} companies, periods {first} -> {last}")
    cur.execute("SELECT parse_status, COUNT(*) FROM financial_filings GROUP BY 1 ORDER BY 1")
    print("  parse status: " + ", ".join(f"{s} {n:,}" for s, n in cur.fetchall()))
    cur.execute("SELECT SUM(bs_total_assets IS NOT NULL), SUM(cf_operating_cf IS NOT NULL) FROM financial_filings")
    bs, cf = cur.fetchone()
    print(f"  with balance sheet: {int(bs or 0):,}   with cash flow: {int(cf or 0):,}")

    print("\nPrices")
    cur.execute("SELECT COUNT(*), COUNT(DISTINCT company_id), MIN(price_date), MAX(price_date) FROM stock_prices")
    rows, companies, first, last = cur.fetchone()
    print(f"  stock_prices: {rows:,} rows, {companies:,} companies, {first:%Y-%m-%d} -> {last:%Y-%m-%d}")
    cur.execute("SELECT index_name, COUNT(*), MAX(price_date) FROM index_prices GROUP BY 1")
    for name, n, latest in cur.fetchall():
        print(f"  {name}: {n:,} days, latest {latest:%Y-%m-%d}")

    print("\nNews")
    cur.execute("SELECT COUNT(*), MAX(published_at) FROM news")
    total, newest = cur.fetchone()
    cur.execute("SELECT started_at, status, fetched, inserted FROM news_ingestion_runs ORDER BY id DESC LIMIT 1")
    started, status, fetched, inserted = cur.fetchone()
    print(f"  {total:,} articles, newest {newest}; last pipeline run {started} {status} "
          f"(fetched {fetched}, new {inserted})")

    conn.close()


if __name__ == "__main__":
    main()
