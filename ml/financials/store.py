"""MySQL storage for parsed XBRL filings: the `financial_filings` table (one row per NSE filing).

Columns mirror the parser output (see README.md) flattened with prefixes:
    inc_*  current-quarter P&L        ytd_*  year-to-date P&L (+ ytd_months)
    bs_*   balance sheet              cf_*   cash flow (+ cf_months)

Money is INR crore (DECIMAL(20,4)), EPS is rupees (DECIMAL(14,4)). Each row keeps the
`filing_date` from NSE's listing, so features can be joined point-in-time.

The connection comes from news_pipeline.db.get_connection (backend/.env, TiDB Cloud TLS, IST).
"""

import json
from datetime import date, datetime
from decimal import Decimal, InvalidOperation

TABLE = "financial_filings"

INCOME_FIELDS = [
    "revenue", "other_income", "total_income", "total_expenses",
    "cost_of_materials", "employee_expense", "finance_costs", "depreciation",
    "profit_before_exceptional", "exceptional_items", "profit_before_tax",
    "tax", "net_profit", "net_profit_owners", "eps_basic", "eps_diluted",
]
BALANCE_SHEET_FIELDS = [
    "total_assets", "non_current_assets", "current_assets",
    "cash_and_equivalents", "inventories", "trade_receivables",
    "total_equity", "equity_owners", "non_controlling_interest",
    "borrowings_current", "borrowings_noncurrent", "total_debt",
    "non_current_liabilities", "current_liabilities", "trade_payables",
]
CASH_FLOW_FIELDS = [
    "operating_cf", "investing_cf", "financing_cf", "capex", "net_change_in_cash",
]
PER_SHARE_FIELDS = {"eps_basic", "eps_diluted"}

# parser section -> (column prefix, fields, has its own `months`)
SECTIONS = {
    "income": ("inc_", INCOME_FIELDS, False),
    "income_ytd": ("ytd_", INCOME_FIELDS, True),
    "balance_sheet": ("bs_", BALANCE_SHEET_FIELDS, False),
    "cash_flow": ("cf_", CASH_FLOW_FIELDS, True),
}

MONEY_SCALE = Decimal("0.0001")


def _value_columns():
    columns = []
    for prefix, fields, has_months in SECTIONS.values():
        if has_months:
            columns.append((f"{prefix}months", "TINYINT NULL"))
        for field in fields:
            ddl = "DECIMAL(14,4) NULL" if field in PER_SHARE_FIELDS else "DECIMAL(20,4) NULL"
            columns.append((f"{prefix}{field}", ddl))
    return columns


VALUE_COLUMNS = _value_columns()

TABLE_SQL = f"""
CREATE TABLE IF NOT EXISTS {TABLE} (
    id BIGINT NOT NULL AUTO_INCREMENT PRIMARY KEY,
    company_id INT NULL,
    symbol VARCHAR(50) NOT NULL,
    isin VARCHAR(20) NULL,
    statement_type ENUM('consolidated', 'standalone') NULL,
    format VARCHAR(20) NULL,
    period_start DATE NULL,
    period_end DATE NOT NULL,
    months TINYINT NULL,
    /* When the market could first see these numbers (IST) - used for point-in-time joins */
    filing_date DATETIME NULL,

    {(","+chr(10)+"    ").join(f"{name} {ddl}" for name, ddl in VALUE_COLUMNS)},

    nse_seq_number BIGINT NOT NULL,
    xbrl_url VARCHAR(500) NULL,
    parse_status ENUM('ok', 'partial', 'failed') NOT NULL,
    warnings JSON NULL,
    created_at TIMESTAMP NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,

    UNIQUE KEY uq_financial_filings_seq (nse_seq_number),
    KEY idx_financial_filings_symbol_period (symbol, period_end),
    KEY idx_financial_filings_company (company_id),
    KEY idx_financial_filings_filing_date (filing_date)
)
"""

COLUMNS = [
    "company_id", "symbol", "isin", "statement_type", "format",
    "period_start", "period_end", "months", "filing_date",
    *[name for name, _ in VALUE_COLUMNS],
    "nse_seq_number", "xbrl_url", "parse_status", "warnings",
]

UPSERT_SQL = f"""
INSERT INTO {TABLE} ({", ".join(COLUMNS)})
VALUES ({", ".join(["%s"] * len(COLUMNS))})
ON DUPLICATE KEY UPDATE
    {", ".join(f"{c} = VALUES({c})" for c in COLUMNS if c != "nse_seq_number")}
"""

# A filing whose quarter shows neither of these is stored as `partial`
KEY_INCOME_FIELDS = ("revenue", "net_profit")

STATEMENT_TYPES = {"Consolidated": "consolidated", "Non-Consolidated": "standalone"}


def ensure_table(conn):
    cur = conn.cursor()
    cur.execute(TABLE_SQL)
    conn.commit()
    cur.close()


# ---------------------------------------------------------
# Lookups
# ---------------------------------------------------------

def company_maps(conn):
    """(symbol -> company_id, isin -> company_id) from the companies table."""

    cur = conn.cursor()
    cur.execute("SELECT id, symbol, isin FROM companies WHERE exchange = 'NSE' OR exchange IS NULL ORDER BY id")
    by_symbol, by_isin = {}, {}
    for company_id, symbol, isin in cur.fetchall():
        if symbol:
            by_symbol.setdefault(symbol.strip().upper(), company_id)
        if isin:
            by_isin.setdefault(isin.strip().upper(), company_id)
    cur.close()
    return by_symbol, by_isin


def universe_symbols(conn):
    """Every NSE main-board equity with an ISIN: series EQ, plus BE (trade-for-trade, often small caps)."""

    cur = conn.cursor()
    cur.execute("""
        SELECT DISTINCT symbol FROM companies
        WHERE series IN ('EQ', 'BE') AND isin IS NOT NULL AND symbol IS NOT NULL
        ORDER BY symbol
    """)
    symbols = [row[0].strip().upper() for row in cur.fetchall()]
    cur.close()
    return symbols


def stored_seq_numbers(conn, symbol, include_failed=True):
    """Seq numbers already stored for a symbol (optionally leaving out failed parses, to retry them)."""

    sql = f"SELECT nse_seq_number FROM {TABLE} WHERE symbol = %s"
    if not include_failed:
        sql += " AND parse_status <> 'failed'"

    cur = conn.cursor()
    cur.execute(sql, (symbol,))
    values = {int(row[0]) for row in cur.fetchall()}
    cur.close()
    return values


# ---------------------------------------------------------
# Row mapping
# ---------------------------------------------------------

def parse_listing_datetime(value):
    """'29-Jan-2025 16:37:05' / '29-Jan-2025 16:37' -> naive IST datetime (NSE times are IST)."""

    if not value or value == "-":
        return None
    for fmt in ("%d-%b-%Y %H:%M:%S", "%d-%b-%Y %H:%M", "%d-%b-%Y"):
        try:
            return datetime.strptime(value.strip(), fmt)
        except ValueError:
            continue
    return None


def listing_filing_date(record):
    """When the filing became public.

    NSE's listing record carries three timestamps:
      broadCastDate  when NSE received the company's submission
      exchdisstime   when NSE disseminated it to the market (= broadCastDate + `difference`)
      filingDate     broadCastDate truncated to the minute ('-' on some old filings)
    exchdisstime is the moment the numbers were actually public, so it is the right
    point-in-time stamp (it is never earlier than broadCastDate; usually seconds later,
    occasionally hours). It is missing on some records, so fall back to broadCastDate, then filingDate.
    """

    for field in ("exchdisstime", "broadCastDate", "filingDate"):
        value = parse_listing_datetime(record.get(field))
        if value:
            return value
    return None


def listing_date(value):
    try:
        return datetime.strptime(value.strip(), "%d-%b-%Y").date() if value else None
    except ValueError:
        return None


def _to_date(value):
    if value is None or isinstance(value, date):
        return value
    try:
        return date.fromisoformat(str(value)[:10])
    except ValueError:
        return None


def _to_decimal(value, field, unmapped):
    if value is None or isinstance(value, bool):
        if isinstance(value, bool):
            unmapped.append(f"{field}: non-numeric value {value!r}")
        return None
    try:
        number = Decimal(str(value))
    except (InvalidOperation, ValueError):
        unmapped.append(f"{field}: non-numeric value {value!r}")
        return None
    if not number.is_finite():
        unmapped.append(f"{field}: non-finite value {value!r}")
        return None

    limit = Decimal("1e10") if field in PER_SHARE_FIELDS else Decimal("1e16")
    if abs(number) >= limit:
        unmapped.append(f"{field}: {value!r} out of column range")
        return None
    return number.quantize(MONEY_SCALE)


def _to_months(value, field, unmapped):
    if value is None:
        return None
    try:
        months = int(value)
    except (TypeError, ValueError):
        unmapped.append(f"{field}: non-integer value {value!r}")
        return None
    if not 0 < months < 128:
        unmapped.append(f"{field}: {value!r} out of range")
        return None
    return months


def parse_status(parsed):
    if not parsed or not parsed.get("period_end"):
        return "failed"

    # The quarter block can be None (e.g. filed as zeros) while the year-to-date figures,
    # balance sheet or cash flow are still good, so only a filing with none of them has failed
    income = parsed.get("income")
    if not any(isinstance(parsed.get(k), dict) for k in ("income", "income_ytd", "balance_sheet", "cash_flow")):
        return "failed"
    if (parsed.get("warnings") or not isinstance(income, dict)
            or all(income.get(f) is None for f in KEY_INCOME_FIELDS)):
        return "partial"
    return "ok"


def build_row(record, parsed, company_id, error=None):
    """One `financial_filings` row from an NSE listing record plus the parser's dict.

    `parsed` may be None (download/parse error given in `error`): the row is then stored as
    `failed` with the listing's own period and statement type, so it isn't re-tried every run.
    Returns (row, unmapped) where `unmapped` lists parser output that didn't fit the table.
    """

    parsed = parsed or {}
    unmapped = []
    warnings = [str(w) for w in (parsed.get("warnings") or [])]

    listing_type = STATEMENT_TYPES.get(record.get("consolidated"))
    statement_type = parsed.get("statement_type") or listing_type
    if statement_type not in ("consolidated", "standalone"):
        unmapped.append(f"statement_type: {statement_type!r}")
        statement_type = listing_type
    if listing_type and parsed.get("statement_type") and parsed["statement_type"] != listing_type:
        warnings.append(f"statement_type {parsed['statement_type']!r} in XBRL, {listing_type!r} in NSE listing")

    symbol = record["symbol"].strip().upper()
    if parsed.get("symbol") and str(parsed["symbol"]).strip().upper() != symbol:
        warnings.append(f"symbol {parsed['symbol']!r} in XBRL differs from NSE listing {symbol!r}")

    period_end = _to_date(parsed.get("period_end")) or listing_date(record.get("toDate"))
    period_start = _to_date(parsed.get("period_start"))
    if period_start is None and not parsed:
        period_start = listing_date(record.get("fromDate"))

    row = {
        "company_id": company_id,
        "symbol": symbol,
        "isin": parsed.get("isin") or record.get("isin"),
        "statement_type": statement_type,
        "format": parsed.get("format"),
        "period_start": period_start,
        "period_end": period_end,
        "months": _to_months(parsed.get("months"), "months", unmapped),
        "filing_date": listing_filing_date(record),
        "nse_seq_number": int(record["seqNumber"]),
        "xbrl_url": record.get("xbrl"),
    }

    for section, (prefix, fields, has_months) in SECTIONS.items():
        values = parsed.get(section)
        if values is None:
            values = {}
        if not isinstance(values, dict):
            unmapped.append(f"{section}: expected dict, got {type(values).__name__}")
            values = {}
        if has_months:
            row[f"{prefix}months"] = _to_months(values.get("months"), f"{section}.months", unmapped)
        for field in fields:
            row[f"{prefix}{field}"] = _to_decimal(values.get(field), f"{section}.{field}", unmapped)
        extra = sorted(set(values) - set(fields) - {"months"})
        if extra:
            unmapped.append(f"{section}: extra keys {extra}")

    known = {"symbol", "isin", "statement_type", "format", "period_start", "period_end", "months",
             "warnings", *SECTIONS}
    extra = sorted(set(parsed) - known)
    if extra:
        unmapped.append(f"top-level extra keys {extra}")

    if error:
        warnings.append(f"error: {error}")
    warnings += [f"not stored: {u}" for u in unmapped]

    status = "failed" if error else parse_status(parsed)
    if status == "ok" and warnings:
        status = "partial"
    row["parse_status"] = status
    row["warnings"] = json.dumps(warnings) if warnings else None
    return row, unmapped


def upsert_filing(conn, record, parsed, company_id, error=None):
    """Insert or update the row for one filing (no commit). Returns (row, unmapped)."""

    row, unmapped = build_row(record, parsed, company_id, error=error)
    if row["period_end"] is None:
        raise ValueError(f"seq {record.get('seqNumber')}: no period end in XBRL or listing")

    cur = conn.cursor()
    cur.execute(UPSERT_SQL, tuple(row[c] for c in COLUMNS))
    cur.close()
    return row, unmapped
