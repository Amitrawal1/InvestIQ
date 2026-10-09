"""Raw IPO data from NSE (official, public, no login). Every download is cached under
ml/data/raw/ipo/ (git-ignored) and never fetched twice unless --refresh.

Sources (www.nseindia.com robots.txt: `Allow: /`, only /market-data-test disallowed; the NSE website
terms allow personal / non-commercial viewing and forbid redistribution of NSE data: InvestIQ shows
derived ratios with attribution, not NSE's raw tables. Requests are throttled to one every 2 s.)

    public-past-issues   /api/public-past-issues?from_date&to_date&security_type=all
                         every public issue that closed in the window: symbol, company, issue period,
                         price band, final issue price, listing date, security type (EQ / BE = main
                         board, SME, plus debt / InvIT / REIT types that are dropped)
    ipo-detail           /api/ipo-detail?symbol&series
                         metaInfo (ISIN, NSE industry, listing date: empty for renamed / delisted
                         symbols), issueInfo (issue size text, face value, lot, lead managers, links to
                         the RHP and the "Basis of issue price" ad), activeCat = final consolidated
                         (NSE + BSE) subscription by category, bidDetails = NSE-only subscription
    current / upcoming   /api/ipo-current-issue, /api/all-upcoming-issues?category=ipo (live use)
    CM bhavcopy          nsearchives.nseindia.com daily zip (market_data/delisted.py URLs, shared
                         cache ml/data/raw/bhavcopy/): listing-day open / close UNADJUSTED, ISIN;
                         PREVCLOSE on the listing day = the issue price
    PR zip MCAP file     nsearchives.nseindia.com/archives/equities/bhavcopy/pr/PRddmmyy.zip:
                         `MCAPddmmyyyy.csv` has the exact share count ("Issue Size") per symbol;
                         it exists only from 2024 (checked: none in Jan-2024 or earlier samples)

CLI (from ml/):
    python3 -m ipo.sources past                    # 2016-01 -> today, one call per month
    python3 -m ipo.sources details [--sme]         # ipo-detail for every main-board (and SME) issue
    python3 -m ipo.sources listing                 # bhavcopy + MCAP for every listing day
    python3 -m ipo.sources live                    # current + upcoming issues (prints)
"""

import argparse
import io
import json
import logging
import time
import zipfile
from datetime import date, datetime, timedelta
from pathlib import Path

import pandas as pd

from market_data.delisted import BHAV_DIR, Nse, bhav_url

log = logging.getLogger("ipo.sources")

ML_DIR = Path(__file__).resolve().parent.parent
RAW_DIR = ML_DIR / "data" / "raw" / "ipo"
PAST_DIR = RAW_DIR / "past_issues"
DETAIL_DIR = RAW_DIR / "detail"
MCAP_DIR = RAW_DIR / "mcap"
LIVE_DIR = RAW_DIR / "live"

API = "https://www.nseindia.com/api"
PAST_URL = API + "/public-past-issues?from_date={a:%d-%m-%Y}&to_date={b:%d-%m-%Y}&security_type=all"
DETAIL_URL = API + "/ipo-detail?symbol={symbol}&series={series}"
CURRENT_URL = API + "/ipo-current-issue"
UPCOMING_URL = API + "/all-upcoming-issues?category=ipo"
PR_URL = "https://nsearchives.nseindia.com/archives/equities/bhavcopy/pr/PR{d:%d%m%y}.zip"
MCAP_FROM = date(2024, 1, 1)
START = date(2016, 1, 1)
MAINBOARD = ("EQ", "BE")
SME = ("SME",)
INTERVAL = 2.0


def client():
    return Nse(interval=INTERVAL)


def _url_symbol(symbol):
    return symbol.replace("&", "%26")


# ---------------------------------------------------------
# Past issues
# ---------------------------------------------------------

def fetch_past(nse, start=START, end=None, refresh=False):
    """One cached JSON per calendar month (the current month is always re-fetched)."""
    end = end or date.today()
    PAST_DIR.mkdir(parents=True, exist_ok=True)
    m = date(start.year, start.month, 1)
    while m <= end:
        nxt = date(m.year + (m.month == 12), m.month % 12 + 1, 1)
        path = PAST_DIR / f"{m:%Y-%m}.json"
        current = nxt > date.today()
        if refresh or current or not path.exists():
            data = nse.api(PAST_URL.format(a=m, b=nxt - timedelta(days=1)))
            path.write_text(json.dumps(data if isinstance(data, list) else [], indent=0))
            log.info("past issues %s: %d", m.strftime("%Y-%m"), len(data or []))
        m = nxt


def _d(value):
    if not value or not str(value).strip() or str(value).strip() == "-":
        return pd.NaT
    return pd.to_datetime(str(value).strip(), format="%d-%b-%Y", errors="coerce")


def load_past():
    rows = []
    for path in sorted(PAST_DIR.glob("*.json")):
        for r in json.loads(path.read_text()):
            rows.append({
                "symbol": (r.get("symbol") or "").strip().upper(),
                "company": (r.get("companyName") or r.get("company") or "").strip(),
                "security_type": (r.get("securityType") or "").strip(),
                "issue_start": _d(r.get("ipoStartDate")),
                "issue_end": _d(r.get("ipoEndDate")),
                "listing_date": _d(r.get("listingDate")),
                "price_range": (r.get("priceRange") or "").strip(),
                "issue_price": pd.to_numeric(str(r.get("issuePrice") or "").replace(",", "").strip(),
                                             errors="coerce"),
            })
    df = pd.DataFrame(rows)
    df = df[df["symbol"] != ""].sort_values("issue_end")
    # the same issue can sit in two monthly windows only if NSE changed its dates; keep the last
    return df.drop_duplicates(["symbol", "security_type", "issue_start"], keep="last").reset_index(drop=True)


# ---------------------------------------------------------
# Issue detail + subscription
# ---------------------------------------------------------

def detail_path(symbol, series):
    return DETAIL_DIR / f"{symbol.replace('/', '_')}_{series}.json"


def fetch_details(nse, issues, refresh=False):
    DETAIL_DIR.mkdir(parents=True, exist_ok=True)
    todo = [(r.symbol, "SME" if r.security_type == "SME" else "EQ") for r in issues.itertuples()]
    for i, (symbol, series) in enumerate(todo):
        path = detail_path(symbol, series)
        if path.exists() and not refresh:
            continue
        try:
            data = nse.api(DETAIL_URL.format(symbol=_url_symbol(symbol), series=series))
        except RuntimeError as exc:
            log.warning("%s: %s", symbol, exc)
            continue
        path.write_text(json.dumps(data))
        if i % 25 == 0:
            log.info("detail %d/%d %s", i + 1, len(todo), symbol)


def _num(x):
    try:
        v = float(str(x).replace(",", "").strip())
        return v if v == v else None
    except (TypeError, ValueError):
        return None


SUB_KEYS = [("sub_qib", "qualified institutional"), ("sub_nii", "non institutional investors"),
            ("sub_retail", "retail individual"), ("sub_employee", "employee"), ("sub_total", "total")]


def _subscription(rows, times_key):
    out = {}
    for r in rows or []:
        cat = " ".join(str(r.get("category") or "").lower().split())
        times = _num(r.get(times_key))
        if times is None or times <= 0:     # SME pages often carry a placeholder "Total 0.00"
            continue
        for key, label in SUB_KEYS:
            # the NII line itself (not its >10 lakh / 2-10 lakh sub-lines, whose labels add "(bid ...")
            if key == "sub_nii" and "(" in cat:
                continue
            if cat.startswith(label) and key not in out:
                out[key] = times
    return out


def parse_detail(symbol, series):
    path = detail_path(symbol, series)
    if not path.exists():
        return {}
    d = json.loads(path.read_text())
    if not isinstance(d, dict):
        return {}
    meta = d.get("metaInfo") or {}
    info = {}
    for x in (d.get("issueInfo") or {}).get("dataList", []):
        t = " ".join(str(x.get("title") or "").split())
        if t:
            info[t] = " ".join(str(x.get("value") or "").replace('"', "").split())
    out = {
        "isin": meta.get("isin"), "nse_industry": meta.get("industry"),
        "meta_listing_date": meta.get("listingDate"), "delisted_flag": meta.get("isDelisted"),
        "issue_size_text": info.get("Issue Size"), "issue_type": info.get("Issue Type"),
        "face_value": _num(str(info.get("Face Value", "")).replace("Rs.", "").replace("Re.", "").replace("Rs", "")),
        "lead_managers": info.get("Book Running Lead Managers") or info.get("Book Running Lead Manager"),
        "rhp_url": info.get("Red Herring Prospectus"), "ratios_url": info.get("Ratios / Basis of Issue Price"),
    }
    sub = _subscription((d.get("activeCat") or {}).get("dataList"), "noOfTotalMeant")
    out["sub_source"] = "consolidated" if sub else None
    if not sub:
        sub = _subscription(d.get("bidDetails"), "noOfTime")
        out["sub_source"] = "nse_only" if sub else None
    out.update(sub)
    return out


# ---------------------------------------------------------
# Listing-day prices (bhavcopy, all series) and share counts (MCAP, 2024+)
# ---------------------------------------------------------

def _parse_bhav_all(raw):
    with zipfile.ZipFile(io.BytesIO(raw)) as zf:
        df = pd.read_csv(zf.open(zf.namelist()[0]), dtype=str)
    df.columns = [c.strip() for c in df.columns]
    if "TckrSymb" in df.columns:
        df = df.rename(columns={"TckrSymb": "symbol", "SctySrs": "series", "ISIN": "isin", "OpnPric": "open",
                                "HghPric": "high", "LwPric": "low", "ClsPric": "close",
                                "PrvsClsgPric": "prev_close", "TtlTradgVol": "volume"})
    else:
        df = df.rename(columns={"SYMBOL": "symbol", "SERIES": "series", "ISIN": "isin", "OPEN": "open",
                                "HIGH": "high", "LOW": "low", "CLOSE": "close", "PREVCLOSE": "prev_close",
                                "TOTTRDQTY": "volume"})
    if "isin" not in df.columns:
        df["isin"] = None
    df = df[["symbol", "series", "isin", "open", "high", "low", "close", "prev_close", "volume"]].copy()
    for c in ("symbol", "series", "isin"):
        df[c] = df[c].astype(str).str.strip()
    for c in ("open", "high", "low", "close", "prev_close", "volume"):
        df[c] = pd.to_numeric(df[c], errors="coerce")
    return df


def bhav_day(nse, day):
    path = BHAV_DIR / f"{day:%Y}" / bhav_url(day).rsplit("/", 1)[1]
    if path.exists():
        return _parse_bhav_all(path.read_bytes())
    raw = nse.get(bhav_url(day))
    if raw is None:
        return None
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(raw)
    return _parse_bhav_all(raw)


def mcap_day(nse, day):
    """Share counts on `day` from the PR zip's MCAP file (cached as a small csv), or None."""
    MCAP_DIR.mkdir(parents=True, exist_ok=True)
    path = MCAP_DIR / f"MCAP_{day:%Y%m%d}.csv"
    if path.exists():
        df = pd.read_csv(path)
        return df if len(df) else None
    raw = nse.get(PR_URL.format(d=day))
    df = pd.DataFrame(columns=["symbol", "series", "face_value", "shares", "close", "mcap"])
    if raw:
        try:
            with zipfile.ZipFile(io.BytesIO(raw)) as zf:
                names = [n for n in zf.namelist() if n.upper().startswith("MCAP")]
                if names:
                    m = pd.read_csv(zf.open(names[0]), dtype=str)
                    m.columns = [c.strip() for c in m.columns]
                    df = pd.DataFrame({
                        "symbol": m["Symbol"].str.strip(), "series": m["Series"].str.strip(),
                        "face_value": pd.to_numeric(m["Face Value(Rs.)"], errors="coerce"),
                        "shares": pd.to_numeric(m["Issue Size"], errors="coerce"),
                        "close": pd.to_numeric(m["Close Price/Paid up value(Rs.)"], errors="coerce"),
                        "mcap": pd.to_numeric(m[[c for c in m.columns if c.startswith("Market Cap")][0]],
                                              errors="coerce")})
        except zipfile.BadZipFile:
            pass
    df.to_csv(path, index=False)
    return df if len(df) else None


LISTING_FILE = RAW_DIR / "listing_day.csv"


def fetch_listing(nse, issues):
    """Listing-day bhavcopy row (+ MCAP share count from 2024) for every issue with a listing date."""
    done = pd.read_csv(LISTING_FILE) if LISTING_FILE.exists() else pd.DataFrame(columns=["symbol", "listing_date"])
    have = set(zip(done["symbol"], done["listing_date"].astype(str)))
    rows = []
    issues = issues[issues["listing_date"].notna() & (issues["listing_date"] <= pd.Timestamp(date.today()))
                    & (issues["listing_date"] >= issues["issue_end"]) & (issues["listing_date"] >= pd.Timestamp(START))]
    for day, g in issues.groupby("listing_date"):
        todo = [s for s in g["symbol"] if (s, str(day.date())) not in have]
        if not todo:
            continue
        bhav = bhav_day(nse, day.date())
        mcap = mcap_day(nse, day.date()) if day.date() >= MCAP_FROM else None
        for s in todo:
            r = {"symbol": s, "listing_date": str(day.date())}
            if bhav is not None:
                b = bhav[bhav["symbol"] == s]
                if len(b):
                    b = b.sort_values("volume", ascending=False).iloc[0]
                    r.update({"bhav_series": b["series"], "bhav_isin": b["isin"], "list_open": b["open"],
                              "list_high": b["high"], "list_low": b["low"], "list_close": b["close"],
                              "list_prev_close": b["prev_close"], "list_volume": b["volume"]})
            if mcap is not None:
                m = mcap[mcap["symbol"] == s]
                if len(m):
                    r.update({"mcap_shares": float(m.iloc[0]["shares"]), "mcap_face_value": float(m.iloc[0]["face_value"])})
            rows.append(r)
        if len(rows) % 50 < len(todo):
            log.info("listing %s (%d rows)", day.date(), len(rows))
            pd.concat([done, pd.DataFrame(rows)], ignore_index=True).to_csv(LISTING_FILE, index=False)
    out = pd.concat([done, pd.DataFrame(rows)], ignore_index=True)
    out.to_csv(LISTING_FILE, index=False)
    return out


# ---------------------------------------------------------
# Live
# ---------------------------------------------------------

def fetch_live(nse):
    LIVE_DIR.mkdir(parents=True, exist_ok=True)
    out = {}
    for name, url in (("current", CURRENT_URL), ("upcoming", UPCOMING_URL)):
        data = nse.api(url)
        (LIVE_DIR / f"{name}_{date.today():%Y%m%d}.json").write_text(json.dumps(data, indent=1))
        out[name] = data
    return out


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("what", choices=["past", "details", "listing", "live"])
    ap.add_argument("--sme", action="store_true", help="details: also SME issues")
    ap.add_argument("--refresh", action="store_true")
    a = ap.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    nse = client()
    t0 = time.time()
    if a.what == "past":
        fetch_past(nse, refresh=a.refresh)
    elif a.what == "details":
        issues = load_past()
        types = MAINBOARD + (SME if a.sme else ())
        fetch_details(nse, issues[issues["security_type"].isin(types)], refresh=a.refresh)
    elif a.what == "listing":
        issues = load_past()
        fetch_listing(nse, issues[issues["security_type"].isin(MAINBOARD + SME)])
    else:
        print(json.dumps(fetch_live(nse), indent=1)[:5000])
    log.info("done: %d requests, %.1f MB, %.0fs", nse.requests, nse.bytes / 1e6, time.time() - t0)


if __name__ == "__main__":
    main()
