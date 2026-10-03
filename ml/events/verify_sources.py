"""Check that every source URL in events.csv resolves; record HTTP status and page title.

Polite: one request every 2 s, identifying User-Agent, GET only (no crawling). RBI's WAF rejects
scripted requests ("Unauthorised Access"), so RBI URLs are recorded as 'blocked' and were checked by
hand (see REPORT.md). Output: ml/events/sources_check.csv

CLI: cd ml && python3 -m events.verify_sources
"""
import csv
import re
import time
from pathlib import Path

import requests

HERE = Path(__file__).resolve().parent
UA = "Mozilla/5.0 (Macintosh) InvestIQ-research/1.0 (source check; low volume)"


def title_of(html):
    m = re.search(r"<title[^>]*>(.*?)</title>", html, re.I | re.S)
    return re.sub(r"\s+", " ", m.group(1)).strip()[:140] if m else ""


def main():
    rows = list(csv.DictReader(open(HERE / "events.csv")))
    urls = sorted({r["source_url"] for r in rows})
    out = []
    for i, u in enumerate(urls):
        try:
            r = requests.get(u, headers={"User-Agent": UA}, timeout=25, allow_redirects=True)
            t = title_of(r.text) if "html" in r.headers.get("content-type", "") else r.headers.get("content-type", "")
            status = r.status_code
            if "Unauthorised Access" in r.text[:2000] or "Support ID" in r.text[:3000]:
                status = "blocked"
            if "not available at present" in r.text[:3000]:
                status = "missing"
        except Exception as e:  # noqa: BLE001
            status, t = "error", str(e)[:100]
        out.append({"source_url": u, "status": status, "title": t,
                    "events": ";".join(r["event_id"] for r in rows if r["source_url"] == u)})
        print(f"{i+1}/{len(urls)} {status} {u[:90]} | {t[:70]}")
        time.sleep(2)
    with open(HERE / "sources_check.csv", "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["source_url", "status", "title", "events"])
        w.writeheader()
        w.writerows(out)


if __name__ == "__main__":
    main()
