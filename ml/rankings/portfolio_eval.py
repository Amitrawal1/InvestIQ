"""Portfolio-level backtest of the InvestIQ "Top list": how should the N names be chosen from the ranking?

The ranking (investiq-v1) orders stocks well, but the plain equal-weight top 50 trailed the NIFTY
SMALLCAP 250 last year (+4.1% vs +5.9%, drawdown -23% vs -18%) and drew down -34% vs -27% in the
2022 sell-off (TIME_MACHINE.md). This tests list-construction rules (rankings/portfolio.py), not the
score.

Scores (point-in-time, same rows as rankings/combiner_eval.py)
--------------------------------------------------------------
Label grid of growth_model/labels.py (1st and 16th of every month), liquid universe (median traded
value >= 0.5 cr/day over 60 days, >= 252 trading days), only rows the live ranking could rank:
    non-financial  combiner_eval.nonfin_panel: market = trend6 percentile, financial = fin-v1
                   percentile; growth_score = 0.95 x (0.70 market + 0.30 financial) x 100 + 0.05 x 50
                   - 6 (negative equity)                                    (build_v3.score_v3)
    banks / NBFCs  combiner_eval.fin_panel (eligible rows): growth_score = 0.95 x market x 100
    / insurers     + 0.05 x 50 - asset-quality 4 / capital-near-minimum 6 / negative-equity 6
News has no history: a constant 50 (it does not change the order). Lenders in fin_sector scope have
their features.py rows removed from the non-financial panel, as build_v3 does. Differences from the
live build: percentiles are within the liquid universe (live: all listed names) and names trading
< 0.5 cr/day are never in the backtest list (live lists them with a "thinly traded" risk). Volatility
(vol_3m), 6-month return (mom_6m) and the 200-day gap come from growth_market_features.pkl (prices
up to D). Sectors: today's `companies` table (SELECT only).

Simulation
----------
Rebalance on every grid date D from the first date with >= MIN_NAMES ranked names (mid-2019) to the
last labelled date. The list is chosen with select_top_list(scores on D, holdings before D, rules),
bought at the first close strictly after D (labels.py entry day; you act on the ranking the next
session), equal weight, and held (weights drift) until the next entry day. Daily closes come from
growth_stock_prices.pkl on the benchmark calendar, forward-filled (a stock that stops trading keeps its
last close). A one-day move > +100% or < -60% is a data break (labels.py): that day's return is set
to 0 instead of counting a fake 100x (or -90%) move. Costs: COST_PER_SIDE = 0.3% of traded value on
every buy and sell (brokerage, STT, impact for small caps), charged at each rebalance on
sum |new weight - drifted weight| (the first purchase included). Returns are price returns (no
dividends), before tax.
Benchmarks: NIFTY SMALLCAP 250 (price index) and the equal-weight universe (every ranked name, same
rebalance dates, no costs).

Pre-declared grid (written before any run; 11 single variants + combinations)
-----------------------------------------------------------------------------
    a  base       top 50 by score, equal weight, full replacement     (today's implied list)
    b  liq2/liq5  liquidity floor adv_60d >= 2 / 5 crore
    c  sector20   <= 20% of names per sector
    d  volx5      no new buys in the top 5% of vol_3m on D
       riskadj    market part of the score -> percentile of market / vol_3m
       lowvol     the 50 least volatile of the top 100 by score
    e  buf100/150 keep a holding while its rank <= 100 / 150; fill vacancies from the top
    f  nostretch  no new buys up > 100% in 6m or >= 60% above the 200-day average
    g  n30        top 30 instead of 50
Combination (rule fixed before the run, `pick_combo`): from each family (liquidity, sector, risk,
buffer, stretched) take its best member by the robustness key; keep the family only if that member
beats the baseline on the key. Robustness key, in order: calendar years beating the Smallcap 250
(net of costs), max drawdown (rounded to 1 pt), net CAGR. The combination is run at N = 50 and N = 30
and the better (same key) is the data-selected rule set. Also run, independently of the data: the
"prior" rule set that docs/model-report.md proposed before this test (liq5 + sector20 + riskadj +
buf100), and leave-one-out versions of the selected set. With ~11 variants, ~4 families and only 7
calendar years (2 partial), a 1-2 pt CAGR difference between variants is noise; the halves table
(2019-22 vs 2023-26) shows whether a rule's gain holds in both.

Windows: the time-machine windows (rankings/time_machine.EVENTS) on the continuously run strategy
(the list as a follower would have held it on the window's start, rebalanced inside the window):
return from the first close after the start to the last close on or before the end, and the
worst drawdown inside. This differs from TIME_MACHINE.md, which buys one snapshot and holds it.

Caveats: survivorship (stock_prices has only companies listed today: every variant is flattered,
roughly equally), today's sector labels, financial balance sheets only from late 2022, overlapping
windows, one cost assumption.

Outputs: ml/rankings/reports/PORTFOLIO.md, ml/data/processed/portfolio_eval.json.

CLI:  caffeinate -i python3 -m rankings.portfolio_eval [--cost 0.003]
"""

import argparse
import json
import time
import warnings
from pathlib import Path

import numpy as np
import pandas as pd

from growth_model.market_model import FEATURES_FILE
from growth_model.prices import BENCHMARK, CACHE_DIR, STOCK_CACHE, INDEX_CACHE

from .combiner_eval import FIN_PENALTY, fin_panel, nonfin_panel, penalty_points
from .portfolio import RECOMMENDED, Rules, select_top_list
from .time_machine import EVENTS

COST_PER_SIDE = 0.003
MIN_NAMES = 250
BREAK_UP, BREAK_DOWN = 1.0, -0.6          # growth_model/labels.py
NEWS_NEUTRAL = 50
SPLIT_YEAR = 2023                          # halves: < 2023 vs >= 2023
REPORT = Path(__file__).resolve().parent / "reports" / "PORTFOLIO.md"
OUT_FILE = CACHE_DIR / "portfolio_eval.json"

BASE = Rules(n=50)
SINGLES = {                                # family, rules  (declared before any run)
    "base": (None, BASE),
    "liq2": ("liquidity", BASE.with_(min_adv_cr=2)),
    "liq5": ("liquidity", BASE.with_(min_adv_cr=5)),
    "sector20": ("sector", BASE.with_(sector_cap=0.2)),
    "volx5": ("risk", BASE.with_(vol_exclude_pct=0.05)),
    "riskadj": ("risk", BASE.with_(risk_adjust="score")),
    "lowvol": ("risk", BASE.with_(risk_adjust="lowvol", lowvol_pool=2)),
    "buf100": ("buffer", BASE.with_(buffer_rank=100)),
    "buf150": ("buffer", BASE.with_(buffer_rank=150)),
    "nostretch": ("stretched", BASE.with_(exclude_stretched=True)),
    "n30": ("size", Rules(n=30)),
}
PRIOR = BASE.with_(min_adv_cr=5, sector_cap=0.2, risk_adjust="score", buffer_rank=100)
# Added AFTER the first run (labelled post-hoc in the report): the two single rules that helped in both
# halves (volx5) or cut turnover at no net cost (buffers), combined.
POSTHOC = {
    "volx5+buf100": BASE.with_(vol_exclude_pct=0.05, buffer_rank=100),
    "volx5+buf150": BASE.with_(vol_exclude_pct=0.05, buffer_rank=150),
    "recommended": RECOMMENDED,        # = volx5+buf150 with the universe floor written out (a no-op here)
}
COST_GRID = [0.0, 0.003, 0.006]
TM_CSV = Path(__file__).resolve().parent / "reports" / "time_machine_2025-09-30_2026-09-28.csv"


# ---------------------------------------------------------
# Data
# ---------------------------------------------------------

def load_scores(labels):
    """Point-in-time investiq-v1 scores on the label grid + selection inputs (see docstring)."""
    from growth_model.prices import load_companies

    nf, _ = nonfin_panel(labels)
    fp, table = fin_panel(labels)
    in_scope = set(table["company_id"].dropna().astype(int))
    nf = nf[~nf["company_id"].isin(in_scope)]
    nf_score = ((1 - 0.05) * (0.7 * nf["market"] + 0.3 * nf["financial"]) * 100 + 0.05 * NEWS_NEUTRAL
                - penalty_points(nf, {"flag_negative_equity": 6}))
    fp_score = (1 - 0.05) * fp["market"] * 100 + 0.05 * NEWS_NEUTRAL - penalty_points(fp, FIN_PENALTY)
    cols = ["company_id", "signal_date", "market", "adv_60d_cr", "days_listed"]
    s = pd.concat([nf[cols].assign(growth_score=nf_score.clip(0, 100).values, is_fin_sector=False),
                   fp[cols].assign(growth_score=fp_score.clip(0, 100).values, is_fin_sector=True)],
                  ignore_index=True)
    s = s.drop_duplicates(["company_id", "signal_date"])
    mk = pd.read_pickle(FEATURES_FILE)[["company_id", "signal_date", "vol_3m", "mom_6m", "ma200_gap"]]
    s = s.merge(mk, on=["company_id", "signal_date"], how="left")
    comp = load_companies()[["company_id", "symbol", "sector"]]
    s = s.merge(comp, on="company_id", how="left")
    s = s.rename(columns={"adv_60d_cr": "adv_cr", "vol_3m": "volatility", "mom_6m": "return_6m"})
    s["market_score"] = s["market"] * 100
    return s


def load_daily():
    """-> (daily stock returns on the benchmark calendar with breaks zeroed, benchmark closes, n breaks)."""
    stocks, index = pd.read_pickle(STOCK_CACHE), pd.read_pickle(INDEX_CACHE)
    bench = index[index["index_key"] == BENCHMARK].set_index("price_date")["close"].sort_index()
    cal = bench.index
    close = stocks[stocks["close"] > 0].pivot_table(index="price_date", columns="company_id",
                                                     values="close", aggfunc="last")
    close = close.reindex(close.index.union(cal)).ffill().reindex(cal)
    ret = close.pct_change(fill_method=None)
    broken = (ret > BREAK_UP) | (ret < BREAK_DOWN)
    ret = ret.mask(broken, 0.0).fillna(0.0)
    return ret, bench, int(broken.values.sum())


# ---------------------------------------------------------
# Simulation
# ---------------------------------------------------------

def simulate(scores, ret, bench, rules, cost=COST_PER_SIDE, universe=False):
    """-> dict(nav net, nav gross (daily Series from the first entry close), turnover per rebalance,
    list sizes, holdings per date)."""
    cal = ret.index
    col = {c: i for i, c in enumerate(ret.columns)}
    R = ret.values
    dates = sorted(scores["signal_date"].unique())
    by_date = dict(tuple(scores.groupby("signal_date")))
    entries = [cal.searchsorted(pd.Timestamp(d), side="right") for d in dates]
    pairs = [(d, e) for d, e in zip(dates, entries) if e < len(cal)]
    nav_g, nav_n = [1.0], [1.0]
    idx = [cal[pairs[0][1]]]
    held, w_drift = [], np.array([])
    turns, sizes, hist = [], [], {}
    for k, (d, e) in enumerate(pairs):
        frame = by_date[d]
        if universe:
            pick = frame[frame["growth_score"].notna()]["company_id"].tolist()
        else:
            pick = select_top_list(frame, held, rules)["company_id"].tolist()
        pick = [c for c in pick if c in col]
        hist[pd.Timestamp(d)] = pick
        new_w = pd.Series(1 / len(pick), index=pick)
        old_w = pd.Series(w_drift, index=held, dtype=float)
        traded = new_w.sub(old_w, fill_value=0).abs().sum()
        turn = traded / 2 if k > 0 else 0.0
        turns.append((pd.Timestamp(d), turn))
        sizes.append(len(pick))
        c = 0.0 if universe else cost * traded
        nav_n[-1] *= (1 - c)
        e_next = pairs[k + 1][1] if k + 1 < len(pairs) else len(cal) - 1
        if e_next <= e:
            break
        block = R[e + 1:e_next + 1][:, [col[x] for x in pick]]
        growth = np.cumprod(1 + block, axis=0)               # per stock value relative to entry
        path = growth.mean(axis=1)
        prev = np.concatenate([[1.0], path[:-1]])
        daily = path / prev - 1
        for r in daily:
            nav_g.append(nav_g[-1] * (1 + r))
            nav_n.append(nav_n[-1] * (1 + r))
        idx.extend(cal[e + 1:e_next + 1])
        w_drift = growth[-1] / growth[-1].sum()
        held = pick
    nav_g = pd.Series(nav_g, index=idx)
    nav_n = pd.Series(nav_n, index=idx)
    return dict(nav=nav_n, gross=nav_g, turnover=pd.Series(dict(turns)), sizes=sizes, holdings=hist)


# ---------------------------------------------------------
# Metrics
# ---------------------------------------------------------

def max_dd(nav):
    return float((nav / nav.cummax() - 1).min()) if len(nav) else np.nan


def years_of(nav):
    return (nav.index[-1] - nav.index[0]).days / 365.25


def cagr(nav):
    return float(nav.iloc[-1] / nav.iloc[0]) ** (1 / years_of(nav)) - 1


def yearly_returns(nav):
    """Calendar-year returns (first / last year partial), from the last close of the prior year."""
    out = {}
    for y in sorted(set(nav.index.year)):
        prior = nav[nav.index.year < y]
        start = prior.iloc[-1] if len(prior) else nav.iloc[0]
        out[y] = float(nav[nav.index.year == y].iloc[-1] / start - 1)
    return pd.Series(out)


def metrics(res, bench_nav, uni_nav):
    nav = res["nav"]
    r = nav.pct_change().dropna()
    vol = float(r.std() * np.sqrt(252))
    yr, yb = yearly_returns(nav), yearly_returns(bench_nav)
    turn = res["turnover"].iloc[1:]
    halves = {}
    for name, m in (("2019-22", nav.index.year < SPLIT_YEAR), ("2023-26", nav.index.year >= SPLIT_YEAR)):
        a, b = nav[m], bench_nav[m]
        halves[name] = {"cagr": cagr(a), "vs_index": cagr(a) - cagr(b), "max_dd": max_dd(a)}
    return {
        "cagr": cagr(nav), "cagr_gross": cagr(res["gross"]),
        "total": float(nav.iloc[-1] / nav.iloc[0] - 1),
        "vs_index_cagr": cagr(nav) - cagr(bench_nav), "vs_universe_cagr": cagr(nav) - cagr(uni_nav),
        "vs_index_total": float(nav.iloc[-1] / nav.iloc[0] - bench_nav.iloc[-1] / bench_nav.iloc[0]),
        "vol": vol, "max_dd": max_dd(nav), "sharpe": float(r.mean() * 252 / vol) if vol else np.nan,
        "years_beat": int((yr > yb).sum()), "years": len(yr),
        "turnover_yr": float(turn.sum() / years_of(nav)), "avg_names": float(np.mean(res["sizes"])),
        "per_year": yr.round(4).to_dict(), "halves": halves,
    }


def robust_key(m):
    return (m["years_beat"], round(m["max_dd"], 2), m["cagr"])


def window_stats(nav, d0, d1):
    s = nav[nav.index > pd.Timestamp(d0)]
    if d1:
        s = s[s.index <= pd.Timestamp(d1)]
    if len(s) < 2:
        return None
    return {"ret": float(s.iloc[-1] / s.iloc[0] - 1), "max_dd": max_dd(s / s.iloc[0]),
            "from": str(s.index[0].date()), "to": str(s.index[-1].date())}


def pick_combo(results, singles):
    """Pre-declared: best member per family by the robustness key, kept only if it beats the base."""
    base_key = robust_key(results["base"])
    chosen = {}
    for name, (fam, _) in singles.items():
        if fam in (None, "size"):
            continue
        if fam not in chosen or robust_key(results[name]) > robust_key(results[chosen[fam]]):
            chosen[fam] = name
    return {fam: n for fam, n in chosen.items() if robust_key(results[n]) > base_key}


def merge_rules(names, n):
    kw = {}
    for name in names:
        r = SINGLES[name][1]
        for f in ("min_adv_cr", "min_days_listed", "sector_cap", "vol_exclude_pct", "risk_adjust", "buffer_rank", "exclude_stretched"):
            v = getattr(r, f)
            if v not in (None, False):
                kw[f] = v
                if f == "risk_adjust":
                    kw["lowvol_pool"] = r.lowvol_pool
    if kw.get("buffer_rank") and n != 50:
        kw["buffer_rank"] = int(round(kw["buffer_rank"] * n / 50))     # same buffer relative to N
    return Rules(n=n, **kw)


# ---------------------------------------------------------
# Report
# ---------------------------------------------------------

P = lambda x, d=1: "—" if x is None or pd.isna(x) else f"{x * 100:+.{d}f}%"       # noqa: E731


def main_table(results, rules_of, bench_m, uni_m):
    lines = ["| variant | rules | CAGR (net) | CAGR gross | total | vs Smallcap 250 (CAGR / total) | vs EW universe (CAGR) "
             "| vol | max DD | return/vol | years beating index | turnover / yr | avg names |",
             "|---|---|---|---|---|---|---|---|---|---|---|---|---|"]
    for name, m in results.items():
        lines.append(f"| {name} | {rules_of[name]} | {P(m['cagr'])} | {P(m['cagr_gross'])} | {P(m['total'], 0)} | "
                     f"{P(m['vs_index_cagr'])} / {P(m['vs_index_total'], 0)} | {P(m['vs_universe_cagr'])} | "
                     f"{m['vol'] * 100:.1f}% | {P(m['max_dd'])} | {m['sharpe']:.2f} | {m['years_beat']}/{m['years']} | "
                     f"{m['turnover_yr'] * 100:.0f}% | {m['avg_names']:.0f} |")
    for name, m in (("NIFTY SMALLCAP 250", bench_m), ("EW universe (gross)", uni_m)):
        lines.append(f"| *{name}* | | {P(m['cagr'])} | | {P(m['total'], 0)} | | | {m['vol'] * 100:.1f}% | "
                     f"{P(m['max_dd'])} | {m['sharpe']:.2f} | | | |")
    return "\n".join(lines)


def year_table(results, bench_m, uni_m, names):
    years = sorted(bench_m["per_year"])
    lines = ["| variant | " + " | ".join(str(y) for y in years) + " |", "|---|" + "---|" * len(years)]
    for name in names:
        py = results[name]["per_year"]
        cells = []
        for y in years:
            mark = "**" if py[y] > bench_m["per_year"][y] else ""
            cells.append(f"{mark}{P(py[y])}{mark}")
        lines.append(f"| {name} | " + " | ".join(cells) + " |")
    for lab, m in (("*Smallcap 250*", bench_m), ("*EW universe*", uni_m)):
        lines.append(f"| {lab} | " + " | ".join(P(m["per_year"][y]) for y in years) + " |")
    return "\n".join(lines)


def halves_table(results, names):
    lines = ["| variant | 2019-22 CAGR | vs index | max DD | 2023-26 CAGR | vs index | max DD |",
             "|---|---|---|---|---|---|---|"]
    for n in names:
        h = results[n]["halves"]
        lines.append(f"| {n} | " + " | ".join(f"{P(h[k]['cagr'])} | {P(h[k]['vs_index'])} | {P(h[k]['max_dd'])}"
                                             for k in ("2019-22", "2023-26")) + " |")
    return "\n".join(lines)


def window_table(win, names):
    wins = [w for w, rows in win.items() if not rows.get("_skip")]
    head = [f"{w} ({win[w]['index']['from']} → {win[w]['index']['to']})" for w in wins]
    lines = ["| variant | " + " | ".join(head) + " | windows beating index | windows with smaller DD than index |",
             "|---|" + "---|" * (len(wins) + 2)]
    for n in [*names, "index", "universe"]:
        lab = {"index": "*NIFTY SMALLCAP 250*", "universe": "*EW universe*"}.get(n, n)
        cells = [f"{P(win[w][n]['ret'])} ({P(win[w][n]['max_dd'], 0)})" for w in wins]
        if n in ("index", "universe"):
            extra = ["", ""]
        else:
            beat = sum(win[w][n]["ret"] > win[w]["index"]["ret"] for w in wins)
            dd = sum(win[w][n]["max_dd"] > win[w]["index"]["max_dd"] for w in wins)
            extra = [f"{beat}/{len(wins)}", f"{dd}/{len(wins)}"]
        lines.append(f"| {lab} | " + " | ".join(cells + extra) + " |")
    skipped = [w for w, rows in win.items() if rows.get("_skip")]
    if skipped:
        lines += ["", f"Not testable (before the first rebalance): {', '.join(skipped)}."]
    return "\n".join(lines)


def live_gap(scores):
    """Live top 50 of 2025-09-30 (time-machine CSV) split by membership of the backtest universe."""
    if not TM_CSV.exists():
        return None
    tm = pd.read_csv(TM_CSV).nsmallest(50, "rank_overall")
    d = scores["signal_date"][scores["signal_date"] >= pd.Timestamp("2025-09-30")].min()
    inside = tm["company_id"].isin(scores.loc[scores["signal_date"] == d, "company_id"])
    rows = []
    for lab, m in (("inside the tested universe", inside), ("outside (thin < 0.5 cr/day or listed < 1 year)", ~inside),
                   ("all 50 (as published)", inside | ~inside)):
        t = tm[m]
        rows.append(f"| {lab} | {len(t)} | {P(t['actual_return'].mean())} | {P(t['max_drawdown'].median())} | "
                    f"{', '.join(t['symbol']) if lab.startswith('outside') else ''} |")
    return "\n".join(["| live top 50 on 2025-09-30, bought and held a year | names | avg return | median worst drawdown | names |",
                      "|---|---|---|---|---|", *rows])


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--cost", type=float, default=COST_PER_SIDE, help="cost per side as a fraction (0.003 = 0.3%%)")
    args = ap.parse_args(argv)
    warnings.filterwarnings("ignore")
    t0 = time.time()
    from growth_model.labels import LABELS_FILE

    labels = pd.read_pickle(LABELS_FILE)
    scores = load_scores(labels)
    n_per = scores.groupby("signal_date").size()
    start = n_per[n_per >= MIN_NAMES].index.min()
    scores = scores[scores["signal_date"] >= start]
    ret, bench, n_breaks = load_daily()
    print(f"scores: {len(scores):,} rows, {scores['signal_date'].nunique()} rebalance dates "
          f"{start:%Y-%m-%d} -> {scores['signal_date'].max():%Y-%m-%d}, median {int(n_per[n_per.index >= start].median())} "
          f"ranked names/date; {n_breaks} price-series breaks zeroed ({time.time() - t0:.0f}s)")

    uni = simulate(scores, ret, bench, None, universe=True)
    bench_nav = bench.reindex(uni["nav"].index)
    bench_nav = bench_nav / bench_nav.iloc[0]
    uni_nav = uni["gross"]
    flat = {"nav": bench_nav, "gross": bench_nav, "turnover": pd.Series([0.0, 0.0]), "sizes": [0]}
    bench_m = metrics(flat, bench_nav, uni_nav)
    uni_m = metrics({**uni, "nav": uni_nav}, bench_nav, uni_nav)

    runs, results, rules_of = {}, {}, {}

    def run(name, rules):
        res = simulate(scores, ret, bench, rules, cost=args.cost)
        runs[name], results[name], rules_of[name] = res, metrics(res, bench_nav, uni_nav), rules.label()
        m = results[name]
        print(f"  {name:<22}{rules.label():<70} CAGR {m['cagr']:+.1%}  vs idx {m['vs_index_cagr']:+.1%}  "
              f"DD {m['max_dd']:+.1%}  vol {m['vol']:.1%}  yrs {m['years_beat']}/{m['years']}  "
              f"turn {m['turnover_yr']:.0%}", flush=True)

    print("\nsingle rules:")
    for name, (_, rules) in SINGLES.items():
        run(name, rules)
    combo = pick_combo(results, SINGLES)
    names = list(combo.values())
    print(f"\npre-declared combination rule picked: {combo or 'nothing beats the base'}")
    combos = {}
    if names:
        for n in (50, 30):
            combos[f"combo{n}"] = merge_rules(names, n)
            run(f"combo{n}", combos[f"combo{n}"])
        best = max(combos, key=lambda k: robust_key(results[k]))
        loo = [best]
        for drop in names:
            if len(names) > 1:
                keep = [x for x in names if x != drop]
                key = f"{best}-{drop}"
                run(key, merge_rules(keep, combos[best].n))
                loo.append(key)
    else:
        best, loo = "base", []
    run("prior", PRIOR)
    run("prior30", merge_rules(["liq5", "sector20", "riskadj", "buf100"], 30))
    print("\npost-hoc (added after the first run):")
    for name, rules in POSTHOC.items():
        run(name, rules)

    cost_rows = {}
    for name in ["base", "volx5", "lowvol", "buf150", *combos, *POSTHOC]:
        rules = SINGLES[name][1] if name in SINGLES else combos.get(name) or POSTHOC[name]
        cost_rows[name] = {c: metrics(simulate(scores, ret, bench, rules, cost=c), bench_nav, uni_nav) for c in COST_GRID}

    # windows
    show = list(results)
    win = {}
    for wname, d0, d1, _ in EVENTS:
        if pd.Timestamp(d0) < start:
            win[wname] = {"_skip": True}
            continue
        rows = {n: window_stats(runs[n]["nav"], d0, d1) for n in show}
        rows["index"] = window_stats(bench_nav, d0, d1)
        rows["universe"] = window_stats(uni_nav, d0, d1)
        win[wname] = rows

    single_names = list(SINGLES)
    all_names = list(results)
    out = {"cost_per_side": args.cost, "start": str(start.date()), "end": str(bench_nav.index[-1].date()),
           "combo_families": combo, "selected": best, "rules": rules_of,
           "posthoc": list(POSTHOC), "results": results, "index": bench_m, "universe": uni_m, "windows": win,
           "cost_sensitivity": {n: {str(c): {k: m[k] for k in ("cagr", "vs_index_cagr", "years_beat")}
                                    for c, m in r.items()} for n, r in cost_rows.items()}}
    OUT_FILE.write_text(json.dumps(out, indent=1, default=str))

    md = [
        "# InvestIQ Top list: portfolio backtest of list-construction rules",
        "",
        f"Generated by `python3 -m rankings.portfolio_eval` (ml/rankings/portfolio_eval.py; selection code "
        f"ml/rankings/portfolio.py). Period {start:%Y-%m-%d} → {bench_nav.index[-1]:%Y-%m-%d}, "
        f"{scores['signal_date'].nunique()} rebalances on the 1st/16th grid, investiq-v1 scores rebuilt "
        f"point-in-time on each date (combiner_eval panels). Costs {args.cost * 100:.1f}% per side on traded value. "
        f"{n_breaks} one-day price-series breaks set to 0.",
        "",
        VERDICT,
        "",
        "## 1. All variants (net of costs unless noted)",
        "",
        "Turnover = one-way, per year (100% = the whole list replaced once). return/vol = annualised mean daily "
        "return / annualised volatility (no risk-free rate). Years = calendar years beating the Smallcap 250 "
        f"({min(bench_m['per_year'])} and {max(bench_m['per_year'])} are partial).",
        "",
        main_table(results, rules_of, bench_m, uni_m),
        "",
        f"Post-hoc rows (added after seeing the first run, so their numbers are optimistic): {', '.join(POSTHOC)}.",
        "",
        f"Pre-declared combination rule picked, per family: {combo or 'none'}. Selected (robustness key): **{best}**.",
        "",
        "## 2. Per calendar year (bold = beat the Smallcap 250)",
        "",
        year_table(results, bench_m, uni_m, all_names),
        "",
        "## 3. Halves (does a rule's gain hold in both?)",
        "",
        halves_table(results, all_names),
        "",
        "## 4. Time-machine windows (strategy run continuously; return, worst drawdown in brackets)",
        "",
        "Unlike TIME_MACHINE.md (one snapshot bought and held), the list here is what a follower held on the "
        "window's start and rebalanced every 1st/16th inside it.",
        "",
        window_table(win, show),
        "",
        "## 5. Cost sensitivity (net CAGR / vs Smallcap 250 CAGR / years beating index)",
        "",
        "| variant | " + " | ".join(f"{c * 100:.1f}% per side" for c in COST_GRID) + " |",
        "|---|" + "---|" * len(COST_GRID),
        *[f"| {n} | " + " | ".join(f"{P(r[c]['cagr'])} / {P(r[c]['vs_index_cagr'])} / {r[c]['years_beat']}/{r[c]['years']}"
                                   for c in COST_GRID) + " |" for n, r in cost_rows.items()],
        "",
        "## 6. Why the published top 50 trailed last year: names outside the tested universe",
        "",
        "The scores in this backtest (and every walk-forward IC) only cover stocks trading >= 0.5 crore a day with "
        ">= 1 year of prices. The live build ranks every listed company, so thin stocks and fresh listings can "
        "reach the top 50 without ever having been tested.",
        "",
        live_gap(scores) or "(time-machine CSV not found)",
        "",
        CAVEATS,
    ]
    REPORT.write_text("\n".join(md) + "\n")
    print(f"\nwrote {REPORT} and {OUT_FILE} in {time.time() - t0:.0f}s")


VERDICT = """## Verdict (run of 2026-10-01; numbers net of 0.3% per side)

**Recommended Top list rule set (`portfolio.RECOMMENDED`):** 50 names, equal weight, rebuilt on the
1st/16th, chosen only from the tested universe (>= 0.5 crore traded a day and >= 1 year listed), no
new buys among the 5% most volatile stocks (3-month volatility), and a holding stays while it still
ranks in the top 150 (vacancies filled from the top).

| | CAGR | vs Smallcap 250 | max DD | vol | years beating index | windows beating index / smaller DD | turnover / yr |
|---|---|---|---|---|---|---|---|
| base (top 50, full replacement) | +34.2% | +15.2 pts | -38.3% | 23.1% | 7/8 | 6/6 / 5/6 | 770% |
| **recommended** | **+35.2%** | **+16.2 pts** | **-38.1%** | **22.9%** | **7/8** | **6/6 / 5/6** | **361%** |
| "steady" alternative (lowvol) | +29.9% | +10.8 pts | -34.4% | 19.7% | 7/8 | 6/6 / 6/6 | 827% |

What was actually wrong with the published top 50 (section 6): 8 of the 50 names on 2025-09-30 were
outside the universe the score was ever tested on (5 trading < 0.5 crore a day, 3 listed < 1 year:
SIGMA, TERASOFT, GARUDA, KAVDEFENCE, VINCOFE, RAMAPHO, SEJALLTD, WAAREEENER). They averaged -21% (median
worst drawdown -48%); the other 42 averaged +8.9%, above the index's +5.9%. The second cause is
holding one snapshot for a year: the same rules rebalanced every 15 days returned +17% (base) to
+27% (recommended) over that year vs +7.6% for the index, with a -15% to -18% drawdown (index -18%). In
the 2022 sell-off the rebalanced base fell 0% (drawdown -23%) vs the index -15% (-27%), not -34%.

Rule by rule:
- **Universe floor (>= 0.5 cr/day, >= 1 year listed): adopt.** It is the backtest universe itself; the
  one live failure above comes from breaking it.
- Higher liquidity floors (2 / 5 crore): **reject.** -3 / -5.5 pts CAGR (mostly 2021), no drawdown or
  volatility gain. At a flat 0.3% cost they look worse than they would with real impact costs on thin
  names, but not enough to flip the result.
- Sector cap 20%: **reject.** The base list is concentrated (largest sector: median 13 of 50 names, more
  than 10 on 86% of dates), but capping it gave -1.4 pts CAGR, a deeper drawdown (-39.2%) and smaller
  drawdowns than the index in fewer windows (4/6): the crowded sector was usually where the trend was.
- No new buys in the top-5% volatility: **adopt.** The only single rule better than the base in both
  halves (2019-22 +1.9 pts, 2023-26 +3.5 pts vs the base), in every window, net and gross, with lower
  volatility; return/vol 1.54 vs 1.41. The gain is small (+2.8 pts CAGR) and could partly be luck, but it
  also has a long outside record (the "lottery stock" effect).
- Trend/vol score (riskadj): **reject for the main list.** Lowest volatility (16.6%) and shallowest
  drawdowns, but it lost to the index in 2023, 2024 and 2026 (5/8 years) and in 2023-26 overall.
- Low-vol pick (50 least volatile of the top 100): **offer as an optional "steady" list**, not the default:
  drawdown -34% vs -38%, volatility 19.7% vs 23.1%, smaller drawdown than the index in 6/6 windows, but
  -4 pts CAGR and worse in the 2022 window (-6.7% vs 0%).
- Turnover buffer (keep while rank <= 150): **adopt for turnover, not for return.** Turnover 770% -> 365%
  a year (each rebalance replaces ~7-8 names instead of ~16). Gross of costs it earns slightly less than
  the base (38.0% vs 40.6%: it lagged in the fast 2021 rotation and helped in 2023-25); net of 0.3% it is
  level or better, and at 0.6% per side it is clearly better (+32% vs +28%). Fewer trades also mean less
  short-term capital-gains tax for a real follower, which this test ignores.
- No "stretched" buys: **reject** (keep it as risk text). -5 pts CAGR and *more* turnover; the stretched
  names still beat the index on average.
- N = 30: **reject.** Slightly higher CAGR, but the deepest drawdown (-42%) and more turnover.

**Overfitting, said plainly.** The pre-declared combination rule (best member per family, kept if it beats
the base on years-beating-index, then max drawdown, then CAGR) picked low-vol pick + buffer 150
(`combo50`): +27.2% CAGR, -34.2% drawdown, i.e. lower return than either of its parts (the buffer keeps
names by score rank, which fights the low-vol pick). The key turned out to be nearly degenerate: 9 of 10
single rules beat the index in 7 of 8 years, and every full-period max drawdown is the March 2020 crash,
so the rule effectively ranked variants on one crash. The recommended set (volx5 + buffer 150) was
therefore chosen **after** seeing the first run and is labelled post-hoc; its numbers are optimistic.
It rests on two rules that each held up in both halves or for a cost reason, not on its CAGR rank. With
~20 variants on ~7 years of heavily overlapping, regime-driven returns, differences under ~2 pts of CAGR
are noise. Every variant (including the base) trailed the index in 2025, so none of these rules fixes
the model's weak spells; they make the list cleaner, cheaper to follow, and slightly smoother."""

CAVEATS = """## Caveats

- Survivorship: `stock_prices` only has companies listed today, so every variant (and the equal-weight
  universe) is flattered; the Smallcap 250 is not. Absolute "vs index" numbers are optimistic; differences
  between variants are fairer.
- Costs: one flat 0.3% per side. Real small-cap impact is higher for thin names (it would widen the gap
  in favour of the liquidity floor) and lower for large ones.
- Today's sector labels; balance sheets only from late 2022; news has no history (constant).
- The backtest universe is names trading >= 0.5 crore/day (the scores' universe); the live list can
  include thinner names, so the live "base" list is if anything jumpier than the base here.
- Overfitting: ~16 variants on ~7 years, with overlapping, regime-driven results. Treat 1-2 pt CAGR
  differences as noise; trust rules that help in both halves and in most windows."""


if __name__ == "__main__":
    main()
