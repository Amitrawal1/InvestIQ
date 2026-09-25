"""Point-in-time fundamental features from `nse_financial_results`.

The rule: on any date, only filings whose `filing_date` has already passed may be
used. So the "known state" of a company is rebuilt at each filing event (the moment
new numbers become public) and then joined backwards onto the month-end panel.

Quarterly filings give revenue/profit/EPS (trailing twelve months and growth);
annual filings add shareholders' equity, which quarterly filings don't report.
"""

import numpy as np
import pandas as pd

QUARTERLY_COLUMNS = [
    "symbol", "period_end", "filing_date", "statement_type",
    "revenue", "profit_before_tax", "net_profit", "eps_basic",
    "finance_costs", "total_expenses", "depreciation",
]

ANNUAL_COLUMNS = [
    "symbol", "period_end", "filing_date", "statement_type",
    "equity", "paid_up_capital", "face_value", "debt_equity_ratio", "net_profit", "revenue",
]

# Features safe to train on: all are ratios or growth rates computed from reported
# figures, so share splits and bonus issues don't affect them.
FUNDAMENTAL_FEATURES = [
    "revenue_growth_yoy", "profit_growth_yoy", "eps_growth_yoy",
    "net_margin_ttm", "pbt_margin_ttm", "margin_change_yoy",
    "interest_coverage_ttm", "roe_ttm", "debt_to_equity",
    "days_since_filing",
]

# Computed and stored, but NOT used as features: prices in the price file are
# split-adjusted while reported EPS and share counts are not, so these ratios are
# wrong by the split factor after a bonus/split (e.g. Reliance's 1:1 bonus in 2024
# halves the apparent P/E). They need an adjustment factor before they can be used.
VALUATION_RATIOS = ["pe_ratio", "pb_ratio", "earnings_yield"]


def load_results(conn, period_type):
    columns = QUARTERLY_COLUMNS if period_type == "quarterly" else ANNUAL_COLUMNS

    df = pd.read_sql(
        f"SELECT {', '.join(columns)} FROM nse_financial_results "
        f"WHERE period_type = %s ORDER BY symbol, period_end, filing_date",
        conn, params=(period_type,),
    )

    df["filing_date"] = pd.to_datetime(df["filing_date"])
    df["period_end"] = pd.to_datetime(df["period_end"])

    return df


def _prefer_one_filing(df):
    """One row per (symbol, period_end): consolidated first, then the latest filing."""

    df = df.copy()
    df["prefers"] = (df["statement_type"] == "consolidated").astype(int)

    return (
        df.sort_values(["symbol", "period_end", "prefers", "filing_date"])
        .drop_duplicates(["symbol", "period_end"], keep="last")
        .drop(columns="prefers")
        .reset_index(drop=True)
    )


def _known_state_quarterly(quarterly):
    """Rebuild the trailing-twelve-month state after each filing becomes public."""

    quarterly = _prefer_one_filing(quarterly).sort_values(["symbol", "filing_date", "period_end"])
    states = []

    for symbol, group in quarterly.groupby("symbol", sort=False):
        known = {}  # period_end -> row, as known at the current filing date

        for _, row in group.iterrows():
            known[row["period_end"]] = row
            periods = sorted(known)

            if len(periods) < 4:
                continue

            last4 = [known[p] for p in periods[-4:]]
            prev4 = [known[p] for p in periods[-8:-4]] if len(periods) >= 8 else None

            def total(rows, column):
                values = [r[column] for r in rows if pd.notna(r[column])]
                return float(np.sum(values)) if len(values) == len(rows) else np.nan

            revenue_ttm = total(last4, "revenue")
            profit_ttm = total(last4, "net_profit")
            pbt_ttm = total(last4, "profit_before_tax")
            eps_ttm = total(last4, "eps_basic")
            interest_ttm = total(last4, "finance_costs")

            state = {
                "symbol": symbol,
                "filing_date": row["filing_date"],
                "latest_period_end": periods[-1],
                "revenue_ttm": revenue_ttm,
                "net_profit_ttm": profit_ttm,
                "eps_ttm": eps_ttm,
                "net_margin_ttm": profit_ttm / revenue_ttm if revenue_ttm else np.nan,
                "pbt_margin_ttm": pbt_ttm / revenue_ttm if revenue_ttm else np.nan,
                "interest_coverage_ttm": (pbt_ttm + interest_ttm) / interest_ttm if interest_ttm else np.nan,
            }

            if prev4:
                revenue_prev = total(prev4, "revenue")
                profit_prev = total(prev4, "net_profit")
                eps_prev = total(prev4, "eps_basic")

                state["revenue_growth_yoy"] = _growth(revenue_ttm, revenue_prev)
                state["profit_growth_yoy"] = _growth(profit_ttm, profit_prev)
                state["eps_growth_yoy"] = _growth(eps_ttm, eps_prev)
                previous_margin = profit_prev / revenue_prev if revenue_prev else np.nan
                state["margin_change_yoy"] = state["net_margin_ttm"] - previous_margin
            else:
                state.update({"revenue_growth_yoy": np.nan, "profit_growth_yoy": np.nan,
                              "eps_growth_yoy": np.nan, "margin_change_yoy": np.nan})

            states.append(state)

    return pd.DataFrame(states).sort_values("filing_date").reset_index(drop=True)


def _known_state_annual(annual):
    """Latest published equity / share count / leverage, as known after each filing."""

    annual = _prefer_one_filing(annual).sort_values(["symbol", "filing_date"])
    states = []

    for symbol, group in annual.groupby("symbol", sort=False):
        for _, row in group.iterrows():
            shares = np.nan
            if pd.notna(row["paid_up_capital"]) and row.get("face_value"):
                face_value = float(row["face_value"])
                if face_value > 0:
                    # paid-up capital is in crore rupees; shares in crore
                    shares = float(row["paid_up_capital"]) * 1e7 / face_value / 1e7

            states.append({
                "symbol": symbol,
                "filing_date": row["filing_date"],
                "equity_latest": row["equity"],
                "shares_crore": shares,
                "debt_to_equity": row["debt_equity_ratio"],
            })

    return pd.DataFrame(states).sort_values("filing_date").reset_index(drop=True)


def _growth(current, previous):
    if pd.isna(current) or pd.isna(previous) or previous == 0:
        return np.nan
    return (current - previous) / abs(previous)


def attach_fundamentals(panel, quarterly, annual):
    """Join the latest already-published fundamentals onto each month-end row."""

    quarterly_state = _known_state_quarterly(quarterly)
    annual_state = _known_state_annual(annual)

    panel = panel.sort_values("date").reset_index(drop=True)

    for state in (quarterly_state, annual_state):
        panel = pd.merge_asof(
            panel,
            state.sort_values("filing_date"),
            left_on="date",
            right_on="filing_date",
            by="symbol",
            direction="backward",
        )

    # Derived ratios that need today's price
    panel["roe_ttm"] = panel["net_profit_ttm"] / panel["equity_latest"].replace(0, np.nan)
    panel["pe_ratio"] = panel["close"] / panel["eps_ttm"].replace(0, np.nan)
    panel["earnings_yield"] = panel["eps_ttm"] / panel["close"]

    book_value_per_share = panel["equity_latest"] / panel["shares_crore"].replace(0, np.nan)
    panel["pb_ratio"] = panel["close"] / book_value_per_share.replace(0, np.nan)

    panel["days_since_filing"] = (panel["date"] - panel["filing_date_x"]).dt.days

    panel = panel.drop(columns=[c for c in ("filing_date_x", "filing_date_y", "latest_period_end") if c in panel])
    panel = panel.replace([np.inf, -np.inf], np.nan)

    return panel.sort_values(["ticker", "date"]).reset_index(drop=True)
