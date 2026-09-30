"""InvestIQ combiner (`model_version = 'investiq-v1'`) -> `company_rankings` (same contract as prelim-v2).

Same table, labels, ranks, reasons / risks and key_metrics as rankings/build.py (docs/company-rankings.md);
only the growth_score recipe and the financial-sector coverage change. prelim-v2 (build.py) is left
untouched and still builds with `python3 -m rankings.build`.

Why this recipe (walk-forward evidence: rankings/combiner_eval.py, V3_COMPARISON.md)
------------------------------------------------------------------------------------
- market model (trend6, growth_model/market_model.py) is the strongest signal: walk-forward IC
  ~0.06 (6m) / 0.10 (12m) on the rankable non-financial universe, top decile above the average
  stock in 7/7 and 5/5 years.
- financial model (fin-v1 = prelim-v2's financial blend, financial_model/) is weak and
  regime-dependent: IC 0.04 / 0.03, top decile above average in 4/7 and 2/5 years.
- combiner weight w (growth_score = w x market + (1 - w) x financial) was chosen by a rule fixed
  before the test (`combiner_eval.choose_w`): max of mean(yearly IC) - 0.5 x std(yearly IC) over
  a pre-declared grid, on training years only per fold (expanding window, purged). On all labelled
  years (6m and 12m averaged) the rule picks w = 1.0: 6m alone prefers ~0.7, 12m prefers 1.0, and
  the difference between 0.7-1.0 is within noise. The shipped MARKET_WEIGHT = 0.7 (owner's choice
  within that noise band: 6m IC .065 vs .061 trend-only, 12m .097 vs .102) keeps a 30% business-
  quality anchor so the list is not a pure momentum screen. Financial statements also act as (a) the
  eligibility gate (a company needs a fresh growth reading to be ranked, as in prelim-v2), (b) the one
  red-flag penalty the evidence supports, and (c) the reasons / risks text. prelim-v2's weights (80% financial) had IC 0.052 / 0.057 on the same rows.
- news has only existed since 2026-08 (no labelled history), so it can't be backtested: it keeps
  the small fixed weight NEWS_WEIGHT = 0.05, as in prelim-v2.
- banks / NBFCs / insurers (financials/fin_sector_features.py, FIN_SECTOR_REPORT.md): the
  report's recipe (peer-group percentiles, momentum .50) had IC -0.02 / 0.00 vs +0.01 / +0.05 for
  price trend alone on the same names, so it is NOT adopted (ADOPT_FIN_RECIPE = False, pre-declared
  rule `combiner_eval.adopt_fin_recipe`). They are scored like everyone else (price trend + news)
  and their bank / NBFC / insurer features become component scores (display), reasons and risks.
  Their penalties (asset quality worsening, capital near minimum, negative equity) slightly improved
  trend alone (12m IC 0.053 vs 0.050, 5/6 vs 4/6 years positive), so they are kept.

Method
------
1. Inputs (point-in-time as of the snapshot date D; loaders shared with build.py):
   - non-financial companies: the latest `financials.features` row with filing_date <= D (build.py
     `latest_financials`, stale after 275 days).
   - banks / NBFCs / insurers in scope of fin_sector_features (lender-format filers): the latest
     fin_sector feature row with filing_date <= D 00:00, stale after 275 days. Their features.py
     rows (the odd misdetected quarter) are dropped. The lender lines come from the cached XBRL
     extract (ml/data/processed/fin_sector_filings.pkl); without it (e.g. on CI) these companies
     get no financial components and stay unranked, with a warning.
   - prices (400 days), NIFTY SMALLCAP 250 and 90 days of news, exactly as build.py.

2. Component scores (0-100, display + eligibility; build.py `score` for non-financial companies):
     growth, profitability, financial_health, cash_flow   build.py sub-features and percentiles
     momentum   build.py: percentile of the mean of the six trend-signal percentiles (= trend6)
     news       build.py: centred on 50
   Financial-sector companies: growth / profitability / financial_health from their own features,
   percentiles within peer groups (bank, lending NBFC (loans/assets >= 0.5), other NBFC-format,
   NBFC without a balance sheet yet, insurer; groups with < 15 fresh names are pooled), sub-features
   as combiner_eval.FIN_SUBFEATURES; cash_flow is not applicable (NULL).

3. growth_score = (1 - NEWS_WEIGHT) x [MARKET_WEIGHT x momentum + (1 - MARKET_WEIGHT) x financial]
                  + NEWS_WEIGHT x news - penalty, clipped to 0-100
   where financial = fin-v1: percentile among companies with a growth component of the prelim-v2
   financial blend (growth .30, profitability .20, health .15, cash flow .15, minus prelim-v2's
   flag penalties); with MARKET_WEIGHT = 1.0 it has no weight (it is still computed for the dry-run
   file). Financial-sector companies use FIN_MARKET_WEIGHT (1.0: no financial blend).
   Penalties (points): non-financial: negative equity 6 (the only features.py flag whose flagged
   names trailed in >= 2/3 of years on both horizons; the other four are risk text only);
   financial sector: asset quality worsening 4, capital near minimum 6, negative equity 6; ROA
   collapse is risk text only.
   Ranked only with a momentum score AND a fresh growth component AND coverage >= MIN_COVERAGE
   (0.5 non-financial, 0.6 financial sector); coverage = share of the applicable components
   available (cash flow is not applicable to the financial sector). Otherwise 'Insufficient data'.
   Labels: >= 75 Strong, >= 60 Positive, >= 40 Neutral, else Weak (as prelim-v2).

4. Ranks, reasons / risks and key_metrics as build.py. Financial-sector companies get their own
   reasons / risks (growth, ROE / ROA, cost-to-income, NPAs, provision coverage, CET1, solvency,
   red flags) and key_metrics (nim, cost_to_income_ttm, roa, roe, gross_npa_pct, net_npa_pct,
   cet1_ratio, solvency_ratio, advances_growth_1y, credit_cost; revenue = net revenue). All
   companies get a risk line when they trade < 0.5 crore a day (outside the backtested universe).

CLI:  python3 -m rankings.build_v3 [--date YYYY-MM-DD] [--out PATH] [--compare] [--symbols ...]
          dry run (default): computes the snapshot, writes a local CSV + JSON (default
          ml/data/processed/rankings_investiq_v1_<date>.csv/.json), never touches the DB except SELECTs.
          --compare also recomputes prelim-v2 from the same inputs for V3_COMPARISON.md.
      python3 -m rankings.build_v3 --date YYYY-MM-DD --publish
          writes the snapshot to company_rankings (replaces every row of that snapshot date, like
          build.py). Only with explicit approval.
"""

import argparse
import json
import math
import warnings
from datetime import date, datetime

import numpy as np
import pandas as pd

from . import build as v2
from .build import _num, _ok, _true, crore, pct, pct_rank
from .combiner_eval import FIN_PENALTY, FIN_SUBFEATURES, fin_asof, fin_scores

MODEL_VERSION = "investiq-v1"
MARKET_WEIGHT = 0.7          # user choice: 70% trend + 30% financial (6m IC .065, 12m .097; see docstring)
FIN_MARKET_WEIGHT = 1.0      # financial sector: recipe not adopted -> price trend led
ADOPT_FIN_RECIPE = False     # combiner_eval.adopt_fin_recipe result
NEWS_WEIGHT = 0.05
PENALTY_NONFIN = {"flag_negative_equity": 6}
PENALTY_FIN = dict(FIN_PENALTY)
MIN_COVERAGE = {"non_financial": 0.5, "financial": 0.6}
THIN_TRADING_CR = 0.5        # market model / backtest universe
MOMENTUM_TEXT_PCT = 75       # momentum score >= 75 -> first reason; <= 25 -> first risk
COMPONENTS = ["growth", "profitability", "financial_health", "cash_flow", "momentum", "news"]
FIN_V1_WEIGHTS = {c: v2.WEIGHTS[c] for c in v2.FINANCIAL_COMPONENTS}

METHOD_TEXT = (
    "InvestIQ score (investiq-v1): 70% market model, 30% financial model, plus a small news weight. The "
    "market model measures how strongly the price trend confirms the business - distance from the 52-week "
    "high, position versus the 200-day and 50-day averages, 3- and 6-month returns relative to the NIFTY "
    "Smallcap 250 and how few down days the stock has had. The financial model scores revenue and profit "
    "growth, profitability, balance-sheet health and cash-flow quality from the company's own filings, using "
    "only results that were public at the time. In walk-forward tests over 2019-2026 this mix ranked future "
    "6- and 12-month out-performers about twice as well as the earlier preliminary score. A fresh financial "
    "reading is required to be ranked, and red flags that have historically preceded under-performance "
    "(negative equity; for banks, NBFCs and insurers also worsening asset quality and capital near the "
    "regulatory minimum) cost points. Banks, NBFCs and insurers are scored mainly on price trend, with their "
    "NPAs, capital, ROA/ROE and cost ratios shown against their own peer group. Scores are percentiles from 0 "
    "to 100; companies with too little data are shown as unranked. This is a screening aid, not investment advice."
)

PEER_NAME = {"bank": "banks", "lending_nbfc": "lending NBFCs", "other_nbfc": "NBFC-format peers",
             "nbfc_unknown": "NBFCs", "insurance": "insurers", "all_financial": "financial companies"}


# ---------------------------------------------------------
# Financial sector inputs
# ---------------------------------------------------------

def load_fin_sector(snap, company_ids, conn=None):
    """-> (scored fin_sector rows for D keyed by company_id, in-scope company ids, raw extract or None).
    Reads the local extract when present (the Mac with the XBRL cache), else its DB copy (CI)."""
    from financials.fin_sector_features import (EXTRACT_FILE, build_feature_table, load_extract,
                                                load_extract_db, raw_from_extract)

    extract = load_extract() if EXTRACT_FILE.exists() else (load_extract_db(conn) if conn else None)
    if extract is None:
        print(f"warning: no fin_sector extract ({EXTRACT_FILE} or DB table): banks/NBFCs/insurers get no "
              f"financial components (run `python3 -m financials.fin_sector_features --refresh-extract "
              f"--push-db` where the XBRL cache is)")
        return pd.DataFrame(columns=["company_id"]), set(), None
    raw = raw_from_extract(extract)
    table = build_feature_table(raw)
    in_scope = set(table["company_id"].dropna().astype(int))
    keys = pd.DataFrame({"company_id": sorted(in_scope & set(company_ids)), "snapshot": pd.Timestamp(snap)})
    rows = fin_asof(table, keys, key_date="snapshot")
    rows = rows[~rows["fin_stale"]].reset_index(drop=True)
    rows = fin_scores(rows, date_col="snapshot")
    return rows.set_index("company_id"), in_scope, raw


# ---------------------------------------------------------
# Scoring
# ---------------------------------------------------------

def fin_v1_score(df):
    """fin-v1 (financial_model baseline) on the snapshot: percentile x 100 of the prelim-v2 financial
    blend among non-financial companies with a growth component."""
    avail = pd.DataFrame({c: df[f"score_{c}"].notna() for c in FIN_V1_WEIGHTS})
    wsum = sum(avail[c] * w for c, w in FIN_V1_WEIGHTS.items())
    wscore = sum(df[f"score_{c}"].fillna(0) * w for c, w in FIN_V1_WEIGHTS.items())
    pen = sum(df[f].map(_true).astype(bool) * pts for f, pts in v2.FLAG_PENALTY.items())
    blend = (wscore / wsum.replace(0, np.nan) - pen).where(avail["growth"] & ~df["is_fin_sector"])
    return pct_rank(blend) * 100


def score_v3(df, fs, fin_scope):
    """df: build.score output (all companies). fs: scored fin_sector rows by company_id;
    fin_scope: ids of every in-scope lender / insurer (fresh or not)."""
    df = df.copy()
    fin_mask = df["company_id"].isin(fs.index)
    df["is_fin_sector"] = df["company_id"].isin(fin_scope)
    for c in ("growth", "profitability", "financial_health"):
        df.loc[df["is_fin_sector"], f"score_{c}"] = np.nan
        df.loc[fin_mask, f"score_{c}"] = df.loc[fin_mask, "company_id"].map(fs[f"score_{c}"]).values
    df.loc[df["is_fin_sector"], "score_cash_flow"] = np.nan

    df["market_score"] = df["score_momentum"]
    df["financial_score"] = fin_v1_score(df)
    is_fin = df["is_fin_sector"]

    # penalties
    pen_nonfin = sum(df[f].map(_true).astype(bool) * pts for f, pts in PENALTY_NONFIN.items())
    pen_nonfin = pen_nonfin.where(~df["fin_stale"].astype(bool), 0)
    pen_fin = pd.Series(0.0, index=df.index)
    for f, pts in PENALTY_FIN.items():
        vals = df.loc[fin_mask, "company_id"].map(fs[f]) if f in fs else pd.Series(dtype=object)
        pen_fin.loc[fin_mask] += vals.map(_true).astype(bool).values * pts
    df["penalty"] = np.where(is_fin, pen_fin, pen_nonfin)

    # coverage over applicable components (equal share)
    applicable = [c for c in COMPONENTS]
    avail = pd.DataFrame({c: df[f"score_{c}"].notna() for c in applicable})
    n_app = np.where(is_fin, len(applicable) - 1, len(applicable))
    df["coverage"] = (avail.sum(axis=1) / n_app).round(4)

    mom, news = df["score_momentum"], df["score_news"]
    if ADOPT_FIN_RECIPE:
        from .combiner_eval import FIN_WEIGHTS
        w = FIN_WEIGHTS
        fav = pd.DataFrame({c: df[f"score_{c}"].notna() for c in w})
        fin_base = (sum(df[f"score_{c}"].fillna(0) * w[c] * fav[c] for c in w)
                    / sum(fav[c] * w[c] for c in w).replace(0, np.nan))
    else:
        fin_base = (1 - NEWS_WEIGHT) * mom + NEWS_WEIGHT * news
        if FIN_MARKET_WEIGHT < 1:
            raise SystemExit("FIN_MARKET_WEIGHT < 1 needs a tested financial-sector blend")
    fin_part = df["financial_score"] if MARKET_WEIGHT < 1 else 0.0
    nonfin_base = (1 - NEWS_WEIGHT) * (MARKET_WEIGHT * mom + (1 - MARKET_WEIGHT) * fin_part) + NEWS_WEIGHT * news
    base = np.where(is_fin, fin_base, nonfin_base)

    has_growth = df["score_growth"].notna()
    if MARKET_WEIGHT < 1:
        has_growth &= df["financial_score"].notna() | is_fin
    min_cov = np.where(is_fin, MIN_COVERAGE["financial"], MIN_COVERAGE["non_financial"])
    ranked = mom.notna() & has_growth & (df["coverage"] >= min_cov)
    df["growth_score"] = (pd.Series(base, index=df.index) - df["penalty"]).clip(0, 100).where(ranked).round(2)

    df["growth_label"] = np.select(
        [df["growth_score"].isna(), df["growth_score"] >= 75, df["growth_score"] >= 60, df["growth_score"] >= 40],
        ["Insufficient data", "Strong", "Positive", "Neutral"], default="Weak")
    order = df.sort_values(["growth_score", "symbol"], ascending=[False, True], na_position="last")
    r = order[order["growth_score"].notna()]
    df["rank_overall"] = pd.Series(np.arange(1, len(r) + 1), index=r.index)
    df["rank_in_sector"] = r[r["sector"].notna()].groupby("sector").cumcount() + 1
    df["rank_in_industry"] = r[r["industry"].notna()].groupby("industry").cumcount() + 1
    return df


# ---------------------------------------------------------
# Explanations
# ---------------------------------------------------------

def _fs_get(fsrow, f):
    return _num(fsrow.get(f)) if fsrow is not None else np.nan


def explain_fin(row, fsrow):
    """Bank / NBFC / insurer reasons and risks: (priority, text) lists + red-flag lines."""
    reasons, risks, flags = [], [], []
    if fsrow is None:
        return reasons, risks, flags
    peers = PEER_NAME.get(fsrow.get("peer_group"), "peers")
    v = lambda f: _fs_get(fsrow, f)                    # noqa: E731
    P = lambda f: _fs_get(fsrow, f"p_{f}")             # noqa: E731
    strong = lambda f: _ok(P(f)) and P(f) >= 0.8       # noqa: E731
    weak = lambda f: _ok(P(f)) and P(f) <= 0.2         # noqa: E731

    for f, name, basis in (("ppop_ttm_growth", "Pre-provision operating profit", "TTM vs a year ago"),
                           ("net_profit_yoy", "Net profit", "YoY (latest quarter)"),
                           ("net_profit_ttm_growth", "TTM net profit", "vs a year ago"),
                           ("net_revenue_ttm_growth", "Net revenue", "TTM vs a year ago"),
                           ("nii_ttm_growth", "Net interest income", "TTM vs a year ago"),
                           ("net_revenue_yoy", "Net revenue", "YoY (latest quarter)")):
        x = v(f)
        if not _ok(x):
            continue
        if strong(f) and x > 0:
            reasons.append((P(f), f"{name} up {pct(x)} {basis}"))
        elif weak(f) and x < 0 and x > -1:
            risks.append((1 - P(f), f"{name} down {pct(-x)} {basis}"))
    if _ok(v("net_profit_ttm")) and v("net_profit_ttm") < 0:
        risks.append((0.9, f"Loss-making: TTM net loss {crore(-v('net_profit_ttm'))}"))
    x = v("advances_growth_1y")
    if _ok(x) and x > 0.2:
        reasons.append((0.72, f"Loan book up {pct(x)} in a year"))

    for f, name in (("roe", "ROE"), ("roa", "ROA")):
        x = v(f)
        if _ok(x) and strong(f) and x > 0:
            reasons.append((P(f) - 0.02, f"{name} {pct(x, 1 if f == 'roa' else 0)} (among the best of {peers})"))
        elif _ok(x) and weak(f):
            risks.append((1 - P(f) - 0.05, f"Low {name}: {pct(x, 1 if f == 'roa' else 0)} (bottom of {peers})"))
    x = v("cost_to_income_ttm")
    if _ok(x) and strong("cost_to_income_ttm"):
        reasons.append((P("cost_to_income_ttm") - 0.05, f"Efficient: cost-to-income {pct(x)} (TTM)"))
    elif _ok(x) and weak("cost_to_income_ttm") and x > 0.5:
        risks.append((1 - P("cost_to_income_ttm") - 0.1, f"High cost-to-income: {pct(x)} (TTM)"))

    g, n = v("gross_npa_pct"), v("net_npa_pct")
    if _ok(g) and strong("gross_npa_pct"):
        reasons.append((P("gross_npa_pct") - 0.02, f"Clean loan book: gross NPA {pct(g, 2)}"
                        + (f", net NPA {pct(n, 2)}" if _ok(n) else "")))
    elif _ok(g) and weak("gross_npa_pct") and g > 0.03:
        risks.append((1 - P("gross_npa_pct"), f"High bad loans: gross NPA {pct(g, 1)}"
                      + (f", net NPA {pct(n, 1)}" if _ok(n) else "")))
    x = v("provision_coverage")
    if _ok(x) and strong("provision_coverage") and x > 0.7:
        reasons.append((P("provision_coverage") - 0.1, f"Provision coverage {pct(x)}"))
    x = v("credit_cost")
    if _ok(x) and weak("credit_cost") and x > 0.02:
        risks.append((1 - P("credit_cost") - 0.05, f"High credit cost: provisions {pct(x, 1)} of loans (TTM)"))
    x = v("cet1_ratio")
    if _ok(x) and strong("cet1_ratio") and x > 0.14:
        reasons.append((P("cet1_ratio") - 0.15, f"Well capitalised: CET1 {pct(x, 1)}"))
    x = v("solvency_ratio")
    if _ok(x) and strong("solvency_ratio"):
        reasons.append((P("solvency_ratio") - 0.1, f"Solvency ratio {x:.2f}x"))
    x = v("combined_ratio")
    if _ok(x) and weak("combined_ratio") and x > 1:
        risks.append((1 - P("combined_ratio") - 0.1, f"Combined ratio {pct(x)} (underwriting loss)"))

    if _true(fsrow.get("flag_negative_equity")):
        flags.append("Negative net worth")
    if _true(fsrow.get("flag_capital_near_minimum")):
        c, s = v("cet1_ratio"), v("solvency_ratio")
        flags.append(f"Capital near the regulatory minimum: CET1 {pct(c, 1)}" if _ok(c)
                     else f"Solvency near the regulatory minimum: {s:.2f}x" if _ok(s)
                     else "Capital near the regulatory minimum")
    if _true(fsrow.get("flag_asset_quality_worsening")):
        ch = v("gross_npa_change_1y")
        flags.append(f"Asset quality worsening: gross NPA up {ch * 100:.1f} pts in a year" if _ok(ch) and ch >= 0.005
                     else "Asset quality worsening: provisions rising sharply relative to income")
    if _true(fsrow.get("flag_roa_collapse")):
        risks.append((0.85, "Profitability fell below half of a year ago (ROA / TTM profit)"))
    return reasons, risks, flags


def _market_news_text(row):
    """build.explain's momentum + news part with priorities (row has no fresh features.py data)."""
    r = dict(row)
    r["fin_stale"], r["period_end"] = True, None
    reasons, risks = v2.explain(r)
    # build.explain returns them sorted by priority; keep that order with descending priorities
    return ([(0.84 - 0.02 * i, t) for i, t in enumerate(reasons)],
            [(0.84 - 0.02 * i, t) for i, t in enumerate(risks)])


def explain(row, fsrow):
    if row["is_fin_sector"]:
        fr, fk, flags = explain_fin(row, fsrow)
        mr, mk = _market_news_text(row)
        if fsrow is None and _ok(_num(row.get("last_price"))):
            mk.append((0.3, "Bank / NBFC / insurer financials not available yet"))
        reasons = [t for _, t in sorted(fr + mr, key=lambda x: -x[0])][:5]
        risks = [t for _, t in sorted(fk + mk, key=lambda x: -x[0])]
    else:
        reasons, risks = v2.explain(row)
        k = _n_flag_lines(row)             # build.explain puts its red-flag lines first
        flags, risks = risks[:k], risks[k:]
    # The score is price-trend led: say so first when the trend is clearly strong or weak
    m = _num(row.get("score_momentum"))
    if _ok(m) and m >= MOMENTUM_TEXT_PCT:
        reasons = [f"Price trend stronger than {math.floor(m)}% of listed stocks (market model)"] + reasons
    elif _ok(m) and m <= 100 - MOMENTUM_TEXT_PCT:
        risks = [f"Price trend weaker than {math.floor(100 - m)}% of listed stocks (market model)"] + risks
    tv = _num(row.get("avg_traded_value_3m_cr"))
    if _ok(tv) and tv < THIN_TRADING_CR and not bool(row.get("price_stale", True)):
        risks = risks[:3] + [f"Thinly traded: about Rs {tv * 100:.0f} lakh a day over 3 months"] + risks[3:]
    # build.explain prints "within -0%" for a stock exactly at its 52-week high (left as is for prelim-v2)
    reasons = [t.replace("Trading within -0% of", "Trading at") for t in reasons]
    return reasons[:5], (flags + risks)[:5]


def _n_flag_lines(row):
    """How many red-flag lines build.explain put at the top of the risks (same conditions)."""
    g = row.get
    if not bool(g("fin_stale", True)):
        n = sum(_true(g(f)) for f in ("flag_negative_equity", "flag_debt_to_equity_rising",
                                      "flag_profit_up_ocf_negative", "flag_receivables_outpacing_revenue"))
        return n + int(_true(g("flag_low_interest_coverage")) and _ok(_num(g("interest_coverage_ttm"))))
    pe = g("period_end")
    return int(pe is not None and not pd.isna(pe))


def key_metrics(row, fsrow):
    km = v2.key_metrics(row)
    if not row["is_fin_sector"] or fsrow is None:
        return km
    km["as_of_period"] = f"{pd.Timestamp(fsrow['period_end']):%Y-%m-%d}"
    km["last_filing_date"] = f"{pd.Timestamp(fsrow['filing_date']):%Y-%m-%d}"
    mapping = {"revenue_ttm": "net_revenue_ttm", "net_profit_ttm": "net_profit_ttm",
               "revenue_growth_yoy": "net_revenue_yoy", "profit_growth_yoy": "net_profit_yoy",
               "revenue_ttm_growth": "net_revenue_ttm_growth", "roe": "roe", "roa": "roa", "nim": "nim",
               "cost_to_income_ttm": "cost_to_income_ttm", "gross_npa_pct": "gross_npa_pct",
               "net_npa_pct": "net_npa_pct", "cet1_ratio": "cet1_ratio", "solvency_ratio": "solvency_ratio",
               "advances_growth_1y": "advances_growth_1y", "credit_cost": "credit_cost"}
    for k, src in mapping.items():
        x = _fs_get(fsrow, src)
        if _ok(x):
            km[k] = round(x, 2 if k in ("revenue_ttm", "net_profit_ttm") else 4)
    mc = _num(row.get("market_cap_est"))
    if _ok(mc):
        km["market_cap_est"] = round(mc, 2)
    return km


# ---------------------------------------------------------
# Build
# ---------------------------------------------------------

def load_inputs(conn, snap):
    """Everything build.py loads (SELECT only), plus the financial-sector rows. -> merged df."""
    from financials.features import _load_raw, build_feature_table

    companies = v2.load_companies(conn)
    raw = _load_raw(conn)
    features = build_feature_table(None, raw=raw)
    fin = v2.latest_financials(features, snap)
    shares = v2.shares_outstanding(raw, snap)
    prices, idx = v2.load_prices(conn, companies["company_id"], snap)
    px, idx_ret = v2.price_signals(prices, idx, snap)
    news = v2.news_signals(v2.load_news(conn, snap))
    fs, fin_scope, fs_raw = load_fin_sector(snap, companies["company_id"], conn)
    fs_shares = v2.shares_outstanding(fs_raw, snap) if fs_raw is not None else None
    return dict(companies=companies, fin=fin, shares=shares, px=px, idx_ret=idx_ret, news=news,
                fs=fs, fin_scope=fin_scope, fs_shares=fs_shares)


def merge_inputs(inp, drop_fin_scope):
    """build.build's merge; with drop_fin_scope the features.py rows of in-scope lenders are removed."""
    fin = inp["fin"]
    shares = inp["shares"]
    if drop_fin_scope:
        fin = fin[~fin["company_id"].isin(inp["fin_scope"])]
        if inp["fs_shares"] is not None:
            shares = pd.concat([shares[~shares["company_id"].isin(inp["fin_scope"])],
                                inp["fs_shares"][inp["fs_shares"]["company_id"].isin(inp["fin_scope"])]])
    df = inp["companies"].merge(fin, on="company_id", how="left")
    df = df.merge(inp["px"], on="company_id", how="left").merge(inp["news"], on="company_id", how="left")
    df = df.merge(shares, on="company_id", how="left")
    df["fin_stale"] = df["fin_stale"].astype("boolean").fillna(True)
    df["price_stale"] = df["price_stale"].astype("boolean").fillna(True)
    df["market_cap_est"] = (df["shares_cr"] * df["last_price"]).where(~df["fin_stale"].astype(bool))
    if drop_fin_scope:
        fresh_fs = df["company_id"].isin(inp["fs"].index)
        df.loc[fresh_fs, "market_cap_est"] = (df["shares_cr"] * df["last_price"])[fresh_fs]
    for col in [c for c in df.columns if c.startswith("flag_") or c.endswith("_neg_base")]:
        df[col] = df[col].astype(object).where(df[col].notna(), None)
    return df


def build(conn, snap, inp=None):
    inp = inp or load_inputs(conn, snap)
    df = v2.score(merge_inputs(inp, drop_fin_scope=True))
    df = score_v3(df, inp["fs"], inp["fin_scope"])
    fs = inp["fs"]
    records = df.to_dict("records")
    for r in records:
        fsrow = fs.loc[r["company_id"]].to_dict() if r["company_id"] in fs.index else None
        r["reasons"], r["risks"] = explain(r, fsrow)
        r["key_metrics"] = key_metrics(r, fsrow)
    return df, records, inp["idx_ret"]


def build_prelim_v2(inp):
    """prelim-v2 recomputed from the same inputs (identical to build.build on the same data)."""
    df = v2.score(merge_inputs(inp, drop_fin_scope=False))
    return df


def to_rows(records, snap):
    rows = []
    for r in records:
        rows.append((
            snap, int(r["company_id"]), r["symbol"], MODEL_VERSION, v2._db(r["growth_score"]), r["growth_label"],
            v2._int(r["rank_overall"]), v2._int(r["rank_in_sector"]), v2._int(r["rank_in_industry"]),
            round(float(r["coverage"]), 2),
            *[v2._db(r[f"score_{c}"]) for c in COMPONENTS],
            json.dumps(r["reasons"]) if r["reasons"] else None,
            json.dumps(r["risks"]) if r["risks"] else None,
            json.dumps(r["key_metrics"]),
        ))
    return rows


OUT_COLUMNS = ["snapshot_date", "company_id", "symbol", "name", "sector", "industry", "model_version",
               "growth_score", "growth_label", "rank_overall", "rank_in_sector", "rank_in_industry", "coverage",
               *[f"score_{c}" for c in COMPONENTS], "market_score", "financial_score", "penalty",
               "is_fin_sector", "peer_group", "reasons", "risks", "key_metrics"]


def to_frame(df, records, snap, fs):
    out = pd.DataFrame(records)
    out["snapshot_date"] = str(snap)
    out["model_version"] = MODEL_VERSION
    out["peer_group"] = out["company_id"].map(fs["peer_group"]) if "peer_group" in fs else None
    for c in ("reasons", "risks", "key_metrics"):
        out[c] = out[c].map(json.dumps)
    num = ["growth_score", "coverage", *[f"score_{c}" for c in COMPONENTS], "market_score", "financial_score"]
    out[num] = out[num].astype(float).round(2)
    for c in ("rank_overall", "rank_in_sector", "rank_in_industry"):
        out[c] = out[c].astype("Int64")
    return out[OUT_COLUMNS].sort_values(["rank_overall", "symbol"], na_position="last")


def main(argv=None):
    parser = argparse.ArgumentParser(description="Build the InvestIQ combiner (investiq-v1) ranking snapshot.")
    parser.add_argument("--date", help="snapshot date YYYY-MM-DD (default: today)")
    parser.add_argument("--out", help="dry-run CSV path (default ml/data/processed/rankings_investiq_v1_<date>.csv)")
    parser.add_argument("--compare", action="store_true", help="also write prelim-v2 from the same inputs")
    parser.add_argument("--symbols", nargs="*", help="print these symbols")
    parser.add_argument("--publish", action="store_true",
                        help="WRITE the snapshot to company_rankings (replaces that date's rows). Needs approval.")
    args = parser.parse_args(argv)

    warnings.filterwarnings("ignore")
    from growth_model.prices import CACHE_DIR
    from news_pipeline.db import get_connection

    snap = datetime.strptime(args.date, "%Y-%m-%d").date() if args.date else date.today()
    symbols = [s.strip().upper() for s in args.symbols] if args.symbols else None
    conn = get_connection()
    try:
        inp = load_inputs(conn, snap)
        df, records, idx_ret = build(conn, snap, inp)
        print(f"snapshot {snap}  model {MODEL_VERSION}  benchmark 1y return: {idx_ret['return_1y']:.1%}")
        ranked = df["growth_score"].notna()
        print(f"companies: {len(df)}   ranked: {ranked.sum()}   unranked: {(~ranked).sum()}")
        print("labels:", df["growth_label"].value_counts().to_dict())
        if args.publish:
            v2.write(conn, to_rows(records, snap), snap)
            print(f"\nwrote {len(records)} rows to company_rankings for {snap} ({MODEL_VERSION})")
            return
        out = to_frame(df, records, snap, inp["fs"])
        path = args.out or str(CACHE_DIR / f"rankings_investiq_v1_{snap}.csv")
        out.to_csv(path, index=False)
        meta = {"snapshot_date": str(snap), "model_version": MODEL_VERSION, "ranked": int(ranked.sum()),
                "unranked": int((~ranked).sum()), "method": METHOD_TEXT,
                "labels": df["growth_label"].value_counts().to_dict(),
                "market_weight": MARKET_WEIGHT, "news_weight": NEWS_WEIGHT,
                "fin_sector_recipe_adopted": ADOPT_FIN_RECIPE,
                "penalties": {"non_financial": PENALTY_NONFIN, "financial_sector": PENALTY_FIN}}
        with open(path.rsplit(".", 1)[0] + ".json", "w") as fh:
            json.dump(meta, fh, indent=2)
        print(f"dry run: {len(out)} rows -> {path} (+ .json); nothing written to the DB")
        if args.compare:
            old = build_prelim_v2(inp)
            cols = ["company_id", "symbol", "sector", "growth_score", "growth_label", "rank_overall", "coverage",
                    *[f"score_{c}" for c in COMPONENTS]]
            cpath = str(CACHE_DIR / f"rankings_prelim_v2_{snap}.csv")
            old[cols].to_csv(cpath, index=False)
            print(f"prelim-v2 from the same inputs -> {cpath}")
        if symbols:
            by = {r["symbol"]: r for r in records}
            for s in symbols:
                r = by.get(s)
                if r:
                    print(f"\n{s}: score={r['growth_score']} label={r['growth_label']} rank={r['rank_overall']}"
                          f"\n  reasons={r['reasons']}\n  risks={r['risks']}\n  key_metrics={r['key_metrics']}")
    finally:
        conn.close()


if __name__ == "__main__":
    main()
