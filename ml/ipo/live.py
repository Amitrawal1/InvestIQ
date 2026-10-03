"""Live prototype: valuation vs listed peers for an upcoming / open IPO (and recently listed ones).

For each issue in ml/ipo/live_inputs.json (pre-IPO figures typed from the RHP) it builds:
    1. post-issue market cap at the UPPER end of the band (shares = pre-issue + fresh issue / cap price)
    2. P/E, P/B (post-issue book = pre-issue net worth + fresh money), P/S vs the median of listed
       InvestIQ-industry peers priced at the last close before today (point-in-time peer panel,
       ml/valuation/features.py rules), plus the RHP's own named peers where they are in the panel
    3. verdict wording (ipo/valuation.py; descriptive, not advice)
    4. historical context from ml/ipo/eval_sample.csv: how earlier IPOs with the same verdict did
    5. rule-based key risks
`--recent N` also prints the N most recently listed IPOs from ipo_dataset.csv (XBRL-proxy financials).

Output: printed markdown + ml/ipo/live_output.json.
CLI (from ml/):  python3 -m ipo.live [--recent 2]
"""

import argparse
import json
import math
from datetime import date
from pathlib import Path

import numpy as np
import pandas as pd

from growth_model.prices import BENCHMARK, load_prices

from . import dataset as ds
from .valuation import ipo_valuation

PKG_DIR = Path(__file__).resolve().parent
INPUTS = PKG_DIR / "live_inputs.json"
OUTPUT = PKG_DIR / "live_output.json"
SAMPLE = PKG_DIR / "eval_sample.csv"
LIVE_PEERS = ds.src.RAW_DIR / "peer_panel_live.pkl"
DISCLAIMER = ("InvestIQ is not a SEBI-registered investment adviser or research analyst. This compares the "
              "issue price with listed companies; it is not a recommendation to apply, buy or sell.")


def ipo_from_rhp(x):
    cap = float(x["price_band"][1])
    fresh_sh = x.get("fresh_issue_shares_cr")
    if fresh_sh is None:
        fresh_sh = float(x.get("fresh_issue_cr", 0.0)) / cap
    fresh_amt = fresh_sh * cap
    shares_post = float(x["pre_issue_shares_cr"]) + fresh_sh
    issue_size = fresh_amt + float(x.get("ofs_shares_cr", 0.0)) * cap
    return {"issue_price": cap, "shares_post": shares_post, "revenue_ann": x["revenue_cr"],
            "net_profit_ann": x["pat_cr"], "equity": x["net_worth_pre_cr"] + fresh_amt,
            "industry": x["industry"], "issue_size_cr": issue_size,
            "ofs_share": (float(x.get("ofs_shares_cr", 0.0)) * cap) / issue_size if issue_size else None}


def history(verdict, loss_making):
    if not SAMPLE.exists():
        return None
    s = pd.read_csv(SAMPLE)
    g = s[s["verdict"].astype(str).str.replace("_loss_making", "") == verdict.replace("_loss_making", "")]
    out = {"verdict": verdict, "n": int(len(g))}
    for c in ("list_gain_close", "exc_6m", "exc_12m"):
        v = g[c].dropna()
        out[c] = {"n": int(len(v)), "median": float(v.median()) if len(v) else None,
                  "mean": float(v.mean()) if len(v) else None, "share_positive": float((v > 0).mean()) if len(v) else None}
    a = s
    out["all_ipos"] = {c: {"n": int(a[c].notna().sum()), "median": float(a[c].median())} for c in ("list_gain_close", "exc_6m", "exc_12m")}
    return out


def market_now(index, issues_df):
    bench = index[index["index_key"] == BENCHMARK].set_index("price_date")["close"].sort_index()
    hi = bench.rolling(252, min_periods=120).max()
    out = {"sc250_date": str(bench.index[-1].date()), "sc250_drawdown": float(bench.iloc[-1] / hi.iloc[-1] - 1),
           "sc250_ret_3m": float(bench.iloc[-1] / bench.iloc[-64] - 1)}
    if issues_df is not None:
        t = pd.Timestamp(date.today())
        m = issues_df[(issues_df["board"] == "mainboard") & ~issues_df["is_fpo"].astype(bool)]
        m = m[(pd.to_datetime(m["listing_date"]) < t) & (pd.to_datetime(m["listing_date"]) >= t - pd.Timedelta(days=90))]
        out["ipos_prior_90d"] = int(len(m))
        out["prior_90d_median_list_gain"] = float(m["list_gain_close"].median()) if m["list_gain_close"].notna().sum() >= 3 else None
    return out


def risks(x, ipo, val, mkt):
    r = []
    if val.get("loss_making"):
        r.append("Loss-making at the latest fiscal year: no P/E; the price rests on future profits.")
    rel_pe = val.get("rel_pe")
    if rel_pe is not None and rel_pe > 0.405:
        r.append(f"P/E is {math.exp(rel_pe) - 1:.0%} above the listed-peer median.")
    e0, e2 = x.get("eps_basic_2y_earlier"), x.get("eps_basic_latest")
    if e0 and e2 and e0 > 0 and e2 / e0 >= 3:
        r.append(f"Earnings rose {e2 / e0:.1f}x in two years (EPS {e0} -> {e2}): the P/E rests on a short record; "
                 "check how repeatable the latest year is.")
    if ipo.get("ofs_share") is not None and ipo["ofs_share"] > 0.5:
        r.append(f"{ipo['ofs_share']:.0%} of the issue is an offer for sale (money goes to selling shareholders, not the company).")
    if ipo.get("issue_size_cr") is not None and ipo["issue_size_cr"] < 250:
        r.append(f"Small issue (about Rs {ipo['issue_size_cr']:.0f} crore): small IPOs are more volatile after listing and can be thinly traded.")
    if (val.get("peer_n_pe") or 0) < 10:
        r.append(f"Only {val.get('peer_n_pe')} listed profitable peers in the industry: the comparison is coarse.")
    if mkt.get("prior_90d_median_list_gain") is not None and mkt["prior_90d_median_list_gain"] > 0.2:
        r.append("Hot IPO market (median listing gain of the last 90 days above 20%).")
    if mkt.get("sc250_drawdown", 0) < -0.2:
        r.append("Small caps are more than 20% below their 1-year high.")
    return r


def peers_now(companies, stocks, today):
    p = ds.peer_panel([today], companies, stocks, refresh=True, cache=LIVE_PEERS)
    return p[p["signal_date"] == today]


def render(rep):
    v = rep["valuation"]
    lines = [f"### {rep['company']} ({rep['symbol']}) — {rep.get('status', '')}",
             f"Price band Rs {rep['price_band'][0]}-{rep['price_band'][1]}; at the upper end: market cap "
             f"Rs {v['mcap_cr']:,.0f} crore; {rep['fiscal']}. Peers: InvestIQ industry `{rep['industry']}` "
             f"({v['n_peers']} listed, priced {rep['peer_date']}).",
             "", "| Metric | IPO (upper band) | Peer median | Peers | IPO vs peers |", "|---|---|---|---|---|"]
    for t in v["table"]:
        f = lambda z: f"{z:.1f}x" if z is not None else "n/a"
        prem = f"{t['premium_pct']:+.0f}%" if t["premium_pct"] is not None else "n/a"
        lines.append(f"| {t['metric']} | {f(t['ipo'])} | {f(t['peer_median'])} | {t['peers']} | {prem} |")
    if rep.get("rhp_peers"):
        lines.append("")
        lines.append("RHP-named peers (P/E as InvestIQ computes it today vs as stated in the RHP): " + ", ".join(
            f"{k} {('%.1fx' % d['investiq_pe']) if d['investiq_pe'] else 'n/a'} (RHP {d['rhp_pe']}x)" for k, d in rep["rhp_peers"].items()))
    lines += ["", f"**Verdict:** {v['wording']}"]
    h = rep.get("history")
    if h and h["n"]:
        def pc(d):
            return f"{d['median']:+.0%} median, {d['share_positive']:.0%} positive (n={d['n']})" if d["n"] else "n/a"
        lines.append(f"**History:** earlier IPOs with the same verdict ({h['n']}): listing-day gain {pc(h['list_gain_close'])}; "
                     f"12 months vs Smallcap 250 {pc(h['exc_12m'])}. All tested IPOs: listing gain median "
                     f"{h['all_ipos']['list_gain_close']['median']:+.0%}, 12m excess median {h['all_ipos']['exc_12m']['median']:+.0%}.")
    lines.append("**Key risks:** " + (" ".join(f"({i + 1}) {x}" for i, x in enumerate(rep["risks"])) or "none flagged"))
    lines.append(f"_{DISCLAIMER}_")
    return "\n".join(lines)


def run(recent=2):
    inputs = json.loads(INPUTS.read_text())["issues"]
    companies = ds.load_companies()
    companies["listing_date"] = pd.to_datetime(companies["listing_date"])
    stocks, index = load_prices()
    today = pd.Timestamp(date.today())
    panel = peers_now(companies, stocks, today)
    peer_date = str(panel["price_date"].max().date()) if len(panel) else None
    issues_df = pd.read_csv(ds.OUT_FILE, low_memory=False) if ds.OUT_FILE.exists() else None
    mkt = market_now(index, issues_df)
    reports = []
    for x in inputs:
        ipo = ipo_from_rhp(x)
        sector = companies.loc[companies["industry"] == x["industry"], "sector"].mode()
        peers, level = ds.peers_for(panel, x["industry"], sector.iloc[0] if len(sector) else None, -1)
        val = ipo_valuation(ipo, peers, today)
        named = {}
        for sym, rhp_pe in (x.get("rhp_peers") or {}).items():
            row = panel[panel["symbol"] == sym]
            ey = float(row["ey"].iloc[0]) if len(row) and pd.notna(row["ey"].iloc[0]) else None
            named[sym] = {"rhp_pe": rhp_pe, "investiq_pe": (1 / ey) if ey and ey > 0 else None}
        rep = {"symbol": x["symbol"], "company": x["company"], "status": f"open {x['issue_start']} to {x['issue_end']}",
               "price_band": x["price_band"], "fiscal": x["fiscal"], "industry": x["industry"], "peer_level": level,
               "peer_date": peer_date, "ipo_inputs": ipo, "valuation": val, "rhp_peers": named,
               "rhp_peer_avg_pe": x.get("rhp_peer_avg_pe"),
               "rhp_style_pe_pre_issue_eps": x["price_band"][1] / x["eps_basic_latest"],
               "peer_symbols_largest": peers.sort_values("mcap_cr", ascending=False)["symbol"].head(10).tolist(),
               "history": history(val["verdict"], val["loss_making"]), "market": mkt, "sources": x.get("sources")}
        rep["risks"] = risks(x, ipo, val, mkt)
        reports.append(rep)
    if recent and issues_df is not None:
        d = issues_df[issues_df["rel_median"].notna() & (issues_df["board"] == "mainboard")].copy()
        d["listing_date"] = pd.to_datetime(d["listing_date"])
        for r in d.sort_values("listing_date").tail(recent).itertuples():
            ipo = {"issue_price": r.issue_price, "shares_post": r.shares_post, "revenue_ann": r.revenue_ann,
                   "net_profit_ann": r.net_profit_ann, "equity": r.equity, "industry": r.co_industry}
            g = ds.peer_panel([pd.Timestamp(r.issue_start)], companies, stocks, cache=ds.PEER_FILE)
            g = g[g["signal_date"] == pd.Timestamp(r.issue_start)]
            peers, level = ds.peers_for(g, r.co_industry, r.co_sector, r.company_id)
            val = ipo_valuation(ipo, peers, r.issue_start)
            rep = {"symbol": r.symbol, "company": r.company,
                   "status": f"listed {r.listing_date.date()} (issue price Rs {r.issue_price:g}; listing-day close "
                             f"{r.list_gain_close:+.0%}); financials = XBRL proxy ({r.fin_basis}, {r.fin_months}m to "
                             f"{str(r.fin_period_end)[:10]}, filed {str(r.fin_filing_date)[:10]})",
                   "price_band": [r.issue_price, r.issue_price], "fiscal": "annualised XBRL proxy",
                   "industry": r.co_industry, "peer_level": level, "peer_date": str(pd.Timestamp(r.issue_start).date()),
                   "ipo_inputs": ipo, "valuation": val, "rhp_peers": {},
                   "history": history(val["verdict"], val["loss_making"]), "market": mkt}
            rep["risks"] = risks({}, {"issue_size_cr": None}, val, {})
            reports.append(rep)
    for rep in reports:
        print(render(rep))
        print()
    OUTPUT.write_text(json.dumps(reports, indent=1, default=str))
    print(f"wrote {OUTPUT}")
    return reports


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--recent", type=int, default=2)
    a = ap.parse_args(argv)
    run(a.recent)


if __name__ == "__main__":
    main()
