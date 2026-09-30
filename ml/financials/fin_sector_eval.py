"""Quick, honest check of the bank/NBFC/insurer features (fin_sector_features.py) against returns.

Question: among financial-sector companies on a signal date, do these features rank the ones that
go on to beat the NIFTY SMALLCAP 250 over the next 6 / 12 months?

Data:
    labels     growth_model/labels.py (ml/data/processed/growth_labels.pkl): 1st and 16th of each
               month, excess_6m / excess_12m = stock return - Smallcap 250 return, entry the next
               trading day after the signal date.
    features   fin_sector_features.py rows joined as-of: on signal date D a company gets the row
               with the latest period_end among rows filed on or before D (same rule as
               rankings/build.py), and nothing if that period ended more than 275 days before D.
    universe   financial-sector companies in scope of fin_sector_features, median traded value
               >= 0.5 cr/day over 60 days and >= 1 year of trading (the market model's universe).

Metrics, per test year (2019 onwards) and overall:
    ic         mean over signal dates of the Spearman correlation between the feature and the
               excess return (dates with < MIN_NAMES companies having the feature are skipped)
    pos        share of signal dates with IC > 0;  yrs+ = test years with mean IC > 0
    spread     blend only: mean excess of the top 20% minus the bottom 20% (clipped to [-100%, 300%])
Blends (no fitting unless stated):
    blend_fixed   equal-weight mean of cross-sectional percentiles of the BLEND features below, each
                  with a direction fixed in advance from textbook priors (e.g. lower cost-to-income is
                  better); needs >= 3 of them, missing ones are skipped
    blend_wf      walk-forward: for test year Y, keep the features whose mean IC over earlier years
                  (label windows ended before Y; purged) is >= 0.02 in absolute value, signed by that
                  IC; equal weight
    trend6        the market model's price-trend score (growth_model/market_model.py) in the same
                  universe, for scale

Caveats: survivorship (prices exist only for companies listed today), overlapping 6/12-month
windows on 1st/16th dates (dates within a year are far from independent: a year is closer to
one observation than to 24), and a cross-section of ~40-110 names. Treat results as indicative.

CLI:  python3 -m financials.fin_sector_eval [--horizon 6m --horizon 12m] [--out report.csv]
"""

import argparse
import warnings

import numpy as np
import pandas as pd
from scipy.stats import spearmanr

from .config import ML_DIR
from .fin_sector_features import build_feature_table, load_extract, raw_from_extract

PROCESSED = ML_DIR / "data" / "processed"
LABELS_FILE = PROCESSED / "growth_labels.pkl"
MARKET_FEATURES_FILE = PROCESSED / "growth_market_features.pkl"

STALE_DAYS = 275
MIN_ADV_CR = 0.5
MIN_DAYS_LISTED = 252
MIN_NAMES = 15
FIRST_TEST_YEAR = 2019
PURGE_DAYS = {"6m": 190, "12m": 375}
CLIP = (-1.0, 3.0)
WF_MIN_IC = 0.02

# feature -> higher is better (fixed in advance, not fitted)
DIRECTIONS = {
    "net_revenue_yoy": True, "net_revenue_ttm_growth": True, "nii_yoy": True, "nii_ttm_growth": True,
    "ppop_yoy": True, "ppop_ttm_growth": True, "net_profit_yoy": True, "net_profit_ttm_growth": True,
    "net_profit_yoy_accel": True, "eps_ttm_growth": True, "advances_growth_1y": True,
    "deposits_growth_1y": True, "nim": True, "cost_to_income_ttm": False, "credit_cost": False,
    "credit_cost_to_income_ttm": False, "roa": True, "roe": True, "roa_reported": True,
    "leverage": False, "cet1_ratio": True, "cet1_change_1y": True, "solvency_ratio": True,
    "loan_to_deposit": True, "gross_npa_pct": False, "net_npa_pct": False,
    "gross_npa_change_1y": False, "net_npa_change_1y": False, "provision_coverage": True,
    "combined_ratio": False, "claims_ratio": False,
    "flag_asset_quality_worsening": False, "flag_roa_collapse": False,
}
# blend_fixed: growth, profitability/efficiency, asset quality; one per idea where they overlap
BLEND = ["net_revenue_ttm_growth", "net_profit_ttm_growth", "ppop_ttm_growth", "roa", "roe",
         "cost_to_income_ttm", "credit_cost_to_income_ttm", "gross_npa_pct", "gross_npa_change_1y",
         "cet1_ratio"]
TREND_SIGNALS = ["dist_52w_high", "ma200_gap", "ma50_over_200", "rel_6m", "rel_3m"]


def feature_panel(table, labels):
    """As-of join of feature rows onto (company, signal_date) label rows."""

    t = table[table["company_id"].notna()].copy()
    t["company_id"] = t["company_id"].astype(int)
    t = t.sort_values(["company_id", "filing_date", "period_end"])
    # Only a row whose period_end beats every earlier-filed row can ever be "latest period"
    t = t[t["period_end"] >= t.groupby("company_id")["period_end"].cummax()]
    t = t.drop_duplicates(["company_id", "filing_date"], keep="last")
    lab = labels[labels["company_id"].isin(t["company_id"].unique())].copy()
    # known on or before D: anything filed up to the end of the signal date
    lab["asof"] = lab["signal_date"] + pd.Timedelta(hours=23, minutes=59, seconds=59)
    panel = pd.merge_asof(lab.sort_values("asof"), t.rename(columns={"filing_date": "fd"}).sort_values("fd"),
                          left_on="asof", right_on="fd", by="company_id", direction="backward")
    stale = (panel["signal_date"] - panel["period_end"]).dt.days > STALE_DAYS
    feats = [c for c in table.columns if c in DIRECTIONS or c in BLEND]
    panel.loc[stale | panel["period_end"].isna(), feats] = np.nan
    universe = (panel["adv_60d_cr"] >= MIN_ADV_CR) & (panel["days_listed"] >= MIN_DAYS_LISTED)
    return panel[universe & panel["period_end"].notna() & ~stale].reset_index(drop=True)


def _pct(frame, feature, higher):
    p = frame.groupby("signal_date")[feature].rank(pct=True)
    return p if higher else 1 - p


def add_blends(panel):
    parts = []
    for f in BLEND:
        parts.append(_pct(panel, f, DIRECTIONS[f]).rename(f))
    parts = pd.concat(parts, axis=1)
    raw = parts.mean(axis=1).where(parts.notna().sum(axis=1) >= 3)
    panel["blend_fixed"] = raw.groupby(panel["signal_date"]).rank(pct=True)
    return panel


def ic_by_date(panel, col, h):
    out = []
    for d, g in panel.groupby("signal_date"):
        g = g[[col, f"excess_{h}"]].dropna()
        if len(g) < MIN_NAMES or g[col].nunique() < 3:
            continue
        out.append((d, spearmanr(g[col], g[f"excess_{h}"]).statistic, len(g)))
    frame = pd.DataFrame(out, columns=["signal_date", "ic", "n"])
    frame["signal_date"] = pd.to_datetime(frame["signal_date"])
    return frame


def spread_by_date(panel, col, h):
    rows = []
    for d, g in panel.groupby("signal_date"):
        g = g[[col, f"excess_{h}"]].dropna()
        if len(g) < MIN_NAMES:
            continue
        p = g[col].rank(pct=True)
        ex = g[f"excess_{h}"].clip(*CLIP)
        rows.append((d, ex[p > 0.8].mean() - ex[p <= 0.2].mean(), ex[p > 0.8].mean(), ex.mean()))
    frame = pd.DataFrame(rows, columns=["signal_date", "spread", "top20", "all"])
    frame["signal_date"] = pd.to_datetime(frame["signal_date"])
    return frame


def flag_effect(panel, h):
    """Red flags (booleans have no useful rank IC): mean excess of flagged minus unflagged names on
    the same signal date, averaged over dates, per test year."""

    rows = []
    for flag in [c for c in panel.columns if c.startswith("flag_")]:
        per_date = []
        for d, g in panel[panel["signal_date"].dt.year >= FIRST_TEST_YEAR].groupby("signal_date"):
            g = g[[flag, f"excess_{h}"]].dropna()
            on, off = g[g[flag].astype(bool)], g[~g[flag].astype(bool)]
            if len(on) >= 3 and len(off) >= 3:
                ex = f"excess_{h}"
                per_date.append((d, on[ex].clip(*CLIP).mean() - off[ex].clip(*CLIP).mean(), len(on), len(g)))
        if not per_date:
            continue
        f = pd.DataFrame(per_date, columns=["signal_date", "gap", "flagged", "names"])
        by_year = f.groupby(f["signal_date"].dt.year)["gap"].mean()
        rows.append({"flag": flag, "dates": len(f), "flagged_per_date": round(f["flagged"].median(), 1),
                     "names": int(f["names"].median()), "gap": f["gap"].mean(),
                     "yrs_neg": f"{int((by_year < 0).sum())}/{len(by_year)}",
                     **{str(y): v for y, v in by_year.items()}})
    out = pd.DataFrame(rows)
    years = sorted(c for c in out.columns if c.isdigit())
    return out[[c for c in out.columns if not c.isdigit()] + years]


def walk_forward_blend(panel, ic_tables, h):
    """blend_wf per test year from features' IC on earlier (purged) signal dates."""

    panel["blend_wf"] = np.nan
    chosen = {}
    for year in sorted(panel["signal_date"].dt.year.unique()):
        if year < FIRST_TEST_YEAR:
            continue
        cutoff = pd.Timestamp(year, 1, 1) - pd.Timedelta(days=PURGE_DAYS[h])
        picks = {}
        for f, ics in ic_tables.items():
            past = ics[ics["signal_date"] < cutoff]
            if len(past) >= 12 and abs(past["ic"].mean()) >= WF_MIN_IC:
                picks[f] = past["ic"].mean() > 0
        chosen[year] = picks
        rows = panel["signal_date"].dt.year == year
        if len(picks) < 2:
            continue
        sub = panel[rows]
        parts = pd.concat([_pct(sub, f, higher).rename(f) for f, higher in picks.items()], axis=1)
        raw = parts.mean(axis=1).where(parts.notna().sum(axis=1) >= 2)
        panel.loc[rows, "blend_wf"] = raw.groupby(sub["signal_date"]).rank(pct=True)
    return chosen


def add_trend(panel):
    if not MARKET_FEATURES_FILE.exists():
        return panel
    from growth_model.market_features import rank_features
    mf = rank_features(pd.read_pickle(MARKET_FEATURES_FILE))
    mf = mf[mf["company_id"].isin(panel["company_id"].unique())]
    cols = [c for c in TREND_SIGNALS + ["down_days_3m"] if c in mf.columns]
    panel = panel.merge(mf[["company_id", "signal_date", *cols]], on=["company_id", "signal_date"], how="left")
    signals = panel[[c for c in TREND_SIGNALS if c in panel.columns]].copy()
    if "down_days_3m" in panel.columns:
        signals["inv_down"] = 1 - panel["down_days_3m"]
    panel["trend6"] = signals.fillna(0.5).mean(axis=1)
    return panel


def evaluate(panel, h, features):
    panel = panel[panel[f"excess_{h}"].notna()].copy()
    ic_tables = {f: ic_by_date(panel, f, h) for f in features}
    chosen = walk_forward_blend(panel, ic_tables, h)
    for col in ("blend_fixed", "blend_wf", "trend6"):
        if col in panel.columns:
            ic_tables[col] = ic_by_date(panel, col, h)
    rows = []
    for f, ics in ic_tables.items():
        ics = ics[ics["signal_date"].dt.year >= FIRST_TEST_YEAR]
        if ics.empty:
            continue
        by_year = ics.groupby(ics["signal_date"].dt.year)["ic"].mean()
        # signed so that + means "the fixed prior direction worked"
        sign = 1 if DIRECTIONS.get(f, True) else -1
        rows.append({"feature": f, "dates": len(ics), "names": int(ics["n"].median()),
                     "ic": ics["ic"].mean() * sign, "pos": (ics["ic"] * sign > 0).mean(),
                     "yrs_pos": f"{int((by_year * sign > 0).sum())}/{len(by_year)}",
                     **{str(y): v * sign for y, v in by_year.items()}})
    result = pd.DataFrame(rows)
    years = sorted(c for c in result.columns if c.isdigit())
    result = result[[c for c in result.columns if not c.isdigit()] + years]
    spreads = {}
    for col in ("blend_fixed", "blend_wf", "trend6"):
        if col in panel.columns:
            s = spread_by_date(panel[panel["signal_date"].dt.year >= FIRST_TEST_YEAR], col, h)
            spreads[col] = s.groupby(s["signal_date"].dt.year)[["spread", "top20", "all"]].mean()
    return result, spreads, chosen


def load_panel():
    raw = raw_from_extract(load_extract())
    table = build_feature_table(raw)
    labels = pd.read_pickle(LABELS_FILE)
    panel = add_blends(feature_panel(table, labels))
    return add_trend(panel), table


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--horizon", action="append", choices=["6m", "12m"])
    ap.add_argument("--segment", choices=["all", "bank", "nbfc", "lending_nbfc"], default="all")
    ap.add_argument("--out", help="write the per-feature table(s) to this CSV prefix")
    args = ap.parse_args(argv)
    warnings.filterwarnings("ignore")
    pd.set_option("display.width", 250)

    panel, table = load_panel()
    if args.segment == "lending_nbfc":
        panel = panel[(panel["company_format"] == "nbfc") & (panel["loans_to_assets"] >= 0.5)]
    elif args.segment != "all":
        panel = panel[panel["company_format"] == args.segment]
    print(f"panel ({args.segment}): {len(panel):,} company-dates, {panel['company_id'].nunique()} companies, "
          f"{panel['signal_date'].nunique()} signal dates {panel['signal_date'].min():%Y-%m} .. "
          f"{panel['signal_date'].max():%Y-%m}; median names per date "
          f"{int(panel.groupby('signal_date').size().median())}")
    features = [f for f in DIRECTIONS if f in panel.columns]
    for h in args.horizon or ["6m", "12m"]:
        result, spreads, chosen = evaluate(panel, h, features)
        print(f"\n=== {h}: IC signed by the fixed prior direction (+ = prior was right) ===")
        print(result.sort_values("ic", ascending=False).round(3).to_string(index=False))
        for col, s in spreads.items():
            print(f"\n{col}: top-20% minus bottom-20% excess ({h}), by year")
            print(s.round(3).to_string())
        flags = flag_effect(panel[panel[f"excess_{h}"].notna()], h)
        if len(flags):
            print(f"\nred flags: excess ({h}) of flagged minus unflagged names, same date (negative = flag worked)")
            print(flags.round(3).to_string(index=False))
        print("\nblend_wf picks per test year:", {int(y): sorted(f"{'+' if s else '-'}{f}" for f, s in p.items())
                                                  for y, p in chosen.items()})
        if args.out:
            result.to_csv(f"{args.out}_{args.segment}_{h}.csv", index=False)


if __name__ == "__main__":
    main()
