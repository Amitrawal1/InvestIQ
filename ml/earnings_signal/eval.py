"""Do earnings surprises add out-of-sample ranking skill on top of investiq-v1?

Universe and baseline (same rows as rankings/combiner_eval.py Part A)
---------------------------------------------------------------------
combiner_eval.nonfin_panel(labels): label grid (1st/16th), liquid universe (>= 0.5 cr/day, >= 252
trading days), fresh point-in-time financials with a growth reading, a trend score.
    v1    per-date percentile of 0.70 x market + 0.30 x financial (investiq-v1 without news, which
          has no history, and without the negative-equity penalty: combiner_eval's mix_0.7)
Signals (earnings_signal/features.py, point-in-time; latest result known strictly before D):
    s1_rC     per-date percentile of S1 (announcement excess return) among names whose S1 is at
              most C days old (C = 45 or 90); older / missing -> 0.5 (neutral)
    s2_rC     the same for S2 (growth surprise)
    s12_rC    mean of the s1 / s2 percentiles that are fresh (one if only one is), else 0.5
Combinations with investiq-v1 (weights {0.10, 0.20}):
    v1+SIG_w  (1 - w) x v1 + w x SIG        (both 0-1 percentiles, so w is the real share)

Pre-declared selection and pass rule (written before any result was looked at)
------------------------------------------------------------------------------
Candidates: "v1" (no change) + the 12 combinations (3 signals x 2 recency cuts x 2 weights).
Walk-forward, test years FIRST_TEST_YEAR..2026. For test year Y the training set is every signal date
before Jan 1 Y - PURGE (190 days: the 6m label, which also covers 3m; combiner_eval's purge). On the
training dates the candidate with the highest objective wins:
    objective = mean over h in {3m, 6m} of [ mean(yearly IC) - 0.5 x std(yearly IC) ]
(combiner_eval's stability-penalised IC, averaged over the two horizons that matter for a short-term
signal). A candidate is eligible only if its signal had >= 50 fresh names on >= 12 training dates
(S2 only exists from mid-2020: before that the fold falls back to v1). Ties go to v1.
PASS (all must hold, test years, walk-forward column "wf" vs "v1"):
    3m and 6m: mean yearly IC higher, mean yearly top-minus-bottom decile spread higher, and no fewer
    years with IC > 0.
1m and 12m are reported, not part of the rule. The "best candidate" for the portfolio/time-machine
checks is the same selection rule run on all labelled years (like combiner_eval's live weight).

Also reported: standalone per-year IC by horizon (neutral-filled and conditional on a fresh result),
decay (IC by days since the result, and the event-time drift of top-minus-bottom S1/S2 quintiles),
correlation with the market / financial scores and the part of S1 not explained by them (residual IC),
Top-list backtest (portfolio_eval.simulate, RECOMMENDED rules, 0.3% per side) and the time-machine
windows (rankings/time_machine.EVENTS) for the best candidate vs investiq-v1.

CLI:  caffeinate -i python3 -m earnings_signal.eval [--refresh]
Writes ml/earnings_signal/results.json (+ a panel cache in ml/data/processed/earnings_signal_panel.pkl).
"""

import argparse
import json
import time
import warnings
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.stats import spearmanr

from growth_model.market_model import CLIP
from growth_model.prices import CACHE_DIR

from . import features as F

HORIZONS = ["1m", "3m", "6m", "12m"]
SEL_HORIZONS = ["3m", "6m"]
PURGE = 190
SIGNALS = ["s1", "s2", "s12"]
RECENCY = [45, 90]
WEIGHTS = [0.10, 0.20]
STABILITY_PENALTY = 0.5
MIN_FRESH = 50
MIN_TRAIN_SIGNAL_DATES = 12
FIRST_TEST_YEAR = 2020
MIN_ROWS = 50
AGE_BUCKETS = [(0, 15), (16, 30), (31, 45), (46, 60), (61, 90), (91, 120), (121, 180)]
EVENT_DAYS = [1, 5, 10, 21, 42, 63, 126]
MARKET_WEIGHT = 0.7

HERE = Path(__file__).resolve().parent
OUT_FILE = HERE / "results.json"
PANEL_CACHE = CACHE_DIR / "earnings_signal_panel.pkl"


def combos():
    return [f"v1+{s}_r{c}_w{w:.2f}" for s in SIGNALS for c in RECENCY for w in WEIGHTS]


def pct_by_date(s, dates):
    return s.groupby(dates).rank(pct=True, method="average")


def add_signal_columns(df, base_col="v1_raw", out_base="v1"):
    """Signal percentiles (neutral 0.5) and combinations. df needs signal_date, s1, s1_age, s2, s2_age."""
    d = df["signal_date"]
    df[out_base] = pct_by_date(df[base_col], d)
    for cut in RECENCY:
        f1 = df["s1"].notna() & (df["s1_age"] <= cut)
        f2 = df["s2"].notna() & (df["s2_age"] <= cut)
        p1, p2 = pct_by_date(df["s1"].where(f1), d), pct_by_date(df["s2"].where(f2), d)
        df[f"s1_r{cut}"] = p1.fillna(0.5)
        df[f"s2_r{cut}"] = p2.fillna(0.5)
        df[f"s12_r{cut}"] = pd.concat([p1, p2], axis=1).mean(axis=1).fillna(0.5)
        df[f"fresh_s1_r{cut}"], df[f"fresh_s2_r{cut}"], df[f"fresh_s12_r{cut}"] = f1, f2, f1 | f2
    for s in SIGNALS:
        for c in RECENCY:
            for w in WEIGHTS:
                df[f"{out_base}+{s}_r{c}_w{w:.2f}"] = (1 - w) * df[out_base] + w * df[f"{s}_r{c}"]
    return df


# ---------------------------------------------------------
# Panel
# ---------------------------------------------------------

def load_panel(refresh=False):
    from growth_model.labels import LABELS_FILE
    from rankings.combiner_eval import nonfin_panel

    if PANEL_CACHE.exists() and not refresh:
        panel = pd.read_pickle(PANEL_CACHE)
        return panel, None
    labels = pd.read_pickle(LABELS_FILE)
    panel, _ = nonfin_panel(labels)
    keep = ["company_id", "signal_date", "market", "financial", "adv_60d_cr", "days_listed",
            "revenue_yoy", "net_profit_yoy", "revenue_yoy_accel", "net_profit_yoy_accel",
            *[c for c in panel.columns if c.startswith(("excess_", "top_q_", "beat_"))]]
    panel = panel[keep].rename(columns={"revenue_yoy": "fin_revenue_yoy", "net_profit_yoy": "fin_net_profit_yoy"})
    sig, events, inputs = F.build_panel(panel[["company_id", "signal_date"]])
    panel = pd.concat([panel.reset_index(drop=True), sig.drop(columns=["company_id", "signal_date"]).reset_index(drop=True)], axis=1)
    panel.to_pickle(PANEL_CACHE)
    return panel, (events, inputs)


# ---------------------------------------------------------
# Metrics
# ---------------------------------------------------------

def per_date(df, col, h):
    """Per-date IC and top/bottom-decile mean clipped excess (dates with >= MIN_ROWS labelled rows)."""
    d = df[df[f"excess_{h}"].notna() & df[col].notna()]
    rows = []
    for date, g in d.groupby("signal_date"):
        if len(g) < MIN_ROWS:
            continue
        ic = spearmanr(g[col], g[f"excess_{h}"]).statistic
        p = g[col].rank(pct=True)
        ex = g[f"excess_{h}"].clip(*CLIP)
        rows.append({"date": date, "ic": ic, "top": ex[p > 0.9].mean(), "bot": ex[p <= 0.1].mean(),
                     "uni": ex.mean(), "n_top": int((p > 0.9).sum()), "n_bot": int((p <= 0.1).sum())})
    return pd.DataFrame(rows)


def yearly_from(pdt, first_year=None):
    """Yearly IC (mean of dates), spread pooled like market_model.evaluate (row-weighted)."""
    if len(pdt) == 0:
        return pd.DataFrame(columns=["year", "ic", "spread", "top10_minus_uni"])
    p = pdt.assign(year=pdt["date"].dt.year)
    if first_year:
        p = p[p["year"] >= first_year]
    out = []
    for y, g in p.groupby("year"):
        top = (g["top"] * g["n_top"]).sum() / g["n_top"].sum()
        bot = (g["bot"] * g["n_bot"]).sum() / g["n_bot"].sum()
        out.append({"year": int(y), "ic": float(np.nanmean(g["ic"])), "spread": float(top - bot),
                    "top10_minus_uni": float(top - g["uni"].mean())})
    return pd.DataFrame(out)


def summ(t):
    if len(t) == 0:
        return {"ic": np.nan, "spread": np.nan, "years_pos": "0/0", "n_pos": 0, "n": 0}
    return {"ic": float(t["ic"].mean()), "spread": float(t["spread"].mean()),
            "top_minus_uni": float(t["top10_minus_uni"].mean()),
            "years_pos": f"{int((t['ic'] > 0).sum())}/{len(t)}", "n_pos": int((t["ic"] > 0).sum()), "n": len(t)}


def objective(pdt):
    t = yearly_from(pdt)
    ic = t["ic"].dropna() if len(t) else pd.Series(dtype=float)
    if len(ic) == 0:
        return -np.inf
    return ic.mean() - STABILITY_PENALTY * (ic.std(ddof=0) if len(ic) > 1 else 0.0)


def fresh_dates(panel, col):
    sig = col.split("+")[1].rsplit("_w", 1)[0]
    n = panel.groupby("signal_date")[f"fresh_{sig}"].sum()
    return n[n >= MIN_FRESH].index


def choose(panel, pd_cache, cutoff):
    """Pre-declared rule on dates < cutoff -> (chosen column, objective table)."""
    cands = ["v1", *combos()]
    table = {}
    for c in cands:
        if c != "v1":
            ok = fresh_dates(panel, c)
            if (ok < cutoff).sum() < MIN_TRAIN_SIGNAL_DATES:
                table[c] = None
                continue
        objs = [objective(pd_cache[(c, h)][pd_cache[(c, h)]["date"] < cutoff]) for h in SEL_HORIZONS]
        table[c] = float(np.mean(objs))
    best = "v1"
    for c in cands[1:]:
        if table[c] is not None and table[c] > table[best] + 1e-12:
            best = c
    return best, table


# ---------------------------------------------------------
# Decay / event study / incremental
# ---------------------------------------------------------

def decay_by_age(panel, sig, h):
    out = {}
    for lo, hi in AGE_BUCKETS:
        sub = panel[panel[sig].notna() & panel[f"{sig}_age"].between(lo, hi) & panel[f"excess_{h}"].notna()]
        ics = [spearmanr(g[sig], g[f"excess_{h}"]).statistic for _, g in sub.groupby("signal_date") if len(g) >= 30]
        out[f"{lo}-{hi}"] = {"ic": float(np.nanmean(ics)) if ics else None, "dates": len(ics),
                             "t": float(np.nanmean(ics) / (np.nanstd(ics) / np.sqrt(len(ics)))) if len(ics) > 2 else None}
    return out


def event_drift(events, panel, stocks, index):
    """Q5 - Q1 mean cumulative excess return from the S1/S2 known close to +k sessions (liquid events)."""
    cal, bench, base_px, _, breaks = F._price_matrices(stocks, index)
    px = base_px.values
    col = {c: i for i, c in enumerate(base_px.columns)}
    pos = {d: i for i, d in enumerate(cal)}
    B, K = bench.values, breaks.values
    liquid = set(zip(panel["company_id"], panel["signal_date"].dt.to_period("Q")))
    out = {}
    for sig, known in (("s1", "s1_known"), ("s2", "s2_known")):
        e = events[events[sig].notna() & events[known].notna()].copy()
        kd = e[known].dt.normalize()
        # the first close at or after the known time: S1's window-end close; S2's filing -> next session close
        e["p0"] = [pos.get(d) if sig == "s1" else int(cal.searchsorted(d, side="right")) for d in kd]
        e = e[e["p0"].notna()]
        e["p0"] = e["p0"].astype(int)
        e["q"] = e["first_filing"].dt.to_period("Q")
        e = e[[(c, q) in liquid for c, q in zip(e["company_id"], e["q"])] & e["company_id"].isin(col)]
        e["quint"] = e.groupby("q")[sig].transform(lambda s: pd.qcut(s.rank(method="first"), 5, labels=False) + 1 if len(s) >= 25 else np.nan)
        e = e[e["quint"].notna()]
        res = {}
        for k in EVENT_DAYS:
            vals = {1: [], 5: []}
            years = {}
            for cid, p0, qn, yr in zip(e["company_id"], e["p0"], e["quint"], e["first_filing"].dt.year):
                if qn not in (1, 5) or p0 + k >= len(cal):
                    continue
                j = col[cid]
                a, b = px[p0, j], px[p0 + k, j]
                if np.isnan(a) or np.isnan(b) or K[p0 + k, j] != K[p0, j]:
                    continue
                x = np.clip((b / a - 1) - (B[p0 + k] / B[p0] - 1), *CLIP)
                vals[int(qn)].append(x)
                years.setdefault(yr, {1: [], 5: []})[int(qn)].append(x)
            yr_spread = {y: float(np.mean(v[5]) - np.mean(v[1])) for y, v in years.items() if v[1] and v[5]}
            res[k] = {"q5": float(np.mean(vals[5])), "q1": float(np.mean(vals[1])),
                      "spread": float(np.mean(vals[5]) - np.mean(vals[1])), "n": len(vals[1]) + len(vals[5]),
                      "years_positive": f"{sum(v > 0 for v in yr_spread.values())}/{len(yr_spread)}"}
        out[sig] = res
    return out


def incremental(panel, sig, cut, h_list=("1m", "3m", "6m")):
    """Correlations with market / financial and residual IC of a fresh signal (raw, fresh rows only)."""
    sub = panel[panel[sig].notna() & (panel[f"{sig}_age"] <= cut)].copy()
    corr = {}
    for other in ("market", "financial", "v1"):
        cs = [spearmanr(g[sig], g[other]).statistic for _, g in sub.groupby("signal_date") if len(g) >= 30]
        corr[other] = float(np.nanmean(cs))
    res = {}
    for h in h_list:
        raw_ic, res_m, res_v1 = [], [], []
        for _, g in sub[sub[f"excess_{h}"].notna()].groupby("signal_date"):
            if len(g) < 30:
                continue
            y = g[f"excess_{h}"].rank()
            s = g[sig].rank()
            raw_ic.append(spearmanr(s, y).statistic)
            for ctrl, store in ((["market"], res_m), (["market", "financial"], res_v1)):
                X = np.column_stack([np.ones(len(g)), *[g[c].rank() for c in ctrl]])
                beta = np.linalg.lstsq(X, s.values, rcond=None)[0]
                store.append(spearmanr(s.values - X @ beta, y).statistic)
        res[h] = {"ic": float(np.nanmean(raw_ic)), "resid_vs_market": float(np.nanmean(res_m)),
                  "resid_vs_market_fin": float(np.nanmean(res_v1)), "dates": len(raw_ic)}
    return {"corr": corr, "ic": res}


# ---------------------------------------------------------
# Top list / time machine
# ---------------------------------------------------------

def portfolio_checks(best, events):
    from growth_model.labels import LABELS_FILE
    from rankings.portfolio import RECOMMENDED
    from rankings.portfolio_eval import MIN_NAMES, load_daily, load_scores, metrics, simulate, window_stats
    from rankings.time_machine import EVENTS

    labels = pd.read_pickle(LABELS_FILE)
    scores = load_scores(labels)
    n_per = scores.groupby("signal_date").size()
    start = n_per[n_per >= MIN_NAMES].index.min()
    scores = scores[scores["signal_date"] >= start].reset_index(drop=True)
    sig = F.attach(scores[["company_id", "signal_date"]], events)
    scores = pd.concat([scores, sig.drop(columns=["company_id", "signal_date"])], axis=1)
    scores = add_signal_columns(scores, base_col="growth_score", out_base="gs")
    ret, bench, _ = load_daily()
    variants = {"investiq-v1": "growth_score"}
    if best != "v1":
        s, w = best.split("+")[1].rsplit("_w", 1)
        for ww in WEIGHTS:
            variants[f"v1+{s}_w{ww:.2f}"] = f"gs+{s}_w{ww:.2f}"
    runs, res = {}, {}
    uni = simulate(scores, ret, bench, None, universe=True)
    bench_nav = bench.reindex(uni["nav"].index)
    bench_nav = bench_nav / bench_nav.iloc[0]
    for name, col in variants.items():
        sc = scores.assign(growth_score=scores[col] * (100 if col != "growth_score" else 1))
        runs[name] = simulate(sc, ret, bench, RECOMMENDED)
        m = metrics(runs[name], bench_nav, uni["gross"])
        res[name] = {k: m[k] for k in ("cagr", "vs_index_cagr", "max_dd", "vol", "years_beat", "years",
                                        "turnover_yr", "per_year", "halves")}
        print(f"  top list {name:<22} CAGR {m['cagr']:+.1%}  vs idx {m['vs_index_cagr']:+.1%}  DD {m['max_dd']:+.1%}  "
              f"yrs {m['years_beat']}/{m['years']}  turnover {m['turnover_yr']:.0%}", flush=True)
    # overlap of lists
    if len(runs) > 1:
        a = runs["investiq-v1"]["holdings"]
        for name in list(runs)[1:]:
            b = runs[name]["holdings"]
            res[name]["overlap_with_v1"] = float(np.mean([len(set(a[d]) & set(b[d])) / max(len(a[d]), 1) for d in a if d in b]))
    windows = {}
    cal = ret.index
    close_rel = (1 + ret).cumprod()
    for wname, d0, d1, _ in EVENTS:
        if pd.Timestamp(d0) < start:
            windows[wname] = {"skip": f"before first backtest date {start:%Y-%m-%d}"}
            continue
        row = {"continuous": {n: window_stats(runs[n]["nav"], d0, d1) for n in runs}}
        row["continuous"]["index"] = window_stats(bench_nav, d0, d1)
        # snapshot (time-machine style): grid date on/before d0, top 50 in the tested universe, buy and hold
        g = scores[scores["signal_date"] <= pd.Timestamp(d0)]["signal_date"].max()
        snap = scores[(scores["signal_date"] == g) & (scores["adv_cr"] >= 0.5) & (scores["days_listed"] >= 252)]
        e = cal.searchsorted(g, side="right")
        x = cal.searchsorted(pd.Timestamp(d1), side="right") - 1 if d1 else len(cal) - 1
        rel = close_rel.iloc[x] / close_rel.iloc[e]
        b_ret = float(bench.iloc[x] / bench.iloc[e] - 1)
        snap = snap.assign(r=rel.reindex(snap["company_id"]).values - 1)
        snap_out = {"grid_date": str(g.date()), "index": b_ret, "all": float(snap["r"].mean())}
        for n, col in variants.items():
            ic = spearmanr(snap[col], snap["r"], nan_policy="omit").statistic
            top = snap.nlargest(50, col)
            path = close_rel.iloc[e:x + 1][[c for c in top["company_id"] if c in close_rel.columns]]
            path = (path / path.iloc[0]).mean(axis=1)
            snap_out[n] = {"ic": float(ic), "top50": float(top["r"].mean()),
                           "top50_dd": float((path / path.cummax() - 1).min())}
        row["snapshot"] = snap_out
        windows[wname] = row
    return res, windows


# ---------------------------------------------------------
# Main
# ---------------------------------------------------------

def fmt(x, pct=False):
    if x is None or (isinstance(x, float) and np.isnan(x)):
        return "—"
    return f"{x:+.1%}" if pct else f"{x:+.4f}"


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--refresh", action="store_true", help="rebuild the panel cache")
    ap.add_argument("--skip-portfolio", action="store_true")
    args = ap.parse_args(argv)
    warnings.filterwarnings("ignore")
    t0 = time.time()
    panel, built = load_panel(args.refresh)
    inputs = F.load_inputs()
    events = built[0] if built else F.build_events(*inputs)
    print(f"panel {len(panel):,} rows, {panel['company_id'].nunique():,} companies, {panel['signal_date'].nunique()} dates "
          f"({time.time() - t0:.0f}s)", flush=True)

    # ---- no look-ahead ----
    check = F.check_no_lookahead(panel, *inputs, n=300)
    print(f"no-look-ahead check passed: {check}", flush=True)

    panel["v1_raw"] = MARKET_WEIGHT * panel["market"] + (1 - MARKET_WEIGHT) * panel["financial"]
    panel = add_signal_columns(panel)
    out = {"check": check, "panel_rows": len(panel), "pre_declared": {
        "signals": SIGNALS, "recency": RECENCY, "weights": WEIGHTS, "purge_days": PURGE,
        "selection": "mean over 3m,6m of mean(yearly IC) - 0.5 std(yearly IC); ties -> v1",
        "pass": "wf beats v1 on mean IC and mean decile spread at 3m AND 6m, years IC>0 not fewer"}}

    # coverage
    cov = panel.groupby(panel["signal_date"].dt.year).agg(
        **{f"fresh_{s}_r{c}": (f"fresh_{s}_r{c}", "mean") for s in ("s1", "s2") for c in RECENCY})
    out["coverage"] = cov.round(3).to_dict()
    print("\nshare of rows with a fresh signal, by year:\n" + cov.round(2).to_string())

    # per-date metric cache
    cols = ["v1", "market", "financial", *[f"{s}_r{c}" for s in SIGNALS for c in RECENCY], *combos()]
    pd_cache = {(c, h): per_date(panel, c, h) for c in cols for h in HORIZONS}
    print(f"per-date metrics done ({time.time() - t0:.0f}s)", flush=True)

    # ---- 1. standalone ----
    out["standalone"] = {}
    print("\n=== standalone (neutral-filled percentiles), per-year IC ===")
    for c in [f"{s}_r{c}" for s in SIGNALS for c in RECENCY] + ["v1", "market"]:
        out["standalone"][c] = {}
        for h in HORIZONS:
            t = yearly_from(pd_cache[(c, h)], 2019)
            out["standalone"][c][h] = {"summary": summ(t), "per_year": t.round(4).to_dict("records")}
        line = "  ".join(f"{h} {out['standalone'][c][h]['summary']['ic']:+.4f} ({out['standalone'][c][h]['summary']['years_pos']})"
                         f" spr {out['standalone'][c][h]['summary']['spread']:+.1%}" for h in HORIZONS)
        print(f"  {c:<10} {line}")
        print("     per-year 3m IC: " + ", ".join(f"{int(r['year'])} {r['ic']:+.3f}"
                                                  for r in out["standalone"][c]["3m"]["per_year"]))
    # conditional: raw signal only among fresh rows
    out["conditional"] = {}
    print("\n=== conditional IC (raw signal, only names with a result <= 90 days old) ===")
    for s in ("s1", "s2", "rev_sue", "np_sue"):
        age = "s2_age" if s in ("s2", "rev_sue", "np_sue") else "s1_age"
        sub = panel[panel[s].notna() & (panel[age] <= 90)]
        out["conditional"][s] = {}
        for h in HORIZONS:
            t = yearly_from(per_date(sub, s, h), 2019)
            out["conditional"][s][h] = {"summary": summ(t), "per_year": t.round(4).to_dict("records")}
        print(f"  {s:<8} " + "  ".join(f"{h} {out['conditional'][s][h]['summary']['ic']:+.4f} "
                                     f"({out['conditional'][s][h]['summary']['years_pos']})" for h in HORIZONS))

    # ---- 2. walk-forward ----
    print("\n=== walk-forward selection (training years only, purged 190 days) ===")
    last_year = int(panel["signal_date"].dt.year.max())
    chosen = {}
    panel["wf"] = np.nan
    for y in range(FIRST_TEST_YEAR, last_year + 1):
        cutoff = pd.Timestamp(y, 1, 1) - pd.Timedelta(days=PURGE)
        best, table = choose(panel, pd_cache, cutoff)
        chosen[y] = best
        m = panel["signal_date"].dt.year == y
        panel.loc[m, "wf"] = panel.loc[m, best]
        elig = {k: round(v, 4) for k, v in table.items() if v is not None}
        print(f"  {y}: train < {cutoff:%Y-%m-%d}; chosen {best}; v1 obj {table['v1']:+.4f}; "
              f"best combo obj {max((v for k, v in elig.items() if k != 'v1'), default=float('nan')):+.4f}")
    out["chosen_by_year"] = chosen
    wf = {}
    for c in ["wf", "v1", *combos()]:
        wf[c] = {}
        for h in HORIZONS:
            pdt = per_date(panel[panel["signal_date"].dt.year >= FIRST_TEST_YEAR], c, h) if c == "wf" else pd_cache[(c, h)]
            t = yearly_from(pdt, FIRST_TEST_YEAR)
            wf[c][h] = {"summary": summ(t), "per_year": t.round(4).to_dict("records")}
    out["walk_forward"] = wf
    print(f"\n{'method':<24}" + "".join(f"{h + ' IC':>10}{'spread':>9}{'yrs':>6}" for h in HORIZONS))
    for c in ["v1", "wf", *combos()]:
        print(f"{c:<24}" + "".join(f"{wf[c][h]['summary']['ic']:>+10.4f}{wf[c][h]['summary']['spread']:>+9.1%}"
                                   f"{wf[c][h]['summary']['years_pos']:>6}" for h in HORIZONS))
    passed = all(wf["wf"][h]["summary"]["ic"] > wf["v1"][h]["summary"]["ic"]
                 and wf["wf"][h]["summary"]["spread"] > wf["v1"][h]["summary"]["spread"]
                 and wf["wf"][h]["summary"]["n_pos"] >= wf["v1"][h]["summary"]["n_pos"] for h in SEL_HORIZONS)
    out["pass"] = bool(passed)
    print(f"\nPASS rule (3m and 6m: IC up, spread up, years positive not fewer): {passed}")
    print("wf vs v1 per year (IC diff / spread diff):")
    out["wf_vs_v1"] = {}
    for h in HORIZONS:
        a = {r["year"]: r for r in wf["wf"][h]["per_year"]}
        b = {r["year"]: r for r in wf["v1"][h]["per_year"]}
        ys = [y for y in sorted(a) if y in b and y > FIRST_TEST_YEAR]      # 2020 = v1 by construction
        d_ic = [a[y]["ic"] - b[y]["ic"] for y in ys]
        d_sp = [a[y]["spread"] - b[y]["spread"] for y in ys]
        # paired per-date IC difference (dates overlap in their label windows: the t is optimistic)
        pa = per_date(panel[panel["signal_date"].dt.year > FIRST_TEST_YEAR], "wf", h).set_index("date")["ic"]
        pb = pd_cache[("v1", h)].set_index("date")["ic"]
        dd = (pa - pb.reindex(pa.index)).dropna()
        out["wf_vs_v1"][h] = {"years_ic_up": f"{sum(x > 0 for x in d_ic)}/{len(ys)}",
                              "years_spread_up": f"{sum(x > 0 for x in d_sp)}/{len(ys)}",
                              "dates_ic_up": float((dd > 0).mean()), "mean_date_diff": float(dd.mean()),
                              "naive_t": float(dd.mean() / (dd.std() / np.sqrt(len(dd))))}
        print(f"  {h}: " + ", ".join(f"{y} {a[y]['ic'] - b[y]['ic']:+.4f}/{a[y]['spread'] - b[y]['spread']:+.1%}" for y in sorted(a) if y in b)
              + f"   [2021+: IC up {out['wf_vs_v1'][h]['years_ic_up']} yrs, spread up {out['wf_vs_v1'][h]['years_spread_up']}; "
                f"dates IC up {(dd > 0).mean():.0%}, naive t {out['wf_vs_v1'][h]['naive_t']:.1f}]")

    final, table = choose(panel, pd_cache, pd.Timestamp("2100-01-01"))
    out["final_choice"] = final
    out["final_objectives"] = {k: (round(v, 5) if v is not None else None) for k, v in table.items()}
    print(f"\nselection rule on all labelled years -> {final}")
    print("  " + ", ".join(f"{k} {v:+.4f}" for k, v in table.items() if v is not None))

    # ---- 3. decay ----
    print("\n=== decay: IC of the raw signal by days since its known date ===")
    out["decay_age"] = {}
    for s in ("s1", "s2"):
        out["decay_age"][s] = {h: decay_by_age(panel, s, h) for h in ("1m", "3m", "6m")}
        for h in ("1m", "3m", "6m"):
            print(f"  {s} {h}: " + ", ".join(f"{k}: {fmt(v['ic'])} ({v['dates']}d)" for k, v in out["decay_age"][s][h].items()))
    stocks, index = inputs[2], inputs[3]
    out["event_drift"] = event_drift(events, panel, stocks, index)
    print("\n=== event time: Q5 - Q1 cumulative excess from the known close (liquid events) ===")
    for s, r in out["event_drift"].items():
        print(f"  {s}: " + ", ".join(f"+{k}d {v['spread']:+.2%} ({v['years_positive']})" for k, v in r.items()))

    # ---- 4. incremental ----
    print("\n=== overlap with the market score; residual IC (fresh rows, <= 90 days) ===")
    out["incremental"] = {}
    for s in ("s1", "s2"):
        out["incremental"][s] = incremental(panel, s, 90)
        r = out["incremental"][s]
        print(f"  {s}: corr market {r['corr']['market']:+.3f}, financial {r['corr']['financial']:+.3f}, v1 {r['corr']['v1']:+.3f}")
        for h, v in r["ic"].items():
            print(f"     {h}: raw IC {v['ic']:+.4f}  resid|market {v['resid_vs_market']:+.4f}  resid|market+fin {v['resid_vs_market_fin']:+.4f}")
    # correlation of the combined score with v1
    out["combo_corr_with_v1"] = {c: float(np.nanmean([spearmanr(g[c], g["v1"]).statistic for _, g in panel.groupby("signal_date")]))
                                 for c in combos() if c.endswith(("0.10", "0.20")) and "r90" in c}

    # ---- 5. Top list and time machine ----
    best_for_pf = final if final != "v1" else max(combos(), key=lambda c: table[c] if table[c] is not None else -9)
    out["portfolio_candidate"] = best_for_pf
    if not args.skip_portfolio:
        print(f"\n=== Top list (RECOMMENDED rules) and time-machine windows: v1 vs {best_for_pf} ===", flush=True)
        res, windows = portfolio_checks(best_for_pf, events)
        out["top_list"], out["windows"] = res, windows
        for wname, w in windows.items():
            if "skip" in w:
                print(f"  {wname}: skipped ({w['skip']})")
                continue
            cont = ", ".join(f"{n} {fmt(v['ret'], True)} (DD {fmt(v['max_dd'], True)})" for n, v in w["continuous"].items() if v)
            snap = w["snapshot"]
            sn = ", ".join(f"{n} IC {v['ic']:+.3f} top50 {fmt(v['top50'], True)}" for n, v in snap.items() if isinstance(v, dict))
            print(f"  {wname}: continuous {cont}\n      snapshot {snap['grid_date']}: {sn}; all {fmt(snap['all'], True)}, index {fmt(snap['index'], True)}")

    OUT_FILE.write_text(json.dumps(out, indent=1, default=str))
    print(f"\nwrote {OUT_FILE} in {time.time() - t0:.0f}s")


if __name__ == "__main__":
    main()
