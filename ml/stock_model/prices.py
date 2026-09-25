"""Load and clean the NIFTY 50 daily price history (ml/data/raw/nifty50_historical_data.csv).

Only price/volume columns are kept. The file's fundamental columns (PE_Ratio, EPS,
Market_Cap, Price_to_Book, Beta, 52Week_High/Low, ...) hold a single present-day
snapshot repeated on every historical row, so using them would leak the future.
Rolling equivalents (e.g. distance from the 52-week high) are computed from prices
instead, in features_panel.py.
"""

import numpy as np
import pandas as pd

from .config import ML_DIR

RAW_CSV = ML_DIR / "data" / "raw" / "nifty50_historical_data.csv"
CLEAN_FILE = ML_DIR / "data" / "processed" / "nifty50_prices.parquet"

KEEP_COLUMNS = ["Date", "Ticker", "Company_Name", "Sector", "Open", "High", "Low", "Close", "Volume"]

# Columns that are a present-day snapshot copied onto every row (verified: one
# distinct value per ticker across all 27 years) - never use them as features.
LEAKY_COLUMNS = [
    "Market_Cap", "PE_Ratio", "Forward_PE", "PEG_Ratio", "Price_to_Book",
    "Dividend_Yield", "EPS", "Beta", "52Week_High", "52Week_Low",
]


def load_raw(path=RAW_CSV):
    df = pd.read_csv(path, usecols=lambda c: c in KEEP_COLUMNS + ["Dividend"])

    df["date"] = (
        pd.to_datetime(df["Date"], utc=True)
        .dt.tz_convert("Asia/Kolkata")
        .dt.tz_localize(None)
        .dt.normalize()
    )

    df = df.rename(columns={
        "Ticker": "ticker",
        "Company_Name": "company_name",
        "Sector": "sector",
        "Open": "open",
        "High": "high",
        "Low": "low",
        "Close": "close",
        "Volume": "volume",
    })

    df["symbol"] = df["ticker"].str.replace(".NS", "", regex=False)

    return df[["date", "ticker", "symbol", "company_name", "sector",
               "open", "high", "low", "close", "volume"]]


def clean_prices(df):
    """Drop unusable rows and report what was removed."""

    report = {"rows_in": len(df), "tickers_in": df["ticker"].nunique()}

    for col in ["open", "high", "low", "close", "volume"]:
        df[col] = pd.to_numeric(df[col], errors="coerce")

    before = len(df)
    df = df.drop_duplicates(["ticker", "date"], keep="last")
    report["duplicates_dropped"] = before - len(df)

    before = len(df)
    df = df[df["close"].notna() & (df["close"] > 0)]
    report["bad_close_dropped"] = before - len(df)

    # Zero volume on a trading day means "no data", not a real print
    df.loc[df["volume"] <= 0, "volume"] = np.nan
    report["zero_volume_set_nan"] = int(df["volume"].isna().sum())

    df = df.sort_values(["ticker", "date"]).reset_index(drop=True)
    df, spike_report = _fix_extreme_moves(df)
    report.update(spike_report)

    report["rows_out"] = len(df)
    report["tickers_out"] = df["ticker"].nunique()
    report["date_min"], report["date_max"] = df["date"].min().date(), df["date"].max().date()

    return df, report


JUMP_THRESHOLD = 0.5  # |log return| above this is not a normal daily move


def _fix_extreme_moves(df, threshold=JUMP_THRESHOLD):
    """Separate bad data from real corporate actions.

    * A spike that reverses the next day (e.g. a lone 254 between two 2.32 closes)
      is a data glitch: that bar is dropped.
    * A jump that does NOT reverse is a structural break in the series, such as the
      2008 Bajaj demerger. Returns across it would be meaningless, so only the
      history after the break is kept for that ticker.
    """

    report = {"glitch_bars_dropped": 0, "structural_breaks": {}}

    log_return = np.log(df["close"]).groupby(df["ticker"]).diff()
    next_log_return = log_return.groupby(df["ticker"]).shift(-1)

    # Spike up then straight back down (or vice versa) => single bad bar
    glitch = (log_return.abs() > threshold) & ((log_return + next_log_return).abs() < 0.2)
    report["glitch_bars_dropped"] = int(glitch.sum())
    df = df[~glitch].reset_index(drop=True)

    # Recompute on the cleaned series; whatever is left is a genuine level shift
    log_return = np.log(df["close"]).groupby(df["ticker"]).diff()
    breaks = df.loc[log_return.abs() > threshold, ["ticker", "date"]]

    keep = pd.Series(True, index=df.index)
    for ticker, group in breaks.groupby("ticker"):
        last_break = group["date"].max()
        keep &= ~((df["ticker"] == ticker) & (df["date"] < last_break))
        report["structural_breaks"][ticker] = str(last_break.date())

    report["rows_before_breaks_dropped"] = int((~keep).sum())

    return df[keep].reset_index(drop=True), report


def coverage_table(df):
    """Per-ticker history span, used to spot short or stale series."""

    return (
        df.groupby(["ticker", "sector"])
        .agg(rows=("date", "size"), start=("date", "min"), end=("date", "max"),
             missing_volume=("volume", lambda s: int(s.isna().sum())))
        .reset_index()
        .sort_values("start")
    )


def trading_calendar_gaps(df, max_gap_days=7):
    """Calendar gaps longer than a normal weekend/holiday break, per ticker."""

    gaps = df.groupby("ticker")["date"].diff().dt.days
    flagged = df.loc[gaps > max_gap_days, ["ticker", "date"]].copy()
    flagged["gap_days"] = gaps[gaps > max_gap_days]

    return flagged


def build_clean_file(path=RAW_CSV, out=CLEAN_FILE):
    df, report = clean_prices(load_raw(path))

    out.parent.mkdir(parents=True, exist_ok=True)
    try:
        df.to_parquet(out, index=False)
    except (ImportError, ValueError):
        out = out.with_suffix(".csv")
        df.to_csv(out, index=False)

    return df, report, out


def load_clean(path=CLEAN_FILE):
    """Clean prices, building the file on first use."""

    csv_fallback = path.with_suffix(".csv")

    if path.exists():
        return pd.read_parquet(path)
    if csv_fallback.exists():
        return pd.read_csv(csv_fallback, parse_dates=["date"])

    return build_clean_file(out=path)[0]
