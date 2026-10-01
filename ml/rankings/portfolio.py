"""Top-list construction for the InvestIQ ranking: which N companies make the "Top list" on a date.

The growth_score ranks companies well (walk-forward IC ~0.07-0.10), but the plain "top 50 by score,
equal weight, replaced every 15 days" list is jumpy: thinly traded names, sector piles, very volatile
stocks and heavy churn (rankings/portfolio_eval.py, reports/PORTFOLIO.md). This module turns a scored
cross-section into a holdings list with explicit, testable rules. It is pure (no DB, no I/O) so the
backtest (portfolio_eval.py), build_v3.py and the site can all call the same function.

Input frame (`scored_df`), one row per company on the date, columns:
    company_id      int
    growth_score    0-100, NaN = unranked (never selected)
    sector          str or None (None: not capped)
    adv_cr          median daily traded value, INR crore (eval: labels adv_60d_cr; live: build.py
                    avg_traded_value_3m_cr, a mean, so slightly looser)          [min_adv_cr]
    days_listed     trading days with a price up to the date (eval: labels)      [min_days_listed]
    volatility      annualised daily volatility (eval: market features vol_3m)  [volatility rules]
    market_score    0-100 market-model percentile (build_v3 market_score)        [risk_adjust="score"]
    is_fin_sector   bool (financial-sector rows put all their non-news weight on the market part)
    return_6m       6-month price return                                          [exclude_stretched]
    ma200_gap       close / 200-day average - 1                                   [exclude_stretched]
Only the columns a rule needs must be present.

Rules (`Rules`, defaults = today's implied list: top 50, nothing else):
    n                 list size
    min_adv_cr        liquidity floor; applies to holdings too (an illiquid name is sold)
    min_days_listed   listing-age floor (252 = 1 year of prices); applies to holdings too. Together with
                      min_adv_cr = 0.5 this is the universe every backtest of the score covers
    sector_cap        max share of n from one sector (0.2 -> 10 of 50); counts kept holdings first
    vol_exclude_pct   new buys must not be in the top x of the date's volatility (0.05 = top 5%)
    risk_adjust       None; "score": the market part of growth_score is replaced by the percentile of
                      market_score / volatility (smooth risers beat wild ones; same weights as
                      build_v3: 0.95 x 0.70 non-financial, 0.95 financial sector); "lowvol": take the
                      top `lowvol_pool` x n by score, then the n least volatile of them
    lowvol_pool       pool multiple for risk_adjust="lowvol" (2 -> choose 50 from the top 100)
    buffer_rank       turnover buffer: a holding is kept while its rank (by the selection score,
                      among names passing the hard filters) <= buffer_rank; vacancies are filled from
                      the top. None = full replacement every rebalance
    exclude_stretched new buys must not be "price already stretched" (build_v3 caution: up > 100% in
                      6 months or >= 60% above the 200-day average)
Entry-only rules (volatility exclusion, stretched) do not force a sale of a name already held:
selling a stock because it went up (or got bumpy) while it still ranks well would just add churn.

select_top_list() returns a DataFrame of the chosen rows (company_id, rank, selection score,
"kept" = held before and retained) in list order: kept holdings first by rank, then new entries.
"""

from dataclasses import dataclass, replace

import numpy as np
import pandas as pd

NEWS_WEIGHT = 0.05            # build_v3
MARKET_WEIGHT = 0.7           # build_v3 (non-financial)
FIN_MARKET_WEIGHT = 1.0       # build_v3 (financial sector)
STRETCHED_RET_6M = 1.0        # build_v3.EXTENDED_RET_6M
STRETCHED_MA200_GAP = 0.6     # build_v3.EXTENDED_MA200_GAP


@dataclass(frozen=True)
class Rules:
    n: int = 50
    min_adv_cr: float | None = None
    min_days_listed: int | None = None
    sector_cap: float | None = None
    vol_exclude_pct: float | None = None
    risk_adjust: str | None = None
    lowvol_pool: float = 2.0
    buffer_rank: int | None = None
    exclude_stretched: bool = False

    def with_(self, **kw):
        return replace(self, **kw)

    def label(self):
        parts = [f"N{self.n}"]
        if self.min_adv_cr:
            parts.append(f"liq>={self.min_adv_cr:g}cr")
        if self.min_days_listed:
            parts.append(f"listed>={self.min_days_listed}d")
        if self.sector_cap:
            parts.append(f"sector<={self.sector_cap:.0%}")
        if self.vol_exclude_pct:
            parts.append(f"no top-{self.vol_exclude_pct:.0%} vol")
        if self.risk_adjust == "score":
            parts.append("trend/vol score")
        elif self.risk_adjust == "lowvol":
            parts.append(f"low-vol of top {self.lowvol_pool:g}N")
        if self.buffer_rank:
            parts.append(f"keep while rank<={self.buffer_rank}")
        if self.exclude_stretched:
            parts.append("no stretched buys")
        return ", ".join(parts)


TODAY = Rules()               # the list the site implies today
# reports/PORTFOLIO.md: the tested universe (>= 0.5 cr/day, >= 1 year listed), no new buys in the most
# volatile 5%, keep a holding while it ranks <= 150; 50 names, equal weight, rebalanced on the 1st/16th
RECOMMENDED = Rules(n=50, min_adv_cr=0.5, min_days_listed=252, vol_exclude_pct=0.05, buffer_rank=150)


def _pct(s):
    """Percentile 0-1 among non-null values (average ties)."""
    return s.rank(pct=True, method="average")


def risk_adjusted_score(df):
    """growth_score with its market part replaced by the percentile of market_score / volatility."""
    ratio = df["market_score"] / df["volatility"].where(df["volatility"] > 0)
    ra = _pct(ratio.where(df["growth_score"].notna())) * 100
    fin = df["is_fin_sector"].astype(bool) if "is_fin_sector" in df else pd.Series(False, index=df.index)
    w = (1 - NEWS_WEIGHT) * np.where(fin, FIN_MARKET_WEIGHT, MARKET_WEIGHT)
    out = df["growth_score"] + w * (ra - df["market_score"])
    return out.where(ra.notna(), df["growth_score"])        # no volatility -> unchanged score


def stretched(df):
    r6 = df["return_6m"] if "return_6m" in df else pd.Series(np.nan, index=df.index)
    gap = df["ma200_gap"] if "ma200_gap" in df else pd.Series(np.nan, index=df.index)
    return (r6 > STRETCHED_RET_6M) | (gap >= STRETCHED_MA200_GAP)


def select_top_list(scored_df, prev_holdings=(), rules=TODAY):
    """-> DataFrame of the selected rows, columns of scored_df plus sel_score, sel_rank, kept."""
    df = scored_df[scored_df["growth_score"].notna()].copy()
    prev = {int(c) for c in prev_holdings}
    if rules.risk_adjust == "score":
        df["sel_score"] = risk_adjusted_score(df)
    else:
        df["sel_score"] = df["growth_score"]

    # hard filters (holdings too)
    if rules.min_adv_cr:
        df = df[df["adv_cr"] >= rules.min_adv_cr]
    if rules.min_days_listed:
        df = df[df["days_listed"] >= rules.min_days_listed]
    df = df.sort_values(["sel_score", "company_id"], ascending=[False, True])
    df["sel_rank"] = np.arange(1, len(df) + 1)

    # entry filters (new buys only)
    can_buy = pd.Series(True, index=df.index)
    if rules.vol_exclude_pct:
        cut = df["volatility"].quantile(1 - rules.vol_exclude_pct)
        can_buy &= ~(df["volatility"] > cut)
    if rules.exclude_stretched:
        can_buy &= ~stretched(df)
    if rules.risk_adjust == "lowvol":
        pool = df[can_buy].head(int(round(rules.lowvol_pool * rules.n)))
        order = pool.sort_values(["volatility", "sel_rank"], na_position="last").index
        candidates = list(order)
    else:
        candidates = list(df.index[can_buy])

    cap = int(np.floor(rules.sector_cap * rules.n)) if rules.sector_cap else None
    counts, chosen, kept = {}, [], set()

    def room(sector):
        return cap is None or sector is None or pd.isna(sector) or counts.get(sector, 0) < cap

    def take(i):
        chosen.append(i)
        s = df.at[i, "sector"] if "sector" in df else None
        if s is not None and not pd.isna(s):
            counts[s] = counts.get(s, 0) + 1

    # 1. keep holdings that still rank inside the buffer (best first, sector cap respected)
    if rules.buffer_rank and prev:
        held = df[df["company_id"].isin(prev) & (df["sel_rank"] <= rules.buffer_rank)]
        for i in held.index:
            if len(chosen) >= rules.n:
                break
            if room(df.at[i, "sector"] if "sector" in df else None):
                take(i)
                kept.add(i)
    # 2. fill vacancies from the top
    for i in candidates:
        if len(chosen) >= rules.n:
            break
        if i in kept:
            continue
        if room(df.at[i, "sector"] if "sector" in df else None):
            take(i)

    out = df.loc[chosen].copy()
    out["kept"] = out.index.isin(kept) | out["company_id"].isin(prev)
    return out.reset_index(drop=True)
