"""Feature engineering and target construction.

Every feature at date t uses only information available at or before t.
Fundamentals are joined point-in-time on their estimated publication date.
"""

import numpy as np
import pandas as pd

from .config import (
    MA_WINDOWS,
    MIN_LOOKBACK,
    QUARTERLY_REPORT_LAG_DAYS,
    RETURN_WINDOWS,
    RSI_WINDOW,
    TARGET_HORIZON,
    VOLATILITY_WINDOWS,
    VOLUME_WINDOWS,
    YEARLY_REPORT_LAG_DAYS,
)

TARGET_COL = "target"
FORWARD_RETURN_COL = f"fwd_return_{TARGET_HORIZON}d"

# Identifier / label columns that must never be fed to the model.
NON_FEATURE_COLS = {
    "company_id",
    "symbol",
    "price_date",
    "open_price",
    "high_price",
    "low_price",
    "close_price",
    "volume",
    TARGET_COL,
    FORWARD_RETURN_COL,
}


# =========================================================
# PRICE FEATURES
# =========================================================

def _rsi(close, window):
    delta = close.diff()
    gain = delta.clip(lower=0).rolling(window).mean()
    loss = (-delta.clip(upper=0)).rolling(window).mean()

    return 100 - 100 / (1 + gain / loss.replace(0, np.nan))


def _price_features_one_company(g):
    g = g.copy()
    close = g["close_price"]
    volume = g["volume"]
    daily_ret = close.pct_change()

    for w in RETURN_WINDOWS:
        g[f"ret_{w}d"] = close.pct_change(w)

    # Price relative to its moving average is scale-free, unlike the raw SMA.
    for w in MA_WINDOWS:
        g[f"close_to_sma_{w}"] = close / close.rolling(w).mean() - 1

    g["sma_5_to_sma_20"] = close.rolling(5).mean() / close.rolling(20).mean() - 1

    for w in VOLATILITY_WINDOWS:
        g[f"volatility_{w}d"] = daily_ret.rolling(w).std()

    g["volume_change_1d"] = volume.pct_change()

    for w in VOLUME_WINDOWS:
        g[f"volume_to_avg_{w}d"] = volume / volume.rolling(w).mean() - 1

    g["high_low_range"] = (g["high_price"] - g["low_price"]) / close
    g["close_to_open"] = close / g["open_price"] - 1
    g[f"rsi_{RSI_WINDOW}"] = _rsi(close, RSI_WINDOW)

    return g


def add_price_features(prices):
    return (
        prices.groupby("company_id", group_keys=False)
        .apply(_price_features_one_company)
        .reset_index(drop=True)
    )


# =========================================================
# FUNDAMENTAL FEATURES
# =========================================================

def _growth(series, periods=1):
    """Period-over-period growth that stays sane when the base is negative."""

    prev = series.shift(periods)

    return (series - prev) / prev.abs().replace(0, np.nan)


def _safe_div(a, b):
    return a / b.replace(0, np.nan)


def _quarterly_features(q):
    out = q[["company_id", "period_end_date"]].copy()
    grp = q.groupby("company_id")

    out["q_revenue_qoq"] = grp["revenue"].transform(_growth)
    out["q_net_profit_qoq"] = grp["net_profit"].transform(_growth)
    out["q_operating_profit_qoq"] = grp["operating_profit"].transform(_growth)
    out["q_revenue_yoy"] = grp["revenue"].transform(lambda s: _growth(s, 4))
    out["q_net_profit_yoy"] = grp["net_profit"].transform(lambda s: _growth(s, 4))
    out["q_operating_margin"] = _safe_div(q["operating_profit"], q["revenue"])
    out["q_net_margin"] = _safe_div(q["net_profit"], q["revenue"])
    out["q_eps"] = q["eps"]
    out["q_eps_qoq"] = grp["eps"].transform(_growth)

    out["available_date"] = q["period_end_date"] + pd.Timedelta(days=QUARTERLY_REPORT_LAG_DAYS)

    return out


def _yearly_features(y):
    out = y[["company_id", "period_end_date"]].copy()
    grp = y.groupby("company_id")

    out["y_revenue_growth"] = grp["revenue"].transform(_growth)
    out["y_net_profit_growth"] = grp["net_profit"].transform(_growth)
    out["y_total_assets_growth"] = grp["total_assets"].transform(_growth)
    out["y_net_margin"] = _safe_div(y["net_profit"], y["revenue"])
    out["y_roe"] = _safe_div(y["net_profit"], y["total_equity"])
    out["y_roa"] = _safe_div(y["net_profit"], y["total_assets"])
    out["y_debt_to_equity"] = _safe_div(y["total_debt"], y["total_equity"])
    out["y_equity_to_assets"] = _safe_div(y["total_equity"], y["total_assets"])
    out["y_ocf_to_net_profit"] = _safe_div(y["operating_cash_flow"], y["net_profit"])
    out["y_eps"] = y["eps"]
    out["y_eps_growth"] = grp["eps"].transform(_growth)

    out["available_date"] = y["period_end_date"] + pd.Timedelta(days=YEARLY_REPORT_LAG_DAYS)

    return out


def build_fundamental_features(financials):
    """Return (quarterly_features, yearly_features), each keyed by available_date."""

    q = financials[financials["period_type"] == "quarterly"].sort_values(
        ["company_id", "period_end_date"]
    )
    y = financials[financials["period_type"] == "yearly"].sort_values(
        ["company_id", "period_end_date"]
    )

    return _quarterly_features(q.reset_index(drop=True)), _yearly_features(y.reset_index(drop=True))


def merge_point_in_time(price_df, fundamentals):
    """As-of join: each trading day gets the latest statement already published."""

    df = price_df.sort_values("price_date")

    for fund in fundamentals:
        fund = (
            fund.drop(columns="period_end_date")
            .sort_values("available_date")
        )

        df = pd.merge_asof(
            df,
            fund,
            left_on="price_date",
            right_on="available_date",
            by="company_id",
            direction="backward",
        ).drop(columns="available_date")

    # Valuation ratios need per-share data; they appear once EPS is populated.
    df["pe_ratio"] = _safe_div(df["close_price"], df["y_eps"])

    return df.sort_values(["company_id", "price_date"]).reset_index(drop=True)


# =========================================================
# TARGET
# =========================================================

def add_target(df, horizon=TARGET_HORIZON):
    """target = 1 if close price `horizon` trading days ahead is above today's."""

    df = df.copy()
    future_close = df.groupby("company_id")["close_price"].shift(-horizon)

    df[FORWARD_RETURN_COL] = future_close / df["close_price"] - 1
    df[TARGET_COL] = (df[FORWARD_RETURN_COL] > 0).astype("Int64")
    df.loc[df[FORWARD_RETURN_COL].isna(), TARGET_COL] = pd.NA

    return df


# =========================================================
# FULL DATASET
# =========================================================

def get_feature_columns(df):
    return [c for c in df.columns if c not in NON_FEATURE_COLS]


def build_dataset(prices, financials):
    """Assemble the modelling table and report which features were usable.

    Returns (dataset, feature_cols, dropped_empty_features).
    """

    df = add_price_features(prices)
    df = merge_point_in_time(df, build_fundamental_features(financials))
    df = add_target(df)

    # Warm-up rows: not enough history for the core lookback windows.
    row_number = df.groupby("company_id").cumcount()
    df = df[row_number >= MIN_LOOKBACK]

    # Rows at the end have no future price to label them.
    df = df[df[TARGET_COL].notna()].copy()
    df[TARGET_COL] = df[TARGET_COL].astype(int)

    df = df.replace([np.inf, -np.inf], np.nan)

    feature_cols = get_feature_columns(df)

    # Features with no data at all (e.g. EPS / debt not yet ingested) add nothing.
    empty = [c for c in feature_cols if df[c].isna().all()]
    feature_cols = [c for c in feature_cols if c not in empty]

    return df.reset_index(drop=True), feature_cols, empty
