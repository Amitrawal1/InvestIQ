"""Client for NSE's corporate financial results (list of filings + their numbers).

Two endpoints are used:
  /api/corporates-financial-results        -> filings for a symbol, each with a real filingDate
  /api/corporates-financial-results-data   -> the reported numbers for one filing

Only filings in the "New" (Ind-AS XBRL) format carry data; older ones return
"no data found" from both this endpoint and their XBRL link.
"""

import logging
import time

import requests

log = logging.getLogger(__name__)

BASE_URL = "https://www.nseindia.com"
LIST_URL = f"{BASE_URL}/api/corporates-financial-results"
DATA_URL = f"{BASE_URL}/api/corporates-financial-results-data"
WARMUP_URL = f"{BASE_URL}/companies-listing/corporate-filings-financial-results"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/139.0 Safari/537.36"
    ),
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "en-US,en;q=0.9",
    "Referer": WARMUP_URL,
}

PERIODS = ("Quarterly", "Annual")
MAX_RETRIES = 4


class NSEResultsClient:
    def __init__(self, pause=1.0):
        self.session = None
        self.pause = pause

    def _new_session(self):
        session = requests.Session()
        session.headers.update(HEADERS)
        session.get(WARMUP_URL, timeout=20)
        self.session = session

    def _get(self, url, params):
        for attempt in range(1, MAX_RETRIES + 1):
            try:
                if self.session is None:
                    self._new_session()

                response = self.session.get(url, params=params, timeout=30)
                response.raise_for_status()
                return response.json()

            except (requests.RequestException, ValueError) as exc:
                self.session = None  # fresh cookies fix most NSE 401/403s
                if attempt == MAX_RETRIES:
                    raise RuntimeError(f"NSE request failed ({params}): {exc}") from exc

                wait = 2 ** attempt
                log.warning("NSE request failed (%s/%s): %s; retrying in %ds",
                            attempt, MAX_RETRIES, exc, wait)
                time.sleep(wait)

    def list_filings(self, symbol, period="Quarterly"):
        """All result filings for a symbol; each record includes filingDate and format."""

        data = self._get(LIST_URL, {"index": "equities", "symbol": symbol, "period": period})
        time.sleep(self.pause)

        return data if isinstance(data, list) else []

    def fetch_filing_data(self, record):
        """The reported numbers for one filing, or None when nothing is published."""

        data = self._get(DATA_URL, {
            "index": "equities",
            "params": record["params"],
            "seq_id": record["seqNumber"],
            "industry": record.get("industry") or "-",
            "ind": record.get("indAs") or "",
            "format": record.get("format") or "",
        })
        time.sleep(self.pause)

        if isinstance(data, list):
            data = data[0] if data else None
        if not isinstance(data, dict) or not isinstance(data.get("resultsData2"), dict):
            return None

        return data
