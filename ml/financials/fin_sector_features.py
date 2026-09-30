"""Point-in-time features for banks, NBFCs and insurers (the financial sector's Financial Model inputs).

features.py covers `format = 'non_financial'` filings only; lenders and insurers report a P&L and
balance sheet where margins, ROCE, current ratio and debt/equity don't mean the same thing. This
module gives them their own feature set, with exactly the same point-in-time conventions:

    One feature row per (company, period_end), stamped with the filing_date of the filing that
    reported that period. Every feature on a row is computed only from filings whose filing_date is
    on or before the row's filing_date (the "visible" set; later revisions of a period replace
    earlier ones only once they are filed), so the table can be joined as-of onto any date panel
    without look-ahead. `check_point_in_time` proves it by recomputing sampled rows from a
    truncated filing history.

Scope: companies whose filings are mostly in the bank / nbfc / insurance formats (company format
= the most common lender format among its parsed filings; companies with fewer than half of their
parsed filings in a lender format stay with features.py). Every filing of an in-scope company is
used, including the odd quarter detected as non_financial (its fin_sector lines are parsed with the
company's format).

Data: the lender lines (interest earned/expended, provisions, NPAs, CET1, advances, deposits,
premiums, solvency...) are the parser's new `fin_sector` block, which `financial_filings` has no
columns for yet. Until it is backfilled, `extract` re-parses the cached XBRL of the in-scope filings
(ml/data/raw/xbrl/<SYMBOL>/<seq>.xml) into ml/data/processed/fin_sector_filings.pkl; the only
things read from the database are each filing's listing metadata (company_id, symbol, filing_date).
The DB is never written.

Basis: consolidated is preferred over standalone for a period when both were filed. Series are
built separately per basis (a growth rate never compares a consolidated quarter with a standalone
one). Quarterly flows come from the filing's quarter block, or are derived from year-to-date blocks
(Q = YTD - previous YTD), with the same grid as features.py (it reuses features._Company). One
deviation: an old June filing whose only P&L context has no start date (131 bank/NBFC filings,
2018-2021) is taken as the 3-month Q1, since a first-quarter period can't be anything else.

Definitions (TTM = sum of the last four quarters; "avg" = mean of the balance sheet at b and a
year (else half a year) earlier, where b is the latest visible balance sheet at or before the
row's period, at most 4 quarters old; balance sheets are in the XBRL only from Sep 2022):
    net_revenue       bank/NBFC: total income - interest expended (= NII + fees + other income);
                      insurer: net premium
    nii               interest earned - interest expended (NBFC: finance costs)
    ppop              pre-provision operating profit (bank: filed; NBFC: profit before exceptional
                      items and tax + impairment on financial instruments)
    provisions        bank: provisions and contingencies (ex tax); NBFC: impairment on financial
                      instruments (ECL)
    *_yoy, *_ttm_growth   quarter vs same quarter a year ago; TTM vs TTM a year ago
    nim               NII TTM / avg total assets   (a NIM proxy: assets, not interest-earning assets)
    cost_to_income_ttm    operating expenses TTM / net_revenue TTM
    credit_cost       provisions TTM / avg advances (loans);  credit_cost_to_income_ttm = / net_revenue
    roa, roe          net profit TTM / avg total assets, / avg net worth
    leverage          total assets / net worth (banks, NBFCs)
    gross_npa_pct, net_npa_pct, cet1_ratio, roa_reported  as filed by banks (as of the period end);
                      provision_coverage = 1 - net NPA / gross NPA; *_change_1y in fraction points
    loan_to_deposit   advances / deposits (banks)
    loans_to_assets   advances / total assets: separates lending NBFCs (~0.8) from brokers, AMCs
                      and holding companies that also file the NBFC format (~0-0.3)
    claims_ratio, combined_ratio, solvency_ratio  as filed by (non-life) insurers
Red flags (nullable booleans):
    flag_asset_quality_worsening  gross NPA up >= 0.5 pt in a year, or provisions / net revenue
                                  (TTM) up >= 10 pts in a year
    flag_roa_collapse             ROA (else net profit TTM) below half of a year ago, or turned
                                  negative from positive
    flag_capital_near_minimum     bank CET1 < 9% (RBI minimum 8% incl. conservation buffer);
                                  insurer solvency < 1.7x (IRDAI minimum 1.5x); NBFC: NA (their
                                  capital adequacy is not in the XBRL)
    flag_negative_equity; *_neg_base (growth from a zero/negative base -> NaN + flag)

Conventions: money INR crore, ratios as fractions (0.12 = 12%). Missing inputs give NaN (never 0).
Divisions by ~0 give NaN. Bank NPA / CET1 fields that consolidated filings leave as 0.00 are
None in the parser, so NaN here.

CLI:  python3 -m financials.fin_sector_features --symbols HDFCBANK BAJFINANCE --out fin.csv
      python3 -m financials.fin_sector_features --refresh-extract --check 300 --out fin.csv
      python3 -m financials.fin_sector_features --push-db      # refresh the DB copy CI reads
"""

import argparse
import json
import time
from multiprocessing import Pool
from pathlib import Path

import numpy as np
import pandas as pd

from .config import ML_DIR, XBRL_CACHE_DIR
from .features import (MAX_STATEMENT_AGE_Q, TINY, _Company, _div, _fill, _fy_end_month, _growth,
                       _pick_one, _qo_to_date, _quarter_ordinal)
from .store import BALANCE_SHEET_FIELDS, INCOME_FIELDS, parse_status
from .xbrl_parse import FIN_BALANCE_TAGS, FIN_FLOW_TAGS, LENDER_FORMATS, parse_xbrl

TABLE = "financial_filings"
EXTRACT_FILE = ML_DIR / "data" / "processed" / "fin_sector_filings.pkl"
MIN_LENDER_SHARE = 0.5

# fin_sector block keys (flows / point-in-time / balance sheet), union over the three formats
FS_FLOW_KEYS = sorted({k for tags in FIN_FLOW_TAGS.values() for k in tags}
                      | {"net_interest_income", "operating_expenses", "pre_provision_profit"})
FS_PIT_KEYS = ["gross_npa_pct", "net_npa_pct", "cet1_ratio", "at1_ratio", "roa_reported",
               "gross_npa", "net_npa", "claims_ratio", "combined_ratio", "solvency_ratio"]
FS_BS_KEYS = sorted({k for tags in FIN_BALANCE_TAGS.values() for k in tags} | {"net_worth"})

# Quarterly grid (additive flows)
PL_FIELDS = [
    "net_revenue", "interest_income", "interest_expense", "nii", "operating_expenses", "ppop",
    "provisions", "net_profit", "eps_basic", "net_premium",
]
PIT_FIELDS = ["gross_npa_pct", "net_npa_pct", "gross_npa", "net_npa", "cet1_ratio", "roa_reported",
              "claims_ratio", "combined_ratio", "solvency_ratio"]
BS_FIELDS = ["total_assets", "net_worth", "advances", "deposits"]
P = {name: i for i, name in enumerate(PL_FIELDS)}
Q = {name: i for i, name in enumerate(PIT_FIELDS)}
B = {name: i for i, name in enumerate(BS_FIELDS)}

# Red-flag thresholds
GNPA_RISE = 0.005            # gross NPA up 0.5 pt in a year
CREDIT_COST_RISE = 0.10      # provisions / net revenue up 10 pts in a year
ROA_COLLAPSE = 0.5           # below half of a year ago
CET1_NEAR_MIN = 0.09         # RBI: CET1 5.5% + 2.5% conservation buffer = 8%
SOLVENCY_NEAR_MIN = 1.7      # IRDAI: 1.5x

KEY_COLUMNS = ["company_id", "symbol", "filing_date", "period_end"]

FEATURES = [
    # growth
    "net_revenue_yoy", "net_revenue_ttm_growth", "nii_yoy", "nii_ttm_growth",
    "ppop_yoy", "ppop_ttm_growth", "net_profit_yoy", "net_profit_ttm_growth", "net_profit_yoy_accel",
    "eps_ttm_growth", "advances_growth_1y", "deposits_growth_1y",
    # profitability / efficiency
    "nim", "cost_to_income_ttm", "credit_cost", "credit_cost_to_income_ttm", "roa", "roe", "roa_reported",
    # capital / leverage / funding
    "leverage", "cet1_ratio", "cet1_change_1y", "solvency_ratio", "loan_to_deposit", "loans_to_assets",
    # asset quality (banks)
    "gross_npa_pct", "net_npa_pct", "gross_npa_change_1y", "net_npa_change_1y", "provision_coverage",
    # insurers
    "claims_ratio", "combined_ratio",
    # size
    "net_revenue_ttm", "net_profit_ttm", "total_assets",
    # red flags
    "flag_asset_quality_worsening", "flag_roa_collapse", "flag_capital_near_minimum",
    "flag_negative_equity",
    "net_revenue_neg_base", "nii_neg_base", "ppop_neg_base", "net_profit_neg_base",
    # staleness
    "days_since_period_end", "days_since_bs",
]
FLAG_FEATURES = [f for f in FEATURES if f.startswith("flag_") or f.endswith("_neg_base")]

NAN = np.nan


# ---------------------------------------------------------
# Extract: re-parse the cached XBRL of in-scope filings
# ---------------------------------------------------------

def load_listing(conn, symbols=None):
    """Listing metadata of every filing of companies with any bank/nbfc/insurance filing, plus
    each company's lender format. SELECT only."""

    sql = (f"SELECT nse_seq_number, company_id, symbol, statement_type, format, period_end, filing_date, "
           f"parse_status FROM {TABLE} WHERE symbol IN "
           f"(SELECT DISTINCT symbol FROM {TABLE} WHERE format IN ('bank', 'nbfc', 'insurance'))")
    params = None
    if symbols:
        symbols = [s.strip().upper() for s in symbols]
        sql += f" AND symbol IN ({', '.join(['%s'] * len(symbols))})"
        params = tuple(symbols)
    meta = pd.read_sql(sql, conn, params=params)
    meta["filing_date"] = pd.to_datetime(meta["filing_date"])

    # A company's lender format: most common among its usable lender filings. Failed 'bank' rows
    # are 2018 old-GAAP files whose schema name "other_than_banks" contains "bank"; they are not
    # evidence of a bank. Insurers' filings all failed before the parser learnt their P&L.
    usable = meta[meta["format"].isin(LENDER_FORMATS)
                  & ((meta["parse_status"] != "failed") | (meta["format"] == "insurance"))]
    fmt = usable.groupby("symbol")["format"].agg(lambda s: s.value_counts().index[0])
    meta["company_format"] = meta["symbol"].map(fmt)
    return meta[meta["company_format"].notna() & meta["filing_date"].notna()].reset_index(drop=True)


def _flatten(parsed):
    row = {"p_format": parsed.get("format"), "p_statement_type": parsed.get("statement_type"),
           "p_period_end": parsed.get("period_end"), "months": parsed.get("months"),
           "p_parse_status": parse_status(parsed)}
    for section, prefix in (("income", "inc_"), ("income_ytd", "ytd_")):
        block = parsed.get(section) or {}
        for field in INCOME_FIELDS:
            row[prefix + field] = block.get(field)
    row["ytd_months"] = (parsed.get("income_ytd") or {}).get("months")
    sheet = parsed.get("balance_sheet") or {}
    for field in BALANCE_SHEET_FIELDS:
        row["bs_" + field] = sheet.get(field)
    fs = parsed.get("fin_sector") or {}
    quarter, ytd, fs_sheet = fs.get("quarter") or {}, fs.get("ytd") or {}, fs.get("balance_sheet") or {}
    for key in FS_FLOW_KEYS:
        row["fsq_" + key] = quarter.get(key)
        row["fsy_" + key] = ytd.get(key)
    row["fsy_months"] = ytd.get("months")
    for key in FS_PIT_KEYS:
        row["fsq_" + key] = quarter.get(key)
    for key in FS_BS_KEYS:
        row["fsb_" + key] = fs_sheet.get(key)
    row["fs_warnings"] = len(fs.get("warnings") or [])
    return row


def _parse_one(job):
    seq, symbol, company_format = job
    path = XBRL_CACHE_DIR / symbol / f"{seq}.xml"
    if not path.exists():
        return {"nse_seq_number": seq, "extract_status": "not_cached"}
    try:
        parsed = parse_xbrl(path.read_bytes(), fin_sector_format=company_format)
    except ValueError as error:
        return {"nse_seq_number": seq, "extract_status": f"error: {error}"[:120]}
    return {"nse_seq_number": seq, "extract_status": "ok", **_flatten(parsed)}


def extract(meta, processes=8):
    """Parse every listed filing from the XBRL cache (no network) -> one row per nse_seq_number."""

    jobs = list(zip(meta["nse_seq_number"].astype(int), meta["symbol"], meta["company_format"]))
    with Pool(processes) as pool:
        rows = pool.map(_parse_one, jobs, chunksize=20)
    parsed = pd.DataFrame(rows)
    out = meta.merge(parsed, on="nse_seq_number", how="left")
    # Lender share per company (among filings that parsed): companies mostly filing the
    # non-financial format stay with features.py
    ok = out[out["p_parse_status"].isin(["ok", "partial"])]
    share = ok.groupby("symbol")["p_format"].apply(lambda s: s.isin(LENDER_FORMATS).mean())
    out["lender_share"] = out["symbol"].map(share)
    return out


def load_extract(conn=None, symbols=None, refresh=False):
    if refresh or not EXTRACT_FILE.exists():
        if conn is None:
            raise ValueError("no extract file yet: pass a DB connection (or run the CLI once)")
        t0 = time.time()
        table = extract(load_listing(conn))
        EXTRACT_FILE.parent.mkdir(parents=True, exist_ok=True)
        table.to_pickle(EXTRACT_FILE)
        print(f"extract: {len(table):,} filings of {table['symbol'].nunique()} companies re-parsed "
              f"in {time.time() - t0:.0f}s -> {EXTRACT_FILE}")
    table = pd.read_pickle(EXTRACT_FILE)
    if symbols:
        table = table[table["symbol"].isin([s.strip().upper() for s in symbols])]
    return table


# The XBRL cache only exists on the Mac that downloaded it, so the extract is also pushed to a small
# DB table (one JSON row per filing) that CI (rankings workflow) reads when the local file is absent.
DB_TABLE = "fin_sector_extract"
DB_TABLE_SQL = f"""
CREATE TABLE IF NOT EXISTS {DB_TABLE} (
    nse_seq_number BIGINT NOT NULL PRIMARY KEY,
    symbol VARCHAR(50) NOT NULL,
    data JSON NOT NULL,
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
)"""


def push_extract(conn, table, batch=500):
    """Replace the DB copy of the extract with `table` (whole-table swap in one transaction)."""

    records = json.loads(table.to_json(orient="records", date_format="iso"))
    cur = conn.cursor()
    try:
        cur.execute(DB_TABLE_SQL)
        cur.execute(f"DELETE FROM {DB_TABLE}")
        rows = [(r["nse_seq_number"], r["symbol"], json.dumps(r)) for r in records]
        for i in range(0, len(rows), batch):
            cur.executemany(f"INSERT INTO {DB_TABLE} (nse_seq_number, symbol, data) VALUES (%s, %s, %s)",
                            rows[i:i + batch])
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        cur.close()
    return len(rows)


def load_extract_db(conn):
    """-> the extract table from the DB copy, same dtypes as the pickle, or None if not pushed yet."""

    cur = conn.cursor()
    try:
        cur.execute(f"SHOW TABLES LIKE '{DB_TABLE}'")
        if not cur.fetchall():
            return None
        cur.execute(f"SELECT data FROM {DB_TABLE} ORDER BY nse_seq_number")
        records = [json.loads(d) if isinstance(d, (str, bytes)) else d for (d,) in cur.fetchall()]
    finally:
        cur.close()
    if not records:
        return None
    table = pd.DataFrame(records)
    table["filing_date"] = pd.to_datetime(table["filing_date"]).dt.tz_localize(None)
    table["period_end"] = pd.to_datetime(table["period_end"]).dt.date
    return table


def raw_from_extract(table):
    """In-scope, usable filings in the layout the feature code expects."""

    df = table[(table["extract_status"] == "ok") & table["p_parse_status"].isin(["ok", "partial"])
               & (table["lender_share"] >= MIN_LENDER_SHARE)].copy()
    df["period_end"] = pd.to_datetime(df["p_period_end"].fillna(df["period_end"].astype(str)))
    df["statement_type"] = df["p_statement_type"].fillna(df["statement_type"])
    df = df[df["statement_type"].isin(["consolidated", "standalone"])]
    df["parse_status"] = df["p_parse_status"]
    for col in df.columns:
        if col.startswith(("inc_", "ytd_", "bs_", "fsq_", "fsy_", "fsb_")) or col == "months":
            df[col] = pd.to_numeric(df[col], errors="coerce").astype(float)
    df = df.copy()
    df["company_key"] = df["company_id"].fillna(-1).astype(int).astype(str) + ":" + df["symbol"]
    return df.reset_index(drop=True)


# ---------------------------------------------------------
# Quarterly grid (features._Company with this module's P&L fields)
# ---------------------------------------------------------

class _FinCompany(_Company):
    """features._Company (visible set, FY grid, TTM, latest statement) over PL_FIELDS above."""

    def _fy(self, f):
        if f in self.fy_cache:
            return self.fy_cache[f]
        n = len(PL_FIELDS)
        Qd, C = {}, {}
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
            Qd[qo], C[k] = q, c
        zero = np.zeros(n)
        for _ in range(3):             # same fixpoint as features._Company._fy
            for k in range(1, 5):
                prev = zero if k == 1 else C[k - 1]
                q, c = Qd[f + k - 1], C[k]
                _fill(q, c - prev)
                _fill(c, prev + q)
                if k > 1:
                    _fill(C[k - 1], c - q)
        self.fy_cache[f] = (Qd, C)
        return Qd, C

    def pit(self, qo):
        rec = self.visible.get(qo)
        return None if rec is None else rec["pit"]


def _flows(row, prefix, fs_prefix, company_format):
    def g(col):
        return row.get(col, NAN)

    if company_format == "insurance":
        net_revenue = g(fs_prefix + "net_premium")
    else:
        net_revenue = g(fs_prefix + "total_income") - g(fs_prefix + "interest_expense")
    values = {
        "net_revenue": net_revenue,
        "interest_income": g(fs_prefix + "interest_income"),
        "interest_expense": g(fs_prefix + "interest_expense"),
        "nii": g(fs_prefix + "net_interest_income"),
        "operating_expenses": g(fs_prefix + "operating_expenses"),
        "ppop": g(fs_prefix + "pre_provision_profit"),
        "provisions": g(fs_prefix + "provisions"),
        "net_profit": g(prefix + "net_profit"),
        "eps_basic": g(prefix + "eps_basic"),
        "net_premium": g(fs_prefix + "net_premium"),
    }
    return np.array([values[f] for f in PL_FIELDS], dtype=float)


def _record(row, qo, st):
    months = None if np.isnan(row["months"]) else int(row["months"])
    ytd_months = row["ytd_months"]
    ytd_months = None if ytd_months is None or np.isnan(ytd_months) else int(ytd_months)
    fsy_months = row.get("fsy_months", NAN)
    if months is None and ytd_months is None and st.k_of(qo) == 1:
        months = 3          # old single-context June filing (see module docstring)

    net_worth = row["fsb_net_worth"] if not np.isnan(row["fsb_net_worth"]) else row["bs_total_equity"]
    bs = np.array([row["bs_total_assets"], net_worth, row["fsb_advances"], row["fsb_deposits"]], dtype=float)
    has_bs = not np.all(np.isnan(bs))
    fmt = row["company_format"]
    return {
        "fd": row["filing_date"],
        "inc": _flows(row, "inc_", "fsq_", fmt),
        "inc_months": months,
        "ytd": _flows(row, "ytd_", "fsy_", fmt),
        # the fin_sector YTD block and the main one come from the same context
        "ytd_months": ytd_months if ytd_months is not None else (
            None if fsy_months is None or np.isnan(fsy_months) else int(fsy_months)),
        "pit": np.array([row.get("fsq_" + f, NAN) for f in PIT_FIELDS], dtype=float),
        "bs": bs if has_bs else None,
        # unused by the grid but required by features._Company.latest()
        "cf": None,
    }


# ---------------------------------------------------------
# Features
# ---------------------------------------------------------

def _avg(now, prior):
    if prior is None or np.isnan(prior):
        return now
    return (now + prior) / 2


def _features(st, r, filing_date, period_end, company_format):
    out = {}
    qr, qr4, qr1, qr5 = st.q(r), st.q(r - 4), st.q(r - 1), st.q(r - 5)
    t, t4 = st.ttm(r), st.ttm(r - 4)

    # Growth
    for name in ("net_revenue", "nii", "ppop", "net_profit"):
        i = P[name]
        out[f"{name}_yoy"], out[f"{name}_neg_base"] = _growth(qr[i], qr4[i])
        out[f"{name}_ttm_growth"], neg_ttm = _growth(t[i], t4[i])
        if neg_ttm is True:
            out[f"{name}_neg_base"] = True
    prev_yoy, _ = _growth(qr1[P["net_profit"]], qr5[P["net_profit"]])
    out["net_profit_yoy_accel"] = out["net_profit_yoy"] - prev_yoy
    out["eps_ttm_growth"], _ = _growth(t[P["eps_basic"]], t4[P["eps_basic"]])
    rev, np_ttm = t[P["net_revenue"]], t[P["net_profit"]]
    out["net_revenue_ttm"], out["net_profit_ttm"] = rev, np_ttm
    out["cost_to_income_ttm"] = _div(t[P["operating_expenses"]], rev)
    out["credit_cost_to_income_ttm"] = _div(t[P["provisions"]], rev)
    cci_prev = _div(t4[P["provisions"]], t4[P["net_revenue"]])

    # Point-in-time ratios filed with this quarter (banks: asset quality, capital; insurers)
    pit, pit4 = st.pit(r), st.pit(r - 4)
    for name in ("gross_npa_pct", "net_npa_pct", "cet1_ratio", "roa_reported", "claims_ratio",
                 "combined_ratio", "solvency_ratio"):
        out[name] = pit[Q[name]] if pit is not None else NAN
    prior = pit4 if pit4 is not None else np.full(len(PIT_FIELDS), NAN)
    out["gross_npa_change_1y"] = out["gross_npa_pct"] - prior[Q["gross_npa_pct"]]
    out["net_npa_change_1y"] = out["net_npa_pct"] - prior[Q["net_npa_pct"]]
    out["cet1_change_1y"] = out["cet1_ratio"] - prior[Q["cet1_ratio"]]
    out["provision_coverage"] = (1 - _div(pit[Q["net_npa"]], pit[Q["gross_npa"]])
                                 if pit is not None else NAN)

    # Balance sheet (latest visible one at or before this period, at most 4 quarters old)
    for key in ("nim", "credit_cost", "roa", "roe", "leverage", "loan_to_deposit", "loans_to_assets", "total_assets",
                "advances_growth_1y", "deposits_growth_1y", "days_since_bs"):
        out[key] = NAN
    out["flag_negative_equity"] = pd.NA
    roa_prev = NAN
    b = st.latest("bs", r, MAX_STATEMENT_AGE_Q)
    if b is not None:
        bs = st.bs(b)
        prior_bs = next((st.bs(b - lag) for lag in (4, 2) if st.bs(b - lag) is not None), None)
        prior_of = (lambda key: prior_bs[B[key]]) if prior_bs is not None else (lambda key: None)
        assets, worth = bs[B["total_assets"]], bs[B["net_worth"]]
        avg_assets = _avg(assets, prior_of("total_assets"))
        avg_worth = _avg(worth, prior_of("net_worth"))
        avg_adv = _avg(bs[B["advances"]], prior_of("advances"))
        out["days_since_bs"] = (filing_date - _qo_to_date(b)).days
        out["total_assets"] = assets
        if not np.isnan(worth):
            out["flag_negative_equity"] = bool(worth < 0)
        out["roe"] = _div(np_ttm, avg_worth)
        if company_format in ("bank", "nbfc"):
            out["nim"] = _div(t[P["nii"]], avg_assets)
            out["roa"] = _div(np_ttm, avg_assets)
            out["credit_cost"] = _div(t[P["provisions"]], avg_adv)
            out["leverage"] = _div(assets, worth)
            out["loans_to_assets"] = _div(bs[B["advances"]], assets)
        if company_format == "bank":
            out["loan_to_deposit"] = _div(bs[B["advances"]], bs[B["deposits"]])
        bs_prev = st.bs(b - 4)
        if bs_prev is not None:
            out["advances_growth_1y"], _ = _growth(bs[B["advances"]], bs_prev[B["advances"]])
            out["deposits_growth_1y"], _ = _growth(bs[B["deposits"]], bs_prev[B["deposits"]])
            if company_format in ("bank", "nbfc"):
                prior2 = st.bs(b - 8)
                avg_prev = _avg(bs_prev[B["total_assets"]], prior2[B["total_assets"]] if prior2 is not None else None)
                roa_prev = _div(st.ttm(b - 4)[P["net_profit"]], avg_prev)

    # Red flags
    aq = []
    if not np.isnan(out["gross_npa_change_1y"]):
        aq.append(out["gross_npa_change_1y"] >= GNPA_RISE)
    if not (np.isnan(out["credit_cost_to_income_ttm"]) or np.isnan(cci_prev)):
        aq.append(out["credit_cost_to_income_ttm"] - cci_prev >= CREDIT_COST_RISE)
    out["flag_asset_quality_worsening"] = bool(any(aq)) if aq else pd.NA

    now, before = out["roa"], roa_prev
    if np.isnan(now) or np.isnan(before):
        now, before = np_ttm, t4[P["net_profit"]]
    if np.isnan(now) or np.isnan(before) or before <= TINY:
        out["flag_roa_collapse"] = pd.NA
    else:
        out["flag_roa_collapse"] = bool(now < ROA_COLLAPSE * before)

    if company_format == "bank" and not np.isnan(out["cet1_ratio"]):
        out["flag_capital_near_minimum"] = bool(out["cet1_ratio"] < CET1_NEAR_MIN)
    elif company_format == "insurance" and not np.isnan(out["solvency_ratio"]):
        out["flag_capital_near_minimum"] = bool(out["solvency_ratio"] < SOLVENCY_NEAR_MIN)
    else:
        out["flag_capital_near_minimum"] = pd.NA

    out["days_since_period_end"] = (filing_date - period_end).days
    return out


def _company_features(rows):
    """Features for every filing of one company on one basis (rows sorted by filing_date)."""

    fy_end = _fy_end_month(rows)
    st = _FinCompany(fy_end)
    company_format = rows["company_format"].iloc[0]
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
                st.add(qo, _record(row, qo, st))
        for row in batch:
            qo = _quarter_ordinal(row["period_end"])
            if qo is None:
                continue
            # the visible set never holds a filing newer than this row
            assert all(rec["fd"] <= row["filing_date"] for rec in st.visible.values())
            feats = _features(st, qo, row["filing_date"], row["period_end"], company_format)
            feats["nse_seq_number"] = row["nse_seq_number"]
            results.append(feats)
        i = j
    return results


def compute_features(raw):
    results = []
    raw = raw.sort_values(["company_key", "statement_type", "filing_date", "nse_seq_number"])
    for _, rows in raw.groupby(["company_key", "statement_type"], sort=False):
        results.extend(_company_features(rows))
    return pd.DataFrame(results, columns=["nse_seq_number", *FEATURES])


def build_feature_table(raw):
    """Point-in-time feature table keyed by (company_id, symbol, filing_date, period_end)."""

    feats = compute_features(raw)
    picked = _pick_one(raw)[["nse_seq_number", *KEY_COLUMNS, "statement_type", "company_format"]]
    table = picked.merge(feats, on="nse_seq_number", how="inner")
    for col in FLAG_FEATURES:
        table[col] = table[col].astype("boolean")
    return table.sort_values(["symbol", "period_end"]).reset_index(drop=True)


def check_point_in_time(raw, table, n=200, seed=0):
    """Recompute sampled rows from only the filings public by the row's filing_date.

    Any feature that differs from the full-history run would mean a later filing leaked into it.
    Returns the number of mismatching rows (0 expected).
    """

    sample = table.sample(min(n, len(table)), random_state=seed)
    bad = 0
    for _, row in sample.iterrows():
        visible = raw[(raw["company_key"].str.endswith(":" + row["symbol"]))
                      & (raw["filing_date"] <= row["filing_date"])]
        again = build_feature_table(visible)
        again = again[(again["period_end"] == row["period_end"])]
        if len(again) != 1:
            bad += 1
            continue
        a = again.iloc[0]
        for f in FEATURES:
            x, y = row[f], a[f]
            if pd.isna(x) and pd.isna(y):
                continue
            if pd.isna(x) != pd.isna(y) or (not isinstance(x, (bool, np.bool_)) and abs(float(x) - float(y)) > 1e-9) \
                    or (isinstance(x, (bool, np.bool_)) and bool(x) != bool(y)):
                bad += 1
                print(f"  look-ahead? {row['symbol']} {row['period_end']:%Y-%m-%d} {f}: {x} vs {y}")
                break
    return bad


# ---------------------------------------------------------
# CLI
# ---------------------------------------------------------

def summarize(table, extract_table=None):
    if extract_table is not None:
        e = extract_table.drop_duplicates("symbol")
        in_scope = e["lender_share"] >= MIN_LENDER_SHARE
        print(f"companies with a lender-format filing: {len(e)}; in scope: {in_scope.sum()} "
              f"({e[in_scope]['company_format'].value_counts().to_dict()}); left to features.py "
              f"(mostly non_financial filings): {(~in_scope).sum()}")
    print(f"rows: {len(table)}   companies: {table['symbol'].nunique()}   "
          f"period_end: {table['period_end'].min():%Y-%m-%d} .. {table['period_end'].max():%Y-%m-%d}")
    print("% non-null per feature (all / bank / nbfc / insurance):")
    width = max(len(f) for f in FEATURES)
    groups = {g: table[table["company_format"] == g] for g in LENDER_FORMATS}
    for name in FEATURES:
        cells = [table[name].notna().mean()] + [d[name].notna().mean() if len(d) else NAN for d in groups.values()]
        print(f"  {name:<{width}}  " + "  ".join(f"{100 * c:5.1f}" for c in cells))


def main(argv=None):
    parser = argparse.ArgumentParser(description="Build point-in-time bank/NBFC/insurer features.")
    parser.add_argument("--symbols", nargs="*", help="NSE symbols (default: all in scope)")
    parser.add_argument("--out", help="write the feature table to this CSV")
    parser.add_argument("--refresh-extract", action="store_true",
                        help=f"re-parse the cached XBRL into {EXTRACT_FILE.relative_to(ML_DIR)}")
    parser.add_argument("--push-db", action="store_true",
                        help=f"also replace the DB copy ({DB_TABLE}) that CI reads")
    parser.add_argument("--check", type=int, default=0, metavar="N",
                        help="recompute N sampled rows from truncated history (look-ahead check)")
    args = parser.parse_args(argv)

    import warnings
    warnings.filterwarnings("ignore", message="pandas only supports SQLAlchemy")

    conn = None
    if args.refresh_extract or args.push_db or not EXTRACT_FILE.exists():
        from news_pipeline.db import get_connection
        conn = get_connection()
    try:
        extract_table = load_extract(conn, args.symbols, refresh=args.refresh_extract)
        if args.push_db:
            if args.symbols:
                raise SystemExit("--push-db replaces the whole DB copy: run it without --symbols")
            print(f"pushed {push_extract(conn, extract_table):,} filings to {DB_TABLE}")
    finally:
        if conn is not None:
            conn.close()

    raw = raw_from_extract(extract_table)
    table = build_feature_table(raw)
    summarize(table, extract_table)
    if args.check:
        bad = check_point_in_time(raw, table, n=args.check)
        print(f"point-in-time check: {args.check} sampled rows recomputed from truncated history, "
              f"{bad} mismatches")
    if args.out:
        table.to_csv(args.out, index=False)
        print(f"wrote {args.out}")


if __name__ == "__main__":
    main()
