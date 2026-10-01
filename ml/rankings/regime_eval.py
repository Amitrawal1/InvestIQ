"""Walk-forward test of the market-regime switch (rankings/regime.py) against investiq-v1.

Question: after a deep market fall, does lowering the trend weight (rules and alternatives
pre-declared in regime.py) stop the "momentum crash" (IC -0.19 when ranked on 2020-04-16) without
hurting normal years?

Rows and scores: exactly combiner_eval Part A (non-financial companies, liquid universe, fresh
point-in-time financials, rankable rows): `market` (trend6 percentile), `financial` (fin-v1
percentile). Added per-date percentiles for the tilts: lowvol = 1 - pct(vol_3m), reversal =
1 - pct(mom_1m) (growth_model.market_features, same cache). investiq-v1 = mix_0.7.
Market state per signal date: growth_market_features.pkl mood columns plus mkt_dd_52w from the
cached NIFTY SMALLCAP 250 closes (last trading day on or before D). Hysteresis rules walk the full
1st/16th grid from 2017, so a state on D never uses anything after D.

Candidates: investiq-v1 (no regime) + every (rule, alternative) in regime.RULES x
regime.ALTERNATIVES (12 x 5 = 60). A candidate's score equals investiq-v1 on normal dates and the
alternative's blend on risk dates.

Walk-forward (combiner_eval.walk_forward, unchanged logic): for test year Y and horizon h, train on
signal dates whose label window ended before Y began (PURGE_DAYS: 190 days 6m, 375 days 12m); pick
the candidate with max mean(yearly IC) - 0.5 x std(yearly IC) over training years; ties (within
1e-12) go to investiq-v1. Test years from 2020. Metrics: growth_model.market_model.evaluate per
test year (mean per-date Spearman IC, top-minus-bottom decile excess, top-decile beat rate).
Also reported: the PRIMARY hypothesis (fixed, no selection), per-date IC on every trigger date, the
whole grid on test years (for the record, not used to choose) and the live choice (same objective
on all labelled years, averaged over 6m and 12m, as combiner_eval's final w).

Ship criteria (pre-declared, `passes`): on BOTH horizons the walk-forward regime model has
    1. mean yearly IC >= investiq-v1's and mean decile spread >= investiq-v1's - 0.005,
    2. no test year with IC more than 0.01 below investiq-v1 (neutral elsewhere),
    3. mean per-date IC on test-year trigger dates above investiq-v1's,
and the live choice is not investiq-v1 itself. Otherwise: do not ship.

Time machine (`--tm`, DB SELECT only): rankings.time_machine.run_window on its EVENTS plus extra
windows ranked on dates where the chosen rule (or PRIMARY when nothing is chosen) is in the risk
regime, once with investiq-v1 and once with the regime weights (build_v3.MARKET_WEIGHT is
overridden in memory for that run; build_v3.py is not edited; weight-only alternatives only, tilts
are measured on the label panel instead). A label-panel proxy of the same windows (12m / 6m labels
from the nearest grid date) is always printed.

Caveats: 2-3 crash episodes in 2017-2026 (2018-19 slow bear, March 2020, early 2025) so any rule is
judged on very few independent events; survivorship (today's company list); overlapping labels.

Outputs: ml/rankings/reports/REGIME.md and ml/data/processed/regime_walkforward.json.

CLI:  caffeinate -i python3 -m rankings.regime_eval [--tm]
"""

import argparse
import json
import time
import warnings
from datetime import date

import numpy as np
import pandas as pd

from growth_model.market_features import rank_features as rank_market
from growth_model.market_model import FEATURES_FILE, PURGE_DAYS, evaluate
from growth_model.prices import BENCHMARK, CACHE_DIR, INDEX_CACHE, STOCK_CACHE

from . import regime as R
from .combiner_eval import FIRST_TEST_YEAR, HORIZONS, STABILITY_PENALTY, nonfin_panel, summary, yearly

BASE = "investiq-v1"
BASE_COL = "mix_0.7"
MIN_ROWS_PER_DATE = 50
SHIP_SPREAD_TOL = 0.005
SHIP_YEAR_IC_TOL = 0.01
REPORT_FILE = R.__file__.rsplit("/", 1)[0] + "/reports/REGIME.md"
OUT_FILE = CACHE_DIR / "regime_walkforward.json"
PANEL_CACHE = None      # set by --cache

# time-machine windows: (name, start, end or None, note). Extra trigger windows are added at run time.
TM_EVENTS = [
    ("One year ago", "2025-09-30", None),
    ("COVID crash", "2020-01-16", "2020-03-31"),
    ("COVID crash and rebound", "2020-01-16", "2021-01-15"),
    ("Post-COVID rally", "2020-04-16", "2021-04-16"),
    ("2022 rate-hike sell-off", "2021-12-16", "2022-06-30"),
    ("2024-25 small-cap correction", "2024-09-16", "2025-03-03"),
]
TM_EXTRA = [  # ranked inside the crash windows: these are where a regime can change anything
    ("COVID low, 6m", "2020-04-01", "2020-10-01"),
    ("May 2020, 12m", "2020-05-16", "2021-05-17"),
    ("March 2025 low, 12m", "2025-03-16", "2026-03-16"),
    ("2026 spring low, to date", "2026-04-01", None),
]


# ---------------------------------------------------------
# Data
# ---------------------------------------------------------

def market_state_grid(dates):
    """Market state on each signal date: mood columns from the features cache + mkt_dd_52w."""
    feats = pd.read_pickle(FEATURES_FILE)
    mood = feats.groupby("signal_date")[[c for c in R.STATE_COLUMNS if c != "mkt_dd_52w"]].first()
    ix = pd.read_pickle(INDEX_CACHE)
    bench = ix[ix["index_key"] == BENCHMARK].set_index("price_date")["close"].sort_index().astype(float)
    dd = (bench / bench.rolling(252, min_periods=200).max() - 1).rename("mkt_dd_52w").to_frame()
    st = R.state_on(dd, mood.index).join(mood)
    st = st[R.STATE_COLUMNS]
    return st.reindex(sorted(set(st.index) | set(pd.to_datetime(dates))))


def daily_state():
    """regime.market_state_daily on the cached prices (for off-grid time-machine dates + a check)."""
    ix = pd.read_pickle(INDEX_CACHE)
    bench = ix[ix["index_key"] == BENCHMARK].set_index("price_date")["close"].sort_index()
    px = pd.read_pickle(STOCK_CACHE)
    wide = px.pivot_table(index="price_date", columns="company_id", values="close", aggfunc="last")
    return R.market_state_daily(bench, wide)


def rule_states(grid):
    """dates x rule name -> True when in the risk regime (hysteresis walks the whole grid)."""
    g = grid.sort_index()
    return pd.DataFrame({r.name: R.regime_state(g, r) == "risk" for r in R.RULES}, index=g.index)


def load_panel(labels):
    if PANEL_CACHE is not None and PANEL_CACHE.exists():
        return pd.read_pickle(PANEL_CACHE)
    panel, _ = nonfin_panel(labels)
    feats = rank_market(pd.read_pickle(FEATURES_FILE), columns=["vol_3m", "mom_1m"])
    panel = panel.merge(feats[["company_id", "signal_date", "vol_3m", "mom_1m"]],
                        on=["company_id", "signal_date"], how="left")
    panel["lowvol"] = 1 - panel["vol_3m"]
    panel["reversal"] = 1 - panel["mom_1m"]
    for name, w in R.ALTERNATIVES.items():
        panel[f"alt_{name}"] = R.blend(panel, w)
    panel["alt_normal"] = R.blend(panel, R.NORMAL_WEIGHTS)
    if PANEL_CACHE is not None:
        panel.to_pickle(PANEL_CACHE)
    return panel


# ---------------------------------------------------------
# Walk-forward
# ---------------------------------------------------------

def per_date_ic(data, cols, h):
    """signal date x column -> Spearman IC of the column vs excess_h (dates with >= 50 rows)."""
    out = {}
    for d, g in data.groupby("signal_date"):
        if len(g) < MIN_ROWS_PER_DATE:
            continue
        ex = g[f"excess_{h}"].rank()
        out[d] = {c: g[c].rank().corr(ex) for c in cols}
    return pd.DataFrame(out).T.sort_index()


EPISODES = {"2018-19": (2018, 2019), "2020": (2020, 2020), "2022": (2022, 2022), "2025-26": (2025, 2026)}


def trend_diagnostic(states):
    """Does a risk state reverse price trend outside COVID? trend6 (and the tilts) per-date IC on the
    whole market-model universe from 2017 (no financials needed, so the 2018-19 bear is included),
    averaged over each rule's risk dates per episode, vs all normal dates."""
    from growth_model.market_model import load_dataset, trend_score

    df = load_dataset()
    df["trend6"] = trend_score(df)
    df["lowvol"] = 1 - df["vol_3m"]
    df["reversal"] = 1 - df["mom_1m"]
    rows = []
    for h in HORIZONS:
        ic = per_date_ic(df[df[f"excess_{h}"].notna()], ["trend6", "lowvol", "reversal"], h)
        st = states.reindex(ic.index).fillna(False)
        for r in R.RULES:
            risk = st[r.name].astype(bool)
            row = {"rule": r.name, "h": h, "normal": ic.loc[~risk, "trend6"].mean(), "n_risk": int(risk.sum())}
            for ep, (a, b) in EPISODES.items():
                m = risk & (ic.index.year >= a) & (ic.index.year <= b)
                row[ep] = ic.loc[m, "trend6"].mean() if m.any() else np.nan
                row[f"n_{ep}"] = int(m.sum())
            row["risk_all"] = ic.loc[risk, "trend6"].mean()
            row["reversal_risk"] = ic.loc[risk, "reversal"].mean()
            row["lowvol_risk"] = ic.loc[risk, "lowvol"].mean()
            rows.append(row)
    return pd.DataFrame(rows)


def candidate_ic(ic, states):
    """dates x candidate -> per-date IC; candidate (rule, alt) uses alt on risk dates, else investiq-v1."""
    cand = {BASE: ic[BASE_COL]}
    st = states.reindex(ic.index).fillna(False)
    for r in R.RULES:
        for a in R.ALTERNATIVES:
            cand[f"{r.name}|{a}"] = ic[f"alt_{a}"].where(st[r.name], ic[BASE_COL])
    return pd.DataFrame(cand)


def objective(ic_series):
    yr = ic_series.groupby(ic_series.index.year).mean().dropna()
    if len(yr) == 0:
        return -np.inf
    sd = yr.std(ddof=0) if len(yr) > 1 else 0.0
    return yr.mean() - STABILITY_PENALTY * sd


def choose(cand_ic):
    """argmax of the stability-penalised IC; ties -> investiq-v1 (listed first)."""
    if len(cand_ic) == 0:
        return BASE, {c: -np.inf for c in cand_ic.columns}
    objs = {c: objective(cand_ic[c]) for c in cand_ic.columns}
    best = BASE
    for c, v in objs.items():
        if v > objs[best] + 1e-12:
            best = c
    return best, objs


def candidate_score(frame, name, states):
    if name == BASE:
        return frame[BASE_COL]
    rule, alt = name.split("|")
    risk = frame["signal_date"].map(states[rule]).fillna(False).astype(bool)
    return frame[f"alt_{alt}"].where(risk, frame[BASE_COL])


def walk_forward(panel, states, h, cand_ic):
    data = panel[panel[f"excess_{h}"].notna() & panel[f"top_q_{h}"].notna()]
    chosen, scored = {}, []
    for year in range(FIRST_TEST_YEAR, data["signal_date"].max().year + 1):
        cutoff = pd.Timestamp(year, 1, 1) - pd.Timedelta(days=PURGE_DAYS[h])
        train_ic = cand_ic[cand_ic.index < cutoff]
        test = data[data["signal_date"].dt.year == year].copy()
        # combiner_eval's fold rule: >= 6 training signal dates of any size (IC needs >= 50 rows a date)
        if len(test) == 0 or data.loc[data["signal_date"] < cutoff, "signal_date"].nunique() < 6:
            continue
        best, objs = choose(train_ic)
        chosen[year] = best
        test["regime_wf"] = candidate_score(test, best, states)
        test["primary"] = candidate_score(test, "|".join(R.PRIMARY), states)
        scored.append(test)
        print(f"  {h} {year}: train {len(train_ic)} dates (< {cutoff:%Y-%m-%d}); chosen {best} "
              f"(obj {objs[best]:.4f} vs {BASE} {objs[BASE]:.4f})")
    return pd.concat(scored), chosen


def date_ranges(dates):
    """Compress a sorted list of grid dates into 'YYYY-MM-DD..YYYY-MM-DD (n)' runs."""
    dates = sorted(pd.to_datetime(dates))
    runs, start, prev, n = [], None, None, 0
    for d in dates:
        if prev is not None and (d - prev).days <= 17:
            prev, n = d, n + 1
            continue
        if start is not None:
            runs.append((start, prev, n))
        start, prev, n = d, d, 1
    if start is not None:
        runs.append((start, prev, n))
    return ", ".join(f"{a:%Y-%m-%d}" + (f"..{b:%Y-%m-%d}" if b != a else "") + f" ({k})" for a, b, k in runs)


def passes(res, live_choice):
    checks = {}
    for h in HORIZONS:
        b, r = res[h]["per_year"][BASE], res[h]["per_year"]["regime_wf"]
        m = b.merge(r, on="year", suffixes=("_b", "_r"))
        trig = res[h]["trigger_ic"]
        checks[h] = {
            "ic_not_worse": bool(r["ic"].mean() >= b["ic"].mean()),
            "spread_not_worse": bool(r["spread"].mean() >= b["spread"].mean() - SHIP_SPREAD_TOL),
            "no_year_worse_by_0.01": bool(((m["ic_r"] - m["ic_b"]) >= -SHIP_YEAR_IC_TOL).all()),
            "trigger_dates_better": bool(len(trig) > 0 and trig["regime_wf"].mean() > trig[BASE].mean()),
        }
    ok = all(all(c.values()) for c in checks.values()) and live_choice != BASE
    return ok, checks


# ---------------------------------------------------------
# Time machine
# ---------------------------------------------------------

def label_proxy(panel, states, choice, windows):
    """Same windows on the label panel: nearest grid date at or before the start, 12m or 6m label."""
    rows = []
    grid = np.array(sorted(panel["signal_date"].unique()))
    for name, d0, d1 in windows:
        d = pd.Timestamp(d0)
        g = grid[grid <= np.datetime64(d)]
        if not len(g):
            continue
        sd = pd.Timestamp(g[-1])
        end = pd.Timestamp(d1) if d1 else pd.Timestamp(date.today())
        h = "12m" if (end - d).days > 250 else "6m"
        t = panel[(panel["signal_date"] == sd) & panel[f"excess_{h}"].notna()].copy()
        if len(t) < MIN_ROWS_PER_DATE:
            rows.append({"window": name, "grid_date": sd.date(), "h": h, "n": len(t)})
            continue
        t["cand"] = candidate_score(t, choice, states)
        top_b = t.nlargest(50, BASE_COL)[f"ret_{h}"].mean()
        top_c = t.nlargest(50, "cand")[f"ret_{h}"].mean()
        rule = choice.split("|")[0] if choice != BASE else None
        rows.append({"window": name, "grid_date": sd.date(), "h": h, "n": len(t),
                     "state": ("risk" if rule and bool(states[rule].get(sd, False)) else "normal"),
                     "ic_base": t[BASE_COL].corr(t[f"excess_{h}"], method="spearman"),
                     "ic_regime": t["cand"].corr(t[f"excess_{h}"], method="spearman"),
                     "top50_base": top_b, "top50_regime": top_c, "all": t[f"ret_{h}"].mean(),
                     "bench": t[f"bench_{h}"].median()})
    return pd.DataFrame(rows)


def run_time_machine(choice, state_daily, windows):
    """Real time machine (build_v3 from the DB) with investiq-v1 and with the regime weights."""
    from news_pipeline.db import get_connection

    from growth_model.labels import signal_dates

    from . import build_v3 as v3
    from . import time_machine as tm

    rule, alt = choice.split("|")
    weights = R.ALTERNATIVES[alt]
    if set(k for k, v in weights.items() if v) - {"market", "financial"}:
        print(f"time machine: {alt} has a tilt build_v3 cannot express; label proxy only")
        return []
    hist = state_daily.copy()
    rows = []
    conn = get_connection()
    base_w = v3.MARKET_WEIGHT
    try:
        for name, d0, d1 in windows:
            snap = pd.Timestamp(d0)
            # state on the snapshot date: hysteresis walks the 1st/16th grid up to D, plus D itself
            grid = [d for d in signal_dates("2017-01-01", snap) if d < snap] + [snap]
            st = R.regime_state(R.state_on(hist, grid), rule).iloc[-1]
            end = pd.Timestamp(d1).date() if d1 else date.today()
            out = {"window": name, "snap": snap.date(), "state": st}
            for label, w in (("base", base_w), ("regime", weights["market"] if st == "risk" else base_w)):
                if label == "regime" and st != "risk":
                    out.update({k.replace("base", "regime"): v for k, v in list(out.items()) if k.endswith("_base")})
                    continue
                v3.MARKET_WEIGHT = w
                try:
                    win = tm.run_window(conn, snap.date(), end)
                except tm.NotRankable as e:
                    out[f"ic_{label}"] = None
                    out["note"] = str(e)[:80]
                    continue
                pf = win["pf"]
                top = next(v for k, v in pf.items() if k.startswith("Top"))
                dec = win["rows"].groupby("decile")["actual_return"].mean()
                out.update({f"ic_{label}": win["ic"], f"top50_{label}": top.iloc[-1] - 1,
                            f"dd50_{label}": tm.max_dd(top), f"dec10_{label}": dec.get(10),
                            f"dec1_{label}": dec.get(1), "all": pf["All ranked stocks"].iloc[-1] - 1,
                            "bench": win["bench"], "end": win["end"]})
            rows.append(out)
            print(f"  TM {name}: state {st}; IC base {out.get('ic_base')}, regime {out.get('ic_regime')}", flush=True)
    finally:
        v3.MARKET_WEIGHT = base_w
        conn.close()
    return rows


# ---------------------------------------------------------
# Report
# ---------------------------------------------------------

f3 = lambda x: "—" if x is None or pd.isna(x) else f"{x:+.3f}"            # noqa: E731
fp = lambda x: "—" if x is None or pd.isna(x) else f"{x * 100:+.1f}%"      # noqa: E731


def write_report(ctx):
    L = ["# Market-regime switch: walk-forward and time-machine test", "",
         f"Generated {date.today()} by `python3 -m rankings.regime_eval{' --tm' if ctx['tm'] else ''}` "
         "(rules: `ml/rankings/regime.py`, pre-declared; evaluation logic: combiner_eval Part A).", "",
         f"**Verdict: {ctx['verdict']}**", ""]
    L += ["## 1. Pre-declared rules and alternatives", "",
          "| rule | definition | risk dates 2017-2026 | trigger dates |", "|---|---|---|---|"]
    for r in R.RULES:
        d = ctx["states"].index[ctx["states"][r.name]]
        L.append(f"| `{r.name}` | {r.text} | {len(d)} | {date_ranges(d) or '—'} |")
    L += ["", "Risk-regime alternatives (normal regime: market .7, financial .3): " +
          "; ".join(f"`{k}` = " + ", ".join(f"{c} {w}" for c, w in v.items()) for k, v in R.ALTERNATIVES.items()),
          f"Primary hypothesis (fixed before testing): `{'|'.join(R.PRIMARY)}`.", ""]
    L += ["## 2. Does a risk state reverse trend? (market-model universe from 2017, trend6 only)", "",
          "Mean per-date IC of trend6 on each rule's risk dates, by episode (number of dates), vs its normal dates; "
          "last two columns: IC of the reversal and low-volatility tilts on all risk dates. This uses no financial "
          "data, so it covers the 2018-19 bear that the walk-forward panel (financials from 2019-05) cannot see.", ""]
    for h in HORIZONS:
        t = ctx["diag"][ctx["diag"]["h"] == h]
        L += [f"**{h}**", "", "| rule | " + " | ".join(EPISODES) + " | all risk dates | normal dates | reversal (risk) | lowvol (risk) |",
              "|---|" + "---|" * (len(EPISODES) + 4)]
        for _, r in t.iterrows():
            L.append(f"| `{r['rule']}` | " + " | ".join(
                (f"{r[ep]:+.3f} ({r[f'n_{ep}']})" if r[f"n_{ep}"] else "—") for ep in EPISODES)
                + f" | {f3(r['risk_all'])} | {f3(r['normal'])} | {f3(r['reversal_risk'])} | {f3(r['lowvol_risk'])} |")
        L.append("")
    L += ["## 3. Walk-forward (test years 2020+, rule chosen on purged training years per fold)", ""]
    for h in HORIZONS:
        res = ctx["res"][h]
        L += [f"### {h}", "", "Chosen per test year: " +
              ", ".join(f"{y}: `{c}`" for y, c in res["chosen"].items()), "",
              "| method | year | IC | top-bottom decile | top-decile beat |", "|---|---|---|---|---|"]
        for m, t in res["per_year"].items():
            for _, r in t.iterrows():
                L.append(f"| {m} | {int(r.year)} | {r.ic:+.3f} | {fp(r.spread)} | {r.top10_beat * 100:.1f}% |")
        L += ["", "| method | mean IC | mean spread | top-decile beat | years IC > 0 | years top10 > all |",
              "|---|---|---|---|---|---|"]
        for m, s in res["summary"].items():
            L.append(f"| {m} | {s['ic_mean']:+.4f} | {fp(s['spread_mean'])} | {s['top10_beat_mean'] * 100:.1f}% | "
                     f"{s['years_ic_positive']} | {s['years_top10_above_universe']} |")
        L += ["", f"Per-date IC on test-year dates where the walk-forward choice was in the risk regime ({h}):", "",
              "| signal date | rule in force | investiq-v1 IC | regime IC | primary IC |", "|---|---|---|---|---|"]
        for d, r in res["trigger_ic"].iterrows():
            L.append(f"| {d:%Y-%m-%d} | `{r['choice']}` | {f3(r[BASE])} | {f3(r['regime_wf'])} | {f3(r['primary'])} |")
        if not len(res["trigger_ic"]):
            L.append("| (none) | | | | |")
        L += ["", f"Key dates ({h}, per-date IC; every candidate equals investiq-v1 on its normal dates):", "",
              "| signal date | investiq-v1 | " + " | ".join(f"`{a}`" for a in R.ALTERNATIVES) + " |",
              "|---|---|" + "---|" * len(R.ALTERNATIVES)]
        for d, r in res["key_dates"].iterrows():
            L.append(f"| {d:%Y-%m-%d} | {f3(r[BASE_COL])} | " + " | ".join(f3(r[f'alt_{a}']) for a in R.ALTERNATIVES) + " |")
        L.append("")
    L += ["## 4. Whole grid on test years (record only; not used to choose)", "",
          "Mean yearly IC minus investiq-v1's on the same test years (6m / 12m), and test years where the "
          "candidate's IC is more than 0.01 worse.", "",
          "| rule | " + " | ".join(f"`{a}`" for a in R.ALTERNATIVES) + " |", "|---|" + "---|" * len(R.ALTERNATIVES)]
    for r in R.RULES:
        cells = []
        for a in R.ALTERNATIVES:
            g = ctx["grid"][f"{r.name}|{a}"]
            cells.append(f"{g['6m'][0]:+.4f} / {g['12m'][0]:+.4f} ({g['6m'][1]}/{g['12m'][1]})")
        L.append(f"| `{r.name}` | " + " | ".join(cells) + " |")
    L += ["", "## 5. Live choice (same objective on all labelled years, 6m and 12m averaged)", "",
          "| candidate | objective 6m | objective 12m | average |", "|---|---|---|---|"]
    for c, (o6, o12, avg) in ctx["live_top"]:
        L.append(f"| `{c}` | {o6:.4f} | {o12:.4f} | {avg:.4f} |")
    L += ["", f"Live choice: `{ctx['live']}`.", "", "Ship criteria (pre-declared):", ""]
    for h, c in ctx["checks"].items():
        L.append(f"- {h}: " + ", ".join(f"{k} {'yes' if v else 'NO'}" for k, v in c.items()))
    L += ["", "## 6. Time-machine windows", "",
          f"Label-panel proxy for `{ctx['tm_choice']}` (nearest grid date, 12m label when the window is > 250 days "
          "else 6m; top 50 by score, raw return; non-financial rows only):", "",
          "| window | grid date | h | state | IC investiq-v1 | IC regime | top 50 v1 | top 50 regime | all | Smallcap 250 |",
          "|---|---|---|---|---|---|---|---|---|---|"]
    for _, r in ctx["proxy"].iterrows():
        L.append(f"| {r['window']} | {r['grid_date']} | {r['h']} | {r.get('state', '—')} | {f3(r.get('ic_base'))} | "
                 f"{f3(r.get('ic_regime'))} | {fp(r.get('top50_base'))} | {fp(r.get('top50_regime'))} | "
                 f"{fp(r.get('all'))} | {fp(r.get('bench'))} |")
    if ctx["tm_rows"]:
        L += ["", f"Real time machine (build_v3 from the DB, all ranked companies incl. financials; "
              f"`{ctx['tm_choice']}` sets MARKET_WEIGHT on risk dates only):", "",
              "| window | ranked → held to | state | IC v1 | IC regime | top 50 v1 | top 50 regime | top-50 drawdown v1 / regime | all ranked | Smallcap 250 |",
              "|---|---|---|---|---|---|---|---|---|---|"]
        for r in ctx["tm_rows"]:
            L.append(f"| {r['window']} | {r['snap']} → {r.get('end', '—')} | {r['state']} | {f3(r.get('ic_base'))} | "
                     f"{f3(r.get('ic_regime'))} | {fp(r.get('top50_base'))} | {fp(r.get('top50_regime'))} | "
                     f"{fp(r.get('dd50_base'))} / {fp(r.get('dd50_regime'))} | {fp(r.get('all'))} | {fp(r.get('bench'))} |")
    L += ["", "## 7. Assessment", "", *ctx["assessment"], ""]
    with open(REPORT_FILE, "w") as fh:
        fh.write("\n".join(L))
    print(f"wrote {REPORT_FILE}")


# ---------------------------------------------------------
# Main
# ---------------------------------------------------------

def main(argv=None):
    global PANEL_CACHE
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--tm", action="store_true", help="also run the real time machine (DB, SELECT only)")
    ap.add_argument("--cache", help="pickle path to cache the panel between runs")
    ap.add_argument("--tm-choice", help="candidate 'rule|alt' for the time machine (default: live / walk-forward / primary)")
    args = ap.parse_args(argv)
    warnings.filterwarnings("ignore")
    t0 = time.time()
    if args.cache:
        from pathlib import Path
        PANEL_CACHE = Path(args.cache)
    from growth_model.labels import LABELS_FILE
    labels = pd.read_pickle(LABELS_FILE)
    panel = load_panel(labels)
    grid = market_state_grid(panel["signal_date"].unique())
    states = rule_states(grid)
    print(f"panel {len(panel):,} rows, {panel['signal_date'].nunique()} dates ({time.time() - t0:.0f}s)")
    for r in R.RULES:
        print(f"  {r.name:<18} risk on {int(states[r.name].sum()):>3} dates: {date_ranges(states.index[states[r.name]])}")

    alt_cols = [BASE_COL] + [f"alt_{a}" for a in R.ALTERNATIVES]
    res, cand_ics, out = {}, {}, {"rules": [r.name for r in R.RULES], "alternatives": R.ALTERNATIVES,
                                  "primary": "|".join(R.PRIMARY), "horizons": {}}
    key = pd.to_datetime(["2020-03-01", "2020-03-16", "2020-04-01", "2020-04-16", "2020-05-01", "2020-05-16",
                          "2020-06-01", "2020-06-16", "2022-06-16", "2022-07-01", "2025-02-16", "2025-03-01",
                          "2025-03-16", "2025-04-01", "2026-03-16", "2026-04-01"])
    for h in HORIZONS:
        data = panel[panel[f"excess_{h}"].notna() & panel[f"top_q_{h}"].notna()]
        ic = per_date_ic(data, alt_cols, h)
        cand = candidate_ic(ic, states)
        cand_ics[h] = cand
        scored, chosen = walk_forward(panel, states, h, cand)
        methods = {BASE: BASE_COL, "regime_wf": "regime_wf", "primary": "primary", "trend6": "mix_1.0"}
        per = {m: yearly(scored, c, h, FIRST_TEST_YEAR) for m, c in methods.items()}
        summ = {m: summary(t) for m, t in per.items()}
        # trigger dates of the walk-forward choice in test years
        trig = []
        for d in sorted(scored["signal_date"].unique()):
            d = pd.Timestamp(d)
            c = chosen.get(d.year, BASE)
            if c != BASE and bool(states[c.split("|")[0]].get(d, False)) and d in cand.index:
                trig.append({"date": d, "choice": c, BASE: cand.loc[d, BASE], "regime_wf": cand.loc[d, c],
                             "primary": cand.loc[d, "|".join(R.PRIMARY)]})
        trig = pd.DataFrame(trig).set_index("date") if trig else pd.DataFrame(columns=["choice", BASE, "regime_wf", "primary"])
        res[h] = {"chosen": chosen, "per_year": per, "summary": summ, "trigger_ic": trig,
                  "key_dates": ic.reindex([d for d in key if d in ic.index])}
        print(f"\n=== {h} ===")
        for m, s in summ.items():
            print(f"  {m:<12} IC {s['ic_mean']:+.4f}  spread {s['spread_mean']:+.1%}  beat {s['top10_beat_mean']:.1%}  "
                  f"yrs IC>0 {s['years_ic_positive']}  yrs top10>all {s['years_top10_above_universe']}")
        print(pd.concat({m: t.set_index("year")[["ic", "spread", "top10_beat"]] for m, t in per.items()}, axis=1).round(3).to_string())
        print("trigger dates:\n" + (trig.round(3).to_string() if len(trig) else "  none"))
        out["horizons"][h] = {"chosen": {str(y): c for y, c in chosen.items()}, "summary": summ,
                              "per_year": {m: t.round(4).to_dict("records") for m, t in per.items()},
                              "trigger_ic": trig.reset_index().astype(str).to_dict("records")}

    diag = trend_diagnostic(states)
    print("\ntrend diagnostic:\n" + diag.round(3).to_string())

    # whole grid on test years (record only)
    grid_rec = {}
    for c in cand_ics["6m"].columns:
        if c == BASE:
            continue
        rec = {}
        for h in HORIZONS:
            ci = cand_ics[h]
            test = ci[ci.index.year >= FIRST_TEST_YEAR]
            yb = test[BASE].groupby(test.index.year).mean()
            yc = test[c].groupby(test.index.year).mean()
            rec[h] = (float((yc - yb).mean()), int(((yc - yb) < -SHIP_YEAR_IC_TOL).sum()))
        grid_rec[c] = rec

    # live choice
    objs = {h: choose(cand_ics[h])[1] for h in HORIZONS}
    avg = {c: np.mean([objs[h][c] for h in HORIZONS]) for c in objs["6m"]}
    live = BASE
    for c, v in avg.items():
        if v > avg[live] + 1e-12:
            live = c
    live_top = sorted(avg, key=lambda c: -avg[c])[:10]
    if BASE not in live_top:
        live_top.append(BASE)
    live_top = [(c, (objs["6m"][c], objs["12m"][c], avg[c])) for c in live_top]
    print(f"\nlive choice: {live}  (avg obj {avg[live]:.4f} vs {BASE} {avg[BASE]:.4f})")
    ok, checks = passes(res, live)
    print(f"ship criteria: {ok} {checks}")

    # time machine
    tm_choice = args.tm_choice or (live if live != BASE else "|".join(R.PRIMARY))
    windows = TM_EVENTS + TM_EXTRA
    proxy = label_proxy(panel, states, tm_choice, windows)
    print(f"\nlabel proxy ({tm_choice}):\n{proxy.round(3).to_string()}")
    tm_rows = []
    if args.tm:
        ds = daily_state()
        chk = R.state_on(ds, grid.index).sub(grid).abs().max()
        print(f"daily-state recompute vs cached grid, max abs diff: {chk.round(4).to_dict()}")
        tm_rows = run_time_machine(tm_choice, ds, windows)

    verdict = (f"ship `{live}`" if ok else
               "no rule passed the pre-declared criteria; keep investiq-v1 (MARKET_WEIGHT 0.7 always)")
    ctx = {"tm": args.tm, "verdict": verdict, "states": states, "res": res, "grid": grid_rec, "live": live,
           "live_top": live_top, "checks": checks, "tm_choice": tm_choice, "proxy": proxy, "tm_rows": tm_rows,
           "assessment": ASSESSMENT, "diag": diag}
    write_report(ctx)
    out.update({"live_choice": live, "passes": ok, "checks": checks, "grid_on_test_years": grid_rec,
                "proxy": proxy.astype(str).to_dict("records"), "time_machine": [{k: str(v) for k, v in r.items()} for r in tm_rows]})
    OUT_FILE.write_text(json.dumps(out, indent=1, default=str))
    print(f"wrote {OUT_FILE} in {time.time() - t0:.0f}s")


ASSESSMENT = [  # written after the 2026-10-01 run; re-check if the numbers above change
    "- **The pre-declared walk-forward does not pass.** On 6m the regime model is slightly worse than investiq-v1 "
    "(mean yearly IC and decile spread lower): the 2020 fold had only 3 usable training dates (2019-05/06, all inside the "
    "2018-19 bear) and picked `dd25_exit_b50|w0.3_lowvol`, which made 2020 worse (spread -2.9% -> -8.9%). From 2021 the "
    "chosen rules rarely trigger in their test year, so 2021-2026 are identical or within +-0.005 IC: neutral, not better. "
    "12m passes, but only because one date (2025-03-01) differs.",
    "- **No fold could learn from COVID before 2020.** The financial panel starts 2019-05, so the only crash the "
    "walk-forward can test out of sample is the one used to motivate the idea. Every claim that a rule \"fixes\" April "
    "2020 is in-sample.",
    "- **Deep-fall states do not reliably reverse trend.** On the 2017+ market universe (section 2), trend6 IC on "
    "dd25 / breadth / bear12 risk dates in the 2018-19 bear was +0.20 to +0.30, *higher* than on normal dates (+0.11). "
    "Only the COVID V-rebound (and, on 6m only, March 2025) reversed. A rule keyed to drawdown or breadth would have "
    "cut the trend weight exactly when trend worked best in 2018-19. Panic rules (stress, ret3m_m20, dd25_and_vol30) "
    "avoid 2018-19 but fire on 5-9 dates in one or two episodes: there is nothing to validate them on.",
    "- **Even in-sample the fix is partial.** With trend weight 0 on COVID dates the IC goes from -0.19 to -0.06 "
    "(time machine, 2020-04-16) but stays negative: fin-v1 also failed in 2020. The reversal tilt helped in March 2020 "
    "only; the low-vol tilt made 2020 worse (the rebound was led by high-volatility stocks).",
    "- **Time machine with the in-sample favourite `dd25_or_b15|w0.0`:** windows ranked in a normal state are unchanged "
    "by construction (one year ago, COVID crash, crash + rebound, 2022, 2024-25). Ranked in the risk state: Post-COVID "
    "IC -0.19 -> -0.06 and top 50 +101% -> +122%; COVID low 6m IC -0.17 -> -0.03 but top 50 +94% -> +88%; May 2020 "
    "IC -0.26 -> -0.12, top 50 +119% -> +131%; March 2025 12m IC +0.08 -> +0.07 but top 50 -5% -> +9%; spring 2026 "
    "about the same. Mixed on the top-50 measure and always in-sample.",
    "- **Recommendation: do not ship a regime switch now.** Keep investiq-v1 (MARKET_WEIGHT 0.7 always) and keep "
    "regime.RECOMMENDED = None. Re-run `python3 -m rankings.regime_eval --tm` after the next deep fall adds an "
    "out-of-sample episode, or once financial history before 2019 (or a trend-only fallback panel) lets the 2018-19 "
    "bear enter the training folds. If the owner still wants a guard, the least risky ex-post option is a panic-only "
    "rule (`stress_exit_ma200` or `ret3m_m20`, market weight 0.3), presented as a judgement call, not a tested result.",
]


if __name__ == "__main__":
    main()
