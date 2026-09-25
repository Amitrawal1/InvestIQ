"""Monthly feature/target panel built from daily prices.

One row per (stock, month-end). Every feature uses only prices up to that month-end;
every target looks forward from it. Monthly rows overlap far less than daily rows,
which makes the walk-forward evaluation more honest.

The market is the equal-weighted average of the stocks trading on each day, used
both as a benchmark for the targets and for relative-strength/beta features.
"""

import numpy as np
import pandas as pd

TRADING_DAYS = {"1m": 21, "3m": 63, "6m": 126, "12m": 252}

# Horizons in months; targets are created for each one
HORIZONS = {"1M": 1, "3M": 3, "6M": 6, "1Y": 12, "3Y": 36}

ID_COLUMNS = ["date", "ticker", "symbol", "company_name", "sector", "close"]


def market_series(prices):
    """Equal-weighted market: daily average return across all stocks trading that day."""

    daily = prices.copy()
    daily["ret_1d"] = daily.groupby("ticker")["close"].pct_change()

    market = (
        daily.groupby("date")["ret_1d"]
        .mean()
        .rename("mkt_ret_1d")
        .to_frame()
    )
    market["mkt_index"] = (1 + market["mkt_ret_1d"].fillna(0)).cumprod()

    return market


def _daily_features(prices, market):
    df = prices.merge(market, left_on="date", right_index=True, how="left")
    df["ret_1d"] = df.groupby("ticker")["close"].pct_change()

    by_ticker = df.groupby("ticker", sort=False)

    # Trend / momentum inputs
    for name, window in TRADING_DAYS.items():
        df[f"sma_{name}"] = by_ticker["close"].transform(lambda s, w=window: s.rolling(w).mean())

    df["close_to_sma_3m"] = df["close"] / df["sma_3m"] - 1
    df["close_to_sma_12m"] = df["close"] / df["sma_12m"] - 1

    # Distance from the rolling 52-week high/low (computed, not the leaky CSV columns)
    df["high_52w"] = by_ticker["close"].transform(lambda s: s.rolling(TRADING_DAYS["12m"]).max())
    df["low_52w"] = by_ticker["close"].transform(lambda s: s.rolling(TRADING_DAYS["12m"]).min())
    df["dist_from_52w_high"] = df["close"] / df["high_52w"] - 1
    df["dist_from_52w_low"] = df["close"] / df["low_52w"] - 1

    # Risk
    df["volatility_3m"] = by_ticker["ret_1d"].transform(lambda s: s.rolling(TRADING_DAYS["3m"]).std())
    df["volatility_12m"] = by_ticker["ret_1d"].transform(lambda s: s.rolling(TRADING_DAYS["12m"]).std())

    # Liquidity
    # Tolerate missing volume days (zero volume was set to NaN during cleaning)
    df["avg_volume_1m"] = by_ticker["volume"].transform(
        lambda s: s.rolling(TRADING_DAYS["1m"], min_periods=10).mean())
    df["avg_volume_12m"] = by_ticker["volume"].transform(
        lambda s: s.rolling(TRADING_DAYS["12m"], min_periods=120).mean())
    df["volume_trend"] = df["avg_volume_1m"] / df["avg_volume_12m"] - 1

    # Market sensitivity over the last year
    cov = by_ticker.apply(
        lambda g: g["ret_1d"].rolling(TRADING_DAYS["12m"]).cov(g["mkt_ret_1d"]),
        include_groups=False,
    ).reset_index(level=0, drop=True)
    market_var = df["mkt_ret_1d"].rolling(TRADING_DAYS["12m"]).var()
    df["beta_12m"] = cov / market_var

    return df


def _month_end_rows(df):
    """Keep the last trading day of each calendar month per stock."""

    period = df["date"].dt.to_period("M")
    last_day = df.groupby(["ticker", period])["date"].transform("max")

    return df[df["date"] == last_day].copy()


def build_monthly_panel(prices, horizons=HORIZONS):
    """Returns (panel, feature_columns). Rows without a full 12-month history are dropped."""

    market = market_series(prices)
    daily = _daily_features(prices, market)
    monthly = _month_end_rows(daily).sort_values(["ticker", "date"]).reset_index(drop=True)

    monthly["month"] = monthly["date"].dt.to_period("M")
    by_ticker = monthly.groupby("ticker", sort=False)

    # Past returns from the month-end close
    for months in (1, 3, 6, 12):
        monthly[f"ret_{months}m"] = by_ticker["close"].transform(lambda s, m=months: s / s.shift(m) - 1)

    # Classic 12-1 momentum: last year but skipping the most recent month
    monthly["momentum_12_1"] = by_ticker["close"].transform(lambda s: s.shift(1) / s.shift(12) - 1)

    # Market context and relative strength
    mkt_monthly = monthly.groupby("month")["mkt_index"].first()
    for months in (1, 3, 6, 12):
        mkt_ret = (mkt_monthly / mkt_monthly.shift(months) - 1).rename(f"mkt_ret_{months}m")
        monthly = monthly.merge(mkt_ret, left_on="month", right_index=True, how="left")
        monthly[f"rel_ret_{months}m"] = monthly[f"ret_{months}m"] - monthly[f"mkt_ret_{months}m"]

    # Cross-sectional ranks: how a stock compares with its peers that month
    for col in ("ret_12m", "momentum_12_1", "volatility_12m", "dist_from_52w_high"):
        monthly[f"rank_{col}"] = monthly.groupby("month")[col].rank(pct=True)

    # ---- Targets: forward return, forward excess return vs market, direction ----
    target_cols = []
    for label, months in horizons.items():
        fwd_stock = by_ticker["close"].transform(lambda s, m=months: s.shift(-m) / s - 1)
        fwd_market = monthly["month"].map(
            (mkt_monthly.shift(-months) / mkt_monthly - 1).to_dict()
        )

        monthly[f"fwd_return_{label}"] = fwd_stock
        monthly[f"fwd_excess_{label}"] = fwd_stock - fwd_market
        monthly[f"target_beat_{label}"] = (fwd_stock - fwd_market > 0).astype("Int64")
        monthly[f"target_up_{label}"] = (fwd_stock > 0).astype("Int64")

        # Rows with no future price yet can't be labelled
        missing = fwd_stock.isna()
        monthly.loc[missing, [f"target_beat_{label}", f"target_up_{label}"]] = pd.NA

        target_cols += [f"fwd_return_{label}", f"fwd_excess_{label}",
                        f"target_beat_{label}", f"target_up_{label}"]

    feature_cols = [
        "ret_1m", "ret_3m", "ret_6m", "ret_12m", "momentum_12_1",
        "rel_ret_1m", "rel_ret_3m", "rel_ret_6m", "rel_ret_12m",
        "close_to_sma_3m", "close_to_sma_12m",
        "dist_from_52w_high", "dist_from_52w_low",
        "volatility_3m", "volatility_12m", "beta_12m",
        "volume_trend",
        "rank_ret_12m", "rank_momentum_12_1", "rank_volatility_12m", "rank_dist_from_52w_high",
        "mkt_ret_1m", "mkt_ret_3m", "mkt_ret_12m",
        "sector",
    ]

    # `sector` is both an identifier and a feature: keep one column only
    columns = list(dict.fromkeys(ID_COLUMNS + ["month"] + feature_cols + target_cols))
    panel = monthly[columns].copy()
    panel = panel.replace([np.inf, -np.inf], np.nan)

    # Need a full year of history before a stock enters the panel
    panel = panel[panel["ret_12m"].notna()].reset_index(drop=True)
    panel["sector"] = panel["sector"].astype("category")

    return panel, feature_cols
