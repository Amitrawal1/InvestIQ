"""Event study: how did sectors, industries and themes move after major market events (2016 ->)?

Inputs (read-only):
    ml/events/events.csv                     curated events (see REPORT.md)
    growth_model.prices.load_prices()        daily closes/volumes (cached pickle; DB SELECT on refresh)
    companies / sectors / industries         DB SELECT (cached to data/processed/events_companies.pkl)

Timing (no look-ahead):
    event time      date + time_ist (HH:MM IST, 'pre_open', 'after_close', or blank = unknown)
    entry day E     the first trading day whose close is AFTER the event became public:
                    same day if the date is a trading day and the event was public before 15:30 IST
                    (pre_open or a time < 15:30); otherwise the next trading day. Unknown time -> next
                    trading day (conservative).
    reference R     the last close before the event (used only for the day-0 "reaction", which you
                    could NOT have traded; it is reported to show how much was priced in at once)
    horizons        E -> E + h trading days, h = 5, 21, 63, 126 (1 week, 1 month, 3 months, 6 months)

Stock filters at E (same spirit as growth_model.labels / rankings.time_machine):
    >= 120 trading days of prices before E, close >= Rs 1, median traded value over the previous
    60 days >= Rs 0.5 crore/day (the Top-list liquidity rule), no data break (one-day move > +100%
    or < -60%) inside (E, E+h], exit close within 5 days of E+h (else excluded, see survivorship).
    Returns are winsorised at the 1st/99th percentile of each day's cross-section.

Group return = equal-weight mean of eligible member stocks (>= 5 members, else NaN). Measures:
    excess_sc  group return - NIFTY SMALLCAP 250 return      (the spec's benchmark)
    excess_n50 group return - NIFTY 50 return
    rel        group return - equal-weight mean of ALL eligible stocks ("rotation": removes the
               common move every group shares, so it isolates which sectors did better than others)
    abn_vol    median over members of (mean volume E..E+4) / (median volume E-65..E-6)

Known biases: survivorship (stock_prices only has companies listed today; delisted names are
missing), current sector labels applied to the past, overlapping events (e.g. 2022 rate hikes).

CLI:
    cd ml && python3 -m events.event_study            # build panel + event returns + playbooks
    cd ml && python3 -m events.event_study --refresh  # re-pull company sectors from the DB
Writes ml/events/results/*.csv and data/processed/events_panel.pkl (local cache, git-ignored).
"""

import argparse
import time
from pathlib import Path

import numpy as np
import pandas as pd

from growth_model.prices import BENCHMARK, CACHE_DIR, load_prices

HERE = Path(__file__).resolve().parent
RESULTS = HERE / "results"
EVENTS_CSV = HERE / "events.csv"
COMPANY_CACHE = CACHE_DIR / "events_companies.pkl"
PANEL_CACHE = CACHE_DIR / "events_panel.pkl"

NIFTY50 = "NSE_INDEX|Nifty 50"
HORIZONS = {"5d": 5, "21d": 21, "63d": 63, "126d": 126}
MARKET_CLOSE = "15:30"
MIN_HISTORY = 120
MIN_PRICE = 1.0
MIN_ADV = 0.5e7          # Rs 0.5 crore a day
STALE = 5
BREAK_UP, BREAK_DOWN = 1.0, -0.6
MIN_MEMBERS = 5
WINSOR = (0.01, 0.99)

# Hand-curated thematic baskets (by line of business, not by past returns). The DB industry labels
# put e.g. HAL under Aviation and BEL under Engineering, so a "defence" view needs a basket.
THEMES = {
    "Defence": "HAL BEL BDL MAZDOCK COCHINSHIP GRSE BEML DATAPATTNS MIDHANI PARAS ASTRAMICRO SOLARINDS ZENTEC MTARTECH",
    "PSU banks": "SBIN PNB BANKBARODA CANBK UNIONBANK INDIANB BANKINDIA CENTRALBK IOB UCOBANK MAHABANK PSB",
    "Oil marketing (OMCs)": "BPCL IOC HINDPETRO",
    "Upstream oil & gas": "ONGC OIL",
    "Sugar & ethanol": "BALRAMCHIN TRIVENI DWARKESH DHAMPURSUG BAJAJHIND RENUKA AVADHSUGAR MAGADSUGAR DALMIASUG",
    "Rice exporters": "KRBL LTFOODS",
    "Capital-market intermediaries": "BSE CDSL ANGELONE MCX CAMS KFINTECH MOTILALOFS NUVAMA",
    "Gaming": "NAZARA DELTACORP",
    "Steel & iron ore": "TATASTEEL JSWSTEEL SAIL JINDALSTEL NMDC",
    "Telecom operators": "IDEA BHARTIARTL INDUSTOWER",
    "Automakers": "M&M MARUTI HEROMOTOCO BAJAJ-AUTO TVSMOTOR EICHERMOT OLECTRA",
    "Cement": "ULTRACEMCO SHREECEM ACC AMBUJACEM DALBHARAT RAMCOCEM JKCEMENT",
    "Real estate developers": "DLF GODREJPROP OBEROIRLTY LODHA PRESTIGE PHOENIXLTD",
    "Retail NBFCs & HFCs": "BAJFINANCE SHRIRAMFIN CHOLAFIN MUTHOOTFIN MANAPPURAM LICHSGFIN PNBHOUSING",
    "Power PSUs & lenders": "NTPC POWERGRID NHPC SJVN PFC RECLTD IRFC IREDA",
    "Renewables": "TATAPOWER ADANIGREEN SUZLON INOXWIND WAAREEENER PREMIERENE BORORENEW KPIGREEN",
    "Infra & rail EPC": "LT IRB KNRCON PNCINFRA NCC RVNL IRCON KEC HGINFRA",
    "Pharma majors": "SUNPHARMA DRREDDY CIPLA LUPIN AUROPHARMA ZYDUSLIFE GLENMARK BIOCON ALKEM TORNTPHARM DIVISLAB",
}
THEME_MIN_MEMBERS = 2


# ----------------------------------------------------------------------------------------- inputs

def load_events(path=EVENTS_CSV):
    ev = pd.read_csv(path, dtype=str, keep_default_na=False)
    ev["date"] = pd.to_datetime(ev["date"])
    return ev


def load_companies(refresh=False):
    """company_id, symbol, sector, industry (DB SELECT, cached)."""
    if COMPANY_CACHE.exists() and not refresh:
        return pd.read_pickle(COMPANY_CACHE)
    from news_pipeline.db import get_connection
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute("""SELECT c.id, c.symbol, c.name, s.name, i.name FROM companies c
                       LEFT JOIN sectors s ON s.id = c.sector_id
                       LEFT JOIN industries i ON i.id = c.industry_id""")
        df = pd.DataFrame(cur.fetchall(), columns=["company_id", "symbol", "name", "sector", "industry"])
    finally:
        conn.close()
    df.to_pickle(COMPANY_CACHE)
    return df


def entry_and_ref(date, time_ist, cal):
    """-> (entry day E, reference day R) on the trading calendar `cal` (sorted DatetimeIndex)."""
    on_trading_day = date in cal
    t = (time_ist or "").strip()
    before_close = t == "pre_open" or (len(t) == 5 and t[2] == ":" and t < MARKET_CLOSE)
    after_close = t == "after_close" or (len(t) == 5 and t[2] == ":" and t >= MARKET_CLOSE)
    nxt = cal.searchsorted(date, side="right")
    prev = cal.searchsorted(date, side="left") - 1
    if on_trading_day and before_close:
        e = date                                        # public during/before the session
    else:
        e = cal[nxt] if nxt < len(cal) else None        # after close, holiday, or unknown time
    if on_trading_day and after_close:
        r = date                                        # that day's close was before the news
    else:
        r = cal[prev] if prev >= 0 else None            # last close of an earlier day
    return e, r


# ------------------------------------------------------------------------------------------ panel

def _wide(stocks, cal):
    px = stocks.pivot_table(index="price_date", columns="company_id", values="close", aggfunc="last")
    vol = stocks.pivot_table(index="price_date", columns="company_id", values="volume", aggfunc="last")
    px = px.reindex(cal)
    vol = vol.reindex(cal)
    return px, vol


def build_panel(refresh=False):
    """Daily stock-level arrays needed for every event: returns a dict with
    px_ff (ffilled closes), elig (eligible at d), brk_cum (cumulative data-break count),
    vol, adv, plus calendar, index closes and company groups."""
    if PANEL_CACHE.exists() and not refresh:
        return pd.read_pickle(PANEL_CACHE)
    t0 = time.time()
    stocks, index = load_prices()
    sc = index[index.index_key == BENCHMARK].set_index("price_date")["close"].sort_index()
    n50 = index[index.index_key == NIFTY50].set_index("price_date")["close"].sort_index()
    cal = sc.index
    px, vol = _wide(stocks, cal)
    px_ff = px.ffill(limit=STALE)
    daily = px_ff.pct_change(fill_method=None)
    brk = ((daily > BREAK_UP) | (daily < BREAK_DOWN)).astype(np.int16)
    brk_cum = brk.cumsum()
    history = px.notna().cumsum()
    adv = (px * vol).rolling(60, min_periods=40).median()
    elig = (history >= MIN_HISTORY) & (px_ff >= MIN_PRICE) & (adv >= MIN_ADV) & px.notna()
    panel = {"cal": cal, "sc": sc, "n50": n50.reindex(cal).ffill(), "px_ff": px_ff, "vol": vol,
             "brk_cum": brk_cum, "elig": elig}
    pd.to_pickle(panel, PANEL_CACHE)
    print(f"  panel built: {px.shape[1]} stocks x {len(cal)} days in {time.time() - t0:.0f}s")
    return panel


def group_map(companies, columns):
    """company_id -> {level: group name}; levels sector, industry, theme."""
    comp = companies.set_index("company_id")
    comp = comp.reindex(columns)
    maps = {"sector": comp["sector"], "industry": comp["industry"]}
    sym = comp["symbol"]
    theme = pd.Series(index=columns, dtype=object)
    members = {}
    for name, syms in THEMES.items():
        ids = sym[sym.isin(syms.split())].index
        members[name] = ids
    maps["theme_members"] = members
    return maps


def _winsor(row):
    v = row.dropna()
    if len(v) < 20:
        return row
    lo, hi = v.quantile(WINSOR[0]), v.quantile(WINSOR[1])
    return row.clip(lo, hi)


def forward_returns(panel, d_idx, h):
    """Stock returns from close(d) to close(d+h) for eligible stocks at day index d_idx."""
    px = panel["px_ff"]
    if d_idx + h >= len(px):
        return None
    p0 = px.iloc[d_idx]
    p1 = px.iloc[d_idx + h]
    ok = panel["elig"].iloc[d_idx] & p1.notna() & (panel["brk_cum"].iloc[d_idx + h] == panel["brk_cum"].iloc[d_idx])
    r = (p1 / p0 - 1).where(ok)
    return _winsor(r)


def window_returns(panel, i0, i1):
    """Stock returns close(i0) -> close(i1) (i1 > i0) among stocks eligible at i0 (day-0 reaction)."""
    px = panel["px_ff"]
    ok = panel["elig"].iloc[i0] & px.iloc[i1].notna() & (panel["brk_cum"].iloc[i1] == panel["brk_cum"].iloc[i0])
    return _winsor((px.iloc[i1] / px.iloc[i0] - 1).where(ok))


def group_means(r, maps):
    """Stock returns -> {(level, group): (mean, n)} for sector, industry, theme, plus 'ALL'."""
    out = {("all", "All eligible stocks"): (r.mean(), int(r.notna().sum()))}
    for level in ("sector", "industry"):
        g = r.groupby(maps[level]).agg(["mean", "count"])
        for name, row in g.iterrows():
            if row["count"] >= MIN_MEMBERS:
                out[(level, name)] = (row["mean"], int(row["count"]))
    for name, ids in maps["theme_members"].items():
        v = r.reindex(ids).dropna()
        if len(v) >= THEME_MIN_MEMBERS:
            out[("theme", name)] = (v.mean(), len(v))
    return out


def abnormal_volume(panel, d_idx, maps):
    vol = panel["vol"]
    if d_idx + 5 > len(vol) or d_idx < 66:
        return {}
    pre = vol.iloc[d_idx - 65:d_idx - 5].median()
    post = vol.iloc[d_idx:d_idx + 5].mean()
    ratio = np.log((post / pre).where((pre > 0) & panel["elig"].iloc[d_idx]))
    ratio = ratio.replace([np.inf, -np.inf], np.nan)
    out = {("all", "All eligible stocks"): float(np.exp(ratio.median()))}
    for level in ("sector", "industry"):
        g = ratio.groupby(maps[level]).agg(["median", "count"])
        for name, row in g.iterrows():
            if row["count"] >= MIN_MEMBERS:
                out[(level, name)] = float(np.exp(row["median"]))
    for name, ids in maps["theme_members"].items():
        v = ratio.reindex(ids).dropna()
        if len(v) >= THEME_MIN_MEMBERS:
            out[("theme", name)] = float(np.exp(v.median()))
    return out


# ------------------------------------------------------------------------------- event returns

def event_returns(events, panel, companies):
    """Long table: one row per (event, level, group, horizon)."""
    cal = panel["cal"]
    maps = group_map(companies, panel["px_ff"].columns)
    sc, n50 = panel["sc"], panel["n50"]
    rows = []
    for ev in events.itertuples():
        e, r = entry_and_ref(ev.date, ev.time_ist, cal)
        if e is None:
            continue
        ei = cal.get_loc(e)
        ri = cal.get_loc(r) if r is not None else None
        base = {"event_id": ev.event_id, "event_date": ev.date.date(), "entry_date": e.date(),
                "ref_date": r.date() if r is not None else None, "event_type": ev.event_type,
                "subtype": ev.subtype, "stance": ev.stance, "scope": ev.scope}
        av = abnormal_volume(panel, ei, maps)
        # day-0 reaction (not tradeable)
        if ri is not None and ri < ei:
            rr = window_returns(panel, ri, ei)
            g0 = group_means(rr, maps)
            sc0, n0 = sc.iloc[ei] / sc.iloc[ri] - 1, n50.iloc[ei] / n50.iloc[ri] - 1
            u0 = g0[("all", "All eligible stocks")][0]
            for (level, name), (m, n) in g0.items():
                rows.append({**base, "level": level, "group": name, "horizon": "day0", "h": 0,
                             "n_stocks": n, "ret": m, "index_sc": sc0, "index_n50": n0,
                             "excess_sc": m - sc0, "excess_n50": m - n0, "rel": m - u0,
                             "abn_vol": av.get((level, name))})
        for hname, h in HORIZONS.items():
            fr = forward_returns(panel, ei, h)
            if fr is None:
                continue
            g = group_means(fr, maps)
            sch = sc.iloc[ei + h] / sc.iloc[ei] - 1
            nh = n50.iloc[ei + h] / n50.iloc[ei] - 1
            u = g[("all", "All eligible stocks")][0]
            for (level, name), (m, n) in g.items():
                rows.append({**base, "level": level, "group": name, "horizon": hname, "h": h,
                             "n_stocks": n, "ret": m, "index_sc": sch, "index_n50": nh,
                             "excess_sc": m - sch, "excess_n50": m - nh, "rel": m - u,
                             "abn_vol": av.get((level, name))})
        print(f"  {ev.event_id} {ev.date.date()} -> entry {e.date()}", end="\r")
    print()
    return pd.DataFrame(rows)


# ------------------------------------------------------------------------- placebo distribution

def daily_group_panels(panel, companies, h):
    """Forward h-day `rel` and `excess_sc` of every group for every trading day (placebo tests,
    validation baselines). -> {level: DataFrame index=date, columns=MultiIndex(measure, group)}."""
    cache = CACHE_DIR / f"events_daily_{h}.pkl"
    if cache.exists():
        return pd.read_pickle(cache)
    maps = group_map(companies, panel["px_ff"].columns)
    cal, sc = panel["cal"], panel["sc"]
    recs = {lv: {} for lv in ("sector", "industry", "theme")}
    for i in range(130, len(cal) - h):
        g = group_means(forward_returns(panel, i, h), maps)
        u = g[("all", "All eligible stocks")][0]
        sch = sc.iloc[i + h] / sc.iloc[i] - 1
        for lv in recs:
            recs[lv][cal[i]] = {}
        for (lv, name), (m, n) in g.items():
            if lv in recs:
                recs[lv][cal[i]][("rel", name)] = m - u
                recs[lv][cal[i]][("excess_sc", name)] = m - sch
        if i % 250 == 0:
            print(f"  daily panels h={h}: {cal[i].date()}", end="\r")
    print()
    out = {}
    for lv, rec in recs.items():
        df = pd.DataFrame.from_dict(rec, orient="index")
        df.columns = pd.MultiIndex.from_tuples(df.columns)
        out[lv] = df.sort_index()
    pd.to_pickle(out, cache)
    return out


def placebo_pvalues(er, daily, measure="rel", n_draws=2000, window=63, seed=7):
    """Two-sided placebo p-value for each group's mean `measure` across a set of events:
    redraw each event's entry date uniformly within +-`window` trading days (same regime, different
    day), recompute the mean, and compare. Returns {group: p}."""
    rng = np.random.default_rng(seed)
    dates = daily.index
    sub = daily[measure]
    entries = pd.to_datetime(er["entry_date"].unique())
    pos = [dates.searchsorted(d) for d in entries]
    pos = [p for p in pos if p < len(dates)]
    if not pos:
        return {}
    obs = er.groupby("group")[measure].mean()
    draws = np.empty((n_draws, len(pos)), dtype=int)
    for k, p in enumerate(pos):
        lo, hi = max(0, p - window), min(len(dates) - 1, p + window)
        draws[:, k] = rng.integers(lo, hi + 1, size=n_draws)
    out = {}
    arr = sub.to_numpy()
    cols = list(sub.columns)
    for gname, o in obs.items():
        if gname not in cols or pd.isna(o):
            continue
        col = arr[:, cols.index(gname)]
        sims = np.nanmean(col[draws], axis=1)
        centre = np.nanmean(sims)
        out[gname] = float((np.abs(sims - centre) >= abs(o - centre)).mean())
    return out


# ------------------------------------------------------------------------------------------- CLI

def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--refresh", action="store_true", help="re-pull companies and rebuild the panel")
    args = ap.parse_args(argv)
    RESULTS.mkdir(exist_ok=True)
    events = load_events()
    companies = load_companies(args.refresh)
    panel = build_panel(args.refresh)
    er = event_returns(events, panel, companies)
    er.to_csv(RESULTS / "event_returns.csv", index=False)
    entries = er.drop_duplicates("event_id")[["event_id", "event_date", "ref_date", "entry_date"]]
    entries.to_csv(RESULTS / "event_entries.csv", index=False)
    print(f"  {er.event_id.nunique()} events, {len(er):,} rows -> results/event_returns.csv")

    # playbooks with placebo p-values (sector + theme levels, every type and type:stance)
    from .playbook import playbook, add_bh_qvalues, GROUPINGS
    tables = []
    for h in ("21d", "63d", "126d"):
        daily = daily_group_panels(panel, companies, HORIZONS[h])
        for key in GROUPINGS(events):
            et, stance = key
            for level in ("sector", "theme", "industry"):
                t = playbook(et, stance=stance, horizon=h, level=level, event_returns=er)
                if t.empty:
                    continue
                if level in daily:
                    sub = er[(er.event_type == et) & (er.level == level) & (er.horizon == h)]
                    if stance:
                        sub = sub[sub.stance.isin(stance.split("|"))]
                    p = placebo_pvalues(sub, daily[level])
                    t["placebo_p"] = t["group"].map(p)
                tables.append(t)
    pb = pd.concat(tables, ignore_index=True)
    pb = add_bh_qvalues(pb)
    pb.to_csv(RESULTS / "playbook_tables.csv", index=False)
    print(f"  playbook rows: {len(pb):,} -> results/playbook_tables.csv")


if __name__ == "__main__":
    main()
