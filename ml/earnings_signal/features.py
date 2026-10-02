"""Point-in-time earnings-surprise signals per (company, signal date D).

Two classic post-earnings-drift signals, built only from data public before D:

S1  "earnings announcement return" (EAR): the stock's return minus the NIFTY SMALLCAP 250 over the
    3 sessions around the result filing.
        filing time      financial_filings.filing_date (a timestamp, IST): the first time ANY filing
                         (standalone or consolidated) of that period became public on NSE
        day 0            the first session whose close comes after the filing: the filing date itself
                         if it is a trading day and the filing time is before 15:30; otherwise the
                         next trading day (most results arrive after market hours). A timestamp of
                         exactly 00:00:00 has no time of day and is treated as after the close.
        base close       close of the session before day 0 (the last price before the news), or the
                         stock's last close within STALE sessions before it
        window end       close of day +2 (S1_POST_SESSIONS), last close within 2 sessions
        S1               (close_end / close_base - 1) - (index_end / index_base - 1)
        known            after the close of day +2: usable on signal dates D > that day
                         (signal dates are 00:00; the ranking is acted on the session after D)
    A data break (one-day move > +100% or < -60%, growth_model/labels.py) inside the window -> NaN.

S2  "growth surprise" (SUE-like; there are no analyst estimates in the data): for revenue and net
    profit separately, the latest quarter's YoY growth minus the mean of the previous 4 quarters'
    YoY growth, divided by their standard deviation (with a floor), i.e. how unusual this quarter's
    growth is against the company's own recent growth path.
        YoY values       financials.features rows (one per company and quarter, stamped with its
                         filing_date); previous quarters only count if filed on or before the
                         current row's filing_date; YoY clipped to [-100%, +300%] first (small bases)
        needs            >= S2_MIN_PRIOR of the 4 previous quarters
        sd floor         revenue 0.05, net profit 0.20 (fraction points)
        S2               mean of the available revenue / net-profit surprises, clipped to +-5
        known            filing_date of that feature row (consolidated preferred, as features.py),
                         usable on D when filing_date < D 00:00 (the build.py visibility rule)

Result events: one per (company, quarter end) from `financial_filings` (non_financial format, the
same SELECT/cache as financial_model.data), kept only when it is a NEW latest quarter (period end
later than every period filed before it) and filed within MAX_FILING_LAG_DAYS of the quarter end
(old-period refilings and restatements are not result announcements).

As-of join (`attach`): for each (company, D), the latest event whose S1 is known before D, and
separately the latest event whose S2 row was filed before D, each with "days since" (D minus its
known date). Recency cuts (45 / 90 days) are applied in eval.py.

No look-ahead (`check_no_lookahead`): (1) structural asserts on every joined row (known dates < D,
the S1 window starts after the first filing, window end = known date); (2) a recompute test: for a
random sample of (company, D) the whole pipeline is re-run with ONLY prices dated < D and filings /
feature rows filed < D, and the joined values must be identical.

Banks / NBFCs / insurers: S1 works for any filer; S2 uses financials.features, which is
non-financial only (eval.py tests the non-financial universe, as combiner_eval Part A).

Data: caches only (ml/data/processed/financial_raw.pkl, financial_features.pkl,
growth_stock_prices.pkl, growth_index_prices.pkl); a missing financial cache is rebuilt with one
SELECT by financial_model.data.load_feature_table. No DB writes.
"""

import numpy as np
import pandas as pd

from growth_model.prices import BENCHMARK, INDEX_CACHE, STOCK_CACHE

# ---- pre-declared (written before any result was looked at) ----
MARKET_CLOSE = pd.Timedelta(hours=15, minutes=30)
S1_POST_SESSIONS = 2            # day 0 .. day +2
STALE = 5                       # base close may lag by this many sessions (labels.ENTRY_STALE)
END_STALE = 2
BREAK_UP, BREAK_DOWN = 1.0, -0.6
MAX_FILING_LAG_DAYS = 120
S2_MIN_PRIOR = 3
YOY_CLIP = (-1.0, 3.0)
SD_FLOOR = {"revenue": 0.05, "net_profit": 0.20}
SUE_CLIP = 5.0


# ---------------------------------------------------------
# Inputs
# ---------------------------------------------------------

def load_inputs():
    """-> (raw filings, feature table, stock prices, index prices) from the caches."""
    from financial_model.data import load_feature_table

    table, raw = load_feature_table()
    return raw, table, pd.read_pickle(STOCK_CACHE), pd.read_pickle(INDEX_CACHE)


def _price_matrices(stocks, index):
    bench = index[index["index_key"] == BENCHMARK].set_index("price_date")["close"].sort_index()
    cal = bench.index
    s = stocks[stocks["close"] > 0]
    close = s.pivot_table(index="price_date", columns="company_id", values="close", aggfunc="last")
    step = close.apply(lambda c: c.dropna().pct_change()).reindex(close.index)
    breaks = ((step > BREAK_UP) | (step < BREAK_DOWN)).astype(int)
    union = close.index.union(cal)
    close = close.reindex(union)
    breaks = breaks.reindex(union, fill_value=0).cumsum().reindex(cal, method="ffill")
    base_px = close.ffill(limit=STALE).reindex(cal)
    end_px = close.ffill(limit=END_STALE).reindex(cal)
    return cal, bench, base_px, end_px, breaks


# ---------------------------------------------------------
# Events
# ---------------------------------------------------------

def result_events(raw):
    """One row per fresh result: company_id, period_end, first_filing."""
    r = raw[raw["company_id"].notna()].copy()
    r["company_id"] = r["company_id"].astype(int)
    r = r[r["period_end"].dt.is_month_end & r["period_end"].dt.month.isin([3, 6, 9, 12])]
    ev = r.groupby(["company_id", "period_end"], as_index=False)["filing_date"].min()
    ev = ev.rename(columns={"filing_date": "first_filing"}).sort_values(["company_id", "first_filing", "period_end"])
    prev_max = ev.groupby("company_id")["period_end"].transform(lambda s: s.cummax().shift())
    lag = (ev["first_filing"] - ev["period_end"]).dt.days
    ev = ev[(prev_max.isna() | (ev["period_end"] > prev_max)) & (lag >= 0) & (lag <= MAX_FILING_LAG_DAYS)]
    return ev.reset_index(drop=True)


def add_s1(ev, cal, bench, base_px, end_px, breaks):
    ts = ev["first_filing"]
    day = ts.dt.normalize()
    tod = ts - day
    on_cal = day.isin(cal)
    before_close = (tod > pd.Timedelta(0)) & (tod < MARKET_CLOSE)
    pos_after = cal.searchsorted(day, side="right")
    pos_same = cal.searchsorted(day, side="left")
    pos0 = np.where(on_cal & before_close, pos_same, pos_after)
    pos_b, pos_e = pos0 - 1, pos0 + S1_POST_SESSIONS
    n = len(cal)
    ok = (pos_b >= 0) & (pos_e < n) & ev["company_id"].isin(base_px.columns).values
    col = {c: i for i, c in enumerate(base_px.columns)}
    B, E, K, I = base_px.values, end_px.values, breaks.values, bench.values
    s1 = np.full(len(ev), np.nan)
    known = np.full(len(ev), np.datetime64("NaT"), dtype="datetime64[ns]")
    d0 = known.copy()
    for k in np.flatnonzero(ok):
        j = col[ev["company_id"].iat[k]]
        b, e = pos_b[k], pos_e[k]
        pb, pe = B[b, j], E[e, j]
        d0[k] = cal[pos0[k]]
        known[k] = cal[e]
        if np.isnan(pb) or np.isnan(pe) or K[e, j] != K[b, j]:
            continue
        s1[k] = (pe / pb - 1) - (I[e] / I[b] - 1)
    ev = ev.copy()
    ev["day0"] = d0
    ev["s1_known"] = known
    ev["s1"] = s1
    return ev


def growth_surprise(table):
    """S2 per features row: company_id, period_end, s2_known (filing_date), rev_sue, np_sue, s2."""
    f = table[table["company_id"].notna()][["company_id", "period_end", "filing_date",
                                            "revenue_yoy", "net_profit_yoy"]].copy()
    f["company_id"] = f["company_id"].astype(int)
    f = f.drop_duplicates(["company_id", "period_end"], keep="first")
    for c in ("revenue_yoy", "net_profit_yoy"):
        f[c] = f[c].clip(*YOY_CLIP)
    out = f.copy()
    for k in range(1, 5):
        prev = f.rename(columns={"period_end": "pe_prev", "filing_date": f"fd_{k}",
                                 "revenue_yoy": f"rev_{k}", "net_profit_yoy": f"np_{k}"})
        out[f"pe_{k}"] = out["period_end"] - pd.offsets.QuarterEnd(k)
        out = out.merge(prev, left_on=["company_id", f"pe_{k}"], right_on=["company_id", "pe_prev"], how="left")
        late = out[f"fd_{k}"] > out["filing_date"]                  # not visible yet at this filing
        out.loc[late, [f"rev_{k}", f"np_{k}"]] = np.nan
        out = out.drop(columns=["pe_prev", f"pe_{k}", f"fd_{k}"])
    for name, cur, pre in (("revenue", "revenue_yoy", "rev"), ("net_profit", "net_profit_yoy", "np")):
        hist = out[[f"{pre}_{k}" for k in range(1, 5)]]
        cnt = hist.notna().sum(axis=1)
        mu, sd = hist.mean(axis=1), hist.std(axis=1, ddof=1).clip(lower=SD_FLOOR[name])
        sue = ((out[cur] - mu) / sd).where(cnt >= S2_MIN_PRIOR).clip(-SUE_CLIP, SUE_CLIP)
        out[f"{pre}_sue"] = sue
    out["s2"] = out[["rev_sue", "np_sue"]].mean(axis=1)
    out = out.rename(columns={"filing_date": "s2_known"})
    return out[["company_id", "period_end", "s2_known", "revenue_yoy", "net_profit_yoy", "rev_sue", "np_sue", "s2"]]


def build_events(raw, table, stocks, index):
    """Result events with S1 and S2 (each with its own known time)."""
    cal, bench, base_px, end_px, breaks = _price_matrices(stocks, index)
    ev = add_s1(result_events(raw), cal, bench, base_px, end_px, breaks)
    s2 = growth_surprise(table)
    return ev.merge(s2, on=["company_id", "period_end"], how="left")


# ---------------------------------------------------------
# As-of join onto (company, D)
# ---------------------------------------------------------

def _asof(keys, right, on, cols, prefix):
    r = right[right["s_val"].notna()][["company_id", on, *cols]].dropna(subset=[on]).sort_values(on)
    r = r.rename(columns={c: f"{prefix}{c}" for c in cols})
    left = keys[["company_id", "signal_date"]].sort_values("signal_date").reset_index()
    m = pd.merge_asof(left, r, left_on="signal_date", right_on=on, by="company_id",
                      direction="backward", allow_exact_matches=False)
    return m.set_index("index").drop(columns=["company_id", "signal_date"]).reindex(keys.index)


def attach(keys, events):
    """keys: company_id, signal_date (00:00). Adds S1 / S2 of the latest result known strictly before D."""
    keys = keys.copy()
    keys["signal_date"] = keys["signal_date"].astype("datetime64[ns]")
    e = events.copy()
    e1 = e.assign(s_val=e["s1"])
    a = _asof(keys, e1, "s1_known", ["s1", "first_filing", "day0", "period_end"], "")
    a = a.rename(columns={"s1_known": "s1_known", "first_filing": "s1_first_filing",
                          "day0": "s1_day0", "period_end": "s1_period_end"})
    e2 = e.assign(s_val=e["s2"])
    b = _asof(keys, e2, "s2_known", ["s2", "rev_sue", "np_sue", "period_end"], "")
    b = b.rename(columns={"period_end": "s2_period_end"})
    out = pd.concat([keys, a, b], axis=1)
    out["s1_age"] = (out["signal_date"] - out["s1_known"]).dt.days
    out["s2_age"] = (out["signal_date"] - out["s2_known"].dt.normalize()).dt.days
    return out


# ---------------------------------------------------------
# No-look-ahead check
# ---------------------------------------------------------

SIGNAL_COLS = ["s1", "s1_known", "s1_period_end", "s2", "s2_known", "s2_period_end", "rev_sue", "np_sue"]


def check_structure(panel):
    has1 = panel["s1"].notna()
    p = panel[has1]
    assert (p["s1_known"] < p["signal_date"]).all(), "S1 known on/after D"
    assert (p["s1_day0"] > p["s1_first_filing"].dt.normalize() - pd.Timedelta(days=1)).all(), "S1 window before filing"
    assert (p["s1_day0"] <= p["s1_known"]).all()
    assert (p["s1_first_filing"] < p["signal_date"]).all()
    has2 = panel["s2"].notna()
    p = panel[has2]
    assert (p["s2_known"] < p["signal_date"]).all(), "S2 filed on/after D"
    assert (p["s2_period_end"] < p["signal_date"]).all()
    return int(has1.sum()), int(has2.sum())


def check_no_lookahead(panel, raw, table, stocks, index, n=300, seed=7):
    """Structural asserts + recompute a random sample with data truncated at D. Returns a summary dict."""
    n1, n2 = check_structure(panel)
    sample = panel[panel["s1"].notna() | panel["s2"].notna()].sample(n=min(n, len(panel)), random_state=seed)
    raw_c = raw[raw["company_id"].notna()].assign(company_id=lambda x: x["company_id"].astype(int))
    tab_c = table[table["company_id"].notna()].assign(company_id=lambda x: x["company_id"].astype(int))
    mism, done = [], 0
    for _, row in sample.iterrows():
        cid, d = int(row["company_id"]), row["signal_date"]
        r = raw_c[(raw_c["company_id"] == cid) & (raw_c["filing_date"] < d)]
        t = tab_c[(tab_c["company_id"] == cid) & (tab_c["filing_date"] < d)]
        s = stocks[(stocks["company_id"] == cid) & (stocks["price_date"] < d)]
        i = index[index["price_date"] < d]
        if len(r) == 0 or len(s) == 0:
            continue
        done += 1
        ev = build_events(r, t, s, i)
        got = attach(pd.DataFrame({"company_id": [cid], "signal_date": [d]}), ev).iloc[0]
        for c in SIGNAL_COLS:
            a, b = row[c], got[c]
            same = (pd.isna(a) and pd.isna(b)) or (not pd.isna(a) and not pd.isna(b) and
                                                     (a == b or (isinstance(a, float) and abs(a - b) < 1e-9)))
            if not same:
                mism.append((cid, str(d.date()), c, a, b))
    assert not mism, f"look-ahead check failed on {len(mism)} values, e.g. {mism[:5]}"
    return {"rows_with_s1": n1, "rows_with_s2": n2, "recomputed_rows": done, "values_compared": done * len(SIGNAL_COLS), "mismatches": 0}


def build_panel(keys, inputs=None):
    """-> (keys + point-in-time signals, events, inputs)."""
    raw, table, stocks, index = inputs or load_inputs()
    events = build_events(raw, table, stocks, index)
    return attach(keys, events), events, (raw, table, stocks, index)
