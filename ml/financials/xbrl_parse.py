"""Parse an NSE/BSE result-filing XBRL instance into income, balance sheet and cash flow.

`parse_xbrl(xml_text)` is a pure function (no network, no DB) that returns the dict described in
README.md ("Parser contract"). Money is INR crore, per-share values stay in rupees, and anything
not reported is None.

How periods are found (never by context-id name):
- Each context's period comes from its XBRL dates, overridden by the `DateOfStartOfReportingPeriod`
  / `DateOfEndOfReportingPeriod` facts filed inside it. Filers often copy the quarter's dates onto
  the YTD context (e.g. a Sep filing whose YTD context says Jul-Sep but holds Apr-Sep figures), and
  those two facts carry the true period. Old (2018-2021) files sometimes omit the context
  definitions entirely, and then those facts are the only dates available.
- P&L: of the non-dimensional duration contexts ending at the period end, the shortest is the
  quarter and the longest is the year-to-date.
- Balance sheet: the non-dimensional instant context at the period end.
- Cash flow: the longest context holding the cash-flow totals (year-to-date: 6 months in Sep,
  12 in Mar). When that context is mis-dated, its depreciation/finance-cost add-backs are matched
  against the P&L contexts to find the period it really covers.
"""

import re
import xml.etree.ElementTree as ET
from datetime import date

RUPEES_PER_CRORE = 1e7

# ---------------------------------------------------------------------------
# Tag maps: output key -> local tag names, first reported one wins
# ---------------------------------------------------------------------------

INCOME_TAGS = {
    "revenue": ("RevenueFromOperations",),
    "other_income": ("OtherIncome",),
    "total_income": ("Income",),
    "total_expenses": ("Expenses",),
    "cost_of_materials": ("CostOfMaterialsConsumed",),
    "employee_expense": ("EmployeeBenefitExpense",),
    "finance_costs": ("FinanceCosts",),
    "depreciation": ("DepreciationDepletionAndAmortisationExpense",),
    "profit_before_exceptional": ("ProfitBeforeExceptionalItemsAndTax",),
    "exceptional_items": ("ExceptionalItemsBeforeTax", "ExceptionalItems"),
    "profit_before_tax": ("ProfitBeforeTax",),
    "tax": ("TaxExpense",),
    "net_profit": ("ProfitLossForPeriod",),
    "net_profit_owners": ("ProfitOrLossAttributableToOwnersOfParent",),
    "eps_basic": (
        "BasicEarningsLossPerShareFromContinuingAndDiscontinuedOperations",
        "BasicEarningsLossPerShareFromContinuingOperations",
    ),
    "eps_diluted": (
        "DilutedEarningsLossPerShareFromContinuingAndDiscontinuedOperations",
        "DilutedEarningsLossPerShareFromContinuingOperations",
    ),
}

# Banks (and some NBFCs) file the banking taxonomy. Only lines that mean the same thing as the
# non-financial keys are mapped; the rest stay None.
BANK_INCOME_TAGS = {
    "revenue": ("InterestEarned",),
    "other_income": ("OtherIncome",),
    "total_income": ("Income",),
    "total_expenses": ("ExpenditureExcludingProvisionsAndContingencies",),   # NSE's own definition
    "employee_expense": ("EmployeesCost",),
    "finance_costs": ("InterestExpended",),
    "profit_before_tax": ("ProfitLossFromOrdinaryActivitiesBeforeTax",),
    "exceptional_items": ("ExceptionalItems",),
    "tax": ("TaxExpense",),
    "net_profit": ("ProfitLossForThePeriod", "ProfitLossForPeriod"),
    "net_profit_owners": ("ProfitLossAfterTaxesMinorityInterestAndShareOfProfitLossOfAssociates",),
    "eps_basic": ("BasicEarningsPerShareAfterExtraordinaryItems",
                  "BasicEarningsPerShareBeforeExtraordinaryItems"),
    "eps_diluted": ("DilutedEarningsPerShareAfterExtraordinaryItems",
                    "DilutedEarningsPerShareBeforeExtraordinaryItems"),
}

BALANCE_TAGS = {
    "total_assets": ("Assets",),
    "non_current_assets": ("NoncurrentAssets",),
    "current_assets": ("CurrentAssets",),
    "cash_and_equivalents": ("CashAndCashEquivalents",),
    "inventories": ("Inventories",),
    "total_equity": ("Equity",),
    "equity_owners": ("EquityAttributableToOwnersOfParent",),
    "non_controlling_interest": ("NonControllingInterest",),
    "borrowings_current": ("BorrowingsCurrent",),
    "borrowings_noncurrent": ("BorrowingsNoncurrent",),
    "non_current_liabilities": ("NoncurrentLiabilities",),
    "current_liabilities": ("CurrentLiabilities",),
}

# Summed when either part is reported (receivables/payables are split current vs non-current)
BALANCE_SUMS = {
    "trade_receivables": ("TradeReceivablesCurrent", "TradeReceivablesNoncurrent"),
    "trade_payables": ("TradePayablesCurrent", "TradePayablesNoncurrent"),
}

CASH_FLOW_TAGS = {
    "operating_cf": ("CashFlowsFromUsedInOperatingActivities",),
    "investing_cf": ("CashFlowsFromUsedInInvestingActivities",),
    "financing_cf": ("CashFlowsFromUsedInFinancingActivities",),
    "net_change_in_cash": ("IncreaseDecreaseInCashAndCashEquivalents",
                           "IncreaseDecreaseInCashAndCashEquivalentsBeforeEffectOfExchangeRateChanges"),
}

CAPEX_TAGS = (
    "PurchaseOfPropertyPlantAndEquipmentClassifiedAsInvestingActivities",
    "PurchaseOfTangibleAssetsClassifiedAsInvestingActivities",        # banking taxonomy
    "PurchaseOfIntangibleAssetsClassifiedAsInvestingActivities",
    "PurchaseOfIntangibleAssetsUnderDevelopment",
)

# Tags that mark a context as holding each statement
PNL_MARKERS = ("RevenueFromOperations", "ProfitLossForPeriod", "InterestEarned",
               "ProfitLossForThePeriod", "ProfitBeforeTax")
BALANCE_MARKERS = ("Assets", "Equity", "EquityAndLiabilities", "CurrentAssets", "CurrentLiabilities",
                   "CapitalAndLiabilities")

# Lenders' balance sheets have no current/non-current split; their debt is the sum of these lines
NBFC_DEBT_TAGS = ("DebtSecurities", "Borrowings", "SubordinatedLiabilities")
BANK_DEBT_TAGS = ("Borrowings",)
CASH_FLOW_MARKERS = ("CashFlowsFromUsedInOperatingActivities", "CashFlowsFromUsedInInvestingActivities",
                     "CashFlowsFromUsedInFinancingActivities")

# Tags whose presence identifies a lender's taxonomy
BANK_MARKERS = ("InterestExpended", "GrossNonPerformingAssets", "PercentageOfGrossNpa",
                "CET1Ratio", "ProvisionsOtherThanTaxAndContingencies", "CapitalAndLiabilities")
NBFC_MARKERS = ("ImpairmentOnFinancialInstruments", "FeesAndCommissionIncome",
                "NetGainOnFairValueChanges", "DebtSecurities", "SubordinatedLiabilities")
INSURANCE_MARKERS = ("PremiumsEarnedNet", "GrossPremiumIncome", "NetPremiumIncome",
                     "PremiumEarned", "NetPremiumEarned")

# ---------------------------------------------------------------------------
# Financial-sector lines: the optional `fin_sector` block (banks, NBFCs, insurers)
#
# Added after the non-financial schema was fixed, as NEW keys only: a filing detected as
# non_financial gets no `fin_sector` key and its output is unchanged. Money is crore; ratios are
# fractions, read as filed (whatever unit they were tagged with) and range-checked.
# ---------------------------------------------------------------------------

LENDER_FORMATS = ("bank", "nbfc", "insurance")

# Flows (quarter and year-to-date P&L contexts)
FIN_FLOW_TAGS = {
    "bank": {
        "interest_income": ("InterestEarned",),
        "interest_on_advances": ("InterestOrDiscountOnAdvancesOrBills",),
        "interest_expense": ("InterestExpended",),
        "other_income": ("OtherIncome",),
        "total_income": ("Income",),
        "operating_expenses": ("OperatingExpenses",),
        "pre_provision_profit": ("OperatingProfitBeforeProvisionAndContingencies",),
        "provisions": ("ProvisionsOtherThanTaxAndContingencies",),
    },
    "nbfc": {                         # Ind-AS Division III
        "interest_income": ("InterestEarned", "InterestIncome"),
        "interest_expense": ("FinanceCosts",),
        "fee_income": ("FeesAndCommissionIncome",),
        "other_income": ("OtherIncome",),
        "total_income": ("Income",),
        "provisions": ("ImpairmentOnFinancialInstruments",),
        "total_expenses": ("Expenses",),
        "profit_before_exceptional": ("ProfitBeforeExceptionalItemsAndTax",),
    },
    "insurance": {
        "gross_premium": ("GrossPremiumsWritten", "GrossPremiumIncome"),
        "net_premium": ("NetPremiumWritten", "NetPremiumIncome"),
        "premium_earned": ("PremiumEarned",),
        "incurred_claims": ("IncurredClaims",),
        "benefits_paid": ("BenefitsPaidNet",),
        "commission": ("NetCommission", "Commission"),
        "investment_income": ("IncomeFromInvestmentsNet",),
        "underwriting_profit": ("UnderwritingProfitOrLoss",),
    },
}

# Point-in-time ratios filed inside the P&L contexts (as of the period end). name -> (tags, lo, hi):
# a value outside [lo, hi] is a keying error (e.g. 14% filed as 0.0014) and becomes None. An exact
# 0 is how consolidated bank filings leave these "not applicable", so 0 is None too.
FIN_RATIO_TAGS = {
    "bank": {
        "gross_npa_pct": (("PercentageOfGrossNpa",), 0.0005, 0.6),
        "net_npa_pct": (("PercentageOfNpa",), 0.0, 0.4),
        "cet1_ratio": (("CET1Ratio",), 0.03, 0.6),
        "at1_ratio": (("AdditionalTier1Ratio",), 0.0, 0.3),
        "roa_reported": (("ReturnOnAssets",), -0.3, 0.1),
    },
    "insurance": {
        "claims_ratio": (("IncurredClaimRatio",), 0.05, 3.0),
        "combined_ratio": (("CombinedRatio",), 0.3, 3.0),
        "solvency_ratio": (("SolvencyRatio",), 0.5, 10.0),
    },
}
# Amounts filed in the P&L contexts but meaning "as of the period end" (bank asset quality)
FIN_POINT_TAGS = {
    "bank": {"gross_npa": ("GrossNonPerformingAssets",), "net_npa": ("NonPerformingAssets",)},
}

# Balance sheet (instant context at the period end)
FIN_BALANCE_TAGS = {
    "bank": {
        "advances": ("Advances",), "deposits": ("Deposits",), "investments": ("Investments",),
        "borrowings": ("Borrowings",), "cash_with_rbi": ("CashAndBalancesWithReserveBankOfIndia",),
    },
    "nbfc": {
        "advances": ("Loans",), "deposits": ("Deposits",), "investments": ("Investments",),
        "borrowings": ("Borrowings",), "debt_securities": ("DebtSecurities",),
        "subordinated_liabilities": ("SubordinatedLiabilities",),
    },
    "insurance": {
        "investments": ("Investments",), "policyholders_funds": ("PolicyholdersFunds",),
        "borrowings": ("Borrowings",),
    },
}

# Insurers' P&L: found by these tags (only when the filing is detected as insurance, so other
# formats pick contexts exactly as before), and the lines that mean the same as the main schema
INSURANCE_PNL_MARKERS = ("ProfitLossAfterTax", "ProfitLossAfterTaxAndExtraordinaryItems",
                         "ProfitOrLossBeforeTax", "ProfitLossBeforeTax",
                         "GrossPremiumsWritten", "GrossPremiumIncome")
INSURANCE_INCOME_TAGS = {
    "profit_before_tax": ("ProfitOrLossBeforeTax", "ProfitLossBeforeTax"),
    "tax": ("ProvisionsForTaxes", "ProvisionForTax"),        # life: shareholders' tax; non-life: tax
    "net_profit": ("ProfitLossAfterTax", "ProfitLossAfterTaxAndExtraordinaryItems"),
    "eps_basic": ("BasicAndDilutedEPSAfterExtraordinaryItemsNetOfTaxExpenseForThePeriodNotToBeAnnualized",),
    "eps_diluted": ("BasicAndDilutedEPSAfterExtraordinaryItemsNetOfTaxExpenseForThePeriodNotToBeAnnualized",),
}


# ---------------------------------------------------------------------------
# Low-level helpers
# ---------------------------------------------------------------------------

def _local(tag):
    return tag.rsplit("}", 1)[-1]


def _date(text):
    try:
        return date.fromisoformat((text or "").strip()[:10])
    except ValueError:
        return None


def _months(start, end):
    """Whole months covered by [start, end], e.g. Apr 1 - Sep 30 -> 6."""
    if not (start and end):
        return None
    return max(1, round(((end - start).days + 1) / 30.44))


def _number(text):
    text = (text or "").strip().replace(",", "")
    if not text:
        return None
    try:
        return float(text)
    except ValueError:
        return None


def _parse_contexts(root):
    """Context id -> {"dim": bool, "start", "end", "instant"} for contexts defined in the file."""
    contexts = {}
    for node in root.iter():
        if _local(node.tag) != "context":
            continue
        info = {"dim": False, "start": None, "end": None, "instant": None}
        for child in node.iter():
            name = _local(child.tag)
            if name in ("segment", "scenario"):
                info["dim"] = True
            elif name == "startDate":
                info["start"] = _date(child.text)
            elif name == "endDate":
                info["end"] = _date(child.text)
            elif name == "instant":
                info["instant"] = _date(child.text)
        contexts[node.get("id")] = info
    return contexts


def _parse_units(root):
    """Unit id -> "money" | "per_share" | "other"."""
    units = {}
    for node in root.iter():
        if _local(node.tag) != "unit":
            continue
        measures = [(m.text or "").strip().lower() for m in node.iter() if _local(m.tag) == "measure"]
        if len(measures) == 2 and measures[0].startswith("iso4217") and "shares" in measures[1]:
            units[node.get("id")] = "per_share"
        elif measures == ["iso4217:inr"]:
            units[node.get("id")] = "money"
        elif measures and measures[0].startswith("iso4217"):
            units[node.get("id")] = "foreign"
        else:
            units[node.get("id")] = "other"
    return units


# ---------------------------------------------------------------------------
# Facts grouped by context
# ---------------------------------------------------------------------------

class _Filing:
    """Facts of one XBRL instance, indexed by context and local tag name."""

    def __init__(self, root):
        self.contexts = _parse_contexts(root)
        self.units = _parse_units(root)
        self.facts = {}        # context id -> {tag: [(text, unit_ref), ...]}
        for node in root:
            ref = node.get("contextRef")
            if not ref:
                continue
            bucket = self.facts.setdefault(ref, {})
            bucket.setdefault(_local(node.tag), []).append((node.text, node.get("unitRef")))

    def text(self, ctx, tag):
        values = self.facts.get(ctx, {}).get(tag)
        return (values[0][0] or "").strip() if values else None

    def first_text(self, tag):
        """Value of a non-numeric tag from whichever context carries it."""
        for ctx in self.facts:
            value = self.text(ctx, tag)
            if value:
                return value
        return None

    def has_any(self, ctx, tags):
        bucket = self.facts.get(ctx, {})
        return any(tag in bucket for tag in tags)

    def tag_anywhere(self, tags):
        return any(self.has_any(ctx, tags) for ctx in self.facts)

    def period(self, ctx):
        """(kind, start, end) of a context: kind is "duration", "instant" or None (unknown).

        The reporting-period facts inside a context override its declared dates.
        """
        info = self.contexts.get(ctx)
        start = _date(self.text(ctx, "DateOfStartOfReportingPeriod"))
        end = _date(self.text(ctx, "DateOfEndOfReportingPeriod"))
        if info and info["instant"]:
            return "instant", None, info["instant"]
        if end:
            return "duration", start or (info or {}).get("start"), end
        if info and info["end"]:
            return "duration", info["start"], info["end"]
        return None, None, None

    def is_dimensional(self, ctx):
        info = self.contexts.get(ctx)
        if info is not None:
            return info["dim"]
        # Undefined context (old files): only trust it if it carries its own reporting dates
        # or is referenced by the plain statement tags
        return not (self.text(ctx, "DateOfEndOfReportingPeriod")
                    or self.has_any(ctx, PNL_MARKERS + BALANCE_MARKERS + CASH_FLOW_MARKERS))

    def value(self, ctx, tag, warnings, label):
        """Numeric fact in crore (money) or rupees (per share); None when absent or nil."""
        values = self.facts.get(ctx, {}).get(tag)
        if not values:
            return None
        numbers = [(_number(text), unit) for text, unit in values]
        numbers = [(n, unit) for n, unit in numbers if n is not None]
        if not numbers:
            return None
        number, unit = numbers[0]
        if len({n for n, _ in numbers}) > 1:
            warnings.append(f"{label}: {tag} filed more than once with different values; used the first")
        kind = self.units.get(unit)
        if kind == "per_share" or unit is None and "PerShare" in tag:
            return number
        if kind == "foreign":
            warnings.append(f"{label}: {tag} is not in INR (unit {unit})")
            return None
        if kind not in ("money", None):
            return number
        return number / RUPEES_PER_CRORE

    def pick(self, ctx, tags, warnings, label):
        for tag in tags:
            number = self.value(ctx, tag, warnings, label)
            if number is not None:
                return number
        return None


# ---------------------------------------------------------------------------
# Statement builders
# ---------------------------------------------------------------------------

def _detect_format(filing, schema_href):
    """Banks file the banking taxonomy; NBFCs file Ind-AS Division III lines inside the Ind-AS one."""
    href = (schema_href or "").lower()
    if filing.tag_anywhere(INSURANCE_MARKERS) or "insurance" in href:
        return "insurance"
    if filing.tag_anywhere(BANK_MARKERS) or "bank" in href:
        return "bank"
    if "nbfc" in href or filing.tag_anywhere(NBFC_MARKERS):
        return "nbfc"
    if filing.tag_anywhere(("RevenueFromOperations", "Assets")):
        return "non_financial"
    return "unknown"


def _income(filing, ctx, fmt, statement_type, warnings, label):
    tags = {"bank": BANK_INCOME_TAGS, "insurance": INSURANCE_INCOME_TAGS}.get(fmt, INCOME_TAGS)
    income = {key: filing.pick(ctx, tags.get(key, ()), warnings, label) for key in INCOME_TAGS}

    # Some older filings omit the bottom line but give continuing + discontinued profit
    if income["net_profit"] is None and fmt != "bank":
        continuing = filing.value(ctx, "ProfitLossForPeriodFromContinuingOperations", warnings, label)
        if continuing is not None:
            extra = [filing.value(ctx, tag, warnings, label) for tag in
                     ("ProfitLossFromDiscontinuedOperationsAfterTax",
                      "ShareOfProfitLossOfAssociatesAndJointVenturesAccountedForUsingEquityMethod")]
            income["net_profit"] = continuing + sum(x for x in extra if x is not None)
            warnings.append(f"{label}: ProfitLossForPeriod missing; net profit = continuing + "
                            "discontinued operations + share of associates")

    # Diluted EPS can never exceed basic (beyond rounding), and a diluted EPS equal to the share's face value (while
    # basic differs) is the face value keyed into the wrong field
    basic, diluted = income["eps_basic"], income["eps_diluted"]
    face_value = filing.value(ctx, "FaceValueOfEquityShareCapital", [], label)
    if basic is not None and diluted is not None and abs(diluted - basic) > 0.01 and (
            (basic > 0 and diluted > basic * 1.02 + 0.02) or diluted == face_value):
        warnings.append(f"{label}: diluted EPS {diluted} inconsistent with basic EPS {basic}; "
                        "eps_diluted set to None")
        income["eps_diluted"] = None
    if fmt == "bank":
        # Banking taxonomy: owners' profit is the after-minority line; no NCI tag to reconcile
        return income

    # Owners' share must reconcile with total profit. Many consolidated filers leave the optional
    # owners/NCI split as 0.00 placeholders; that is "not reported", not a filing error.
    profit, owners = income["net_profit"], income["net_profit_owners"]
    nci = filing.value(ctx, "ProfitOrLossAttributableToNonControllingInterests", warnings, label)
    if statement_type == "standalone" and owners is None:
        income["net_profit_owners"] = profit
    elif owners == 0 and not nci:
        income["net_profit_owners"] = None
    elif profit is not None and owners is not None:
        nci = nci or 0.0
        if abs(owners + nci - profit) > max(0.02 * abs(profit), 0.05):
            warnings.append(f"{label}: owners' profit {owners:.2f} + NCI {nci:.2f} != net profit "
                            f"{profit:.2f}; net_profit_owners set to None")
            income["net_profit_owners"] = None
    return income


def _balance_sheet(filing, ctx, fmt, statement_type, warnings):
    label = "balance_sheet"
    sheet = {key: filing.pick(ctx, tags, warnings, label) for key, tags in BALANCE_TAGS.items()}
    for key, tags in BALANCE_SUMS.items():
        parts = [filing.value(ctx, tag, warnings, label) for tag in tags]
        parts = [p for p in parts if p is not None]
        sheet[key] = sum(parts) if parts else None

    if fmt == "bank":
        # Banking taxonomy: shareholders' funds = capital + reserves and surplus
        capital = filing.value(ctx, "Capital", warnings, label)
        reserves = filing.value(ctx, "ReservesAndSurplus", warnings, label)
        if sheet["total_equity"] is None and capital is not None and reserves is not None:
            sheet["total_equity"] = capital + reserves

    if statement_type == "standalone" and sheet["equity_owners"] is None:
        sheet["equity_owners"] = sheet["total_equity"]

    current, noncurrent = sheet["borrowings_current"], sheet["borrowings_noncurrent"]
    lender_debt_tags = {"bank": BANK_DEBT_TAGS, "nbfc": NBFC_DEBT_TAGS}.get(fmt)
    if current is None and noncurrent is None and lender_debt_tags:
        parts = [filing.value(ctx, tag, warnings, label) for tag in lender_debt_tags]
        parts = [p for p in parts if p is not None]
        sheet["total_debt"] = sum(parts) if parts else None
    elif current is None and noncurrent is None:
        sheet["total_debt"] = None
    else:
        sheet["total_debt"] = (current or 0.0) + (noncurrent or 0.0)

    assets = sheet["total_assets"]
    equity_and_liabilities = filing.pick(ctx, ("EquityAndLiabilities", "CapitalAndLiabilities"),
                                         warnings, label)
    if assets and equity_and_liabilities and abs(assets - equity_and_liabilities) > 0.01 * abs(assets):
        warnings.append(f"balance_sheet: assets {assets:.2f} != equity + liabilities "
                        f"{equity_and_liabilities:.2f}")
    return sheet


def _cash_flow(filing, ctx, months, warnings):
    label = "cash_flow"
    flow = {"months": months}
    flow.update({key: filing.pick(ctx, tags, warnings, label) for key, tags in CASH_FLOW_TAGS.items()})

    parts = [filing.value(ctx, tag, warnings, label) for tag in CAPEX_TAGS]
    parts = [p for p in parts if p is not None]
    investing = flow.get("investing_cf")
    if parts and all(p == 0 for p in parts) and investing is not None and abs(investing) >= 1:
        # Every capex line filed as 0.00 while money clearly went into investing: these are
        # template placeholders (e.g. KAYNES FY23 consolidated shows 0 but standalone 47 cr), not
        # real zero capex. Unknown beats a zero that would overstate free cash flow.
        warnings.append("cash_flow: capex lines filed as 0.00 despite investing outflows; treated as not reported")
        flow["capex"] = None
    elif parts:
        if any(p < 0 for p in parts):
            warnings.append("cash_flow: capex filed as negative outflow; sign flipped to positive")
        flow["capex"] = sum(abs(p) for p in parts)
    else:
        flow["capex"] = None
    return flow


def _cash_flow_period(filing, cf_ctx, pnl_contexts):
    """Months of the P&L context whose depreciation/finance costs equal the cash flow's add-backs.

    Some filers put a year-to-date cash flow in the quarter-dated context. The indirect method
    adds back the same period's depreciation and finance costs, which pins down the real period.
    Returns None when there is no clean match.
    """
    pairs = (("AdjustmentsForDepreciationAndAmortisationExpense", "DepreciationDepletionAndAmortisationExpense"),
             ("AdjustmentsForFinanceCosts", "FinanceCosts"))
    for cf_tag, pnl_tag in pairs:
        added_back = filing.value(cf_ctx, cf_tag, [], "")
        if not added_back:
            continue
        matches = {m for ctx, m in pnl_contexts
                   if m and (v := filing.value(ctx, pnl_tag, [], "")) is not None
                   and abs(v - added_back) <= 0.005 * abs(added_back)}
        if len(matches) == 1:
            return matches.pop()
    return None


def _infer_starts(filing, contexts, period_end, warnings):
    """Fill missing P&L start dates (old files that give only the period end).

    With two or more contexts, the one with the smallest top line is the quarter and the one with
    the largest is the year-to-date from the financial-year start. A lone context stays undated.
    """
    if len(contexts) < 2:
        return contexts
    top_line = ("RevenueFromOperations", "InterestEarned", "Income")
    ranked = sorted(contexts, key=lambda c: abs(filing.pick(c[0], top_line, [], "") or 0.0))
    fy_start = _date(filing.first_text("DateOfStartOfFinancialYear"))
    month = period_end.month - 2
    year = period_end.year + (month - 1) // 12
    quarter_start = date(year, (month - 1) % 12 + 1, 1)
    filled = []
    for ctx, start, end in ranked:
        if start is None and ctx == ranked[0][0]:
            start = quarter_start
        elif start is None and ctx == ranked[-1][0]:
            start = fy_start
        filled.append((ctx, start, end))
    warnings.append("P&L contexts had no start dates; quarter/year-to-date inferred from size")
    return filled


def _all_zero(section, keys):
    values = [section.get(k) for k in keys]
    return all(v in (None, 0.0) for v in values)


def _raw_ratio(filing, ctx, tags):
    """A ratio fact as filed, ignoring its unit (ReturnOnAssets is often tagged INR)."""
    for tag in tags:
        for text, _ in filing.facts.get(ctx, {}).get(tag, ()):
            number = _number(text)
            if number is not None:
                return number
    return None


def _fin_flows(filing, ctx, fmt, warnings, label):
    flows = {key: filing.pick(ctx, tags, warnings, label) for key, tags in FIN_FLOW_TAGS[fmt].items()}
    if fmt in ("bank", "nbfc"):
        income, expense = flows["interest_income"], flows["interest_expense"]
        flows["net_interest_income"] = income - expense if income is not None and expense is not None else None
    if fmt == "nbfc":
        # Division III has no opex / pre-provision lines: derive them from the totals
        total, finance, impairment = flows["total_expenses"], flows["interest_expense"], flows["provisions"]
        flows["operating_expenses"] = (total - finance - impairment
                                       if None not in (total, finance, impairment) else None)
        pbe = flows["profit_before_exceptional"]
        flows["pre_provision_profit"] = pbe + impairment if None not in (pbe, impairment) else None
    return flows


def _fin_point_in_time(filing, contexts, fmt, warnings):
    """Ratios / NPA amounts as of the period end, from the first P&L context that files them."""
    out = {}
    for key, (tags, lo, hi) in FIN_RATIO_TAGS.get(fmt, {}).items():
        value = next((v for v in (_raw_ratio(filing, c, tags) for c in contexts) if v), None)
        if value is not None and key == "solvency_ratio" and 0.005 <= value < 0.1:
            # IRDAI solvency (1.5-3x) filed as a percentage then divided by 100 (e.g. 0.0267 for 2.67)
            warnings.append(f"fin_sector: solvency ratio {value} looks divided by 100; used {value * 100:g}")
            value *= 100
        if value is not None and not lo <= value <= hi:
            warnings.append(f"fin_sector: {key} {value} outside [{lo}, {hi}]; set to None")
            value = None
        out[key] = value
    for key, tags in FIN_POINT_TAGS.get(fmt, {}).items():
        out[key] = next((v for v in (filing.pick(c, tags, warnings, "fin_sector") for c in contexts) if v), None)
    if fmt == "bank" and out.get("net_npa_pct") == 0.0 and not out.get("gross_npa_pct"):
        out["net_npa_pct"] = None
    return out


def _fin_balance(filing, ctx, fmt, warnings):
    label = "fin_sector.balance_sheet"
    sheet = {key: filing.pick(ctx, tags, warnings, label) for key, tags in FIN_BALANCE_TAGS[fmt].items()}
    # Shareholders' funds: banks and insurers file capital + reserves (insurers' own
    # ShareholdersFunds line is unreliable); NBFCs file Ind-AS Equity
    if fmt == "nbfc":
        sheet["net_worth"] = filing.pick(ctx, ("Equity",), warnings, label)
    else:
        capital = filing.pick(ctx, ("Capital", "ShareCapital"), warnings, label)
        reserves = filing.value(ctx, "ReservesAndSurplus", warnings, label)
        sheet["net_worth"] = capital + reserves if capital is not None and reserves is not None else None
    return None if _all_zero(sheet, sheet) else sheet


def _fin_sector(filing, fmt, quarter_ctx, ytd_ctx, ytd_months, bs_ctx):
    """The `fin_sector` block: lender / insurer lines the main schema has no place for.

    Its warnings stay inside the block, so the filing's main `warnings` list is unchanged.
    """
    warnings = []
    block = {"format": fmt,
             "quarter": _fin_flows(filing, quarter_ctx, fmt, warnings, "fin_sector.quarter"),
             "ytd": None, "balance_sheet": None}
    if ytd_ctx is not None:
        block["ytd"] = {"months": ytd_months, **_fin_flows(filing, ytd_ctx, fmt, warnings, "fin_sector.ytd")}
    contexts = [quarter_ctx] + ([ytd_ctx] if ytd_ctx is not None else [])
    block["quarter"].update(_fin_point_in_time(filing, contexts, fmt, warnings))
    if bs_ctx is not None:
        block["balance_sheet"] = _fin_balance(filing, bs_ctx, fmt, warnings)
    block["warnings"] = warnings
    return block


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def parse_xbrl(xml_text: str, fin_sector_format: str | None = None) -> dict:
    """Parse one XBRL results filing into the README contract. Raises ValueError on invalid XML.

    Filings detected as bank / nbfc / insurance also get a `fin_sector` block (README). Pass
    `fin_sector_format` to build that block with a given format's tags whatever the detected format
    (e.g. an NBFC quarter whose markers were missing and that was detected as non_financial);
    without it, non_financial output is exactly what it always was.
    """

    if isinstance(xml_text, bytes):
        xml_text = xml_text.decode("utf-8", errors="replace")
    xml_text = xml_text.lstrip("﻿ \t\r\n")
    try:
        root = ET.fromstring(xml_text.encode("utf-8"))
    except ET.ParseError as error:
        raise ValueError(f"invalid XBRL XML: {error}") from error

    filing = _Filing(root)
    warnings = []

    schema_href = next((node.get("{http://www.w3.org/1999/xlink}href") for node in root
                        if _local(node.tag) == "schemaRef"), None)
    fmt = _detect_format(filing, schema_href)

    nature = (filing.first_text("NatureOfReportStandaloneConsolidated") or "").lower()
    statement_type = ("consolidated" if "consolidated" in nature
                      else "standalone" if "standalone" in nature else None)
    if statement_type is None:
        warnings.append("statement type (standalone/consolidated) not stated")

    symbol = filing.first_text("Symbol")
    if not symbol:
        ident = next((node.text for node in root.iter() if _local(node.tag) == "identifier"), None)
        symbol = (ident or "").strip() or None
    isin = filing.first_text("ISIN") or filing.first_text("ISINOfEquityShares")

    result = {
        "symbol": symbol.strip().upper() if symbol else None,
        "isin": isin,
        "statement_type": statement_type,
        "format": fmt,
        "period_start": None,
        "period_end": None,
        "months": None,
        "income": None,
        "income_ytd": None,
        "balance_sheet": None,
        "cash_flow": None,
        "warnings": warnings,
    }

    # --- P&L contexts: non-dimensional durations carrying P&L lines --------------------------
    pnl = []
    pnl_markers = PNL_MARKERS + (INSURANCE_PNL_MARKERS if fmt == "insurance" else ())
    for ctx in filing.facts:
        if filing.is_dimensional(ctx) or not filing.has_any(ctx, pnl_markers):
            continue
        kind, start, end = filing.period(ctx)
        if kind == "duration" and end:
            pnl.append((ctx, start, end))
    if not pnl:
        warnings.append("no profit-and-loss context found")
        return result

    period_end = max(end for _, _, end in pnl)
    at_end = [(ctx, start, end) for ctx, start, end in pnl if end == period_end]
    if any(start is None for _, start, _ in at_end):
        at_end = _infer_starts(filing, at_end, period_end, warnings)
    at_end.sort(key=lambda item: (item[1] is None, -(item[1] or date.min).toordinal()))
    quarter_ctx, quarter_start, _ = at_end[0]           # latest start = shortest period
    ytd_ctx, ytd_start, _ = at_end[-1]
    months = _months(quarter_start, period_end)
    if quarter_start is None:
        warnings.append("current period has no start date")

    result.update(period_start=quarter_start.isoformat() if quarter_start else None,
                  period_end=period_end.isoformat(), months=months)
    if len(pnl) > len(at_end):
        warnings.append("P&L contexts ending before the period end were ignored")

    income = _income(filing, quarter_ctx, fmt, statement_type, warnings, "income")
    if _all_zero(income, INCOME_TAGS):
        warnings.append("income filed with only zeros; treated as not reported")
    else:
        result["income"] = income
    ytd_months = _months(ytd_start, period_end)
    if ytd_ctx != quarter_ctx and ytd_months and months and ytd_months > months:
        ytd = _income(filing, ytd_ctx, fmt, statement_type, warnings, "income_ytd")
        if _all_zero(ytd, INCOME_TAGS):
            warnings.append("income_ytd filed with only zeros; treated as not reported")
        else:
            result["income_ytd"] = {"months": ytd_months, **ytd}

    # --- Balance sheet: instant at period end ------------------------------------------------
    instants = [ctx for ctx in filing.facts
                if not filing.is_dimensional(ctx) and filing.has_any(ctx, BALANCE_MARKERS)]
    bs_ctx = next((ctx for ctx in instants if filing.period(ctx) == ("instant", None, period_end)), None)
    if bs_ctx is None:
        other = [ctx for ctx in instants if filing.period(ctx)[0] != "duration"]
        if other:
            bs_ctx = other[0]
            warnings.append(f"balance sheet context {bs_ctx!r} is not dated at the period end; used anyway")
    if bs_ctx is not None:
        sheet = _balance_sheet(filing, bs_ctx, fmt, statement_type, warnings)
        if _all_zero(sheet, ("total_assets", "total_equity", "current_assets", "current_liabilities")):
            warnings.append("balance sheet filed with only zeros; treated as not reported")
        else:
            result["balance_sheet"] = sheet

    # --- Cash flow: the longest non-dimensional context holding the totals -------------------
    flows = []
    for ctx in filing.facts:
        if filing.is_dimensional(ctx) or not filing.has_any(ctx, CASH_FLOW_MARKERS):
            continue
        kind, start, end = filing.period(ctx)
        if kind == "duration" and end == period_end:
            flows.append((ctx, start))
    if flows:
        flows.sort(key=lambda item: (item[1] or date.max))
        cf_ctx, cf_start = flows[0]
        cf_months = _months(cf_start, period_end)
        matched = _cash_flow_period(filing, cf_ctx, [(quarter_ctx, months), (ytd_ctx, ytd_months)])
        if matched and matched != cf_months:
            warnings.append(f"cash flow sits in a context dated {cf_months} months, but its "
                            f"add-backs match the {matched}-month P&L; months set to {matched}")
            cf_months = matched
        flow = _cash_flow(filing, cf_ctx, cf_months, warnings)
        if _all_zero(flow, ("operating_cf", "investing_cf", "financing_cf")):
            warnings.append("cash flow filed with only zeros; treated as not reported")
        else:
            result["cash_flow"] = flow

    # --- Financial-sector lines (new key; absent for non_financial unless asked for) ----------
    fin_fmt = fin_sector_format or (fmt if fmt in LENDER_FORMATS else None)
    if fin_fmt is not None:
        if fin_fmt not in LENDER_FORMATS:
            raise ValueError(f"fin_sector_format must be one of {LENDER_FORMATS}, not {fin_fmt!r}")
        has_ytd = ytd_ctx != quarter_ctx and ytd_months and months and ytd_months > months
        result["fin_sector"] = _fin_sector(filing, fin_fmt, quarter_ctx, ytd_ctx if has_ytd else None,
                                           ytd_months if has_ytd else None, bs_ctx)

    # --- Lender formats: say what was left out -----------------------------------------------
    if fmt in ("bank", "nbfc", "insurance"):
        warnings.append(f"{fmt} format: only lines that map cleanly to the non-financial schema "
                        "are filled; the rest are None")
    elif fmt == "unknown":
        warnings.append("unrecognised taxonomy; fields may be missing")

    return result
