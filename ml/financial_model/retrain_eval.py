"""Retrain test after the 2026-10-02 backfill (legacy balance-sheet totals, bank standalone filings).

Everything below (variants, metrics, pass rule, how the combiner and the bank recipe are re-tested)
was written before any of the tests were run. Report: financial_model/RETRAIN_2026-10.md.

Data
----
    old       the feature cache from before the backfill (ml/data/processed/financial_features.pkl
              as of 2026-09-30, copied aside before `train --refresh`; pass it with --old-features)
    new       the refreshed cache (`python3 -m financial_model.train --refresh`, one SELECT)
    new_roe   the same raw filings with financials.features roe_owners_fallback=True (opt-in: ROE
              falls back to owners' equity / owners' profit where total equity is missing)
All three use the same label file (growth_model/labels.py cache) and market features, so the only
difference between them is the financial data.

Variants (financial score)
--------------------------
    F0_old     fin-v1 (prelim-v2 financial blend, model.baseline_score) on `old`     reference only
    blend_old  data-selected blend on `old` (the candidate that lost in September)    reference only
    F0         fin-v1 on `new` (no code change, longer history)                      the reference
    F1         fin-v1 on `new_roe` (F0 + ROE fallback)                                candidate
    F2         data-selected blend (model.blend_score, selection on training years only) on `new`  candidate
    F3         data-selected blend on `new_roe`                                       candidate
Walk-forward exactly as financial_model/train.py (`train.walk_forward`: test years 2020.., purge
190 / 375 days, blend features selected from training-year ICs only), metrics from
growth_model.market_model.evaluate, summarised by train.summarise.

Combined score (investiq-v1 at its live weight)
-----------------------------------------------
Rows as rankings/combiner_eval.py Part A: walk-forward test rows that the live ranking could rank
(a growth component, >= 2 growth sub-features) and that have a trend score. financial = per-date
percentile of the variant's out-of-sample score among those rows, market = trend6 percentile in
the liquid universe (combiner_eval.market_panel), combined = 0.7 x market + 0.3 x financial (news
has no history and a constant does not change the order). Per year (2020..) IC / decile spread,
then the mean of the years (combiner_eval.yearly / summary).

Pass rule (a candidate replaces fin-v1 only if ALL hold, on BOTH 6m and 12m, vs F0)
-----------------------------------------------------------------------------------
    financial-only mean yearly IC        > F0's
    financial-only mean yearly spread    > F0's
    financial-only years with IC > 0    >= F0's
    combined (0.7/0.3) mean yearly IC    > F0's
Best candidate = the passing one with the highest combined IC averaged over 6m and 12m; none
passing -> keep fin-v1 (F0).

Combiner weight re-test
-----------------------
combiner_eval Part A (walk-forward choice of w on W_GRID by stability-penalised IC, then the live
w on all labelled years) re-run on F0's data and, if a candidate passes, on the best candidate.
For a baseline-type candidate (F1) this is combiner_eval unchanged with that feature table. For a
blend-type candidate the financial score only exists out of sample (test years 2020..), so the
w walk-forward uses only those rows (first w test year 2021) and is compared with F0 on the same
years.

Banks / NBFCs / insurers
------------------------
combiner_eval Part B (recipe vs trend vs trend_pen, adoption rule `adopt_fin_recipe`) on the
refreshed fin_sector extract, and the same on bank rows only (peer percentiles unchanged; IC over
banks, >= 15 per date). "Before" = the refreshed extract with what the backfill added removed
(INDUSINDBK, and bank standalone filings for periods that also have a consolidated filing: the old
collector kept only the consolidated one), an approximation of the pre-backfill extract (the old
file was overwritten). Also financials.fin_sector_eval's per-feature ICs for banks (NPA, CET1).
The bank recipe "beats trend" only if adopt_fin_recipe's rule holds on the bank rows.

CLI:  caffeinate -i python3 -m financial_model.retrain_eval --old-features <old financial_features.pkl>
"""

import argparse
import functools
import json
import time
import warnings

import numpy as np
import pandas as pd

from growth_model.labels import LABELS_FILE
from growth_model.prices import CACHE_DIR

HORIZONS = ["6m", "12m"]
COMBINER_W = 0.7
FIRST_TEST_YEAR = 2020
VARIANTS = {
    "F0_old": ("old", "baseline"),
    "blend_old": ("old", "blend"),
    "F0": ("new", "baseline"),
    "F1": ("new_roe", "baseline"),
    "F2": ("new", "blend"),
    "F3": ("new_roe", "blend"),
}
REFERENCE = "F0"
CANDIDATES = ["F1", "F2", "F3"]
COVERAGE_FEATURES = ["roe", "roce", "debt_to_equity", "current_ratio", "accruals_ratio", "flag_negative_equity",
                     "debt_to_equity_change_1y", "receivables_minus_revenue_growth", "cash_conversion",
                     "revenue_ttm_growth"]
OUT_FILE = CACHE_DIR / "retrain_eval_2026-10.json"


def passes(summ, comb, cand, ref=REFERENCE):
    """Pre-declared pass rule -> (bool, list of failed checks)."""
    failed = []
    for h in HORIZONS:
        c, r = summ[cand][h], summ[ref][h]
        if not c["ic_mean"] > r["ic_mean"]:
            failed.append(f"{h} fin IC {c['ic_mean']:.4f} <= {r['ic_mean']:.4f}")
        if not c["spread_mean"] > r["spread_mean"]:
            failed.append(f"{h} fin spread {c['spread_mean']:+.4f} <= {r['spread_mean']:+.4f}")
        if not c["years_ic_positive"] >= r["years_ic_positive"]:
            failed.append(f"{h} years IC>0 {c['years_ic_positive']} < {r['years_ic_positive']}")
        if not comb[cand][h]["ic_mean"] > comb[ref][h]["ic_mean"]:
            failed.append(f"{h} combined IC {comb[cand][h]['ic_mean']:.4f} <= {comb[ref][h]['ic_mean']:.4f}")
    return not failed, failed


# ---------------------------------------------------------
# Coverage
# ---------------------------------------------------------

def coverage_tables(tables, panels):
    out = {}
    for name, t in tables.items():
        t = t.assign(year=pd.to_datetime(t["period_end"]).dt.year)
        cov = t.groupby("year")[[c for c in COVERAGE_FEATURES if c in t]].agg(lambda s: s.notna().mean())
        cov.insert(0, "rows", t.groupby("year").size())
        out[f"table_{name}"] = cov
    for name, p in panels.items():
        p = p.assign(year=p["signal_date"].dt.year)
        cov = p.groupby("year")[[c for c in COVERAGE_FEATURES if c in p]].agg(lambda s: s.notna().mean())
        cov.insert(0, "rows", p.groupby("year").size())
        out[f"panel_{name}"] = cov
    return out


def raw_coverage(raw_old, raw_new):
    rows = []
    for name, raw in (("old", raw_old), ("new", raw_new)):
        r = raw[raw["period_end"].dt.month == 3].assign(year=raw["period_end"].dt.year)
        g = r.groupby("year")
        d = pd.DataFrame({"n": g.size(), "total_assets": g["bs_total_assets"].apply(lambda s: s.notna().mean()),
                          "total_equity": g["bs_total_equity"].apply(lambda s: s.notna().mean())})
        if "bs_equity_owners" in r:
            d["equity_owners"] = g["bs_equity_owners"].apply(lambda s: s.notna().mean())
        d["data"] = name
        rows.append(d.reset_index())
    return pd.concat(rows)


# ---------------------------------------------------------
# Walk-forward per data set
# ---------------------------------------------------------

def run_dataset(name, features, labels):
    from rankings.combiner_eval import fin_components

    from . import train
    from .data import build_panel, rank_features
    from .model import baseline_score, daily_ics

    panel, stats = build_panel(labels=labels, features=features)
    ranked = rank_features(panel)
    ranked["baseline_raw"] = baseline_score(panel)
    ranked["rankable"] = fin_components(panel)["growth"].notna()
    print(f"[{name}] panel {len(ranked):,} rows, {ranked['company_id'].nunique():,} companies; {stats}")
    res = {"panel": panel, "stats": stats, "h": {}}
    for h in HORIZONS:
        data = ranked[ranked[f"excess_{h}"].notna() & ranked[f"top_q_{h}"].notna()]
        ics = daily_ics(data, h)
        results, scored, sel = train.walk_forward(ranked, ics, h)
        summ = train.summarise(results, scored, h, train.METHODS)
        res["h"][h] = {"results": results, "scored": scored, "selections": sel, "summary": summ}
    return res


def combined(scored, method, market, h):
    from rankings.combiner_eval import summary, yearly

    df = scored[scored["rankable"]].merge(market, on=["company_id", "signal_date"], how="inner")
    df["financial"] = df.groupby("signal_date")[method].rank(pct=True)
    df["combo"] = COMBINER_W * df["market"] + (1 - COMBINER_W) * df["financial"]
    per = yearly(df, "combo", h, FIRST_TEST_YEAR)
    return summary(per), per


# ---------------------------------------------------------
# Combiner weight re-test (combiner_eval Part A)
# ---------------------------------------------------------

def combiner_weights(features, labels, blend_scores=None):
    """combiner_eval Part A with `features` as the financial feature table.

    blend_scores: {h: Series of out-of-sample blend scores keyed by (company_id, signal_date)} for a
    blend-type variant (replaces fin_raw; only rows with a score are used)."""
    import financial_model.data as fdata
    import rankings.combiner_eval as ce

    original = fdata.build_panel
    fdata.build_panel = functools.partial(original, features=features)
    try:
        panel, _ = ce.nonfin_panel(labels)
    finally:
        fdata.build_panel = original
    out, all_obj = {}, {}
    for h in HORIZONS:
        p = panel
        if blend_scores is not None:
            s = blend_scores[h].rename("fin_raw")
            p = panel.drop(columns=["fin_raw"]).merge(s.reset_index(), on=["company_id", "signal_date"], how="inner")
            p["financial"] = p.groupby("signal_date")["fin_raw"].rank(pct=True)
            for x in ce.W_GRID:
                p[f"mix_{x}"] = x * p["market"] + (1 - x) * p["financial"]
        scored, chosen = ce.walk_forward(p, h)
        first = min(chosen) if chosen else FIRST_TEST_YEAR
        per = {m: ce.yearly(scored, col, h, first) for m, col in
               {"combiner_wf": "combiner_wf", "mix_0.7": "mix_0.7", "trend6": "mix_1.0", "financial": "mix_0.0"}.items()}
        data = p[p[f"excess_{h}"].notna() & p[f"top_q_{h}"].notna()]
        _, obj = ce.choose_w(data, h)
        all_obj[h] = obj
        out[h] = {"chosen_w_by_test_year": {int(y): w for y, w in chosen.items()},
                  "summary": {m: ce.summary(t) for m, t in per.items()},
                  "objective_all_years": {str(k): round(v, 4) for k, v in obj.items()}}
    avg = {x: float(np.mean([all_obj[h][x] for h in HORIZONS])) for x in ce.W_GRID}
    out["final_w"] = max(ce.W_GRID, key=lambda x: (round(avg[x], 12), x))
    out["objective_avg"] = {str(k): round(v, 4) for k, v in avg.items()}
    return out


# ---------------------------------------------------------
# Banks
# ---------------------------------------------------------

def approx_old_extract(table):
    t = table[table["symbol"] != "INDUSINDBK"]
    is_bank = t["company_format"] == "bank"
    cons = set(map(tuple, t.loc[is_bank & (t["statement_type"] == "consolidated"), ["symbol", "period_end"]].values))
    drop = is_bank & (t["statement_type"] == "standalone") & \
        pd.Series([(s, p) in cons for s, p in zip(t["symbol"], t["period_end"])], index=t.index)
    return t[~drop].copy()


def bank_eval(extract, labels):
    import financials.fin_sector_eval as fse
    import financials.fin_sector_features as fsf
    import rankings.combiner_eval as ce

    orig_fsf, orig_fse = fsf.load_extract, fse.load_extract
    fsf.load_extract = fse.load_extract = lambda *a, **k: extract
    try:
        fpanel, _ = ce.fin_panel(labels)
        fe_panel, _ = fse.load_panel()
    finally:
        fsf.load_extract, fse.load_extract = orig_fsf, orig_fse
    out = {"rows": len(fpanel), "companies": int(fpanel["company_id"].nunique())}
    banks = fpanel[fpanel["segment"] == "bank"]
    out["bank_rows"], out["bank_companies"] = len(banks), int(banks["company_id"].nunique())
    out["bank_names_per_date_median"] = float(banks.groupby("signal_date").size().median())
    out["bank_coverage"] = {c: round(float(banks[c].notna().mean()), 3)
                            for c in ("gross_npa_pct", "net_npa_pct", "cet1_ratio", "provision_coverage")
                            if c in banks}
    out["bank_score_health_coverage"] = round(float(banks["score_financial_health"].notna().mean()), 3)
    for scope, d0 in (("all", fpanel), ("bank", banks)):
        res, per_all = {}, {}
        for h in HORIZONS:
            d = d0[d0[f"excess_{h}"].notna()]
            per = {m: ce.fin_yearly(d, m, h) for m in ("recipe", "trend", "trend_pen")}
            res[h] = {m: {"ic_mean": float(t["ic"].mean()), "spread_mean": float(t["spread"].mean()),
                          "years_ic_positive": f"{int((t['ic'] > 0).sum())}/{len(t)}"} if len(t) else None
                      for m, t in per.items()}
            per_all[h] = {m: t.round(4).to_dict("records") for m, t in per.items()}
        ok = all(res[h][m] is not None for h in HORIZONS for m in ("recipe", "trend"))
        out[scope] = {"summary": res, "per_year": per_all, "adopt_recipe": bool(ok and ce.adopt_fin_recipe(res))}
    # per-feature ICs for banks (fin_sector_eval, prior-signed)
    bp = fe_panel[fe_panel["company_format"] == "bank"]
    feats = [f for f in fse.DIRECTIONS if f in bp.columns]
    out["bank_feature_ic"] = {}
    for h in HORIZONS:
        result, spreads, _ = fse.evaluate(bp, h, feats)
        keep = result[result["feature"].isin(["gross_npa_pct", "net_npa_pct", "gross_npa_change_1y", "net_npa_change_1y",
                                               "cet1_ratio", "cet1_change_1y", "provision_coverage", "roa_reported",
                                               "flag_asset_quality_worsening", "blend_fixed", "blend_wf", "trend6"])]
        out["bank_feature_ic"][h] = {"features": keep.round(4).to_dict("records"),
                                     "spreads": {c: s.round(4).reset_index().to_dict("records") for c, s in spreads.items()}}
    return out


# ---------------------------------------------------------
# Main
# ---------------------------------------------------------

def _clean(o):
    if isinstance(o, dict):
        return {str(k): _clean(v) for k, v in o.items()}
    if isinstance(o, (list, tuple)):
        return [_clean(v) for v in o]
    if isinstance(o, (np.floating, float)):
        return None if np.isnan(o) else round(float(o), 5)
    if isinstance(o, np.integer):
        return int(o)
    if isinstance(o, pd.DataFrame):
        return _clean(o.reset_index().to_dict("records"))
    return o


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--old-features", required=True)
    ap.add_argument("--old-raw", required=True)
    ap.add_argument("--skip-banks", action="store_true")
    args = ap.parse_args(argv)
    warnings.filterwarnings("ignore")
    pd.set_option("display.width", 250)
    t0 = time.time()

    from rankings.combiner_eval import market_panel

    from .data import load_feature_table

    labels = pd.read_pickle(LABELS_FILE)
    tables = {"old": pd.read_pickle(args.old_features)}
    tables["new"], raw_new = load_feature_table()
    tables["new_roe"], _ = load_feature_table(roe_owners_fallback=True)
    out = {"variants": VARIANTS, "pass_rule": passes.__doc__}

    runs = {name: run_dataset(name, t, labels) for name, t in tables.items()}
    cov = coverage_tables(tables, {n: r["panel"] for n, r in runs.items()})
    rc = raw_coverage(pd.read_pickle(args.old_raw), raw_new)
    print("\n=== raw March filings: share with balance-sheet totals ===")
    print(rc.round(3).to_string(index=False))
    for k, v in cov.items():
        print(f"\n=== coverage {k} ===")
        print(v.round(3).to_string())
    out["coverage"] = {k: _clean(v) for k, v in cov.items()}
    out["raw_coverage"] = _clean(rc.to_dict("records"))

    market = market_panel(labels)
    summ, comb, per_year, comb_year = {}, {}, {}, {}
    for v, (data, method) in VARIANTS.items():
        summ[v], comb[v], per_year[v], comb_year[v] = {}, {}, {}, {}
        for h in HORIZONS:
            r = runs[data]["h"][h]
            summ[v][h] = r["summary"][method]
            res = r["results"]
            per_year[v][h] = res[res.method == method][["year", "ic", "spread", "top10", "bot10", "universe"]]
            comb[v][h], comb_year[v][h] = combined(r["scored"], method, market, h)
    print("\n=== variants: financial-only walk-forward and combined 0.7/0.3 ===")
    print(f"{'variant':<10}{'h':<5}{'fin IC':>8}{'spread':>9}{'yrs IC>0':>10}{'IC 2022+':>10}"
          f"{'comb IC':>9}{'comb spr':>10}{'comb yrs':>10}")
    for v in VARIANTS:
        for h in HORIZONS:
            s, c = summ[v][h], comb[v][h]
            print(f"{v:<10}{h:<5}{s['ic_mean']:>8.4f}{s['spread_mean']:>+9.1%}{s['years_ic_positive']:>7}/{s['n_years']}"
                  f"{s['ic_mean_2022_on']:>10.4f}{c['ic_mean']:>9.4f}{c['spread_mean']:>+10.1%}{c['years_ic_positive']:>10}")
    print("\n=== per year (fin IC / spread | combined IC / spread) ===")
    for h in HORIZONS:
        for v in VARIANTS:
            py, cy = per_year[v][h].set_index("year"), comb_year[v][h].set_index("year")
            print(f"{h} {v:<10}" + "  ".join(f"{y}: {py.loc[y, 'ic']:+.3f}/{py.loc[y, 'spread']:+.1%}|"
                                            f"{cy.loc[y, 'ic']:+.3f}/{cy.loc[y, 'spread']:+.1%}"
                                            for y in py.index if y in cy.index))
    verdict = {}
    for c in CANDIDATES:
        ok, failed = passes(summ, comb, c)
        verdict[c] = {"passes": ok, "failed": failed}
        print(f"\n{c}: {'PASSES' if ok else 'fails'}" + ("" if ok else ": " + "; ".join(failed)))
    passing = [c for c in CANDIDATES if verdict[c]["passes"]]
    best = max(passing, key=lambda c: np.mean([comb[c][h]["ic_mean"] for h in HORIZONS])) if passing else REFERENCE
    print(f"\nbest financial variant: {best}")
    sel = {v: {h: {str(y): s for y, s in runs[VARIANTS[v][0]]["h"][h]["selections"].items()} for h in HORIZONS}
           for v in VARIANTS if VARIANTS[v][1] == "blend"}
    out.update({"summary": summ, "combined": comb, "per_year": {v: {h: per_year[v][h] for h in HORIZONS} for v in VARIANTS},
                "combined_per_year": {v: {h: comb_year[v][h] for h in HORIZONS} for v in VARIANTS},
                "verdict": verdict, "best": best, "blend_selections": sel})

    # combiner weights
    cw = {"F0": combiner_weights(tables["new"], labels)}
    if best != REFERENCE:
        data, method = VARIANTS[best]
        if method == "baseline":
            cw[best] = combiner_weights(tables[data], labels)
        else:
            bs = {h: runs[data]["h"][h]["scored"].set_index(["company_id", "signal_date"])["blend"] for h in HORIZONS}
            cw[best] = combiner_weights(tables[data], labels, blend_scores=bs)
            cw["F0_same_years"] = combiner_weights(
                tables["new"], labels,
                blend_scores={h: runs["new"]["h"][h]["scored"].set_index(["company_id", "signal_date"])["baseline"]
                              for h in HORIZONS})
    for k, r in cw.items():
        print(f"\ncombiner weights on {k}: live w = {r['final_w']}; objective avg {r['objective_avg']}")
        for h in HORIZONS:
            print(f"  {h} chosen by year {r[h]['chosen_w_by_test_year']}")
            for m, s in r[h]["summary"].items():
                print(f"    {m:<12} IC {s['ic_mean']:.4f} spread {s['spread_mean']:+.1%} yrs IC>0 {s['years_ic_positive']}")
    out["combiner_weights"] = cw

    if not args.skip_banks:
        from financials.fin_sector_features import load_extract
        ext = load_extract()
        banks = {"after": bank_eval(ext, labels), "before_approx": bank_eval(approx_old_extract(ext), labels)}
        for k, b in banks.items():
            print(f"\n=== fin sector {k}: {b['rows']:,} rows, {b['companies']} companies; banks {b['bank_rows']:,} rows, "
                  f"{b['bank_companies']} banks, median {b['bank_names_per_date_median']}/date; coverage {b['bank_coverage']}")
            for scope in ("all", "bank"):
                for h in HORIZONS:
                    print(f"  {scope:<5}{h:<4}" + "  ".join(
                        f"{m} IC {s['ic_mean']:+.3f} spr {s['spread_mean']:+.1%} yrs {s['years_ic_positive']}"
                        for m, s in b[scope]["summary"][h].items() if s))
                print(f"  {scope}: recipe adopted = {b[scope]['adopt_recipe']}")
            for h in HORIZONS:
                print(f"  bank feature ICs {h}:")
                for r in b["bank_feature_ic"][h]["features"]:
                    print(f"    {r['feature']:<30} ic {r['ic']:+.3f} yrs+ {r['yrs_pos']} names {r['names']}")
        out["banks"] = banks

    OUT_FILE.write_text(json.dumps(_clean(out), indent=1, default=str))
    print(f"\nwrote {OUT_FILE} in {time.time() - t0:.0f}s")


if __name__ == "__main__":
    main()
