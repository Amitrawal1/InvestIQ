"""Check XBRL parser output against NSE's own JSON figures and against accounting identities.

Usage (from ml/):
    python3 -m financials.validate --samples                  # every filing under SAMPLE_DIR
    python3 -m financials.validate --symbols KAYNES DIXON     # only these sample folders
    python3 -m financials.validate --samples --verbose        # show every failing check
    python3 -m financials.validate --samples --json out.json  # also write the full report

Two kinds of checks run on every filing (`<seq>.xml` + `<seq>_detail.json`):

1. Cross-source: the parser's P&L vs NSE's `resultsData2` for the same filing (NSE is in rupees
   lakhs, the parser in crore). The listing record also gives the expected period and statement type.
2. Identities / sanity on the parser output alone: assets = equity + liabilities, debt = sum of its
   parts, net profit ~ PBT - tax, cash flows add up, plausible magnitudes, expected period lengths.

Exit code is 1 when the failure rate on core fields (revenue, net_profit, eps_basic, total_assets,
operating_cf) exceeds --max-mismatch. A value the parser leaves out while NSE reports it counts as a
failure there: returning None must not look better than returning a wrong number.
"""

import argparse
import json
import logging
import sys
from collections import defaultdict
from datetime import date, datetime

from .config import SAMPLE_DIR

log = logging.getLogger("financials.validate")

LAKH_TO_CRORE = 0.01
RUPEE_TO_CRORE = 1e-7

MONEY_REL_TOL = 0.005    # cross-source: 0.5% ...
MONEY_ABS_TOL = 0.05     # ... or 5 lakh rupees, whichever is larger
EPS_ABS_TOL = 0.011      # EPS is filed to 2 decimals; allow for float noise on 0.01
IDENTITY_REL_TOL = 0.01  # balance-sheet identities: 1%
IDENTITY_ABS_TOL = 0.5
PROFIT_REL_TOL = 0.02    # net_profit ~ PBT - tax is loose: associates, discontinued ops, NCI
PROFIT_ABS_TOL = 0.5

MAX_REVENUE = 1e6        # 10 lakh crore per period: more than any Indian company
MAX_MONEY = 1e7          # anything beyond this is a units bug
MAX_EPS = 1e5

CORE_FIELDS = ("revenue", "net_profit", "eps_basic", "total_assets", "operating_cf")

PASS, FAIL, WARN, SKIP = "pass", "fail", "warn", "skip"
MISSING_PARSER, MISSING_REF = "missing_parser", "missing_nse"

# NSE resultsData2 key(s) per parser income field; values in lakhs unless per-share.
# re_proloss_ord_act is profit AFTER tax from continuing operations (before associates), not PBT:
# NSE's PBT is derived as re_proloss_ord_act + re_tax (== re_total_inc - re_oth_tot_exp + exceptional).
NSE_MONEY = {
    "revenue": ("re_net_sale",),
    "other_income": ("re_oth_inc_new", "re_oth_inc"),
    "total_income": ("re_total_inc", "re_tot_inc"),
    "total_expenses": ("re_oth_tot_exp",),
    "cost_of_materials": ("re_rawmat_consump",),
    "employee_expense": ("re_staff_cost",),
    "finance_costs": ("re_int_new", "re_int"),
    "depreciation": ("re_depr_und_exp",),
    "exceptional_items": ("re_excepn_items_new", "re_excepn_items"),
    "tax": ("re_tax",),
    "net_profit": ("re_net_profit", "re_con_pro_loss"),
}
NSE_PER_SHARE = {
    "eps_basic": ("re_basic_eps_for_cont_dic_opr", "re_basic_eps", "re_bsc_eps_bfr_exi"),
    "eps_diluted": ("re_dilut_eps_for_cont_dic_opr", "re_diluted_eps", "re_dilut_eps",
                    "re_dil_eps_bfr_exi"),
}
# Banks file a different template (listing record bank="B"): interest earned is the top line,
# re_tot_inc = interest earned + other income, re_tot_exp_exc_pro_cont = interest expended +
# operating expenses (provisions and contingencies excluded), and PBT is filed explicitly
NSE_BANK_MONEY = {
    "revenue": ("re_int_earned",),
    "other_income": ("re_oth_inc_new", "re_oth_inc"),
    "total_income": ("re_tot_inc", "re_total_inc"),
    "total_expenses": ("re_tot_exp_exc_pro_cont",),
    "employee_expense": ("re_prov_emp_pay",),
    "finance_costs": ("re_int_expd",),
    "exceptional_items": ("re_excepn_items",),
    "tax": ("re_tax",),
    "net_profit": ("re_net_profit", "re_con_pro_loss"),
}

INCOME_FIELDS = (
    "revenue", "other_income", "total_income", "total_expenses", "cost_of_materials",
    "employee_expense", "finance_costs", "depreciation", "profit_before_exceptional",
    "exceptional_items", "profit_before_tax", "tax", "net_profit", "net_profit_owners",
    "eps_basic", "eps_diluted",
)
PER_SHARE_FIELDS = ("eps_basic", "eps_diluted")
CROSS_FIELDS = (
    "revenue", "other_income", "total_income", "total_expenses", "cost_of_materials",
    "employee_expense", "finance_costs", "depreciation", "profit_before_exceptional",
    "exceptional_items", "profit_before_tax", "tax", "net_profit", "eps_basic", "eps_diluted",
    "equity",
)


# ---------------------------------------------------------------- helpers

def number(value):
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return float(value)
    text = str(value).strip().replace(",", "")
    if text in ("", "-", "None", "null", "NA"):
        return None
    try:
        return float(text)
    except ValueError:
        return None


def first(values, keys):
    for key in keys:
        value = number(values.get(key))
        if value is not None:
            return value
    return None


def parse_date(value):
    if not value:
        return None
    if isinstance(value, date):
        return value
    for fmt in ("%Y-%m-%d", "%d-%b-%Y"):
        try:
            return datetime.strptime(str(value).strip()[:11], fmt).date()
        except ValueError:
            continue
    return None


def months_between(start, end):
    if not (start and end):
        return None
    return round(((end - start).days + 1) / 30.44)


def fiscal_months(period_end):
    """Months from the Indian fiscal-year start (1 April) to period_end."""
    return (period_end.month - 3) % 12 or 12


def close(a, b, rel, abs_tol):
    return abs(a - b) <= max(rel * max(abs(a), abs(b)), abs_tol)


def fmt(value):
    if value is None:
        return "None"
    if isinstance(value, float):
        return f"{value:,.4f}".rstrip("0").rstrip(".")
    return str(value)


def check(name, kind, status, field=None, parser=None, reference=None, note=""):
    return {"check": name, "kind": kind, "field": field, "status": status,
            "parser": parser, "reference": reference, "note": note}


# ---------------------------------------------------------------- NSE reference figures

def resolve_paid_up(values):
    """re_pdup is filed in lakhs, rupees, or garbage; pick the unit that fits NSE's own EPS.

    Implied paid-up capital (crore) = shares x face value = net_profit_lakhs / eps * fv / 100.
    Returns (crore or None, note).
    """
    raw = number(values.get("re_pdup"))
    if raw is None or raw <= 0:
        return None, "re_pdup missing"

    profit = first(values, ("re_net_profit", "re_con_pro_loss"))
    eps = first(values, NSE_PER_SHARE["eps_basic"])
    face = number(values.get("re_face_val"))
    candidates = {"lakhs": raw * LAKH_TO_CRORE, "rupees": raw * RUPEE_TO_CRORE}

    if profit and eps and face and abs(eps) >= 0.1:
        implied = abs(profit / eps * face / 100)
        for unit, crore in candidates.items():
            if implied / 2 <= crore <= implied * 2:
                return crore, f"re_pdup read as {unit} (EPS-implied ~{implied:,.1f} cr)"
        return None, f"re_pdup={raw:g} fits no unit (EPS-implied ~{implied:,.1f} cr)"

    if raw < 1e6:
        return candidates["lakhs"], "re_pdup assumed lakhs (no EPS to confirm)"
    return None, f"re_pdup={raw:g} unit unknown"


def nse_reference(record, detail):
    """NSE's figures for this filing, in the parser's units. None when NSE has no JSON."""

    values = (detail or {}).get("resultsData2") or {}
    if not values:
        return None

    bank = (record.get("bank") or "N").upper() not in ("N", "") or number(values.get("re_int_earned")) is not None
    money_map = NSE_BANK_MONEY if bank else NSE_MONEY

    # A template filed with zeros (e.g. DEEPAKNTR FY19 annual) is "not reported", not a 0 match
    if all(not first(values, keys) for keys in (money_map["revenue"], money_map["total_income"],
                                                 money_map["net_profit"])):
        return None

    ref = {"_bank": bank, "_notes": {}, "_alt": {}}
    for field, keys in money_map.items():
        value = first(values, keys)
        ref[field] = None if value is None else value * LAKH_TO_CRORE
    for field, keys in NSE_PER_SHARE.items():
        ref[field] = first(values, keys)

    # PBT is not a field of its own in the non-bank template (see NSE_MONEY comment)
    explicit_pbt = first(values, ("re_pro_loss_bef_tax",))
    after_tax = number(values.get("re_proloss_ord_act"))
    if explicit_pbt is not None:
        ref["profit_before_tax"] = explicit_pbt * LAKH_TO_CRORE
    elif not bank and after_tax is not None and ref.get("tax") is not None:
        ref["profit_before_tax"] = after_tax * LAKH_TO_CRORE + ref["tax"]
        ref["_notes"]["profit_before_tax"] = "NSE PBT derived as re_proloss_ord_act + re_tax"

    if not bank and ref.get("total_income") is not None and ref.get("total_expenses") is not None:
        ref["profit_before_exceptional"] = ref["total_income"] - ref["total_expenses"]
        ref["_notes"]["profit_before_exceptional"] = "NSE derived as re_total_inc - re_oth_tot_exp"

    # Reserves are only filed with annual results; a literal 0 means "not filled in"
    reserves = number(values.get("re_res_reval"))
    if reserves:
        paid_up, note = resolve_paid_up(values)
        ref["equity"] = None if paid_up is None else reserves * LAKH_TO_CRORE + paid_up
        ref["_notes"]["equity"] = "NSE reserves (excl. revaluation) + paid-up; " + note
        # Some filers put total equity (not reserves) in re_res_reval (e.g. ROUTE FY24)
        ref["_alt"] = {"equity": (reserves * LAKH_TO_CRORE, "matches re_res_reval alone: NSE field holds total equity")}
    else:
        ref["equity"] = None
    return ref


def record_expectations(record):
    start, end = parse_date(record.get("fromDate")), parse_date(record.get("toDate"))
    consolidated = (record.get("consolidated") or "").strip().lower()
    return {
        "period_start": start,
        "period_end": end,
        "months": months_between(start, end),
        "quarterly": (record.get("period") or "").lower() == "quarterly",
        "statement_type": ("consolidated" if consolidated == "consolidated"
                           else "standalone" if consolidated else None),
        "symbol": (record.get("symbol") or "").strip().upper() or None,
        "isin": (record.get("isin") or "").strip() or None,
        "bank": (record.get("bank") or "N").strip().upper() not in ("N", ""),
        # Listing flag: B = bank template, F = NBFC (Ind-AS financial-company template)
        "format": {"B": "bank", "F": "nbfc"}.get((record.get("bank") or "").strip().upper()),
    }


# ---------------------------------------------------------------- cross-source checks

def pick_pl_block(parsed, months):
    """The parser P&L block covering `months` (income for the quarter, income_ytd for YTD)."""
    if parsed.get("months") == months:
        return parsed.get("income") or {}, "income"
    ytd = parsed.get("income_ytd") or {}
    if ytd and ytd.get("months") == months:
        return ytd, "income_ytd"
    return None, None


def diagnose(field, value, ref, parsed, block_name):
    """Best guess at why a parser value disagrees with NSE."""

    hints = []
    if value and ref:
        ratio = abs(value / ref)
        for factor, label in ((100, "lakhs"), (1e5, "thousands"), (1e7, "rupees"), (1e3, "1000x")):
            for f in (factor, 1 / factor):
                if abs(ratio - f) / f < 0.02:
                    hints.append(f"off by x{ratio:g}: units ({label}?)")
        if close(value, -ref, 0.005, 0.05):
            hints.append("sign flipped")

    other_name = "income_ytd" if block_name == "income" else "income"
    other = parsed.get(other_name) or {}
    other_value = other.get(field)
    if other_value is not None and ref is not None and close(other_value, ref, MONEY_REL_TOL, MONEY_ABS_TOL) \
            and not (value is not None and close(value, ref, MONEY_REL_TOL, MONEY_ABS_TOL)):
        hints.append(f"NSE value matches parser {other_name}.{field}: quarter/YTD context swapped")

    block = parsed.get(block_name) or {}
    if field == "net_profit" and block.get("net_profit_owners") is not None and ref is not None \
            and close(block["net_profit_owners"], ref, MONEY_REL_TOL, MONEY_ABS_TOL):
        hints.append("NSE value equals net_profit_owners (NSE reports owners' share)")
    if field == "exceptional_items" and value is not None and ref is not None \
            and close(value, -ref, MONEY_REL_TOL, MONEY_ABS_TOL):
        hints.append("NSE signs exceptional items as gain(+)/loss(-)")
    return "; ".join(hints)


def cross_checks(parsed, record, detail):
    exp = record_expectations(record)
    out = []

    # Metadata vs the listing record
    pe = parse_date(parsed.get("period_end"))
    out.append(check("period_end", "meta", PASS if pe == exp["period_end"] else FAIL,
                     parser=str(pe) if pe else None, reference=str(exp["period_end"])))
    st = parsed.get("statement_type")
    out.append(check("statement_type", "meta",
                     SKIP if exp["statement_type"] is None else
                     MISSING_PARSER if st is None else
                     PASS if st == exp["statement_type"] else FAIL,
                     parser=st, reference=exp["statement_type"]))
    if parsed.get("symbol") is not None and exp["symbol"]:
        out.append(check("symbol", "meta", PASS if parsed["symbol"].upper() == exp["symbol"] else FAIL,
                         parser=parsed["symbol"], reference=exp["symbol"]))
    if parsed.get("isin") is not None and exp["isin"]:
        out.append(check("isin", "meta", PASS if parsed["isin"] == exp["isin"] else FAIL,
                         parser=parsed["isin"], reference=exp["isin"]))
    if exp["bank"]:
        fmt_ = parsed.get("format")
        wanted = (exp["format"],) if exp["format"] else ("bank", "nbfc")
        out.append(check("format", "meta", PASS if fmt_ in wanted else FAIL,
                         parser=fmt_, reference="/".join(wanted),
                         note=f"listing bank flag {record.get('bank')!r}"))
    if exp["quarterly"]:
        out.append(check("quarter_months", "meta", PASS if parsed.get("months") == 3 else FAIL,
                         parser=parsed.get("months"), reference=3,
                         note="quarterly filing: current P&L must be 3 months"))
        ps = parse_date(parsed.get("period_start"))
        out.append(check("period_start", "meta", PASS if ps == exp["period_start"] else FAIL,
                         parser=str(ps) if ps else None, reference=str(exp["period_start"])))

    ref = nse_reference(record, detail)
    if ref is None:
        out.append(check("nse_json", "meta", SKIP, note="no NSE JSON (or NSE JSON is all zeros)"))
        return out

    block, block_name = pick_pl_block(parsed, exp["months"])
    if block is None:
        out.append(check("pl_block", "meta", FAIL, parser=parsed.get("months"), reference=exp["months"],
                         note=f"no parser P&L block of {exp['months']} months to compare with NSE"))
        block, block_name = {}, "income"

    for field in CROSS_FIELDS:
        if field == "equity":
            bs = parsed.get("balance_sheet")
            if not bs:
                continue  # no balance sheet in the XBRL at all: reported by bs:present instead
            value = bs.get("equity_owners")
            if value is None:
                value = bs.get("total_equity")
        else:
            value = block.get(field)
        reference = ref.get(field)
        note = ref["_notes"].get(field, "")
        if field != "equity":
            note = (note + "; " if note else "") + f"parser {block_name}"

        if value is None and reference is None:
            continue
        if reference is None:
            status = MISSING_REF
        elif value is None:
            status = MISSING_PARSER
        elif field in PER_SHARE_FIELDS:
            status = PASS if abs(value - reference) <= EPS_ABS_TOL else FAIL
        else:
            status = PASS if close(value, reference, MONEY_REL_TOL, MONEY_ABS_TOL) else FAIL

        alt = ref["_alt"].get(field)
        if status == FAIL and alt and close(value, alt[0], MONEY_REL_TOL, MONEY_ABS_TOL):
            status, reference, note = PASS, alt[0], f"{note}; {alt[1]}"
        if status in (FAIL, MISSING_PARSER):
            hint = diagnose(field, value, reference, parsed, block_name) if field != "equity" else ""
            note = f"{note}; {hint}" if hint else note
        out.append(check(f"nse:{field}", "cross", status, field=field,
                         parser=value, reference=reference, note=note))
    return out


# ---------------------------------------------------------------- identity / sanity checks

def identity(name, field, lhs, rhs, rel=IDENTITY_REL_TOL, abs_tol=IDENTITY_ABS_TOL, severity=FAIL, note=""):
    if lhs is None or rhs is None:
        return None
    ok = close(lhs, rhs, rel, abs_tol)
    return check(name, "identity", PASS if ok else severity, field=field, parser=lhs, reference=rhs, note=note)


def pl_identities(block, label, fmt_):
    out = []
    g = block.get
    non_financial = fmt_ in ("non_financial", "unknown", None)

    money = [g(f) for f in INCOME_FIELDS if f not in PER_SHARE_FIELDS]
    if any(v is not None for v in money) and all(not v for v in money):
        out.append(check(f"{label}:not_all_zero", "identity", FAIL, "revenue", 0, None,
                         note="every P&L line is 0: a zero-filled template, should be None (not reported)"))
        return out

    # Holds for banks (interest earned + other income) and Ind-AS NBFCs too
    if None not in (g("revenue"), g("other_income")):
        out.append(identity(f"{label}:total_income=revenue+other", "total_income",
                            g("total_income"), g("revenue") + g("other_income"),
                            rel=MONEY_REL_TOL, abs_tol=MONEY_ABS_TOL))
    if non_financial and None not in (g("total_income"), g("total_expenses")):
        out.append(identity(f"{label}:pbe=income-expenses", "profit_before_exceptional",
                            g("profit_before_exceptional"), g("total_income") - g("total_expenses"),
                            rel=MONEY_REL_TOL, abs_tol=MONEY_ABS_TOL))

    pbe, exc, pbt = g("profit_before_exceptional"), g("exceptional_items"), g("profit_before_tax")
    if None not in (pbe, exc, pbt):
        if close(pbt, pbe + exc, MONEY_REL_TOL, MONEY_ABS_TOL):
            out.append(check(f"{label}:pbt=pbe+exceptional", "identity", PASS, "profit_before_tax", pbt, pbe + exc))
        elif close(pbt, pbe - exc, MONEY_REL_TOL, MONEY_ABS_TOL):
            out.append(check(f"{label}:pbt=pbe+exceptional", "identity", WARN, "exceptional_items", pbt, pbe + exc,
                             note="holds only as pbe - exceptional: exceptional_items sign is expense-positive"))
        else:
            out.append(check(f"{label}:pbt=pbe+exceptional", "identity", FAIL, "profit_before_tax", pbt, pbe + exc))
    elif pbe is not None and pbt is not None and exc is None:
        out.append(identity(f"{label}:pbt=pbe (no exceptional)", "profit_before_tax", pbt, pbe,
                            rel=MONEY_REL_TOL, abs_tol=MONEY_ABS_TOL, severity=WARN))

    if None not in (pbt, g("tax"), g("net_profit")):
        out.append(identity(f"{label}:net_profit~pbt-tax", "net_profit", g("net_profit"), pbt - g("tax"),
                            rel=PROFIT_REL_TOL, abs_tol=PROFIT_ABS_TOL, severity=WARN,
                            note="loose: share of associates / discontinued ops sit between them"))

    np_, owners = g("net_profit"), g("net_profit_owners")
    if np_ is not None and owners is not None and abs(owners) > abs(np_) * 1.5 + 1:
        out.append(check(f"{label}:owners<=total", "identity", WARN, "net_profit_owners", owners, np_,
                         note="owners' profit much larger than total profit"))

    eps, eps_d = g("eps_basic"), g("eps_diluted")
    profit = owners if owners is not None else np_
    if eps is not None and profit is not None and abs(profit) > 0.1 and abs(eps) >= 0.05:
        same_sign = (eps > 0) == (profit > 0)
        out.append(check(f"{label}:eps_sign", "identity", PASS if same_sign else FAIL, "eps_basic", eps, profit,
                         note="EPS sign must follow profit"))
    if eps is not None and eps_d is not None and eps > 0:
        out.append(check(f"{label}:diluted<=basic", "identity",
                         PASS if eps_d <= eps + EPS_ABS_TOL else WARN, "eps_diluted", eps_d, eps))

    for field in ("revenue", "total_income", "total_expenses", "depreciation", "employee_expense",
                  "cost_of_materials", "finance_costs"):
        value = g(field)
        if value is not None and value < -MONEY_ABS_TOL:
            out.append(check(f"{label}:{field}>=0", "identity", FAIL, field, value, 0))
    return [c for c in out if c]


def magnitude_checks(parsed):
    out = []
    months = parsed.get("months") or 3
    for block_name in ("income", "income_ytd", "balance_sheet", "cash_flow"):
        block = parsed.get(block_name) or {}
        for field, value in block.items():
            if field == "months" or not isinstance(value, (int, float)):
                continue
            limit = MAX_EPS if field in PER_SHARE_FIELDS else MAX_MONEY
            if abs(value) > limit:
                out.append(check(f"magnitude:{block_name}.{field}", "identity", FAIL, field, value, limit,
                                 note="absurd magnitude: units?"))
    revenue = (parsed.get("income") or {}).get("revenue")
    if revenue is not None and revenue > MAX_REVENUE * max(months, 3) / 3:
        out.append(check("magnitude:revenue", "identity", FAIL, "revenue", revenue, MAX_REVENUE,
                         note="revenue above 10 lakh crore"))
    return out


def balance_sheet_checks(parsed):
    bs = parsed.get("balance_sheet")
    pe = parse_date(parsed.get("period_end"))
    out = []
    if not bs:
        if pe and pe.month in (3, 9):
            out.append(check("bs:present", "identity", WARN, "total_assets",
                             note=f"no balance sheet in a {pe:%b} filing (normally required)"))
        return out

    g = bs.get
    ta = g("total_assets")
    if ta is not None and ta <= 0:
        out.append(check("bs:total_assets>0", "identity", FAIL, "total_assets", ta, 0))

    if None not in (g("total_equity"), g("non_current_liabilities"), g("current_liabilities")):
        out.append(identity("bs:assets=equity+liabilities", "total_assets", ta,
                            g("total_equity") + g("non_current_liabilities") + g("current_liabilities")))
    if ta is not None and g("current_assets") is not None:
        out.append(check("bs:current<=total", "identity",
                         PASS if g("current_assets") <= ta * (1 + IDENTITY_REL_TOL) + IDENTITY_ABS_TOL else FAIL,
                         "total_assets", g("current_assets"), ta))
    if None not in (g("current_assets"), g("non_current_assets")):
        out.append(identity("bs:current+noncurrent=total", "total_assets", ta,
                            g("current_assets") + g("non_current_assets")))
    if None not in (g("equity_owners"), g("non_controlling_interest")):
        out.append(identity("bs:owners+nci=equity", "total_equity", g("total_equity"),
                            g("equity_owners") + g("non_controlling_interest")))

    parts = [g("borrowings_current"), g("borrowings_noncurrent")]
    present = [p for p in parts if p is not None]
    expected = sum(present) if present else None
    if parsed.get("format") in ("bank", "nbfc"):
        pass  # lenders don't split borrowings into current/non-current; total_debt stands alone
    elif g("total_debt") is None and expected is None:
        pass
    elif g("total_debt") is None or expected is None:
        out.append(check("bs:debt=sum(parts)", "identity", FAIL, "total_debt", g("total_debt"), expected,
                         note="total_debt and its parts disagree on presence"))
    else:
        out.append(identity("bs:debt=sum(parts)", "total_debt", g("total_debt"), expected,
                            rel=MONEY_REL_TOL, abs_tol=MONEY_ABS_TOL))

    for field in ("cash_and_equivalents", "inventories", "trade_receivables", "trade_payables",
                  "current_assets", "non_current_assets", "borrowings_current", "borrowings_noncurrent"):
        value = g(field)
        if value is not None and value < -MONEY_ABS_TOL:
            out.append(check(f"bs:{field}>=0", "identity", FAIL, field, value, 0))
    if ta is not None:
        for field in ("current_assets", "cash_and_equivalents", "inventories", "trade_receivables"):
            value = g(field)
            if value is not None and value > ta * (1 + IDENTITY_REL_TOL) + IDENTITY_ABS_TOL:
                out.append(check(f"bs:{field}<=total_assets", "identity", FAIL, field, value, ta))
    return [c for c in out if c]


def cash_flow_checks(parsed):
    cf = parsed.get("cash_flow")
    pe = parse_date(parsed.get("period_end"))
    out = []
    if not cf:
        # Cash flow in H1 results became mandatory from FY2019-20 (Sep 2019)
        if pe and pe.month in (3, 9) and pe >= date(2019, 9, 30):
            out.append(check("cf:present", "identity", WARN, "operating_cf",
                             note=f"no cash flow in a {pe:%b %Y} filing (normally required)"))
        return out

    months = cf.get("months")
    expected = fiscal_months(pe) if pe else None
    if months in (6, 12):
        status, note = PASS, ""
    elif months in (3, 9):
        status, note = WARN, "voluntary quarterly cash flow (allowed; only 6/12 are mandatory)"
    else:
        status, note = FAIL, "cash flow months should be 6 or 12"
    out.append(check("cf:months", "identity", status, "cash_flow", months, "6/12", note))
    if expected is not None and months is not None and months != expected:
        out.append(check("cf:months=fiscal_ytd", "identity", FAIL, "cash_flow", months, expected,
                         note="cash flow period is not the year-to-date ending at period_end"))

    capex = cf.get("capex")
    if capex is not None:
        out.append(check("cf:capex>=0", "identity", PASS if capex >= 0 else FAIL, "capex", capex, 0))

    flows = [cf.get(k) for k in ("operating_cf", "investing_cf", "financing_cf")]
    if None not in flows and cf.get("net_change_in_cash") is not None:
        # Filers put the FX effect on cash between the three sections and the net change, and the
        # contract has no field for it, so a gap is a warning, not proof of a parser error
        gross = sum(abs(f) for f in flows)
        ok = abs(sum(flows) - cf["net_change_in_cash"]) <= max(0.01 * gross, IDENTITY_ABS_TOL)
        out.append(check("cf:op+inv+fin=net_change", "identity", PASS if ok else WARN, "net_change_in_cash",
                         sum(flows), cf["net_change_in_cash"],
                         note="" if ok else "gap is usually EffectOfExchangeRateChangesOnCash (not in contract)"))
    return out


def period_checks(parsed):
    out = []
    ps, pe = parse_date(parsed.get("period_start")), parse_date(parsed.get("period_end"))
    months = parsed.get("months")
    if ps and pe and months is not None:
        out.append(check("period:months=dates", "identity", PASS if months_between(ps, pe) == months else FAIL,
                         "months", months, months_between(ps, pe)))
    ytd = parsed.get("income_ytd") or {}
    if ytd:
        ytd_months = ytd.get("months")
        if months is not None and ytd_months is not None:
            ok = ytd_months >= months and ytd_months in (3, 6, 9, 12)
            out.append(check("ytd:months", "identity", PASS if ok else FAIL, "months", ytd_months, months))
        if pe and ytd_months is not None and ytd_months != fiscal_months(pe):
            out.append(check("ytd:months=fiscal_ytd", "identity", WARN, "months", ytd_months, fiscal_months(pe),
                             note="YTD block is not April-to-period_end (non-April fiscal year?)"))
        q_rev, y_rev = (parsed.get("income") or {}).get("revenue"), ytd.get("revenue")
        if q_rev is not None and y_rev is not None and q_rev > 0:
            if ytd_months == months:
                out.append(identity("ytd:revenue=quarter (same length)", "revenue", y_rev, q_rev,
                                    rel=MONEY_REL_TOL, abs_tol=MONEY_ABS_TOL))
            else:
                out.append(check("ytd:revenue>=quarter", "identity",
                                 PASS if y_rev >= q_rev - MONEY_ABS_TOL else FAIL, "revenue", y_rev, q_rev))
    return [c for c in out if c]


def identity_checks(parsed):
    fmt_ = parsed.get("format")
    out = []
    out += pl_identities(parsed.get("income") or {}, "income", fmt_)
    if parsed.get("income_ytd"):
        out += pl_identities(parsed["income_ytd"], "income_ytd", fmt_)
    out += magnitude_checks(parsed)
    out += balance_sheet_checks(parsed)
    out += cash_flow_checks(parsed)
    out += period_checks(parsed)
    return out


# ---------------------------------------------------------------- running

def coverage_checks(parsed):
    """Without NSE figures, a P&L that has revenue must still carry the bottom lines."""
    out = []
    for label in ("income", "income_ytd"):
        block = parsed.get(label) or {}
        if not block.get("revenue") and not block.get("total_income"):
            continue
        for field in ("total_income", "profit_before_tax", "tax", "net_profit", "eps_basic"):
            if block.get(field) is None:
                out.append(check(f"{label}:has_{field}", "identity", MISSING_PARSER, field,
                                 note="no NSE JSON to compare; line missing from a P&L that has revenue"))
    return out


def validate_filing(parsed, record, detail):
    """All checks for one filing. `parsed` is parse_xbrl output, `record`/`detail` from NSE."""
    checks = cross_checks(parsed, record, detail)
    if any(c["check"] == "nse_json" for c in checks):
        checks += coverage_checks(parsed)
    return checks + identity_checks(parsed)


def sample_filings(symbols=None):
    """Yield (symbol, seq, xml_path, detail_path) for every sample filing that has its XML."""
    folders = sorted(p for p in SAMPLE_DIR.iterdir() if p.is_dir()) if SAMPLE_DIR.exists() else []
    wanted = {s.upper() for s in symbols} if symbols else None
    for folder in folders:
        if wanted and folder.name.upper() not in wanted:
            continue
        for xml_path in sorted(folder.glob("*.xml")):
            detail_path = folder / f"{xml_path.stem}_detail.json"
            yield folder.name, xml_path.stem, xml_path, detail_path


def run_one(parse_xbrl, symbol, seq, xml_path, detail_path):
    result = {"symbol": symbol, "seq": seq, "checks": [], "error": None}
    if not detail_path.exists():
        result["error"] = "no _detail.json (listing record) next to the XML"
        return result
    wrapper = json.loads(detail_path.read_text())
    record, detail = wrapper.get("record") or {}, wrapper.get("detail")
    exp = record_expectations(record)
    result.update(period_end=str(exp["period_end"]), statement_type=exp["statement_type"],
                  period=record.get("period"))
    try:
        parsed = parse_xbrl(xml_path.read_text(errors="replace"))
    except Exception as exc:  # a crash is a finding, not a reason to stop
        result["error"] = f"parse_xbrl raised {type(exc).__name__}: {exc}"
        ref = nse_reference(record, detail) or {}
        for field in CORE_FIELDS:
            if ref.get(field) is not None:
                result["checks"].append(check(f"nse:{field}", "cross", MISSING_PARSER, field,
                                              None, ref[field], note="parser crashed"))
        return result
    result["format"] = parsed.get("format")
    result["months"] = parsed.get("months")
    result["warnings"] = parsed.get("warnings") or []
    result["checks"] = validate_filing(parsed, record, detail)
    return result


def is_failure(c):
    return c["status"] in (FAIL, MISSING_PARSER)


def summarise(results):
    cross = defaultdict(lambda: defaultdict(int))
    idents = defaultdict(lambda: defaultdict(int))
    companies = defaultdict(lambda: defaultdict(int))
    core = defaultdict(int)

    for r in results:
        comp = companies[r["symbol"]]
        comp["filings"] += 1
        comp["errors"] += bool(r["error"])
        for c in r["checks"]:
            status = c["status"]
            if status == SKIP:
                continue
            if c["kind"] == "cross":
                cross[c["field"]][status] += 1
            else:
                idents[c["check"].split(":", 1)[-1] if c["kind"] == "meta" else c["check"]][status] += 1
            if status in (PASS, FAIL, MISSING_PARSER):
                comp["checked"] += 1
                comp["passed"] += status == PASS
            if c["field"] in CORE_FIELDS and status in (PASS, FAIL, MISSING_PARSER):
                core["checked"] += 1
                core["failed"] += is_failure(c)
                core["mismatch"] += status == FAIL
                core["missing"] += status == MISSING_PARSER

    return {
        "filings": len(results),
        "parse_errors": sum(1 for r in results if r["error"]),
        "cross": {k: dict(v) for k, v in cross.items()},
        "identity": {k: dict(v) for k, v in idents.items()},
        "companies": {k: dict(v) for k, v in companies.items()},
        "core": dict(core),
        "core_failure_rate": core["failed"] / core["checked"] if core["checked"] else None,
    }


def rate(n, d):
    return f"{100 * n / d:5.1f}%" if d else "    -"


def print_report(results, summary, verbose):
    print("\nPer filing")
    for r in results:
        head = f"  {r['symbol']:<11} {r['seq']:>8} {r.get('period_end') or '?':<10} " \
               f"{(r.get('statement_type') or '?')[:4]:<4} {(r.get('period') or '?')[:1]}"
        if r["error"]:
            print(f"{head}  ERROR {r['error']}")
            if not r["checks"]:
                continue
        n = defaultdict(int)
        for c in r["checks"]:
            n[c["status"]] += 1
        print(f"{head}  fmt={r.get('format')!s:<13} months={r.get('months')!s:<4} pass={n[PASS]:<3} "
              f"fail={n[FAIL]:<2} parser-missing={n[MISSING_PARSER]:<2} warn={n[WARN]}")
        if verbose:
            for c in r["checks"]:
                if c["status"] in (FAIL, MISSING_PARSER, WARN):
                    print(f"      {c['status'].upper():<14} {c['check']:<34} parser={fmt(c['parser'])} "
                          f"ref={fmt(c['reference'])}  {c['note']}")

    print("\nCross-source vs NSE JSON (per field)")
    print(f"  {'field':<27}{'compared':>9}{'match':>7}{'mismatch':>9}{'no-parser':>10}{'no-nse':>8}{'match%':>8}")
    for field in CROSS_FIELDS:
        s = summary["cross"].get(field)
        if not s:
            continue
        compared = s.get(PASS, 0) + s.get(FAIL, 0)
        print(f"  {field:<27}{compared:>9}{s.get(PASS, 0):>7}{s.get(FAIL, 0):>9}"
              f"{s.get(MISSING_PARSER, 0):>10}{s.get(MISSING_REF, 0):>8}{rate(s.get(PASS, 0), compared):>8}")

    print("\nIdentity, sanity and metadata checks")
    print(f"  {'check':<40}{'pass':>6}{'fail':>6}{'missing':>8}{'warn':>6}")
    for name in sorted(summary["identity"]):
        s = summary["identity"][name]
        print(f"  {name:<40}{s.get(PASS, 0):>6}{s.get(FAIL, 0):>6}{s.get(MISSING_PARSER, 0):>8}{s.get(WARN, 0):>6}")

    print("\nPer company")
    print(f"  {'symbol':<12}{'filings':>8}{'errors':>7}{'checks':>8}{'passed':>8}{'pass%':>8}")
    for symbol in sorted(summary["companies"]):
        s = summary["companies"][symbol]
        print(f"  {symbol:<12}{s['filings']:>8}{s.get('errors', 0):>7}{s.get('checked', 0):>8}"
              f"{s.get('passed', 0):>8}{rate(s.get('passed', 0), s.get('checked', 0)):>8}")

    core = summary["core"]
    print(f"\nFilings: {summary['filings']}  parse errors: {summary['parse_errors']}")
    print(f"Core fields ({', '.join(CORE_FIELDS)}): checked={core.get('checked', 0)} "
          f"mismatch={core.get('mismatch', 0)} parser-missing={core.get('missing', 0)} "
          f"failure rate={rate(core.get('failed', 0), core.get('checked', 0)).strip()}")


def main(argv=None):
    parser = argparse.ArgumentParser(description="Validate XBRL financials against NSE JSON and accounting identities")
    parser.add_argument("--samples", action="store_true", help="Every filing under the sample directory")
    parser.add_argument("--symbols", nargs="*", help="Only these sample companies")
    parser.add_argument("--verbose", action="store_true", help="Show every failing check with both values")
    parser.add_argument("--json", metavar="PATH", help="Also write per-filing results and the summary as JSON")
    parser.add_argument("--max-mismatch", type=float, default=0.02,
                        help="Max core-field failure rate before exiting non-zero (default 0.02)")
    args = parser.parse_args(argv)

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s",
                        datefmt="%H:%M:%S", stream=sys.stdout)
    if not (args.samples or args.symbols):
        parser.error("Pass --samples or --symbols")

    from .xbrl_parse import parse_xbrl

    filings = list(sample_filings(None if args.samples and not args.symbols else args.symbols))
    if not filings:
        log.error("No sample filings found under %s", SAMPLE_DIR)
        return 2

    results = [run_one(parse_xbrl, *f) for f in filings]
    summary = summarise(results)
    print_report(results, summary, args.verbose)

    if args.json:
        with open(args.json, "w") as fh:
            json.dump({"summary": summary, "filings": results}, fh, indent=1, default=str)
        log.info("Wrote %s", args.json)

    failure_rate = summary["core_failure_rate"]
    if failure_rate is None or failure_rate > args.max_mismatch:
        log.error("Core failure rate %s exceeds --max-mismatch %.1f%%",
                  "n/a" if failure_rate is None else f"{100 * failure_rate:.1f}%", 100 * args.max_mismatch)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
