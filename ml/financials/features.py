"""Point-in-time financial features from `financial_filings` (the Financial Model's inputs).

One feature row per (company, period_end), stamped with the filing_date of the filing that
reported that period. Every feature on a row is computed only from filings whose filing_date is
on or before the row's filing_date (the "visible" set), so the table can be joined as-of onto any
date panel without look-ahead.

Scope: `format = 'non_financial'` only. Banks, NBFCs and insurers report a different P&L/balance
sheet (interest earned, advances, deposits...) where margins, ROCE, current ratio and debt/equity
don't mean the same thing; they are left out until they get their own feature set.

Basis: consolidated is preferred over standalone for a period when both were filed. Series are
built separately per basis, so a growth rate never compares a consolidated quarter with a
standalone one (if a company only started filing consolidated this year, its YoY is NaN until a
consolidated year-ago period exists).

Quarterly series: the quarter P&L is the filing's `inc_*` block. When that is missing, it is derived
from year-to-date blocks within the same financial year (Q = YTD - previous YTD; e.g. Q3 = 9M - H1,
or Q3 = FY - H1 - Q4 when the December filing itself is missing). The FY end month is inferred per
company from its YTD blocks (March for almost everyone). Derived EPS is approximate when the share
count changed during the year.

Cash flow is only filed half-yearly (cumulative YTD): H1 = September YTD, H2 = March FY - H1.
Trailing cash flow at a September date = H1 + previous H2 = FY(prev) + H1 - H1(prev).

Conventions: money INR crore, ratios as fractions (0.12 = 12%), margin changes in fraction points.
Missing inputs give NaN (never 0). Divisions by ~0 give NaN, and growth from a zero/negative base
gives NaN plus a `*_neg_base` flag. Red flags are nullable booleans (NA when not computable).

CLI:  python3 -m financials.features --symbols KAYNES DIXON --out features.csv
"""

import argparse

import numpy as np
import pandas as pd

TABLE = "financial_filings"

# Additive P&L fields tracked in the quarterly grid (EPS is summed approximately)
PL_FIELDS = [
    "revenue", "other_income", "total_income", "finance_costs", "depreciation",
    "profit_before_exceptional", "exceptional_items", "profit_before_tax",
    "net_profit", "net_profit_owners", "eps_basic",
]
BS_FIELDS = [
    "total_assets", "current_assets", "current_liabilities", "trade_receivables",
    "total_equity", "total_debt", "cash_and_equivalents",
]
CF_FIELDS = ["operating_cf", "capex"]

P = {name: i for i, name in enumerate(PL_FIELDS)}
B = {name: i for i, name in enumerate(BS_FIELDS)}
CF = {name: i for i, name in enumerate(CF_FIELDS)}

TINY = 0.01          # crore (1 lakh) / rupee: anything smaller is treated as zero in a denominator

# Red-flag thresholds
RECEIVABLES_GAP = 0.25      # receivables YoY growth exceeds revenue TTM growth by 25+ points
DE_RISE = 0.5               # debt/equity up by 0.5+ in a year
LOW_COVERAGE = 1.5
# A balance sheet / cash flow more than 4 quarters older than the row's period is treated as missing
# (one skipped half-year is tolerated; older statements would silently forward-fill stale values)
MAX_STATEMENT_AGE_Q = 4

KEY_COLUMNS = ["company_id", "symbol", "filing_date", "period_end"]

FEATURES = [
    # growth
    "revenue_yoy", "net_profit_yoy", "eps_yoy",
    "revenue_ttm_growth", "net_profit_ttm_growth", "eps_ttm_growth",
    "revenue_yoy_accel", "net_profit_yoy_accel",
    # profitability
    "op_margin_q", "op_margin_ttm", "op_margin_change_yoy",
    "net_margin_ttm", "net_margin_change_yoy", "roe", "roce",
    # leverage / liquidity
    "debt_to_equity", "debt_to_equity_change_1y", "current_ratio", "interest_coverage_ttm",
    # cash-flow quality
    "ocf_ttm", "capex_ttm", "fcf_ttm", "cash_conversion", "accruals_ratio",
    "receivables_minus_revenue_growth",
    # size (context for the model)
    "revenue_ttm", "net_profit_ttm",
    # red flags
    "flag_profit_up_ocf_negative", "flag_receivables_outpacing_revenue", "flag_debt_to_equity_rising",
    "flag_negative_equity", "flag_low_interest_coverage",
    "revenue_neg_base", "net_profit_neg_base", "eps_neg_base",
    # staleness
    "days_since_period_end", "days_since_bs", "days_since_cf",
]
FLAG_FEATURES = [f for f in FEATURES if f.startswith("flag_") or f.endswith("_neg_base")]

NAN = np.nan


# ---------------------------------------------------------
# Loading
# ---------------------------------------------------------

def _load_raw(conn, symbols=None):
    """Every usable non_financial filing (both bases, all revisions), parse_status ok/partial."""

    columns = [
        "nse_seq_number", "company_id", "symbol", "statement_type", "format", "period_end",
        "months", "filing_date", "parse_status", "ytd_months", "cf_months",
        *[f"inc_{f}" for f in PL_FIELDS], *[f"ytd_{f}" for f in PL_FIELDS],
        *[f"bs_{f}" for f in BS_FIELDS], "bs_equity_owners", *[f"cf_{f}" for f in CF_FIELDS],
    ]
    sql = (f"SELECT {', '.join(columns)} FROM {TABLE} "
           "WHERE format = 'non_financial' AND parse_status <> 'failed' AND filing_date IS NOT NULL")
    params = None
    if symbols:
        symbols = [s.strip().upper() for s in symbols]
        sql += f" AND symbol IN ({', '.join(['%s'] * len(symbols))})"
        params = tuple(symbols)

    df = pd.read_sql(sql, conn, params=params)
    df["filing_date"] = pd.to_datetime(df["filing_date"])
    df["period_end"] = pd.to_datetime(df["period_end"])
    # DECIMAL columns arrive as object; make them float (None -> NaN)
    for col in df.columns:
        if col.startswith(("inc_", "ytd_", "bs_", "cf_")) or col in ("months",):
            df[col] = pd.to_numeric(df[col], errors="coerce").astype(float)
    # Filings with no company_id still get a stable key
    df["company_key"] = df["company_id"].fillna(-1).astype(int).astype(str) + ":" + df["symbol"]
    return df


def _pick_one(df):
    """One filing per (company, period_end): consolidated > standalone, then ok > partial,
    then the earliest filing (first time the numbers were public)."""

    ranked = df.assign(
        _basis=(df["statement_type"] != "consolidated").astype(int),
        _status=(df["parse_status"] != "ok").astype(int),
    ).sort_values(["company_key", "period_end", "_basis", "_status", "filing_date"])
    picked = ranked.drop_duplicates(["company_key", "period_end"], keep="first")
    return picked.drop(columns=["_basis", "_status"])


def load_filings(conn, symbols=None):
    """One row per (company, period_end) from `financial_filings`.

    non_financial format only (banks/NBFCs/insurers are excluded for now: their statements don't
    map onto margins/ROCE/debt-equity). Consolidated is preferred over standalone when both exist;
    among revisions the `ok` parse, then the earliest filing, wins. Failed parses are dropped.
    """

    return _pick_one(_load_raw(conn, symbols)).reset_index(drop=True)


# ---------------------------------------------------------
# Quarterly grid helpers
# ---------------------------------------------------------

def _quarter_ordinal(ts):
    """Quarter-end date -> integer (consecutive quarters differ by 1); None if not a quarter end."""

    if ts.month not in (3, 6, 9, 12) or not ts.is_month_end:
        return None
    return ts.year * 4 + (ts.month - 1) // 3


def _fy_end_month(rows):
    """Infer a company's financial-year end month from its YTD blocks (default March)."""

    votes = {}
    for month, ytd_months in zip(rows["period_end"].dt.month, rows["ytd_months"]):
        if ytd_months and not np.isnan(ytd_months) and ytd_months % 3 == 0:
            end = (month - int(ytd_months) - 1) % 12 + 1
            votes[end] = votes.get(end, 0) + 1
    return max(votes, key=votes.get) if votes else 3


def _fill(a, b):
    """Where a is NaN, take b (in place). Returns a."""

    mask = np.isnan(a)
    a[mask] = b[mask]
    return a


def _div(num, den, positive_den=True):
    if num is None or den is None or np.isnan(num) or np.isnan(den):
        return NAN
    if positive_den and den <= TINY:
        return NAN
    if abs(den) <= TINY:
        return NAN
    return num / den


def _growth(cur, prev):
    """(cur/prev - 1, neg_base flag). prev <= 0 -> NaN and flag True; prev ~0 -> NaN."""

    if np.isnan(cur) or np.isnan(prev):
        return NAN, pd.NA
    if prev <= 0:
        return NAN, True
    if prev <= TINY:
        return NAN, False
    return cur / prev - 1.0, False


class _Company:
    """Point-in-time state of one company on one basis, fed filings in filing_date order."""

    def __init__(self, fy_end_month):
        self.E = fy_end_month
        self.visible = {}          # qo -> record (latest filed wins)
        self.fy_cache = {}         # fy first qo -> (Q dict, C dict)

    def k_of(self, qo):
        month = (qo % 4) * 3 + 3
        return ((month - self.E - 1) % 12) // 3 + 1

    def fy_of(self, qo):
        return qo - self.k_of(qo) + 1

    def add(self, qo, rec):
        self.visible[qo] = rec
        self.fy_cache.pop(self.fy_of(qo), None)

    # --- P&L grid --------------------------------------------------------
    def _fy(self, f):
        if f in self.fy_cache:
            return self.fy_cache[f]
        n = len(PL_FIELDS)
        Q, C = {}, {}
        for k in range(1, 5):
            qo = f + k - 1
            q = np.full(n, NAN)
            c = np.full(n, NAN)
            rec = self.visible.get(qo)
            if rec is not None:
                if rec["inc_months"] == 3:
                    q = rec["inc"].copy()
                elif rec["inc_months"] == 3 * k:
                    c = rec["inc"].copy()
                if rec["ytd_months"] == 3 * k:
                    _fill(c, rec["ytd"])
            Q[qo], C[k] = q, c
        zero = np.zeros(n)
        for _ in range(3):             # small fixpoint: Q_k = C_k - C_{k-1}
            for k in range(1, 5):
                prev = zero if k == 1 else C[k - 1]
                q, c = Q[f + k - 1], C[k]
                _fill(q, c - prev)
                _fill(c, prev + q)
                if k > 1:
                    _fill(C[k - 1], c - q)
        self.fy_cache[f] = (Q, C)
        return Q, C

    def q(self, qo):
        Q, _ = self._fy(self.fy_of(qo))
        return Q[qo]

    def ttm(self, qo):
        parts = [self.q(qo - i) for i in range(4)]
        out = parts[0] + parts[1] + parts[2] + parts[3]
        f, k = self.fy_of(qo), self.k_of(qo)
        _, C = self._fy(f)
        if k == 4:
            return _fill(out, C[4])
        _, C_prev = self._fy(f - 4)
        return _fill(out, C_prev[4] + C[k] - C_prev[k])

    # --- balance sheet / cash flow ----------------------------------------
    def latest(self, key, upto_qo, max_age=None):
        """Latest visible qo <= upto_qo (and >= upto_qo - max_age) whose record has block `key`."""

        best = None
        for qo, rec in self.visible.items():
            if qo <= upto_qo and rec[key] is not None and (best is None or qo > best):
                best = qo
        if best is not None and max_age is not None and best < upto_qo - max_age:
            return None
        return best

    def bs(self, qo):
        rec = self.visible.get(qo)
        return None if rec is None else rec["bs"]

    def cf_ytd(self, qo, months):
        rec = self.visible.get(qo)
        if rec is None or rec["cf"] is None or rec["cf_months"] != months:
            return None
        return rec["cf"]

    def half_years(self, f):
        """(H1, H2) cash-flow arrays of FY starting at quarter f (None when unknown)."""

        h1 = self.cf_ytd(f + 1, 6)
        fy = self.cf_ytd(f + 3, 12)
        h2 = fy - h1 if (fy is not None and h1 is not None) else None
        return h1, h2

    def cf_ttm(self, c):
        """Trailing-12-month cash flow as of cash-flow date c, plus the last two half-years."""

        f, k = self.fy_of(c), self.k_of(c)
        if k == 4 and self.cf_ytd(c, 12) is not None:
            h1, h2 = self.half_years(f)
            return self.cf_ytd(c, 12), (h2, h1)
        if k == 2 and self.cf_ytd(c, 6) is not None:
            h1 = self.cf_ytd(c, 6)
            _, h2_prev = self.half_years(f - 4)
            ttm = h1 + h2_prev if h2_prev is not None else None
            return ttm, (h1, h2_prev)
        return None, (None, None)


def _record(row):
    eq_owners = row.get("bs_equity_owners", NAN)       # only read by the opt-in ROE fallback
    eq_owners = NAN if eq_owners is None or pd.isna(eq_owners) else float(eq_owners)
    has_bs = not (np.isnan(row["bs_total_assets"]) and np.isnan(row["bs_total_equity"]))
    has_cf = not np.isnan(row["cf_operating_cf"]) and row["cf_months"] in (6, 12)
    ytd_months = row["ytd_months"]
    return {
        "inc": np.array([row[f"inc_{f}"] for f in PL_FIELDS], dtype=float),
        "inc_months": int(row["months"]) if not np.isnan(row["months"]) else None,
        "ytd": np.array([row[f"ytd_{f}"] for f in PL_FIELDS], dtype=float),
        "ytd_months": int(ytd_months) if not np.isnan(ytd_months) else None,
        "bs": np.array([row[f"bs_{f}"] for f in BS_FIELDS], dtype=float) if has_bs else None,
        "cf": np.array([row[f"cf_{f}"] for f in CF_FIELDS], dtype=float) if has_cf else None,
        "cf_months": int(row["cf_months"]) if has_cf else None,
        "eq_owners": eq_owners,
    }


def _qo_to_date(qo):
    year, idx = divmod(qo, 4)
    return pd.Timestamp(year=year, month=idx * 3 + 3, day=1) + pd.offsets.MonthEnd(0)


# ---------------------------------------------------------
# Features
# ---------------------------------------------------------

def _features(st, r, filing_date, period_end, roe_owners_fallback=False):
    out = {}
    qr, qr4 = st.q(r), st.q(r - 4)
    qr1, qr5 = st.q(r - 1), st.q(r - 5)
    t, t4 = st.ttm(r), st.ttm(r - 4)

    def ebit(a):
        return a[P["profit_before_tax"]] + a[P["finance_costs"]]

    # Growth
    for name, field in (("revenue", "revenue"), ("net_profit", "net_profit"), ("eps", "eps_basic")):
        i = P[field]
        out[f"{name}_yoy"], out[f"{name}_neg_base"] = _growth(qr[i], qr4[i])
        out[f"{name}_ttm_growth"], neg_ttm = _growth(t[i], t4[i])
        if neg_ttm is True:
            out[f"{name}_neg_base"] = True
    for name, field in (("revenue", "revenue"), ("net_profit", "net_profit")):
        i = P[field]
        prev_yoy, _ = _growth(qr1[i], qr5[i])
        out[f"{name}_yoy_accel"] = out[f"{name}_yoy"] - prev_yoy

    # Profitability
    rev_i, np_i = P["revenue"], P["net_profit"]
    out["op_margin_q"] = _div(ebit(qr), qr[rev_i])
    out["op_margin_ttm"] = _div(ebit(t), t[rev_i])
    out["op_margin_change_yoy"] = out["op_margin_q"] - _div(ebit(qr4), qr4[rev_i])
    out["net_margin_ttm"] = _div(t[np_i], t[rev_i])
    out["net_margin_change_yoy"] = out["net_margin_ttm"] - _div(t4[np_i], t4[rev_i])
    out["revenue_ttm"], out["net_profit_ttm"] = t[rev_i], t[np_i]
    ebit_ttm, fin_ttm = ebit(t), t[P["finance_costs"]]
    out["interest_coverage_ttm"] = _div(ebit_ttm, fin_ttm)

    # Balance sheet (latest visible one at or before this period)
    b = st.latest("bs", r, MAX_STATEMENT_AGE_Q)
    for key in ("roe", "roce", "debt_to_equity", "debt_to_equity_change_1y", "current_ratio",
                "receivables_minus_revenue_growth"):
        out[key] = NAN
    out["flag_negative_equity"] = pd.NA
    out["flag_debt_to_equity_rising"] = pd.NA
    out["flag_receivables_outpacing_revenue"] = pd.NA
    out["days_since_bs"] = NAN
    if b is not None:
        bs = st.bs(b)
        eq, debt = bs[B["total_equity"]], bs[B["total_debt"]]
        out["days_since_bs"] = (filing_date - _qo_to_date(b)).days
        if not np.isnan(eq):
            out["flag_negative_equity"] = bool(eq < 0)
        prior = next((st.bs(b - lag) for lag in (4, 2) if st.bs(b - lag) is not None), None)
        eq_avg = eq if prior is None or np.isnan(prior[B["total_equity"]]) else (eq + prior[B["total_equity"]]) / 2
        out["roe"] = _div(t[np_i], eq_avg)
        out["roce"] = _div(ebit_ttm, eq + debt)
        out["debt_to_equity"] = _div(debt, eq)
        out["current_ratio"] = _div(bs[B["current_assets"]], bs[B["current_liabilities"]])
        bs_prev = st.bs(b - 4)
        if bs_prev is not None:
            de_prev = _div(bs_prev[B["total_debt"]], bs_prev[B["total_equity"]])
            out["debt_to_equity_change_1y"] = out["debt_to_equity"] - de_prev
            if not np.isnan(out["debt_to_equity_change_1y"]):
                out["flag_debt_to_equity_rising"] = bool(out["debt_to_equity_change_1y"] >= DE_RISE)
            recv_g, _ = _growth(bs[B["trade_receivables"]], bs_prev[B["trade_receivables"]])
            rev_g, _ = _growth(st.ttm(b)[rev_i], st.ttm(b - 4)[rev_i])
            out["receivables_minus_revenue_growth"] = recv_g - rev_g
            if not np.isnan(out["receivables_minus_revenue_growth"]):
                out["flag_receivables_outpacing_revenue"] = bool(out["receivables_minus_revenue_growth"] > RECEIVABLES_GAP)

    if roe_owners_fallback and (b is None or np.isnan(st.bs(b)[B["total_equity"]])):
        out["roe"] = _roe_owners(st, r, b, t)

    # Cash-flow quality (latest visible cash-flow statement at or before this period)
    for key in ("ocf_ttm", "capex_ttm", "fcf_ttm", "cash_conversion", "accruals_ratio", "days_since_cf"):
        out[key] = NAN
    out["flag_profit_up_ocf_negative"] = pd.NA
    c = st.latest("cf", r, MAX_STATEMENT_AGE_Q)
    if c is not None:
        out["days_since_cf"] = (filing_date - _qo_to_date(c)).days
        cf, halves = st.cf_ttm(c)
        if cf is not None:
            ocf = cf[CF["operating_cf"]]
            out["ocf_ttm"], out["capex_ttm"] = ocf, cf[CF["capex"]]
            out["fcf_ttm"] = ocf - cf[CF["capex"]]
            np_c = st.ttm(c)[np_i]
            out["cash_conversion"] = _div(ocf, np_c)
            bs_c = st.bs(st.latest("bs", c)) if st.latest("bs", c) is not None else None
            if bs_c is not None:
                out["accruals_ratio"] = _div(np_c - ocf, bs_c[B["total_assets"]])
        h_ocf = [h[CF["operating_cf"]] if h is not None else NAN for h in halves]
        np_g = st.ttm(c)[np_i] - st.ttm(c - 4)[np_i]
        if not (np.isnan(h_ocf[0]) or np.isnan(h_ocf[1]) or np.isnan(np_g)):
            out["flag_profit_up_ocf_negative"] = bool(np_g > 0 and h_ocf[0] < 0 and h_ocf[1] < 0)

    ic = out["interest_coverage_ttm"]
    out["flag_low_interest_coverage"] = pd.NA if np.isnan(ic) else bool(ic < LOW_COVERAGE)
    out["days_since_period_end"] = (filing_date - period_end).days
    return out


def _roe_owners(st, r, b, t):
    """Opt-in ROE fallback for a balance sheet without total equity (default code never calls it).

    Legacy consolidated annual rows (period end < Sep 2022) carry owners' equity but no total
    equity (NCI unknown). ROE = TTM profit attributable to owners (net profit when not filed) /
    owners' equity of the latest visible statement within MAX_STATEMENT_AGE_Q quarters that has it
    (never older than the latest balance sheet `b`), averaged with the owners' equity 4 (else 2)
    quarters earlier when filed. Only rows whose total-equity ROE is NaN are touched.
    """

    has = [qo for qo, rec in st.visible.items()
           if qo <= r and not np.isnan(rec["eq_owners"]) and qo >= r - MAX_STATEMENT_AGE_Q]
    if not has:
        return NAN
    bo = max(has)
    if b is not None and bo < b:
        return NAN
    eq = st.visible[bo]["eq_owners"]
    prior = next((st.visible[bo - lag]["eq_owners"] for lag in (4, 2)
                  if bo - lag in st.visible and not np.isnan(st.visible[bo - lag]["eq_owners"])), NAN)
    eq_avg = eq if np.isnan(prior) else (eq + prior) / 2
    num = t[P["net_profit_owners"]]
    return _div(t[P["net_profit"]] if np.isnan(num) else num, eq_avg)


def _company_features(rows, roe_owners_fallback=False):
    """Features for every filing of one company on one basis (rows sorted by filing_date)."""

    st = _Company(_fy_end_month(rows))
    results = []
    records = rows.to_dict("records")
    i = 0
    while i < len(records):
        # All filings with the same filing_date become visible together
        j = i
        while j < len(records) and records[j]["filing_date"] == records[i]["filing_date"]:
            j += 1
        batch = records[i:j]
        for row in batch:
            qo = _quarter_ordinal(row["period_end"])
            if qo is not None:
                st.add(qo, _record(row))
        for row in batch:
            qo = _quarter_ordinal(row["period_end"])
            if qo is None:
                continue
            feats = _features(st, qo, row["filing_date"], row["period_end"], roe_owners_fallback)
            feats["nse_seq_number"] = row["nse_seq_number"]
            results.append(feats)
        i = j
    return results


def compute_features(raw, roe_owners_fallback=False):
    """Features at every raw filing (per company and basis); keyed by nse_seq_number.

    roe_owners_fallback (opt-in, default False = unchanged output): when a balance sheet has no
    total equity, ROE uses owners' equity (`bs_equity_owners`) and owners' TTM profit instead of
    staying NaN. Tested in financial_model/RETRAIN_2026-10.md.
    """

    results = []
    raw = raw.sort_values(["company_key", "statement_type", "filing_date", "nse_seq_number"])
    for _, rows in raw.groupby(["company_key", "statement_type"], sort=False):
        results.extend(_company_features(rows, roe_owners_fallback))
    return pd.DataFrame(results, columns=["nse_seq_number", *FEATURES])


def build_feature_table(conn, symbols=None, raw=None, roe_owners_fallback=False):
    """Point-in-time feature table keyed by (company_id, symbol, filing_date, period_end).

    `raw` (the output of `_load_raw`) can be passed instead of a connection, e.g. for tests.
    """

    if raw is None:
        raw = _load_raw(conn, symbols)
    feats = compute_features(raw, roe_owners_fallback)
    picked = _pick_one(raw)[["nse_seq_number", *KEY_COLUMNS, "statement_type"]]
    table = picked.merge(feats, on="nse_seq_number", how="inner")
    for col in FLAG_FEATURES:
        table[col] = table[col].astype("boolean")
    return table.sort_values(["symbol", "period_end"]).reset_index(drop=True)


# ---------------------------------------------------------
# CLI
# ---------------------------------------------------------

def summarize(table):
    print(f"rows: {len(table)}   companies: {table['company_id'].nunique()}   "
          f"period_end: {table['period_end'].min():%Y-%m-%d} .. {table['period_end'].max():%Y-%m-%d}")
    print("% non-null per feature:")
    coverage = table[FEATURES].notna().mean().mul(100).round(1)
    width = max(len(f) for f in FEATURES)
    for name, value in coverage.items():
        print(f"  {name:<{width}}  {value:5.1f}")


def main(argv=None):
    parser = argparse.ArgumentParser(description="Build point-in-time financial features.")
    parser.add_argument("--symbols", nargs="*", help="NSE symbols (default: all)")
    parser.add_argument("--out", help="write the feature table to this CSV")
    args = parser.parse_args(argv)

    import warnings
    warnings.filterwarnings("ignore", message="pandas only supports SQLAlchemy")
    from news_pipeline.db import get_connection

    conn = get_connection()
    try:
        table = build_feature_table(conn, args.symbols)
    finally:
        conn.close()

    summarize(table)
    if args.out:
        table.to_csv(args.out, index=False)
        print(f"wrote {args.out}")


if __name__ == "__main__":
    main()
