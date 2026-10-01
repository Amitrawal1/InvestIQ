"""How much does survivorship inflate the 12m excess return? (local files only, no DB writes)

Two estimates:

1. Full list, monthly snapshots (bhav_monthly.csv.gz from `market_data.delisted list`): every
   EQ/BE/BZ ISIN on the first trading day of each month, 12m forward return to the snapshot 12
   months later, minus the NIFTY SMALLCAP 250 return. A company that left before the exit snapshot
   gets a terminal value (scenarios below); a survivor whose ISIN vanished (split) gets NaN.
   Stats with and without the departed names give the survivorship effect. Prices are NOT
   split/bonus adjusted here (one snapshot a month cannot be); the survivors' rows are checked
   against the adjusted labels to size that noise, and it hits both groups alike.

   Terminal scenarios for a departed name whose exit snapshot is missing:
       last      last monthly close (holder paid ~ the last price; the most generous case)
       distress  0 for liquidation / compulsory delisting / BZ suspension, else last close
       collapse  distress + 0 for any other exit whose last close is <= 20% of its 3-year peak
                 (IBC resolutions such as DHFL / Reliance Capital, where equity was extinguished)

2. Daily sample (delisted_prices_sample.csv from `market_data.delisted sample`): the real label
   pipeline (growth_model.labels.build_labels) with and without the sample names, plus a check of
   the split/bonus adjustment against `stock_prices` for the control symbol(s).

CLI:  python3 -m market_data.delisted_eval      (prints; writes ml/data/raw/delisted/delisted_eval.json)
"""

import json
import sys

import numpy as np
import pandas as pd

from growth_model.labels import LABELS_FILE, build_labels
from growth_model.prices import BENCHMARK, load_prices

from .delisted import LIST_FILE, MONTHLY_FILE, RAW_DIR, SAMPLE_FILE, terminal_prices

OUT_FILE = RAW_DIR / "delisted_eval.json"
HORIZON = 12                 # months
MIN_PRICE = 1.0
LIQUID_CR = 0.5              # traded value on the snapshot day, INR crore
COLLAPSE = 0.2               # last close <= 20% of the 3y peak
SCENARIOS = ("last", "distress", "collapse")


def _stats(excess, ret):
    excess, ret = excess.dropna(), ret.dropna()
    return {"n": int(len(excess)), "mean_excess": float(excess.mean()), "median_excess": float(excess.median()),
            "beat_rate": float((excess > 0).mean()), "share_ret_le_-90%": float((ret <= -0.9).mean()),
            "share_ret_le_-50%": float((ret <= -0.5).mean())}


def monthly_estimate(index):
    snap = pd.read_csv(MONTHLY_FILE, parse_dates=["price_date"], dtype={"name": str})
    gone = pd.read_csv(LIST_FILE, parse_dates=["last_seen"]).set_index("isin")
    snap = snap.sort_values(["price_date", "isin", "series"]).drop_duplicates(["price_date", "isin"])
    close = snap.pivot(index="price_date", columns="isin", values="close")
    value = snap.pivot(index="price_date", columns="isin", values="value") / 1e7
    dates = close.index

    # 3y peak of monthly closes up to the last snapshot, for the collapse rule
    peak = close.rolling(36, min_periods=1).max()
    last_close = {i: close[i].dropna().iloc[-1] for i in gone.index if i in close.columns}
    last_peak = {i: peak[i][close[i].notna()].iloc[-1] for i in last_close}
    collapsed = {i: last_close[i] <= COLLAPSE * last_peak[i] for i in last_close}

    bench = index[index["index_key"] == BENCHMARK].set_index("price_date")["close"].sort_index()
    bench = bench.reindex(dates, method="ffill")

    rows = []
    for k in range(len(dates) - HORIZON):
        d0, d1 = dates[k], dates[k + HORIZON]
        p0 = close.loc[d0].dropna()
        p0 = p0[p0 >= MIN_PRICE]
        p1 = close.loc[d1].reindex(p0.index)
        f = pd.DataFrame({"isin": p0.index, "date": d0, "p0": p0.values, "p1": p1.values,
                          "value": value.loc[d0].reindex(p0.index).values})
        # simple 6m trend signal (what the market model leans on), for the ranking-quality check
        f["mom6"] = (p0 / close.iloc[k - 6].reindex(p0.index) - 1).values if k >= 6 else np.nan
        f["departed"] = f["isin"].isin(gone.index)
        left = f["departed"] & f["p1"].isna() & f["isin"].map(gone["last_seen"]).lt(d1)
        f["left"] = left
        f["bench"] = bench[d1] / bench[d0] - 1
        for sc in SCENARIOS:
            term = f["isin"].map(last_close)
            if sc != "last":
                zero = f["isin"].map(gone["distress"]).eq(1)
                if sc == "collapse":
                    zero |= f["isin"].map(collapsed).eq(True)
                term = term.where(~zero, 0.0)
            p1s = f["p1"].where(~left, term)
            f[f"ret_{sc}"] = p1s / f["p0"] - 1
        rows.append(f)
    df = pd.concat(rows, ignore_index=True)

    out = {"snapshots": len(dates), "windows": len(dates) - HORIZON, "rows": len(df),
           "departed_rows": int(df["departed"].sum()), "rows_that_left_inside_window": int(df["left"].sum()),
           "departed_isins_with_a_row": int(df.loc[df["departed"], "isin"].nunique())}
    for subset, mask in (("all", np.ones(len(df), bool)), ("liquid", (df["value"] >= LIQUID_CR).values)):
        surv = df[mask & ~df["departed"]]
        res = {"survivors_only": _stats(surv["ret_last"] - surv["bench"], surv["ret_last"])}
        for sc in SCENARIOS:
            sub = df[mask]
            res[f"with_departed_{sc}"] = _stats(sub[f"ret_{sc}"] - sub["bench"], sub[f"ret_{sc}"])
            res[f"effect_mean_{sc}"] = res["survivors_only"]["mean_excess"] - res[f"with_departed_{sc}"]["mean_excess"]
            res[f"effect_median_{sc}"] = (res["survivors_only"]["median_excess"]
                                          - res[f"with_departed_{sc}"]["median_excess"])
            dep = df[mask & df["departed"]]
            res[f"departed_only_{sc}"] = _stats(dep[f"ret_{sc}"] - dep["bench"], dep[f"ret_{sc}"])
        out[subset] = res
    out["trend_ranking"] = trend_ranking(df)
    return out, df


def trend_ranking(df):
    """Does survivorship flatter a trend ranking? Mean per-date rank IC of 6m momentum vs 12m excess
    and the top-minus-bottom decile spread, survivors only vs with departed names."""
    out = {}
    for name, sub in (("survivors_only", df[~df["departed"]]), ("with_departed_distress", df)):
        sub = sub.dropna(subset=["mom6", "ret_distress"])
        ics, spreads = [], []
        for _, g in sub.groupby("date"):
            if len(g) < 100:
                continue
            ics.append(g["mom6"].rank().corr(g["ret_distress"].rank()))
            dec = pd.qcut(g["mom6"].rank(method="first"), 10, labels=False)
            spreads.append(g.loc[dec == 9, "ret_distress"].mean() - g.loc[dec == 0, "ret_distress"].mean())
        out[name] = {"dates": len(ics), "mean_ic": float(np.mean(ics)), "top_minus_bottom_decile": float(np.mean(spreads))}
    return out


def check_against_labels(df):
    """Survivor rows of the monthly method vs the adjusted labels on the same 1st-of-month signal date."""
    from news_pipeline.db import get_connection
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute("SELECT id, isin FROM companies WHERE isin IS NOT NULL")
        ids = pd.DataFrame(cur.fetchall(), columns=["company_id", "isin"])
    finally:
        conn.close()
    labels = pd.read_pickle(LABELS_FILE)
    labels = labels[labels["signal_date"].dt.day == 1][["company_id", "signal_date", "ret_12m"]]
    m = (df[~df["departed"]].merge(ids, on="isin")
         .assign(signal_date=lambda x: x["date"].dt.to_period("M").dt.to_timestamp())
         .merge(labels, on=["company_id", "signal_date"]).dropna(subset=["ret_last", "ret_12m"]))
    diff = (m["ret_last"] - m["ret_12m"]).abs()
    return {"matched_rows": int(len(m)), "corr": float(m["ret_last"].corr(m["ret_12m"])),
            "share_abs_diff_gt_10pp": float((diff > 0.10).mean()),
            "share_abs_diff_gt_40pp": float((diff > 0.40).mean()),
            "mean_ret_monthly_method": float(m["ret_last"].mean()), "mean_ret_labels": float(m["ret_12m"].mean())}


def sample_estimate(stocks, index):
    from growth_model.prices import load_companies

    from .delisted import load_delisted
    raw = pd.read_csv(SAMPLE_FILE, parse_dates=["price_date"])
    gone = pd.read_csv(LIST_FILE)
    out = {"names": {}}

    # adjustment check on controls (listed today, so also in stock_prices)
    comp = load_companies().set_index("symbol")
    for isin in raw.loc[raw["isin"].str.startswith("CONTROL:"), "isin"].unique():
        sym = isin.split(":", 1)[1]
        mine = raw[raw["isin"] == isin].set_index("price_date")["adj_close"]
        theirs = stocks[stocks["company_id"] == comp.loc[sym, "company_id"]].set_index("price_date")["close"]
        both = pd.concat([mine, theirs], axis=1, keys=["nse_adj", "upstox"]).dropna()
        rel = (both["nse_adj"] / both["upstox"] - 1).abs()
        rel_raw = (raw[raw["isin"] == isin].set_index("price_date")["close"].reindex(both.index) / both["upstox"] - 1).abs()
        out[f"control_{sym}"] = {"days": int(len(both)), "median_abs_diff_adj": float(rel.median()),
                                 "p99_abs_diff_adj": float(rel.quantile(0.99)),
                                 "median_abs_diff_unadjusted": float(rel_raw.median()),
                                 "corp_actions": raw.loc[(raw["isin"] == isin) & raw["corp_action"], "price_date"]
                                 .dt.strftime("%Y-%m-%d").tolist()}

    dl = raw[~raw["isin"].str.startswith("CONTROL:")]
    meta = gone.set_index("isin")
    for isin, g in dl.groupby("isin"):
        g = g.sort_values("price_date")
        px = g.set_index("price_date")["adj_close"]
        r252 = px.pct_change(252)          # 12m trailing return on trading days
        out["names"][meta.loc[isin, "symbol"]] = {
            "exit_kind": meta.loc[isin, "exit_kind"], "first": f"{px.index[0]:%Y-%m-%d}",
            "last": f"{px.index[-1]:%Y-%m-%d}", "days": int(len(px)), "last_series": g["series"].iloc[-1],
            "corp_actions": int(g["corp_action"].sum()), "first_close": float(px.iloc[0]),
            "last_close": float(px.iloc[-1]), "ret_first_to_last": float(px.iloc[-1] / px.iloc[0] - 1),
            "drawdown_from_peak": float(px.iloc[-1] / px.max() - 1), "worst_12m": float(r252.min()),
        }

    extra, comp_d = load_delisted("local", prices_file=SAMPLE_FILE)
    base = pd.read_pickle(LABELS_FILE)
    res = {"baseline": _stats(base["excess_12m"], base["ret_12m"])}
    for name, dv, col in (("terminal_last", 1.0, None), ("terminal_zero_distress", 0.0, None),
                          ("terminal_zero_distress_or_collapse", 0.0, COLLAPSE)):
        lab = build_labels(pd.concat([stocks, extra], ignore_index=True), index,
                           terminal=terminal_prices(extra, comp_d, distress_value=dv, collapse=col))
        res[name] = _stats(lab["excess_12m"], lab["ret_12m"])
        d = lab[lab["company_id"] < 0]
        res[name + "_sample_rows"] = _stats(d["excess_12m"], d["ret_12m"])
    out["labels"] = res
    return out


def main(argv=None):
    stocks, index = load_prices()
    report = {}
    monthly, df = monthly_estimate(index)
    report["monthly"] = monthly
    try:
        report["monthly_vs_labels"] = check_against_labels(df)
    except Exception as exc:                       # DB unavailable: skip the cross-check
        report["monthly_vs_labels"] = {"error": str(exc)}
    if SAMPLE_FILE.exists():
        report["sample"] = sample_estimate(stocks, index)
    OUT_FILE.write_text(json.dumps(report, indent=2, default=str))
    print(json.dumps(report, indent=2, default=str))
    print(f"\nsaved {OUT_FILE}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
