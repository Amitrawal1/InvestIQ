"""Point-in-time valuation features per (company, signal date D): market cap, earnings / book / sales /
FCF yield, their cross-sectional percentiles (overall and within sector) and the stock's own history.

Inputs (no collectors; one DB SELECT for equity, cached)
-------------------------------------------------------
- price(D)        `close_d` of growth_model/labels.py: last close on or before D. NOTE: the price cache
                  (growth_stock_prices.pkl, i.e. `stock_prices`) is split- AND bonus-adjusted to TODAY's
                  share basis (TATASTEEL shows ~93 in July 2022, before its 1:10 split; NESTLEIND ~1,370
                  before its Jan-2024 1:10 split; WIPRO has no jump at its Dec-2024 1:1 bonus).
- shares          rankings/build.py `shares_outstanding`: net profit to owners / basic EPS of a quarter
                  (crore shares). Here per filing, point-in-time (see below).
- TTM P&L / FCF   financial_model.data.build_panel rows (financials/features.py, filing_date <= D):
                  net_profit_ttm, revenue_ttm, fcf_ttm (cash flow from Sep 2020).
- equity          `financial_filings.bs_equity_owners` (owners' equity; fallback total equity - NCI,
                  then total equity). Before Sep 2022 it exists only in the legacy ANNUAL (March) filings;
                  from Sep 2022 half-yearly. One SELECT, cached in valuation_equity_raw.pkl.

Share count, point in time
--------------------------
Per filing row: s = profit_owners / eps_basic of the quarter block (build.py rule: |eps| >= 0.05,
|profit| >= 0.5 cr, same sign, 0.01 < s < 5000 crore), else the same ratio on the year-to-date block.
Per (company, period_end) the visible estimate at time t is the best row filed by t (consolidated >
standalone, ok > partial, earliest filing; build.py `_pick_one`, restricted to rows with a usable s,
which is a small coverage gain over build.py). At D the latest visible period is used, with a guard:
if it differs by > 30% from the median of the latest three visible periods (same share basis), the
median is used (one noisy EPS would otherwise move the market cap).

Split / bonus correction (the one non-point-in-time ingredient, deliberately):
Because prices are adjusted to today's basis, mcap(D) = adjusted price(D) x shares(D) expressed in
TODAY's basis = adjusted price(D) x s x F, where F = product of the split/bonus ratios that happened
after the period of s. That is exactly price-as-quoted-on-D x shares-on-D: F only converts units back
(it undoes the adjustment the data vendor applied with hindsight); it adds no information about D.
Split events are detected in each company's full share-estimate series (all filings): a jump in the
persistent jump (>= 1.4x) in the level of the share estimate whose ratio is within +-7% of a
split/bonus ratio in NICE_RATIOS (>= 1.5x; consolidations 2:1 or bigger), see `detect_splits`. Genuine
issuance (QIPs, mergers) rarely lands on these ratios and is NOT adjusted (it is real dilution).
Errors: an undetected split makes the stock look k times cheaper before the split (and splits follow
rallies), so eval.py also reports every result on companies with no split events at all.

Validation of the share estimate (see `validate_shares`): `nse_financial_results` has paid_up_capital /
face_value (= exact share count) for 44 large companies; the estimate and the detected splits are
compared with it.

Features (NaN when an input is missing; never 0)
    mcap_cr    close_d x shares (crore Rs); NaN when the share period ended > 275 days before D
    ey         net_profit_ttm / mcap   (negative earnings kept: loss-makers rank at the bottom)
    bp         equity / mcap           (equity <= 450 days old; negative equity ranks at the bottom)
    sp         revenue_ttm / mcap      (revenue_ttm > 0)
    fcfy       fcf_ttm / mcap          (from Sep 2020)
    p_<x>      percentile 0-1 per signal date among the panel rows (higher = cheaper)
    s_<x>      percentile within (date, sector) when the sector has >= SECTOR_MIN names, else p_<x>
    own_ey     percentile of ey against the company's own ey on earlier grid dates in the 3 years before
               D (>= 24 earlier observations, i.e. ~1 year; NaN before)

Banks / NBFCs / insurers are outside this panel (financials/features.py covers non_financial filers
only), so they get no valuation features here (eval.py: excluded, scored as today).

No look-ahead: `check_point_in_time` asserts filing_date <= D and period_end < D for every input row,
and `truncation_check` rebuilds shares and equity from filings truncated at D for sample dates and
asserts the as-of values are identical (F is held fixed: it is the unit conversion above).
"""

import numpy as np
import pandas as pd

from growth_model.prices import CACHE_DIR

EQUITY_RAW = CACHE_DIR / "valuation_equity_raw.pkl"

# split / bonus ratios detected (1:4 and 1:3 bonuses, 1.25x / 1.33x, are left out: indistinguishable from
# issuance in noisy EPS-based counts; missing one misstates earlier market caps by <= 25-33%)
NICE_RATIOS = [1.5, 2.0, 2.5, 3.0, 4.0, 5.0, 6.0, 8.0, 10.0, 15.0, 20.0, 25.0, 50.0, 100.0]
MIN_CONSOLIDATION = 2.0             # reverse splits only 2:1 or bigger
SPLIT_MIN_JUMP = np.log(1.4)
PERSIST = 0.10                      # log tolerance for "steady level"
REVERT_LOOKBACK = 4                 # periods before the pre-jump level checked for a revert
TOL_BIG = 0.07
LEVEL_OBS = 3                       # periods each side for the level comparison
GUARD = np.log(1.3)                 # latest estimate vs median of the last 3 visible periods
SHARES_MAX_AGE_DAYS = 275           # build.py STALE_FINANCIALS_DAYS
EQUITY_MAX_AGE_DAYS = 450           # annual-only statements before Sep 2022
SECTOR_MIN = 10
OWN_YEARS_DAYS = 3 * 365
OWN_MIN_OBS = 24
SIGNALS = ["ey", "bp", "sp", "fcfy"]
UNIT_RATIO = (0.2, 5.0)             # revenue_ttm / (4 x quarter revenue) outside -> unit error suspected
# outside these a yield is a data error (P/E < 0.2, P/S < 0.01, P/B < 0.02 or equity 20x mcap negative)
PLAUSIBLE = {"ey": (-5.0, 5.0), "bp": (-20.0, 50.0), "sp": (0.0, 100.0), "fcfy": (-10.0, 10.0)}


# ---------------------------------------------------------
# Loading
# ---------------------------------------------------------

def load_raw():
    """financial_raw.pkl (financial_model.data cache of financials.features._load_raw)."""
    from financial_model.data import RAW_CACHE, load_feature_table

    if not RAW_CACHE.exists():
        load_feature_table()
    return pd.read_pickle(RAW_CACHE)


def load_equity_raw(refresh=False):
    """Equity rows of non_financial filings (one SELECT, cached)."""
    if EQUITY_RAW.exists() and not refresh:
        return pd.read_pickle(EQUITY_RAW)
    import warnings

    from news_pipeline.db import get_connection

    warnings.filterwarnings("ignore", message="pandas only supports SQLAlchemy")
    sql = ("SELECT company_id, symbol, statement_type, parse_status, period_end, filing_date, "
           "bs_equity_owners, bs_total_equity, bs_non_controlling_interest FROM financial_filings "
           "WHERE format = 'non_financial' AND parse_status <> 'failed' AND filing_date IS NOT NULL "
           "AND company_id IS NOT NULL AND (bs_equity_owners IS NOT NULL OR bs_total_equity IS NOT NULL)")
    conn = get_connection()
    try:
        df = pd.read_sql(sql, conn)
    finally:
        conn.close()
    df["filing_date"] = pd.to_datetime(df["filing_date"])
    df["period_end"] = pd.to_datetime(df["period_end"])
    for c in ("bs_equity_owners", "bs_total_equity", "bs_non_controlling_interest"):
        df[c] = pd.to_numeric(df[c], errors="coerce").astype(float)
    df.to_pickle(EQUITY_RAW)
    return df


# ---------------------------------------------------------
# Point-in-time "best row per period" events
# ---------------------------------------------------------

def _pref(df):
    return df.assign(pref_basis=(df["statement_type"] != "consolidated").astype(int),
                     pref_status=(df["parse_status"] != "ok").astype(int))


def period_events(rows, value_col):
    """rows: company_id, period_end, filing_date, statement_type, parse_status, value_col (non-null).

    -> events (company_id, period_end, filing_date, value): one per row that changes the best
    visible value of its period (preference consolidated > standalone, ok > partial, earliest).
    """
    r = _pref(rows[rows[value_col].notna()]).sort_values(["company_id", "period_end", "filing_date"])
    out = []
    for (cid, pe), g in r.groupby(["company_id", "period_end"], sort=False):
        best = None
        for row in g.itertuples(index=False):
            key = (row.pref_basis, row.pref_status, row.filing_date)
            if best is None or key < best[0]:
                best = (key, getattr(row, value_col))
                out.append((cid, pe, row.filing_date, best[1]))
    ev = pd.DataFrame(out, columns=["company_id", "period_end", "filing_date", "value"])
    ev["company_id"] = ev["company_id"].astype(int)
    return ev


def final_per_period(ev):
    """Best value per (company, period) using every filing (the last event of each period)."""
    return ev.sort_values("filing_date").groupby(["company_id", "period_end"], as_index=False).last()


# ---------------------------------------------------------
# Shares
# ---------------------------------------------------------

def _ratio(profit, eps):
    ok = (eps.abs() >= 0.05) & (profit.abs() >= 0.5) & (np.sign(eps) == np.sign(profit))
    s = (profit / eps).where(ok)
    return s.where((s > 0.01) & (s < 5000))


def row_share_estimates(raw):
    r = raw[raw["company_id"].notna() & raw["filing_date"].notna()].copy()
    r["company_id"] = r["company_id"].astype(int)
    s_q = _ratio(r["inc_net_profit_owners"].fillna(r["inc_net_profit"]), r["inc_eps_basic"])
    s_y = _ratio(r["ytd_net_profit_owners"].fillna(r["ytd_net_profit"]), r["ytd_eps_basic"])
    r["shares_raw"] = s_q.fillna(s_y)
    return r[["company_id", "symbol", "period_end", "filing_date", "statement_type", "parse_status", "shares_raw"]]


def _nice(ratio):
    """Nearest split/bonus ratio (or, <= 1/2, a consolidation) if within tolerance, else None."""
    up = ratio >= 1
    x = ratio if up else 1 / ratio
    best = min(NICE_RATIOS, key=lambda n: abs(np.log(x / n)))
    if not up and best < MIN_CONSOLIDATION:
        return None
    if abs(np.log(x / best)) <= TOL_BIG:
        return best if up else 1 / best
    return None


def detect_splits(final):
    """final: company_id, period_end, value (period-basis share estimate). -> events + F per period.

    A boundary i (between periods i-1 and i) is a split/bonus when the one-step jump is >= 1.4x
    (either way), the level after it persists (every one of the next <= 3 estimates within 10% of their
    median; a jump into the very last period cannot be confirmed: the company goes to `uncertain`), the level before it is steady (the last
    <= 2 estimates within 10% of each other), the new level is not a return to one of the 4 estimates
    before that (a noisy dip or spike reverting), and the before/after level ratio is within 7% of a
    ratio in NICE_RATIOS. Companies in `uncertain` get no valuation features (add_valuation).
    Returns (split events DataFrame, factors DataFrame company_id, period_end, F)."""
    events, factors, uncertain = [], [], set()
    for cid, g in final.sort_values(["company_id", "period_end"]).groupby("company_id", sort=False):
        pes = g["period_end"].to_numpy()
        lv = np.log(g["value"].to_numpy(dtype=float))
        n = len(lv)
        start, ks = 0, np.ones(n)            # ks[i]: ratio of an event at boundary i (between i-1 and i)
        for i in range(1, n):
            step = lv[i] - lv[i - 1]
            if abs(step) < SPLIT_MIN_JUMP:
                continue
            pre_obs = lv[max(start, i - 2):i]
            post_obs = lv[i:min(n, i + LEVEL_OBS)]
            if np.ptp(pre_obs) > PERSIST:
                continue
            if len(post_obs) < 2:
                uncertain.add(int(cid))      # a jump into the last period cannot be confirmed
                continue
            post = np.median(post_obs)
            if np.abs(post_obs - post).max() > PERSIST:
                continue
            earlier = lv[max(0, i - len(pre_obs) - REVERT_LOOKBACK):i - len(pre_obs)]
            if len(earlier) and np.abs(earlier - post).min() <= PERSIST:
                continue                     # back to an earlier level: the dip/spike was noise
            k = _nice(float(np.exp(post - np.median(pre_obs))))
            if k is None:
                continue
            ks[i] = k
            events.append({"company_id": int(cid), "before": pes[i - 1], "after": pes[i], "ratio": k,
                           "measured": float(np.exp(step))})
            start = i
        # F for period i = product of ks[j] for j > i
        F = np.ones(n)
        for i in range(n - 2, -1, -1):
            F[i] = F[i + 1] * ks[i + 1]
        factors.append(pd.DataFrame({"company_id": int(cid), "period_end": pes, "F": F}))
    ev = pd.DataFrame(events, columns=["company_id", "before", "after", "ratio", "measured"])
    ev.attrs["uncertain"] = sorted(uncertain)
    return ev, pd.concat(factors, ignore_index=True)


def share_events(raw, factors=None):
    """-> (visible share events in today's basis, split events, factors).

    Events: company_id, period_end, filing_date, shares_tb (guarded), shares_latest_tb."""
    rows = row_share_estimates(raw)
    ev = period_events(rows, "shares_raw")
    split_ev = None
    if factors is None:
        split_ev, factors = detect_splits(final_per_period(ev))
    ev = ev.merge(factors, on=["company_id", "period_end"], how="left")
    ev["F"] = ev["F"].fillna(1.0)
    ev["tb"] = ev["value"] * ev["F"]
    ev = ev.sort_values(["company_id", "filing_date", "period_end"]).reset_index(drop=True)
    out = []
    for cid, g in ev.groupby("company_id", sort=False):
        visible = {}
        maxpe = None
        for row in g.itertuples(index=False):
            visible[row.period_end] = row.tb
            if maxpe is not None and row.period_end < maxpe:
                continue                     # an older period filed late never becomes "latest"
            maxpe = row.period_end
            last3 = [visible[p] for p in sorted(visible)[-3:]]
            latest = visible[maxpe]
            med = float(np.median(last3))
            use = med if (len(last3) == 3 and abs(np.log(latest / med)) > GUARD) else latest
            out.append((cid, maxpe, row.filing_date, use, latest))
    out = pd.DataFrame(out, columns=["company_id", "period_end", "filing_date", "shares_tb", "shares_latest_tb"])
    return out, split_ev, factors


# ---------------------------------------------------------
# Equity
# ---------------------------------------------------------

def _quarter_revenue(raw):
    """Quarterly-equivalent revenue of the period's own block from its first filing (point in time:
    the panel's feature row for that period was filed at or after it)."""
    r = raw[raw["company_id"].notna()].copy()
    r["company_id"] = r["company_id"].astype(int)
    r["q_rev"] = (r["inc_revenue"] * 3 / r["months"]).where(r["months"].isin([3, 6]) & (r["inc_revenue"] > 0))
    ev = period_events(r, "q_rev").sort_values("filing_date")
    ev = ev.groupby(["company_id", "period_end"], as_index=False).first()   # first filed: visible by then
    return ev[["company_id", "period_end", "value"]].rename(columns={"value": "q_revenue"})


def equity_events(eq_raw):
    e = eq_raw.copy()
    e["company_id"] = e["company_id"].astype(int)
    nci = e["bs_non_controlling_interest"]
    e["equity"] = e["bs_equity_owners"].fillna(e["bs_total_equity"] - nci).fillna(e["bs_total_equity"])
    ev = period_events(e, "equity")
    ev = ev.sort_values(["company_id", "filing_date", "period_end"])
    prev = ev.groupby("company_id")["period_end"].transform(lambda s: s.cummax().shift())
    ev = ev[prev.isna() | (ev["period_end"] >= prev)]
    return ev.rename(columns={"value": "equity"}).reset_index(drop=True)


# ---------------------------------------------------------
# As-of join onto the panel
# ---------------------------------------------------------

def _asof(keys, events, prefix):
    left = keys[["company_id", "signal_date"]].drop_duplicates().copy()
    left["signal_date"] = left["signal_date"].astype("datetime64[ns]")
    left = left.sort_values("signal_date").reset_index(drop=True)
    right = events.rename(columns={"period_end": f"{prefix}_period_end", "filing_date": f"{prefix}_filing_date"})
    right[f"{prefix}_filing_date"] = right[f"{prefix}_filing_date"].astype("datetime64[ns]")
    right = right.sort_values(f"{prefix}_filing_date").reset_index(drop=True)
    return pd.merge_asof(left, right, left_on="signal_date", right_on=f"{prefix}_filing_date",
                         by="company_id", direction="backward", allow_exact_matches=True)


def check_point_in_time(df):
    for p in ("sh", "eq"):
        has = df[f"{p}_filing_date"].notna()
        assert (df.loc[has, f"{p}_filing_date"] <= df.loc[has, "signal_date"]).all(), f"{p}: filing after D"
        assert (df.loc[has, f"{p}_period_end"] < df.loc[has, "signal_date"]).all(), f"{p}: period_end after D"
    has = df["filing_date"].notna() if "filing_date" in df else pd.Series(False, index=df.index)
    assert (df.loc[has, "filing_date"] <= df.loc[has, "signal_date"]).all(), "P&L row filed after D"
    return True


def _pct(values, groups):
    g = values.groupby(groups)
    rank = g.rank(method="average")
    n = g.transform("count")
    out = (rank - 1) / (n - 1).where(n > 1)
    return out.where(~(n == 1) | values.isna(), 0.5)


def own_history(frame, col):
    """Percentile of col at D vs the same company's values on earlier dates within 3 years."""
    out = pd.Series(np.nan, index=frame.index)
    f = frame[["company_id", "signal_date", col]].dropna().sort_values(["company_id", "signal_date"])
    for _, g in f.groupby("company_id", sort=False):
        d = g["signal_date"].to_numpy()
        v = g[col].to_numpy()
        idx = g.index.to_numpy()
        lo = 0
        for i in range(len(v)):
            while d[lo] < d[i] - np.timedelta64(OWN_YEARS_DAYS, "D"):
                lo += 1
            past = v[lo:i]
            if len(past) >= OWN_MIN_OBS:
                out[idx[i]] = ((past < v[i]).sum() + 0.5 * (past == v[i]).sum()) / len(past)
    return out


def add_valuation(panel, sectors=None, raw=None, eq_raw=None, with_own=True):
    """panel: financial_model rows (company_id, signal_date, close_d, net_profit_ttm, revenue_ttm, fcf_ttm).

    Returns (panel + valuation columns, info dict with split events / factors / coverage)."""
    raw = load_raw() if raw is None else raw
    eq_raw = load_equity_raw() if eq_raw is None else eq_raw
    sh_ev, split_ev, factors = share_events(raw)
    eq_ev = equity_events(eq_raw)
    p = panel.copy()
    sh = _asof(p, sh_ev, "sh")
    eq = _asof(p, eq_ev, "eq")
    p = p.merge(sh, on=["company_id", "signal_date"], how="left").merge(eq, on=["company_id", "signal_date"], how="left")
    check_point_in_time(p)
    sh_age = (p["signal_date"] - p["sh_period_end"]).dt.days
    eq_age = (p["signal_date"] - p["eq_period_end"]).dt.days
    uncertain = set(split_ev.attrs.get("uncertain", [])) if split_ev is not None else set()
    shares = p["shares_tb"].where((sh_age <= SHARES_MAX_AGE_DAYS) & ~p["company_id"].isin(uncertain))
    p["mcap_cr"] = p["close_d"] * shares
    mc = p["mcap_cr"].where(p["mcap_cr"] > 0)
    # unit check: TTM revenue vs 4 x the quarter's own revenue (a lakh/crore mix-up in one filing
    # inflates a TTM sum ~25x); inconsistent rows get no P&L-based yields
    q = _quarter_revenue(raw)
    p = p.merge(q, on=["company_id", "period_end"], how="left")
    ratio = p["revenue_ttm"] / (4 * p["q_revenue"])
    p["unit_suspect"] = (ratio < UNIT_RATIO[0]) | (ratio > UNIT_RATIO[1])
    ok = ~p["unit_suspect"]
    p["ey"] = (p["net_profit_ttm"] / mc).where(ok)
    p["bp"] = p["equity"].where(eq_age <= EQUITY_MAX_AGE_DAYS) / mc
    p["sp"] = (p["revenue_ttm"].where(p["revenue_ttm"] > 0) / mc).where(ok)
    p["fcfy"] = (p["fcf_ttm"] / mc).where(ok)
    for c in SIGNALS:
        lo, hi = PLAUSIBLE[c]
        p[c] = p[c].replace([np.inf, -np.inf], np.nan)
        p[c] = p[c].where(p[c].between(lo, hi))
    if sectors is not None:
        p = p.merge(sectors, on="company_id", how="left")
    sector = p["sector"].fillna("Unknown") if "sector" in p else pd.Series("Unknown", index=p.index)
    size = p.groupby([p["signal_date"], sector])["company_id"].transform("count")
    for c in SIGNALS:
        p[f"p_{c}"] = _pct(p[c], p["signal_date"])
        within = _pct(p[c], [p["signal_date"], sector])
        p[f"s_{c}"] = within.where(size >= SECTOR_MIN, p[f"p_{c}"])
    if with_own:
        p["own_ey"] = own_history(p, "ey")
    split_cos = (set(split_ev["company_id"]) | uncertain) if split_ev is not None else set()
    p["split_company"] = p["company_id"].isin(split_cos)
    info = {"split_events": split_ev, "factors": factors, "share_events": sh_ev, "equity_events": eq_ev}
    return p, info


# ---------------------------------------------------------
# Checks
# ---------------------------------------------------------

def truncation_check(raw, eq_raw, factors, dates, keys):
    """Rebuild share/equity events from filings with filing_date <= D and compare as-of values at D.

    keys: company_id, signal_date rows. Returns number of compared values; raises on any mismatch."""
    full_sh, _, _ = share_events(raw, factors=factors)
    full_eq = equity_events(eq_raw)
    n = 0
    for d in dates:
        d = pd.Timestamp(d)
        k = keys[keys["signal_date"] == d]
        a_sh = _asof(k, full_sh, "sh").set_index("company_id")
        a_eq = _asof(k, full_eq, "eq").set_index("company_id")
        t_sh, _, _ = share_events(raw[raw["filing_date"] <= d], factors=factors)
        t_eq = equity_events(eq_raw[eq_raw["filing_date"] <= d])
        b_sh = _asof(k, t_sh, "sh").set_index("company_id")
        b_eq = _asof(k, t_eq, "eq").set_index("company_id")
        for a, b, c in ((a_sh, b_sh, "shares_tb"), (a_eq, b_eq, "equity")):
            x, y = a[c].reindex(k["company_id"]), b[c].reindex(k["company_id"])
            same = (x.isna() & y.isna()) | (np.isclose(x, y, rtol=1e-12, equal_nan=False))
            assert same.all(), f"look-ahead: {int((~same).sum())} {c} values differ at {d.date()}"
            n += int(x.notna().sum())
    return n


def validate_shares(raw, factors):
    """Compare the EPS-based share estimate with paid_up_capital / face_value (nse_financial_results)."""
    import warnings

    from news_pipeline.db import get_connection

    warnings.filterwarnings("ignore", message="pandas only supports SQLAlchemy")
    conn = get_connection()
    try:
        t = pd.read_sql("SELECT company_id, period_end, statement_type, paid_up_capital, face_value "
                        "FROM nse_financial_results WHERE paid_up_capital > 0 AND face_value > 0", conn)
    finally:
        conn.close()
    t["period_end"] = pd.to_datetime(t["period_end"])
    t["true_shares"] = pd.to_numeric(t["paid_up_capital"]).astype(float) / pd.to_numeric(t["face_value"]).astype(float)
    t = t.groupby(["company_id", "period_end"], as_index=False)["true_shares"].median()
    rows = row_share_estimates(raw)
    ev = final_per_period(period_events(rows, "shares_raw"))
    m = ev.merge(t, on=["company_id", "period_end"], how="inner")
    err = np.log(m["value"] / m["true_shares"])
    # split check: true shares in today's basis = true x (later true jumps); compare F
    tt = t.sort_values(["company_id", "period_end"])
    tt["true_F"] = tt.groupby("company_id")["true_shares"].transform(lambda s: s.iloc[-1] / s)
    f = factors.merge(tt, on=["company_id", "period_end"], how="inner")
    f_err = np.log(f["F"] / f["true_F"])
    return {
        "pairs": int(len(m)), "companies": int(m["company_id"].nunique()),
        "median_abs_err": float(np.exp(err.abs().median()) - 1),
        "share_within_5pct": float((err.abs() <= np.log(1.05)).mean()),
        "share_within_20pct": float((err.abs() <= np.log(1.2)).mean()),
        "factor_pairs": int(len(f)),
        "factor_exact_5pct": float((f_err.abs() <= np.log(1.05)).mean()),
        "factor_off_by_2x_or_more": float((f_err.abs() >= np.log(1.9)).mean()),
        "note": "true_F = latest true share count / true count at the period (includes genuine issuance, "
                "so small gaps are expected; only >= 2x gaps are split errors)",
    }
