"""Download a small, fixed set of NSE result filings for developing and testing the XBRL parser.

Usage (from ml/):
    python3 -m financials.fetch_samples

For each sample company it saves, under ml/data/raw/xbrl_samples/<SYMBOL>/:
    listing_quarterly.json, listing_annual.json   every filing record NSE lists
    <seqNumber>.xml                                the filing's XBRL
    <seqNumber>_detail.json                        NSE's own JSON figures for the same filing
                                                   (used to cross-check what the parser extracts)

Only this script talks to NSE, at ~1 request/second, so parser work can iterate offline.
Already-downloaded files are skipped, so it can be re-run safely.
"""

import json
import logging
import sys
import time
from datetime import datetime

from fundamentals.nse_client import NSEResultsClient

from .config import SAMPLE_DIR, SAMPLE_SYMBOLS

log = logging.getLogger("financials.fetch_samples")

RECENT_FILINGS = 8      # newest filings kept per company
OLD_FILINGS_FROM = 2019  # plus the oldest half-year filings back to this year, for older formats


def filing_date(record):
    return datetime.strptime(record["toDate"], "%d-%b-%Y")


def pick_filings(records):
    """Newest filings (both statement types) plus a few older half-year ones."""

    with_xbrl = [r for r in records if r.get("xbrl") and r["xbrl"].endswith(".xml")]
    with_xbrl.sort(key=filing_date, reverse=True)

    recent = with_xbrl[:RECENT_FILINGS]
    old_half_years = [
        r for r in with_xbrl[RECENT_FILINGS:]
        if filing_date(r).month in (3, 9) and filing_date(r).year >= OLD_FILINGS_FROM
    ][-2:]
    return recent + old_half_years


def main():
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s", datefmt="%H:%M:%S")
    client = NSEResultsClient(pause=1.0)

    for i, symbol in enumerate(SAMPLE_SYMBOLS, 1):
        out = SAMPLE_DIR / symbol
        out.mkdir(parents=True, exist_ok=True)

        records = []
        for period in ("Quarterly", "Annual"):
            path = out / f"listing_{period.lower()}.json"
            if path.exists():
                listed = json.loads(path.read_text())
            else:
                listed = client.list_filings(symbol, period)
                path.write_text(json.dumps(listed, indent=1))
            records += listed

        picked = pick_filings(records)
        saved = 0
        for record in picked:
            seq = record["seqNumber"]
            xml_path, detail_path = out / f"{seq}.xml", out / f"{seq}_detail.json"

            if not xml_path.exists():
                client.session or client._new_session()
                response = client.session.get(record["xbrl"], timeout=30)
                time.sleep(client.pause)
                if response.ok and response.text.lstrip().startswith("<"):
                    xml_path.write_text(response.text)
                    saved += 1

            if not detail_path.exists():
                detail = client.fetch_filing_data(record)
                detail_path.write_text(json.dumps({"record": record, "detail": detail}, indent=1))

        log.info("[%d/%d] %s: %d filings listed, %d picked, %d new XBRL files",
                 i, len(SAMPLE_SYMBOLS), symbol, len(records), len(picked), saved)


if __name__ == "__main__":
    sys.exit(main())
