"""Turn raw NSE announcement records into `news` rows (same rules as ml/app.ipynb)."""

import re
from datetime import datetime

from .config import FEED_TYPE, SOURCE

NSE_TIME_FORMAT = "%d-%b-%Y %H:%M:%S"  # e.g. 18-Sep-2026 23:59:24


def normalize_event(event_type):
    return re.sub(r"\s+", " ", str(event_type or "").strip())


# Copied from classify_event_v4 in ml/app.ipynb (the version used for the stored rows)
HIGH_PATTERNS = [
    # Board / management
    "outcome of board meeting", "change in management", "change in auditors",
    "resignation", "cessation",
    # Business / strategic
    "acquisition", "amalgamation", "merger", "demerger", "scheme of arrangement",
    "other restructuring", "corporate debt restructuring", "one time settlement",
    "sale or disposal", "diversification/disinvestment", "adoption of new line",
    "strategic, technical, manufacturing", "memorandum of understanding",
    "agreement", "arrangement",
    # Orders / operations
    "bagging/receiving of orders", "awarding of order", "order(s)/contract(s)",
    "capacity addition", "commencement of commercial production", "product launch",
    "disruption of operations", "closure of operations", "strikes/lockouts/disturbances",
    # Financial / capital
    "credit rating", "qualified institutional placement", "preferential issue",
    "issue of securities", "allotment of securities", "rights issue", "buyback",
    "open offer", "offer for sale", "utilisation of funds", "increase in authorised capital",
    # Legal / regulatory
    "litigation", "dispute", "insolvency", "forensic audit", "fraud/default/arrest",
    "fraud", "default", "arrest", "key licenses", "regulatory approvals", "orders passed",
    "action(s) initiated", "action(s) taken", "fines/penalties/dues",
    "suspension of trading", "voluntary delisting",
    # Financial-result issues
    "clarification - financial results", "reply to clarification- financial results",
    "reasons for delayed/non-submission of financial results",
    # SEBI / material disclosure
    "disclosure under sebi takeover regulations", "disclosure of material issue",
    # Guarantees / obligations
    "giving guarantees/indemnity",
    # Trading plan
    "trading plan under pit",
    # Termination
    "rescission/termination",
]

MEDIUM_PATTERNS = [
    "dividend", "integrated filing- financial", "integrated filing - financial",
    "amendment to aoa/moa", "options to purchase securities", "change in company secretary",
    "compliance officer", "retirement", "demise", "record date", "revised record date",
    "appointment", "change in director", "esop", "monitoring agency", "deviation",
    "shareholders meeting", "press release", "investor presentation", "general updates",
    "updates", "monthly business updates", "committee meeting updates", "name change",
    "address change", "name and symbol change", "certificate under sebi",
    "registrar & share transfer agent", "forfeiture", "stock split", "bonus", "conversion",
    "redemption", "closure of buy back", "post buyback public announcement",
    "rumour verification", "news verification", "corrigendum", "addendum", "amendment",
    "effect(s) on listed entity",
]

LOW_PATTERNS = [
    "copy of newspaper publication", "spurt in volume", "trading window", "price movement",
    "loss of share certificates", "integrated filing- governance",
    "integrated filing - governance", "structural digital database",
    "analysts/institutional investor meet/con. call updates", "others",
]


def classify_importance(event_type):
    """HIGH / MEDIUM / LOW, or None for event types the rules don't cover ('REVIEW')."""

    event = normalize_event(event_type).lower()
    if not event:
        return None
    if any(p in event for p in HIGH_PATTERNS):
        return "HIGH"
    if any(p in event for p in LOW_PATTERNS):
        return "LOW"
    if any(p in event for p in MEDIUM_PATTERNS):
        return "MEDIUM"
    return None


def _parse_time(value):
    try:
        return datetime.strptime(str(value).strip(), NSE_TIME_FORMAT)
    except (TypeError, ValueError):
        return None


def to_news_rows(records, isin_map, symbol_map, isin_by_id):
    """Map raw NSE records to news rows.

    Returns (rows, unmapped_symbols). Announcements for companies missing from the
    `companies` table can't be stored (news.company_id is required), so they are
    reported instead of being dropped silently.
    """

    rows, unmapped = [], []
    seen = set()

    for rec in records:
        seq_id = str(rec.get("seq_id") or "").strip()
        if not seq_id.isdigit() or seq_id in seen:
            continue
        seen.add(seq_id)

        isin = str(rec.get("sm_isin") or "").strip()
        symbol = str(rec.get("symbol") or "").strip().upper()

        company_id = isin_map.get(isin) or symbol_map.get(symbol)
        if not company_id:
            unmapped.append(symbol or isin or seq_id)
            continue

        published_at = _parse_time(rec.get("an_dt"))
        event = normalize_event(rec.get("desc")) or "NSE Announcement"
        url = str(rec.get("attchmntFile") or "").strip()

        rows.append({
            "company_id": int(company_id),
            "symbol": symbol,
            "isin": isin or isin_by_id.get(company_id, ""),
            "company_name": str(rec.get("sm_name") or "").strip(),
            "headline": event,
            "content": str(rec.get("attchmntText") or "").strip(),
            "event_type": event,
            "importance": classify_importance(event),
            "feed_type": FEED_TYPE,
            "published_at": published_at,
            "event_date": published_at.date() if published_at else None,
            "date_status": "published",
            "url": url,
            "source": SOURCE,
            "nse_seq_id": int(seq_id),
            "attachment_url": url,
            "has_xbrl": 1 if str(rec.get("hasXbrl")).strip().lower() == "true" else 0,
        })

    return rows, unmapped
