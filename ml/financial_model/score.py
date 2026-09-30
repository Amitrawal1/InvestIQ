"""Score every eligible company with the Financial Model as of a signal date.

    python3 -m financial_model.score --date 2026-09-16 --out scores.csv [--refresh]

Eligible = the training universe on that date: non_financial format, fresh financials (period end
within 275 days, filed on or before D), median traded value >= 0.5 crore/day over 60 trading days,
>= 252 trading days of history, last close >= Rs 1 within 5 trading days of D. The liquidity context
comes from the cached price file (ml/data/processed/growth_stock_prices.pkl; refresh it with
`python3 -m growth_model.labels --refresh-prices` for dates past the cache).

Output columns: signal_date, company_id, symbol, financial_score (0-100: percentile of the model
score among eligible companies on D), financial_score_6m / _12m (the per-horizon scores the
walk-forward tested), top_positive / top_negative (feature contributions, "feature:+points"), and
reasons / risks (JSON lists of plain-language strings with the actual values, for the rankings'
reasons/risks). The model spec (features + signs per horizon, or XGBoost files) is read from
ml/models/financial_model.json, written by `python3 -m financial_model.train`.
"""

import argparse
import json
import math
import warnings

import pandas as pd

from growth_model.labels import ENTRY_STALE, MIN_PRICE
from growth_model.prices import BENCHMARK, CACHE_DIR, load_prices

from .data import (FEATURE_NAMES, MIN_ADV_CR, MIN_DAYS_LISTED, MODEL_FEATURES, add_derived, asof_join,
                   check_point_in_time, load_feature_table, rank_features)
from .model import baseline_oriented, baseline_parts, blend_contributions, blend_score

MODELS_DIR = CACHE_DIR.parent.parent / "models"
SPEC_FILE = MODELS_DIR / "financial_model.json"
N_TEXT = 5
TEXT_PCT = 0.75          # a feature is a reason / risk only in the top / bottom quarter of peers


# ---------------------------------------------------------
# Universe as of any date
# ---------------------------------------------------------

def universe_asof(date, stocks=None, index=None):
    """company_id, close_d, adv_60d_cr, days_listed as of D (same definitions as labels.py)."""
    if stocks is None:
        stocks, index = load_prices()
    bench = index[index["index_key"] == BENCHMARK].set_index("price_date")["close"].sort_index()
    calendar = bench.index[bench.index <= date]
    if len(calendar) == 0:
        raise SystemExit(f"no benchmark prices on or before {date:%Y-%m-%d}")
    if (date - calendar[-1]).days > 7:
        print(f"warning: price cache ends {calendar[-1]:%Y-%m-%d}; refresh prices for {date:%Y-%m-%d}")
    s = stocks[stocks["price_date"] <= date]
    s = s[s["price_date"] >= calendar[max(len(calendar) - 400, 0)]]
    close = s.pivot_table(index="price_date", columns="company_id", values="close", aggfunc="last")
    tv = (s.assign(tv=s["close"] * s["volume"] / 1e7)
          .pivot_table(index="price_date", columns="company_id", values="tv", aggfunc="last"))
    union = close.index.union(calendar)
    last = close.reindex(union).ffill(limit=ENTRY_STALE).reindex(calendar).iloc[-1]
    adv = tv.reindex(union).rolling(60, min_periods=20).median().reindex(calendar).ffill(limit=ENTRY_STALE).iloc[-1]
    # days listed counts all history, not only the 400-day window
    full = stocks[stocks["price_date"] <= date].groupby("company_id")["price_date"].nunique()
    out = pd.DataFrame({"close_d": last, "adv_60d_cr": adv}).reset_index().rename(columns={"index": "company_id"})
    out["days_listed"] = out["company_id"].map(full).fillna(0)
    return out[(out["close_d"] >= MIN_PRICE) & out["adv_60d_cr"].notna()]


def eligible_panel(date, features, stocks=None, index=None):
    uni = universe_asof(date, stocks, index)
    uni = uni[(uni["adv_60d_cr"] >= MIN_ADV_CR) & (uni["days_listed"] >= MIN_DAYS_LISTED)].copy()
    uni["signal_date"] = date
    uni["company_id"] = uni["company_id"].astype(int)
    panel = asof_join(uni, features)
    check_point_in_time(panel)
    return add_derived(panel[~panel["fin_stale"]]).reset_index(drop=True)


# ---------------------------------------------------------
# Plain-language text
# ---------------------------------------------------------

def _p(x):
    return f"{x * 100:.0f}%"


def _pts(x):
    return f"{abs(x) * 100:.1f} pts"


def _cr(x):
    return f"Rs {x:,.0f} cr" if abs(x) >= 1000 else f"Rs {x:,.1f} cr"


def _chg(x, noun):
    return f"{noun} {'up' if x >= 0 else 'down'} {_p(abs(x))}"


TEXT = {
    "revenue_yoy": lambda r, v: _chg(v, "Revenue") + " YoY (latest quarter)",
    "net_profit_yoy": lambda r, v: _chg(v, "Net profit") + " YoY (latest quarter)",
    "eps_yoy": lambda r, v: _chg(v, "EPS") + " YoY (latest quarter)",
    "revenue_ttm_growth": lambda r, v: _chg(v, "TTM revenue") + " vs a year ago",
    "net_profit_ttm_growth": lambda r, v: _chg(v, "TTM net profit") + " vs a year ago",
    "eps_ttm_growth": lambda r, v: _chg(v, "TTM EPS") + " vs a year ago",
    "revenue_yoy_accel": lambda r, v: f"Revenue growth {'accelerating' if v >= 0 else 'slowing'} ({_pts(v)} vs previous quarter)",
    "net_profit_yoy_accel": lambda r, v: f"Profit growth {'accelerating' if v >= 0 else 'slowing'} ({_pts(v)} vs previous quarter)",
    "op_margin_q": lambda r, v: f"Operating margin {_p(v)} (latest quarter)",
    "op_margin_ttm": lambda r, v: f"Operating margin {_p(v)} (TTM)",
    "op_margin_change_yoy": lambda r, v: f"Operating margin {'up' if v >= 0 else 'down'} {_pts(v)} YoY",
    "net_margin_ttm": lambda r, v: f"Net margin {_p(v)} (TTM)",
    "net_margin_change_yoy": lambda r, v: f"Net margin {'up' if v >= 0 else 'down'} {_pts(v)} YoY",
    "roe": lambda r, v: f"ROE {_p(v)}",
    "roce": lambda r, v: f"ROCE {_p(v)}",
    "profitable": lambda r, v: (f"Profitable: TTM net profit {_cr(r['net_profit_ttm'])}" if v > 0
                                else f"Loss-making: TTM net loss {_cr(-r['net_profit_ttm'])}"),
    "debt_to_equity": lambda r, v: "Virtually debt-free" if v < 0.05 else f"Debt/equity {v:.2f}",
    "debt_to_equity_change_1y": lambda r, v: f"Debt/equity {'up' if v >= 0 else 'down'} {abs(v):.2f} in a year",
    "current_ratio": lambda r, v: f"Current ratio {v:.2f}",
    "coverage_input": lambda r, v: ("No meaningful interest cost (debt-free)" if v > 1e8
                                    else f"Interest coverage {v:.1f}x"),
    "cash_conversion": lambda r, v: f"Operating cash flow {v:.1f}x net profit (TTM)",
    "fcf_margin": lambda r, v: f"Free cash flow {_p(v)} of revenue (TTM)",
    "ocf_margin": lambda r, v: f"Operating cash flow {_p(v)} of revenue (TTM)",
    "accruals_ratio": lambda r, v: f"Accruals (profit not backed by cash) {_p(v)} of assets",
    "capex_intensity": lambda r, v: f"Capex {_p(v)} of revenue (TTM)",
    "receivables_minus_revenue_growth": lambda r, v: (f"Receivables growing {_pts(v)} {'faster' if v >= 0 else 'slower'} "
                                                      "than revenue"),
    "n_red_flags": lambda r, v: "No accounting red flags" if v == 0 else f"{int(v)} accounting red flag(s)",
    "filing_lag_days": lambda r, v: f"Results filed {int(v)} days after period end",
    "log_revenue_ttm": lambda r, v: f"Size: TTM revenue {_cr(10 ** v)}",
    # red flags (features.py); value is True when the flag is set
    "flag_profit_up_ocf_negative": lambda r, v: "Profit rising but operating cash flow negative in both recent half-years",
    "flag_receivables_outpacing_revenue": lambda r, v: "Receivables growing much faster than revenue",
    "flag_debt_to_equity_rising": lambda r, v: "Debt/equity up by 0.5 or more in a year",
    "flag_low_interest_coverage": lambda r, v: "Low interest coverage (below 1.5x)",
    "flag_negative_equity": lambda r, v: "Negative shareholder equity",
}
TEXT["coverage_rank_input"] = TEXT["coverage_input"]
FLAGS = [f for f in TEXT if f.startswith("flag_")]


def _bucket(p, good):
    """Oriented percentile -> 'top 10% of peers' / 'bottom 10% of peers'."""
    if good:
        return f"top {max(1, min(50, int(math.ceil((1 - p) * 20) * 5)))}% of peers"
    return f"bottom {max(1, min(50, int(math.ceil(p * 20) * 5)))}% of peers"


def explain(row, contrib, oriented):
    """contrib: Series feature -> points; oriented: Series feature -> oriented percentile (0-1).

    Reasons: the largest positive contributions (> 0.5 points) among features in the top quarter of
    peers; risks: red flags first, then the largest negative contributions (< -0.5 points) among
    features in the bottom quarter; at most N_TEXT each, with the actual values.
    """
    reasons, risks = [], []
    for f, c in contrib.sort_values(ascending=False).items():
        v = row.get(f)
        if (c <= 0.5 or f in FLAGS or v is None or pd.isna(v) or len(reasons) >= N_TEXT
                or not oriented.get(f, 0) >= TEXT_PCT):
            continue
        reasons.append(f"{TEXT[f](row, float(v))} ({_bucket(oriented[f], True)})")
    risks = [TEXT[f](row, True) for f in FLAGS if f in contrib.index and contrib[f] < 0]
    for f, c in contrib.sort_values().items():
        v = row.get(f)
        if (c >= -0.5 or f in FLAGS or v is None or pd.isna(v) or len(risks) >= N_TEXT
                or not oriented.get(f, 1) <= 1 - TEXT_PCT):
            continue
        risks.append(f"{TEXT[f](row, float(v))} ({_bucket(oriented[f], False)})")
    return reasons, risks[:N_TEXT]


# ---------------------------------------------------------
# Scoring
# ---------------------------------------------------------

def load_spec():
    if not SPEC_FILE.exists():
        raise SystemExit(f"{SPEC_FILE} not found: run `python3 -m financial_model.train` first")
    return json.loads(SPEC_FILE.read_text())


def _xgb_scores(spec, ranked, h):
    from xgboost import XGBRegressor
    model = XGBRegressor()
    model.load_model(MODELS_DIR / spec["horizons"][h]["xgb_file"])
    import xgboost as xgb
    dm = xgb.DMatrix(ranked[FEATURE_NAMES].to_numpy(dtype=float), feature_names=FEATURE_NAMES)
    contribs = model.get_booster().predict(dm, pred_contribs=True)[:, :-1]
    pred = pd.Series(model.predict(ranked[FEATURE_NAMES].to_numpy(dtype=float)), index=ranked.index)
    scale = 100 / max(pred.std(), 1e-9) / 10     # contributions in rough score points
    return pred, pd.DataFrame(contribs * scale, columns=FEATURE_NAMES, index=ranked.index)


def score_panel(panel, spec):
    """-> DataFrame with scores, contributions and text for every row of an eligible panel (one date)."""
    ranked = rank_features(panel)
    method = spec["method_key"]
    if method == "baseline":
        return _finish(panel, {}, *baseline_parts(panel), baseline_oriented(panel))
    per_h, contribs = {}, {}
    for h, hs in spec["horizons"].items():
        if method == "blend":
            chosen = hs["features"]
            per_h[h] = blend_score(ranked, chosen)
            contribs[h] = blend_contributions(ranked, chosen)
        elif method in ("xgb", "blend_xgb"):
            pred, con = _xgb_scores(spec, ranked, h)
            if method == "blend_xgb":
                b = blend_score(ranked, hs["features"])
                pred = (b.rank(pct=True) + pred.rank(pct=True)) / 2
                con = (con.add(blend_contributions(ranked, hs["features"]), fill_value=0)) / 2
            per_h[h], contribs[h] = pred, con
        else:
            raise SystemExit(f"unknown method {method}")
    raw = sum(s.rank(pct=True) for s in per_h.values()) / len(per_h)
    total = sum(c.reindex(columns=FEATURE_NAMES).fillna(0) for c in contribs.values()) / len(contribs)
    signs = {}
    for hs in spec["horizons"].values():
        for f, s in hs.get("features", {}).items():
            signs.setdefault(f, s)
    oriented = pd.DataFrame({f: (ranked[f] if signs.get(f, MODEL_FEATURES[f][1] or 1) > 0 else 1 - ranked[f])
                             for f in FEATURE_NAMES}, index=ranked.index)
    return _finish(panel, per_h, raw, total, oriented)


def _finish(panel, per_h, raw, total, oriented):
    """Score columns (0-100 percentiles on the date), top contributions and reasons/risks text."""
    out = panel[["company_id", "signal_date"]].copy()
    for h, s in per_h.items():
        out[f"financial_score_{h}"] = (s.rank(pct=True) * 100).round(1)
    out["financial_score"] = (raw.rank(pct=True) * 100).round(1)
    out["model_raw"] = raw.round(4)
    tops, bots, reasons, risks = [], [], [], []
    for i in out.index:
        c = total.loc[i]
        c = c[c.abs() > 0.05]
        tops.append("; ".join(f"{f}:{v:+.1f}" for f, v in c.sort_values(ascending=False).head(3).items() if v > 0))
        bots.append("; ".join(f"{f}:{v:+.1f}" for f, v in c.sort_values().head(3).items() if v < 0))
        rs, rk = explain(panel.loc[i], c, oriented.loc[i])
        reasons.append(json.dumps(rs))
        risks.append(json.dumps(rk))
    out["top_positive"], out["top_negative"] = tops, bots
    out["reasons"], out["risks"] = reasons, risks
    out["period_end"] = panel["period_end"].dt.date
    out["filing_date"] = panel["filing_date"].dt.date
    out["adv_60d_cr"] = panel["adv_60d_cr"].round(2)
    return out


def score_date(date, spec=None, refresh=False, companies=None):
    date = pd.Timestamp(date)
    spec = spec or load_spec()
    features, _ = load_feature_table(refresh=refresh)
    panel = eligible_panel(date, features)
    out = score_panel(panel, spec)
    if companies is None:
        from growth_model.prices import load_companies
        companies = load_companies()
    out = out.merge(companies[["company_id", "symbol", "name", "sector"]], on="company_id", how="left")
    cols = ["signal_date", "company_id", "symbol", "name", "sector", "financial_score",
            *[c for c in out.columns if c.startswith("financial_score_")], "model_raw", "top_positive", "top_negative",
            "reasons", "risks", "period_end", "filing_date", "adv_60d_cr"]
    out["signal_date"] = date.date()
    return out[cols].sort_values("financial_score", ascending=False).reset_index(drop=True)


def main(argv=None):
    ap = argparse.ArgumentParser(description="Score companies with the Financial Model as of a date.")
    ap.add_argument("--date", required=True, help="signal date YYYY-MM-DD")
    ap.add_argument("--out", required=True, help="CSV path")
    ap.add_argument("--refresh", action="store_true", help="re-read financial_filings from the DB (SELECT only)")
    args = ap.parse_args(argv)
    warnings.filterwarnings("ignore", category=RuntimeWarning)
    out = score_date(args.date, refresh=args.refresh)
    out.to_csv(args.out, index=False)
    print(f"{len(out):,} companies scored as of {args.date} -> {args.out}")
    with pd.option_context("display.width", 200, "display.max_colwidth", 60):
        print(out.head(10)[["symbol", "financial_score", "top_positive", "top_negative"]].to_string(index=False))


if __name__ == "__main__":
    main()
