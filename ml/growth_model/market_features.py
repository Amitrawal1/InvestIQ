"""Market (price/volume) features for the growth model, one row per (company, signal_date).

Every feature uses only candles up to the last trading day on or before the signal date D (the
same D the labels in labels.py start from), so rows can be joined 1:1 onto the labels.

Stock features (computed on the benchmark trading calendar; a stock's last close is carried at
most ENTRY_STALE days, so a long-suspended stock has no features):
    momentum     mom_1m/3m/6m/12m (simple return), mom_12_1 (12-month return skipping the last
                 month, the classic momentum signal), rel_* = the same minus NIFTY SMALLCAP 250
    trend        dist_52w_high / dist_52w_low, ma50_gap / ma200_gap (close vs moving average),
                 ma50_over_200
    risk         vol_3m / vol_1y (annualised daily-return volatility), beta_1y vs the benchmark,
                 max_ret_1m (largest one-day gain in a month: "lottery" stocks), down_days_3m
    volume       vol_surge (20-day vs 126-day mean traded value), tv_growth_3m (last 63 days vs the
                 63 before), updown_volume_3m (volume on up days / volume on down days),
                 log_adv (log median traded value, 60 days), trade_ratio_6m (share of days traded)
    size proxy   log_price
A feature whose look-back window contains a price-series break (see labels.py) is NaN.

Market-mood features (same value for every stock on a date):
    mkt_ret_3m, mkt_ret_12m, mkt_ma200_gap, mkt_vol_3m (the benchmark itself) and
    breadth_ma200 (share of stocks trading above their 200-day average).

`rank_features` turns stock features into cross-sectional percentiles per date, so a model sees
"top 10% momentum today" rather than a raw return whose scale changes between bull and bear years.
"""

import numpy as np
import pandas as pd

from .labels import BREAK_DOWN, BREAK_UP, ENTRY_STALE, signal_dates
from .prices import BENCHMARK

STOCK_FEATURES = [
    "mom_1m", "mom_3m", "mom_6m", "mom_12m", "mom_12_1",
    "rel_3m", "rel_6m", "rel_12m",
    "dist_52w_high", "dist_52w_low", "ma50_gap", "ma200_gap", "ma50_over_200",
    "vol_3m", "vol_1y", "beta_1y", "max_ret_1m", "down_days_3m",
    "vol_surge", "tv_growth_3m", "updown_volume_3m", "log_adv", "trade_ratio_6m",
    "log_price",
]
MARKET_FEATURES = ["mkt_ret_3m", "mkt_ret_12m", "mkt_ma200_gap", "mkt_vol_3m", "breadth_ma200"]
FEATURES = STOCK_FEATURES + MARKET_FEATURES

# look-back (trading days) each feature depends on, for the series-break check
WINDOWS = {
    "mom_1m": 21, "mom_3m": 63, "mom_6m": 126, "mom_12m": 252, "mom_12_1": 252,
    "rel_3m": 63, "rel_6m": 126, "rel_12m": 252,
    "dist_52w_high": 252, "dist_52w_low": 252, "ma50_gap": 50, "ma200_gap": 200, "ma50_over_200": 200,
    "vol_3m": 63, "vol_1y": 252, "beta_1y": 252, "max_ret_1m": 21, "down_days_3m": 63,
    "vol_surge": 126, "tv_growth_3m": 126, "updown_volume_3m": 63, "log_adv": 60,
    "trade_ratio_6m": 126, "log_price": 1,
}


def _matrices(stocks, calendar):
    """close / volume / traded-value / break-count matrices on the benchmark calendar."""
    close = stocks.pivot_table(index="price_date", columns="company_id", values="close", aggfunc="last")
    volume = stocks.pivot_table(index="price_date", columns="company_id", values="volume", aggfunc="last")
    step = close.apply(lambda col: col.dropna().pct_change()).reindex(close.index)
    breaks = ((step > BREAK_UP) | (step < BREAK_DOWN)).astype(int)

    union = close.index.union(calendar)
    traded = close.reindex(union).notna().reindex(calendar, fill_value=False)
    # volume on special sessions is dropped (small); closes carry forward at most ENTRY_STALE days
    close = close.reindex(union).ffill(limit=ENTRY_STALE).reindex(calendar)
    volume = volume.reindex(calendar).where(traded, 0.0)
    breaks = breaks.reindex(union, fill_value=0).cumsum().reindex(calendar, method="ffill").fillna(0)
    return close, volume, traded, breaks


def build_market_features(stocks, index, start="2017-01-01"):
    bench = index[index["index_key"] == BENCHMARK].set_index("price_date")["close"].sort_index()
    calendar = bench.index
    close, volume, traded, breaks = _matrices(stocks, calendar)

    ret = close.pct_change(fill_method=None)
    ret = ret.where(traded)                     # no return on days the stock didn't trade
    bret = bench.pct_change()
    tv = (close * volume / 1e7).where(traded, 0.0)     # INR crore

    f = {}
    for name, n in [("mom_1m", 21), ("mom_3m", 63), ("mom_6m", 126), ("mom_12m", 252)]:
        f[name] = close / close.shift(n) - 1
    f["mom_12_1"] = close.shift(21) / close.shift(252) - 1
    for name, n in [("rel_3m", 63), ("rel_6m", 126), ("rel_12m", 252)]:
        f[name] = (close / close.shift(n) - 1).sub(bench / bench.shift(n) - 1, axis=0)

    hi = close.rolling(252, min_periods=200).max()
    lo = close.rolling(252, min_periods=200).min()
    f["dist_52w_high"] = close / hi - 1
    f["dist_52w_low"] = close / lo - 1
    ma50 = close.rolling(50, min_periods=40).mean()
    ma200 = close.rolling(200, min_periods=160).mean()
    f["ma50_gap"] = close / ma50 - 1
    f["ma200_gap"] = close / ma200 - 1
    f["ma50_over_200"] = ma50 / ma200 - 1

    f["vol_3m"] = ret.rolling(63, min_periods=40).std() * np.sqrt(252)
    f["vol_1y"] = ret.rolling(252, min_periods=160).std() * np.sqrt(252)
    # beta = cov(r, rb) / var(rb) via rolling means (days the stock didn't trade are skipped)
    rb = pd.DataFrame(np.repeat(bret.values[:, None], ret.shape[1], axis=1), index=ret.index, columns=ret.columns)
    rb = rb.where(ret.notna())
    m_xy = (ret * rb).rolling(252, min_periods=160).mean()
    m_x = ret.rolling(252, min_periods=160).mean()
    m_y = rb.rolling(252, min_periods=160).mean()
    var_y = (rb * rb).rolling(252, min_periods=160).mean() - m_y ** 2
    f["beta_1y"] = (m_xy - m_x * m_y) / var_y.where(var_y > 1e-8)
    f["max_ret_1m"] = ret.rolling(21, min_periods=10).max()
    f["down_days_3m"] = (ret < 0).astype(float).where(ret.notna()).rolling(63, min_periods=40).mean()

    tv_mean_20 = tv.rolling(20, min_periods=10).mean()
    tv_mean_126 = tv.rolling(126, min_periods=60).mean()
    f["vol_surge"] = tv_mean_20 / tv_mean_126.where(tv_mean_126 > 0)
    tv_63 = tv.rolling(63, min_periods=40).sum()
    f["tv_growth_3m"] = np.log1p(tv_63) - np.log1p(tv_63.shift(63))
    up_v = volume.where(ret > 0, 0.0).rolling(63, min_periods=40).sum()
    dn_v = volume.where(ret < 0, 0.0).rolling(63, min_periods=40).sum()
    f["updown_volume_3m"] = np.log((up_v + 1) / (dn_v + 1))
    adv = tv.where(traded).rolling(60, min_periods=20).median()
    f["log_adv"] = np.log10(adv.where(adv > 0))
    f["trade_ratio_6m"] = traded.astype(float).rolling(126, min_periods=60).mean()
    f["log_price"] = np.log10(close.where(close > 0))

    # market mood
    b_ma200 = bench.rolling(200).mean()
    mood = pd.DataFrame({
        "mkt_ret_3m": bench / bench.shift(63) - 1,
        "mkt_ret_12m": bench / bench.shift(252) - 1,
        "mkt_ma200_gap": bench / b_ma200 - 1,
        "mkt_vol_3m": bret.rolling(63).std() * np.sqrt(252),
        "breadth_ma200": (close > ma200).where(ma200.notna()).mean(axis=1),
    })

    rows = []
    for d in signal_dates(start, calendar[-1]):
        pos = calendar.searchsorted(d, side="right") - 1
        if pos < 0:
            continue
        valid = close.iloc[pos].notna()
        ids = close.columns[valid]
        frame = {"company_id": ids.values, "signal_date": np.full(len(ids), d)}
        b_now = breaks.iloc[pos][valid]
        for name in STOCK_FEATURES:
            vals = f[name].iloc[pos][valid]
            w = WINDOWS[name]
            b_then = breaks.iloc[max(pos - w, 0)][valid]
            frame[name] = vals.where(b_now == b_then).values
        for name in MARKET_FEATURES:
            frame[name] = mood[name].iloc[pos]
        rows.append(pd.DataFrame(frame))

    out = pd.concat(rows, ignore_index=True)
    out["company_id"] = out["company_id"].astype(int)
    out = out.replace([np.inf, -np.inf], np.nan)
    return out


def rank_features(df, columns=STOCK_FEATURES):
    """Cross-sectional percentile (0-1) of each stock feature within its signal date."""
    ranked = df.copy()
    ranked[columns] = df.groupby("signal_date")[columns].rank(pct=True)
    return ranked
