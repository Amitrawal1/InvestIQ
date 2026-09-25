"""Client for NSE's corporate announcements endpoint."""

import logging
import time

import requests

from .config import MAX_RETRIES

log = logging.getLogger(__name__)

BASE_URL = "https://www.nseindia.com"
API_URL = f"{BASE_URL}/api/corporate-announcements"

# Visiting the announcements page first gives the session the cookies NSE expects
WARMUP_URL = f"{BASE_URL}/companies-listing/corporate-filings-announcements"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/139.0 Safari/537.36"
    ),
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "en-US,en;q=0.9",
    "Referer": WARMUP_URL,
}


class NSEClient:
    def __init__(self):
        self.session = None

    def _new_session(self):
        session = requests.Session()
        session.headers.update(HEADERS)
        session.get(WARMUP_URL, timeout=20)
        self.session = session

    def fetch_day(self, day):
        """All equity announcements for one calendar day, with retries."""

        date_str = day.strftime("%d-%m-%Y")
        params = {"index": "equities", "from_date": date_str, "to_date": date_str}

        for attempt in range(1, MAX_RETRIES + 1):
            try:
                if self.session is None:
                    self._new_session()

                response = self.session.get(API_URL, params=params, timeout=30)
                response.raise_for_status()
                data = response.json()

                if isinstance(data, dict):
                    data = data.get("data", [])
                if not isinstance(data, list):
                    raise ValueError(f"Unexpected response shape: {type(data).__name__}")

                return data

            except (requests.RequestException, ValueError) as exc:
                # A fresh session (new cookies) fixes most NSE 401/403 responses
                self.session = None

                if attempt == MAX_RETRIES:
                    raise RuntimeError(f"NSE fetch failed for {date_str}: {exc}") from exc

                wait = 2 ** attempt
                log.warning("NSE fetch %s failed (attempt %d/%d): %s; retrying in %ds",
                            date_str, attempt, MAX_RETRIES, exc, wait)
                time.sleep(wait)
