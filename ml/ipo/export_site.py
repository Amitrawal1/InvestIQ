"""Export the IPO study to one JSON file the website backend serves (backend/data/ipos.json).

Like the events study it ships as a static file instead of database tables:
    analyses     open / upcoming issues valued from their RHP figures, plus recently listed ones
                 (ipo/live.py -> live_output.json), with issue dates and business from live_inputs.json
    listings     main-board IPOs listed in the last LISTED_DAYS days: listing-day gain, QIB subscription,
                 valuation verdict at issue, returns vs NIFTY Smallcap 250 and the latest price vs issue price
    base_rates   what earlier IPOs did by verdict, QIB subscription, market conditions and loss-making
                 (eval.py's tables), and the headline test result (valuation and subscription did not
                 predict 6-12 month returns)

Re-run after `python3 -m ipo.dataset`, `python3 -m ipo.eval` and `python3 -m ipo.live`:
    cd ml && python3 -m ipo.export_site
"""

import json
import math
from datetime import date
from pathlib import Path

import pandas as pd

from growth_model.prices import load_prices

HERE = Path(__file__).resolve().parent
OUT = HERE.parent.parent / "backend" / "data" / "ipos.json"
LISTED_DAYS = 550
HORIZONS = ["1m", "3m", "6m", "12m"]
BUCKET_FIELDS = ["list_gain_close", "exc_6m", "exc_12m"]
VERDICT_LABELS = {
    "below": "Below peers", "in_line": "In line with peers", "above": "Above peers", "well_above": "Well above peers",
    "below_loss_making": "Below peers, loss-making", "in_line_loss_making": "In line, loss-making",
    "above_loss_making": "Above peers, loss-making", "well_above_loss_making": "Well above peers, loss-making",
    "insufficient_data": "Not enough data",
}


def _num(x, digits=4):
    if x is None:
        return None
    try:
        x = float(x)
    except (TypeError, ValueError):
        return None
    return None if math.isnan(x) or math.isinf(x) else round(x, digits)


def _str(x):
    return None if x is None or (isinstance(x, float) and math.isnan(x)) else str(x)


def _bucket_rows(rows):
    out = []
    for r in rows:
        row = {"bucket": r["bucket"], "n": int(r["n"])}
        for f in BUCKET_FIELDS:
            row[f] = {"n": int(r.get(f"{f}_n") or 0), "median": _num(r.get(f"{f}_median")),
                      "mean": _num(r.get(f"{f}_mean")), "hit": _num(r.get(f"{f}_hit"), 3)}
        out.append(row)
    return out


def _analyses():
    reports = json.loads((HERE / "live_output.json").read_text())
    inputs = {x["symbol"]: x for x in json.loads((HERE / "live_inputs.json").read_text())["issues"]}
    data = pd.read_csv(HERE / "ipo_dataset.csv", low_memory=False).drop_duplicates("symbol", keep="last").set_index("symbol")
    out = []
    for r in reports:
        x = inputs.get(r["symbol"], {})
        d = data.loc[r["symbol"]] if r["symbol"] in data.index else None
        v = r["valuation"]
        ipo = r.get("ipo_inputs") or {}
        listed = r["status"].startswith("listed")
        out.append({
            "symbol": r["symbol"], "company": r["company"], "business": x.get("business"),
            "board": x.get("board", "mainboard"),
            "issue_start": x.get("issue_start") or (_str(d["issue_start"]) if d is not None else None),
            "issue_end": x.get("issue_end") or (_str(d["issue_end"]) if d is not None else None),
            "listing_date": _str(d["listing_date"]) if d is not None and listed else None,
            "price_band": r["price_band"], "issue_size_cr": _num(ipo.get("issue_size_cr"), 1),
            "ofs_share": _num(ipo.get("ofs_share"), 3),
            "list_gain_close": _num(d["list_gain_close"]) if d is not None and listed else None,
            "sub_qib": _num(d["sub_qib"], 2) if d is not None else None,
            "sub_total": _num(d["sub_total"], 2) if d is not None else None,
            "fiscal": r["fiscal"], "fin_source": "xbrl_proxy" if listed else "rhp",
            "industry": r["industry"], "peer_level": r["peer_level"], "peer_date": r["peer_date"],
            "mcap_cr": _num(v.get("mcap_cr"), 1), "loss_making": bool(v.get("loss_making")),
            "n_peers": v.get("n_peers"),
            "table": [{"metric": t["metric"], "ipo": _num(t["ipo"], 2), "peer_median": _num(t["peer_median"], 2),
                       "peers": t["peers"], "premium_pct": _num(t["premium_pct"], 1)} for t in v["table"]],
            "verdict": v["verdict"], "verdict_label": VERDICT_LABELS.get(v["verdict"], v["verdict"]),
            "wording": v["wording"],
            "rhp_peers": [{"symbol": k, "rhp_pe": _num(p["rhp_pe"], 2), "investiq_pe": _num(p["investiq_pe"], 2)}
                          for k, p in (r.get("rhp_peers") or {}).items()],
            "rhp_peer_avg_pe": _num(r.get("rhp_peer_avg_pe"), 2),
            "rhp_style_pe": _num(r.get("rhp_style_pe_pre_issue_eps"), 2),
            "largest_peers": r.get("peer_symbols_largest") or [],
            "history": r.get("history"), "risks": r.get("risks") or [], "sources": r.get("sources"),
            "rhp_url": _str(d["rhp_url"]) if d is not None and "rhp_url" in d else None,
        })
    market = reports[0]["market"] if reports else None
    return out, market


def _listings():
    d = pd.read_csv(HERE / "ipo_dataset.csv", low_memory=False)
    d = d[(d["board"] == "mainboard") & ~d["is_fpo"].astype(bool) & d["listing_date"].notna()].copy()
    d["listing_date"] = pd.to_datetime(d["listing_date"])
    d = d[d["listing_date"] >= pd.Timestamp(date.today()) - pd.Timedelta(days=LISTED_DAYS)]
    stocks, _ = load_prices()
    stocks = stocks[stocks["company_id"].isin(d["company_id"].dropna().astype(int))]
    last = {}
    for cid, g in stocks.groupby("company_id"):
        g = g.sort_values("price_date")
        last[int(cid)] = g
    out = []
    for r in d.sort_values("listing_date", ascending=False).itertuples():
        now = None
        if not pd.isna(r.company_id) and int(r.company_id) in last and not pd.isna(r.list_gain_close):
            g = last[int(r.company_id)]
            g = g[g["price_date"] >= r.listing_date]
            if len(g) and (g["price_date"].iloc[0] - r.listing_date).days <= 7:
                # adjusted series from the listing-day close, chained onto the unadjusted listing gain
                now = {"date": str(g["price_date"].iloc[-1].date()),
                       "vs_issue": _num((1 + r.list_gain_close) * float(g["close"].iloc[-1]) / float(g["close"].iloc[0]) - 1)}
        out.append({
            "symbol": r.symbol, "company": r.company, "site_symbol": _str(r.co_symbol),
            "industry": _str(r.co_industry), "sector": _str(r.co_sector),
            "issue_start": _str(r.issue_start), "listing_date": str(r.listing_date.date()),
            "issue_price": _num(r.issue_price, 2), "issue_size_text": _str(r.issue_size_text),
            "sub_qib": _num(r.sub_qib, 2), "sub_total": _num(r.sub_total, 2),
            "list_gain_close": _num(r.list_gain_close),
            "verdict": _str(r.verdict), "verdict_label": VERDICT_LABELS.get(r.verdict) if isinstance(r.verdict, str) else None,
            "fin_basis": _str(r.fin_basis),
            "vs_peers": {k: _num(math.exp(v) - 1, 3) if not pd.isna(v) else None
                         for k, v in (("pe", r.rel_pe), ("pb", r.rel_pb), ("ps", r.rel_ps))},
            "exc": {h: _num(getattr(r, f"exc_{h}")) for h in HORIZONS},
            "now": now,
        })
    return out


def _base_rates():
    ev = json.loads((HERE / "eval_results.json").read_text())
    s = pd.read_csv(HERE / "eval_sample.csv")
    overall = {f: {"n": int(s[f].notna().sum()), "median": _num(s[f].median()), "mean": _num(s[f].mean()),
                   "hit": _num((s[f].dropna() > 0).mean(), 3)} for f in BUCKET_FIELDS}
    dg = ev["diagnostics"]
    tests = {}
    for k, label in (("VAL", "Cheapness vs peers"), ("SUB", "QIB subscription"), ("COMBO", "Both combined")):
        t = ev[k]
        tests[k] = {"label": label, "pass": bool(t["pass_rule"]["pass"]),
                    "ic": {h: _num(t["ic"][h]["ic"], 3) for h in ("list_gain_close", "exc_6m", "exc_12m")},
                    "terciles": _bucket_rows(t["terciles"])}
    return {
        "sample": ev["sample"], "overall": overall, "tests": tests,
        "verdict": _bucket_rows(dg["verdict_buckets"]),
        "qib": _bucket_rows(dg["qib_buckets_all_mainboard"]),
        "market": _bucket_rows(dg["market_drawdown_buckets_all_mainboard"]),
        "loss_making": _bucket_rows(dg["loss_making"]),
        "summary": ("Comparing an IPO's price with listed peers describes it consistently, but on 2018-2026 history it "
                    "did not predict returns after listing: IPOs priced cheaply against peers did not beat dearly "
                    "priced ones over 6 or 12 months. Heavy QIB subscription strongly predicted a bigger listing-day "
                    "gain, but not returns after that. The median IPO trailed the Smallcap 250 by about 16% over its "
                    "first year."),
    }


def main():
    analyses, market = _analyses()
    data = {
        "built_from": "ml/ipo (dataset.py, eval.py, live.py)", "as_of": str(date.today()),
        "source_note": "Issue data: NSE. Pre-IPO financials: the issuer's Red Herring Prospectus. Peer prices: "
                       "InvestIQ database. Ratios and verdicts are InvestIQ's own calculations.",
        "disclaimer": ("InvestIQ is not a SEBI-registered investment adviser or research analyst. This compares the issue "
                       "price with listed companies and shows what earlier IPOs did; it is not a recommendation to "
                       "apply, buy or sell."),
        "market": market, "analyses": analyses, "listings": _listings(), "base_rates": _base_rates(),
        "verdict_labels": VERDICT_LABELS,
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(data, separators=(",", ":"), default=str))
    print(f"wrote {OUT} ({OUT.stat().st_size / 1e3:.0f} KB): {len(analyses)} analyses, {len(data['listings'])} listings")


if __name__ == "__main__":
    main()
