"""Collect income statement, balance sheet and cash flow from NSE result XBRL filings.

Usage (from ml/):
    python3 -m financials.collect --symbols KPITTECH DIXON
    python3 -m financials.collect --all                  # every EQ company with an ISIN
    python3 -m financials.collect --all --limit 50 --since 2019
    python3 -m financials.collect --all --refresh        # re-download and re-store everything
    python3 -m financials.collect --all --reparse        # re-parse cached XBRL (after parser fixes)

    # Offline: read listings + XBRL from a cache dir, no network at all
    python3 -m financials.collect --from-cache data/raw/xbrl_samples --all-in-cache

For each company: list its Quarterly and Annual filings, keep those with an XBRL (.xml) file,
skip the ones already stored, download the XBRL into ml/data/raw/xbrl/<SYMBOL>/<seq>.xml
(cached; never re-downloaded unless --refresh), parse it and upsert one `financial_filings`
row per filing. Consolidated and standalone results are separate filings, so both are stored.

Resumable: work is committed per company, and stored seq numbers are skipped next run.
One bad filing or company is logged and skipped. Only one run at a time (lock file).
"""

import argparse
import fcntl
import json
import logging
import sys
import time
from collections import Counter
from contextlib import contextmanager
from datetime import datetime
from logging.handlers import RotatingFileHandler

from news_pipeline.db import get_connection

from . import store
from .config import ML_DIR, XBRL_CACHE_DIR

log = logging.getLogger("financials.collect")

LOG_DIR = ML_DIR / "logs"
LOG_FILE = LOG_DIR / "financials_collect.log"
LOCK_FILE = LOG_DIR / "financials_collect.lock"

# "Integrated": results filed from April 2025 through SEBI's Integrated Filing (Financial).
# NSE's old results listing stops at Dec 2024; newer quarters are only in the integrated one.
PERIODS = ("Quarterly", "Annual", "Integrated")
DEFAULT_SINCE_YEAR = 2016
DOWNLOAD_RETRIES = 4

INTEGRATED_URL = "https://www.nseindia.com/api/integrated-filing-results"
INTEGRATED_TYPE = "Integrated Filing- Financials"
# Integrated filings have their own seq_Id numbering; offset it so it can never collide with
# the old results' seqNumber in the unique nse_seq_number column
INTEGRATED_SEQ_OFFSET = 10_000_000_000


def integrated_to_listing(record):
    """An integrated-filing record in the old results-listing shape the rest of the code uses."""

    return {
        "symbol": record.get("symbol"),
        "seqNumber": str(INTEGRATED_SEQ_OFFSET + int(record["seq_Id"])),
        "toDate": (record.get("qe_Date") or "").title(),          # '30-JUN-2026' -> '30-Jun-2026'
        "consolidated": "Consolidated" if record.get("consolidated") == "Consolidated" else "Non-Consolidated",
        "xbrl": record.get("xbrl"),
        "broadCastDate": record.get("broadcast_Date"),
        "exchdisstime": record.get("creation_Date"),             # broadcast + diff, like the old field
        "audited": record.get("audited"),
        "period": "Quarterly",
        "source": "integrated",
        "revisedDate": record.get("revised_Date"),
    }


def list_integrated(client, symbol):
    """Every 'Integrated Filing- Financials' record for a symbol (the API pages 20 at a time)."""

    records, page = [], 1
    while True:
        data = client._get(INTEGRATED_URL, {"index": "equities", "symbol": symbol, "page": page})
        time.sleep(client.pause)
        rows = data.get("data") if isinstance(data, dict) else None
        if not rows:
            break
        records += rows
        if len(records) >= int(data.get("totalCount") or 0) or page >= 50:
            break
        page += 1
    return [integrated_to_listing(r) for r in records
            if r.get("type") == INTEGRATED_TYPE and r.get("seq_Id") and r.get("xbrl")]


def setup_logging():
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    fmt = logging.Formatter("%(asctime)s %(levelname)s %(message)s", "%Y-%m-%d %H:%M:%S")

    file_handler = RotatingFileHandler(LOG_FILE, maxBytes=1_000_000, backupCount=5)
    file_handler.setFormatter(fmt)
    stream_handler = logging.StreamHandler(sys.stdout)
    stream_handler.setFormatter(fmt)

    root = logging.getLogger()
    root.setLevel(logging.INFO)
    root.handlers = [file_handler, stream_handler]
    logging.getLogger("urllib3").setLevel(logging.WARNING)


@contextmanager
def single_instance():
    """Skip this run if another collector is still going (it may be talking to NSE)."""

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


# ---------------------------------------------------------
# Filing sources: NSE (cached on disk) or an offline cache dir
# ---------------------------------------------------------

class NSESource:
    """Lists filings from NSE and downloads XBRL into the cache (never re-downloads unless refresh)."""

    offline = False

    def __init__(self, cache_dir, pause=1.0, refresh=False):
        from fundamentals.nse_client import NSEResultsClient

        self.cache_dir = cache_dir
        self.client = NSEResultsClient(pause=pause)
        self.refresh = refresh

    def list_filings(self, symbol, period):
        if period == "Integrated":
            records = list_integrated(self.client, symbol)
        else:
            records = self.client.list_filings(symbol, period)
        out = self.cache_dir / symbol
        out.mkdir(parents=True, exist_ok=True)
        _write_atomic(out / f"listing_{period.lower()}.json", json.dumps(records, indent=1))
        return records

    def xbrl_text(self, symbol, record):
        path = self.cache_dir / symbol / f"{record['seqNumber']}.xml"
        if path.exists() and not self.refresh:
            return path.read_text(errors="replace")

        text = self._download(record["xbrl"])
        _write_atomic(path, text)
        return text

    def _download(self, url):
        client = self.client
        for attempt in range(1, DOWNLOAD_RETRIES + 1):
            try:
                if client.session is None:
                    client._new_session()
                response = client.session.get(url, timeout=30)
                time.sleep(client.pause)
                if response.status_code == 404:
                    # The file doesn't exist on NSE's archive (common for old filings): retrying won't help
                    raise FileNotFoundError(f"XBRL not on NSE (404): {url}")
                response.raise_for_status()
                if not response.text.lstrip().startswith("<"):
                    raise ValueError("response is not XML")
                return response.text

            except FileNotFoundError:
                raise
            except Exception as exc:  # requests errors, blocked/HTML pages
                client.session = None  # fresh cookies fix most NSE 401/403s
                if attempt == DOWNLOAD_RETRIES:
                    raise RuntimeError(f"XBRL download failed ({url}): {exc}") from exc
                wait = 2 ** attempt
                log.warning("XBRL download failed (%s/%s): %s; retrying in %ds",
                            attempt, DOWNLOAD_RETRIES, exc, wait)
                time.sleep(wait)


class CacheSource:
    """Offline: listings and XBRL from a cache dir laid out like ml/data/raw/xbrl_samples/<SYMBOL>/."""

    offline = True

    def __init__(self, cache_dir):
        self.cache_dir = cache_dir

    def symbols(self):
        return sorted(p.name for p in self.cache_dir.iterdir()
                      if p.is_dir() and any(p.glob("listing_*.json")))

    def list_filings(self, symbol, period):
        path = self.cache_dir / symbol / f"listing_{period.lower()}.json"
        if not path.exists():
            return []
        data = json.loads(path.read_text())
        return data if isinstance(data, list) else []

    def has_xbrl(self, symbol, record):
        return (self.cache_dir / symbol / f"{record['seqNumber']}.xml").exists()

    def xbrl_text(self, symbol, record):
        return (self.cache_dir / symbol / f"{record['seqNumber']}.xml").read_text(errors="replace")


def _write_atomic(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(text)
    tmp.replace(path)


# ---------------------------------------------------------
# Per company
# ---------------------------------------------------------

def has_xbrl_link(record):
    url = record.get("xbrl") or ""
    return url.lower().endswith(".xml") and bool(record.get("seqNumber"))


def select_filings(source, symbol, since_year, stats, both_types=False):
    """Listed filings with an XBRL file whose period ends in or after `since_year`, one per seq number.

    Unless `both_types`, keep one statement type per period: consolidated (the whole group, what
    investors own) when filed, otherwise standalone. That halves the downloads for most companies.
    """

    by_seq = {}
    for period in PERIODS:
        for record in source.list_filings(symbol, period):
            stats["listed"] += 1
            if not has_xbrl_link(record):
                stats["no_xbrl"] += 1
                continue
            period_end = store.listing_date(record.get("toDate"))
            if period_end and period_end.year < since_year:
                stats["too_old"] += 1
                continue
            by_seq.setdefault(int(record["seqNumber"]), record)

    if not both_types:
        by_period = {}
        for record in by_seq.values():
            key = (record.get("toDate"), record.get("period"))
            kept = by_period.get(key)
            if kept is None:
                by_period[key] = record
                continue
            kept_cons = kept.get("consolidated") == "Consolidated"
            new_cons = record.get("consolidated") == "Consolidated"
            same_type_earlier = (kept_cons == new_cons and
                                 (store.listing_filing_date(record) or datetime.max) <
                                 (store.listing_filing_date(kept) or datetime.max))
            if (new_cons and not kept_cons) or same_type_earlier:
                by_period[key] = record
        stats["other_type_skipped"] = stats.get("other_type_skipped", 0) + len(by_seq) - len(by_period)
        by_seq = {int(r["seqNumber"]): r for r in by_period.values()}

    # Oldest first; consolidated before standalone for the same period
    return sorted(by_seq.values(), key=lambda r: (
        store.listing_date(r.get("toDate")) or datetime.min.date(),
        r.get("consolidated") != "Consolidated",
        int(r["seqNumber"]),
    ))


def collect_symbol(conn, source, parse_xbrl, symbol, company_ids, args, totals):
    stats = Counter()
    by_symbol, by_isin = company_ids

    records = select_filings(source, symbol, args.since, stats, args.both_statement_types)
    skip = set()
    if not (args.refresh or args.reparse):
        skip = store.stored_seq_numbers(conn, symbol, include_failed=not args.retry_failed)

    company_id = by_symbol.get(symbol)
    if company_id is None and records:
        company_id = by_isin.get((records[0].get("isin") or "").upper())
    if company_id is None:
        log.warning("%s: not in companies table (stored without company_id)", symbol)
        totals["unmapped_companies"] += 1

    for record in records:
        seq = int(record["seqNumber"])
        if seq in skip:
            stats["skipped"] += 1
            continue
        if source.offline and not source.has_xbrl(symbol, record):
            stats["not_cached"] += 1
            continue

        try:
            text = source.xbrl_text(symbol, record)
        except Exception as exc:
            # Not stored: a download problem is retried on the next run
            log.error("%s seq %s: %s", symbol, seq, exc)
            stats["failed"] += 1
            continue

        parsed, error = None, None
        try:
            parsed = parse_xbrl(text)
        except Exception as exc:
            error = f"{type(exc).__name__}: {exc}"
            log.error("%s seq %s: parse error: %s", symbol, seq, error)

        try:
            row, unmapped = store.upsert_filing(conn, record, parsed, company_id, error=error)
        except Exception as exc:
            log.error("%s seq %s: not stored: %s", symbol, seq, exc)
            stats["failed"] += 1
            continue

        stats["stored"] += 1
        totals["status"][row["parse_status"]] += 1
        if row["parse_status"] == "failed":
            stats["failed"] += 1
        for item in unmapped:
            totals["unmapped_fields"][item.split(":")[0]] += 1
            log.warning("%s seq %s: parser output not stored: %s", symbol, seq, item)

    conn.commit()
    return stats


def load_parser():
    from .xbrl_parse import parse_xbrl

    return parse_xbrl


def main(argv=None):
    parser = argparse.ArgumentParser(description="Collect financial statements from NSE XBRL filings")
    parser.add_argument("--symbols", nargs="*", help="NSE symbols, e.g. KPITTECH DIXON")
    parser.add_argument("--all", action="store_true", help="Every EQ/BE-series company with an ISIN")
    parser.add_argument("--both-statement-types", action="store_true",
                        help="Store consolidated AND standalone for each period (default: consolidated, else standalone)")
    parser.add_argument("--all-in-cache", action="store_true",
                        help="Every symbol folder in the cache dir (with --from-cache: the offline dir)")
    parser.add_argument("--limit", type=int, help="Only the first N symbols")
    parser.add_argument("--since", type=int, default=DEFAULT_SINCE_YEAR,
                        help=f"Skip filings whose period ends before this year (default {DEFAULT_SINCE_YEAR})")
    parser.add_argument("--from-cache", metavar="DIR",
                        help="Offline: read listings and XBRL from DIR/<SYMBOL>/ (no network)")
    parser.add_argument("--refresh", action="store_true",
                        help="Re-download (online) and re-store filings already stored")
    parser.add_argument("--reparse", action="store_true",
                        help="Re-parse and re-store filings already stored, from cached XBRL")
    parser.add_argument("--retry-failed", action="store_true", help="Retry filings stored as failed")
    parser.add_argument("--pause", type=float, default=1.0, help="Seconds between NSE requests")
    args = parser.parse_args(argv)

    setup_logging()

    if args.from_cache:
        from pathlib import Path

        cache_dir = Path(args.from_cache).resolve()
        if not cache_dir.is_dir():
            parser.error(f"--from-cache: {cache_dir} is not a directory")
        source = CacheSource(cache_dir)
    else:
        source = None
        cache_dir = XBRL_CACHE_DIR

    with single_instance() as acquired:
        if not acquired:
            log.info("Another financials collector is running; skipping")
            return 0

        parse_xbrl = load_parser()
        conn = get_connection()
        try:
            store.ensure_table(conn)

            symbols = [s.strip().upper() for s in (args.symbols or [])]
            if args.all:
                symbols += store.universe_symbols(conn)
            if args.all_in_cache:
                symbols += CacheSource(cache_dir).symbols() if cache_dir.is_dir() else []
            symbols = list(dict.fromkeys(symbols))
            if args.limit:
                symbols = symbols[:args.limit]
            if not symbols:
                parser.error("Pass --symbols, --all or --all-in-cache")

            if source is None:
                source = NSESource(cache_dir, pause=args.pause, refresh=args.refresh)

            company_ids = store.company_maps(conn)
            log.info("Collecting %d companies (%s, filings since %d)", len(symbols),
                     f"offline from {cache_dir}" if source.offline else "NSE", args.since)

            totals = {"companies": 0, "company_errors": 0, "unmapped_companies": 0,
                      "counts": Counter(), "status": Counter(), "unmapped_fields": Counter()}

            for index, symbol in enumerate(symbols, start=1):
                try:
                    conn.ping(reconnect=True, attempts=3, delay=5)
                    stats = collect_symbol(conn, source, parse_xbrl, symbol, company_ids, args, totals)
                except Exception as exc:
                    log.error("[%d/%d] %s: %s", index, len(symbols), symbol, exc)
                    totals["company_errors"] += 1
                    try:
                        conn.rollback()
                    except Exception:
                        pass
                    continue

                totals["companies"] += 1
                totals["counts"].update(stats)
                log.info("[%d/%d] %s: listed=%d with-xbrl=%d stored=%d skipped=%d failed=%d%s",
                         index, len(symbols), symbol, stats["listed"],
                         stats["listed"] - stats["no_xbrl"] - stats["too_old"],
                         stats["stored"], stats["skipped"], stats["failed"],
                         f" not-cached={stats['not_cached']}" if source.offline else "")

            counts = totals["counts"]
            log.info("Done: companies=%d (errors=%d, not in companies table=%d) filings stored=%d "
                     "skipped=%d failed=%d older-than-%d=%d%s parse_status=%s",
                     totals["companies"], totals["company_errors"], totals["unmapped_companies"],
                     counts["stored"], counts["skipped"], counts["failed"], args.since, counts["too_old"],
                     f" not-cached={counts['not_cached']}" if source.offline else "",
                     dict(totals["status"]))
            if totals["unmapped_fields"]:
                log.warning("Parser output that didn't fit the table: %s", dict(totals["unmapped_fields"]))
            return 1 if totals["company_errors"] else 0

        finally:
            conn.close()


if __name__ == "__main__":
    sys.exit(main())
