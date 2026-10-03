"""Historical test: do IPOs priced cheaply vs their listed peers do better after listing?

Data: ml/ipo/ipo_dataset.csv (ipo/dataset.py). Outcomes: listing-day gain (close vs issue price) and
1m/3m/6m/12m return from the listing-day close minus NIFTY SMALLCAP 250 (`exc_*`); `pit_exc_*` enters
at the first close after the proxy financials were filed (strictly point-in-time variant).

PRE-DECLARED (written in this file before any outcome column was looked at)
-------------------------------------------------------------------------
Sample ("test sample"): main-board IPOs (EQ/BE, not FPOs), non-financial companies, own financials
from a PRE-LISTING period (`fin_basis == "pre_listing"`), a post-issue share count, and at least one
peer-relative multiple (`rel_median` not null).

Signals (all point in time: each IPO is ranked only against IPOs that LISTED BEFORE its issue opened)
    cheap_pe, cheap_pb, cheap_ps   expanding percentile (0 = dearest, 1 = cheapest so far) of
                                   -rel_x = -log(IPO multiple / peer median); needs >= 30 earlier IPOs
                                   with that multiple; a loss-making IPO gets cheap_pe = 0
    VAL    = mean of the available cheap_* (>= 2 of 3)                         <- the IPO valuation score
    SUB    = expanding percentile of log(QIB subscription, times)             (known before listing)
    COMBO  = mean(VAL, SUB) (both required)
Buckets: terciles on the score (< 1/3 "expensive / low", 1/3-2/3 "middle", >= 2/3 "cheap / high").

PASS RULE (per score; VAL is the one that answers the owner's question):
    1. pooled mean exc of the top tercile > bottom tercile, on BOTH 6m and 12m
    2. in MORE THAN HALF of the calendar listing years that have >= 4 IPOs in both the top and the
       bottom tercile, top > bottom (mean exc), on BOTH 6m and 12m
    3. time split: rule 1 holds separately in the earlier and the later half of the SCORED sample
       (split at the median listing date; each half needs >= 10 IPOs in the top and the bottom
       tercile, otherwise that half is "not testable" and the rule fails)
       [amended before any outcome was looked at: coverage showed only ~20 scored IPOs listed up to
       2022 (pre-listing XBRL is sparse before 2023), so a fixed 2022/2023 split could never be tested]
    4. point-in-time check: rule 1 holds on pit_exc_6m and pit_exc_12m
    PASS = 1 and 2 and 3 and 4. Anything else: "no reliable predictive value" (the score may still be
    shown as a description, never as a forecast).
Diagnostics (declared, not used for the decision): medians, hit rates (exc > 0), Spearman IC of each
score vs each outcome, buckets of raw rel_median / verdict / loss-making, total-subscription buckets,
QIB buckets, listing-gain by bucket, market-condition buckets (Smallcap 250 drawdown, hot IPO market),
SME subscription buckets (descriptive; SME has no valuation test).

CLI (from ml/):  python3 -m ipo.eval            -> prints tables, writes ml/ipo/eval_results.json
"""

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd

PKG_DIR = Path(__file__).resolve().parent
DATA = PKG_DIR / "ipo_dataset.csv"
OUT = PKG_DIR / "eval_results.json"
MIN_PRIOR = 30
OUTCOMES = ["list_gain_close", "exc_1m", "exc_3m", "exc_6m", "exc_12m"]
DECISION = ["exc_6m", "exc_12m"]
MIN_YEAR_N = 4
MIN_HALF_N = 10
TERC = [-0.001, 1 / 3, 2 / 3, 1.001]
TERC_LABELS = ["bottom", "middle", "top"]


def load(path=DATA):
    df = pd.read_csv(path, low_memory=False)
    for c in ("issue_start", "issue_end", "listing_date", "fin_filing_date", "fin_period_end"):
        if c in df:
            df[c] = pd.to_datetime(df[c])
    return df


def test_sample(df):
    m = ((df["board"] == "mainboard") & ~df["is_fpo"].astype(bool) & (df["fin_basis"] == "pre_listing")
         & (df["fin_format"] == "non_financial") & df["shares_post"].notna() & df["rel_median"].notna())
    return df[m].sort_values("issue_start").reset_index(drop=True)


def expanding_pct(df, col, higher_is_better=True, fill=None):
    """Percentile of each row's value among rows that LISTED before its issue opened."""
    out = pd.Series(np.nan, index=df.index)
    vals = df[col] if higher_is_better else -df[col]
    for i, r in df.iterrows():
        v = vals[i]
        if pd.isna(v):
            continue
        prior = vals[(df["listing_date"] < r["issue_start"]) & vals.notna()]
        if len(prior) < MIN_PRIOR:
            continue
        out[i] = ((prior < v).sum() + 0.5 * (prior == v).sum()) / len(prior)
    return out


def add_scores(s):
    s = s.copy()
    for k in ("pe", "pb", "ps"):
        s[f"cheap_{k}"] = expanding_pct(s, f"rel_{k}", higher_is_better=False)
    # loss-makers: no P/E -> the dearest on P/E, once the expanding window is warm
    warm = s["cheap_ps"].notna() | s["cheap_pb"].notna()
    s.loc[s["loss_making"].astype(bool) & warm, "cheap_pe"] = 0.0
    c = s[["cheap_pe", "cheap_pb", "cheap_ps"]]
    s["VAL"] = c.mean(axis=1).where(c.notna().sum(axis=1) >= 2)
    s["log_qib"] = np.log(s["sub_qib"].clip(lower=0.01))
    s["SUB"] = expanding_pct(s, "log_qib")
    s["COMBO"] = s[["VAL", "SUB"]].mean(axis=1).where(s["VAL"].notna() & s["SUB"].notna())
    for sc in ("VAL", "SUB", "COMBO"):
        s[f"{sc}_terc"] = pd.cut(s[sc], TERC, labels=TERC_LABELS)
    return s


def bucket_table(s, by, outcomes=OUTCOMES, prefix=""):
    rows = []
    for b, g in s.groupby(by, observed=True):
        r = {"bucket": str(b), "n": int(len(g))}
        for o in outcomes:
            x = g[f"{prefix}{o}" if o != "list_gain_close" else o].dropna()
            r[f"{o}_n"] = int(len(x))
            r[f"{o}_mean"] = float(x.mean()) if len(x) else None
            r[f"{o}_median"] = float(x.median()) if len(x) else None
            r[f"{o}_hit"] = float((x > 0).mean()) if len(x) else None
        rows.append(r)
    return rows


def top_minus_bottom(s, score, col):
    t, b = s[s[f"{score}_terc"] == "top"][col].dropna(), s[s[f"{score}_terc"] == "bottom"][col].dropna()
    return {"top_n": int(len(t)), "bottom_n": int(len(b)), "top_mean": float(t.mean()) if len(t) else None,
            "bottom_mean": float(b.mean()) if len(b) else None,
            "diff_mean": float(t.mean() - b.mean()) if len(t) and len(b) else None,
            "diff_median": float(t.median() - b.median()) if len(t) and len(b) else None}


def per_year(s, score, col):
    rows = []
    for y, g in s.groupby(s["listing_date"].dt.year):
        tb = top_minus_bottom(g, score, col)
        tb["year"] = int(y)
        tb["testable"] = tb["top_n"] >= MIN_YEAR_N and tb["bottom_n"] >= MIN_YEAR_N
        rows.append(tb)
    return rows


def pass_rule(s, score):
    res = {}
    r1 = {c: top_minus_bottom(s, score, c) for c in DECISION}
    res["rule1_pooled"] = {c: v for c, v in r1.items()}
    ok1 = all((v["diff_mean"] or -1) > 0 for v in r1.values())
    res["rule2_years"] = {}
    ok2 = True
    for c in DECISION:
        yrs = [y for y in per_year(s, score, c) if y["testable"]]
        wins = sum(1 for y in yrs if (y["diff_mean"] or -1) > 0)
        res["rule2_years"][c] = {"testable_years": len(yrs), "years_top_beats_bottom": wins,
                                 "per_year": yrs}
        ok2 = ok2 and len(yrs) > 0 and wins > len(yrs) / 2
    res["rule3_split"] = {}
    ok3 = True
    scored = s[s[score].notna()]
    cut = scored["listing_date"].median() if len(scored) else pd.Timestamp("2100-01-01")
    for name, part in ((f"first half (listed <= {cut.date()})", scored[scored["listing_date"] <= cut]),
                       (f"second half (listed > {cut.date()})", scored[scored["listing_date"] > cut])):
        d = {c: top_minus_bottom(part, score, c) for c in DECISION}
        testable = all(v["top_n"] >= MIN_HALF_N and v["bottom_n"] >= MIN_HALF_N for v in d.values())
        good = testable and all((v["diff_mean"] or -1) > 0 for v in d.values())
        res["rule3_split"][name] = {"testable": testable, "pass": good, **d}
        ok3 = ok3 and good
    r4 = {c: top_minus_bottom(s, score, f"pit_{c}") for c in DECISION}
    res["rule4_pit"] = r4
    ok4 = all((v["diff_mean"] or -1) > 0 for v in r4.values())
    res["checks"] = {"rule1": ok1, "rule2": ok2, "rule3": ok3, "rule4": ok4}
    res["pass"] = bool(ok1 and ok2 and ok3 and ok4)
    return res


def ic(s, score, col):
    g = s[[score, col]].dropna()
    return {"n": int(len(g)), "ic": float(g[score].rank().corr(g[col].rank())) if len(g) > 10 else None}


def describe(df, s):
    out = {}
    main = df[(df["board"] == "mainboard") & ~df["is_fpo"].astype(bool)]
    # subscription buckets on every main-board IPO with outcomes (financial companies included)
    qb = pd.cut(main["sub_qib"], [-1, 1, 10, 50, 100, 1e9], labels=["<1x", "1-10x", "10-50x", "50-100x", ">100x"])
    out["qib_buckets_all_mainboard"] = bucket_table(main, qb)
    tb = pd.cut(main["sub_total"], [-1, 2, 10, 30, 80, 1e9], labels=["<2x", "2-10x", "10-30x", "30-80x", ">80x"])
    out["total_sub_buckets_all_mainboard"] = bucket_table(main, tb)
    rb = pd.cut(s["rel_median"], [-10, -0.3, -0.1, 0.1, 0.4, 0.8, 10],
                labels=["<-26% (cheap)", "-26%..-10%", "-10%..+10%", "+10%..+49%", "+49%..+123%", ">+123% (dear)"])
    out["rel_median_buckets"] = bucket_table(s, rb)
    out["verdict_buckets"] = bucket_table(s, "verdict")
    out["loss_making"] = bucket_table(s, s["loss_making"].astype(bool).map({True: "loss-making", False: "profitable"}))
    dd = pd.cut(main["sc250_drawdown"], [-1, -0.2, -0.1, 0.01], labels=["SC250 >=20% off high", "10-20% off", "within 10%"])
    out["market_drawdown_buckets_all_mainboard"] = bucket_table(main, dd)
    hot = pd.cut(main["prior_90d_median_list_gain"], [-10, 0.05, 0.2, 10],
                 labels=["cold (<5% median listing gain prior 90d)", "normal 5-20%", "hot (>20%)"])
    out["ipo_market_buckets_all_mainboard"] = bucket_table(main, hot)
    sme = df[(df["board"] == "sme")]
    sb = pd.cut(sme["sub_total"], [-1, 2, 10, 50, 200, 1e9], labels=["<2x", "2-10x", "10-50x", "50-200x", ">200x"])
    out["sme_total_sub_buckets"] = bucket_table(sme, sb)
    return out


def fmt_table(rows, outcomes=OUTCOMES):
    lines = [f"  {'bucket':<44}{'n':>4} " + "".join(f"{o.replace('_close', ''):>22}" for o in outcomes)]
    for r in rows:
        cells = []
        for o in outcomes:
            if r.get(f"{o}_n"):
                cells.append(f"{r[f'{o}_mean']:+7.1%}/{r[f'{o}_median']:+6.1%} n{r[f'{o}_n']:<3}")
            else:
                cells.append(f"{'-':>21}")
        lines.append(f"  {r['bucket'][:44]:<44}{r['n']:>4} " + " ".join(f"{c:>21}" for c in cells))
    return "\n".join(lines)


def run(path=DATA):
    df = load(path)
    s = add_scores(test_sample(df))
    res = {"sample": {"mainboard_ipos": int(((df["board"] == "mainboard") & ~df["is_fpo"].astype(bool)).sum()),
                      "test_sample": int(len(s)), "scored_VAL": int(s["VAL"].notna().sum()),
                      "scored_SUB": int(s["SUB"].notna().sum()), "scored_COMBO": int(s["COMBO"].notna().sum()),
                      "by_year": {int(k): int(v) for k, v in s.groupby(s["listing_date"].dt.year).size().items()}}}
    print(json.dumps(res["sample"], indent=1))
    for sc in ("VAL", "SUB", "COMBO"):
        res[sc] = {"terciles": bucket_table(s, f"{sc}_terc"),
                   "ic": {o: ic(s, sc, o) for o in OUTCOMES + ["pit_exc_6m", "pit_exc_12m"]},
                   "pass_rule": pass_rule(s, sc)}
        print(f"\n=== {sc} terciles (mean/median, n) ===")
        print(fmt_table(res[sc]["terciles"]))
        print("  IC:", {o: (round(v["ic"], 3) if v["ic"] is not None else None, v["n"]) for o, v in res[sc]["ic"].items()})
        pr = res[sc]["pass_rule"]
        print(f"  PASS RULE {sc}: {pr['pass']}  {pr['checks']}")
        for c in DECISION:
            y = pr["rule2_years"][c]
            print(f"   {c}: pooled top-bottom {pr['rule1_pooled'][c]['diff_mean']}, years {y['years_top_beats_bottom']}/{y['testable_years']}"
                  f"  per-year: " + " ".join(f"{r['year']}:{(r['diff_mean'] or 0):+.2f}(n{r['top_n']}/{r['bottom_n']})" for r in y["per_year"]))
            print(f"   split: " + "; ".join(f"{k} testable={v['testable']} diff={v[c]['diff_mean']}" for k, v in pr["rule3_split"].items()),
                  f" pit diff={pr['rule4_pit'][c]['diff_mean']}")
    res["diagnostics"] = describe(df, s)
    for k, rows in res["diagnostics"].items():
        print(f"\n--- {k} ---")
        print(fmt_table(rows))
    OUT.write_text(json.dumps(res, indent=1, default=str))
    s.to_csv(PKG_DIR / "eval_sample.csv", index=False)
    print(f"\nwrote {OUT}")
    return res, s


def main(argv=None):
    argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter).parse_args(argv)
    run()


if __name__ == "__main__":
    main()
