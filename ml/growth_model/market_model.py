"""Market model: which stocks' price trend points to beating the NIFTY SMALLCAP 250 in 6-12 months.

The model (v1, "trend6") is a transparent equal-weight blend of six trend signals, each a
cross-sectional percentile on the signal date:
    dist_52w_high   close vs 52-week high (near the high = better)
    ma200_gap       close vs its 200-day average
    ma50_over_200   50-day average vs 200-day average
    rel_6m, rel_3m  6- and 3-month return minus NIFTY SMALLCAP 250
    1 - down_days_3m  fewer down days over 3 months
market_score = percentile of that blend x 100.

Why not ML: in the walk-forward test below, XGBoost and logistic regression on all 29 features did
no better than momentum alone (6m IC ~0.06 vs 0.08; 12m ~0.01 vs 0.05), because they learnt the
handful of market regimes in 2017-2026 (e.g. the 2020 rebound) instead of stock ranking. Signal by
signal, trend measures were positive in 7-9 of 9 years, while low volatility / beta flipped sign
with the regime, so they are left out. trend6 walk-forward (2019-2026): 6m IC 0.089, top-10% vs
bottom-10% spread +10.3%/half-year; 12m IC 0.097, spread +17.7%/year, top 10% beat the average
stock in 7 of 7 years. Caveat: the six signals were chosen after looking at 2018-2026 single-signal
results, so the numbers are slightly optimistic; they are textbook trend measures, not a fitted set.
The ML models stay in the report so any future feature (financials, news) is judged the same way.

Walk-forward test: for each test year Y, fitted models train on signal dates whose label window
ended before Y began (purged: a 6-month label from July can't be trained on when testing from
January), then score every signal date in Y. Compared:
    trend6      the model above (no fitting)
    momentum    rank by mom_12_1 alone (the textbook signal)
    xgb         XGBoost on all ranked features + market mood (top-20% classifier)
    logistic    logistic regression on the same features
    universe    the average stock (what random picks would get)

Universe (both training and testing): median traded value >= MIN_ADV_CR crore/day over 60 days,
>= 1 year of trading history, entry price >= Rs 1 (labels.py). Tiny illiquid stocks are excluded
because their returns can't be captured in practice.

Reported per test year and overall:
    auc          how well the score separates top-20% stocks from the rest (0.5 = coin flip)
    ic           mean over signal dates of the Spearman correlation between score and excess return
    top10        mean excess return of the top-scored 10% (excess clipped to [-100%, +300%] so one
                 penny rally can't carry a year), top10_med its median, top10_beat its beat rate
    bot10        the same for the bottom 10%;  spread = top10 - bot10
Survivorship: prices exist only for companies listed today (see labels.py), so absolute excess
returns are optimistic; the comparison between methods is the fair part.

Output for the latest signal date: ml/data/processed/market_scores.csv (market_score 0-100 plus the
six signal percentiles) and ml/models/market_model_meta.json (method, walk-forward results).

CLI:  python3 -m growth_model.market_model [--horizon 6m] [--horizon 12m] [--rebuild-features]
"""

import argparse
import json
import time
import warnings
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.stats import spearmanr
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import roc_auc_score
from xgboost import XGBClassifier

from .labels import LABELS_FILE, build_labels
from .market_features import FEATURES, STOCK_FEATURES, build_market_features, rank_features
from .prices import CACHE_DIR, load_companies, load_prices

MODELS_DIR = Path(__file__).resolve().parent.parent / "models"
FEATURES_FILE = CACHE_DIR / "growth_market_features.pkl"

MIN_ADV_CR = 0.5
MIN_DAYS_LISTED = 252
MODEL_VERSION = "market-trend6-v1"
TREND_SIGNALS = ["dist_52w_high", "ma200_gap", "ma50_over_200", "rel_6m", "rel_3m", "inv_down_days_3m"]
PURGE_DAYS = {"1m": 40, "3m": 100, "6m": 190, "12m": 375}   # label length + buffer, calendar days
FIRST_TEST_YEAR = 2019
CLIP = (-1.0, 3.0)
SEED = 42

XGB_PARAMS = dict(
    n_estimators=400, max_depth=4, learning_rate=0.03, subsample=0.8, colsample_bytree=0.8,
    min_child_weight=200, reg_lambda=5.0, tree_method="hist", eval_metric="logloss",
    random_state=SEED, n_jobs=4,
)


def trend_score(frame):
    """Equal-weight blend of the six trend-signal percentiles (missing signal -> neutral 0.5)."""
    signals = frame[TREND_SIGNALS[:-1]].copy()
    signals["inv_down_days_3m"] = 1 - frame["down_days_3m"]
    return signals.fillna(0.5).mean(axis=1)


def load_dataset(rebuild=False):
    if rebuild or not FEATURES_FILE.exists() or not LABELS_FILE.exists():
        stocks, index = load_prices()
        build_labels(stocks, index).to_pickle(LABELS_FILE)
        build_market_features(stocks, index).to_pickle(FEATURES_FILE)
    labels = pd.read_pickle(LABELS_FILE)
    feats = rank_features(pd.read_pickle(FEATURES_FILE))
    df = feats.merge(labels, on=["company_id", "signal_date"], how="inner")
    universe = (df["adv_60d_cr"] >= MIN_ADV_CR) & (df["days_listed"] >= MIN_DAYS_LISTED)
    return df[universe].reset_index(drop=True)


def _xgb():
    return XGBClassifier(**XGB_PARAMS)


def _logistic(train, target):
    X = train[FEATURES].to_numpy(dtype=float)
    med = np.nanmedian(X, axis=0)
    mu, sd = np.nanmean(X, axis=0), np.nanstd(X, axis=0) + 1e-9
    fill = lambda A: (np.where(np.isnan(A), med, A) - mu) / sd
    model = LogisticRegression(max_iter=500, C=0.1).fit(fill(X), train[target])
    return lambda frame: model.predict_proba(fill(frame[FEATURES].to_numpy(dtype=float)))[:, 1]


METHODS = ["trend6", "momentum", "xgb", "logistic"]


def evaluate(test, score_col, h):
    excess = test[f"excess_{h}"]
    clipped = excess.clip(*CLIP)
    out = {"auc": roc_auc_score(test[f"top_q_{h}"], test[score_col])}
    ics, top, bot = [], [], []
    for _, g in test.groupby("signal_date"):
        if len(g) < 50:
            continue
        ics.append(spearmanr(g[score_col], g[f"excess_{h}"]).statistic)
        pct = g[score_col].rank(pct=True)
        top.append(g[pct > 0.9])
        bot.append(g[pct <= 0.1])
    top, bot = pd.concat(top), pd.concat(bot)
    out["ic"] = float(np.nanmean(ics))
    out["top10"] = top[f"excess_{h}"].clip(*CLIP).mean()
    out["top10_med"] = top[f"excess_{h}"].median()
    out["top10_beat"] = top[f"beat_{h}"].mean()
    out["bot10"] = bot[f"excess_{h}"].clip(*CLIP).mean()
    out["spread"] = out["top10"] - out["bot10"]
    out["universe"] = clipped.mean()
    return out


def walk_forward(df, h):
    target = f"top_q_{h}"
    data = df[df[target].notna()]
    last_year = data["signal_date"].max().year
    results, scored = [], []
    for year in range(FIRST_TEST_YEAR, last_year + 1):
        start = pd.Timestamp(year, 1, 1)
        train = data[data["signal_date"] < start - pd.Timedelta(days=PURGE_DAYS[h])]
        test = data[data["signal_date"].dt.year == year].copy()
        if len(test) == 0 or train[target].nunique() < 2:
            continue
        model = _xgb().fit(train[FEATURES], train[target])
        test["xgb"] = model.predict_proba(test[FEATURES])[:, 1]
        test["logistic"] = _logistic(train, target)(test)
        test["momentum"] = test["mom_12_1"].fillna(0.5)
        test["trend6"] = trend_score(test)
        for method in METHODS:
            results.append({"year": year, "method": method, "train_rows": len(train),
                            "test_rows": len(test), **evaluate(test, method, h)})
        scored.append(test)
        print(f"  {h} {year}: trained on {len(train):,} rows, tested on {len(test):,}")
    return pd.DataFrame(results), pd.concat(scored)


def report(results, scored, h):
    pct = lambda v: f"{v:+.1%}"
    print(f"\n=== {h} horizon: walk-forward by test year ===")
    print(f"{'year':<6}{'method':<10}{'auc':>6}{'ic':>7}{'top10':>8}{'top10 med':>10}{'beat%':>7}"
          f"{'bot10':>8}{'spread':>8}{'all':>8}")
    for _, r in results.iterrows():
        print(f"{r.year:<6}{r.method:<10}{r.auc:>6.3f}{r.ic:>7.3f}{pct(r.top10):>8}{pct(r.top10_med):>10}"
              f"{r.top10_beat:>7.0%}{pct(r.bot10):>8}{pct(r.spread):>8}{pct(r.universe):>8}")
    print(f"\n{'ALL YEARS':<16}{'auc':>6}{'ic':>7}{'top10':>8}{'top10 med':>10}{'beat%':>7}{'bot10':>8}{'spread':>8}"
          f"{'yrs top10>all':>15}")
    for method in METHODS:
        m = evaluate(scored, method, h)
        r = results[results.method == method]
        wins = int((r.top10 > r.universe).sum())
        print(f"{method:<16}{m['auc']:>6.3f}{m['ic']:>7.3f}{pct(m['top10']):>8}{pct(m['top10_med']):>10}"
              f"{m['top10_beat']:>7.0%}{pct(m['bot10']):>8}{pct(m['spread']):>8}{wins:>11}/{len(r)}")
    print(f"{'universe avg':<16}{'':>13}{pct(scored[f'excess_{h}'].clip(*CLIP).mean()):>8}"
          f"{pct(scored[f'excess_{h}'].median()):>10}{scored[f'beat_{h}'].mean():>7.0%}")


def score_latest(df, companies, walkforward):
    """market_score for every universe stock on the latest signal date + model metadata."""
    latest = df["signal_date"].max()
    now = df[df["signal_date"] == latest].copy()
    now["trend_raw"] = trend_score(now)
    now["market_score"] = (now["trend_raw"].rank(pct=True) * 100).round(1)
    now["inv_down_days_3m"] = 1 - now["down_days_3m"]
    now = now.merge(companies, on="company_id", how="left").sort_values("market_score", ascending=False)
    cols = ["company_id", "symbol", "name", "sector", "market_score", "adv_60d_cr", *TREND_SIGNALS]
    now["signal_date"] = latest.date()
    now[["signal_date", *cols]].round(4).to_csv(CACHE_DIR / "market_scores.csv", index=False)

    summary = {}
    for h, (results, scored) in walkforward.items():
        r = results[results.method == "trend6"]
        overall = evaluate(scored, "trend6", h)
        summary[h] = {
            "ic_mean": round(float(r.ic.mean()), 4), "spread_mean": round(float(r.spread.mean()), 4),
            "top10_beat_rate": round(float(overall["top10_beat"]), 4),
            "years_top10_above_universe": f"{int((r.top10 > r.universe).sum())}/{len(r)}",
            "test_years": [int(y) for y in r.year],
        }
    meta = {
        "model_version": MODEL_VERSION, "created_at": datetime.now().isoformat(timespec="seconds"),
        "method": "equal-weight mean of cross-sectional percentiles, missing -> 0.5; score = percentile x 100",
        "signals": TREND_SIGNALS, "universe": {"min_adv_cr": MIN_ADV_CR, "min_days_listed": MIN_DAYS_LISTED},
        "scored_signal_date": str(latest.date()), "companies_scored": len(now), "walkforward": summary,
    }
    MODELS_DIR.mkdir(exist_ok=True)
    (MODELS_DIR / "market_model_meta.json").write_text(json.dumps(meta, indent=2))

    print(f"\n{len(now):,} companies scored on {latest:%Y-%m-%d}; top 15 market scores:")
    for _, r in now.head(15).iterrows():
        print(f"  {r.symbol:<14}{r.market_score:>6.1f}  {r.adv_60d_cr:>8.1f} cr/day  {str(r.sector)[:34]}")


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--horizon", action="append", choices=["1m", "3m", "6m", "12m"])
    ap.add_argument("--rebuild-features", action="store_true")
    ap.add_argument("--no-final", action="store_true", help="walk-forward only, don't write scores")
    args = ap.parse_args(argv)
    horizons = args.horizon or ["6m", "12m"]
    warnings.filterwarnings("ignore", category=RuntimeWarning)

    t0 = time.time()
    df = load_dataset(rebuild=args.rebuild_features)
    print(f"dataset: {len(df):,} rows, {df['company_id'].nunique():,} companies "
          f"(universe: >= {MIN_ADV_CR} cr/day traded, >= 1 year listed)")
    walkforward = {}
    for h in horizons:
        results, scored = walk_forward(df, h)
        results.to_csv(CACHE_DIR / f"market_walkforward_{h}.csv", index=False)
        report(results, scored, h)
        walkforward[h] = (results, scored)
    if not args.no_final:
        score_latest(df, load_companies(), walkforward)
    print(f"\ndone in {time.time() - t0:.0f}s")


if __name__ == "__main__":
    main()
