"""Forward-return labels: did a stock beat the NIFTY SMALLCAP 250 over the next 1/3/6/12 months?

One row per (company, signal_date). Signal dates are the 1st and 16th of every month, the same
cadence the rankings are rebuilt on, so a model trained on these rows answers exactly the question
the Predictor page asks: "given what was known on this date, which companies will do best?"

Timing (no look-ahead):
    signal_date D   features may use anything known on or before D
    entry day E     the first benchmark trading day strictly after D (you act on the ranking the
                    next session); entry price = the stock's close on E, or its last close within
                    ENTRY_STALE trading days before E (a stock with no recent trade gets no row)
    exit day X_h    E + h trading days (h = 21, 63, 126, 252 ~ 1, 3, 6, 12 months) on the
                    benchmark calendar; exit price = last close within EXIT_STALE days before X_h.
                    If the stock stopped trading earlier than that, the label is NaN, not a loss:
                    we can't tell a delisting from a data gap. Labels past the end of the data are NaN.
                    Opt-in (--include-delisted): for companies that left NSE (market_data/delisted.py)
                    the exit price after the last trade is a terminal value instead: the last close
                    (merger, voluntary delisting) or --distress-value x last close (liquidation,
                    compulsory delisting, BZ suspension, or a last close <= 20% of its 3y peak;
                    default 0 = equity wiped out).
    series breaks   NSE circuit limits keep a normal day within about +-20%, so a close-to-close move
                    above +100% or below -60% is a data break (pre-listing placeholder candles, an
                    unadjusted corporate action, a relisting). A label whose window [E, X_h] contains a
                    break is NaN instead of a fake 100x winner.
    penny filter    no row when the entry price is below MIN_PRICE (Rs 1: untradeable placeholders).

Columns per horizon h (1m, 3m, 6m, 12m):
    ret_h       stock simple return E -> X_h
    bench_h     NIFTY SMALLCAP 250 return over the same days
    excess_h    ret_h - bench_h
    beat_h      1 if excess_h > 0 else 0 (NaN when excess_h is NaN)
    top_q_h     1 if excess_h is in the top 20% of that signal date's cross-section (the "best
                small companies" target); needs >= MIN_CROSS_SECTION stocks on the date

Context columns (known at D, used as filters, not targets):
    close_d            last close on or before D
    adv_60d_cr         median daily traded value (close x volume) over the 60 trading days to D,
                       INR crore (liquidity filter: tiny values mean the stock is hard to trade)
    days_listed        trading days with a price up to D
    suspect_h          |ret_h| > 5 (a 500%+ move): kept, but worth checking for bad candles

Known bias: `stock_prices` only has companies listed today (no delisted names), so historical
returns are survivorship-biased upwards (unless --include-delisted; see market_data/DELISTED.md). Excess-vs-benchmark and cross-sectional (top_q) labels are
less affected than raw returns, and the backtest must be read with this in mind.

CLI:  python3 -m growth_model.labels [--refresh-prices] [--start 2017-01-01]
      writes ml/data/processed/growth_labels.pkl and prints a summary
      [--include-delisted [--distress-value 0]] writes growth_labels_delisted.pkl instead
"""

import argparse
import time

import numpy as np
import pandas as pd

from .prices import BENCHMARK, CACHE_DIR, load_companies, load_prices

HORIZONS = {"1m": 21, "3m": 63, "6m": 126, "12m": 252}
ENTRY_STALE = 5             # trading days a stock's last close may lag the entry day
EXIT_STALE = 10             # ... or the exit day
ADV_WINDOW = 60
ADV_MIN_PERIODS = 20
MIN_CROSS_SECTION = 50      # stocks with an excess return on a date before top_q is defined
TOP_Q = 0.8
SUSPECT_MOVE = 5.0
BREAK_UP = 1.0              # +100% in one trading step
BREAK_DOWN = -0.6           # -60%
MIN_PRICE = 1.0

LABELS_FILE = CACHE_DIR / "growth_labels.pkl"
LABELS_DELISTED_FILE = CACHE_DIR / "growth_labels_delisted.pkl"


def signal_dates(start, end):
    """1st and 16th of every month in [start, end]."""
    months = pd.date_range(pd.Timestamp(start).replace(day=1), end, freq="MS")
    dates = sorted(list(months) + [m + pd.Timedelta(days=15) for m in months])
    return [d for d in dates if pd.Timestamp(start) <= d <= pd.Timestamp(end)]


def _wide(stocks, calendar):
    """Stock closes / traded values as (benchmark calendar x company) matrices.

    Days the stock traded but the benchmark didn't (special sessions) are folded in by
    forward-filling on the union of dates before re-indexing to the benchmark calendar.
    """
    close = stocks.pivot_table(index="price_date", columns="company_id", values="close", aggfunc="last")
    value = (stocks.assign(tv=stocks["close"] * stocks["volume"] / 1e7)
             .pivot_table(index="price_date", columns="company_id", values="tv", aggfunc="last"))
    # a break is flagged on the day of the jump, comparing each close with the stock's previous close
    step = close.apply(lambda col: col.dropna().pct_change()).reindex(close.index)
    breaks = ((step > BREAK_UP) | (step < BREAK_DOWN)).astype(int)
    union = close.index.union(calendar)
    traded = close.reindex(union).notna()
    close = close.reindex(union)
    breaks = breaks.reindex(union, fill_value=0).cumsum()
    return close, value.reindex(union), traded, breaks


def _apply_terminal(exit_px, terminal):
    exit_px = exit_px.copy()
    for cid, (last_traded, value) in terminal.items():
        if cid in exit_px.columns:
            exit_px.loc[exit_px.index > last_traded, cid] = value
    return exit_px


def build_labels(stocks, index, start="2017-01-01", terminal=None):
    """terminal: optional {company_id: (last_traded, value)} for companies that left NSE; after
    last_traded their exit price is `value` (see market_data.delisted.terminal_prices)."""
    bench = (index[index["index_key"] == BENCHMARK]
             .set_index("price_date")["close"].sort_index())
    calendar = bench.index
    close, value, traded, breaks = _wide(stocks, calendar)

    # "last close within N trading days" on the benchmark calendar
    entry_px = close.ffill(limit=ENTRY_STALE).reindex(calendar)
    exit_px = close.ffill(limit=EXIT_STALE).reindex(calendar)
    if terminal:
        exit_px = _apply_terminal(exit_px, terminal)
    last_px = close.ffill().reindex(calendar)
    adv = value.rolling(ADV_WINDOW, min_periods=ADV_MIN_PERIODS).median().ffill(limit=ENTRY_STALE).reindex(calendar)
    days_listed = traded.cumsum().reindex(calendar)
    # cumulative break count up to each calendar day (special-session breaks roll into the next day)
    breaks = breaks.reindex(calendar, method="ffill")
    n_breaks = int(breaks.iloc[-1].sum())

    n = len(calendar)
    rows = []
    for d in signal_dates(start, calendar[-1]):
        pos_e = calendar.searchsorted(d, side="right")      # first trading day strictly after D
        if pos_e >= n:
            continue
        pos_d = pos_e - 1                                    # last trading day on/before D
        if pos_d < 0:
            continue
        p_entry = entry_px.iloc[pos_e]
        ok = p_entry.notna() & (p_entry >= MIN_PRICE)
        b_entry = breaks.iloc[pos_e][ok].values
        frame = pd.DataFrame({
            "company_id": p_entry.index[ok],
            "signal_date": d,
            "entry_date": calendar[pos_e],
            "entry_price": p_entry[ok].values,
            "close_d": last_px.iloc[pos_d][ok].values,
            "adv_60d_cr": adv.iloc[pos_d][ok].values,
            "days_listed": days_listed.iloc[pos_d][ok].values,
        })
        for h, steps in HORIZONS.items():
            pos_x = pos_e + steps
            if pos_x >= n:
                frame[f"ret_{h}"] = np.nan
                frame[f"bench_{h}"] = np.nan
                continue
            p_exit = exit_px.iloc[pos_x][ok].values
            clean = breaks.iloc[pos_x][ok].values == b_entry
            frame[f"ret_{h}"] = np.where(clean, p_exit / frame["entry_price"].values - 1, np.nan)
            frame[f"bench_{h}"] = bench.iloc[pos_x] / bench.iloc[pos_e] - 1
        rows.append(frame)

    labels = pd.concat(rows, ignore_index=True)
    for h in HORIZONS:
        excess = labels[f"ret_{h}"] - labels[f"bench_{h}"]
        labels[f"excess_{h}"] = excess
        labels[f"beat_{h}"] = np.where(excess.isna(), np.nan, (excess > 0).astype(float))
        pct = excess.groupby(labels["signal_date"]).rank(pct=True)
        count = excess.groupby(labels["signal_date"]).transform("count")
        top = np.where(excess.isna() | (count < MIN_CROSS_SECTION), np.nan, (pct >= TOP_Q).astype(float))
        labels[f"top_q_{h}"] = top
        labels[f"suspect_{h}"] = labels[f"ret_{h}"].abs() > SUSPECT_MOVE
    labels["company_id"] = labels["company_id"].astype(int)
    labels.attrs["series_breaks"] = n_breaks
    return labels


def summarise(labels, companies):
    print(f"\n{len(labels):,} rows, {labels['company_id'].nunique():,} companies, "
          f"{labels['signal_date'].nunique()} signal dates "
          f"({labels['signal_date'].min():%Y-%m-%d} -> {labels['signal_date'].max():%Y-%m-%d}); "
          f"{labels.attrs.get('series_breaks', 0)} price-series breaks excluded")
    print(f"\n{'horizon':<8}{'labelled':>10}{'beat rate':>11}{'median excess':>15}{'suspect':>9}  last labelled signal")
    for h in HORIZONS:
        col = labels[f"excess_{h}"]
        has = col.notna()
        last = labels.loc[has, "signal_date"].max()
        print(f"{h:<8}{has.sum():>10,}{labels[f'beat_{h}'].mean():>10.1%}{col.median():>14.1%}"
              f"{int(labels[f'suspect_{h}'].sum()):>9}  {last:%Y-%m-%d}")

    liquid = labels["adv_60d_cr"] >= 0.5
    print(f"\nliquid rows (median traded value >= 0.5 cr/day): {liquid.mean():.0%}; "
          f"6m beat rate liquid {labels.loc[liquid, 'beat_6m'].mean():.1%} "
          f"vs illiquid {labels.loc[~liquid, 'beat_6m'].mean():.1%}")

    sus = labels[labels["suspect_12m"]].merge(companies[["company_id", "symbol"]], on="company_id", how="left")
    if len(sus):
        top = (sus.groupby("symbol")["ret_12m"].max().sort_values(ascending=False).head(10))
        print("\nlargest 12m moves (check for bad candles):")
        for sym, r in top.items():
            print(f"  {sym:<14}{r:>9.0%}")


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--refresh-prices", action="store_true", help="re-download prices from TiDB")
    ap.add_argument("--start", default="2017-01-01", help="first signal date (needs ~1y of prior prices)")
    ap.add_argument("--include-delisted", action="store_true",
                    help="add companies that left NSE (backtests only; writes growth_labels_delisted.pkl)")
    ap.add_argument("--delisted-source", default="local", choices=["local", "db"])
    ap.add_argument("--distress-value", type=float, default=0.0,
                    help="terminal value of a distress exit as a fraction of its last close")
    args = ap.parse_args(argv)

    t0 = time.time()
    if not args.include_delisted:
        stocks, index = load_prices(refresh=args.refresh_prices)
        labels = build_labels(stocks, index, start=args.start)
        labels.to_pickle(LABELS_FILE)
        summarise(labels, load_companies())
        print(f"\nsaved {LABELS_FILE} in {time.time() - t0:.0f}s")
        return

    from market_data.delisted import load_delisted, terminal_prices
    stocks, index = load_prices(refresh=args.refresh_prices)
    extra, gone = load_delisted(args.delisted_source)
    stocks = pd.concat([stocks, extra], ignore_index=True)
    labels = build_labels(stocks, index, start=args.start,
                          terminal=terminal_prices(extra, gone, distress_value=args.distress_value))
    labels.to_pickle(LABELS_DELISTED_FILE)
    summarise(labels, pd.concat([load_companies(), gone[["company_id", "symbol"]]], ignore_index=True))
    print(f"\nsaved {LABELS_DELISTED_FILE} in {time.time() - t0:.0f}s")


if __name__ == "__main__":
    main()
