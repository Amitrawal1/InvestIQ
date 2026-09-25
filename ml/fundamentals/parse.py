"""Map NSE result fields (re_*) to a tidy schema.

NSE reports values in rupees lakhs; they are converted to crore to match the
existing `financial_statements` table.
"""

from datetime import datetime

LAKH_TO_CRORE = 0.01

# NSE field -> our column. First non-null match wins for tuples.
FIELD_MAP = {
    "revenue": ("re_net_sale",),
    "other_income": ("re_oth_inc_new", "re_oth_inc"),
    "total_income": ("re_total_inc",),
    "total_expenses": ("re_oth_tot_exp",),
    "raw_material_cost": ("re_rawmat_consump",),
    "employee_cost": ("re_staff_cost",),
    "finance_costs": ("re_int_new", "re_int"),
    "depreciation": ("re_depr_und_exp",),
    "other_expenses": ("re_oth_exp",),
    "exceptional_items": ("re_excepn_items_new",),
    "profit_before_tax": ("re_proloss_ord_act",),
    "tax": ("re_tax",),
    "net_profit": ("re_net_profit", "re_con_pro_loss"),
    "reserves": ("re_res_reval",),
    "paid_up_capital": ("re_pdup",),
}

# Per-share and ratio fields are NOT in lakhs and must not be scaled
UNSCALED_MAP = {
    "eps_basic": ("re_basic_eps_for_cont_dic_opr", "re_basic_eps", "re_bsc_eps_bfr_exi"),
    "eps_diluted": ("re_dilut_eps_for_cont_dic_opr", "re_dilut_eps"),
    "face_value": ("re_face_val",),
    "debt_equity_ratio": ("re_debt_eqt_rat",),
    "debt_service_coverage": ("re_debt_ser_cov",),
    "interest_service_coverage": ("re_int_ser_cov",),
}


def _number(value):
    if value is None:
        return None
    text = str(value).strip().replace(",", "")
    if text in ("", "-", "None", "null", "NA"):
        return None
    try:
        return float(text)
    except ValueError:
        return None


def _first(values, keys):
    for key in keys:
        number = _number(values.get(key))
        if number is not None:
            return number
    return None


def _date(value, formats=("%d-%b-%Y %H:%M", "%d-%b-%Y %H:%M:%S", "%d-%b-%Y")):
    if not value:
        return None
    text = str(value).strip()
    for fmt in formats:
        try:
            return datetime.strptime(text, fmt)
        except ValueError:
            continue
    return None


def parse_filing(record, detail):
    """Combine a filing record (dates, format) with its reported numbers."""

    values = detail.get("resultsData2", {})

    filing_date = _date(record.get("filingDate")) or _date(record.get("broadCastDate"))
    period_start = _date(record.get("fromDate"))
    period_end = _date(record.get("toDate"))

    if not (filing_date and period_end):
        return None

    row = {
        "symbol": record["symbol"].strip().upper(),
        "isin": (record.get("isin") or "").strip(),
        "company_name": (record.get("companyName") or "").strip(),
        "period_type": "quarterly" if record.get("period") == "Quarterly" else "annual",
        "statement_type": "consolidated" if record.get("consolidated") == "Consolidated" else "standalone",
        "period_start": period_start.date() if period_start else None,
        "period_end": period_end.date(),
        "filing_date": filing_date,
        "audited": (record.get("audited") or "").strip() or None,
        "relating_to": (record.get("relatingTo") or "").strip() or None,
        "nse_seq_number": int(record["seqNumber"]),
    }

    for column, keys in FIELD_MAP.items():
        number = _first(values, keys)
        row[column] = None if number is None else number * LAKH_TO_CRORE

    for column, keys in UNSCALED_MAP.items():
        row[column] = _first(values, keys)

    # Shareholders' funds = reserves + paid-up capital (needed for ROE)
    if row["reserves"] is not None and row["paid_up_capital"] is not None:
        row["equity"] = row["reserves"] + row["paid_up_capital"]
    else:
        row["equity"] = None

    # A filing with no revenue and no profit carries nothing useful
    if row["revenue"] is None and row["net_profit"] is None:
        return None

    return row


def has_data(record):
    """Old-format filings (pre-2018) publish no structured numbers."""

    return (record.get("format") or "").strip().lower() == "new"
