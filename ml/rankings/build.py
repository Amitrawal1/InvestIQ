"""Preliminary growth ranking (`model_version = 'prelim-v2'`) -> `company_rankings`.

One snapshot per run for every EQ/BE company (contract: docs/company-rankings.md). Rebuilt on the
1st and 16th of each month by .github/workflows/rankings.yml; rows for the snapshot date are replaced.

Method
------
1. Inputs (all point-in-time as of the snapshot date D):
   - financials: the latest `financials.features` row per company with filing_date <= D (latest
     period_end, then latest filing). If that period ended more than 275 days (~9 months) before D
     the financials are stale and every financial component is NULL. Banks/NBFCs/insurers have no
     feature rows (features.py skips them), so they only get momentum/news -> 'Insufficient data'.
   - prices: the last ~400 calendar days of `stock_prices` (one query per chunk of company ids) and
     NIFTY SMALLCAP 250 from `index_prices`. Momentum is NULL if the last close is >10 days old.
   - news: 90 days before D, non-duplicate, sentiment-scored rows of `news`.

2. Each sub-feature is turned into a cross-sectional percentile (0-1, flipped where lower is
   better) among companies that have it. Percentiles are rank-based, so outliers are bounded
   (equivalent to winsorising); NaN is never treated as 0 - a missing sub-feature is skipped.
   A component's raw value is the weighted mean of its available sub-feature percentiles (it needs
   a minimum number of them), and the component score is that raw value's percentile x 100:
     growth            revenue & net-profit YoY (latest quarter) and TTM growth; YoY acceleration (x0.5)
     profitability     ROCE, ROE, TTM operating margin; op/net margin change YoY (x0.5)
     financial_health  low debt/equity, current ratio, interest coverage (debt-free counts as best),
                       low rise in debt/equity over a year (x0.5)
     cash_flow         cash conversion (OCF / net profit, only when profit > 0), FCF margin
                       (FCF TTM / revenue TTM), low accruals ratio
     momentum          the market model's six trend signals, equal weight (growth_model/market_model.py,
                       walk-forward tested 2019-2026): distance from 52-week high, close vs 200-day
                       average, 50-day vs 200-day average, 3m and 6m return minus NIFTY SMALLCAP 250,
                       share of down days over 3 months (fewer = better). Low volatility was dropped
                       (v1): it helped in some years and hurt in others. Price signals are NULL when the
                       last year contains a price-series break (one-day move > +100% / < -60%).
     news              sum over items of sign x confidence x importance weight (HIGH 2, MEDIUM 1,
                       LOW 0.5; neutral = 0) / (total weight + 3), plus 0.1 x (HIGH positive - HIGH
                       negative); centred on 50: net-positive companies get 50 + 50 x their
                       percentile among net-positive ones, net-negative 50 x their percentile among
                       net-negative ones; no news or neutral-only news -> 50.

3. growth_score = weighted mean of the available components (growth 0.30, profitability 0.20,
   financial_health 0.15, cash_flow 0.15, momentum 0.15, news 0.05; weights renormalised over the
   available ones) minus 3 points per red flag from features.py (profit up while OCF negative,
   receivables outpacing revenue, debt/equity rising, low interest coverage; negative equity costs
   6), clipped to 0-100. coverage = available weight share. coverage < 0.5, no financial
   component or no growth component -> growth_score NULL, 'Insufficient data', unranked.
   Labels: >= 75 Strong, >= 60 Positive, >= 40 Neutral, else Weak.

4. Ranks (1 = best) overall, within sector and within industry, among ranked companies only.
   reasons / risks: up to 5 each, from the strongest (percentile >= 0.8) and weakest (<= 0.2)
   sub-features with their actual values; red flags always come first among the risks.

CLI:  python3 -m rankings.build [--date YYYY-MM-DD] [--dry-run] [--symbols KAYNES DIXON]
      (--symbols still scores the whole universe, but only writes/prints those companies)
"""

import argparse
import json
import math
import warnings
from datetime import date, datetime, timedelta

import numpy as np
import pandas as pd

MODEL_VERSION = "prelim-v2"
SERIES = ("EQ", "BE")
BENCHMARK = "NIFTY SMALLCAP 250"

WEIGHTS = {
    "growth": 0.30, "profitability": 0.20, "financial_health": 0.15,
    "cash_flow": 0.15, "momentum": 0.15, "news": 0.05,
}
FINANCIAL_COMPONENTS = ("growth", "profitability", "financial_health", "cash_flow")
MIN_COVERAGE = 0.5

STALE_FINANCIALS_DAYS = 275
STALE_PRICE_DAYS = 10
PRICE_LOOKBACK_DAYS = 400
BREAK_UP, BREAK_DOWN = 1.0, -0.6     # same series-break rule as growth_model/labels.py
NEWS_DAYS = 90

FLAG_PENALTY = {
    "flag_profit_up_ocf_negative": 3, "flag_receivables_outpacing_revenue": 3,
    "flag_debt_to_equity_rising": 3, "flag_low_interest_coverage": 3, "flag_negative_equity": 6,
}

# component -> [(feature, weight, higher_is_better)], minimum sub-features needed
SUBFEATURES = {
    "growth": ([
        ("revenue_yoy", 1, True), ("net_profit_yoy", 1, True),
        ("revenue_ttm_growth", 1, True), ("net_profit_ttm_growth", 1, True),
        ("revenue_yoy_accel", 0.5, True), ("net_profit_yoy_accel", 0.5, True),
    ], 2),
    "profitability": ([
        ("roce", 1, True), ("roe", 1, True), ("op_margin_ttm", 1, True),
        ("op_margin_change_yoy", 0.5, True), ("net_margin_change_yoy", 0.5, True),
    ], 2),
    "financial_health": ([
        ("debt_to_equity", 1, False), ("current_ratio", 1, True),
        ("coverage_rank_input", 1, True), ("debt_to_equity_change_1y", 0.5, False),
    ], 2),
    "cash_flow": ([
        ("cash_conversion", 1, True), ("fcf_margin", 1, True), ("accruals_ratio", 1, False),
    ], 1),
    "momentum": ([
        ("dist_52w_high", 1, True), ("ma200_gap", 1, True), ("ma50_over_200", 1, True),
        ("rel_return_6m", 1, True), ("rel_return_3m", 1, True), ("down_days_3m", 1, False),
    ], 3),
}

NEWS_IMPORTANCE_WEIGHT = {"HIGH": 2.0, "MEDIUM": 1.0, "LOW": 0.5}
NEWS_PRIOR_WEIGHT = 3.0


# ---------------------------------------------------------
# Helpers
# ---------------------------------------------------------

def _num(x):
    """float or NaN (handles None / pd.NA / Decimal)."""
    try:
        if x is None or x is pd.NA:
            return np.nan
        return float(x)
    except (TypeError, ValueError):
        return np.nan


def _true(x):
    """Nullable boolean -> strictly True only for a real True."""
    return x is not None and x is not pd.NA and not (isinstance(x, float) and math.isnan(x)) and bool(x)


def _ok(x):
    return x is not None and not (isinstance(x, float) and math.isnan(x))


def pct_rank(s):
    """Percentile 0-1 among non-null values (0 = worst, 1 = best); NaN stays NaN."""
    s = pd.to_numeric(s, errors="coerce")
    n = s.notna().sum()
    if n == 0:
        return s * np.nan
    if n == 1:
        return s.where(s.isna(), 0.5)
    return (s.rank(method="average") - 1) / (n - 1)


def pct(x, digits=0):
    return f"{x * 100:.{digits}f}%"


def top_share(p):
    """Percentile 0-1 -> 'top 10%' style bucket."""
    t = (1 - p) * 100
    if t <= 1:
        return "top 1%"
    return f"top {min(50, int(math.ceil(t / 5) * 5))}%"


def crore(x):
    if abs(x) >= 1000:
        return f"Rs {x:,.0f} cr"
    return f"Rs {x:,.1f} cr"


# ---------------------------------------------------------
# Loading
# ---------------------------------------------------------

def load_companies(conn):
    sql = f"""
        SELECT c.id AS company_id, c.symbol, c.name, c.series,
               s.name AS sector, s.slug AS sector_slug,
               COALESCE(i.name, c.industry) AS industry
        FROM companies c
        LEFT JOIN sectors s ON s.id = c.sector_id
        LEFT JOIN industries i ON i.id = c.industry_id
        WHERE c.series IN ({", ".join(["%s"] * len(SERIES))})
    """
    cur = conn.cursor()
    cur.execute(sql, SERIES)
    cols = [d[0] for d in cur.description]
    df = pd.DataFrame(cur.fetchall(), columns=cols)
    cur.close()
    return df


def load_prices(conn, company_ids, snap):
    start = snap - timedelta(days=PRICE_LOOKBACK_DAYS)
    rows = []
    cur = conn.cursor()
    ids = sorted(int(i) for i in company_ids)
    for k in range(0, len(ids), 600):
        chunk = ids[k:k + 600]
        cur.execute(
            f"SELECT company_id, price_date, close_price, volume FROM stock_prices "
            f"WHERE company_id IN ({', '.join(['%s'] * len(chunk))}) AND price_date BETWEEN %s AND %s",
            [*chunk, start, snap],
        )
        rows.extend(cur.fetchall())
    cur.execute(
        "SELECT price_date, close_price FROM index_prices WHERE index_name = %s AND price_date BETWEEN %s AND %s",
        (BENCHMARK, start, snap),
    )
    idx = pd.DataFrame(cur.fetchall(), columns=["price_date", "close"])
    cur.close()

    prices = pd.DataFrame(rows, columns=["company_id", "price_date", "close", "volume"])
    prices["price_date"] = pd.to_datetime(prices["price_date"])
    prices["close"] = pd.to_numeric(prices["close"], errors="coerce").astype(float)
    prices["volume"] = pd.to_numeric(prices["volume"], errors="coerce").astype(float)
    prices = prices[prices["close"] > 0].sort_values(["company_id", "price_date"])
    idx["price_date"] = pd.to_datetime(idx["price_date"])
    idx["close"] = pd.to_numeric(idx["close"], errors="coerce").astype(float)
    return prices, idx.dropna().sort_values("price_date")


def load_news(conn, snap):
    cur = conn.cursor()
    cur.execute(
        """
        SELECT company_id, sentiment, sentiment_confidence, importance FROM news
        WHERE published_at >= %s AND published_at < %s
          AND is_duplicate = 0 AND company_id IS NOT NULL AND sentiment IS NOT NULL
        """,
        (snap - timedelta(days=NEWS_DAYS), snap + timedelta(days=1)),
    )
    df = pd.DataFrame(cur.fetchall(), columns=["company_id", "sentiment", "confidence", "importance"])
    cur.close()
    df["confidence"] = pd.to_numeric(df["confidence"], errors="coerce").fillna(0.5).astype(float)
    return df


# ---------------------------------------------------------
# Signals
# ---------------------------------------------------------

def _close_asof(dates, closes, target, tolerance_days=10):
    """Last close on or before target (within tolerance), else NaN."""
    i = np.searchsorted(dates, np.datetime64(target), side="right") - 1
    if i < 0 or (np.datetime64(target) - dates[i]) > np.timedelta64(tolerance_days, "D"):
        return np.nan
    return closes[i]


def price_signals(prices, idx, snap):
    snap_ts = pd.Timestamp(snap)
    horizons = {"return_1m": 30, "return_3m": 91, "return_6m": 182, "return_1y": 365}

    idx_dates, idx_close = idx["price_date"].values, idx["close"].values
    idx_last = _close_asof(idx_dates, idx_close, snap_ts)
    idx_ret = {k: idx_last / _close_asof(idx_dates, idx_close, snap_ts - pd.Timedelta(days=d)) - 1
               for k, d in horizons.items()}

    out = []
    for cid, g in prices.groupby("company_id", sort=False):
        dates, closes = g["price_date"].values, g["close"].values
        last_date = pd.Timestamp(dates[-1])
        rec = {"company_id": cid, "last_price": closes[-1], "price_date": last_date}
        tail = g.tail(63)
        rec["avg_traded_value_3m_cr"] = float((tail["close"] * tail["volume"]).mean() / 1e7)
        if (snap_ts - last_date).days > STALE_PRICE_DAYS:
            rec["price_stale"] = True
            out.append(rec)
            continue
        rec["price_stale"] = False
        last = closes[-1]
        for k, d in horizons.items():
            rec[k] = last / _close_asof(dates, closes, snap_ts - pd.Timedelta(days=d)) - 1
        rec["rel_return_3m"] = rec["return_3m"] - idx_ret["return_3m"]
        rec["rel_return_6m"] = rec["return_6m"] - idx_ret["return_6m"]
        rec["rel_return_1y"] = rec["return_1y"] - idx_ret["return_1y"]
        rec["return_1y_vs_smallcap"] = rec["rel_return_1y"]
        year = g[g["price_date"] > snap_ts - pd.Timedelta(days=365)]
        if len(year) >= 120:
            rec["high_52w"] = year["close"].max()
            rec["dist_52w_high"] = last / rec["high_52w"] - 1
            logret = np.diff(np.log(year["close"].values))
            rec["volatility_1y"] = float(np.std(logret, ddof=1) * np.sqrt(252))
            step = np.diff(year["close"].values) / year["close"].values[:-1]
            if ((step > BREAK_UP) | (step < BREAK_DOWN)).any():
                rec["price_break"] = True
        if len(closes) >= 200:
            ma50, ma200 = closes[-50:].mean(), closes[-200:].mean()
            rec["ma200_gap"] = last / ma200 - 1
            rec["ma50_over_200"] = ma50 / ma200 - 1
        q = np.diff(closes[-64:])
        if len(q) >= 40:
            rec["down_days_3m"] = float((q < 0).mean())
        if rec.get("price_break"):
            for k in ("dist_52w_high", "ma200_gap", "ma50_over_200", "rel_return_3m", "rel_return_6m",
                      "rel_return_1y", "return_1y_vs_smallcap", "down_days_3m", "volatility_1y",
                      *horizons):
                rec[k] = np.nan
        out.append(rec)
    return pd.DataFrame(out), idx_ret


def news_signals(news):
    if news.empty:
        return pd.DataFrame(columns=["company_id", "news_count_90d", "news_sentiment_90d", "news_raw",
                                     "news_high_pos", "news_high_neg"])
    sign = news["sentiment"].map({"POSITIVE": 1.0, "NEGATIVE": -1.0}).fillna(0.0)
    w = news["importance"].map(NEWS_IMPORTANCE_WEIGHT).fillna(1.0)
    news = news.assign(s=sign * news["confidence"], sw=sign * news["confidence"] * w, w=w,
                       hp=(news["importance"] == "HIGH") & (sign > 0),
                       hn=(news["importance"] == "HIGH") & (sign < 0))
    g = news.groupby("company_id")
    df = pd.DataFrame({
        "news_count_90d": g.size(),
        "news_sentiment_90d": g["s"].mean(),
        "news_high_pos": g["hp"].sum(),
        "news_high_neg": g["hn"].sum(),
        "_sw": g["sw"].sum(), "_w": g["w"].sum(),
    })
    df["news_raw"] = df["_sw"] / (df["_w"] + NEWS_PRIOR_WEIGHT) + 0.1 * (df["news_high_pos"] - df["news_high_neg"])
    return df.drop(columns=["_sw", "_w"]).reset_index()


def latest_financials(features, snap):
    snap_ts = pd.Timestamp(snap)
    f = features[(features["filing_date"] <= snap_ts) & features["company_id"].notna()].copy()
    f["company_id"] = f["company_id"].astype(int)
    f = f.sort_values(["company_id", "period_end", "filing_date"]).drop_duplicates("company_id", keep="last")
    f["fin_stale"] = (snap_ts - f["period_end"]).dt.days > STALE_FINANCIALS_DAYS
    return f.drop(columns=["symbol"])


def shares_outstanding(raw, snap):
    """Crore shares from the latest visible quarter: net profit (owners) / basic EPS."""
    from financials.features import _pick_one

    r = raw[(raw["filing_date"] <= pd.Timestamp(snap)) & (raw["months"] == 3) & raw["company_id"].notna()]
    r = _pick_one(r)
    r = r.sort_values(["company_id", "period_end"]).drop_duplicates("company_id", keep="last")
    profit = r["inc_net_profit_owners"].fillna(r["inc_net_profit"])
    eps = r["inc_eps_basic"]
    sensible = (eps.abs() >= 0.05) & (profit.abs() >= 0.5) & (np.sign(eps) == np.sign(profit))
    shares = (profit / eps).where(sensible)
    shares = shares.where((shares > 0.01) & (shares < 5000))     # 1 lakh .. 50,000 crore shares
    return pd.DataFrame({"company_id": r["company_id"].astype(int).values, "shares_cr": shares.values})


# ---------------------------------------------------------
# Scoring
# ---------------------------------------------------------

def score(df):
    """Adds sub-feature percentiles (p_*), component scores (score_*), growth_score, label, ranks."""
    fin = ~df["fin_stale"].fillna(True).astype(bool)

    # Derived inputs (NaN where meaningless, never 0)
    df["fcf_margin"] = df["fcf_ttm"] / df["revenue_ttm"].where(df["revenue_ttm"] > 1)
    df["cash_conversion"] = df["cash_conversion"].where(df["net_profit_ttm"] > 0)
    df["roe"] = df["roe"].where(~df["flag_negative_equity"].map(_true).astype(bool))
    debt_free = df["debt_to_equity"] < 0.05
    cov = df["interest_coverage_ttm"].clip(upper=100)
    df["coverage_rank_input"] = cov.where(cov.notna(), np.where(debt_free, 1e9, np.nan))

    fin_features = {f for c in FINANCIAL_COMPONENTS for f, _, _ in SUBFEATURES[c][0]}
    for comp, (subs, min_n) in SUBFEATURES.items():
        num = pd.Series(0.0, index=df.index)
        den = pd.Series(0.0, index=df.index)
        cnt = pd.Series(0, index=df.index)
        for feat, w, higher in subs:
            vals = df[feat].where(fin) if feat in fin_features else df[feat]
            p = pct_rank(vals)
            if not higher:
                p = 1 - p
            df[f"p_{feat}"] = p
            has = p.notna()
            num += p.fillna(0) * w * has
            den += w * has
            cnt += has.astype(int)
        raw = (num / den.replace(0, np.nan)).where(cnt >= min_n)
        df[f"score_{comp}"] = pct_rank(raw) * 100

    # News is centred on 50 = neutral: net-positive companies spread over 50-100 by their percentile
    # among net-positive ones, net-negative over 0-50; no news or exactly neutral news -> 50.
    nr = df["news_raw"]
    pos, neg = nr.where(nr > 0), nr.where(nr < 0)
    df["p_news_raw"] = pct_rank(nr)
    df["score_news"] = (50 + 50 * pct_rank(pos)).fillna(50 * pct_rank(neg)).fillna(50.0)

    comps = list(WEIGHTS)
    avail = pd.DataFrame({c: df[f"score_{c}"].notna() for c in comps})
    wsum = sum(avail[c] * WEIGHTS[c] for c in comps)
    wscore = sum(df[f"score_{c}"].fillna(0) * WEIGHTS[c] * avail[c] for c in comps)
    df["coverage"] = (wsum / sum(WEIGHTS.values())).round(4)
    penalty = sum(df[f].map(_true).astype(bool) * pts for f, pts in FLAG_PENALTY.items())
    df["penalty"] = penalty.where(fin, 0)
    base = wscore / wsum.replace(0, np.nan)
    has_fin = avail[list(FINANCIAL_COMPONENTS)].any(axis=1)
    # A growth-potential rank needs an actual growth reading, not just margins or momentum
    ranked = has_fin & avail["growth"] & (df["coverage"] >= MIN_COVERAGE)
    df["growth_score"] = (base - df["penalty"]).clip(0, 100).where(ranked).round(2)

    df["growth_label"] = np.select(
        [df["growth_score"].isna(), df["growth_score"] >= 75, df["growth_score"] >= 60, df["growth_score"] >= 40],
        ["Insufficient data", "Strong", "Positive", "Neutral"], default="Weak")

    # Ties broken by symbol so ranks are deterministic
    order = df.sort_values(["growth_score", "symbol"], ascending=[False, True], na_position="last")
    r = order[order["growth_score"].notna()]
    df["rank_overall"] = pd.Series(np.arange(1, len(r) + 1), index=r.index)
    df["rank_in_sector"] = r[r["sector"].notna()].groupby("sector").cumcount() + 1
    df["rank_in_industry"] = r[r["industry"].notna()].groupby("industry").cumcount() + 1
    return df


# ---------------------------------------------------------
# Explanations
# ---------------------------------------------------------

def explain(row):
    fresh = not bool(row.get("fin_stale", True))
    reasons, risks, flags = [], [], []    # (priority, text)
    g = row.get
    P = lambda f: _num(g(f"p_{f}"))  # noqa: E731

    def strong(f):
        p = P(f)
        return _ok(p) and p >= 0.8

    def weak(f):
        p = P(f)
        return _ok(p) and p <= 0.2

    def v(f):
        return _num(g(f))

    if fresh:
        # growth
        for f, name, basis in (("revenue_yoy", "Revenue", "YoY (latest quarter)"),
                               ("net_profit_yoy", "Net profit", "YoY (latest quarter)"),
                               ("revenue_ttm_growth", "TTM revenue", "vs a year ago"),
                               ("net_profit_ttm_growth", "TTM net profit", "vs a year ago")):
            x = v(f)
            if not _ok(x):
                continue
            if strong(f) and x > 0:
                reasons.append((P(f), f"{name} up {pct(x)} {basis}"))
            elif weak(f) and x <= -1:     # profit swung from positive to a loss
                if f == "net_profit_yoy":
                    risks.append((1 - P(f), "Latest quarter swung to a net loss (profit a year ago)"))
                # TTM swing is covered by the 'Loss-making' risk below
            elif weak(f) and x < 0:
                risks.append((1 - P(f), f"{name} down {pct(-x)} {basis}"))
        if _true(g("net_profit_neg_base")) and v("net_profit_ttm") > 0 and not _ok(v("net_profit_ttm_growth")):
            reasons.append((0.85, f"Turned profitable: TTM net profit {crore(v('net_profit_ttm'))}"))
        if _ok(v("net_profit_ttm")) and v("net_profit_ttm") < 0:
            risks.append((0.9, f"Loss-making: TTM net loss {crore(-v('net_profit_ttm'))}"))
        x = v("revenue_yoy_accel")
        if strong("revenue_yoy_accel") and x > 0.05:
            reasons.append((P("revenue_yoy_accel") - 0.1, f"Revenue growth accelerating (+{x * 100:.0f} pts vs previous quarter)"))

        # profitability
        for f, name in (("roce", "ROCE"), ("roe", "ROE")):
            x = v(f)
            if _ok(x) and strong(f) and x > 0.12:
                reasons.append((P(f), f"{name} {pct(x)} ({top_share(P(f))} of companies)"))
            elif _ok(x) and weak(f) and x < 0.08:
                risks.append((1 - P(f), f"Low {name}: {pct(x)}"))
        x = v("op_margin_ttm")
        if _ok(x) and strong("op_margin_ttm") and x > 0:
            reasons.append((P("op_margin_ttm") - 0.05, f"Operating margin {pct(x)} (TTM)"))
        x = v("op_margin_change_yoy")
        if _ok(x) and strong("op_margin_change_yoy") and x > 0.01:
            reasons.append((P("op_margin_change_yoy") - 0.1, f"Operating margin up {x * 100:.1f} pts YoY"))
        elif _ok(x) and weak("op_margin_change_yoy") and x < -0.01:
            risks.append((1 - P("op_margin_change_yoy") - 0.1, f"Operating margin down {-x * 100:.1f} pts YoY"))

        # financial health
        de = v("debt_to_equity")
        if _ok(de) and de < 0.05:
            reasons.append((0.8, "Virtually debt-free" if de < 0.01 else f"Very low debt: debt/equity {de:.2f}"))
        elif _ok(de) and weak("debt_to_equity") and de > 1:
            risks.append((1 - P("debt_to_equity"), f"High leverage: debt/equity {de:.1f}"))
        cr = v("current_ratio")
        if _ok(cr) and weak("current_ratio") and cr < 1:
            risks.append((1 - P("current_ratio") - 0.1, f"Current ratio {cr:.2f} (current liabilities exceed current assets)"))
        ic = v("interest_coverage_ttm")
        if _ok(ic) and strong("coverage_rank_input") and ic > 10 and not (_ok(de) and de < 0.05):
            reasons.append((P("coverage_rank_input") - 0.1, f"Interest coverage {ic:.0f}x"))

        # cash flow
        cc = v("cash_conversion")
        if _ok(cc) and strong("cash_conversion") and cc > 1:
            reasons.append((P("cash_conversion") - 0.05, f"Operating cash flow {cc:.1f}x net profit (TTM)"))
        fcf = v("fcf_ttm")
        if _ok(fcf) and strong("fcf_margin") and fcf > 0:
            reasons.append((P("fcf_margin") - 0.05, f"Free cash flow {crore(fcf)} TTM ({pct(v('fcf_margin'))} of revenue)"))
        elif _ok(fcf) and weak("fcf_margin") and fcf < 0:
            risks.append((1 - P("fcf_margin") - 0.05, f"Negative free cash flow: {crore(fcf)} TTM"))

        # red flags (features.py)
        if _true(g("flag_negative_equity")):
            flags.append("Negative shareholder equity")
        if _true(g("flag_debt_to_equity_rising")):
            ch = v("debt_to_equity_change_1y")
            flags.append(f"Debt/equity rose from {de - ch:.1f} to {de:.1f} in a year" if _ok(de) and _ok(ch)
                         else "Debt/equity rising sharply")
        if _true(g("flag_profit_up_ocf_negative")):
            flags.append("Profit rising but operating cash flow negative in both recent half-years")
        if _true(g("flag_receivables_outpacing_revenue")):
            gap = v("receivables_minus_revenue_growth")
            flags.append(f"Receivables growing {gap * 100:.0f} pts faster than revenue" if _ok(gap)
                         else "Receivables outpacing revenue")
        if _true(g("flag_low_interest_coverage")) and _ok(ic):
            flags.append(f"Low interest coverage: {ic:.1f}x" if ic >= 0 else "Operating profit does not cover interest")
    elif _ok(g("period_end")) and g("period_end") is not None and not pd.isna(g("period_end")):
        flags.append(f"Latest financials are for {pd.Timestamp(g('period_end')):%b %Y} (stale)")

    # momentum
    if not bool(g("price_stale", True)):
        r6, rel = v("return_6m"), v("rel_return_6m")
        if _ok(r6) and _ok(rel) and strong("rel_return_6m") and r6 > 0:
            reasons.append((P("rel_return_6m") - 0.05,
                            f"Stock up {pct(r6)} in 6 months, {rel * 100:.0f} pts ahead of Smallcap 250"))
        elif _ok(r6) and _ok(rel) and weak("rel_return_6m") and rel < 0:
            risks.append((1 - P("rel_return_6m") - 0.05,
                          f"Stock {'down ' + pct(-r6) if r6 < 0 else 'up only ' + pct(r6)} in 6 months, "
                          f"{-rel * 100:.0f} pts behind Smallcap 250"))
        gap, cross = v("ma200_gap"), v("ma50_over_200")
        if _ok(gap) and _ok(cross) and gap > 0 and cross > 0 and strong("ma200_gap"):
            reasons.append((0.7, f"In an uptrend: {gap * 100:.0f}% above its 200-day average"))
        elif _ok(gap) and _ok(cross) and gap < 0 and cross < 0 and weak("ma200_gap"):
            risks.append((0.7, f"In a downtrend: {-gap * 100:.0f}% below its 200-day average"))
        d = v("dist_52w_high")
        if _ok(d) and d > -0.05:
            reasons.append((0.75, f"Trading within {max(-d * 100, 0):.0f}% of its 52-week high"))
        elif _ok(d) and d < -0.4:
            risks.append((0.75, f"{-d * 100:.0f}% below its 52-week high"))
        vol = v("volatility_1y")
        if _ok(vol) and vol > 0.6:
            risks.append((0.6, f"Highly volatile: {pct(vol)} annualised volatility"))
    elif _ok(v("last_price")):
        risks.append((0.5, "No recent trading data"))
    if g("price_break") is True:
        risks.append((0.55, "Price history has a gap or unadjusted corporate action; trend signals skipped"))

    # news
    n = v("news_count_90d")
    if _ok(n) and n > 0:
        hp, hn = int(v("news_high_pos") or 0), int(v("news_high_neg") or 0)
        if strong("news_raw") and v("news_raw") > 0:
            extra = f", {hp} high-importance positive" if hp else ""
            reasons.append((P("news_raw") - 0.2, f"Positive news flow: {int(n)} announcements in 90 days{extra}"))
        if hn >= 2 and hn > hp:
            risks.append((0.7, f"{hn} high-importance negative announcements in 90 days"))

    reasons = [t for _, t in sorted(reasons, key=lambda x: -x[0])][:5]
    risks = (flags + [t for _, t in sorted(risks, key=lambda x: -x[0])])[:5]
    return reasons, risks


def key_metrics(row):
    g = row.get
    km = {}
    if g("period_end") is not None and not pd.isna(g("period_end")):
        km["as_of_period"] = f"{pd.Timestamp(g('period_end')):%Y-%m-%d}"
        km["last_filing_date"] = f"{pd.Timestamp(g('filing_date')):%Y-%m-%d}"
    fresh = not bool(g("fin_stale", True))
    money = ["revenue_ttm", "net_profit_ttm", "ocf_ttm", "fcf_ttm", "market_cap_est", "last_price",
             "avg_traded_value_3m_cr"]
    ratios = ["revenue_growth_yoy", "profit_growth_yoy", "revenue_ttm_growth", "op_margin_ttm", "net_margin_ttm",
              "roe", "roce", "debt_to_equity", "current_ratio", "return_1m", "return_3m", "return_6m", "return_1y",
              "return_1y_vs_smallcap", "volatility_1y", "news_sentiment_90d"]
    src = {"revenue_growth_yoy": "revenue_yoy", "profit_growth_yoy": "net_profit_yoy"}
    fin_keys = {"revenue_ttm", "net_profit_ttm", "ocf_ttm", "fcf_ttm", "revenue_growth_yoy", "profit_growth_yoy",
                "revenue_ttm_growth", "op_margin_ttm", "net_margin_ttm", "roe", "roce", "debt_to_equity",
                "current_ratio"}
    for k in money + ratios:
        if k in fin_keys and not fresh:
            continue
        x = _num(g(src.get(k, k)))
        if _ok(x):
            km[k] = round(x, 2 if k in money else 4)
    if g("price_date") is not None and not pd.isna(g("price_date")):
        km["price_date"] = f"{pd.Timestamp(g('price_date')):%Y-%m-%d}"
    km["news_count_90d"] = int(_num(g("news_count_90d"))) if _ok(_num(g("news_count_90d"))) else 0
    return km


# ---------------------------------------------------------
# Build / write
# ---------------------------------------------------------

def build(conn, snap):
    from financials.features import _load_raw, build_feature_table

    companies = load_companies(conn)
    raw = _load_raw(conn)
    features = build_feature_table(None, raw=raw)
    fin = latest_financials(features, snap)
    shares = shares_outstanding(raw, snap)
    prices, idx = load_prices(conn, companies["company_id"], snap)
    px, idx_ret = price_signals(prices, idx, snap)
    news = news_signals(load_news(conn, snap))

    df = companies.merge(fin, on="company_id", how="left")
    df = df.merge(px, on="company_id", how="left").merge(news, on="company_id", how="left")
    df = df.merge(shares, on="company_id", how="left")
    df["fin_stale"] = df["fin_stale"].astype("boolean").fillna(True)
    df["price_stale"] = df["price_stale"].astype("boolean").fillna(True)
    # market cap only when the share count comes from fresh financials
    df["market_cap_est"] = (df["shares_cr"] * df["last_price"]).where(~df["fin_stale"].astype(bool))
    for col in [c for c in df.columns if c.startswith("flag_") or c.endswith("_neg_base")]:
        df[col] = df[col].astype(object).where(df[col].notna(), None)

    df = score(df)
    records = df.to_dict("records")
    for r in records:
        r["reasons"], r["risks"] = explain(r)
        r["key_metrics"] = key_metrics(r)
    return df, records, idx_ret


INSERT_SQL = """
INSERT INTO company_rankings (
    snapshot_date, company_id, symbol, model_version, growth_score, growth_label,
    rank_overall, rank_in_sector, rank_in_industry, coverage,
    score_growth, score_profitability, score_financial_health, score_cash_flow, score_momentum, score_news,
    reasons, risks, key_metrics
) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
"""


def _db(x, digits=2):
    x = _num(x)
    return None if math.isnan(x) else round(x, digits)


def _int(x):
    x = _num(x)
    return None if math.isnan(x) else int(x)


def to_rows(records, snap):
    rows = []
    for r in records:
        rows.append((
            snap, int(r["company_id"]), r["symbol"], MODEL_VERSION, _db(r["growth_score"]), r["growth_label"],
            _int(r["rank_overall"]), _int(r["rank_in_sector"]), _int(r["rank_in_industry"]),
            round(float(r["coverage"]), 2),
            *[_db(r[f"score_{c}"]) for c in WEIGHTS],
            json.dumps(r["reasons"]) if r["reasons"] else None,
            json.dumps(r["risks"]) if r["risks"] else None,
            json.dumps(r["key_metrics"]),
        ))
    return rows


def write(conn, rows, snap, partial_ids=None):
    cur = conn.cursor()
    try:
        if partial_ids is None:
            cur.execute("DELETE FROM company_rankings WHERE snapshot_date = %s", (snap,))
        else:
            ids = list(partial_ids)
            cur.execute(f"DELETE FROM company_rankings WHERE snapshot_date = %s AND company_id IN "
                        f"({', '.join(['%s'] * len(ids))})", [snap, *ids])
        for k in range(0, len(rows), 500):
            cur.executemany(INSERT_SQL, rows[k:k + 500])
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        cur.close()


def report(df, records, symbols=None):
    ranked = df["growth_score"].notna()
    print(f"companies: {len(df)}   ranked: {ranked.sum()}   unranked: {(~ranked).sum()}")
    print("labels:", df["growth_label"].value_counts().to_dict())
    cols = ["rank_overall", "symbol", "sector", "growth_score", "growth_label", "coverage",
            *[f"score_{c}" for c in WEIGHTS]]
    view = df[df["symbol"].isin(symbols)] if symbols else df[ranked].nsmallest(15, "rank_overall")
    with pd.option_context("display.width", 220, "display.max_columns", 30):
        print(view[cols].round(1).to_string(index=False))
    by_symbol = {r["symbol"]: r for r in records}
    for sym in (symbols or view["symbol"].head(3)):
        r = by_symbol.get(sym)
        if r:
            print(f"\n{sym}: reasons={r['reasons']}\n  risks={r['risks']}\n  key_metrics={r['key_metrics']}")


def main(argv=None):
    parser = argparse.ArgumentParser(description="Build the preliminary company growth ranking snapshot.")
    parser.add_argument("--date", help="snapshot date YYYY-MM-DD (default: today)")
    parser.add_argument("--dry-run", action="store_true", help="compute and print, don't write")
    parser.add_argument("--symbols", nargs="*", help="only write/print these symbols (scores use all companies)")
    args = parser.parse_args(argv)

    warnings.filterwarnings("ignore", message="pandas only supports SQLAlchemy")
    from news_pipeline.db import get_connection

    snap = datetime.strptime(args.date, "%Y-%m-%d").date() if args.date else date.today()
    symbols = [s.strip().upper() for s in args.symbols] if args.symbols else None

    conn = get_connection()
    try:
        df, records, idx_ret = build(conn, snap)
        print(f"snapshot {snap}  model {MODEL_VERSION}  benchmark 1y return: {idx_ret['return_1y']:.1%}")
        report(df, records, symbols)
        out = [r for r in records if not symbols or r["symbol"] in symbols]
        if args.dry_run:
            print(f"\ndry run: {len(out)} rows not written")
        else:
            write(conn, to_rows(out, snap), snap,
                  partial_ids=[r["company_id"] for r in out] if symbols else None)
            print(f"\nwrote {len(out)} rows to company_rankings for {snap}")
    finally:
        conn.close()


if __name__ == "__main__":
    main()
