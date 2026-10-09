"""Build ml/ipo/ipo_dataset.csv: one row per NSE main-board (and SME) IPO since 2016 with issue data,
subscription, listing-day prices, the company's own financials, valuation vs listed peers at the
issue date, market conditions and post-listing outcomes.

Inputs: raw NSE downloads (ipo/sources.py, cached under ml/data/raw/ipo/), the `companies` table
(SELECT), the price caches (growth_model/prices.py) and the XBRL filing caches (financial_raw.pkl,
valuation_equity_raw.pkl via ml/valuation/features.py). DB: SELECT only.

Key definitions
---------------
D (valuation date)  issue OPEN date: peers are priced at their last close strictly before D and use
                    financials filed on or before D (valuation/features.py point-in-time rules);
                    the IPO price band is fixed a few days before D, so nothing after D enters.
IPO market cap      issue price x post-issue shares. Shares: (1) NSE MCAP file on the listing day
                    (exact; 2024+), else (2) net profit / basic EPS of the first quarter that starts
                    after listing (weighted shares of a full post-issue quarter = post-issue count;
                    the count is fixed by the issue, so this is a measurement proxy, not information
                    about the business; validated against (1) where both exist), else (3) the same
                    ratio on the last pre-listing quarter (PRE-issue count: understates a fresh issue).
IPO financials      NOT the RHP (offer documents are 300-600 page PDFs; not parsed systematically).
                    Proxy, flagged in `fin_basis`:
                      pre_listing  latest period that ENDED BEFORE listing, from the company's first
                                   XBRL results after listing (year-to-date block preferred, annualised
                                   x 12/months). The period is pre-issue, but the numbers became public
                                   only at `fin_filing_date` (typically 2-8 weeks after listing): the
                                   RHP had the same business up to a few months earlier.
                      post_listing first period ending after listing (bigger look-ahead; research only,
                                   excluded from the pre-declared test)
                    Equity: first balance sheet on or after listing (post-issue book, includes the
                    fresh money), within 400 days.
Peers               same `companies.industry` (InvestIQ's 38 industries, today's labels); fewer than
                    5 peers with the multiple -> same sector. Banks / NBFCs / insurers are outside the
                    peer panel (non_financial filings only) and get no valuation.
Outcomes            from the listing-day close (adjusted series in `stock_prices`): 1m/3m/6m/12m =
                    21/63/126/252 trading days, minus NIFTY SMALLCAP 250 over the same days
                    (`exc_*`). `pit_exc_*`: the same but entering at the first close after
                    `fin_filing_date` when that is later (strictly point-in-time variant).
                    A one-day move > +100% / < -60% inside a window is a data break: outcome dropped.
Listing gain        listing-day close (and open) vs issue price, unadjusted NSE bhavcopy.
Market conditions   Smallcap 250 drawdown from its 252-day high and 3-month return at D; number of
                    main-board IPOs listed in the 90 days before D and their median listing gain.

CLI (from ml/):  python3 -m ipo.dataset
"""

import argparse
import json
import math
import warnings
from pathlib import Path

import numpy as np
import pandas as pd

from growth_model.prices import BENCHMARK, load_prices

from . import sources as src
from .valuation import ipo_valuation

warnings.filterwarnings("ignore", message="pandas only supports SQLAlchemy")

PKG_DIR = Path(__file__).resolve().parent
OUT_FILE = PKG_DIR / "ipo_dataset.csv"
PEER_FILE = src.RAW_DIR / "peer_panel.pkl"
HORIZONS = {"1m": 21, "3m": 63, "6m": 126, "12m": 252}
BREAK_UP, BREAK_DOWN = 1.0, -0.6
EQUITY_MAX_DAYS = 400
PEER_MIN = 5
PEER_START = pd.Timestamp("2017-10-01")   # XBRL filings (peer financials) start late 2017
PEER_PRICE_MAX_AGE = 10          # days: a peer whose last close is older is not priced at D


# ---------------------------------------------------------
# Loading
# ---------------------------------------------------------

def load_companies():
    from news_pipeline.db import get_connection

    conn = get_connection()
    try:
        return pd.read_sql(
            "SELECT c.id AS company_id, c.symbol, c.name, c.isin, c.series, c.listing_date, c.industry, "
            "s.name AS sector FROM companies c LEFT JOIN sectors s ON s.id = c.sector_id", conn)
    finally:
        conn.close()


def load_issues():
    issues = src.load_past()
    issues = issues[issues["security_type"].isin(src.MAINBOARD + src.SME)].copy()
    issues["board"] = np.where(issues["security_type"] == "SME", "sme", "mainboard")
    det = []
    for r in issues.itertuples():
        d = src.parse_detail(r.symbol, "SME" if r.board == "sme" else "EQ")
        d["symbol"], d["security_type"] = r.symbol, r.security_type
        det.append(d)
    det = pd.DataFrame(det).drop_duplicates(["symbol", "security_type"])
    issues = issues.merge(det, on=["symbol", "security_type"], how="left")
    if src.LISTING_FILE.exists():
        lst = pd.read_csv(src.LISTING_FILE, parse_dates=["listing_date"]).drop_duplicates(["symbol", "listing_date"])
        issues = issues.merge(lst, on=["symbol", "listing_date"], how="left")
    text = issues["issue_size_text"].fillna("").str.lower()
    issues["is_fpo"] = text.str.contains("further public offer|follow-on|follow on public", regex=True)
    return issues.reset_index(drop=True)


def match_companies(issues, companies):
    """company_id by ISIN issuer prefix (first 9 chars survive splits / renames), then symbol."""
    c = companies.copy()
    c["isin9"] = c["isin"].str[:9]
    by_isin = c.dropna(subset=["isin9"]).drop_duplicates("isin9").set_index("isin9")["company_id"]
    by_sym = c.drop_duplicates("symbol").set_index("symbol")["company_id"]
    isin = issues["bhav_isin"].fillna(issues["isin"]) if "bhav_isin" in issues else issues["isin"]
    cid = isin.str[:9].map(by_isin)
    cid = cid.fillna(issues["symbol"].map(by_sym))
    issues["company_id"] = cid
    issues["isin_any"] = isin
    info = c.set_index("company_id")[["symbol", "industry", "sector", "listing_date", "series"]].add_prefix("co_")
    return issues.merge(info, left_on="company_id", right_index=True, how="left")


# ---------------------------------------------------------
# Prices: adjustment factor, outcomes, market conditions
# ---------------------------------------------------------

def outcomes(issues, stocks, index):
    bench = index[index["index_key"] == BENCHMARK].set_index("price_date")["close"].sort_index()
    bdates = bench.index
    groups = {cid: g.set_index("price_date")["close"].sort_index()
              for cid, g in stocks[stocks["company_id"].isin(issues["company_id"].dropna().astype(int))].groupby("company_id")}
    rows = []
    for r in issues.itertuples():
        out = {}
        s = groups.get(int(r.company_id)) if not pd.isna(r.company_id) else None
        if s is None or pd.isna(r.listing_date):
            rows.append(out)
            continue
        s = s[s.index >= r.listing_date]
        if len(s) == 0 or (s.index[0] - r.listing_date).days > 7:
            rows.append(out)
            continue
        first_close = float(s.iloc[0])
        out["db_first_date"] = s.index[0]
        if not pd.isna(getattr(r, "list_close", np.nan)) and r.list_close > 0:
            out["adj_factor"] = first_close / r.list_close
        rets = s.pct_change()
        for entry_kind, entry_date in (("", s.index[0]), ("pit_", getattr(r, "fin_filing_date", pd.NaT))):
            if entry_kind == "pit_":
                if pd.isna(entry_date):
                    continue
                entry_date = max(pd.Timestamp(entry_date).normalize() + pd.Timedelta(days=1), s.index[0])
            pos = bdates.searchsorted(entry_date)
            if pos >= len(bdates):
                continue
            b0d = bdates[pos]
            if b0d not in s.index:
                sx = s[s.index >= b0d]
                if len(sx) == 0 or (sx.index[0] - b0d).days > 7:
                    continue
                b0d_s = sx.index[0]
            else:
                b0d_s = b0d
            p0, i0 = float(s.loc[b0d_s]), float(bench.loc[b0d])
            for h, n in HORIZONS.items():
                if entry_kind == "pit_" and h in ("1m",):
                    continue
                if pos + n >= len(bdates):
                    continue
                e = bdates[pos + n]
                se = s[s.index <= e]
                if len(se) == 0 or (e - se.index[-1]).days > 30:
                    continue          # stopped trading long before the horizon: unknown, not 0
                win = rets[(rets.index > b0d_s) & (rets.index <= e)]
                if ((win > BREAK_UP) | (win < BREAK_DOWN)).any():
                    out[f"{entry_kind}break_{h}"] = True
                    continue
                rs = float(se.iloc[-1]) / p0 - 1
                rb = float(bench.loc[e]) / i0 - 1
                out[f"{entry_kind}ret_{h}"] = rs
                out[f"{entry_kind}bench_{h}"] = rb
                out[f"{entry_kind}exc_{h}"] = rs - rb
        rows.append(out)
    return pd.concat([issues.reset_index(drop=True), pd.DataFrame(rows)], axis=1)


def market_conditions(issues, index):
    bench = index[index["index_key"] == BENCHMARK].set_index("price_date")["close"].sort_index()
    hi = bench.rolling(252, min_periods=120).max()
    main = issues[(issues["board"] == "mainboard") & ~issues["is_fpo"]]
    out = []
    for r in issues.itertuples():
        D = r.issue_start
        b = bench[bench.index < D]
        o = {}
        if len(b) > 63:
            o["sc250_drawdown"] = float(b.iloc[-1] / hi[b.index[-1]] - 1)
            o["sc250_ret_3m"] = float(b.iloc[-1] / b.iloc[-64] - 1)
        prior = main[(main["listing_date"] < D) & (main["listing_date"] >= D - pd.Timedelta(days=90))]
        o["ipos_prior_90d"] = int(len(prior))
        g = prior["list_gain_close"].dropna()
        o["prior_90d_median_list_gain"] = float(g.median()) if len(g) >= 3 else np.nan
        out.append(o)
    return pd.concat([issues.reset_index(drop=True), pd.DataFrame(out)], axis=1)


# ---------------------------------------------------------
# The IPO company's own financials (XBRL proxy) and post-issue shares
# ---------------------------------------------------------

def _best_rows(raw):
    r = raw[raw["company_id"].notna()].copy()
    r["company_id"] = r["company_id"].astype(int)
    r["pref"] = (r["statement_type"] != "consolidated").astype(int) * 2 + (r["parse_status"] != "ok").astype(int)
    r = r.sort_values(["company_id", "period_end", "pref", "filing_date"])
    return r.groupby(["company_id", "period_end"], as_index=False).first()


def _annual(row):
    """Annualised (revenue, profit to owners, months, block) of a filing row: YTD block preferred."""
    for blk, mcol in (("ytd_", "ytd_months"), ("inc_", "months")):
        months = row.get(mcol)
        rev = row.get(f"{blk}revenue")
        prof = row.get(f"{blk}net_profit_owners")
        if prof is None or pd.isna(prof):
            prof = row.get(f"{blk}net_profit")
        if months and not pd.isna(months) and months in (3, 6, 9, 12) and not pd.isna(rev) and not pd.isna(prof):
            k = 12.0 / months
            return rev * k, prof * k, int(months), blk.rstrip("_")
    return None


def _shares(row):
    for blk, mcol in (("inc_", "months"), ("ytd_", "ytd_months")):
        p = row.get(f"{blk}net_profit_owners")
        if p is None or pd.isna(p):
            p = row.get(f"{blk}net_profit")
        e = row.get(f"{blk}eps_basic")
        if p is None or e is None or pd.isna(p) or pd.isna(e):
            continue
        if abs(e) >= 0.05 and abs(p) >= 0.5 and np.sign(e) == np.sign(p):
            s = p / e
            if 0.01 < s < 5000:
                return s
    return None


def own_financials(issues, raw, eq_raw):
    best = _best_rows(raw)
    by_c = {cid: g.sort_values("period_end") for cid, g in best.groupby("company_id")}
    e = eq_raw.copy()
    e["equity"] = e["bs_equity_owners"].fillna(e["bs_total_equity"] - e["bs_non_controlling_interest"]).fillna(e["bs_total_equity"])
    e = e[e["equity"].notna()].copy()
    e["company_id"] = e["company_id"].astype(int)
    e["pref"] = (e["statement_type"] != "consolidated").astype(int)
    e = e.sort_values(["company_id", "period_end", "pref", "filing_date"]).groupby(["company_id", "period_end"], as_index=False).first()
    eq_by_c = {cid: g.sort_values("period_end") for cid, g in e.groupby("company_id")}
    rows = []
    for r in issues.itertuples():
        o = {}
        if pd.isna(r.company_id) or pd.isna(r.listing_date):
            rows.append(o)
            continue
        g = by_c.get(int(r.company_id))
        L = r.listing_date
        if g is not None:
            pre = g[g["period_end"] < L]
            # a pre-listing period filed long after listing is not a "first results" filing
            pre = pre[pre["filing_date"] <= L + pd.Timedelta(days=200)]
            post = g[g["period_end"] >= L]
            chosen, basis = None, None
            for cand in reversed(list(pre.itertuples(index=False))):
                a = _annual(cand._asdict())
                if a:
                    chosen, basis = (cand, a), "pre_listing"
                    break
            if chosen is None:
                for cand in post.itertuples(index=False):
                    a = _annual(cand._asdict())
                    if a:
                        chosen, basis = (cand, a), "post_listing"
                        break
            if chosen:
                cand, (rev, prof, months, blk) = chosen
                o.update({"fin_basis": basis, "fin_period_end": cand.period_end, "fin_filing_date": cand.filing_date,
                          "fin_months": months, "fin_block": blk, "fin_statement": cand.statement_type,
                          "revenue_ann": rev, "net_profit_ann": prof, "fin_format": cand.format})
            # post-issue shares: first quarter wholly after listing (period_end >= listing + ~3 months)
            full = g[g["period_end"] >= L + pd.Timedelta(days=88)]
            for cand in full.itertuples(index=False):
                s = _shares(cand._asdict())
                if s:
                    o.update({"xbrl_shares_post": s, "xbrl_shares_period": cand.period_end})
                    break
            for cand in reversed(list(pre.itertuples(index=False))):
                s = _shares(cand._asdict())
                if s:
                    o.update({"xbrl_shares_pre": s})
                    break
        ge = eq_by_c.get(int(r.company_id))
        if ge is not None:
            ge = ge[(ge["period_end"] >= L - pd.Timedelta(days=1)) & (ge["period_end"] <= L + pd.Timedelta(days=EQUITY_MAX_DAYS))]
            if len(ge):
                o.update({"equity": float(ge.iloc[0]["equity"]), "equity_period_end": ge.iloc[0]["period_end"],
                          "equity_filing_date": ge.iloc[0]["filing_date"]})
        rows.append(o)
    out = pd.concat([issues.reset_index(drop=True), pd.DataFrame(rows)], axis=1)
    mc = out["mcap_shares"] / 1e7 if "mcap_shares" in out else pd.Series(np.nan, index=out.index)
    # XBRL share estimates are in the period's basis; a split between listing and that quarter would
    # show up as a ratio vs the MCAP count / pre-issue count; such cases are rare and left as is.
    out["shares_post"] = mc.fillna(out.get("xbrl_shares_post")).fillna(out.get("xbrl_shares_pre"))
    out["shares_source"] = np.where(mc.notna(), "nse_mcap",
                                    np.where(out.get("xbrl_shares_post").notna(), "xbrl_post_quarter",
                                             np.where(out.get("xbrl_shares_pre").notna(), "xbrl_pre_issue", None)))
    return out


# ---------------------------------------------------------
# Peer panel (point-in-time, valuation/features.py)
# ---------------------------------------------------------

def peer_panel(dates, companies, stocks, refresh=False, cache=PEER_FILE):
    """Every non-financial listed company priced on each date (close strictly before D) with
    point-in-time mcap / ey / bp / sp from valuation.features.add_valuation."""
    if cache is not None and cache.exists() and not refresh:
        p = pd.read_pickle(cache)
        if set(pd.to_datetime(dates)) <= set(p["signal_date"].unique()):
            return p
    from financial_model.data import asof_join, load_feature_table
    from valuation import features as vf

    features, raw = load_feature_table()
    dates = sorted(set(pd.to_datetime(dates)))
    cids = stocks["company_id"].unique()
    keys = pd.DataFrame([(c, d) for d in dates for c in cids], columns=["company_id", "signal_date"])
    keys["px_date"] = keys["signal_date"] - pd.Timedelta(days=1)
    st = stocks[["company_id", "price_date", "close"]].sort_values("price_date")
    keys = pd.merge_asof(keys.sort_values("px_date"), st, left_on="px_date", right_on="price_date",
                         by="company_id", direction="backward")
    keys = keys[keys["close"].notna() & ((keys["px_date"] - keys["price_date"]).dt.days <= PEER_PRICE_MAX_AGE)]
    keys = keys.rename(columns={"close": "close_d"}).drop(columns=["px_date"])
    panel = asof_join(keys, features)
    panel = panel[~panel["fin_stale"]].reset_index(drop=True)
    panel, _ = vf.add_valuation(panel, sectors=None, raw=raw, with_own=False)
    keep = ["company_id", "signal_date", "price_date", "close_d", "mcap_cr", "ey", "bp", "sp", "period_end", "filing_date"]
    panel = panel[keep].merge(companies[["company_id", "symbol", "industry", "sector", "listing_date"]],
                              on="company_id", how="left")
    if cache is not None:
        panel.to_pickle(cache)
    return panel


def peers_for(panel_d, industry, sector, exclude_cid):
    p = panel_d[panel_d["company_id"] != exclude_cid]
    p = p.assign(pe=(1 / p["ey"]).where(p["ey"] > 0), pb=(1 / p["bp"]).where(p["bp"] > 0),
                 ps=(1 / p["sp"]).where(p["sp"] > 0))
    ind = p[p["industry"] == industry] if isinstance(industry, str) else p.iloc[0:0]
    if ind["pe"].notna().sum() >= PEER_MIN and ind["ps"].notna().sum() >= PEER_MIN:
        return ind, "industry"
    sec = p[p["sector"] == sector] if isinstance(sector, str) else p.iloc[0:0]
    return sec, "sector"


def add_peer_valuation(issues, panel):
    by_d = {d: g for d, g in panel.groupby("signal_date")}
    rows = []
    for r in issues.itertuples():
        o = {}
        g = by_d.get(r.issue_start)
        fin_ok = getattr(r, "fin_format", None) == "non_financial"
        if g is None or not fin_ok or pd.isna(r.issue_price):
            rows.append(o)
            continue
        peers, level = peers_for(g, r.co_industry, r.co_sector, r.company_id)
        ipo = {"issue_price": r.issue_price, "shares_post": r.shares_post, "revenue_ann": r.revenue_ann,
               "net_profit_ann": r.net_profit_ann, "equity": r.equity, "industry": r.co_industry}
        v = ipo_valuation(ipo, peers, r.issue_start)
        o = {k: v[k] for k in v if k not in ("table", "wording", "date")}
        o["peer_level"] = level
        o["peer_symbols"] = ",".join(peers.sort_values("mcap_cr", ascending=False)["symbol"].dropna().head(8))
        rows.append(o)
    return pd.concat([issues.reset_index(drop=True), pd.DataFrame(rows)], axis=1)


# ---------------------------------------------------------

def build(refresh_peers=False):
    companies = load_companies()
    companies["listing_date"] = pd.to_datetime(companies["listing_date"])
    issues = load_issues()
    issues = match_companies(issues, companies)
    # FPOs and re-issues of already listed companies are not IPOs
    old = issues["co_listing_date"].notna() & (issues["co_listing_date"] < issues["issue_start"] - pd.Timedelta(days=30))
    issues["is_fpo"] = issues["is_fpo"] | (old & issues["list_close"].isna())
    issues["list_gain_close"] = issues["list_close"] / issues["issue_price"] - 1
    issues["list_gain_open"] = issues["list_open"] / issues["issue_price"] - 1
    # sanity: bhavcopy PREVCLOSE on listing day is the issue price (catches symbol mix-ups)
    issues["issue_price_check"] = (issues["list_prev_close"] / issues["issue_price"]).round(3)
    # listing-day previous close far from the issue price: an already-traded share (BSE-first listing,
    # demerger, partly-paid rights) whose "issue" is not an IPO price discovery -> treated like an FPO
    issues["is_fpo"] = issues["is_fpo"] | ((issues["issue_price_check"] - 1).abs() > 0.02)
    issues = issues.drop_duplicates(["symbol", "listing_date"], keep="last").reset_index(drop=True)
    stocks, index = load_prices()
    from valuation import features as vf

    raw = vf.load_raw()
    eq_raw = vf.load_equity_raw()
    issues = own_financials(issues, raw, eq_raw)
    issues = outcomes(issues, stocks, index)
    issues = market_conditions(issues, index)
    dates = issues.loc[(issues["board"] == "mainboard") & issues["issue_start"].notna()
                       & (issues["issue_start"] >= PEER_START), "issue_start"].unique()
    panel = peer_panel(dates, companies, stocks, refresh=refresh_peers)
    issues = add_peer_valuation(issues, panel)
    issues["listing_year"] = issues["listing_date"].dt.year
    issues = issues.sort_values(["issue_start", "symbol"]).reset_index(drop=True)
    issues.to_csv(OUT_FILE, index=False)
    return issues


def coverage(df):
    d = df[~df["is_fpo"]]
    g = d.groupby([d["issue_end"].dt.year.rename("year"), "board"])
    cov = g.agg(issues=("symbol", "size"), listed=("list_close", lambda s: s.notna().sum()),
                subscription=("sub_total", lambda s: s.notna().sum()),
                matched=("company_id", lambda s: s.notna().sum()),
                fin_pre=("fin_basis", lambda s: (s == "pre_listing").sum()),
                fin_post=("fin_basis", lambda s: (s == "post_listing").sum()),
                shares=("shares_post", lambda s: s.notna().sum()),
                valuation=("rel_median", lambda s: s.notna().sum()),
                exc_12m=("exc_12m", lambda s: s.notna().sum()))
    return cov


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--refresh-peers", action="store_true")
    a = ap.parse_args(argv)
    df = build(refresh_peers=a.refresh_peers)
    pd.set_option("display.width", 200)
    print(coverage(df).to_string())
    print(f"wrote {OUT_FILE} ({len(df)} rows)")


if __name__ == "__main__":
    main()
