"""The "Early Movers" list for the InvestIQ ranking: stocks breaking out of a base *before* the stretch.

docs/model-report.md section 5.1 item 3. The Top list (rankings/portfolio.py) buys whatever has the best
investiq-v1 score, and the score is 70% price trend, so the top of the list is full of stocks that have
already run (GANDHAR #1 after +110% in 6 months). A descriptive, in-sample check (all liquid stocks
2017-2026, 12 months ahead) found that a "base breakout" (within 5% of the 52-week high but up < 30% in
6 months, above the 200-day average) had a better typical outcome (median excess -0.6% vs -7.9% for all
stocks) and half the crash rate of stretched stocks (9% vs 20% falling 30%+), and that adding growth and
quality fundamentals cut the crash rate to ~4% on ~5 names a date since 2020. That was a look at the
data, not a test: this module fixes the definitions in code, and rankings/early_movers_eval.py runs them
as rebalanced lists with the Top list's simulator, costs and universe.

Like portfolio.py it is pure (no DB, no I/O), so the backtest, build_v3.py and the site could all call
the same function.

Input frame (`scored_df`), one row per company on the date, columns:
    company_id            int
    growth_score          investiq-v1 score 0-100, NaN = unranked (never selected)
    adv_cr                median daily traded value, INR crore            [min_adv_cr]
    days_listed           trading days with a price up to the date        [min_days_listed]
    volatility            annualised daily volatility (vol_3m)            [vol_exclude_pct]
    dist_52w_high         close / 52-week high close - 1 (<= 0)           [near_high]
    return_6m             6-month price return (mom_6m)                   [max_ret_6m]
    ma200_gap             close / 200-day average - 1                     [above_ma200, max_ma200_gap]
  fundamentals (point-in-time, filing_date <= D; financial_model.data.build_panel; NaN = not reported,
  always NaN for banks / NBFCs / insurers, so those can only qualify under rules without fundamentals):
    revenue_yoy           quarterly revenue vs the same quarter a year ago - 1     [min_revenue_yoy]
    net_profit_yoy        same for net profit                                      [min_profit_yoy]
    net_profit_ttm        trailing-12-month net profit, crore                      [require_profitable]
    revenue_yoy_accel     revenue_yoy minus the previous quarter's revenue_yoy     [growth_momentum]
    op_margin_change_yoy  operating margin vs a year ago (difference)              [growth_momentum]
    cash_conversion       operating cash flow / net profit (TTM, profit > 0)       [min_cash_conversion]
Only the columns a rule needs must be present.

Selection on a date (`select_early_movers`)
    1. hard filters (holdings too): growth_score present, adv_cr >= min_adv_cr, days_listed >=
       min_days_listed. `sel_rank` = rank by growth_score among the names left (the Top list's rank).
    2. `qualifies` = the entry pattern (base breakout [+ score floor] [+ fundamentals]).
    3. keep: a previous holding stays while it passes the hard filters AND (it still qualifies OR
       sel_rank <= keep_rank). The breakout condition is fleeting by design (a winner soon has 6m > 30%
       and stops qualifying), so selling on "no longer qualifies" would sell the winners exactly when
       they work; instead a holding rides as long as the main model still ranks it in its top
       keep_rank (the Top list's buffer), and is sold once it neither qualifies nor ranks there.
       If more than n holdings survive, the n best by score are kept.
    4. fill vacancies with qualifiers by growth_score (best first), skipping new buys among the
       vol_exclude_pct most volatile names of the date (the Top list's entry rule).
    5. if fewer than n names qualify the list is simply shorter (no padding); an empty list = cash.
Equal weight, rebalanced on the 1st/16th like the Top list.

Pre-declared definitions (`DEFINITIONS`), fixed before any backtest result was seen. The only data
looked at before fixing them was the number of qualifying names per date (no returns), used to set
E4's looser thresholds so that it usually has >= 15 qualifiers:
    E1  base breakout only: within 5% of the 52-week high, 6m return < 30%, above the 200-day
        average, < 60% above it (not "stretched", build_v3)
    E2  E1 + investiq-v1 score >= 60
    E3  E1 + strict fundamentals: revenue and profit YoY > 20%, profitable (TTM), revenue growth
        accelerating AND operating margin rising, cash conversion > 0.7 (required: cash-flow data only
        exists from mid-2021, so E3 holds cash before then)
    E4  looser E3: within 10% of the high, 6m < 30%, above the 200-day average; revenue and profit
        YoY > 10%, profitable, revenue accelerating OR margin rising, cash conversion > 0.5 when
        reported (missing allowed, so 2019-21 is testable)
All four: top N = 30 by growth_score among qualifiers, universe >= 0.5 cr/day and >= 252 days listed,
no new buys in the top-5% volatility, keep while qualifying or ranked <= 150.

Decision rule (`passes`, also fixed before any run; applied by early_movers_eval.py). A definition
ships as a second list only if, over the period it can be tested (from its first date with names),
compared with the shipped Top list (portfolio.RECOMMENDED) on the same dates, ALL of:
    a  pick crash rate (new entries whose 12-month return <= -30%) <= 0.75 x the Top list's
    b  max drawdown at least 3 pts shallower than the Top list's
    c  smaller in-year drawdown than the Top list in >= 2/3 of calendar years (robust, not one crash)
    d  CAGR >= the NIFTY SMALLCAP 250's (a list that loses to the index is not worth a tab)
    e  diversification: median overlap with the Top list <= 50% of its names, and the 50/50
       combination has return/vol >= the Top list's alone (it improves the Top list, not just copies it)
    f  enough names: median list size >= 10 and < 10% of dates with fewer than 5 names
    g  >= 4 calendar years of test history
Among definitions that pass, RECOMMENDED is the one with the most years of smaller drawdown than the
Top list, then the lowest crash rate. If none passes, RECOMMENDED = None (the eval report says why).
"""

from dataclasses import dataclass, replace

import numpy as np
import pandas as pd

STRETCHED_MA200_GAP = 0.6     # build_v3.EXTENDED_MA200_GAP


@dataclass(frozen=True)
class EMRules:
    n: int = 30
    min_adv_cr: float | None = 0.5
    min_days_listed: int | None = 252
    vol_exclude_pct: float | None = 0.05
    keep_rank: int | None = 150
    # base breakout
    near_high: float = 0.05               # dist_52w_high >= -near_high
    max_ret_6m: float = 0.30
    above_ma200: bool = True
    max_ma200_gap: float | None = STRETCHED_MA200_GAP
    # score floor
    min_score: float | None = None
    # fundamentals (None = not used)
    min_revenue_yoy: float | None = None
    min_profit_yoy: float | None = None
    require_profitable: bool = False
    growth_momentum: str | None = None    # "all": accel AND margin up; "any": accel OR margin up
    min_cash_conversion: float | None = None
    cash_conversion_missing_ok: bool = False

    def with_(self, **kw):
        return replace(self, **kw)

    def uses_fundamentals(self):
        return any(v not in (None, False) for v in (self.min_revenue_yoy, self.min_profit_yoy, self.require_profitable,
                                                      self.growth_momentum, self.min_cash_conversion))

    def label(self):
        parts = [f"N{self.n}", f"<= {self.near_high:.0%} below 52w high", f"6m < {self.max_ret_6m:.0%}"]
        if self.above_ma200:
            parts.append("above 200d avg")
        if self.min_score is not None:
            parts.append(f"score >= {self.min_score:g}")
        if self.min_revenue_yoy is not None:
            parts.append(f"rev YoY > {self.min_revenue_yoy:.0%}")
        if self.min_profit_yoy is not None:
            parts.append(f"profit YoY > {self.min_profit_yoy:.0%}")
        if self.require_profitable:
            parts.append("profitable")
        if self.growth_momentum == "all":
            parts.append("rev accel AND margin up")
        elif self.growth_momentum == "any":
            parts.append("rev accel OR margin up")
        if self.min_cash_conversion is not None:
            parts.append(f"cash conv > {self.min_cash_conversion:g}" + (" (if reported)" if self.cash_conversion_missing_ok else ""))
        if self.keep_rank:
            parts.append(f"keep while qualifying or rank <= {self.keep_rank}")
        return ", ".join(parts)


E1 = EMRules()
DEFINITIONS = {
    "E1": E1,
    "E2": E1.with_(min_score=60),
    "E3": E1.with_(min_revenue_yoy=0.20, min_profit_yoy=0.20, require_profitable=True, growth_momentum="all",
                   min_cash_conversion=0.7),
    "E4": E1.with_(near_high=0.10, min_revenue_yoy=0.10, min_profit_yoy=0.10, require_profitable=True,
                   growth_momentum="any", min_cash_conversion=0.5, cash_conversion_missing_ok=True),
}

# Decision rule thresholds (see docstring; fixed before any run)
CRASH_RATIO_MAX = 0.75
DD_BETTER_PTS = 0.03
YEARS_SMALLER_DD_SHARE = 2 / 3
MAX_OVERLAP = 0.50
MIN_MEDIAN_NAMES = 10
MAX_SHARE_THIN_DATES = 0.10
THIN_NAMES = 5
MIN_TEST_YEARS = 4

# Set from the eval run of 2026-10-02 by the pre-declared rule (early_movers_eval.py prints which definition
# passes; reports/EARLY_MOVERS.md): E1 and E2 pass, E1 wins the tie-break (equal years with a smaller drawdown,
# crash rate 7.6% vs 7.8%: a coin flip). None would mean nothing passed.
RECOMMENDED = DEFINITIONS["E1"]


def _col(df, name):
    return df[name] if name in df else pd.Series(np.nan, index=df.index)


def qualifies(df, rules):
    """Boolean Series: the entry pattern of `rules` (NaN inputs never qualify)."""
    q = (_col(df, "dist_52w_high") >= -rules.near_high) & (_col(df, "return_6m") < rules.max_ret_6m)
    gap = _col(df, "ma200_gap")
    if rules.above_ma200:
        q &= gap > 0
    if rules.max_ma200_gap is not None:
        q &= gap < rules.max_ma200_gap
    if rules.min_score is not None:
        q &= df["growth_score"] >= rules.min_score
    if rules.min_revenue_yoy is not None:
        q &= _col(df, "revenue_yoy") > rules.min_revenue_yoy
    if rules.min_profit_yoy is not None:
        q &= _col(df, "net_profit_yoy") > rules.min_profit_yoy
    if rules.require_profitable:
        q &= _col(df, "net_profit_ttm") > 0
    accel, margin = _col(df, "revenue_yoy_accel") > 0, _col(df, "op_margin_change_yoy") > 0
    if rules.growth_momentum == "all":
        q &= accel & margin
    elif rules.growth_momentum == "any":
        q &= accel | margin
    if rules.min_cash_conversion is not None:
        cc = _col(df, "cash_conversion")
        ok = cc > rules.min_cash_conversion
        if rules.cash_conversion_missing_ok:
            ok |= cc.isna()
        q &= ok
    return q.fillna(False).astype(bool)


def select_early_movers(scored_df, prev_holdings=(), rules=E1):
    """-> DataFrame of the selected rows (columns of scored_df plus sel_rank, qualifies, kept), kept
    holdings first by score, then new entries by score. May be shorter than rules.n, or empty."""
    df = scored_df[scored_df["growth_score"].notna()].copy()
    prev = {int(c) for c in prev_holdings}
    if rules.min_adv_cr:
        df = df[df["adv_cr"] >= rules.min_adv_cr]
    if rules.min_days_listed:
        df = df[df["days_listed"] >= rules.min_days_listed]
    df = df.sort_values(["growth_score", "company_id"], ascending=[False, True])
    df["sel_rank"] = np.arange(1, len(df) + 1)
    df["qualifies"] = qualifies(df, rules)

    held = df["company_id"].isin(prev)
    keep_ok = df["qualifies"] | (df["sel_rank"] <= rules.keep_rank if rules.keep_rank else False)
    kept_idx = list(df.index[held & keep_ok][:rules.n])

    can_buy = df["qualifies"] & ~held
    if rules.vol_exclude_pct and "volatility" in df:
        cut = df["volatility"].quantile(1 - rules.vol_exclude_pct)
        can_buy &= ~(df["volatility"] > cut)
    new_idx = list(df.index[can_buy][:max(rules.n - len(kept_idx), 0)])

    out = df.loc[kept_idx + new_idx].copy()
    out["kept"] = out.index.isin(kept_idx)
    return out.reset_index(drop=True)


def passes(c):
    """Pre-declared decision rule on a candidate's comparison dict (keys set by early_movers_eval.compare).
    -> (bool, {criterion: bool})."""
    checks = {
        "a crash rate <= 0.75 x Top list": c["crash_rate"] <= CRASH_RATIO_MAX * c["top_crash_rate"],
        "b max DD >= 3 pts shallower": c["max_dd"] >= c["top_max_dd"] + DD_BETTER_PTS,
        "c smaller in-year DD in >= 2/3 of years": c["years_smaller_dd"] >= YEARS_SMALLER_DD_SHARE * c["years"],
        "d CAGR >= Smallcap 250": c["cagr"] >= c["index_cagr"],
        "e overlap <= 50% and 50/50 return/vol >= Top list": (c["overlap_median"] <= MAX_OVERLAP
                                                              and c["combo_sharpe"] >= c["top_sharpe"]),
        "f enough names": (c["names_median"] >= MIN_MEDIAN_NAMES and c["share_thin_dates"] < MAX_SHARE_THIN_DATES),
        "g >= 4 years of history": c["test_years"] >= MIN_TEST_YEARS,
    }
    return all(checks.values()), checks


def choose(candidates):
    """Pre-declared tie-break among passing definitions: most years with a smaller DD, then lowest crash rate."""
    ok = [k for k, c in candidates.items() if passes(c)[0]]
    if not ok:
        return None
    return max(ok, key=lambda k: (candidates[k]["years_smaller_dd"], -candidates[k]["crash_rate"]))
