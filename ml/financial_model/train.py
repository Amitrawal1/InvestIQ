"""Financial Model: walk-forward test of financial-statement scores, pick a winner, fit, score.

Question: given only what was public on signal date D, which non-financial Indian small/mid
companies will beat the NIFTY SMALLCAP 250 over the next 6 and 12 months, judged from their
financial statements alone (price signals are the market model's job)?

Walk-forward (same protocol as growth_model/market_model.py): for each test year Y, fitted parts
(the blend's feature selection, XGBoost) see only signal dates whose label window ended before Y
began (PURGE_DAYS: 190 days for 6m, 375 for 12m), then every signal date in Y is scored. Methods
(model.py): baseline (prelim-v2 financial blend), blend (transparent v1), xgb, blend_xgb.
Metrics per test year and overall: auc, ic, top10 / bot10 / spread, top10_beat, universe, plus
"years IC > 0" and "years top10 > universe". Test years start in FIRST_TEST_YEAR (2020): XBRL
filings start in 2018 and YoY growth needs a year-ago quarter, so 2019 would have no training data.

Winner rule (fixed before looking at the test years): among baseline and blend, the method with
more years IC > 0 summed over both horizons, then higher mean yearly IC. An ML method (xgb,
blend_xgb) replaces it only if on BOTH horizons its mean yearly IC is >= 0.01 higher, it has at
least as many years with IC > 0, and its mean spread is at least as high. The final model is then
refit on every labelled date (per horizon) and scores the latest signal date.

Also reported: Spearman correlation per date between the financial score and the market model's
trend6 score on the same rows (low = the combiner gains from both), and the walk-forward of a
50/50 percentile mix of the two as a first hint for the combiner.

Outputs:
    ml/models/financial_model_meta.json      method, features, universe, walk-forward per horizon
    ml/models/financial_model.json           the fitted spec score.py reads (features + signs)
    ml/models/financial_model_xgb_<h>.json   only when an XGBoost method wins
    ml/data/processed/financial_walkforward_<h>.csv, financial_feature_ic_<h>.csv
    ml/data/processed/financial_scores.csv   scores for the latest signal date

CLI:  python3 -m financial_model.train [--refresh] [--horizon 6m] [--horizon 12m]
"""

import argparse
import json
import time
import warnings
from datetime import datetime

import numpy as np
import pandas as pd

from growth_model.market_features import rank_features as rank_market
from growth_model.market_model import FEATURES_FILE, PURGE_DAYS, evaluate, trend_score
from growth_model.prices import CACHE_DIR, load_companies

from rankings.build import FINANCIAL_COMPONENTS, FLAG_PENALTY, SUBFEATURES, WEIGHTS

from .data import FEATURE_NAMES, MIN_ADV_CR, MIN_DAYS_LISTED, STALE_FINANCIALS_DAYS, build_panel, rank_features
from .model import (MIN_IC, MIN_SIGN_SHARE, XGB_PARAMS, baseline_score, blend_score, daily_ics, fit_xgb,
                    monotone_constraints, per_date_pct, predict_xgb, select_features, yearly_ics)
from .score import MODELS_DIR, SPEC_FILE, score_date

MODEL_VERSION = "fin-v1"
FIRST_TEST_YEAR = 2020
METHODS = ["baseline", "blend", "xgb", "blend_xgb"]
ML_METHODS = ["xgb", "blend_xgb"]
ML_IC_MARGIN = 0.01

METHOD_TEXT = {
    "baseline": ("prelim-v2 financial blend (rankings/build.py), unchanged: per-date percentiles of the "
                 "sub-features -> growth / profitability / financial_health / cash_flow component "
                 "percentiles, weighted 0.30 / 0.20 / 0.15 / 0.15 renormalised over available components, "
                 "minus 3 points per red flag (6 for negative equity); no growth component -> 50; "
                 "financial_score = percentile of that blend among eligible companies x 100. It won the "
                 "walk-forward against a data-selected blend and XGBoost (see winner_rule)."),
    "blend": ("equal-weight mean of cross-sectional percentiles of the selected financial-statement "
              "features, oriented by expected sign, missing -> 0.5; per horizon; financial_score = "
              "percentile of the mean of the 6m and 12m percentiles x 100"),
}
BASELINE_FEATURES = {c: [{"feature": f, "weight": w, "higher_is_better": hb} for f, w, hb in SUBFEATURES[c][0]]
                     for c in FINANCIAL_COMPONENTS}
BASELINE_FEATURES["component_weights"] = {c: WEIGHTS[c] for c in FINANCIAL_COMPONENTS}
BASELINE_FEATURES["red_flag_penalty"] = FLAG_PENALTY


def walk_forward(ranked, ics, h):
    data = ranked[ranked[f"excess_{h}"].notna() & ranked[f"top_q_{h}"].notna()]
    last_year = data["signal_date"].max().year
    results, scored, selections = [], [], {}
    for year in range(FIRST_TEST_YEAR, last_year + 1):
        start = pd.Timestamp(year, 1, 1)
        cutoff = start - pd.Timedelta(days=PURGE_DAYS[h])
        train = data[data["signal_date"] < cutoff]
        test = data[data["signal_date"].dt.year == year].copy()
        if len(test) == 0 or len(train) == 0:
            continue
        chosen = select_features(yearly_ics(ics[ics["signal_date"] < cutoff]))
        selections[year] = chosen
        test["baseline"] = test["baseline_raw"]
        test["blend"] = blend_score(test, chosen)
        test["xgb"] = predict_xgb(fit_xgb(train, h), test)
        test["blend_xgb"] = (per_date_pct(test["blend"], test["signal_date"])
                             + per_date_pct(test["xgb"], test["signal_date"])) / 2
        for method in METHODS:
            results.append({"year": year, "method": method, "train_rows": len(train), "test_rows": len(test),
                            "n_features": len(chosen) if method == "blend" else np.nan,
                            **evaluate(test, method, h)})
        scored.append(test)
        print(f"  {h} {year}: trained on {len(train):,} rows (< {cutoff:%Y-%m-%d}), tested on {len(test):,}; "
              f"blend uses {len(chosen)} features")
    return pd.DataFrame(results), pd.concat(scored), selections


def summarise(results, scored, h, methods):
    out = {}
    for m in methods:
        r = results[results.method == m]
        overall = evaluate(scored, m, h)
        out[m] = {
            "ic_mean": float(r.ic.mean()), "spread_mean": float(r.spread.mean()),
            "top10_mean": float(r.top10.mean()), "top10_beat_rate": float(overall["top10_beat"]),
            "auc": float(overall["auc"]),
            "years_ic_positive": int((r.ic > 0).sum()),
            "years_top10_above_universe": int((r.top10 > r.universe).sum()),
            "bot10_mean": float(r.bot10.mean()),
            "years_bot10_below_universe": int((r.bot10 < r.universe).sum()), "n_years": len(r),
            # secondary, post-hoc view: folds with >= 3 training years (not used to pick the winner)
            "ic_mean_2022_on": float(r[r.year >= 2022].ic.mean()),
            "spread_mean_2022_on": float(r[r.year >= 2022].spread.mean()),
        }
    return out


def report(results, summary, h, methods):
    pct = lambda v: f"{v:+.1%}"
    print(f"\n=== {h} horizon: walk-forward by test year ===")
    print(f"{'year':<6}{'method':<11}{'auc':>6}{'ic':>7}{'top10':>8}{'top10 med':>10}{'beat%':>7}"
          f"{'bot10':>8}{'spread':>8}{'all':>8}")
    for _, r in results[results.method.isin(methods)].iterrows():
        print(f"{r.year:<6}{r.method:<11}{r.auc:>6.3f}{r.ic:>7.3f}{pct(r.top10):>8}{pct(r.top10_med):>10}"
              f"{r.top10_beat:>7.0%}{pct(r.bot10):>8}{pct(r.spread):>8}{pct(r.universe):>8}")
    print(f"\n{'ALL YEARS':<11}{'auc':>6}{'ic mean':>9}{'spread':>8}{'top10 beat':>11}{'yrs ic>0':>10}"
          f"{'yrs top10>all':>15}{'yrs bot10<all':>15}{'ic 2022+':>10}{'spread 2022+':>14}")
    for m in methods:
        s = summary[m]
        print(f"{m:<11}{s['auc']:>6.3f}{s['ic_mean']:>9.3f}{pct(s['spread_mean']):>8}{s['top10_beat_rate']:>11.0%}"
              f"{s['years_ic_positive']:>7}/{s['n_years']}{s['years_top10_above_universe']:>11}/{s['n_years']}"
              f"{s['years_bot10_below_universe']:>11}/{s['n_years']}{s['ic_mean_2022_on']:>10.3f}"
              f"{pct(s['spread_mean_2022_on']):>14}")


def pick_winner(summaries):
    def key(m):
        return (sum(summaries[h][m]["years_ic_positive"] for h in summaries),
                np.mean([summaries[h][m]["ic_mean"] for h in summaries]))
    base = max(["baseline", "blend"], key=key)
    why = f"{base}: more years with IC > 0 / higher mean IC than the other transparent method"
    for m in ML_METHODS:
        clearly = all(
            summaries[h][m]["ic_mean"] >= summaries[h][base]["ic_mean"] + ML_IC_MARGIN
            and summaries[h][m]["years_ic_positive"] >= summaries[h][base]["years_ic_positive"]
            and summaries[h][m]["spread_mean"] >= summaries[h][base]["spread_mean"]
            for h in summaries)
        if clearly:
            return m, f"{m} beat {base} on both horizons by >= {ML_IC_MARGIN} IC with as many positive years"
    return base, why + f"; no ML method beat it by >= {ML_IC_MARGIN} mean IC on both horizons"


# ---------------------------------------------------------
# Market-model comparison
# ---------------------------------------------------------

def market_comparison(scored, h, method):
    """Per-date Spearman(fin score, trend6) and the walk-forward of a 50/50 mix."""
    if not FEATURES_FILE.exists():
        return None
    mk = rank_market(pd.read_pickle(FEATURES_FILE))
    mk["trend6"] = trend_score(mk)
    df = scored.merge(mk[["company_id", "signal_date", "trend6"]], on=["company_id", "signal_date"], how="inner")
    corr = df.groupby("signal_date").apply(
        lambda g: g[method].rank().corr(g["trend6"].rank()) if len(g) >= 50 else np.nan, include_groups=False)
    df["mix"] = (per_date_pct(df[method], df["signal_date"]) + per_date_pct(df["trend6"], df["signal_date"])) / 2
    per_year = []
    for year, g in df.groupby(df["signal_date"].dt.year):
        per_year.append({"year": int(year), "corr": float(corr[corr.index.year == year].mean()),
                         **{f"ic_{m}": float(evaluate(g, m, h)["ic"]) for m in (method, "trend6", "mix")},
                         **{f"spread_{m}": float(evaluate(g, m, h)["spread"]) for m in (method, "trend6", "mix")}})
    return {"rows": len(df), "corr_mean": float(corr.mean()), "per_year": per_year}


# ---------------------------------------------------------
# Main
# ---------------------------------------------------------

def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--horizon", action="append", choices=["6m", "12m"])
    ap.add_argument("--refresh", action="store_true", help="re-read financial_filings from the DB (SELECT only)")
    ap.add_argument("--no-final", action="store_true", help="walk-forward only, don't fit/score")
    args = ap.parse_args(argv)
    horizons = args.horizon or ["6m", "12m"]
    warnings.filterwarnings("ignore", category=RuntimeWarning)
    warnings.filterwarnings("ignore", category=FutureWarning)

    t0 = time.time()
    panel, stats = build_panel(refresh=args.refresh)
    ranked = rank_features(panel)
    ranked["baseline_raw"] = baseline_score(panel)
    print(f"panel: {len(ranked):,} rows, {ranked['company_id'].nunique():,} companies, "
          f"{ranked['signal_date'].nunique()} signal dates; {stats}")

    wf, summaries, selections, ics_by_h = {}, {}, {}, {}
    for h in horizons:
        data = ranked[ranked[f"excess_{h}"].notna() & ranked[f"top_q_{h}"].notna()]
        ics = daily_ics(data, h)
        ics_by_h[h] = ics
        yearly = yearly_ics(ics).T
        yearly["mean"] = yearly.mean(axis=1)
        yearly.round(4).to_csv(CACHE_DIR / f"financial_feature_ic_{h}.csv")
        results, scored, sel = walk_forward(ranked, ics, h)
        results.to_csv(CACHE_DIR / f"financial_walkforward_{h}.csv", index=False)
        summaries[h] = summarise(results, scored, h, METHODS)
        report(results, summaries[h], h, METHODS)
        wf[h], selections[h] = (results, scored), sel

    winner, why = pick_winner(summaries)
    print(f"\nwinner: {winner} ({why})")

    market = {}
    for h in horizons:
        mc = market_comparison(wf[h][1], h, winner)
        if mc:
            market[h] = mc
            print(f"{h}: Spearman(financial {winner}, market trend6) per date, mean {mc['corr_mean']:.3f}")
            for r in mc["per_year"]:
                print(f"   {r['year']}  corr {r['corr']:+.3f}  IC fin {r[f'ic_{winner}']:+.3f}  trend6 "
                      f"{r['ic_trend6']:+.3f}  50/50 {r['ic_mix']:+.3f}   spread fin {r[f'spread_{winner}']:+.1%}  "
                      f"trend6 {r['spread_trend6']:+.1%}  50/50 {r['spread_mix']:+.1%}")
    if args.no_final:
        print(f"\ndone in {time.time() - t0:.0f}s")
        return

    # ---- final fit on every labelled date ----
    method_key = winner
    spec = {"model_version": MODEL_VERSION, "method_key": method_key, "horizons": {}}
    for h in horizons:
        chosen = select_features(yearly_ics(ics_by_h[h]))
        hs = {"features": chosen}
        if method_key in ML_METHODS:
            model = fit_xgb(ranked[ranked[f"excess_{h}"].notna()], h)
            fname = f"financial_model_xgb_{h}.json"
            model.save_model(MODELS_DIR / fname)
            hs["xgb_file"] = fname
        spec["horizons"][h] = hs
    MODELS_DIR.mkdir(exist_ok=True)
    SPEC_FILE.write_text(json.dumps(spec, indent=2))

    latest = ranked["signal_date"].max()
    scores = score_date(latest, spec=spec, companies=load_companies())
    scores.to_csv(CACHE_DIR / "financial_scores.csv", index=False)

    def table(h):
        res = wf[h][0]
        return [{k: (round(float(v), 4) if isinstance(v, (float, np.floating)) else v)
                 for k, v in r.items()} for r in res.to_dict("records")]

    meta = {
        "model_version": MODEL_VERSION, "created_at": datetime.now().isoformat(timespec="seconds"),
        "method": METHOD_TEXT.get(method_key, f"{method_key}: see financial_model/model.py"),
        "winner_rule": why,
        "selection_rule": {"min_mean_ic": MIN_IC, "min_sign_share_of_years": round(MIN_SIGN_SHARE, 3),
                           "sign": "economic prior; IC sign where the prior is unclear (size, capex)",
                           "uses": "training years only in the walk-forward; all labelled years for the final fit"},
        "features": (BASELINE_FEATURES if method_key == "baseline"
                     else {h: spec["horizons"][h]["features"] for h in horizons}),
        "blend_features_final_fit": {h: spec["horizons"][h]["features"] for h in horizons},
        "candidate_features": FEATURE_NAMES,
        "xgb_params": {**XGB_PARAMS, "monotone_constraints": dict(zip(FEATURE_NAMES, monotone_constraints()))},
        "universe": {"min_adv_cr": MIN_ADV_CR, "min_days_listed": MIN_DAYS_LISTED,
                     "format": "non_financial (banks/NBFCs/insurers excluded)",
                     "stale_financials_days": STALE_FINANCIALS_DAYS,
                     "visibility": "filing_date <= signal date 00:00"},
        "panel": {"rows": len(ranked), "companies": int(ranked["company_id"].nunique()), **stats},
        "walkforward": {},
        "market_model_comparison": {h: {"corr_mean": round(m["corr_mean"], 4),
                                        "per_year": [{k: round(v, 4) if isinstance(v, float) else v
                                                      for k, v in r.items()} for r in m["per_year"]]}
                                    for h, m in market.items()},
        "scored_signal_date": str(latest.date()), "companies_scored": len(scores),
    }
    for h in horizons:
        s = summaries[h]
        meta["walkforward"][h] = {
            **{k: (round(v, 4) if isinstance(v, float) else v) for k, v in s[winner].items()},
            "years_top10_above_universe": f"{s[winner]['years_top10_above_universe']}/{s[winner]['n_years']}",
            "years_ic_positive": f"{s[winner]['years_ic_positive']}/{s[winner]['n_years']}",
            "years_bot10_below_universe": f"{s[winner]['years_bot10_below_universe']}/{s[winner]['n_years']}",
            "test_years": sorted(int(y) for y in wf[h][0].year.unique()),
            "all_methods": {m: {k: (round(v, 4) if isinstance(v, float) else v) for k, v in s[m].items()}
                            for m in METHODS},
            "per_year": table(h),
            "blend_features_by_test_year": {str(y): sel for y, sel in selections[h].items()},
        }
    (MODELS_DIR / "financial_model_meta.json").write_text(json.dumps(meta, indent=2, default=str))

    print(f"\n{len(scores):,} companies scored on {latest:%Y-%m-%d}; top 15 financial scores:")
    for _, r in scores.head(15).iterrows():
        print(f"  {str(r.symbol):<14}{r.financial_score:>6.1f}  {r.top_positive}")
    print(f"\ndone in {time.time() - t0:.0f}s")


if __name__ == "__main__":
    main()
