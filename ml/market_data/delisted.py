"""Companies that left NSE since 2016 (delisted, suspended, merged) and their daily prices.

`stock_prices` only holds companies listed today, so every backtest is survivorship-biased. This
module builds the missing side LOCALLY (files under ml/data/raw/delisted/); it never writes to the
database. See ml/market_data/DELISTED.md for sources, coverage, design and the backfill commands.

Sources (all public, no login):
    NSE CM bhavcopy       one zip per trading day, every traded symbol with ISIN, OHLC, PREVCLOSE,
                          volume. <= 2024-07-05: content/historical/EQUITIES/YYYY/MON/cmDDMONYYYYbhav.csv.zip
                          >= 2024-07-08: content/cm/BhavCopy_NSE_CM_0_0_0_YYYYMMDD_F_0000.csv.zip (UDiFF)
    NSE delisted.csv      symbol, name, delisting date and type (voluntary / compulsory / liquidation);
                          NSE stopped updating it in Nov 2020
    NSE security history  www.nseindia.com/api/historicalOR/generateSecurityWiseHistoricalData,
                          per symbol and series, works for delisted symbols, ~70 rows per call
                          (so 90-day windows)
Upstox v3 historical candles reject every delisted ISIN ("Invalid Instrument key"), so they are no use here.

Prices from NSE are NOT adjusted for splits/bonuses (Upstox candles are). On an ex-date NSE sets
PREVCLOSE to the adjusted base price, so prev_close_t / close_(t-1) gives the adjustment factor;
`adjust_closes` back-adjusts with it, which makes the series comparable with `stock_prices`.

Commands (from the ml/ folder):
    python3 -m market_data.delisted list
        monthly bhavcopy snapshots 2016-01 -> today (~130 files, ~5 min) -> every EQ/BE/BZ ISIN that
        traded and is no longer listed -> delisted_companies.csv, plus bhav_monthly.csv.gz (all names)
    python3 -m market_data.delisted sample --symbols DHFL JETAIRWAYS ...
        per-symbol NSE history for a few names (2016 -> exit) -> delisted_prices_sample.csv
    python3 -m market_data.delisted backfill --from 2016-01-01 --to 2026-10-01 [--max-files N]
        every daily bhavcopy in the range (zips cached in ml/data/raw/bhavcopy/) -> rows of the
        delisted ISINs -> delisted_prices.csv.gz (resumable: cached zips are not downloaded again)
"""

import argparse
import io
import json
import logging
import sys
import time
import zipfile
from datetime import date, datetime, timedelta
from pathlib import Path

import numpy as np
import pandas as pd
import requests

log = logging.getLogger("market_data.delisted")

ML_DIR = Path(__file__).resolve().parent.parent
RAW_DIR = ML_DIR / "data" / "raw" / "delisted"
BHAV_DIR = ML_DIR / "data" / "raw" / "bhavcopy"
LIST_FILE = RAW_DIR / "delisted_companies.csv"
MONTHLY_FILE = RAW_DIR / "bhav_monthly.csv.gz"
NSE_DELISTED_FILE = RAW_DIR / "nse_delisted.csv"
NSE_EQUITY_FILE = RAW_DIR / "nse_equity_l.csv"
SAMPLE_FILE = RAW_DIR / "delisted_prices_sample.csv"
PRICES_FILE = RAW_DIR / "delisted_prices.csv.gz"

ARCHIVE = "https://nsearchives.nseindia.com"
OLD_BHAV = ARCHIVE + "/content/historical/EQUITIES/{y}/{mon}/cm{d:%d}{mon}{y}bhav.csv.zip"
UDIFF_BHAV = ARCHIVE + "/content/cm/BhavCopy_NSE_CM_0_0_0_{d:%Y%m%d}_F_0000.csv.zip"
UDIFF_START = date(2024, 7, 8)          # first UDiFF day; the old format ends 2024-07-05
DELISTED_URL = ARCHIVE + "/content/equities/delisted.csv"
EQUITY_URL = ARCHIVE + "/content/equities/EQUITY_L.csv"
HISTORY_URL = ("https://www.nseindia.com/api/historicalOR/generateSecurityWiseHistoricalData"
               "?from={frm:%d-%m-%Y}&to={to:%d-%m-%Y}&symbol={symbol}&type=priceVolumeDeliverable&series={series}")
HISTORY_SPAN = 90                       # calendar days per call (the API returns at most ~70 rows)
# One series per call: series=ALL also returns a company's bonds (DHFL has ~15 NCD series) and they
# eat the row cap. Each window asks only for the series the monthly snapshots show around it.
USER_AGENT = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
              "(KHTML, like Gecko) Chrome/124.0 Safari/537.36")
MIN_INTERVAL = 2.0                      # seconds between requests to NSE (polite; no published limit)
MAX_RETRIES = 4

START = date(2016, 1, 1)
SERIES = ("EQ", "BE", "BZ")             # main board; BZ = trade-for-trade for non-compliant companies
SERIES_RANK = {"EQ": 0, "BE": 1, "BZ": 2}
ADJ_TOL = 0.02                          # prev_close / previous close off by > 2% = corporate action
DISTRESS_TYPES = ("Liquidation", "Compulsory")

# DDL for the database side (NOT executed by this module; see DELISTED.md). Separate tables so the
# website, which reads `companies` / `stock_prices`, can never show these names.
DELISTED_COMPANIES_SQL = """
CREATE TABLE IF NOT EXISTS delisted_companies (
    id INT NOT NULL AUTO_INCREMENT PRIMARY KEY,
    symbol VARCHAR(32) NOT NULL,
    isin VARCHAR(12) NOT NULL,
    name VARCHAR(255) NULL,
    first_seen DATE NULL,
    last_traded DATE NULL,
    last_series VARCHAR(4) NULL,
    last_close DECIMAL(14,4) NULL,
    nse_delisted_date DATE NULL,
    nse_delisting_type VARCHAR(64) NULL,
    exit_kind VARCHAR(32) NOT NULL,
    distress TINYINT(1) NOT NULL DEFAULT 0,
    source VARCHAR(255) NULL,
    UNIQUE KEY uq_delisted_isin (isin),
    KEY idx_delisted_symbol (symbol)
)
"""

DELISTED_PRICES_SQL = """
CREATE TABLE IF NOT EXISTS delisted_prices (
    delisted_id INT NOT NULL,
    price_date DATE NOT NULL,
    series VARCHAR(4) NULL,
    open_price DECIMAL(14,4) NULL,
    high_price DECIMAL(14,4) NULL,
    low_price DECIMAL(14,4) NULL,
    close_price DECIMAL(14,4) NULL,
    prev_close DECIMAL(14,4) NULL,
    adj_close DECIMAL(18,6) NULL,
    volume BIGINT NULL,
    PRIMARY KEY (delisted_id, price_date)
)
"""


# ---------------------------------------------------------------------------
# HTTP
# ---------------------------------------------------------------------------

class Nse:
    """Throttled session for the NSE archive and the www.nseindia.com history API."""

    def __init__(self, interval=MIN_INTERVAL):
        self.session = requests.Session()
        self.session.headers.update({"User-Agent": USER_AGENT, "Accept": "*/*",
                                     "Accept-Language": "en-US,en;q=0.9"})
        self.interval = interval
        self._last = 0.0
        self.requests = 0
        self.bytes = 0
        self._cookies = False

    def get(self, url, **headers):
        """-> bytes, or None on 404 (holiday / unknown file)."""
        for attempt in range(MAX_RETRIES + 1):
            wait = self._last + self.interval - time.monotonic()
            if wait > 0:
                time.sleep(wait)
            self._last = time.monotonic()
            self.requests += 1
            try:
                resp = self.session.get(url, timeout=60, headers=headers)
            except requests.RequestException as exc:
                err = f"network: {exc}"
            else:
                if resp.status_code == 200:
                    self.bytes += len(resp.content)
                    return resp.content
                if resp.status_code == 404:
                    return None
                err = f"HTTP {resp.status_code}"
                if resp.status_code in (401, 403):
                    self._cookies = False
            if attempt == MAX_RETRIES:
                raise RuntimeError(f"{url}: giving up ({err})")
            delay = 5 * 2 ** attempt
            log.warning("%s: %s, retrying in %ss", url, err, delay)
            time.sleep(delay)

    def api(self, url):
        """JSON from www.nseindia.com/api (needs the cookies the home page sets)."""
        if not self._cookies:
            self.get("https://www.nseindia.com/")
            self._cookies = True
        raw = self.get(url, Accept="application/json, text/plain, */*",
                       Referer="https://www.nseindia.com/report-detail/eq_security")
        return json.loads(raw) if raw else {}


# ---------------------------------------------------------------------------
# Bhavcopy
# ---------------------------------------------------------------------------

def bhav_url(day):
    if day >= UDIFF_START:
        return UDIFF_BHAV.format(d=day)
    return OLD_BHAV.format(y=day.year, mon=day.strftime("%b").upper(), d=day)


def _parse_bhav(raw, day):
    with zipfile.ZipFile(io.BytesIO(raw)) as zf:
        df = pd.read_csv(zf.open(zf.namelist()[0]), dtype=str)
    df.columns = [c.strip() for c in df.columns]
    if "TckrSymb" in df.columns:        # UDiFF
        df = df.rename(columns={"TckrSymb": "symbol", "SctySrs": "series", "ISIN": "isin",
                                "FinInstrmNm": "name", "OpnPric": "open", "HghPric": "high",
                                "LwPric": "low", "ClsPric": "close", "PrvsClsgPric": "prev_close",
                                "TtlTradgVol": "volume", "TtlTrfVal": "value"})
    else:
        df = df.rename(columns={"SYMBOL": "symbol", "SERIES": "series", "ISIN": "isin", "OPEN": "open",
                                "HIGH": "high", "LOW": "low", "CLOSE": "close", "PREVCLOSE": "prev_close",
                                "TOTTRDQTY": "volume", "TOTTRDVAL": "value"})
        df["name"] = None
    df = df[["symbol", "series", "isin", "name", "open", "high", "low", "close", "prev_close", "volume", "value"]]
    for col in ("symbol", "series", "isin"):
        df[col] = df[col].str.strip()
    df = df[df["series"].isin(SERIES)].copy()
    for col in ("open", "high", "low", "close", "prev_close", "volume", "value"):
        df[col] = pd.to_numeric(df[col], errors="coerce")
    df.insert(0, "price_date", pd.Timestamp(day))
    return df


def bhavcopy(nse, day, cache=True):
    """Normalised EQ/BE/BZ rows for one day, or None when NSE has no file (holiday)."""
    path = BHAV_DIR / f"{day:%Y}" / bhav_url(day).rsplit("/", 1)[1]
    if path.exists():
        return _parse_bhav(path.read_bytes(), day)
    raw = nse.get(bhav_url(day))
    if raw is None:
        return None
    if cache:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(raw)
    return _parse_bhav(raw, day)


def first_trading_day(nse, year, month):
    for d in range(1, 8):
        day = date(year, month, d)
        if day.weekday() >= 5:
            continue
        df = bhavcopy(nse, day)
        if df is not None:
            return df
    return None


# ---------------------------------------------------------------------------
# Corporate-action adjustment
# ---------------------------------------------------------------------------

def adjust_closes(prices):
    """Add adj_close (split/bonus back-adjusted, latest price = raw) per isin.

    prices: [isin, price_date, close, prev_close, ...], one row per isin and date.
    factor on day t = prev_close_t / close_(t-1); |factor - 1| <= ADJ_TOL is noise and ignored.
    """
    out = []
    for _, g in prices.sort_values(["isin", "price_date"]).groupby("isin", sort=False):
        g = g.copy()
        factor = (g["prev_close"] / g["close"].shift()).fillna(1.0)
        factor = factor.where((factor - 1).abs() > ADJ_TOL, 1.0).where(factor > 0, 1.0)
        # a close before day t is multiplied by every factor from t+1 onwards... i.e. reverse cumprod
        cum = factor[::-1].cumprod()[::-1].shift(-1).fillna(1.0)
        g["adj_factor"] = cum
        g["adj_close"] = g["close"] * cum
        g["corp_action"] = factor != 1.0
        out.append(g)
    return pd.concat(out, ignore_index=True) if out else prices.assign(adj_factor=[], adj_close=[], corp_action=[])


# ---------------------------------------------------------------------------
# list: who left?
# ---------------------------------------------------------------------------

def current_listed():
    """(isins, symbols) of companies listed today: the `companies` table (SELECT), else EQUITY_L.csv."""
    isins, symbols = set(), set()
    try:
        from news_pipeline.db import get_connection
        conn = get_connection()
        try:
            cur = conn.cursor()
            cur.execute("SELECT isin, symbol FROM companies")
            for isin, symbol in cur.fetchall():
                isins.add((isin or "").strip())
                symbols.add((symbol or "").strip())
        finally:
            conn.close()
    except Exception as exc:                       # offline: fall back to NSE's own list
        log.warning("companies table unavailable (%s); using %s", exc, NSE_EQUITY_FILE.name)
    eq = pd.read_csv(NSE_EQUITY_FILE)
    eq.columns = [c.strip() for c in eq.columns]
    isins |= set(eq["ISIN NUMBER"].str.strip())
    symbols |= set(eq["SYMBOL"].str.strip())
    return isins - {""}, symbols - {""}


def load_nse_delisted():
    df = pd.read_csv(NSE_DELISTED_FILE, usecols=[0, 1, 2, 3], encoding="latin-1")
    df.columns = ["symbol", "name", "nse_delisted_date", "nse_delisting_type"]
    df["symbol"] = df["symbol"].str.strip()
    df["nse_delisting_type"] = df["nse_delisting_type"].str.strip()
    df["nse_delisted_date"] = pd.to_datetime(df["nse_delisted_date"], format="%d-%b-%y", errors="coerce")
    return df.dropna(subset=["symbol"]).drop_duplicates("symbol", keep="last")


def build_list(nse, end):
    """Monthly snapshots -> (departed list, all monthly rows)."""
    for path, url in ((NSE_DELISTED_FILE, DELISTED_URL), (NSE_EQUITY_FILE, EQUITY_URL)):
        if not path.exists():
            path.write_bytes(nse.get(url))
    frames = []
    month = date(START.year, START.month, 1)
    while month <= end:
        df = first_trading_day(nse, month.year, month.month)
        if df is not None:
            frames.append(df)
            log.info("snapshot %s: %d rows", df["price_date"].iloc[0].date(), len(df))
        month = (month + timedelta(days=32)).replace(day=1)
    monthly = pd.concat(frames, ignore_index=True)
    latest = monthly["price_date"].max()
    now = monthly[monthly["price_date"] == latest]

    isins, symbols = current_listed()
    isins |= set(now["isin"])
    symbols |= set(now["symbol"])
    seen = (monthly.sort_values("price_date")
            .groupby("isin")
            .agg(symbol=("symbol", "last"), name=("name", lambda s: s.dropna().iloc[-1] if s.notna().any() else None),
                 first_seen=("price_date", "min"), last_seen=("price_date", "max"),
                 last_series=("series", "last"), last_close=("close", "last"),
                 symbols=("symbol", lambda s: "|".join(sorted(set(s))))))
    gone = seen[~seen.index.isin(isins)]
    # same symbol still listed under a new ISIN = face-value split / ISIN change, not an exit
    gone = gone[~gone["symbols"].str.split("|").apply(lambda s: bool(set(s) & symbols))].reset_index()

    nse_del = load_nse_delisted()
    gone = gone.merge(nse_del.drop(columns="name").rename(columns={"symbol": "symbol_j"}),
                      left_on="symbol", right_on="symbol_j", how="left").drop(columns="symbol_j")
    named = nse_del.set_index("symbol")["name"]
    gone["name"] = gone["name"].fillna(gone["symbol"].map(named))
    kind = np.where(gone["nse_delisting_type"].str.contains("Liquidation", na=False), "liquidation",
           np.where(gone["nse_delisting_type"].str.contains("Compulsory", na=False), "compulsory_delisting",
           np.where(gone["nse_delisting_type"].str.contains("Voluntary", na=False), "voluntary_delisting",
           np.where(gone["last_series"] == "BZ", "suspended_bz", "unknown"))))
    gone["exit_kind"] = kind
    gone["distress"] = gone["exit_kind"].isin(["liquidation", "compulsory_delisting", "suspended_bz"]).astype(int)
    gone["source"] = "NSE bhavcopy monthly snapshots; type from " + DELISTED_URL
    gone.loc[gone["nse_delisting_type"].isna(), "source"] = "NSE bhavcopy monthly snapshots"
    gone = gone.sort_values(["last_seen", "symbol"]).reset_index(drop=True)
    gone.insert(0, "id", np.arange(1, len(gone) + 1))
    return gone, monthly


# ---------------------------------------------------------------------------
# sample: per-symbol history API
# ---------------------------------------------------------------------------

def symbol_history(nse, symbol, start, end, isin=None, seen=None):
    """Daily EQ/BE/BZ rows of one symbol from the NSE security history API.

    seen: optional monthly snapshot rows [price_date, series] of this ISIN; each window queries the
    series seen within ~5 weeks of it (EQ when none).
    """
    rows = []
    to = end
    while to >= start:
        frm = max(start, to - timedelta(days=HISTORY_SPAN - 1))
        series = {"EQ"}
        if seen is not None and len(seen):
            near = seen[(seen["price_date"] >= pd.Timestamp(frm) - pd.Timedelta(days=35))
                        & (seen["price_date"] <= pd.Timestamp(to) + pd.Timedelta(days=35))]
            series = set(near["series"]) or series
        for ser in sorted(series):
            data = nse.api(HISTORY_URL.format(frm=frm, to=to, symbol=requests.utils.quote(symbol, safe=""),
                                              series=ser))
            rows.extend(data.get("data") or [])
        to = frm - timedelta(days=1)
    if not rows:
        return pd.DataFrame()
    df = pd.DataFrame(rows)
    df = df[df["CH_SERIES"].isin(SERIES)]
    df = pd.DataFrame({
        "price_date": pd.to_datetime(df["mTIMESTAMP"], format="%d-%b-%Y"),
        "symbol": df["CH_SYMBOL"], "series": df["CH_SERIES"], "isin": isin,
        "open": df["CH_OPENING_PRICE"], "high": df["CH_TRADE_HIGH_PRICE"], "low": df["CH_TRADE_LOW_PRICE"],
        "close": df["CH_CLOSING_PRICE"], "prev_close": df["CH_PREVIOUS_CLS_PRICE"],
        "volume": df["CH_TOT_TRADED_QTY"], "value": df["CH_TOT_TRADED_VAL"],
    })
    return _one_row_per_day(df)


def _one_row_per_day(df):
    df = df.assign(_r=df["series"].map(SERIES_RANK)).sort_values(["isin", "price_date", "_r"])
    return df.drop_duplicates(["isin", "price_date"]).drop(columns="_r").reset_index(drop=True)


def fetch_sample(nse, symbols, companies, monthly):
    """companies: the list from `build_list` (symbol -> isin, first/last seen); monthly: its snapshots."""
    frames = []
    by_symbol = companies.set_index("symbol")
    for sym in symbols:
        if sym in by_symbol.index:
            c = by_symbol.loc[sym]
            c = c.iloc[-1] if isinstance(c, pd.DataFrame) else c
            isin = c["isin"]
            start = START
            # the monthly snapshot only bounds the exit; history runs a month past it
            end = min(c["last_seen"].date() + timedelta(days=45), date.today())
        else:
            isin, start, end = None, START, date.today()    # control (a listed company)
        t0 = nse.requests
        seen = monthly[monthly["symbol"] == sym] if isin is None else monthly[monthly["isin"] == isin]
        df = symbol_history(nse, sym, start, end, isin=isin, seen=seen)
        if df.empty:
            log.warning("%s: no history", sym)
            continue
        if isin is None:
            df["isin"] = "CONTROL:" + sym
        frames.append(df)
        log.info("%s: %d rows %s -> %s (%d requests)", sym, len(df), df["price_date"].min().date(),
                 df["price_date"].max().date(), nse.requests - t0)
    return adjust_closes(pd.concat(frames, ignore_index=True))


# ---------------------------------------------------------------------------
# backfill: every daily bhavcopy (for later; see DELISTED.md)
# ---------------------------------------------------------------------------

def backfill(nse, start, end, isins, max_files=None):
    frames, files, t0 = [], 0, time.monotonic()
    day = start
    while day <= end and (max_files is None or files < max_files):
        if day.weekday() < 5:
            df = bhavcopy(nse, day)
            files += 1
            if df is not None:
                frames.append(df[df["isin"].isin(isins)])
            if files % 50 == 0:
                rate = (time.monotonic() - t0) / files
                log.info("%s: %d files, %.1f MB, %.1fs/file", day, files, nse.bytes / 1e6, rate)
        day += timedelta(days=1)
    prices = _one_row_per_day(pd.concat(frames, ignore_index=True)) if frames else pd.DataFrame()
    return prices, files


# ---------------------------------------------------------------------------
# Loaders for backtests (opt-in; see growth_model.prices.load_prices(include_delisted=True))
# ---------------------------------------------------------------------------

def load_delisted(source="local", prices_file=None):
    """-> (prices [company_id, price_date, close, volume], companies [company_id, symbol, isin, last_traded,
    last_close, distress, exit_kind]).

    company_id = -id (negative), so it never collides with `companies.id`. close is the split/bonus
    adjusted close. source="db" reads the delisted_* tables (once created), "local" the CSVs here.
    """
    if source == "db":
        from news_pipeline.db import get_connection
        conn = get_connection()
        try:
            cur = conn.cursor()
            cur.execute("""SELECT id, symbol, isin, last_traded, last_close, distress, exit_kind
                           FROM delisted_companies""")
            comp = pd.DataFrame(cur.fetchall(), columns=["id", "symbol", "isin", "last_traded", "last_close",
                                                         "distress", "exit_kind"])
            cur.execute("SELECT delisted_id, price_date, adj_close, volume FROM delisted_prices")
            px = pd.DataFrame(cur.fetchall(), columns=["id", "price_date", "close", "volume"])
        finally:
            conn.close()
    else:
        comp = pd.read_csv(LIST_FILE, parse_dates=["last_seen"])
        path = Path(prices_file) if prices_file else (PRICES_FILE if PRICES_FILE.exists() else SAMPLE_FILE)
        raw = pd.read_csv(path, parse_dates=["price_date"])
        raw = raw[raw["isin"].isin(comp["isin"])]
        px = raw.merge(comp[["id", "isin"]], on="isin")[["id", "price_date", "adj_close", "volume"]]
        px = px.rename(columns={"adj_close": "close"})
        last = raw.groupby("isin")["price_date"].max()
        comp = comp[comp["isin"].isin(last.index)].copy()
        comp["last_traded"] = comp["isin"].map(last)
    px["company_id"] = -px.pop("id").astype(int)
    px["price_date"] = pd.to_datetime(px["price_date"])
    px["close"] = px["close"].astype(float)
    px["volume"] = pd.to_numeric(px["volume"], errors="coerce").astype(float)
    comp["company_id"] = -comp["id"].astype(int)
    comp["last_traded"] = pd.to_datetime(comp["last_traded"])
    return (px[["company_id", "price_date", "close", "volume"]].reset_index(drop=True),
            comp[["company_id", "symbol", "isin", "last_traded", "distress", "exit_kind"]].reset_index(drop=True))


def terminal_prices(stocks, companies, distress_value=0.0):
    """{company_id: (last_traded, terminal close)} for labels: what a holder had after the exit.

    Non-distress exits (voluntary delisting, merger, unknown) keep the last adjusted close (the holder
    was paid roughly that); distress exits (liquidation, compulsory delisting, BZ suspension) are
    worth `distress_value` x last close (0 = equity wiped out, the usual IBC outcome).
    """
    last = stocks.sort_values("price_date").groupby("company_id").last()
    out = {}
    for row in companies.itertuples():
        if row.company_id not in last.index:
            continue
        px = last.loc[row.company_id, "close"]
        out[row.company_id] = (last.loc[row.company_id, "price_date"],
                               px * distress_value if row.distress else px)
    return out


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def parse_date(value):
    return datetime.strptime(value, "%Y-%m-%d").date()


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("list", help="monthly snapshots -> delisted_companies.csv")
    sp = sub.add_parser("sample", help="per-symbol NSE history for a few names")
    sp.add_argument("--symbols", nargs="+", required=True)
    sp.add_argument("--controls", nargs="*", default=[], help="listed symbols, to validate against stock_prices")
    bp = sub.add_parser("backfill", help="daily bhavcopies -> delisted_prices.csv.gz")
    bp.add_argument("--from", dest="start", type=parse_date, default=START)
    bp.add_argument("--to", dest="end", type=parse_date, default=date.today())
    bp.add_argument("--max-files", type=int, help="stop after N weekday files (feasibility runs)")
    bp.add_argument("--out", help="output file (default delisted_prices.csv.gz)")
    args = ap.parse_args(argv)

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s", datefmt="%H:%M:%S")
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    nse = Nse()
    t0 = time.monotonic()
    if args.cmd == "list":
        gone, monthly = build_list(nse, date.today())
        gone.to_csv(LIST_FILE, index=False)
        monthly.to_csv(MONTHLY_FILE, index=False)
        log.info("%d departed ISINs -> %s; exit kinds: %s", len(gone), LIST_FILE,
                 gone["exit_kind"].value_counts().to_dict())
    elif args.cmd == "sample":
        comp = pd.read_csv(LIST_FILE, parse_dates=["last_seen"])
        monthly = pd.read_csv(MONTHLY_FILE, usecols=["price_date", "symbol", "series", "isin"],
                              parse_dates=["price_date"])
        prices = fetch_sample(nse, args.symbols + args.controls, comp, monthly)
        prices.to_csv(SAMPLE_FILE, index=False)
        log.info("%d rows for %d names -> %s", len(prices), prices["isin"].nunique(), SAMPLE_FILE)
    else:
        comp = pd.read_csv(LIST_FILE)
        prices, files = backfill(nse, args.start, args.end, set(comp["isin"]), args.max_files)
        if not prices.empty:
            prices = adjust_closes(prices)
            out = Path(args.out) if args.out else PRICES_FILE
            prices.to_csv(out, index=False)
            log.info("%d rows for %d ISINs -> %s", len(prices), prices["isin"].nunique(), out)
        log.info("%d files", files)
    log.info("done in %.1f min, %d requests, %.1f MB downloaded", (time.monotonic() - t0) / 60,
             nse.requests, nse.bytes / 1e6)
    return 0


if __name__ == "__main__":
    sys.exit(main())
