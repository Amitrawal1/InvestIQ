"""Market-regime switch for the InvestIQ combiner: lower the trend weight after deep market falls.

Problem (docs/model-report.md, time machine "Post-COVID rally"): trend-led rankings reverse after a
deep market fall ("momentum crash"). Ranked on 2020-04-16, investiq-v1 had IC -0.19: the stocks that
had fallen most (high beta, weak trend) led the rebound. Hypothesis: when the market is in a
post-crash / low-breadth state, a lower market (trend) weight, leaning on the financial model and
possibly a low-volatility or short-term-reversal tilt, avoids this without hurting normal years.

Everything here is PRE-DECLARED: the rules, the risk-regime alternatives and the primary hypothesis
were written before any result was computed (rankings/regime_eval.py tests them walk-forward, exactly
like combiner_eval.choose_w). Nothing is fitted in this module.

Market state on signal date D (only data up to the last trading day on or before D):
    mkt_dd_52w      NIFTY SMALLCAP 250 close / its 252-day max close - 1   (drawdown from 52-week high)
    mkt_ret_3m      benchmark 63-trading-day return
    mkt_ret_12m     benchmark 252-trading-day return
    mkt_ma200_gap   benchmark close / its 200-day average - 1
    mkt_vol_3m      benchmark annualised daily-return volatility, 63 days
    breadth_ma200   share of stocks above their own 200-day average
The last five are growth_model/market_features.py's market-mood columns (same formulas);
`market_state_daily` recomputes all six from a benchmark close series and a wide close matrix, so
build_v3 (which already loads prices) can call it.

Rules (RULES). A rule is either stateless (risk iff `enter`) or has hysteresis: it enters the risk
regime when `enter` holds and stays there until `exit` holds (the "recovery" condition), evaluated
in date order on the 1st/16th signal grid. Thresholds are round numbers chosen from what a
"deep fall" means for Indian small caps (-20% / -25% from the high, 3-month crash of 15-20%,
fewer than 15-20% of stocks above their 200-day average), not tuned.

Risk-regime alternatives (ALTERNATIVES): weights on per-date percentiles (0-1)
    market     trend6 percentile (as investiq-v1)
    financial  fin-v1 percentile (as investiq-v1)
    lowvol     1 - percentile of vol_3m (calmer stocks first)
    reversal   1 - percentile of mom_1m (last month's losers first: short-term reversal)
Normal regime keeps investiq-v1: market .7, financial .3.

PRIMARY (the single hypothesis written down before testing, from model-report section 4.1):
enter when Smallcap 250 is >= 25% below its 52-week high, stay until breadth recovers above 50%,
market weight 0.3 in the risk regime.

`regime_state(frame, rule)` is pure: a dict / Series (one date; stateless rules only) or a DataFrame
of dates (any rule, sorted by date) -> 'normal' / 'risk'.
"""

from dataclasses import dataclass
from typing import Callable, Optional

import numpy as np
import pandas as pd

NORMAL_WEIGHTS = {"market": 0.7, "financial": 0.3}
STATE_COLUMNS = ["mkt_dd_52w", "mkt_ret_3m", "mkt_ret_12m", "mkt_ma200_gap", "mkt_vol_3m", "breadth_ma200"]


@dataclass(frozen=True)
class Rule:
    name: str
    text: str
    enter: Callable
    exit: Optional[Callable] = None      # None: stateless (risk iff enter)


def _g(row, col):
    v = row.get(col) if hasattr(row, "get") else row[col]
    return np.nan if v is None else float(v)


def _lt(col, x):
    return lambda r: _g(r, col) < x


def _ge(col, x):
    return lambda r: _g(r, col) >= x


def _stress(r):
    return _g(r, "mkt_ret_3m") <= -0.15 and _g(r, "mkt_vol_3m") >= 0.30


# ---- pre-declared rule grid (12 variants) ----
RULES = [
    Rule("dd25", "Smallcap 250 >= 25% below its 52-week high", lambda r: _g(r, "mkt_dd_52w") <= -0.25),
    Rule("dd20", "Smallcap 250 >= 20% below its 52-week high", lambda r: _g(r, "mkt_dd_52w") <= -0.20),
    Rule("breadth15", "< 15% of stocks above their 200-day average", _lt("breadth_ma200", 0.15)),
    Rule("breadth20", "< 20% of stocks above their 200-day average", _lt("breadth_ma200", 0.20)),
    Rule("ret3m_m20", "Smallcap 250 down >= 20% in 3 months", lambda r: _g(r, "mkt_ret_3m") <= -0.20),
    Rule("stress", "Smallcap 250 down >= 15% in 3 months with >= 30% annualised volatility", _stress),
    Rule("bear12", "Smallcap 250 down >= 20% over 12 months (bear state)", lambda r: _g(r, "mkt_ret_12m") <= -0.20),
    Rule("dd25_or_b15", "dd25 or breadth15",
         lambda r: _g(r, "mkt_dd_52w") <= -0.25 or _g(r, "breadth_ma200") < 0.15),
    Rule("dd25_and_vol30", "dd25 and >= 30% annualised volatility (panic, not a slow grind)",
         lambda r: _g(r, "mkt_dd_52w") <= -0.25 and _g(r, "mkt_vol_3m") >= 0.30),
    Rule("dd25_exit_b50", "enter at dd25; stay until breadth >= 50%",
         lambda r: _g(r, "mkt_dd_52w") <= -0.25, _ge("breadth_ma200", 0.50)),
    Rule("b15_exit_b50", "enter at breadth < 15%; stay until breadth >= 50%",
         _lt("breadth_ma200", 0.15), _ge("breadth_ma200", 0.50)),
    Rule("stress_exit_ma200", "enter at stress; stay until Smallcap 250 is back above its 200-day average",
         _stress, _ge("mkt_ma200_gap", 0.0)),
]
RULE_BY_NAME = {r.name: r for r in RULES}

# ---- pre-declared risk-regime alternatives ----
ALTERNATIVES = {
    "w0.5": {"market": 0.5, "financial": 0.5},
    "w0.3": {"market": 0.3, "financial": 0.7},
    "w0.0": {"market": 0.0, "financial": 1.0},
    "w0.3_lowvol": {"market": 0.3, "financial": 0.4, "lowvol": 0.3},
    "w0.3_reversal": {"market": 0.3, "financial": 0.4, "reversal": 0.3},
}
PRIMARY = ("dd25_exit_b50", "w0.3")

# Result of rankings/regime_eval.py (REGIME.md): None = no rule passed, keep investiq-v1 unchanged.
RECOMMENDED = None


# ---------------------------------------------------------
# Market state
# ---------------------------------------------------------

def market_state_daily(bench_close, close_wide, stale_days=5):
    """Daily market state (STATE_COLUMNS) on the benchmark calendar.
    bench_close: Series indexed by date; close_wide: DataFrame dates x companies (raw closes)."""
    bench = bench_close.sort_index().astype(float)
    cal = bench.index
    union = close_wide.index.union(cal)
    close = close_wide.reindex(union).ffill(limit=stale_days).reindex(cal)
    ma200 = close.rolling(200, min_periods=160).mean()
    out = pd.DataFrame({
        "mkt_dd_52w": bench / bench.rolling(252, min_periods=200).max() - 1,
        "mkt_ret_3m": bench / bench.shift(63) - 1,
        "mkt_ret_12m": bench / bench.shift(252) - 1,
        "mkt_ma200_gap": bench / bench.rolling(200).mean() - 1,
        "mkt_vol_3m": bench.pct_change().rolling(63).std() * np.sqrt(252),
        "breadth_ma200": (close > ma200).where(ma200.notna()).mean(axis=1),
    })
    return out


def state_on(daily_state, dates):
    """Market state as of each date (last trading day on or before it)."""
    d = pd.DatetimeIndex(pd.to_datetime(dates))
    pos = daily_state.index.searchsorted(d, side="right") - 1
    out = daily_state.iloc[np.clip(pos, 0, None)].copy()
    out.index = d
    out[pos < 0] = np.nan
    return out


# ---------------------------------------------------------
# Regime
# ---------------------------------------------------------

def _bool(f, row):
    try:
        v = f(row)
    except (KeyError, TypeError):
        return False
    return bool(v) if v is not None and not (isinstance(v, float) and np.isnan(v)) else False


def regime_state(frame, rule=None):
    """'normal' / 'risk' for one date (dict / Series; stateless rules only) or for a date-sorted
    DataFrame of market states (one row per signal date; hysteresis walks forward in that order).
    rule: a Rule, its name, or None -> RECOMMENDED (normal everywhere when nothing is recommended)."""
    if rule is None:
        if RECOMMENDED is None:
            return "normal" if not isinstance(frame, pd.DataFrame) else pd.Series("normal", index=frame.index)
        rule = RECOMMENDED[0]
    if isinstance(rule, str):
        rule = RULE_BY_NAME[rule]
    if not isinstance(frame, pd.DataFrame):
        if rule.exit is not None:
            raise ValueError(f"rule {rule.name} has a recovery condition: pass the date-sorted history")
        return "risk" if _bool(rule.enter, frame) else "normal"
    states, risk = [], False
    for _, row in frame.iterrows():
        if rule.exit is None:
            risk = _bool(rule.enter, row)
        elif risk:
            risk = not _bool(rule.exit, row)
        else:
            risk = _bool(rule.enter, row)
        states.append("risk" if risk else "normal")
    return pd.Series(states, index=frame.index)


def weights_for(state, alternative=None):
    """Component weights for a regime state ('normal' -> investiq-v1; 'risk' -> the alternative)."""
    if state != "risk":
        return dict(NORMAL_WEIGHTS)
    alt = alternative or (RECOMMENDED[1] if RECOMMENDED else None)
    return dict(ALTERNATIVES[alt]) if alt else dict(NORMAL_WEIGHTS)


def blend(frame, weights):
    """Weighted sum of per-date percentile columns (missing -> 0.5), weights over present columns."""
    return sum(frame[c].fillna(0.5) * w for c, w in weights.items() if w)
