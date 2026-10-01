"""Backtest of the "Early Movers" list (rankings/early_movers.py) against the shipped Top list.

Question (docs/model-report.md 5.1 item 3): does a list of base breakouts (near the 52-week high but not
yet stretched), optionally with growth/quality fundamentals, give a *different risk profile* (fewer
blow-ups, shallower drawdowns) or *diversification* versus the Top list, robustly across years? It is
worth a second tab even with a lower CAGR if its drawdown and crash rate are clearly better; it is not
worth one if it is just a worse Top list. The definitions and the ship/no-ship rule are fixed in
early_movers.py (DEFINITIONS, passes, choose) before this script was first run.

Data (point-in-time, same rows as rankings/portfolio_eval.py)
------------------------------------------------------------
investiq-v1 scores on the 1st/16th label grid: portfolio_eval.load_scores (combiner_eval panels; liquid
universe >= 0.5 cr/day, >= 252 trading days; only rows the live ranking could rank). Added per row:
    dist_52w_high              growth_market_features.pkl (prices up to D)
    revenue_yoy, net_profit_yoy, net_profit_ttm, revenue_yoy_accel, op_margin_change_yoy,
    cash_conversion            financial_model.data.build_panel (filing_date <= D 00:00, period ended
                               <= 275 days before D; NaN for banks / NBFCs / insurers). Cash-flow
                               figures (cash_conversion) only exist from mid-2021.
    ret_12m, excess_12m        growth_labels.pkl, only to score picks *after* the fact (crash rate,
                               median outcome); never an input to selection.

Simulation: the portfolio_eval simulator, generalised to any selection function and to lists that are
shorter than N or empty (cash, 0% return). Rebalance on every grid date from the first date with >= 250
ranked names (2019-07), buy at the first close after D, equal weight, weights drift until the next entry
day, 0.3% cost per side on traded value, one-day moves > +100% / < -60% zeroed (data breaks), price
returns, no dividends or tax. `check_simulator` re-runs the Top list with this code and asserts it equals
portfolio_eval.simulate.

Compared lists: Top list (portfolio.RECOMMENDED), plain top 50 (full replacement), NIFTY SMALLCAP 250,
equal-weight universe (every ranked name, no costs), and a 50/50 mix of each Early Movers definition
with the Top list (rebalanced to 50/50 on every entry day; the cost of that re-balancing between the
two halves is ignored, it is small next to each list's own turnover). Reference only, not a candidate:
portfolio_eval's rejected "lowvol" Top-list variant, to tell the breakout pattern apart from simply
holding calmer stocks. Cost sensitivity at 0 / 0.3 / 0.6% per side.

Pick-level outcomes: a "pick" is a new entry (a name bought on D that was not held before D). Crash =
its 12-month return (labels: entry day -> 252 trading days later) <= -30%; also reported, a drawdown
of >= 30% from the entry close at any point in those 252 days (from the daily closes). Median pick
outcome = median 12-month return minus the Smallcap 250 over the same days. Picks from the last year
have no 12-month outcome yet and are left out. The baseline is every ranked name on every date.

Decision: early_movers.passes on each definition's own test period (from its first date with any
name), against the Top list on the same dates; early_movers.choose picks among those that pass.

Outputs: ml/rankings/reports/EARLY_MOVERS.md, ml/data/processed/early_movers_eval.json.

CLI:  caffeinate -i python3 -m rankings.early_movers_eval [--cost 0.003]
"""

import argparse
import json
import time
import warnings
from pathlib import Path

import numpy as np
import pandas as pd

from growth_model.market_model import FEATURES_FILE
from growth_model.prices import CACHE_DIR

from . import early_movers as em
from . import portfolio_eval as pe
from .portfolio import RECOMMENDED as TOP_RULES, Rules, select_top_list
from .time_machine import EVENTS

COST_PER_SIDE = pe.COST_PER_SIDE
CRASH = -0.30
FUND_ERA = pd.Timestamp("2021-07-01")       # cash-flow data (cash_conversion) exists from here
FUND_COLS = ["revenue_yoy", "net_profit_yoy", "net_profit_ttm", "revenue_yoy_accel", "op_margin_change_yoy",
             "cash_conversion"]
LOWVOL_REF = "ref: Top list low-vol pick"
COST_GRID = [0.0, 0.003, 0.006]
REPORT = Path(__file__).resolve().parent / "reports" / "EARLY_MOVERS.md"
OUT_FILE = CACHE_DIR / "early_movers_eval.json"
P = pe.P


# ---------------------------------------------------------
# Data
# ---------------------------------------------------------

def load_inputs(labels):
    from financial_model.data import build_panel

    s = pe.load_scores(labels)
    mk = pd.read_pickle(FEATURES_FILE)[["company_id", "signal_date", "dist_52w_high"]]
    s = s.merge(mk, on=["company_id", "signal_date"], how="left")
    panel, _ = build_panel(labels=labels)
    s = s.merge(panel[["company_id", "signal_date", *FUND_COLS]], on=["company_id", "signal_date"], how="left")
    s = s.merge(labels[["company_id", "signal_date", "ret_12m", "excess_12m"]], on=["company_id", "signal_date"],
                how="left")
    return s


# ---------------------------------------------------------
# Simulation (portfolio_eval.simulate, any selector, short / empty lists allowed)
# ---------------------------------------------------------

def simulate(scores, ret, select, cost=COST_PER_SIDE):
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
    turns, sizes, hist, entry_days = [], [], {}, []
    for k, (d, e) in enumerate(pairs):
        pick = [c for c in select(by_date[d], held) if c in col]
        hist[pd.Timestamp(d)] = pick
        entry_days.append(cal[e])
        new_w = pd.Series(1 / len(pick), index=pick) if pick else pd.Series(dtype=float)
        old_w = pd.Series(w_drift, index=held, dtype=float)
        traded = new_w.sub(old_w, fill_value=0).abs().sum()
        turns.append((pd.Timestamp(d), traded / 2 if k > 0 else 0.0))
        sizes.append(len(pick))
        nav_n[-1] *= (1 - cost * traded)
        e_next = pairs[k + 1][1] if k + 1 < len(pairs) else len(cal) - 1
        if e_next <= e:
            break
        n_days = e_next - e
        if pick:
            growth = np.cumprod(1 + R[e + 1:e_next + 1][:, [col[x] for x in pick]], axis=0)
            path = growth.mean(axis=1)
            w_drift = growth[-1] / growth[-1].sum()
        else:
            path, w_drift = np.ones(n_days), np.array([])
        daily = path / np.concatenate([[1.0], path[:-1]]) - 1
        for r in daily:
            nav_g.append(nav_g[-1] * (1 + r))
            nav_n.append(nav_n[-1] * (1 + r))
        idx.extend(cal[e + 1:e_next + 1])
        held = pick
    return dict(nav=pd.Series(nav_n, index=idx), gross=pd.Series(nav_g, index=idx),
                turnover=pd.Series(dict(turns)), sizes=pd.Series(sizes, index=list(hist)), holdings=hist,
                entry_days=entry_days)


def top_selector(rules):
    return lambda frame, held: select_top_list(frame, held, rules)["company_id"].tolist()


def em_selector(rules):
    return lambda frame, held: em.select_early_movers(frame, held, rules)["company_id"].tolist()


def check_simulator(scores, ret, bench):
    """This simulate() must reproduce portfolio_eval.simulate on the Top list exactly."""
    a = simulate(scores, ret, top_selector(TOP_RULES))["nav"]
    b = pe.simulate(scores, ret, bench, TOP_RULES)["nav"]
    assert len(a) == len(b) and np.allclose(a.values, b.values), "simulator differs from portfolio_eval"
    return float(a.iloc[-1])


def mix(nav_a, nav_b, entry_days):
    """50/50 of two NAVs on the same calendar, re-balanced to 50/50 on every entry day."""
    a, b = nav_a.values, nav_b.values
    pos = set(nav_a.index.get_indexer(pd.DatetimeIndex(entry_days)))
    out, base, ra, rb = np.empty(len(a)), 1.0, a[0], b[0]
    for t in range(len(a)):
        out[t] = base * (0.5 * a[t] / ra + 0.5 * b[t] / rb)
        if t in pos:
            base, ra, rb = out[t], a[t], b[t]
    return pd.Series(out, index=nav_a.index)


# ---------------------------------------------------------
# Metrics
# ---------------------------------------------------------

def yearly_dd(nav):
    return pd.Series({y: pe.max_dd(g / g.iloc[0]) for y, g in nav.groupby(nav.index.year)})


def nav_stats(nav, bench_nav, turnover=None, sizes=None):
    """Return metrics of a NAV slice (rebased) vs the index slice on the same days."""
    nav, b = nav / nav.iloc[0], bench_nav.reindex(nav.index) / bench_nav.reindex(nav.index).iloc[0]
    r = nav.pct_change().dropna()
    vol = float(r.std() * np.sqrt(252))
    yr, yb = pe.yearly_returns(nav), pe.yearly_returns(b)
    out = {"cagr": pe.cagr(nav), "vs_index_cagr": pe.cagr(nav) - pe.cagr(b), "max_dd": pe.max_dd(nav), "vol": vol,
           "sharpe": float(r.mean() * 252 / vol) if vol else np.nan, "years_beat": int((yr > yb).sum()),
           "years": len(yr), "per_year": yr.to_dict(), "per_year_dd": yearly_dd(nav).to_dict(),
           "span_years": pe.years_of(nav), "from": str(nav.index[0].date()), "to": str(nav.index[-1].date())}
    if turnover is not None:
        t = turnover[turnover.index >= nav.index[0] - pd.Timedelta(days=7)].iloc[1:]
        out["turnover_yr"] = float(t.sum() / pe.years_of(nav))
    if sizes is not None:
        sz = sizes[sizes.index >= nav.index[0] - pd.Timedelta(days=7)]
        out.update(names_median=float(sz.median()), names_mean=float(sz.mean()),
                   share_thin_dates=float((sz < em.THIN_NAMES).mean()), share_empty=float((sz == 0).mean()))
    return out


def pick_events(holdings, scores):
    """New entries per date with their 12-month outcomes (labels)."""
    rows, prev = [], set()
    for d, pick in holdings.items():
        rows += [(d, c) for c in pick if c not in prev]
        prev = set(pick)
    ev = pd.DataFrame(rows, columns=["signal_date", "company_id"])
    return ev.merge(scores[["company_id", "signal_date", "ret_12m", "excess_12m"]], on=["company_id", "signal_date"],
                    how="left")


def path_dd(ev, ret, cal):
    """Worst drawdown from the entry close within 252 trading days (NaN if < 252 days of data follow)."""
    col = {c: i for i, c in enumerate(ret.columns)}
    R = ret.values
    out = np.full(len(ev), np.nan)
    for k, (d, c) in enumerate(zip(ev["signal_date"], ev["company_id"])):
        e = cal.searchsorted(d, side="right")
        if c not in col or e + 252 >= len(cal):
            continue
        p = np.cumprod(1 + R[e + 1:e + 253, col[c]])
        out[k] = min(p.min() - 1, 0.0)
    return out


def pick_stats(ev, since=None, until=None):
    e = ev
    if since is not None:
        e = e[e["signal_date"] >= since]
    if until is not None:
        e = e[e["signal_date"] < until]
    lab = e[e["ret_12m"].notna()]
    dd = e[e["dd_12m"].notna()]
    return {"picks": int(len(e)), "picks_labelled": int(len(lab)),
            "crash_rate": float((lab["ret_12m"] <= CRASH).mean()) if len(lab) else np.nan,
            "dd30_rate": float((dd["dd_12m"] <= CRASH).mean()) if len(dd) else np.nan,
            "median_excess": float(lab["excess_12m"].median()) if len(lab) else np.nan,
            "beat_rate": float((lab["excess_12m"] > 0).mean()) if len(lab) else np.nan}


def overlap(h_a, h_b):
    """Per date: share of list A's names that are also in list B (dates where A is empty skipped)."""
    v = [len(set(a) & set(h_b[d])) / len(a) for d, a in h_a.items() if a]
    return pd.Series(v)


# ---------------------------------------------------------
# Report tables
# ---------------------------------------------------------

def summary_table(rows):
    lines = ["| list | CAGR (net) | vs Smallcap 250 | max DD | vol | return/vol | years beating index | turnover / yr "
             "| names / date (median) | pick crash rate (12m <= -30%) | picks with a 30% drawdown | median pick vs index "
             "| picks beating index |",
             "|---|---|---|---|---|---|---|---|---|---|---|---|---|"]
    for name, m, p in rows:
        t = f"{m['turnover_yr'] * 100:.0f}%" if "turnover_yr" in m else ""
        n = f"{m['names_median']:.0f}" if "names_median" in m else ""
        pk = (f"{P(p['crash_rate'])} | {P(p['dd30_rate'])} | {P(p['median_excess'])} | {p['beat_rate'] * 100:.0f}%"
              if p else " | | | ")
        lines.append(f"| {name} | {P(m['cagr'])} | {P(m['vs_index_cagr'])} | {P(m['max_dd'])} | {m['vol'] * 100:.1f}% | "
                     f"{m['sharpe']:.2f} | {m['years_beat']}/{m['years']} | {t} | {n} | {pk} |")
    return "\n".join(lines)


def year_table(navs, key="per_year", bench=None):
    years = sorted(next(iter(navs.values()))[key])
    lines = ["| list | " + " | ".join(str(y) for y in years) + " |", "|---|" + "---|" * len(years)]
    for name, m in navs.items():
        cells = []
        for y in years:
            v = m[key].get(y)
            bold = bench is not None and v is not None and v > bench[key].get(y, np.inf)
            cells.append(f"**{P(v)}**" if bold else P(v))
        lines.append(f"| {name} | " + " | ".join(cells) + " |")
    return "\n".join(lines)


def crash_year_table(evs):
    years = sorted({y for ev in evs.values() for y in ev.loc[ev["ret_12m"].notna(), "signal_date"].dt.year})
    lines = ["| list | " + " | ".join(f"{y}" for y in years) + " |", "|---|" + "---|" * len(years)]
    for name, ev in evs.items():
        cells = []
        for y in years:
            g = ev[(ev["signal_date"].dt.year == y) & ev["ret_12m"].notna()]
            cells.append(f"{(g['ret_12m'] <= CRASH).mean() * 100:.0f}% ({len(g)})" if len(g) else "—")
        lines.append(f"| {name} | " + " | ".join(cells) + " |")
    return "\n".join(lines)


def window_table(win, names):
    wins = [w for w, rows in win.items() if not rows.get("_skip")]
    head = [f"{w} ({win[w]['index']['from']} → {win[w]['index']['to']})" for w in wins]
    lines = ["| list | " + " | ".join(head) + " | windows beating index | smaller DD than Top list |",
             "|---|" + "---|" * (len(wins) + 2)]
    for n in [*names, "index", "universe"]:
        lab = {"index": "*NIFTY SMALLCAP 250*", "universe": "*EW universe*"}.get(n, n)
        cells = [f"{P(win[w][n]['ret'])} ({P(win[w][n]['max_dd'], 0)})" for w in wins]
        if n in ("index", "universe"):
            extra = ["", ""]
        else:
            beat = sum(win[w][n]["ret"] > win[w]["index"]["ret"] for w in wins)
            dd = sum(win[w][n]["max_dd"] > win[w]["Top list"]["max_dd"] for w in wins)
            extra = [f"{beat}/{len(wins)}", "—" if n == "Top list" else f"{dd}/{len(wins)}"]
        lines.append(f"| {lab} | " + " | ".join(cells + extra) + " |")
    skipped = [w for w, rows in win.items() if rows.get("_skip")]
    if skipped:
        lines += ["", f"Not testable (before the first rebalance): {', '.join(skipped)}."]
    return "\n".join(lines)


def fmt_check(c):
    return (f"crash {P(c['crash_rate'])} vs Top {P(c['top_crash_rate'])} (limit {P(em.CRASH_RATIO_MAX * c['top_crash_rate'])}); "
            f"max DD {P(c['max_dd'])} vs Top {P(c['top_max_dd'])}; smaller in-year DD {c['years_smaller_dd']}/{c['years']} years; "
            f"CAGR {P(c['cagr'])} vs index {P(c['index_cagr'])}; overlap median {c['overlap_median'] * 100:.0f}%; "
            f"50/50 return/vol {c['combo_sharpe']:.2f} vs Top {c['top_sharpe']:.2f}; names median {c['names_median']:.0f}, "
            f"dates < 5 names {c['share_thin_dates'] * 100:.0f}%; history {c['test_years']:.1f} years")


# ---------------------------------------------------------
# Main
# ---------------------------------------------------------

def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--cost", type=float, default=COST_PER_SIDE, help="cost per side (0.003 = 0.3%%)")
    args = ap.parse_args(argv)
    warnings.filterwarnings("ignore")
    t0 = time.time()
    from growth_model.labels import LABELS_FILE

    labels = pd.read_pickle(LABELS_FILE)
    scores = load_inputs(labels)
    n_per = scores.groupby("signal_date").size()
    start = n_per[n_per >= pe.MIN_NAMES].index.min()
    scores = scores[scores["signal_date"] >= start]
    ret, bench, n_breaks = pe.load_daily()
    cal = ret.index
    check_simulator(scores, ret, bench)
    print(f"scores {len(scores):,} rows, {scores['signal_date'].nunique()} dates from {start:%Y-%m-%d}; "
          f"simulator check vs portfolio_eval OK ({time.time() - t0:.0f}s)", flush=True)

    uni = pe.simulate(scores, ret, bench, None, universe=True)
    uni_nav = uni["gross"]
    bench_nav = bench.reindex(uni_nav.index) / bench.reindex(uni_nav.index).iloc[0]

    lists = {"Top list": top_selector(TOP_RULES), "Top 50 (plain)": top_selector(Rules(n=50))}
    lists.update({k: em_selector(r) for k, r in em.DEFINITIONS.items()})
    # reference only (not a candidate): portfolio_eval's "lowvol" Top-list variant, to see whether the breakout
    # pattern adds anything beyond simply holding calmer stocks
    lists[LOWVOL_REF] = top_selector(pe.SINGLES["lowvol"][1])
    runs, evs = {}, {}
    for name, sel in lists.items():
        runs[name] = simulate(scores, ret, sel, cost=args.cost)
        ev = pick_events(runs[name]["holdings"], scores)
        ev["dd_12m"] = path_dd(ev, ret, cal)
        evs[name] = ev
        print(f"  ran {name} ({time.time() - t0:.0f}s)", flush=True)
    # baseline: every ranked name on every date counted as a "pick"
    allev = scores[["signal_date", "company_id", "ret_12m", "excess_12m"]].copy()
    allev["dd_12m"] = np.nan
    entry_days = runs["Top list"]["entry_days"]
    combos = {f"50/50 {k} + Top list": mix(runs[k]["nav"], runs["Top list"]["nav"], entry_days) for k in em.DEFINITIONS}

    def stats_for(name, since=None):
        r = runs.get(name)
        nav = r["nav"] if r else combos[name]
        if since is not None:
            nav = nav[nav.index > since]
        return nav_stats(nav, bench_nav, r["turnover"] if r else None, r["sizes"] if r else None)

    def bench_stats(nav, since=None):
        if since is not None:
            nav = nav[nav.index > since]
        return nav_stats(nav, bench_nav)

    # ---- full period and fundamentals era ----
    periods = {"full": None, "fund": FUND_ERA}
    tables, year_rows, dd_rows, full = {}, {}, {}, {}
    for pk, since in periods.items():
        rows, ym = [], {}
        for name in [*lists, *combos]:
            m = stats_for(name, since)
            p = pick_stats(evs[name], since) if name in evs else None
            rows.append((name, m, p))
            ym[name] = m
            full.setdefault(pk, {})[name] = {"metrics": m, "picks": p}
        bm, um = bench_stats(bench_nav, since), bench_stats(uni_nav, since)
        pa = pick_stats(allev, since)
        rows += [("*NIFTY SMALLCAP 250*", bm, None), ("*EW universe (gross; picks = every ranked name)*", um, pa)]
        ym["*NIFTY SMALLCAP 250*"], ym["*EW universe*"] = bm, um
        full[pk]["index"], full[pk]["universe"], full[pk]["all_picks"] = bm, um, pa
        tables[pk] = summary_table(rows)
        year_rows[pk] = year_table(ym, "per_year", bm)
        dd_rows[pk] = year_table(ym, "per_year_dd")

    # ---- diversification ----
    top_daily = runs["Top list"]["nav"].pct_change().dropna()
    div = {}
    for k in em.DEFINITIONS:
        d = runs[k]["nav"].pct_change().dropna()
        nz = runs[k]["sizes"] > 0
        first = runs[k]["sizes"][nz].index.min()
        m = d.index > first
        # 15-day (rebalance-period) returns
        per = runs[k]["nav"].reindex(entry_days).pct_change().dropna()
        per_t = runs["Top list"]["nav"].reindex(entry_days).pct_change().dropna()
        mm = per.index > first
        ov = overlap({dd: h for dd, h in runs[k]["holdings"].items() if dd >= first}, runs["Top list"]["holdings"])
        excess = (d - top_daily)[m]
        div[k] = {"first_date": str(first.date()), "corr_daily": float(d[m].corr(top_daily[m])),
                  "corr_15d": float(per[mm].corr(per_t[mm])), "overlap_median": float(ov.median()),
                  "overlap_mean": float(ov.mean()),
                  "tracking_error": float(excess.std() * np.sqrt(252))}

    # ---- decision (each definition on its own test period) ----
    cand, checks = {}, {}
    for k, rules in em.DEFINITIONS.items():
        first = pd.Timestamp(div[k]["first_date"])
        since = first - pd.Timedelta(days=1)
        m, mt = stats_for(k, since), stats_for("Top list", since)
        mc, mi = stats_for(f"50/50 {k} + Top list", since), bench_stats(bench_nav, since)
        pk_, pt = pick_stats(evs[k], first), pick_stats(evs["Top list"], first)
        ys = [y for y in m["per_year_dd"] if y in mt["per_year_dd"]]
        cand[k] = {"crash_rate": pk_["crash_rate"], "top_crash_rate": pt["crash_rate"], "max_dd": m["max_dd"],
                   "top_max_dd": mt["max_dd"], "years_smaller_dd": int(sum(m["per_year_dd"][y] > mt["per_year_dd"][y] for y in ys)),
                   "years": len(ys), "cagr": m["cagr"], "index_cagr": mi["cagr"], "top_cagr": mt["cagr"],
                   "overlap_median": div[k]["overlap_median"], "combo_sharpe": mc["sharpe"], "top_sharpe": mt["sharpe"],
                   "names_median": m["names_median"], "share_thin_dates": m["share_thin_dates"],
                   "test_years": m["span_years"], "from": m["from"]}
        ok, ch = em.passes(cand[k])
        checks[k] = {"pass": ok, **ch}
        print(f"  {k}: {'PASS' if ok else 'fail'}  " + fmt_check(cand[k]), flush=True)
    chosen = em.choose(cand)
    in_code = next((k for k, r in em.DEFINITIONS.items() if r == em.RECOMMENDED), None)
    print(f"\npre-declared rule -> recommended: {chosen}; early_movers.RECOMMENDED = {in_code}"
          + ("" if in_code == chosen else "  << MISMATCH: update early_movers.RECOMMENDED and the verdict"))

    # ---- cost sensitivity (Top list vs each definition) ----
    cost_rows = {}
    for name in ["Top list", *em.DEFINITIONS]:
        cost_rows[name] = {c: nav_stats(simulate(scores, ret, lists[name], cost=c)["nav"], bench_nav) for c in COST_GRID}

    # ---- windows ----
    show = [*lists, *combos]
    win = {}
    for wname, d0, d1, _ in EVENTS:
        if pd.Timestamp(d0) < start:
            win[wname] = {"_skip": True}
            continue
        rows = {n: pe.window_stats(runs[n]["nav"] if n in runs else combos[n], d0, d1) for n in show}
        rows["index"], rows["universe"] = pe.window_stats(bench_nav, d0, d1), pe.window_stats(uni_nav, d0, d1)
        win[wname] = rows

    out = {"cost_per_side": args.cost, "start": str(start.date()), "end": str(bench_nav.index[-1].date()),
           "definitions": {k: r.label() for k, r in em.DEFINITIONS.items()}, "periods": full,
           "diversification": div, "candidates": cand, "checks": checks, "chosen": chosen, "windows": win,
           "cost_sensitivity": {n: {str(c): {k: m[k] for k in ("cagr", "max_dd", "sharpe")} for c, m in r.items()}
                                for n, r in cost_rows.items()}}
    OUT_FILE.write_text(json.dumps(out, indent=1, default=str))

    defs = "\n".join(f"- **{k}**: {r.label()}" for k, r in em.DEFINITIONS.items())
    div_tab = ["| definition | first date with names | overlap with Top list (median / mean share of its names) "
               "| daily return correlation | 15-day return correlation | tracking error vs Top list |",
               "|---|---|---|---|---|---|"]
    for k, d in div.items():
        div_tab.append(f"| {k} | {d['first_date']} | {d['overlap_median'] * 100:.0f}% / {d['overlap_mean'] * 100:.0f}% | "
                       f"{d['corr_daily']:.2f} | {d['corr_15d']:.2f} | {d['tracking_error'] * 100:.1f}% |")
    crit = list(next(iter(checks.values())))[1:]
    dec_tab = ["| definition | " + " | ".join(crit) + " | ships? |", "|---|" + "---|" * (len(crit) + 1)]
    for k, c in checks.items():
        dec_tab.append(f"| {k} | " + " | ".join("pass" if c[x] else "**fail**" for x in crit) + f" | {'yes' if c['pass'] else 'no'} |")
    md = [
        "# InvestIQ \"Early Movers\": a tradable test of the base-breakout list",
        "",
        f"Generated by `python3 -m rankings.early_movers_eval` (ml/rankings/early_movers_eval.py; definitions, selection "
        f"and the ship rule in ml/rankings/early_movers.py). Period {start:%Y-%m-%d} → {bench_nav.index[-1]:%Y-%m-%d}, "
        f"{scores['signal_date'].nunique()} rebalances on the 1st/16th grid, investiq-v1 scores rebuilt point-in-time "
        f"(portfolio_eval.load_scores), fundamentals point-in-time (financial_model.data.build_panel). Costs "
        f"{args.cost * 100:.1f}% per side. {n_breaks} one-day price-series breaks set to 0. The simulator is checked "
        f"to reproduce portfolio_eval exactly on the Top list.",
        "",
        VERDICT,
        "",
        "## 1. Pre-declared definitions (fixed in code before the first run)",
        "",
        defs,
        "",
        "Shared: universe >= 0.5 crore/day and >= 252 days listed (as the Top list), equal weight, at most 30 names, no "
        "new buys among the 5% most volatile, a holding stays while it still qualifies or ranks in the investiq-v1 "
        "top 150, rebalanced on the 1st/16th; fewer qualifiers = a shorter list, none = cash. Only the number of "
        "qualifiers per date (no returns) was looked at before fixing E4's thresholds.",
        "",
        "## 2. Ship rule (pre-declared, `early_movers.passes`) and result",
        "",
        "Each definition on its own test period (from its first date with any name) vs the Top list on the same dates.",
        "",
        "\n".join(dec_tab),
        "",
        *[f"- {k}: " + fmt_check(c) for k, c in cand.items()],
        "",
        f"Pre-declared choice among passing definitions: **{chosen or 'none'}**.",
        "",
        "## 3. Full period (2019-07 → today), net of costs",
        "",
        "Picks = new entries; crash = 12-month return <= -30% (labels, entry day to 252 trading days later); the 30% "
        "drawdown column counts a fall of 30%+ from the entry close at any point in those 252 days. Picks from the "
        "last 12 months have no outcome yet. E3 holds cash until its first qualifier (cash-flow data starts in 2021), so "
        "its full-period row is not a fair comparison: use section 4. return/vol = annualised mean daily return / vol.",
        "",
        tables["full"],
        "",
        f"## 4. Fundamentals era ({FUND_ERA:%Y-%m-%d} → today: all definitions fully testable)",
        "",
        "Every list sliced to the same start (holdings as a follower would have had them that day).",
        "",
        tables["fund"],
        "",
        "## 5. Per calendar year (full period; bold = beat the Smallcap 250; 2019 and 2026 partial)",
        "",
        year_rows["full"],
        "",
        "### Worst drawdown inside each calendar year",
        "",
        dd_rows["full"],
        "",
        "### Pick crash rate by entry year (share of new entries with a 12-month return <= -30%; picks in brackets)",
        "",
        crash_year_table({**evs, "every ranked name": allev}),
        "",
        "## 6. Diversification vs the Top list",
        "",
        "\n".join(div_tab),
        "",
        f"`{LOWVOL_REF}` (sections 3-5, 8) is portfolio_eval's rejected \"lowvol\" variant (the 50 least volatile of the "
        "top 100 by score, full replacement), shown only as a reference: if Early Movers looked no different from it, "
        "the breakout pattern would add nothing beyond holding calmer stocks.",
        "",
        "50/50 rows in sections 3-4: half in the definition, half in the Top list, back to 50/50 every 1st/16th.",
        "",
        "## 7. Cost sensitivity (net CAGR / max DD / return-vol)",
        "",
        "| list | " + " | ".join(f"{c * 100:.1f}% per side" for c in COST_GRID) + " |",
        "|---|" + "---|" * len(COST_GRID),
        *[f"| {n} | " + " | ".join(f"{P(r[c]['cagr'])} / {P(r[c]['max_dd'])} / {r[c]['sharpe']:.2f}" for c in COST_GRID) + " |"
          for n, r in cost_rows.items()],
        "",
        "## 8. Time-machine windows (lists run continuously; return, worst drawdown in brackets)",
        "",
        window_table(win, show),
        "",
        CAVEATS,
    ]
    REPORT.write_text("\n".join(md) + "\n")
    print(f"\nwrote {REPORT} and {OUT_FILE} in {time.time() - t0:.0f}s")


VERDICT = """## Verdict (run of 2026-10-02; net of 0.3% per side)

**Ship E1 as a second list, described as what it is: a steadier, lower-return list with fewer blow-ups.
It is not a better Top list and it is not a diversifier.** `early_movers.RECOMMENDED = E1`: the base
breakout (within 5% of the 52-week high, up < 30% in 6 months, above the 200-day average, < 60% above it),
the 30 best investiq-v1 scores among those, no new buys in the 5% most volatile, a holding stays while it
still qualifies or ranks in the top 150, equal weight, rebuilt on the 1st/16th. E1 and E2 passed the
pre-declared rule (section 2); E1 won the pre-declared tie-break on a crash rate of 7.6% vs 7.8%, i.e. a
coin flip. E2 (same plus score >= 60) earned +3 pts more CAGR (almost all in 2021) with the same risk;
switching to it now would be a post-hoc choice.

| 2019-07 → 2026-09 | CAGR | vs Smallcap 250 | max DD | vol | return/vol | pick crash rate | picks with a 30% drawdown | median pick vs index | turnover / yr |
|---|---|---|---|---|---|---|---|---|---|
| Top list (shipped) | +35.2% | +16.2 pts | -38.1% | 22.9% | 1.45 | 11.4% | 27.6% | -0.2% | 361% |
| Top 50 (plain) | +34.2% | +15.2 pts | -38.3% | 23.1% | 1.41 | 11.1% | 29.4% | -2.2% | 770% |
| **E1 Early Movers** | **+27.8%** | **+8.8 pts** | **-33.8%** | **19.1%** | **1.40** | **7.6%** | **18.3%** | **-2.5%** | **542%** |
| 50/50 E1 + Top list | +31.6% | +12.6 pts | -35.8% | 20.5% | 1.46 | | | | |
| NIFTY SMALLCAP 250 | +19.0% | | -43.8% | 19.9% | 0.99 | | | | |
| every ranked name (EW, gross) | +22.9% | +3.9 pts | -43.4% | 20.7% | 1.12 | 12.1% | | -8.3% | |

What holds up:
- **Fewer blow-ups.** A third fewer picks fall 30%+ over 12 months (7.6% vs 11.4%) and far fewer suffer a
  30% drawdown at any point (18% vs 28%). By entry year the crash rate is lower in 2021, 2022, 2024 and
  2025 (2024: 9% vs 19%) and level in 2019, 2020 and 2023 (never clearly higher).
- **Shallower drawdowns every year.** Smaller in-year drawdown than the Top list in 8/8 calendar years
  (clearly in 2020-24: e.g. 2022 -17% vs -23%; by under 2.5 pts in 2019, 2025, 2026), and in 5/6 time-machine
  windows (COVID crash -24% vs -29%, 2022 sell-off +1.6% vs -2.7%).
- It still beats the Smallcap 250 (+8.8 pts CAGR, 6/8 years, 5/6 windows). Since mid-2021 the gap to the Top
  list is small (+26.5% vs +28.4% CAGR) with better return/vol (1.38 vs 1.24) and drawdown (-24% vs -26%).

What does not:
- **Lower return, concentrated in fast rallies.** -7.4 pts CAGR over the full period: 2021 +48% vs +108%,
  post-COVID rally +67% vs +120% (and below the index's +95%), the last year +12.9% vs +27.3%. A follower
  must expect to lag badly whenever the market chases momentum.
- **Not a diversifier.** Median overlap with the Top list is 50% of its names (the keep rule lets winners
  ride while the main model ranks them top 150), daily correlation 0.91. The 50/50 mix has return/vol 1.46 vs
  1.45 (no gain) and only -35.8% vs -38.1% max drawdown: the pre-declared criterion e passed at its edge.
- **Partly just "calmer stocks".** The rejected low-vol Top-list variant (reference row) has a similar profile
  (-34.4% max DD, 19.7% vol, +29.9% CAGR). E1 is better on pick-level damage (30% drawdowns 18% vs 24%,
  crash rate 7.6% vs 8.6%) and in 2022 (-17% vs -22%), so the breakout pattern adds a little beyond low
  volatility, not a lot.
- **Costs.** Turnover 542% a year vs 361%. At 0.6% per side E1's return/vol falls to 1.23 (Top list 1.36).

Fundamentals did not earn their place. E3 (strict growth + acceleration + margins + cash conversion) had the
lowest crash rate (4.9% vs the Top list's 12.4% since 2021) but a deeper drawdown than the Top list in its
era (-29.7% vs -26.4%), higher volatility (25.7%), a median of 10 names and < 5 names on 14% of dates. E4
(looser) failed only on max drawdown (2.4 pts better, rule needs 3) and was otherwise like E1/E2.

**Overfitting, said plainly.** The base-breakout pattern was found by looking at 2017-2026 descriptively,
which contains this whole test period: E1 is not out-of-sample. What protects the result: four definitions
and the ship rule were written into early_movers.py before the first backtest (only qualifier counts, no
returns, were looked at to set E4); N = 30 and the keep-while-top-150 rule were not varied afterwards (so
their sensitivity is untested, not tuned). The risk result is the robust part (8/8 years, lower crash rate in
every year where it differed); the return gap is regime-driven. Fundamental evidence is thin: cash
conversion exists only from mid-2021 (about 5 years, one cycle), E3 made 25-85 picks a year (308 with an
outcome), held for months, so closer to a few dozen independent observations; 4.9% vs 7.6% is not
distinguishable from luck. Survivorship bias flatters every list."""

CAVEATS = """## Caveats

- Survivorship: `stock_prices` only has companies listed today, so every list is flattered (the index is not).
  Differences between lists are fairer than levels.
- One flat cost (0.3% per side); price returns, no dividends or tax.
- Fundamentals: revenue/profit growth from 2019, revenue acceleration thinner in 2019-20, cash conversion only
  from mid-2021; banks / NBFCs / insurers never pass the fundamental filters.
- Pick outcomes overlap heavily (a name held for months, 24 entry dates a year): a crash rate on a few hundred
  picks is closer to a few dozen independent observations."""


if __name__ == "__main__":
    main()
