"""Backtest of intra-rebalance exit rules on the shipped InvestIQ Top list (rankings/exits.py).

Question (docs/model-report.md 5.2 item 4): the Top list (portfolio.RECOMMENDED) has deep drawdowns
and individual blow-ups. Does selling a holding between the 1st/16th rebuilds when its own price
breaks (200-day average, trailing / fixed stop) cut them, after costs, without killing the winners?

Scores, prices, universe and Top-list rules are exactly portfolio_eval's (load_scores, load_daily,
select_top_list with portfolio.RECOMMENDED); only the daily holding loop is new.

Simulation (daily, on the Smallcap 250 calendar)
------------------------------------------------
- Rebuild on every grid date D at the first close after D (as portfolio_eval.simulate): the list is
  select_top_list(scores on D, names held at that close, RECOMMENDED); equal weight of the whole NAV
  (stocks + cash), cost 0.3% of traded value per side. A name sold by an exit rule is not "held", so
  the rank <= 150 buffer cannot keep it; it can come back only as a new entry from the top (X5: not at
  the next rebuild at all).
- Every day, after that close's returns: (1) execute yesterday's exit signals at today's close
  (proceeds - 0.3% go to cash, earning 0%), (2) rebuild if today is an entry day, (3) compute exit
  signals on today's close (exits.exit_signals; weekly MA check on the last trading day of the week),
  to be traded at the NEXT close. No same-day look-ahead.
- Signals use break-adjusted closes (cumulative product of load_daily's returns; one-day moves
  > +100% / < -60% are data breaks set to 0), so splits do not trigger stops.

Per variant
-----------
CAGR (net / gross), vs Smallcap 250, max drawdown, volatility, return/vol (annualised mean / vol),
calendar years beating the index, average cash share, rule exits per year, one-way turnover per year
(rebuild trades + exit sells, / 2), and per holding spell (a name from its buy to its sale, whether by
the rule or by a rebuild): share whose worst close while held was >= 30% below the entry close
("fell 30%+, realised") and share sold >= 30% below entry. Whipsaw: rule exits whose price closed
above the exit price within the next 21 trading days. Next-3-month return of sold names vs the index
(> 0 means the rule sold names that went on to beat the market). Per-year table, halves, time-machine
windows (portfolio_eval.window_stats on the continuously run strategy), and every headline number
with 2020 removed (daily returns of 2020 dropped and the rest chained).

Pre-declared decision rule (written before any run; constants below)
--------------------------------------------------------------------
A rule SHIPS only if all of:
  a  max drawdown at least 3 pts shallower than X0 in >= 4 of the 6 time-machine windows;
  b  over the full period, max drawdown >= 3 pts shallower than X0, OR the 30%+ crash share of
     holding spells <= 2/3 of X0's;
  c  net CAGR give-up vs X0 <= 2 pts;
  d  without 2020: max drawdown >= 2 pts shallower than X0 AND CAGR give-up <= 2 pts
     (not driven by the COVID crash alone).
X5 uses the best of X1-X4 by (criteria passed, windows with a materially smaller drawdown, net CAGR)
plus "no re-buy at the next rebuild". If nothing passes, the fallback is a UI warning badge: the
report measures, on the shipped list (X0, nothing sold), how the names a rule WOULD have flagged did
over the next 1 and 3 months vs the other holdings, i.e. whether the badge carries information.

Outputs: ml/rankings/reports/EXITS.md, ml/data/processed/exits_eval.json.

CLI:  caffeinate -i python3 -m rankings.exits_eval [--cost 0.003]
"""

import argparse
import json
import time
import warnings
from dataclasses import replace
from pathlib import Path

import numpy as np
import pandas as pd

from growth_model.prices import CACHE_DIR

from .exits import BY_NAME, CANDIDATES, NONE, RULES, exit_signals, week_ends
from .portfolio import RECOMMENDED, select_top_list
from .portfolio_eval import (COST_PER_SIDE, MIN_NAMES, P, cagr, load_daily, load_scores, max_dd,
                             metrics, window_stats)
from .time_machine import EVENTS

REPORT = Path(__file__).resolve().parent / "reports" / "EXITS.md"
OUT_FILE = CACHE_DIR / "exits_eval.json"
CRASH = -0.30                 # "fell 30%+"
WHIPSAW_DAYS = 21             # back above the exit price within ~1 month
WHIPSAW_STRICT = 0.10         # stricter reading: back 10%+ above the exit price within the month
FWD_DAYS = (21, 63)           # forward horizons for sold / flagged names
# decision rule (pre-declared)
MATERIAL_DD = 0.03
MIN_WINDOWS = 4
CRASH_CUT = 2 / 3
MAX_GIVEUP = 0.02
EX2020_DD = 0.02


# ---------------------------------------------------------
# Simulation
# ---------------------------------------------------------

def simulate_exits(scores, ret, adj, rules, exit_rule, cost=COST_PER_SIDE, shadow=()):
    """Daily Top-list simulation with an exit rule. -> dict(nav, gross, turnover, sizes, cash, spells,
    exits, shadow). `shadow`: extra ExitRules evaluated on the holdings without trading (first firing
    per holding spell is recorded, for the warning-badge analysis)."""
    cal = ret.index
    col = {c: i for i, c in enumerate(ret.columns)}
    R, A = ret.values, adj
    we = week_ends(cal)
    dates = sorted(scores["signal_date"].unique())
    by_date = dict(tuple(scores.groupby("signal_date")))
    entries = [cal.searchsorted(pd.Timestamp(d), side="right") for d in dates]
    pairs = [(d, e) for d, e in zip(dates, entries) if e < len(cal)]
    rebuild = {e: d for d, e in pairs}
    e0 = pairs[0][1]

    pos, info, cash = {}, {}, 1.0
    pending, recently_sold = {}, set()
    nav_n, nav_g, cash_share, idx = [], [], [], []
    g = 1.0
    turns, sizes, spells, exits, shadow_hits = [], [], [], [], []
    sold_frac, first = 0.0, True
    shadow_done = {r.name: set() for r in shadow}

    def close_spell(c, t, how):
        i = info.pop(c)
        j = col[c]
        path = A[i["entry_pos"]:t + 1, j]
        spells.append({"company_id": c, "entry": i["entry_pos"], "exit": t, "how": how,
                       "ret": float(path[-1] / path[0] - 1), "worst": float(path.min() / path[0] - 1)})

    for t in range(e0, len(cal)):
        if t > e0:
            before = sum(pos.values()) + cash
            for c in pos:
                pos[c] *= 1 + R[t, col[c]]
            after = sum(pos.values()) + cash
            g *= after / before
        # 1. yesterday's signals trade at today's close
        if pending:
            total = sum(pos.values()) + cash
            for c, why in pending.items():
                if c not in pos:
                    continue
                v = pos.pop(c)
                sold_frac += v / total
                cash += v * (1 - cost)
                close_spell(c, t, why)
                recently_sold.add(c)
                exits.append({"company_id": c, "t": t, "why": why, "px": float(A[t, col[c]])})
            pending = {}
        # 2. rebuild
        if t in rebuild:
            frame = by_date[rebuild[t]]
            if exit_rule.no_reentry and recently_sold:
                frame = frame[~frame["company_id"].isin(recently_sold)]
            pick = [c for c in select_top_list(frame, list(pos), rules)["company_id"].tolist() if c in col]
            total = sum(pos.values()) + cash
            new = 1 / len(pick)
            traded = sum(abs((new if c in pick else 0) - pos.get(c, 0) / total) for c in set(pick) | set(pos))
            turns.append((cal[t], 0.0 if first else (traded + sold_frac) / 2))
            sizes.append(len(pick))
            total *= 1 - cost * traded
            for c in list(pos):
                if c not in pick:
                    pos.pop(c)
                    close_spell(c, t, "rebuild")
            for c in pick:
                if c not in info:
                    info[c] = {"entry_pos": t}
            pos = {c: total / len(pick) for c in pick}
            cash, sold_frac, first = 0.0, 0.0, False
            recently_sold = set()
        # 3. signals on today's close
        if t < len(cal) - 1:
            paths = {c: A[:t + 1, col[c]] for c in pos}
            if exit_rule.active:
                pending = exit_signals(paths, list(pos), info, exit_rule, week_end=bool(we[t]))
            for r in shadow:
                for c in exit_signals(paths, [c for c in pos if (c, info[c]["entry_pos"]) not in shadow_done[r.name]],
                                      info, r, week_end=bool(we[t])):
                    shadow_done[r.name].add((c, info[c]["entry_pos"]))
                    others = [o for o in pos if o != c]
                    shadow_hits.append({"rule": r.name, "company_id": c, "t": t, "others": others})
        total = sum(pos.values()) + cash
        nav_n.append(total)
        nav_g.append(g)
        cash_share.append(cash / total)
        idx.append(cal[t])
    for c in list(info):
        close_spell(c, len(cal) - 1, "end")
    idx = pd.DatetimeIndex(idx)
    return dict(nav=pd.Series(nav_n, index=idx), gross=pd.Series(nav_g, index=idx),
                turnover=pd.Series(dict(turns)), sizes=sizes, cash=pd.Series(cash_share, index=idx),
                spells=pd.DataFrame(spells), exits=pd.DataFrame(exits), shadow=shadow_hits)


# ---------------------------------------------------------
# Metrics
# ---------------------------------------------------------

def fwd(A, j, t, h):
    return float(A[t + h, j] / A[t, j] - 1) if t + h < len(A) else np.nan


def exit_stats(res, adj, bench_arr, col_of, years):
    ex = res["exits"]
    if ex.empty:
        return {"n_exits": 0, "exits_yr": 0.0, "whipsaw": np.nan, "whipsaw10": np.nan, "fwd21_vs_idx": np.nan, "fwd63_vs_idx": np.nan,
                "sold_up30_3m": np.nan, "reasons": {}}
    whip, whip10, f21, f63, up30 = [], [], [], [], []
    for r in ex.itertuples():
        j = col_of[r.company_id]
        nxt = adj[r.t + 1:r.t + 1 + WHIPSAW_DAYS, j]
        whip.append(bool(len(nxt) and (nxt > r.px).any()))
        whip10.append(bool(len(nxt) and (nxt >= r.px * (1 + WHIPSAW_STRICT)).any()))
        b21 = bench_arr[r.t + 21] / bench_arr[r.t] - 1 if r.t + 21 < len(bench_arr) else np.nan
        b63 = bench_arr[r.t + 63] / bench_arr[r.t] - 1 if r.t + 63 < len(bench_arr) else np.nan
        s63 = fwd(adj, j, r.t, 63)
        f21.append(fwd(adj, j, r.t, 21) - b21)
        f63.append(s63 - b63)
        up30.append(s63 >= 0.30 if not np.isnan(s63) else np.nan)
    return {"n_exits": len(ex), "exits_yr": len(ex) / years, "whipsaw": float(np.mean(whip)),
            "whipsaw10": float(np.mean(whip10)),
            "fwd21_vs_idx": float(np.nanmean(f21)), "fwd63_vs_idx": float(np.nanmean(f63)),
            "sold_up30_3m": float(np.nanmean(up30)), "reasons": ex["why"].value_counts().to_dict()}


def spell_stats(res, years, mask_entry=None):
    sp = res["spells"]
    if mask_entry is not None:
        sp = sp[mask_entry(sp)]
    return {"spells": len(sp), "spells_yr": len(sp) / years,
            "crash_share": float((sp["worst"] <= CRASH).mean()), "crash_yr": float((sp["worst"] <= CRASH).sum() / years),
            "sold_down30_share": float((sp["ret"] <= CRASH).mean()),
            "big_winner_share": float((sp["ret"] >= 1.0).mean())}


def ex2020(nav):
    """CAGR and max drawdown with every 2020 daily return dropped and the rest chained."""
    r = nav.pct_change().dropna()
    r = r[r.index.year != 2020]
    spliced = (1 + r).cumprod()
    days = (nav.index[-1] - nav.index[0]).days - (pd.Timestamp("2021-01-01") - pd.Timestamp("2020-01-01")).days
    return {"cagr": float(spliced.iloc[-1] ** (365.25 / days) - 1), "max_dd": max_dd(spliced)}


def shadow_badge(hits, adj, col_of, bench_arr):
    """Flagged-but-held names (X0) vs the other holdings on the flag date: forward returns."""
    rows = []
    for h in hits:
        j = col_of[h["company_id"]]
        t = h["t"]
        for hz in FWD_DAYS:
            if t + hz >= len(adj):
                continue
            mine = fwd(adj, j, t, hz)
            oth = np.nanmean([fwd(adj, col_of[o], t, hz) for o in h["others"]]) if h["others"] else np.nan
            rows.append({"rule": h["rule"], "h": hz, "flag": mine, "others": oth,
                         "crash": float(adj[t + 1:t + hz + 1, j].min() / adj[t, j] - 1) <= -0.20})
    df = pd.DataFrame(rows)
    out = {}
    for (rule, hz), g in df.groupby(["rule", "h"]):
        out[f"{rule}_{hz}"] = {"n": len(g), "flag": float(g["flag"].mean()), "others": float(g["others"].mean()),
                               "flag_median": float(g["flag"].median()), "gap": float((g["flag"] - g["others"]).mean()),
                               "share_worse": float((g["flag"] < g["others"]).mean()),
                               "fall20": float(g["crash"].mean())}
    return out


def verdict_checks(m, base, win, name, base_name="X0"):
    w_ok = sum((win[w][name]["max_dd"] - win[w][base_name]["max_dd"]) >= MATERIAL_DD for w in win)
    a = w_ok >= MIN_WINDOWS
    b = (m["max_dd"] - base["max_dd"] >= MATERIAL_DD) or (m["crash_share"] <= CRASH_CUT * base["crash_share"])
    c = base["cagr"] - m["cagr"] <= MAX_GIVEUP
    d = (m["ex2020"]["max_dd"] - base["ex2020"]["max_dd"] >= EX2020_DD) and \
        (base["ex2020"]["cagr"] - m["ex2020"]["cagr"] <= MAX_GIVEUP)
    return {"windows_dd_cut": w_ok, "a": a, "b": b, "c": c, "d": d, "passed": sum([a, b, c, d]),
            "ships": a and b and c and d}


def pick_best(results, checks):
    return max(CANDIDATES, key=lambda n: (checks[n]["passed"], checks[n]["windows_dd_cut"], results[n]["cagr"]))


# ---------------------------------------------------------
# Report
# ---------------------------------------------------------

def pts(x):
    return "—" if x is None or pd.isna(x) else f"{x * 100:+.1f}"


def main_table(names, results, rule_text, bench_m):
    lines = ["| variant | rule | CAGR net | CAGR gross | vs Smallcap 250 | max DD | vol | return/vol | years beating index "
             "| avg cash | rule exits / yr | turnover / yr | spells fell 30%+ (worst while held) | sold 30%+ below entry "
             "| whipsaw (back above exit px ≤ 1m) | sold names next 3m vs index |",
             "|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|"]
    for n in names:
        m = results[n]
        lines.append(f"| {n} | {rule_text[n]} | {P(m['cagr'])} | {P(m['cagr_gross'])} | {P(m['vs_index_cagr'])} | "
                     f"{P(m['max_dd'])} | {m['vol'] * 100:.1f}% | {m['sharpe']:.2f} | {m['years_beat']}/{m['years']} | "
                     f"{m['avg_cash'] * 100:.1f}% | {m['exits_yr']:.0f} | {m['turnover_yr'] * 100:.0f}% | "
                     f"{m['crash_share'] * 100:.1f}% ({m['crash_yr']:.1f}/yr) | {m['sold_down30_share'] * 100:.1f}% | "
                     f"{'—' if pd.isna(m['whipsaw']) else f'{m['whipsaw'] * 100:.0f}%'} | {P(m['fwd63_vs_idx'])} |")
    lines.append(f"| *NIFTY SMALLCAP 250* | | {P(bench_m['cagr'])} | | | {P(bench_m['max_dd'])} | {bench_m['vol'] * 100:.1f}% | "
                 f"{bench_m['sharpe']:.2f} | | | | | | | | |")
    return "\n".join(lines)


def year_table(names, results, bench_m):
    years = sorted(bench_m["per_year"])
    lines = ["| variant | " + " | ".join(str(y) for y in years) + " |", "|---|" + "---|" * len(years)]
    for n in names:
        py = results[n]["per_year"]
        cells = [(f"**{P(py[y])}**" if py[y] > bench_m["per_year"][y] else P(py[y])) for y in years]
        lines.append(f"| {n} | " + " | ".join(cells) + " |")
    lines.append("| *Smallcap 250* | " + " | ".join(P(bench_m["per_year"][y]) for y in years) + " |")
    return "\n".join(lines)


def window_table(names, win):
    wins = list(win)
    head = [f"{w} ({win[w]['index']['from']} → {win[w]['index']['to']})" for w in wins]
    lines = ["| variant | " + " | ".join(head) + " | windows with DD ≥3 pts shallower than X0 | windows return ≥ X0 |",
             "|---|" + "---|" * (len(wins) + 2)]
    for n in [*names, "index"]:
        lab = "*NIFTY SMALLCAP 250*" if n == "index" else n
        cells = [f"{P(win[w][n]['ret'])} ({P(win[w][n]['max_dd'], 0)})" for w in wins]
        if n == "index":
            extra = ["", ""]
        else:
            dd = sum(win[w][n]["max_dd"] - win[w]["X0"]["max_dd"] >= MATERIAL_DD for w in wins)
            rr = sum(win[w][n]["ret"] >= win[w]["X0"]["ret"] - 1e-9 for w in wins)
            extra = [f"{dd}/{len(wins)}", f"{rr}/{len(wins)}"]
        lines.append(f"| {lab} | " + " | ".join(cells + extra) + " |")
    return "\n".join(lines)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--cost", type=float, default=COST_PER_SIDE, help="cost per side as a fraction (0.003 = 0.3%%)")
    args = ap.parse_args(argv)
    warnings.filterwarnings("ignore")
    t0 = time.time()
    from growth_model.labels import LABELS_FILE

    scores = load_scores(pd.read_pickle(LABELS_FILE))
    n_per = scores.groupby("signal_date").size()
    start = n_per[n_per >= MIN_NAMES].index.min()
    scores = scores[scores["signal_date"] >= start]
    ret, bench, n_breaks = load_daily()
    adj = (1 + ret).cumprod().values
    col_of = {c: i for i, c in enumerate(ret.columns)}
    bench_arr = bench.values
    print(f"scores: {len(scores):,} rows, {scores['signal_date'].nunique()} rebuilds from {start:%Y-%m-%d}; "
          f"{n_breaks} breaks zeroed ({time.time() - t0:.0f}s)")

    runs, results, rule_text = {}, {}, {}
    bench_nav = None

    def run(rule, shadow=()):
        nonlocal bench_nav
        res = simulate_exits(scores, ret, adj, RECOMMENDED, rule, cost=args.cost, shadow=shadow)
        nav = res["nav"]
        if bench_nav is None:
            b = bench.reindex(nav.index)
            bench_nav = b / b.iloc[0]
        yrs = (nav.index[-1] - nav.index[0]).days / 365.25
        m = metrics(res, bench_nav, bench_nav)
        m.update(spell_stats(res, yrs))
        m.update(exit_stats(res, adj, bench_arr, col_of, yrs))
        m["avg_cash"] = float(res["cash"].mean())
        m["max_cash"] = float(res["cash"].max())
        m["ex2020"] = ex2020(nav)
        runs[rule.name], results[rule.name], rule_text[rule.name] = res, m, rule.text
        print(f"  {rule.name:<5}{rule.text:<52} CAGR {m['cagr']:+.1%}  DD {m['max_dd']:+.1%}  vol {m['vol']:.1%}  "
              f"cash {m['avg_cash']:.1%}  exits/yr {m['exits_yr']:.0f}  turn {m['turnover_yr']:.0%}  "
              f"crash {m['crash_share']:.1%}  whip {m['whipsaw'] if pd.isna(m['whipsaw']) else round(m['whipsaw'], 2)}  "
              f"ex2020 {m['ex2020']['cagr']:+.1%}/{m['ex2020']['max_dd']:+.1%}  ({time.time() - t0:.0f}s)", flush=True)

    shadow = [BY_NAME["X1"], BY_NAME["X2"], BY_NAME["X3"]]
    for rule in RULES:
        run(rule, shadow=shadow if rule is NONE else ())

    def windows():
        win = {}
        for wname, d0, d1, _ in EVENTS:
            if pd.Timestamp(d0) < start:
                continue
            rows = {n: window_stats(runs[n]["nav"], d0, d1) for n in runs}
            rows["index"] = window_stats(bench_nav, d0, d1)
            win[wname] = rows
        return win

    bench_m = metrics({"nav": bench_nav, "gross": bench_nav, "turnover": pd.Series([0.0, 0.0]), "sizes": [0]},
                      bench_nav, bench_nav)
    bench_m["ex2020"] = ex2020(bench_nav)
    win = windows()
    checks = {n: verdict_checks(results[n], results["X0"], win, n) for n in results if n != "X0"}
    best = pick_best(results, checks)
    x5 = replace(BY_NAME[best], name="X5", text=f"{best} + no re-buy at the next rebuild", no_reentry=True)
    print(f"\nbest of X1-X4 (pre-declared key): {best}")
    run(x5)
    win = windows()
    checks = {n: verdict_checks(results[n], results["X0"], win, n) for n in results if n != "X0"}
    badge = shadow_badge(runs["X0"]["shadow"], adj, col_of, bench_arr)

    # crash share by entry year, with / without 2020 entries
    by_year = {}
    for n, res in runs.items():
        sp = res["spells"].copy()
        sp["year"] = ret.index[sp["entry"].values].year
        by_year[n] = {int(y): float((g["worst"] <= CRASH).mean()) for y, g in sp.groupby("year")}
        sp_ex = sp[sp["year"] != 2020]
        results[n]["crash_share_ex2020"] = float((sp_ex["worst"] <= CRASH).mean())
    names = list(results)
    out = {"cost_per_side": args.cost, "start": str(start.date()), "end": str(bench_nav.index[-1].date()),
           "best_of_x1_x4": best, "rules": rule_text,
           "results": {n: {k: v for k, v in m.items()} for n, m in results.items()},
           "index": bench_m, "windows": win, "checks": checks, "crash_share_by_entry_year": by_year, "badge": badge}
    OUT_FILE.write_text(json.dumps(out, indent=1, default=str))

    # ----- report
    years = sorted(bench_m["per_year"])
    check_rows = ["| variant | windows with DD ≥3 pts shallower (need ≥4/6) | a | b (full DD ≥3 pts or crash share ≤2/3) "
                  "| c (CAGR give-up ≤2 pts) | d (ex-2020: DD ≥2 pts, give-up ≤2 pts) | ships |",
                  "|---|---|---|---|---|---|---|"]
    yn = lambda x: "yes" if x else "no"      # noqa: E731
    for n, c in checks.items():
        check_rows.append(f"| {n} | {c['windows_dd_cut']}/{len(win)} | {yn(c['a'])} | {yn(c['b'])} | {yn(c['c'])} | "
                          f"{yn(c['d'])} | **{yn(c['ships'])}** |")
    ex_rows = ["| variant | CAGR (all) | max DD (all) | CAGR ex-2020 | max DD ex-2020 | Δ CAGR vs X0 ex-2020 | "
               "Δ max DD vs X0 ex-2020 | crash share (all) | crash share ex-2020 entries |",
               "|---|---|---|---|---|---|---|---|---|"]
    for n in names:
        m, b = results[n], results["X0"]
        ex_rows.append(f"| {n} | {P(m['cagr'])} | {P(m['max_dd'])} | {P(m['ex2020']['cagr'])} | {P(m['ex2020']['max_dd'])} | "
                       f"{pts(m['ex2020']['cagr'] - b['ex2020']['cagr'])} | {pts(m['ex2020']['max_dd'] - b['ex2020']['max_dd'])} | "
                       f"{m['crash_share'] * 100:.1f}% | {m['crash_share_ex2020'] * 100:.1f}% |")
    ex_rows.append(f"| *Smallcap 250* | {P(bench_m['cagr'])} | {P(bench_m['max_dd'])} | {P(bench_m['ex2020']['cagr'])} | "
                   f"{P(bench_m['ex2020']['max_dd'])} | | | | |")
    halves = ["| variant | 2019-22 CAGR | max DD | 2023-26 CAGR | max DD |", "|---|---|---|---|---|"]
    for n in names:
        h = results[n]["halves"]
        halves.append(f"| {n} | {P(h['2019-22']['cagr'])} | {P(h['2019-22']['max_dd'])} | {P(h['2023-26']['cagr'])} | "
                      f"{P(h['2023-26']['max_dd'])} |")
    crash_years = sorted({y for d in by_year.values() for y in d})
    crash_tab = ["| variant | " + " | ".join(str(y) for y in crash_years) + " |", "|---|" + "---|" * len(crash_years)]
    for n in names:
        crash_tab.append(f"| {n} | " + " | ".join(f"{by_year[n].get(y, np.nan) * 100:.0f}%" for y in crash_years) + " |")
    exit_rows = ["| variant | rule exits | by reason | whipsaw | whipsaw 10%+ | sold names next 1m vs index | next 3m vs index | "
                 "sold names up 30%+ in next 3m | spells | big winners (spell +100%) |",
                 "|---|---|---|---|---|---|---|---|---|---|"]
    for n in names:
        m = results[n]
        exit_rows.append(f"| {n} | {m['n_exits']} | {', '.join(f'{k} {v}' for k, v in m['reasons'].items()) or '—'} | "
                         f"{'—' if pd.isna(m['whipsaw']) else f'{m['whipsaw'] * 100:.0f}%'} | "
                         f"{'—' if pd.isna(m['whipsaw10']) else f'{m['whipsaw10'] * 100:.0f}%'} | {P(m['fwd21_vs_idx'])} | "
                         f"{P(m['fwd63_vs_idx'])} | {'—' if pd.isna(m['sold_up30_3m']) else f'{m['sold_up30_3m'] * 100:.0f}%'} | "
                         f"{m['spells']} | {m['big_winner_share'] * 100:.1f}% |")
    badge_rows = ["| flag (shadow rule on the shipped list, first firing per holding) | flags | horizon | flagged names avg "
                  "| flagged median | other holdings avg | avg gap | flagged worse than others | flagged name fell 20%+ inside horizon |",
                  "|---|---|---|---|---|---|---|---|---|"]
    for k, v in badge.items():
        rule, hz = k.split("_")
        badge_rows.append(f"| {rule}: {BY_NAME[rule].text} | {v['n']} | {hz} days | {P(v['flag'])} | {P(v['flag_median'])} | "
                          f"{P(v['others'])} | {pts(v['gap'])} pts | {v['share_worse'] * 100:.0f}% | {v['fall20'] * 100:.0f}% |")

    md = [
        "# InvestIQ Top list: intra-rebalance exit rules",
        "",
        f"Generated by `python3 -m rankings.exits_eval` (ml/rankings/exits_eval.py; rules ml/rankings/exits.py; list "
        f"rules portfolio.RECOMMENDED). Period {start:%Y-%m-%d} → {bench_nav.index[-1]:%Y-%m-%d}, "
        f"{scores['signal_date'].nunique()} rebuilds on the 1st/16th, investiq-v1 scores point-in-time (portfolio_eval."
        f"load_scores). Costs {args.cost * 100:.1f}% per side on every rebuild trade, exit and re-entry. Exit signals on a "
        f"close are traded at the next close; proceeds earn 0% until the next rebuild. {n_breaks} one-day price breaks set to 0.",
        "",
        VERDICT,
        "",
        "## 1. All variants (net of costs unless noted)",
        "",
        "Rule exits = sales by the exit rule (not rebuild drops). Turnover = one-way per year incl. exit sales. "
        "Spell = one holding from buy to sale (by the rule or a rebuild); \"fell 30%+\" = its worst close while held "
        ">= 30% below the entry close. Whipsaw = rule exits whose price closed above the exit price within "
        f"{WHIPSAW_DAYS} trading days. X5 = best of X1-X4 by the pre-declared key (**{best}**) + no re-buy at the next rebuild.",
        "",
        main_table(names, results, rule_text, bench_m),
        "",
        "## 2. Decision rule (pre-declared in exits_eval.py)",
        "",
        "\n".join(check_rows),
        "",
        "## 3. Per calendar year (bold = beat the Smallcap 250)",
        "",
        year_table(names, results, bench_m),
        "",
        "Halves:",
        "",
        "\n".join(halves),
        "",
        "## 4. Time-machine windows (continuously run strategy; return, worst drawdown in brackets)",
        "",
        window_table(names, win),
        "",
        "Not testable (before the first rebuild): 2018 small-cap crash.",
        "",
        "## 5. With and without 2020",
        "",
        "Ex-2020 = every 2020 daily return dropped and the rest chained (CAGR over the remaining time). Crash share "
        "ex-2020 = holding spells that started outside 2020.",
        "",
        "\n".join(ex_rows),
        "",
        "Share of holding spells that fell 30%+ while held, by year of entry:",
        "",
        "\n".join(crash_tab),
        "",
        "## 6. What the exits sold",
        "",
        f"Whipsaw 10%+ = the price closed {WHIPSAW_STRICT:.0%}+ above the exit price within {WHIPSAW_DAYS} trading days. "
        "Next 1m / 3m vs index = the sold stock's return after the exit minus the Smallcap 250's (> 0: the rule sold "
        "names that went on to beat the market).",
        "",
        "\n".join(exit_rows),
        "",
        "## 7. Warning badge instead of selling (shipped list, nothing sold)",
        "",
        "The same triggers evaluated on the X0 holdings without trading (first firing per holding spell). If flagged "
        "names do clearly worse than the other holdings afterwards, a badge carries information even when selling "
        "does not pay.",
        "",
        "\n".join(badge_rows),
        "",
        CAVEATS,
    ]
    REPORT.write_text("\n".join(md) + "\n")
    print(f"\nwrote {REPORT} and {OUT_FILE} in {time.time() - t0:.0f}s")


VERDICT = """## Verdict (run of 2026-10-02; numbers net of 0.3% per side): no exit rule ships; at most a UI badge

**No rule passes the pre-declared test (section 2).** Every rule fails criterion (a) (a materially smaller
drawdown in >= 4 of 6 windows: best is 2/6, and those two are the same COVID crash) and criterion (d)
(without 2020 the max drawdown improves by at most 1.6 pts). The full-period drawdown cut is real but is
one episode: in the March 2020 crash the rules moved up to 53-67% of the list to cash (peak cash share).

| | CAGR | vs X0 | max DD | max DD ex-2020 | windows DD ≥3 pts better | spells fell 30%+ | rule exits/yr | turnover/yr | whipsaw (10%+) |
|---|---|---|---|---|---|---|---|---|---|
| X0 shipped Top list | +35.2% | — | -38.1% | -26.4% | — | 4.3% | 0 | 361% | — |
| X1 200-day avg, weekly | +34.2% | -1.0 | -35.3% | -26.6% | 0/6 | 2.5% | 31 | 389% | 92% (52%) |
| X1d 200-day avg, daily | +34.6% | -0.6 | -31.6% | -25.1% | 2/6 | 1.3% | 40 | 400% | 89% (48%) |
| X2 trailing -20% | +32.3% | -2.9 | -31.4% | -24.8% | 2/6 | 0.4% | 89 | 443% | 89% (48%) |
| X2b trailing -25% | +35.0% | -0.2 | -32.6% | -25.7% | 2/6 | 0.9% | 45 | 391% | 88% (48%) |
| X3 fixed -15% | +33.2% | -2.0 | -32.8% | -25.5% | 2/6 | 0.4% | 47 | 399% | 88% (53%) |
| X4 X1 or X2 | +31.1% | -4.1 | -31.6% | -25.1% | 2/6 | 0.5% | 103 | 463% | 90% (48%) |
| X5 X2b + no re-buy | +34.8% | -0.4 | -32.2% | -24.8% | 2/6 | 1.0% | 45 | 392% | 88% (48%) |

Rule by rule:
- **The problem is smaller on the rebuilt list than the "1 in 5" suggests.** That figure is for stretched
  names bought and held a year. On the Top list as followed (rebuilt every 15 days, dropped once a name
  ranks below 150), only 4.3% of holding spells ever fell 30%+ below their entry while held (6.8 a year,
  mostly 2019-20 entries); the rebuild is already an exit rule. The stops push this to ~0.5-1%, but by
  selling 30-100 names a year, most of which then recovered.
- **Exits do not sell future losers.** Names sold by every rule went on to match or beat the Smallcap 250
  over the next 1 and 3 months (+0.1 to +4.6 pts); 88-92% closed above the exit price within a month
  (about half rose 10%+ above it). The fixed -15% stop (X3) is worst: its sold names beat the index by
  4.6 pts over 3 months (selling normal small-cap noise near entry).
- **Drawdown:** X1d/X2/X2b/X3/X4/X5 cut the COVID drawdown (-38% -> -31% to -33%), nothing else. In the
  2022 sell-off every rule had a slightly *deeper* drawdown than X0 (-24% vs -23%) and a worse return; in
  the 2024-25 correction at most 1 pt better; last year 0-1 pt. Ex-2020 the max drawdown moves from -26.4%
  to between -24.8% and -26.6%.
- **Return:** X2b (+35.0%) and X1d (+34.6%) are within noise of X0; X2 (-2.9 pts), X3 (-2.0) and X4
  (-4.1) cost real return (more cash drag and re-buying the same names), and every rule loses 1.1-5.1 pts
  of CAGR ex-2020. The weekly 200-day rule (X1, picked before the run to cut whipsaw) was the worst at
  drawdown: by the week's close the break is often already deep.
- **X5 (best rule X2b + no re-buy at the next rebuild):** same picture (-0.4 pts CAGR, -32.2% DD, 2/6
  windows); blocking re-entry neither helps nor hurts materially.

**Recommendation: keep the Top list as shipped (no selling between rebuilds).** If anything is surfaced,
make it an information-only badge on a holding, not a sell signal: the -20% trailing flag (X2 trigger on
the shipped list, section 7) is the only one with any signal (flagged names trailed the other holdings by
1.8 pts over 3 months and 27% fell another 20%+, vs no gap for the 200-day and fixed-stop flags), and
that edge is small. Re-test after the next real crash; 2020 is the only episode where exits helped."""

CAVEATS = """## Caveats

- Survivorship: `stock_prices` only has companies listed today, so delisted blow-ups (where a stop would
  help most) are missing; every variant is flattered, the exit rules possibly less than X0.
- Costs: flat 0.3% per side; a stop in a falling small cap often fills worse than the close (gaps, lower
  circuits), so stop results here are if anything optimistic. Cash earns 0% (a liquid fund would add ~6%/yr
  on the cash share).
- One crash (2020), one sell-off (2022), one correction (2024-25): few independent episodes. Rules were
  declared before the run; X5's base rule was picked by a pre-declared key.
- Tax ignored: every exit realises a short-term gain or loss for a real follower."""


if __name__ == "__main__":
    main()
