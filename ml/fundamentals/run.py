"""Download NSE financial results for a list of symbols into `nse_financial_results`.

Usage (from ml/):
    python3 -m fundamentals.run --symbols RELIANCE TCS
    python3 -m fundamentals.run --nifty50            # the 49 stocks in the price file
    python3 -m fundamentals.run --nifty50 --refresh  # re-fetch filings already stored

Each filing keeps its `filing_date`, so features can be joined point-in-time:
on any given day, only filings already published by that day are visible.
"""

import argparse
import logging
import sys

from . import store
from .nse_client import PERIODS, NSEResultsClient
from .parse import has_data, parse_filing

log = logging.getLogger("fundamentals")


def nifty50_symbols():
    from stock_model import prices

    return sorted(prices.load_clean()["symbol"].unique())


def fetch_symbol(client, conn, symbol, company_id, refresh=False):
    """Returns per-symbol counts: filings listed, with data, saved, skipped."""

    stats = {"listed": 0, "with_data": 0, "saved": 0, "skipped_old": 0, "no_data": 0}
    already = set() if refresh else store.existing_seq_numbers(conn, symbol)
    rows = []

    for period in PERIODS:
        for record in client.list_filings(symbol, period):
            stats["listed"] += 1

            if not has_data(record):
                stats["skipped_old"] += 1
                continue
            if int(record["seqNumber"]) in already:
                continue

            stats["with_data"] += 1
            detail = client.fetch_filing_data(record)
            if detail is None:
                stats["no_data"] += 1
                continue

            row = parse_filing(record, detail)
            if row is None:
                stats["no_data"] += 1
                continue

            row["company_id"] = company_id
            rows.append(row)

    stats["saved"] = store.save_rows(conn, rows)
    return stats


def main(argv=None):
    parser = argparse.ArgumentParser(description="Load NSE financial results")
    parser.add_argument("--symbols", nargs="*", help="NSE symbols, e.g. RELIANCE TCS")
    parser.add_argument("--nifty50", action="store_true", help="All symbols in the cleaned price file")
    parser.add_argument("--refresh", action="store_true", help="Re-fetch filings already stored")
    parser.add_argument("--pause", type=float, default=1.0, help="Seconds between NSE requests")
    args = parser.parse_args(argv)

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s",
                        datefmt="%H:%M:%S", stream=sys.stdout)

    symbols = list(args.symbols or [])
    if args.nifty50:
        symbols = nifty50_symbols()
    if not symbols:
        parser.error("Pass --symbols or --nifty50")

    conn = store.get_connection()
    store.ensure_schema(conn)
    company_ids = store.company_id_by_symbol(conn)
    client = NSEResultsClient(pause=args.pause)

    totals = {"saved": 0, "no_data": 0, "unmapped": 0}

    try:
        for index, symbol in enumerate(symbols, start=1):
            company_id = company_ids.get(symbol)
            if company_id is None:
                totals["unmapped"] += 1
                log.warning("[%d/%d] %s: not in companies table (stored without company_id)",
                            index, len(symbols), symbol)

            try:
                stats = fetch_symbol(client, conn, symbol, company_id, refresh=args.refresh)
            except RuntimeError as exc:
                log.error("[%d/%d] %s: %s", index, len(symbols), symbol, exc)
                continue

            totals["saved"] += stats["saved"]
            totals["no_data"] += stats["no_data"]
            log.info("[%d/%d] %s: listed=%d new-format=%d saved=%d (old-format skipped=%d, empty=%d)",
                     index, len(symbols), symbol, stats["listed"], stats["with_data"],
                     stats["saved"], stats["skipped_old"], stats["no_data"])

        log.info("Done: saved=%d empty=%d symbols-not-in-companies=%d",
                 totals["saved"], totals["no_data"], totals["unmapped"])
        return 0

    finally:
        conn.close()


if __name__ == "__main__":
    sys.exit(main())
