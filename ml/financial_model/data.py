"""Point-in-time panel for the Financial Model: statement features joined onto the label grid.

Sources
-------
- `financial_filings` (TiDB, one SELECT) -> `financials.features.build_feature_table`: one feature
  row per (company, period_end), stamped with the filing_date of the filing that reported it. The
  raw filings and the feature table are cached in ml/data/processed/ (`financial_raw.pkl`,
  `financial_features.pkl`) and reused until `refresh=True`.
- `growth_model.labels` rows (ml/data/processed/growth_labels.pkl): 1st/16th signal dates, excess
  return vs NIFTY SMALLCAP 250 over 1/3/6/12 months, plus the liquidity context (adv_60d_cr,
  days_listed) the market model filters on.

As-of join (no look-ahead)
--------------------------
For a signal date D a feature row is visible when filing_date <= D 00:00 (the same test as
rankings/build.py `latest_financials`, so a filing made during D itself counts from the next
signal date). Among visible rows the one with the latest period_end wins (ties: latest filing).
Because an older period can be filed late, "latest visible" is not simply "last filed": the join
keeps, per company, only the rows that become the best visible row at their filing time (period_end
>= every earlier-filed period_end) and then does a backward as-of merge on filing_date.
If that period ended more than STALE_FINANCIALS_DAYS (275, as in build.py) before D the financials
are stale: the row is kept for bookkeeping but is outside the model universe.
`check_point_in_time` asserts that no joined row has filing_date > D.

Universe (same filters as growth_model/market_model.py, plus fresh financials)
    adv_60d_cr >= 0.5 crore/day, days_listed >= 252, entry price >= Rs 1 (labels.py),
    format = non_financial (features.py skips banks/NBFCs/insurers), fresh financials.

Model features (`MODEL_FEATURES`) are raw statement ratios from features.py plus a few derived ones:
    fcf_margin, ocf_margin, capex_intensity   cash flow / TTM revenue
    cash_conversion                           OCF / net profit, only when profit > 0 (as build.py)
    roe                                       NaN when equity is negative (as build.py)
    coverage_input                            interest coverage capped at 100, debt-free = best
    log_revenue_ttm                           size (log10 crore)
    profitable                                1 if TTM net profit > 0
    n_red_flags                               count of features.py red flags that are True
    filing_lag_days                           days from period end to filing (late filers)
`rank_features` turns each into a cross-sectional percentile (0-1) per signal date within the
universe; NaN stays NaN.
"""

import time
import warnings

import numpy as np
import pandas as pd

from growth_model.labels import LABELS_FILE
from growth_model.prices import CACHE_DIR

RAW_CACHE = CACHE_DIR / "financial_raw.pkl"
FEATURES_CACHE = CACHE_DIR / "financial_features.pkl"

STALE_FINANCIALS_DAYS = 275      # rankings/build.py
MIN_ADV_CR = 0.5                 # growth_model/market_model.py
MIN_DAYS_LISTED = 252

RED_FLAGS = [
    "flag_profit_up_ocf_negative", "flag_receivables_outpacing_revenue", "flag_debt_to_equity_rising",
    "flag_negative_equity", "flag_low_interest_coverage",
]

# feature -> (group, economically expected sign: +1 higher is better, -1 lower, 0 unclear)
MODEL_FEATURES = {
    "revenue_yoy": ("growth", 1), "net_profit_yoy": ("growth", 1), "eps_yoy": ("growth", 1),
    "revenue_ttm_growth": ("growth", 1), "net_profit_ttm_growth": ("growth", 1),
    "eps_ttm_growth": ("growth", 1),
    "revenue_yoy_accel": ("growth", 1), "net_profit_yoy_accel": ("growth", 1),
    "op_margin_q": ("profitability", 1), "op_margin_ttm": ("profitability", 1),
    "op_margin_change_yoy": ("profitability", 1), "net_margin_ttm": ("profitability", 1),
    "net_margin_change_yoy": ("profitability", 1), "roe": ("profitability", 1),
    "roce": ("profitability", 1), "profitable": ("profitability", 1),
    "debt_to_equity": ("financial_health", -1), "debt_to_equity_change_1y": ("financial_health", -1),
    "current_ratio": ("financial_health", 1), "coverage_input": ("financial_health", 1),
    "cash_conversion": ("cash_flow", 1), "fcf_margin": ("cash_flow", 1), "ocf_margin": ("cash_flow", 1),
    "accruals_ratio": ("cash_flow", -1), "capex_intensity": ("cash_flow", 0),
    "receivables_minus_revenue_growth": ("quality", -1), "n_red_flags": ("quality", -1),
    "filing_lag_days": ("quality", -1),
    "log_revenue_ttm": ("size", 0),
}
FEATURE_NAMES = list(MODEL_FEATURES)


# ---------------------------------------------------------
# Loading (cached)
# ---------------------------------------------------------

def load_feature_table(refresh=False):
    """-> (feature table from features.py, raw filings). One DB SELECT when not cached."""
    if not refresh and RAW_CACHE.exists() and FEATURES_CACHE.exists():
        return pd.read_pickle(FEATURES_CACHE), pd.read_pickle(RAW_CACHE)

    warnings.filterwarnings("ignore", message="pandas only supports SQLAlchemy")
    from financials.features import _load_raw, build_feature_table
    from news_pipeline.db import get_connection

    t0 = time.time()
    conn = get_connection()
    try:
        raw = _load_raw(conn)                 # SELECT only
    finally:
        conn.close()
    print(f"  loaded {len(raw):,} non_financial filings in {time.time() - t0:.0f}s; building features ...")
    table = build_feature_table(None, raw=raw)
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    raw.to_pickle(RAW_CACHE)
    table.to_pickle(FEATURES_CACHE)
    print(f"  {len(table):,} feature rows, {table['company_id'].nunique():,} companies in {time.time() - t0:.0f}s")
    return table, raw


def add_derived(f):
    """Model inputs derived from features.py columns (NaN where meaningless, never 0)."""
    f = f.copy()
    rev = f["revenue_ttm"].where(f["revenue_ttm"] > 1)
    f["fcf_margin"] = f["fcf_ttm"] / rev
    f["ocf_margin"] = f["ocf_ttm"] / rev
    f["capex_intensity"] = f["capex_ttm"] / rev
    f["cash_conversion"] = f["cash_conversion"].where(f["net_profit_ttm"] > 0)
    neg_eq = f["flag_negative_equity"].astype("boolean").fillna(False).astype(bool)
    f["roe"] = f["roe"].where(~neg_eq)
    debt_free = f["debt_to_equity"] < 0.05
    cov = f["interest_coverage_ttm"].clip(upper=100)
    f["coverage_input"] = cov.where(cov.notna(), np.where(debt_free, 1e9, np.nan))
    f["coverage_rank_input"] = f["coverage_input"]      # build.py's name, used by the baseline
    f["log_revenue_ttm"] = np.log10(rev)
    f["profitable"] = np.where(f["net_profit_ttm"].isna(), np.nan, (f["net_profit_ttm"] > 0).astype(float))
    flags = pd.DataFrame({c: f[c].astype("boolean").fillna(False).astype(int) for c in RED_FLAGS})
    f["n_red_flags"] = flags.sum(axis=1).astype(float)
    f["filing_lag_days"] = f["days_since_period_end"].astype(float)
    num = [c for c in f.columns if c in FEATURE_NAMES]
    f[num] = f[num].replace([np.inf, -np.inf], np.nan)
    return f


# ---------------------------------------------------------
# As-of join
# ---------------------------------------------------------

def _best_visible_rows(features):
    """Rows that become a company's best visible row (max period_end so far) when filed."""
    f = features[features["company_id"].notna()].copy()
    f["company_id"] = f["company_id"].astype(int)
    f = f.sort_values(["company_id", "filing_date", "period_end"]).reset_index(drop=True)
    prev_max = f.groupby("company_id")["period_end"].transform(lambda s: s.cummax().shift())
    keep = prev_max.isna() | (f["period_end"] >= prev_max)
    return f[keep]


def asof_join(keys, features):
    """keys: DataFrame with company_id, signal_date. Returns keys + the visible feature row as of D.

    Visibility: filing_date <= signal_date (midnight), as rankings/build.py.
    """
    best = _best_visible_rows(features).rename(columns={"symbol": "fin_symbol"})
    left = keys.assign(signal_date=keys["signal_date"].astype("datetime64[ns]"))
    left = left.sort_values("signal_date").reset_index(drop=True)
    right = best.assign(filing_date=best["filing_date"].astype("datetime64[ns]"))
    right = right.sort_values("filing_date").reset_index(drop=True)
    out = pd.merge_asof(left, right, left_on="signal_date", right_on="filing_date",
                        by="company_id", direction="backward", allow_exact_matches=True)
    age = (out["signal_date"] - out["period_end"]).dt.days
    out["fin_stale"] = age.isna() | (age > STALE_FINANCIALS_DAYS)
    return out


def check_point_in_time(panel):
    """Unit check: no feature row may be filed after its signal date."""
    has = panel["filing_date"].notna()
    bad = panel.loc[has, "filing_date"] > panel.loc[has, "signal_date"]
    assert not bad.any(), f"{int(bad.sum())} rows use a filing made after the signal date"
    assert (panel.loc[has, "period_end"] < panel.loc[has, "signal_date"]).all(), "period_end after D"
    return True


def rank_features(panel, columns=FEATURE_NAMES):
    """Cross-sectional percentile (0-1) of each feature within its signal date (NaN stays NaN)."""
    ranked = panel.copy()
    ranked[columns] = panel.groupby("signal_date")[columns].rank(pct=True)
    return ranked


def build_panel(refresh=False, labels=None):
    """Label rows in the universe with fresh, point-in-time financial features (raw + ranked).

    Returns (panel, raw_panel_before_universe_stats dict).
    """
    features, _ = load_feature_table(refresh=refresh)
    if labels is None:
        labels = pd.read_pickle(LABELS_FILE)
    liquid = (labels["adv_60d_cr"] >= MIN_ADV_CR) & (labels["days_listed"] >= MIN_DAYS_LISTED)
    panel = asof_join(labels[liquid], features)
    check_point_in_time(panel)
    stats = {
        "liquid_rows": int(liquid.sum()),
        "with_financials": int(panel["filing_date"].notna().sum()),
        "fresh_financials": int((~panel["fin_stale"]).sum()),
    }
    panel = add_derived(panel[~panel["fin_stale"]])
    return panel.reset_index(drop=True), stats
