"""Load, clean and validate stock_prices and financial_statements from MySQL."""

import os

import numpy as np
import pandas as pd
from dotenv import load_dotenv
from sqlalchemy import create_engine, text
from sqlalchemy.engine import URL

from .config import ENV_FILE

PRICE_COLUMNS = ["open_price", "high_price", "low_price", "close_price", "volume"]

FINANCIAL_COLUMNS = [
    "revenue",
    "operating_profit",
    "net_profit",
    "eps",
    "total_assets",
    "total_debt",
    "total_equity",
    "operating_cash_flow",
    "investing_cash_flow",
    "financing_cash_flow",
    "other_income",
    "total_revenue",
    "total_expenses",
    "profit_before_tax",
    "tax",
    "profit_after_tax",
]


# =========================================================
# DATABASE
# =========================================================

def get_engine():
    """SQLAlchemy engine built from backend/.env (same creds as the backend)."""

    load_dotenv(ENV_FILE, override=True)

    url = URL.create(
        "mysql+mysqlconnector",
        username=os.getenv("DB_USER"),
        password=os.getenv("DB_PASSWORD"),
        host=os.getenv("DB_HOST"),
        database=os.getenv("DB_NAME"),
    )

    return create_engine(url)


def _company_filter(company_ids, column):
    if not company_ids:
        return "", {}

    placeholders = ", ".join(f":cid{i}" for i in range(len(company_ids)))
    params = {f"cid{i}": int(cid) for i, cid in enumerate(company_ids)}

    return f"WHERE {column} IN ({placeholders})", params


def table_overview(engine):
    """Row counts and coverage of the tables this model depends on."""

    query = """
        SELECT 'stock_prices' AS table_name,
               COUNT(*) AS n_rows,
               COUNT(DISTINCT company_id) AS n_companies,
               MIN(price_date) AS min_date,
               MAX(price_date) AS max_date
        FROM stock_prices
        UNION ALL
        SELECT 'financial_statements',
               COUNT(*),
               COUNT(DISTINCT company_id),
               MIN(period_end_date),
               MAX(period_end_date)
        FROM financial_statements
    """

    with engine.connect() as conn:
        return pd.read_sql(text(query), conn)


def load_prices(engine, company_ids=None):
    where, params = _company_filter(company_ids, "sp.company_id")

    query = f"""
        SELECT sp.company_id,
               c.symbol,
               sp.price_date,
               sp.open_price,
               sp.high_price,
               sp.low_price,
               sp.close_price,
               sp.volume
        FROM stock_prices sp
        JOIN companies c ON c.id = sp.company_id
        {where}
        ORDER BY sp.company_id, sp.price_date
    """

    with engine.connect() as conn:
        return pd.read_sql(text(query), conn, params=params)


def load_financials(engine, company_ids=None):
    where, params = _company_filter(company_ids, "company_id")

    query = f"""
        SELECT company_id,
               statement_type,
               period_type,
               period_end_date,
               {", ".join(FINANCIAL_COLUMNS)}
        FROM financial_statements
        {where}
        ORDER BY company_id, period_type, period_end_date
    """

    with engine.connect() as conn:
        return pd.read_sql(text(query), conn, params=params)


# =========================================================
# CLEANING / VALIDATION
# =========================================================

def clean_prices(prices):
    """Coerce types and drop rows that would corrupt price features.

    Returns (clean_df, report) where report counts what was removed.
    """

    df = prices.copy()
    report = {"rows_in": len(df)}

    df["price_date"] = pd.to_datetime(df["price_date"]).dt.normalize()

    for col in PRICE_COLUMNS:
        df[col] = pd.to_numeric(df[col], errors="coerce").astype(float)

    before = len(df)
    df = df.drop_duplicates(["company_id", "price_date"], keep="last")
    report["duplicates_dropped"] = before - len(df)

    before = len(df)
    df = df.dropna(subset=["close_price"])
    report["missing_close_dropped"] = before - len(df)

    before = len(df)
    df = df[df["close_price"] > 0]
    report["non_positive_close_dropped"] = before - len(df)

    # OHLC must be internally consistent; otherwise the bar is corrupt.
    ohlc_ok = (
        (df["low_price"] <= df[["open_price", "close_price"]].min(axis=1))
        & (df["high_price"] >= df[["open_price", "close_price"]].max(axis=1))
    )
    ohlc_known = df[["open_price", "high_price", "low_price"]].notna().all(axis=1)

    before = len(df)
    df = df[ohlc_ok | ~ohlc_known]
    report["inconsistent_ohlc_dropped"] = before - len(df)

    # Zero volume on NSE almost always means a missing value, not a real print.
    df.loc[df["volume"] <= 0, "volume"] = np.nan
    report["zero_volume_set_nan"] = int(df["volume"].isna().sum())

    df = df.sort_values(["company_id", "price_date"]).reset_index(drop=True)
    report["rows_out"] = len(df)

    return df, report


def price_gap_report(prices, max_gap_days=5):
    """Flag calendar gaps longer than a normal weekend/holiday break."""

    gaps = (
        prices.groupby("company_id")["price_date"]
        .diff()
        .dt.days
    )

    flagged = prices.loc[gaps > max_gap_days, ["company_id", "symbol", "price_date"]]

    return flagged.assign(gap_days=gaps[gaps > max_gap_days])


def clean_financials(financials, statement_type="consolidated"):
    df = financials.copy()

    df = df[df["statement_type"] == statement_type]
    df["period_end_date"] = pd.to_datetime(df["period_end_date"])

    for col in FINANCIAL_COLUMNS:
        df[col] = pd.to_numeric(df[col], errors="coerce").astype(float)

    df = (
        df.drop_duplicates(["company_id", "period_type", "period_end_date"], keep="last")
        .sort_values(["company_id", "period_type", "period_end_date"])
        .reset_index(drop=True)
    )

    return df


def financial_coverage(financials):
    """Share of non-null values per column and period type."""

    return (
        financials.groupby("period_type")[FINANCIAL_COLUMNS]
        .apply(lambda g: g.notna().mean())
        .T.round(2)
    )
