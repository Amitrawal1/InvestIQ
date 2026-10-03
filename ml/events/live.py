"""Live detection prototype (no scheduling): official feeds -> candidate events -> classifier.

Sources (checked 2026-10-03, see REPORT.md 'Data sources and terms'):
    PIB English press releases  https://www.pib.gov.in/RssMain.aspx?ModId=6&Lang=1&Regid=3&reg=3
                                (the plain URL redirects to Hindi via a cookie; '&reg=3' keeps English)
    RBI press releases          https://www.rbi.org.in/pressreleases_rss.xml
    RBI notifications           https://www.rbi.org.in/notifications_rss.xml
    SEBI                        https://www.sebi.gov.in/sebirss.xml (robots.txt allows /)
One GET per feed, 3 s apart, identifying User-Agent; nothing is crawled beyond the feed itself.

Every item gets `playbook.classify(title + description)`. A candidate is only an *alert for a human*:
nothing is added to the event set automatically (an admin confirms type, time and source; see
`event_row`). The impacts shown are the historical playbook, never generated from the text.

CLI:
    cd ml && python3 -m events.live                    # fetch the feeds once, print candidates
    cd ml && python3 -m events.live --text "RBI cuts repo rate by 25 bps"   # classify any text
    cd ml && python3 -m events.live --add 2026-10-01 10:00 monetary_policy rbi_rate easing \
            "RBI cuts repo" https://...                # print a validated events.csv row (manual path)
"""

import argparse
import csv
import html
import io
import re
import sys
import time
import xml.etree.ElementTree as ET

import pandas as pd
import requests

from .playbook import TYPE_LABELS, classify

FEEDS = {
    "PIB": "https://www.pib.gov.in/RssMain.aspx?ModId=6&Lang=1&Regid=3&reg=3",
    "RBI press releases": "https://www.rbi.org.in/pressreleases_rss.xml",
    "RBI notifications": "https://www.rbi.org.in/notifications_rss.xml",
    "SEBI": "https://www.sebi.gov.in/sebirss.xml",
}
UA = "Mozilla/5.0 (Macintosh) InvestIQ-research/1.0 (event detection prototype; low volume)"
PAUSE = 3

# Routine items that match keywords but are not market events (cuts false alarms)
NOISE = re.compile(r"appoint|recovery certificate|order for compliance|settlement order|adjudication order|"
                   r"auction (result|of)|treasury bill|weekly statistical|money market operations|"
                   r"lending rate|penalty on|imposes monetary penalty|cancels? (the )?certificate|"
                   r"visit|meets|addresses|inaugurat|exhibition|seized|arrested|smuggling", re.I)


def _clean(s):
    s = html.unescape(re.sub(r"<[^>]+>", " ", s or ""))
    return re.sub(r"\s+", " ", s).strip()


def fetch(name, url, session):
    r = session.get(url, timeout=30)
    r.raise_for_status()
    root = ET.fromstring(r.content.lstrip(b"\xef\xbb\xbf"))
    items = []
    for it in root.iter("item"):
        items.append({"source": name, "title": _clean(it.findtext("title")),
                      "description": _clean(it.findtext("description"))[:600],
                      "link": (it.findtext("link") or "").strip(), "pub_date": (it.findtext("pubDate") or "").strip()})
    return items


def scan(feeds=FEEDS, limit_per_feed=40):
    s = requests.Session()
    s.headers["User-Agent"] = UA
    rows = []
    for name, url in feeds.items():
        try:
            items = fetch(name, url, s)[:limit_per_feed]
        except Exception as e:  # noqa: BLE001
            print(f"  {name}: failed ({e})", file=sys.stderr)
            items = []
        for it in items:
            text = f"{it['title']}. {it['description']}"
            c = classify(text)
            noise = bool(NOISE.search(it["title"]))
            rows.append({**it, "event_type": c["event_type"], "subtype": c["subtype"], "stance": c["stance"],
                         "confidence": c["confidence"], "matched": "; ".join(c["matched"]),
                         "mentioned_groups": "; ".join(c["mentioned_groups"]),
                         "candidate": c["event_type"] != "unclassified" and not noise})
        time.sleep(PAUSE)
    return pd.DataFrame(rows)


VALID_TIME = re.compile(r"^(pre_open|after_close|[0-2]\d:[0-5]\d|)$")


def event_row(date, time_ist, event_type, subtype, stance, title, source_url, scope="india", surprise="high",
              description="", source_kind="official", date_confidence="high", confounders="", event_id="NEW"):
    """Manual 'add event' path: validate and return a CSV line in events.csv format (printed, not written)."""
    pd.Timestamp(date)
    if event_type not in TYPE_LABELS:
        raise ValueError(f"event_type must be one of {sorted(TYPE_LABELS)}")
    if not VALID_TIME.match(time_ist or ""):
        raise ValueError("time_ist: HH:MM (IST), pre_open, after_close or empty")
    if not re.match(r"^https?://", source_url):
        raise ValueError("source_url must be a URL (official source preferred)")
    buf = io.StringIO()
    csv.writer(buf).writerow([event_id, date, time_ist, event_type, subtype, stance, scope, surprise, title,
                              description, source_url, source_kind, date_confidence, confounders])
    return buf.getvalue().strip()


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--text")
    ap.add_argument("--add", nargs=7, metavar=("DATE", "TIME", "TYPE", "SUBTYPE", "STANCE", "TITLE", "URL"))
    ap.add_argument("--save", help="write the scanned items to this CSV")
    a = ap.parse_args(argv)
    if a.text:
        import json
        print(json.dumps(classify(a.text), indent=2, default=str))
        return
    if a.add:
        print(event_row(*a.add))
        return
    df = scan()
    if a.save:
        df.to_csv(a.save, index=False)
    pd.set_option("display.width", 220)
    pd.set_option("display.max_colwidth", 90)
    print(f"{len(df)} items, {int(df.candidate.sum())} candidates")
    print(df[df.candidate][["source", "title", "event_type", "stance", "confidence"]].to_string())


if __name__ == "__main__":
    main()
