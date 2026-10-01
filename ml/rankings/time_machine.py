"""Time-machine validation of the live ranking (investiq-v1): rank as of a past date, then check reality.

For a past date D, the snapshot is rebuilt with rankings.build_v3 exactly as the site would have
published it that morning (same loaders: prices up to D, financial filings with filing_date <= D,
fin-sector rows as of D, news in the 90 days to D). Nothing after D enters the scores. Then actual
returns from D to an end date E are measured and compared with the scores:

    entry      first close strictly after D (you act on the ranking the next session)
    exit       last close on or before E (a stock that stopped trading keeps its last close)
    breaks     a one-day move > +100% or < -60% inside [entry, exit] is a data break
               (growth_model.labels): that company's outcome is dropped, not counted as a 100x win
    benchmark  NIFTY SMALLCAP 250 over the same days

Reported: Spearman IC (score vs return), returns by score decile and by label, an equal-weight
top-N portfolio vs the index and vs all ranked stocks (including the worst drawdown along the way),
the top and bottom names with what actually happened, and how the "price already stretched" risk
flag played out. `--events` runs preset stress windows (COVID crash and rebound, the 2018 and 2024-25
small-cap crashes, the 2022 rate-hike sell-off) plus "one year ago".

Caveats (printed in the report): today's company list (no delisted names: survivorship bias) and
today's sector labels; financial-statement balance sheets only exist from late 2022 and news only
from 2026-08, so older snapshots lean more on price trend than today's.

DB: SELECT only. Writes ml/rankings/reports/time_machine_<D>_<E>.md (+ .csv) and, with --events,
ml/rankings/reports/TIME_MACHINE.md.

CLI:
    python3 -m rankings.time_machine --date 2025-09-30                # to the latest price
    python3 -m rankings.time_machine --date 2020-01-16 --to 2020-03-31
    python3 -m rankings.time_machine --events
"""

import argparse
import json
import warnings
from datetime import date, datetime, timedelta
from pathlib import Path

import numpy as np
import pandas as pd

from . import build_v3 as v3
from .build import BENCHMARK

REPORT_DIR = Path(__file__).resolve().parent / "reports"
TOP_N = 50
BREAK_UP, BREAK_DOWN = 1.0, -0.6

EVENTS = [
    ("One year ago", "2025-09-30", None, "Ranked a year ago, held to today."),
    ("COVID crash", "2020-01-16", "2020-03-31", "Ranked before COVID hit India; held through the March 2020 crash."),
    ("COVID crash and rebound", "2020-01-16", "2021-01-15", "Same picks, held for a year through the crash and the rebound."),
    ("Post-COVID rally", "2020-04-16", "2021-04-16", "Ranked near the bottom; the junk-led rebound year."),
    ("2018 small-cap crash", "2018-01-16", "2019-01-16", "Ranked at the January 2018 small-cap peak."),
    ("2022 rate-hike sell-off", "2021-12-16", "2022-06-30", "Ranked before global rate hikes and the Ukraine war."),
    ("2024-25 small-cap correction", "2024-09-16", "2025-03-03", "Ranked at the September 2024 peak; held through the fall."),
]


# ---------------------------------------------------------
# Outcomes
# ---------------------------------------------------------

def load_paths(conn, company_ids, start, end):
    """Daily closes for the companies and the benchmark between start and end (inclusive)."""
    cur = conn.cursor()
    rows, ids = [], sorted(int(i) for i in company_ids)
    for k in range(0, len(ids), 600):
        chunk = ids[k:k + 600]
        cur.execute(
            f"SELECT company_id, price_date, close_price FROM stock_prices "
            f"WHERE company_id IN ({', '.join(['%s'] * len(chunk))}) AND price_date BETWEEN %s AND %s",
            [*chunk, start, end],
        )
        rows.extend(cur.fetchall())
    cur.execute("SELECT price_date, close_price FROM index_prices WHERE index_name = %s "
                "AND price_date BETWEEN %s AND %s", (BENCHMARK, start, end))
    idx = pd.DataFrame(cur.fetchall(), columns=["price_date", "close"])
    cur.close()
    px = pd.DataFrame(rows, columns=["company_id", "price_date", "close"])
    for f in (px, idx):
        f["price_date"] = pd.to_datetime(f["price_date"])
        f["close"] = pd.to_numeric(f["close"], errors="coerce").astype(float)
    px = px[px["close"] > 0]
    wide = px.pivot_table(index="price_date", columns="company_id", values="close").sort_index()
    return wide, idx.dropna().set_index("price_date")["close"].sort_index()


def outcomes(wide, bench, snap, end):
    """-> (per-company actual return / excess / max drawdown, benchmark return, entry day, exit day)."""
    days = bench.index[(bench.index > pd.Timestamp(snap)) & (bench.index <= pd.Timestamp(end))]
    if len(days) < 2:
        raise SystemExit(f"not enough benchmark days between {snap} and {end}")
    entry_day, exit_day = days[0], days[-1]
    w = wide.loc[(wide.index >= entry_day) & (wide.index <= exit_day)]
    entry = w.iloc[0]
    exit_ = w.ffill().iloc[-1]
    daily = w.pct_change(fill_method=None)
    broken = ((daily > BREAK_UP) | (daily < BREAK_DOWN)).any()
    ret = (exit_ / entry - 1).where(entry.notna() & ~broken)
    path = w.ffill() / entry
    mdd = (path / path.cummax() - 1).min().where(ret.notna())
    b_ret = bench.loc[exit_day] / bench.loc[entry_day] - 1
    out = pd.DataFrame({"actual_return": ret, "max_drawdown": mdd})
    out["excess"] = out["actual_return"] - b_ret
    out.index.name = "company_id"
    return out.reset_index(), b_ret, entry_day, exit_day, path


def portfolio_path(path, ids):
    """Equal-weight buy-and-hold value path of `ids` (each normalised to 1 at entry)."""
    cols = [c for c in ids if c in path.columns]
    return path[cols].mean(axis=1) if cols else pd.Series(dtype=float)


def max_dd(series):
    return float((series / series.cummax() - 1).min()) if len(series) else np.nan


# ---------------------------------------------------------
# One window
# ---------------------------------------------------------

class NotRankable(Exception):
    pass


def run_window(conn, snap, end, top_n=TOP_N):
    inp = v3.load_inputs(conn, snap)
    df, records, _ = v3.build(conn, snap, inp)
    ranks = pd.DataFrame(records)
    ranked = ranks[ranks["growth_score"].notna()].copy()
    if len(ranked) < 100:
        raise NotRankable(f"only {len(ranked)} companies rankable on {snap}: a fresh financial growth reading is "
                          f"required, and filings only support year-on-year growth from about 2019")
    wide, bench = load_paths(conn, ranked["company_id"], snap, end)
    out, b_ret, entry_day, exit_day, path = outcomes(wide, bench, snap, end)
    r = ranked.merge(out, on="company_id", how="left")
    r = r[r["actual_return"].notna()].copy()
    r["stretched"] = r["risks"].apply(lambda x: any("Price already stretched" in t for t in (x or [])))
    r["decile"] = pd.qcut(r["growth_score"].rank(method="first"), 10, labels=range(1, 11)).astype(int)

    bench_path = bench.loc[entry_day:exit_day] / bench.loc[entry_day]
    top_ids = r.nsmallest(top_n, "rank_overall")["company_id"]
    bot_ids = r.nlargest(top_n, "rank_overall")["company_id"]
    pf = {
        f"Top {top_n} by InvestIQ score": portfolio_path(path, top_ids),
        "All ranked stocks": portfolio_path(path, r["company_id"]),
        f"Bottom {top_n}": portfolio_path(path, bot_ids),
        BENCHMARK: bench_path,
    }
    return dict(snap=snap, end=exit_day.date(), entry=entry_day.date(), bench=b_ret, rows=r, pf=pf,
                ic=float(r["growth_score"].corr(r["actual_return"], method="spearman")),
                n_ranked=len(ranked), n_measured=len(r))


# ---------------------------------------------------------
# Report
# ---------------------------------------------------------

pct = lambda x, d=1: "—" if x is None or pd.isna(x) else f"{x * 100:+.{d}f}%"


def bucket_table(r, key, order=None):
    g = r.groupby(key, observed=True)
    t = pd.DataFrame({
        "stocks": g.size(),
        "avg return": g["actual_return"].mean(),
        "median return": g["actual_return"].median(),
        "beat index": g["excess"].apply(lambda s: (s > 0).mean()),
        "fell 30%+": g["actual_return"].apply(lambda s: (s < -0.3).mean()),
        "worst drawdown (median)": g["max_drawdown"].median(),
    })
    if order is not None:
        t = t.reindex([o for o in order if o in t.index])
    lines = [f"| {key} | stocks | avg return | median return | beat index | fell 30%+ | median worst drawdown |",
             "|---|---|---|---|---|---|---|"]
    for k, row in t.iterrows():
        lines.append(f"| {k} | {int(row['stocks'])} | {pct(row['avg return'])} | {pct(row['median return'])} | "
                     f"{row['beat index'] * 100:.0f}% | {row['fell 30%+'] * 100:.0f}% | {pct(row['worst drawdown (median)'])} |")
    return "\n".join(lines)


def names_table(r, ascending, n=15):
    t = r.sort_values("rank_overall", ascending=ascending).head(n)
    lines = ["| rank | company | sector | score | label | actual return | vs index |", "|---|---|---|---|---|---|---|"]
    for _, x in t.iterrows():
        lines.append(f"| {int(x['rank_overall'])} | {x['symbol']} | {x.get('sector') or '—'} | {x['growth_score']:.0f} | "
                     f"{x['growth_label']} | {pct(x['actual_return'], 0)} | {pct(x['excess'], 0)} |")
    return "\n".join(lines)


def window_markdown(w, title=None, note=None):
    r, pf = w["rows"], w["pf"]
    top_key = next(k for k in pf if k.startswith("Top"))
    lines = [f"## {title or 'Ranked ' + str(w['snap'])}: {w['snap']} → {w['end']}", ""]
    if note:
        lines += [note, ""]
    lines += [
        f"Ranked {w['n_ranked']:,} companies as of {w['snap']} (bought at the {w['entry']} close); "
        f"{w['n_measured']:,} have a clean price path to {w['end']}. "
        f"{BENCHMARK}: {pct(w['bench'])}. Spearman IC (score vs actual return): **{w['ic']:+.3f}**.", "",
        "| portfolio (equal weight, buy and hold) | return | worst drawdown on the way |", "|---|---|---|",
    ]
    for k, s in pf.items():
        lines.append(f"| {k} | {pct(s.iloc[-1] - 1) if len(s) else '—'} | {pct(max_dd(s))} |")
    lines += ["", "**By score decile** (10 = highest scores)", "", bucket_table(r, "decile", order=list(range(10, 0, -1))),
              "", "**By label**", "", bucket_table(r, "growth_label", order=["Strong", "Positive", "Neutral", "Weak"]),
              "", "**\"Price already stretched\" risk flag**", "",
              bucket_table(r.assign(flag=np.where(r["stretched"], "flagged", "not flagged")), "flag"),
              "", f"**Top 15 picks on {w['snap']} and what happened**", "", names_table(r, True),
              "", f"**Bottom 15 on {w['snap']}**", "", names_table(r, False), ""]
    return "\n".join(lines)


def summary_line(name, w):
    pf = w["pf"]
    top = next(v for k, v in pf.items() if k.startswith("Top"))
    allr, bench = pf["All ranked stocks"], pf[BENCHMARK]
    r = w["rows"]
    dec = r.groupby("decile")["actual_return"].mean()
    return (f"| {name} | {w['snap']} → {w['end']} | {w['ic']:+.3f} | {pct(top.iloc[-1] - 1)} | {pct(allr.iloc[-1] - 1)} | "
            f"{pct(bench.iloc[-1] - 1)} | {pct(dec.get(10))} / {pct(dec.get(1))} | {pct(max_dd(top))} / {pct(max_dd(bench))} |")


CAVEATS = """**Read with care**
- Scores use only data public on the ranking date, but the company list and sector labels are today's:
  companies that later delisted are missing (survivorship bias), which flatters every row, not one more than another.
- Balance-sheet data starts in late 2022 and company news in 2026-08, so pre-2023 snapshots are mostly price
  trend plus income-statement growth; the 2025-26 window is the closest to today's full model.
- One window is one draw of luck. The walk-forward test (ml/rankings/combiner_eval.py) averages over 2019-2026.
- Returns are price returns before costs and taxes; dividends are not included."""


def main(argv=None):
    parser = argparse.ArgumentParser(description="Rank as of a past date, then compare with what happened.")
    parser.add_argument("--date", help="ranking date YYYY-MM-DD")
    parser.add_argument("--to", help="end date YYYY-MM-DD (default: latest price)")
    parser.add_argument("--top", type=int, default=TOP_N)
    parser.add_argument("--events", action="store_true", help="run the preset stress windows")
    args = parser.parse_args(argv)
    warnings.filterwarnings("ignore")
    from news_pipeline.db import get_connection

    parse = lambda s: datetime.strptime(s, "%Y-%m-%d").date()
    REPORT_DIR.mkdir(exist_ok=True)
    conn = get_connection()
    try:
        if args.events:
            summary = ["| window | ranked → held to | IC | top 50 | all ranked | Smallcap 250 | top / bottom decile avg | worst drawdown top 50 / index |",
                       "|---|---|---|---|---|---|---|---|"]
            sections = []
            for name, d0, d1, note in EVENTS:
                try:
                    w = run_window(conn, parse(d0), parse(d1) if d1 else date.today(), args.top)
                except NotRankable as error:
                    summary.append(f"| {name} | {d0} → {d1} | not testable: {error} | | | | | |")
                    print(summary[-1], flush=True)
                    continue
                summary.append(summary_line(name, w))
                sections.append(window_markdown(w, name, note))
                print(summary[-1], flush=True)
            md = "\n".join(["# InvestIQ time-machine validation (investiq-v1)", "",
                            f"Generated {date.today()}. Each window ranks companies with only the data public on its "
                            "start date, then measures what actually happened.", "", *summary, "", CAVEATS, "", *sections])
            (REPORT_DIR / "TIME_MACHINE.md").write_text(md)
            print(f"wrote {REPORT_DIR / 'TIME_MACHINE.md'}")
            return
        if not args.date:
            parser.error("--date or --events is required")
        snap, end = parse(args.date), parse(args.to) if args.to else date.today()
        w = run_window(conn, snap, end, args.top)
        md = "\n".join(["# InvestIQ time-machine validation (investiq-v1)", "", window_markdown(w), CAVEATS])
        stem = REPORT_DIR / f"time_machine_{w['snap']}_{w['end']}"
        stem.with_suffix(".md").write_text(md)
        w["rows"][["company_id", "symbol", "sector", "rank_overall", "growth_score", "growth_label", "stretched",
                   "actual_return", "excess", "max_drawdown"]].to_csv(stem.with_suffix(".csv"), index=False)
        print(md)
        print(f"\nwrote {stem}.md / .csv")
    finally:
        conn.close()


if __name__ == "__main__":
    main()
