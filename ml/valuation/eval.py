"""Does a valuation signal add out-of-sample ranking skill on top of investiq-v1?

Rows: exactly the combiner_eval Part A panel (rankings/combiner_eval.nonfin_panel): label grid
(1st/16th), liquid universe (>= 0.5 cr/day, >= 252 trading days), fresh point-in-time financials,
rankable rows only. investiq-v1's order on these rows = `mix_0.7` = 0.70 market + 0.30 financial
(news is a constant 50 in the backtest and the negative-equity penalty is left out, as in
combiner_eval; the Top-list backtest below includes it). Banks / NBFCs / insurers are NOT in this
panel (financials/features.py is non_financial only): they are excluded from the valuation test and
keep today's trend-led score in the Top-list backtest.

Valuation features: valuation/features.py (point-in-time, split-corrected market cap).

PRE-DECLARED (written before any return-based result was looked at)
--------------------------------------------------------------------
Signals (per-date percentiles 0-1 among the panel rows, higher = cheaper):
    V1_ey    earnings yield  TTM net profit / mcap   (loss-makers kept, they rank at the bottom)
    V2_bp    book-to-price   owners' equity / mcap   (annual-only equity before Sep 2022)
    V3_sp    sales-to-price  TTM revenue / mcap
    V4_blend equal blend of the SECTOR-RELATIVE percentiles of ey, bp, sp (>= 2 of 3 available),
             re-percentiled per date
Combination with investiq-v1 (value weight v taken proportionally from market and financial):
    score(sig, v) = (1 - v) x (0.70 market + 0.30 financial) + v x sig       v in {0.10, 0.20, 0.30}
    (= market 0.70(1-v), financial 0.30(1-v), value v; the 0.05 news slot is unchanged.)
    A missing value percentile counts as neutral 0.5 (as missing trend signals in trend6).
Walk-forward choice (as combiner_eval.choose_w): for test year Y and horizon h the training set is
every signal date whose label window ended before Y (PURGE_DAYS 190 / 375 days); among investiq-v1
(v = 0) and the 12 candidates the one maximising mean(yearly IC) - 0.5 x std(yearly IC) on the training
years is used for Y (ties -> investiq-v1). Test years 2020 .. last labelled.
PASS RULE: the walk-forward value score ("value_wf") must beat investiq-v1 on the same rows on BOTH
horizons in mean yearly IC AND mean yearly top-minus-bottom-decile spread, with no fewer years of
positive IC. Otherwise: do not ship.
"Best candidate" (for the Top-list backtest and time-machine windows, shown whether or not it passes):
the same objective on all labelled years, averaged over 6m and 12m, among the 12 candidates only.
Diagnostics (declared, not used for the decision): stand-alone yearly IC of every value feature
(overall, within sector, own 3-year history, FCF yield), mean per-date Spearman correlation with the
market and financial scores, IC by NIFTY SMALLCAP 250 drawdown regime at D (no regime switch is
built: that was tested and failed, docs/model-report.md 4.1), post-crash dates (Apr-Jun 2020), and the
whole test on companies with no detected split / bonus (share-count robustness).

Top list: portfolio_eval.simulate with portfolio.RECOMMENDED (and plain top 50) on investiq-v1 vs
the best candidate (non-financial scores swapped, lenders unchanged), 0.3% per side.
Time machine (panel version): on each time_machine.EVENTS start date D, rank the panel rows (the
liquid tested universe, not every listed name like TIME_MACHINE.md), buy at the first close after D,
hold to the window end: IC, top-50 equal-weight return, all ranked, Smallcap 250.

Outputs: ml/data/processed/valuation_eval.json (+ printed tables). Report: ml/valuation/REPORT.md.
CLI:  cd ml && caffeinate -i python3 -m valuation.eval [--skip-truncation]
"""

import argparse
import json
import time
import warnings

import numpy as np
import pandas as pd

from growth_model.market_model import CLIP, PURGE_DAYS, evaluate
from growth_model.prices import BENCHMARK, CACHE_DIR, INDEX_CACHE, STOCK_CACHE
from rankings.combiner_eval import (FIN_PENALTY, STABILITY_PENALTY, fin_panel, nonfin_panel, objective,
                                    penalty_points, summary, yearly)

from . import features as vf

HORIZONS = ["6m", "12m"]
FIRST_TEST_YEAR = 2020
BASE_MARKET_W = 0.70
VALUE_WEIGHTS = [0.10, 0.20, 0.30]
SIGNALS = {"V1_ey": "p_ey", "V2_bp": "p_bp", "V3_sp": "p_sp", "V4_blend": "v4"}
CANDIDATES = {f"{s}@{v:.2f}": (col, v) for s, col in SIGNALS.items() for v in VALUE_WEIGHTS}
BASE = "investiq_v1"
DIAG_FEATURES = ["p_ey", "p_bp", "p_sp", "p_fcfy", "s_ey", "s_bp", "s_sp", "s_fcfy", "v4", "own_ey"]
DD_BUCKETS = [(-1.0, -0.20, "index >= 20% below 1y high"), (-0.20, -0.10, "10-20% below"),
              (-0.10, 0.01, "within 10% of high")]
POST_CRASH = ("2020-04-01", "2020-06-16")
TRUNCATION_DATES = ["2019-07-01", "2020-04-16", "2022-11-16", "2024-06-01", "2026-03-16"]
OUT_FILE = CACHE_DIR / "valuation_eval.json"


# ---------------------------------------------------------
# Panel
# ---------------------------------------------------------

def build(labels):
    from growth_model.prices import load_companies

    panel, stats = nonfin_panel(labels)
    sectors = load_companies()[["company_id", "sector"]]
    panel, info = vf.add_valuation(panel, sectors=sectors)
    have = panel[["s_ey", "s_bp", "s_sp"]]
    raw4 = have.mean(axis=1).where(have.notna().sum(axis=1) >= 2)
    panel["v4"] = vf._pct(raw4, panel["signal_date"])
    panel[BASE] = BASE_MARKET_W * panel["market"] + (1 - BASE_MARKET_W) * panel["financial"]
    for name, (col, v) in CANDIDATES.items():
        panel[name] = (1 - v) * panel[BASE] + v * panel[col].fillna(0.5)
    return panel, stats, info


# ---------------------------------------------------------
# Walk-forward
# ---------------------------------------------------------

def choose(train, h, names):
    best, best_obj = BASE, objective(yearly(train, BASE, h, 0))
    for n in names:
        obj = objective(yearly(train, n, h, 0))
        if obj > best_obj + 1e-12:
            best, best_obj = n, obj
    return best


def walk_forward(panel, h):
    data = panel[panel[f"excess_{h}"].notna() & panel[f"top_q_{h}"].notna()]
    chosen, scored = {}, []
    for year in range(FIRST_TEST_YEAR, data["signal_date"].max().year + 1):
        cutoff = pd.Timestamp(year, 1, 1) - pd.Timedelta(days=PURGE_DAYS[h])
        train = data[data["signal_date"] < cutoff]
        test = data[data["signal_date"].dt.year == year].copy()
        if len(test) == 0 or train["signal_date"].nunique() < 6:
            continue
        pick = choose(train, h, list(CANDIDATES))
        chosen[year] = pick
        test["value_wf"] = test[pick]
        scored.append(test)
    return pd.concat(scored), chosen


def passes(summ):
    ok = {}
    for h in HORIZONS:
        b, v = summ[h][BASE], summ[h]["value_wf"]
        yb, yv = int(b["years_ic_positive"].split("/")[0]), int(v["years_ic_positive"].split("/")[0])
        ok[h] = {"ic": v["ic_mean"] > b["ic_mean"], "spread": v["spread_mean"] > b["spread_mean"],
                 "years_positive": yv >= yb}
    return all(all(x.values()) for x in ok.values()), ok


def run_wf(panel, label):
    out, summ = {}, {}
    for h in HORIZONS:
        scored, chosen = walk_forward(panel, h)
        cols = [BASE, "value_wf", *CANDIDATES]
        per = {c: yearly(scored, c, h, FIRST_TEST_YEAR) for c in cols}
        summ[h] = {c: summary(t) for c, t in per.items()}
        out[h] = {"chosen_by_year": {str(y): c for y, c in chosen.items()}, "summary": summ[h],
                  "per_year": {c: t.round(4).to_dict("records") for c, t in per.items()}}
        print(f"\n[{label}] {h}: chosen per test year {chosen}")
        print(f"  {'score':<16}{'IC':>8}{'spread':>9}{'top10-all':>11}{'yrs IC>0':>10}   per-year IC")
        for c in cols:
            s = summ[h][c]
            yrs = " ".join(f"{int(r.year)}:{r.ic:+.3f}" for r in per[c].itertuples())
            print(f"  {c:<16}{s['ic_mean']:>8.4f}{s['spread_mean']:>+9.1%}{s['top10_minus_universe_mean']:>+11.1%}"
                  f"{s['years_ic_positive']:>10}   {yrs}")
    ok, detail = passes(summ)
    out["pass"], out["pass_detail"] = ok, detail
    print(f"[{label}] PASS RULE: {ok} {detail}")
    return out


def best_candidate(panel):
    objs = {}
    for name in CANDIDATES:
        o = []
        for h in HORIZONS:
            data = panel[panel[f"excess_{h}"].notna() & panel[f"top_q_{h}"].notna()]
            o.append(objective(yearly(data, name, h, 0)))
        objs[name] = float(np.mean(o))
    base_o = []
    for h in HORIZONS:
        data = panel[panel[f"excess_{h}"].notna() & panel[f"top_q_{h}"].notna()]
        base_o.append(objective(yearly(data, BASE, h, 0)))
    return max(objs, key=objs.get), objs, float(np.mean(base_o))


# ---------------------------------------------------------
# Diagnostics
# ---------------------------------------------------------

def coverage(panel):
    rows = []
    for y, g in panel.groupby(panel["signal_date"].dt.year):
        pe = (1 / g["ey"]).where(g["ey"] > 0)
        rows.append({"year": int(y), "rows": len(g), "names_per_date": int(g.groupby("signal_date").size().median()),
                     "mcap": g["mcap_cr"].notna().mean(), "ey": g["ey"].notna().mean(), "bp": g["bp"].notna().mean(),
                     "sp": g["sp"].notna().mean(), "fcfy": g["fcfy"].notna().mean(), "v4": g["v4"].notna().mean(),
                     "own_ey": g["own_ey"].notna().mean(), "loss_makers": (g["ey"] < 0).mean(),
                     "median_pe": float(pe.median()), "median_pb": float((1 / g["bp"]).where(g["bp"] > 0).median()),
                     "median_mcap_cr": float(g["mcap_cr"].median())})
    return pd.DataFrame(rows)


def per_date_ic(panel, col, h):
    out = {}
    for d, g in panel[panel[f"excess_{h}"].notna()].groupby("signal_date"):
        g = g[[col, f"excess_{h}"]].dropna()
        if len(g) >= 50:
            out[d] = g[col].rank().corr(g[f"excess_{h}"].rank())
    return pd.Series(out, dtype=float)


def standalone(panel):
    res = {}
    for h in HORIZONS:
        res[h] = {}
        for c in DIAG_FEATURES:
            ic = per_date_ic(panel, c, h)
            ic = ic[ic.index.year >= 2019]
            yr = ic.groupby(ic.index.year).mean()
            res[h][c] = {"ic_mean": float(yr.mean()), "years_positive": f"{int((yr > 0).sum())}/{len(yr)}",
                         "per_year": {int(k): round(float(v), 4) for k, v in yr.items()}}
    return res


def correlations(panel):
    out = {}
    for c in [*DIAG_FEATURES, "mcap_cr"]:
        r = {}
        for other in ("market", "financial", BASE):
            s = []
            for _, g in panel.groupby("signal_date"):
                g = g[[c, other]].dropna()
                if len(g) >= 50:
                    s.append(g[c].rank().corr(g[other].rank()))
            r[other] = float(np.mean(s)) if s else None
        out[c] = r
    return out


def bench_drawdown():
    idx = pd.read_pickle(INDEX_CACHE)
    b = idx[idx["index_key"] == BENCHMARK].set_index("price_date")["close"].sort_index()
    return b / b.rolling(252, min_periods=60).max() - 1, b


def regimes(panel, best):
    dd, _ = bench_drawdown()
    out = {}
    for h in HORIZONS:
        cols = {"value_V4": "v4", "value_V1": "p_ey", BASE: BASE, best: best}
        ics = pd.DataFrame({k: per_date_ic(panel, c, h) for k, c in cols.items()})
        ics = ics[ics.index.year >= 2019]
        ics["dd"] = dd.reindex(ics.index, method="ffill").values
        rows = []
        for lo, hi, lab in DD_BUCKETS:
            g = ics[(ics["dd"] > lo) & (ics["dd"] <= hi)]
            rows.append({"regime": lab, "dates": len(g), **{k: float(g[k].mean()) for k in cols},
                         "best_minus_base": float((g[best] - g[BASE]).mean())})
        pc = ics.loc[POST_CRASH[0]:POST_CRASH[1]]
        out[h] = {"buckets": rows,
                  "post_crash_dates": {str(d.date()): {k: round(float(r[k]), 4) for k in cols} for d, r in pc.iterrows()},
                  "by_year_best_minus_base": {int(y): round(float(v), 4) for y, v in
                                              (ics[best] - ics[BASE]).groupby(ics.index.year).mean().items()}}
    return out


# ---------------------------------------------------------
# Top list and time-machine windows
# ---------------------------------------------------------

def top_list_scores(panel, labels, best):
    from growth_model.market_model import FEATURES_FILE
    from growth_model.prices import load_companies

    fp, table = fin_panel(labels)
    in_scope = set(table["company_id"].dropna().astype(int))
    nf = panel[~panel["company_id"].isin(in_scope)]
    pen = penalty_points(nf, {"flag_negative_equity": 6})
    cols = ["company_id", "signal_date", "market", "adv_60d_cr", "days_listed"]
    fp_score = ((1 - 0.05) * fp["market"] * 100 + 0.05 * 50 - penalty_points(fp, FIN_PENALTY)).clip(0, 100)
    out = {}
    for name in (BASE, best):
        nf_score = ((1 - 0.05) * nf[name] * 100 + 0.05 * 50 - pen).clip(0, 100)
        s = pd.concat([nf[cols].assign(growth_score=nf_score.values, is_fin_sector=False),
                       fp[cols].assign(growth_score=fp_score.values, is_fin_sector=True)], ignore_index=True)
        out[name] = s.drop_duplicates(["company_id", "signal_date"])
    mk = pd.read_pickle(FEATURES_FILE)[["company_id", "signal_date", "vol_3m", "mom_6m", "ma200_gap"]]
    comp = load_companies()[["company_id", "symbol", "sector"]]
    for k in out:
        s = out[k].merge(mk, on=["company_id", "signal_date"], how="left").merge(comp, on="company_id", how="left")
        s = s.rename(columns={"adv_60d_cr": "adv_cr", "vol_3m": "volatility", "mom_6m": "return_6m"})
        s["market_score"] = s["market"] * 100
        out[k] = s
    return out


def top_list(scores_by, best):
    from rankings.portfolio import RECOMMENDED, Rules
    from rankings.portfolio_eval import MIN_NAMES, load_daily, metrics, simulate, window_stats
    from rankings.time_machine import EVENTS

    ret, bench, _ = load_daily()
    n_per = scores_by[BASE].groupby("signal_date").size()
    start = n_per[n_per >= MIN_NAMES].index.min()
    res, navs = {}, {}
    uni = simulate(scores_by[BASE][scores_by[BASE]["signal_date"] >= start], ret, bench, None, universe=True)
    bench_nav = bench.reindex(uni["nav"].index)
    bench_nav = bench_nav / bench_nav.iloc[0]
    for name, s in scores_by.items():
        s = s[s["signal_date"] >= start]
        for rl, rules in (("recommended", RECOMMENDED), ("top50", Rules(n=50))):
            r = simulate(s, ret, bench, rules)
            m = metrics(r, bench_nav, uni["gross"])
            key = f"{name} | {rl}"
            res[key] = {k: m[k] for k in ("cagr", "vs_index_cagr", "max_dd", "vol", "sharpe", "years_beat", "years",
                                          "turnover_yr", "per_year", "halves")}
            navs[key] = r["nav"]
            print(f"  {key:<40} CAGR {m['cagr']:+.1%}  vs idx {m['vs_index_cagr']:+.1%}  DD {m['max_dd']:+.1%} "
                  f" yrs {m['years_beat']}/{m['years']}  turn {m['turnover_yr']:.0%}")
    flat = {"nav": bench_nav, "gross": bench_nav, "turnover": pd.Series([0.0, 0.0]), "sizes": [0]}
    res["index"] = {k: v for k, v in metrics(flat, bench_nav, uni["gross"]).items() if k in ("cagr", "max_dd", "per_year")}
    win = {}
    for wname, d0, d1, _ in EVENTS:
        if pd.Timestamp(d0) < start:
            continue
        win[wname] = {k: window_stats(n, d0, d1) for k, n in navs.items()}
        win[wname]["index"] = window_stats(bench_nav, d0, d1)
    return {"start": str(start.date()), "results": res, "windows": win}


def snapshot_windows(scores_by, best, panel):
    """Rank on the window start (panel universe), buy next close, hold to the end."""
    from rankings.time_machine import EVENTS

    stocks, index = pd.read_pickle(STOCK_CACHE), pd.read_pickle(INDEX_CACHE)
    bench = index[index["index_key"] == BENCHMARK].set_index("price_date")["close"].sort_index()
    close = stocks[stocks["close"] > 0].pivot_table(index="price_date", columns="company_id", values="close",
                                                   aggfunc="last")
    out = {}
    for wname, d0, d1, _ in EVENTS:
        d = pd.Timestamp(d0)
        frames = {k: s[s["signal_date"] == d] for k, s in scores_by.items()}
        if len(frames[BASE]) < 100:
            out[wname] = {"skip": f"{len(frames[BASE])} ranked rows on {d0}"}
            continue
        days = bench.index[(bench.index > d) & (bench.index <= (pd.Timestamp(d1) if d1 else bench.index[-1]))]
        e0, e1 = days[0], days[-1]
        w = close.loc[(close.index >= e0) & (close.index <= e1)]
        daily = w.pct_change(fill_method=None)
        broken = ((daily > 1.0) | (daily < -0.6)).any()
        entry = w.iloc[0]
        r = (w.ffill().iloc[-1] / entry - 1).where(entry.notna() & ~broken)
        b_ret = float(bench.loc[e1] / bench.loc[e0] - 1)
        row = {"from": str(e0.date()), "to": str(e1.date()), "index": b_ret}
        tops = {}
        for k, f in frames.items():
            f = f.assign(ret=f["company_id"].map(r)).dropna(subset=["ret", "growth_score"])
            f = f.sort_values(["growth_score", "company_id"], ascending=[False, True])
            ic = f["growth_score"].rank().corr(f["ret"].rank())
            nfm = ~f["is_fin_sector"].astype(bool)
            tops[k] = set(f.head(50)["company_id"])
            row[k] = {"ic": float(ic), "ic_nonfin": float(f.loc[nfm, "growth_score"].rank().corr(f.loc[nfm, "ret"].rank())),
                      "top50": float(f.head(50)["ret"].mean()), "bottom50": float(f.tail(50)["ret"].mean()),
                      "all": float(f["ret"].mean()), "names": int(len(f))}
        row["top50_overlap"] = len(tops[BASE] & tops[best])
        # value alone on the non-financial rows
        pv = panel[panel["signal_date"] == d].assign(ret=lambda x: x["company_id"].map(r)).dropna(subset=["ret"])
        row["v4_ic"] = float(pv["v4"].rank().corr(pv["ret"].rank()))
        row["ey_ic"] = float(pv["p_ey"].rank().corr(pv["ret"].rank()))
        out[wname] = row
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
        return None if not np.isfinite(o) else round(float(o), 5)
    if isinstance(o, np.integer):
        return int(o)
    return o


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--skip-truncation", action="store_true")
    args = ap.parse_args(argv)
    warnings.filterwarnings("ignore")
    t0 = time.time()
    from growth_model.labels import LABELS_FILE

    labels = pd.read_pickle(LABELS_FILE)
    panel, stats, info = build(labels)
    out = {"declared": {"signals": SIGNALS, "value_weights": VALUE_WEIGHTS, "candidates": list(CANDIDATES),
                        "stability_penalty": STABILITY_PENALTY, "first_test_year": FIRST_TEST_YEAR},
           "panel": {"rows": len(panel), "companies": int(panel["company_id"].nunique()), **stats}}
    sev = info["split_events"]
    out["shares"] = {"split_events": len(sev), "split_companies": int(sev["company_id"].nunique()),
                     "uncertain_companies": len(sev.attrs.get("uncertain", [])),
                     "ratios": {str(round(k, 3)): int(v) for k, v in sev["ratio"].value_counts().sort_index().items()},
                     "validation": vf.validate_shares(vf.load_raw(), info["factors"])}
    print(f"panel {len(panel):,} rows, {panel['company_id'].nunique():,} companies ({time.time() - t0:.0f}s); "
          f"shares: {out['shares']}")
    if not args.skip_truncation:
        n = vf.truncation_check(vf.load_raw(), vf.load_equity_raw(), info["factors"], TRUNCATION_DATES,
                                panel[["company_id", "signal_date"]])
        out["truncation_check"] = f"passed: {n} share/equity values identical when filings after D are removed"
        print(out["truncation_check"], f"({time.time() - t0:.0f}s)")

    cov = coverage(panel)
    out["coverage"] = cov.round(4).to_dict("records")
    print("\ncoverage by year:\n" + cov.to_string(index=False, float_format=lambda x: f"{x:.3f}"))

    out["correlations"] = correlations(panel)
    print("\nmean per-date Spearman correlation:")
    for c, r in out["correlations"].items():
        print(f"  {c:<8} " + "  ".join(f"{k} {v:+.3f}" for k, v in r.items() if v is not None))

    out["standalone"] = standalone(panel)
    print("\nstand-alone IC (mean of yearly means, years positive):")
    for h in HORIZONS:
        for c, r in out["standalone"][h].items():
            print(f"  {h:<4}{c:<8}{r['ic_mean']:+.4f}  {r['years_positive']}  {r['per_year']}")

    out["walk_forward"] = run_wf(panel, "all")
    split_free = panel[~panel["split_company"]]
    out["walk_forward_split_free"] = run_wf(split_free, "no-split companies")

    best, objs, base_obj = best_candidate(panel)
    out["best_candidate"] = {"name": best, "objective_all_years": objs, "investiq_v1_objective": base_obj}
    print(f"\nbest candidate (all labelled years): {best}  obj {objs[best]:.4f} vs investiq-v1 {base_obj:.4f}")

    out["regimes"] = regimes(panel, best)
    for h in HORIZONS:
        print(f"\nregimes {h}:")
        for r in out["regimes"][h]["buckets"]:
            print("  " + "  ".join(f"{k} {v:+.3f}" if isinstance(v, float) else f"{k} {v}" for k, v in r.items()))
        print("  post-crash:", out["regimes"][h]["post_crash_dates"])

    print("\nTop list backtest:")
    scores_by = top_list_scores(panel, labels, best)
    out["top_list"] = top_list(scores_by, best)
    out["snapshot_windows"] = snapshot_windows(scores_by, best, panel)
    for w, r in out["snapshot_windows"].items():
        print(f"  {w}: {r}")
    OUT_FILE.write_text(json.dumps(_clean(out), indent=1, default=str))
    print(f"\nwrote {OUT_FILE} in {time.time() - t0:.0f}s")


if __name__ == "__main__":
    main()
