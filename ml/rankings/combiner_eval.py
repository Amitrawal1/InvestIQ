"""Walk-forward test of the InvestIQ combiner (`investiq-v1`): how much weight the market model
should get against the financial model, and whether the bank/NBFC/insurer recipe beats price trend.

Question: given only what was public on signal date D, how should the market model (trend6) and the
financial model (fin-v1) be mixed into one growth_score so that the top of the list beats the
NIFTY SMALLCAP 250 over the next 6 and 12 months?

Part A - non-financial companies (the financial model's universe)
-----------------------------------------------------------------
Rows: financial_model.data.build_panel() - label grid of growth_model/labels.py (1st and 16th of
each month), liquid universe (median traded value >= 0.5 cr/day, >= 252 trading days), fresh
point-in-time financials (filing_date <= D 00:00, period ended <= 275 days before D). Only rows that
the live ranking could rank are kept: a growth component (>= 2 growth sub-features) and a trend
score.
Scores per row (all per-date percentiles, 0-1):
    market      trend6 (growth_model/market_model.py): equal-weight mean of the six trend-signal
                percentiles, missing -> 0.5; then its percentile among the liquid universe on D
    financial   fin-v1 = prelim-v2's financial blend (financial_model/model.baseline_score, which
                already includes the red-flag penalties); then its percentile among the rows above
    mix_w       w x market + (1 - w) x financial for w in W_GRID (declared below, before any run)
    prelim_v2   rankings/build.py weights on the same components: growth .30, profitability .20,
                health .15, cash flow .15, momentum .15 (= market percentile), renormalised over
                available components, minus the red-flag penalties. News (.05) is left out: it has
                no history (below), and a constant 50 would not change the order.
News: `news` rows start in 2026-08 (sentiment-scored, company-mapped), so there is no labelled
news history at all and it cannot be backtested. investiq-v1 keeps it at a small FIXED weight
(NEWS_WEIGHT = 0.05, the same as prelim-v2) and says so.

Walk-forward rule for w (pre-declared, `choose_w`): for test year Y and horizon h, the training
set is every signal date whose label window ended before Y began (PURGE_DAYS as the market and
financial models: 190 days for 6m, 375 for 12m). For each w in W_GRID the per-year mean IC over the
training years is computed; w is chosen to maximise  mean(yearly IC) - STABILITY_PENALTY x
std(yearly IC)  (a stability-penalised IC: a weight that is great in one regime and poor in
another loses to one that is steadily good). Ties go to the larger w (the stronger, simpler
signal). The live weight is the same rule on all labelled years, with the objective averaged over
the 6m and 12m horizons, rounded to the grid.
Test years start in FIRST_TEST_YEAR (2020): financial features start in 2018, so 2020 is the first
year with any purged training data (and only ~1 year of it).

Metrics (growth_model.market_model.evaluate, so every number is comparable with the market and
financial models): per test year the mean per-date Spearman IC, top-decile minus bottom-decile mean
excess (clipped to [-100%, +300%]), top-decile beat rate; overall: mean of the yearly values and
"years IC > 0".

Red flags: for each features.py flag, flagged minus unflagged mean excess on the same date,
averaged per year (negative = the flag warned correctly). A flag keeps a penalty on the final
score only if that gap is negative in >= 2/3 of the years on BOTH horizons (`flag_evidence`).

Part B - banks, NBFCs, insurers (financials/fin_sector_features.py)
-------------------------------------------------------------------
Rows: in-scope companies (lender-format filers), same label grid, same liquid universe, as-of join
of fin_sector feature rows with build.py's visibility rule (filing_date <= D 00:00, stale after 275
days). The FIN_SECTOR_REPORT.md recipe (`FIN_SUBFEATURES`, `FIN_WEIGHTS`, `FIN_PENALTY`):
percentiles within peer groups (bank / lending NBFC (loans/assets >= 0.5) / other NBFC-format /
insurer; the pool of all in-scope names when a group has < 15 on the date), components growth,
profitability, financial_health (cash flow not applicable), weights momentum .50, growth .15,
profitability .15, health .15 (news .05 not backtestable, left out), penalties asset-quality
worsening -4, capital near minimum -6, negative equity -6; eligible when momentum and growth are
available and coverage >= 0.6. Compared on the same rows with:
    trend       the market percentile alone
    trend_pen   trend x 100 minus the same penalties
Adoption rule (pre-declared, `adopt_fin_recipe`): the recipe is adopted only if on BOTH horizons its
mean yearly IC >= trend's - 0.005 and its mean yearly top-minus-bottom quintile spread >= trend's
- 0.005. Otherwise financial-sector companies are scored momentum-first (see build_v3.py) and their
financial features are used for reasons / risks text only. The recipe has no fitted parts, but it
was written after looking at FIN_SECTOR_REPORT's per-feature results, so its numbers are, if
anything, optimistic.

Caveats: survivorship (prices exist only for companies listed today), overlapping label windows
(a year is closer to one observation than to 24 dates), few test years (6-7).

Outputs: ml/data/processed/combiner_walkforward.json (everything printed, for V3_COMPARISON.md).

CLI:  caffeinate -i python3 -m rankings.combiner_eval
"""

import argparse
import json
import time
import warnings

import numpy as np
import pandas as pd

from growth_model.market_features import rank_features as rank_market
from growth_model.market_model import CLIP, FEATURES_FILE, PURGE_DAYS, evaluate, trend_score
from growth_model.prices import CACHE_DIR

from .build import FINANCIAL_COMPONENTS, FLAG_PENALTY, SUBFEATURES, WEIGHTS

HORIZONS = ["6m", "12m"]
W_GRID = [0.0, 0.5, 0.6, 0.65, 0.7, 0.75, 0.8, 1.0]     # market weight; declared before any run
STABILITY_PENALTY = 0.5
NEWS_WEIGHT = 0.05
FIRST_TEST_YEAR = 2020
FIN_FIRST_TEST_YEAR = 2019
MIN_ROWS_PER_DATE = 50
FIN_MIN_NAMES = 15
FLAG_YEARS_SHARE = 2 / 3
ADOPT_IC_TOL = 0.005
ADOPT_SPREAD_TOL = 0.005
OUT_FILE = CACHE_DIR / "combiner_walkforward.json"

# ---- financial-sector recipe (FIN_SECTOR_REPORT.md section 5) ----
FIN_GROUP_MIN = 15
FIN_MIN_COVERAGE = 0.6
FIN_WEIGHTS = {"growth": 0.15, "profitability": 0.15, "financial_health": 0.15, "momentum": 0.50, "news": 0.05}
FIN_PENALTY = {"flag_asset_quality_worsening": 4, "flag_capital_near_minimum": 6, "flag_negative_equity": 6}
# component -> segment -> ([(feature, weight, higher_is_better)], minimum sub-features)
FIN_SUBFEATURES = {
    "growth": {
        "bank": ([("ppop_ttm_growth", 1, True), ("net_profit_yoy", 1, True), ("net_revenue_ttm_growth", 1, True),
                  ("net_profit_ttm_growth", 1, True), ("nii_ttm_growth", 0.5, True)], 2),
        "nbfc": ([("net_revenue_ttm_growth", 1, True), ("net_profit_ttm_growth", 1, True),
                  ("net_profit_yoy", 1, True), ("ppop_ttm_growth", 1, True)], 2),
        "insurance": ([("net_revenue_yoy", 1, True), ("net_profit_yoy", 1, True)], 1),
    },
    "profitability": {
        "bank": ([("roe", 1, True), ("roa", 1, True), ("cost_to_income_ttm", 1, False), ("nim", 0.5, True)], 1),
        "nbfc": ([("cost_to_income_ttm", 1, False), ("roe", 1, True), ("roa", 0.5, True)], 1),
        "insurance": ([("roe", 1, True), ("combined_ratio", 1, False)], 1),
    },
    "financial_health": {
        "bank": ([("gross_npa_pct", 1, False), ("net_npa_pct", 1, False), ("provision_coverage", 1, True),
                  ("credit_cost", 1, False), ("cet1_ratio", 0.5, True)], 1),
        "nbfc": ([("credit_cost", 1, False), ("credit_cost_to_income_ttm", 1, False), ("leverage", 0.5, False)], 1),
        "insurance": ([("solvency_ratio", 1, True)], 1),
    },
}
FIN_COMPONENTS = list(FIN_SUBFEATURES)


def _pct_by_date(values, dates):
    """build.pct_rank per date: (rank - 1) / (n - 1) among non-null values, n == 1 -> 0.5."""
    g = values.groupby(dates)
    rank = g.rank(method="average")
    n = g.transform("count")
    out = (rank - 1) / (n - 1).where(n > 1)
    return out.where(~(n == 1) | values.isna(), 0.5)


# ---------------------------------------------------------
# Market scores on the label grid
# ---------------------------------------------------------

def market_panel(labels):
    """company_id, signal_date, market (percentile of trend6 among the liquid universe on D)."""
    from financial_model.data import MIN_ADV_CR, MIN_DAYS_LISTED

    mk = rank_market(pd.read_pickle(FEATURES_FILE))
    mk["trend6"] = trend_score(mk)
    liquid = labels[(labels["adv_60d_cr"] >= MIN_ADV_CR) & (labels["days_listed"] >= MIN_DAYS_LISTED)]
    mk = liquid[["company_id", "signal_date"]].merge(mk[["company_id", "signal_date", "trend6"]],
                                                     on=["company_id", "signal_date"], how="inner")
    mk["market"] = mk.groupby("signal_date")["trend6"].rank(pct=True)
    return mk[["company_id", "signal_date", "market"]]


# ---------------------------------------------------------
# Part A: non-financial companies
# ---------------------------------------------------------

def fin_components(panel):
    """prelim-v2 component scores (0-100 per-date percentiles) on the panel, as financial_model.model."""
    dates = panel["signal_date"]
    comp = {}
    for c in FINANCIAL_COMPONENTS:
        subs, min_n = SUBFEATURES[c]
        num = pd.Series(0.0, index=panel.index)
        den = pd.Series(0.0, index=panel.index)
        cnt = pd.Series(0, index=panel.index)
        for feat, w, higher in subs:
            p = _pct_by_date(panel[feat], dates)
            if not higher:
                p = 1 - p
            has = p.notna()
            num += p.fillna(0) * w * has
            den += w * has
            cnt += has.astype(int)
        raw = (num / den.replace(0, np.nan)).where(cnt >= min_n)
        comp[c] = _pct_by_date(raw, dates) * 100
    return pd.DataFrame(comp, index=panel.index)


def penalty_points(frame, penalties):
    return sum(frame[f].astype("boolean").fillna(False).astype(bool) * pts for f, pts in penalties.items())


def nonfin_panel(labels):
    from financial_model.data import build_panel
    from financial_model.model import baseline_score

    panel, stats = build_panel(labels=labels)
    comps = fin_components(panel)
    panel = pd.concat([panel, comps.add_prefix("score_")], axis=1)
    panel["fin_raw"] = baseline_score(panel)          # fin-v1 (includes red-flag penalties)
    panel = panel[panel["score_growth"].notna()]      # rankable: a growth reading
    panel = panel.merge(market_panel(labels), on=["company_id", "signal_date"], how="inner")
    panel["financial"] = panel.groupby("signal_date")["fin_raw"].rank(pct=True)
    # prelim-v2 weights on the same components (news left out, see docstring)
    w = {c: WEIGHTS[c] for c in (*FINANCIAL_COMPONENTS, "momentum")}
    scores = panel[[f"score_{c}" for c in FINANCIAL_COMPONENTS]].copy()
    scores["score_momentum"] = panel["market"] * 100
    avail = scores.notna()
    wsum = sum(avail[f"score_{c}"] * w[c] for c in w)
    wscore = sum(scores[f"score_{c}"].fillna(0) * w[c] for c in w)
    panel["prelim_v2"] = wscore / wsum - penalty_points(panel, FLAG_PENALTY)
    for x in W_GRID:
        panel[f"mix_{x}"] = x * panel["market"] + (1 - x) * panel["financial"]
    return panel.reset_index(drop=True), stats


def yearly(data, col, h, first_year):
    rows = []
    for year, g in data.groupby(data["signal_date"].dt.year):
        if year < first_year:
            continue
        m = evaluate(g, col, h)
        rows.append({"year": int(year), "ic": m["ic"], "spread": m["spread"], "top10": m["top10"],
                     "top10_beat": m["top10_beat"], "universe": m["universe"], "bot10": m["bot10"]})
    return pd.DataFrame(rows)


def objective(per_year):
    """Stability-penalised IC over years (NaN-safe)."""
    ic = per_year["ic"].dropna()
    if len(ic) == 0:
        return -np.inf
    sd = ic.std(ddof=0) if len(ic) > 1 else 0.0
    return ic.mean() - STABILITY_PENALTY * sd


def choose_w(train, h):
    """Pre-declared rule: argmax over W_GRID of mean(yearly IC) - 0.5 x std(yearly IC); ties -> larger w."""
    best, best_obj, table = None, -np.inf, {}
    for x in W_GRID:
        obj = objective(yearly(train, f"mix_{x}", h, 0))
        table[x] = obj
        if obj > best_obj + 1e-12 or (abs(obj - best_obj) <= 1e-12 and (best is None or x > best)):
            best, best_obj = x, obj
    return best, table


def walk_forward(panel, h):
    data = panel[panel[f"excess_{h}"].notna() & panel[f"top_q_{h}"].notna()]
    last_year = data["signal_date"].max().year
    chosen, scored = {}, []
    for year in range(FIRST_TEST_YEAR, last_year + 1):
        cutoff = pd.Timestamp(year, 1, 1) - pd.Timedelta(days=PURGE_DAYS[h])
        train = data[data["signal_date"] < cutoff]
        test = data[data["signal_date"].dt.year == year].copy()
        if len(test) == 0 or train["signal_date"].nunique() < 6:
            continue
        w, _ = choose_w(train, h)
        chosen[year] = w
        test["combiner_wf"] = test[f"mix_{w}"]
        scored.append(test)
        print(f"  {h} {year}: train {len(train):,} rows (< {cutoff:%Y-%m-%d}), test {len(test):,}; chosen w = {w}")
    return pd.concat(scored), chosen


def summary(per_year):
    return {"ic_mean": float(per_year["ic"].mean()), "spread_mean": float(per_year["spread"].mean()),
            "top10_beat_mean": float(per_year["top10_beat"].mean()),
            "top10_minus_universe_mean": float((per_year["top10"] - per_year["universe"]).mean()),
            "years_ic_positive": f"{int((per_year['ic'] > 0).sum())}/{len(per_year)}",
            "years_top10_above_universe": f"{int((per_year['top10'] > per_year['universe']).sum())}/{len(per_year)}"}


def flag_evidence(panel):
    """Flagged minus unflagged mean excess per year, per features.py flag and horizon."""
    out = {}
    for flag in FLAG_PENALTY:
        res = {}
        for h in HORIZONS:
            d = panel[panel[f"excess_{h}"].notna() & (panel["signal_date"].dt.year >= FIRST_TEST_YEAR)]
            flagged = d[flag].astype("boolean").fillna(False).astype(bool)
            ex = d[f"excess_{h}"].clip(*CLIP)
            per_date = pd.DataFrame({"on": ex.where(flagged), "off": ex.where(~flagged), "d": d["signal_date"]})
            g = per_date.groupby("d").agg(on=("on", "mean"), off=("off", "mean"), n=("on", "count"))
            g = g[g["n"] >= 5]
            gap = (g["on"] - g["off"]).groupby(g.index.year).mean()
            res[h] = {"gap_mean": float(gap.mean()) if len(gap) else None,
                      "years_negative": f"{int((gap < 0).sum())}/{len(gap)}",
                      "flagged_per_date": float(g["n"].median()) if len(g) else 0,
                      "per_year": {int(y): round(float(v), 4) for y, v in gap.items()}}
        keep = all(res[h]["gap_mean"] is not None and
                   (int(res[h]["years_negative"].split("/")[0]) >= FLAG_YEARS_SHARE * int(res[h]["years_negative"].split("/")[1]))
                   for h in HORIZONS)
        out[flag] = {**res, "keep_penalty": bool(keep)}
    return out


# ---------------------------------------------------------
# Part B: financial sector
# ---------------------------------------------------------

def fin_segment(frame):
    """bank / lending_nbfc / other_nbfc / nbfc_unknown / insurance (loans/assets as of the row)."""
    fmt = frame["company_format"]
    lta = frame["loans_to_assets"]
    seg = np.where(fmt == "bank", "bank", np.where(fmt == "insurance", "insurance",
                   np.where(lta >= 0.5, "lending_nbfc", np.where(lta < 0.5, "other_nbfc", "nbfc_unknown"))))
    return pd.Series(seg, index=frame.index)


def fin_asof(table, keys, key_date="signal_date"):
    """As-of join of fin_sector rows onto (company_id, key_date): filing_date <= D 00:00 (build.py)."""
    t = table[table["company_id"].notna()].copy()
    t["company_id"] = t["company_id"].astype(int)
    t = t.sort_values(["company_id", "filing_date", "period_end"])
    prev = t.groupby("company_id")["period_end"].transform(lambda s: s.cummax().shift())
    t = t[prev.isna() | (t["period_end"] >= prev)]
    left = keys.assign(**{key_date: keys[key_date].astype("datetime64[ns]")}).sort_values(key_date)
    right = t.assign(filing_date=t["filing_date"].astype("datetime64[ns]")).sort_values("filing_date")
    out = pd.merge_asof(left.reset_index(drop=True), right.drop(columns=["symbol"]).reset_index(drop=True),
                        left_on=key_date, right_on="filing_date", by="company_id", direction="backward")
    age = (out[key_date] - out["period_end"]).dt.days
    out["fin_stale"] = age.isna() | (age > 275)
    return out


def fin_scores(frame, date_col="signal_date"):
    """Recipe component scores (0-100) + oriented sub-feature percentiles (p_*) within peer groups."""
    frame = frame.copy()
    frame["segment"] = fin_segment(frame)
    fmt_key = np.where(frame["company_format"] == "bank", "bank",
                       np.where(frame["company_format"] == "insurance", "insurance", "nbfc"))
    size = frame.groupby([date_col, "segment"])["company_id"].transform("count")
    frame["peer_group"] = np.where(size >= FIN_GROUP_MIN, frame["segment"], "all_financial")
    grp = [frame[date_col], frame["peer_group"]]
    for comp, spec in FIN_SUBFEATURES.items():
        num = pd.Series(0.0, index=frame.index)
        den = pd.Series(0.0, index=frame.index)
        cnt = pd.Series(0, index=frame.index)
        feats = {f: (w, hb) for key in spec for f, w, hb in spec[key][0]}
        for feat, (_, higher) in feats.items():
            col = f"p_{feat}"
            if col not in frame:
                p = frame[feat].groupby(grp).rank(method="average")
                n = frame[feat].groupby(grp).transform("count")
                p = ((p - 1) / (n - 1).where(n > 1)).where(~(n == 1) | frame[feat].isna(), 0.5)
                frame[col] = p if higher else 1 - p
        min_n = pd.Series(0, index=frame.index)
        for key, (subs, mn) in spec.items():
            is_key = fmt_key == key
            min_n[is_key] = mn
            for feat, w, _ in subs:
                p = frame[f"p_{feat}"].where(is_key)
                has = p.notna()
                num += p.fillna(0) * w * has
                den += w * has
                cnt += has.astype(int)
        raw = (num / den.replace(0, np.nan)).where((cnt >= min_n) & (cnt > 0))
        rank = raw.groupby(grp).rank(method="average")
        n = raw.groupby(grp).transform("count")
        frame[f"score_{comp}"] = ((rank - 1) / (n - 1).where(n > 1)).where(~(n == 1) | raw.isna(), 0.5) * 100
    return frame


def fin_panel(labels):
    from financial_model.data import MIN_ADV_CR, MIN_DAYS_LISTED
    from financials.fin_sector_features import build_feature_table, load_extract, raw_from_extract

    table = build_feature_table(raw_from_extract(load_extract()))
    liquid = labels[(labels["adv_60d_cr"] >= MIN_ADV_CR) & (labels["days_listed"] >= MIN_DAYS_LISTED)
                    & labels["company_id"].isin(table["company_id"].dropna().astype(int).unique())]
    panel = fin_asof(table, liquid)
    panel = panel[~panel["fin_stale"]].reset_index(drop=True)
    panel = fin_scores(panel)
    panel = panel.merge(market_panel(labels), on=["company_id", "signal_date"], how="inner")
    panel["score_momentum"] = panel["market"] * 100
    w = {c: FIN_WEIGHTS[c] for c in (*FIN_COMPONENTS, "momentum")}
    scores = panel[[f"score_{c}" for c in w]]
    avail = scores.notna()
    wsum = sum(avail[f"score_{c}"] * w[c] for c in w)
    panel["coverage"] = wsum / sum(w.values())
    pen = penalty_points(panel, FIN_PENALTY)
    panel["recipe"] = sum(scores[f"score_{c}"].fillna(0) * w[c] for c in w) / wsum - pen
    panel["trend"] = panel["market"]
    panel["trend_pen"] = panel["market"] * 100 - pen
    eligible = panel["score_growth"].notna() & (panel["coverage"] >= FIN_MIN_COVERAGE)
    return panel[eligible].reset_index(drop=True), table


def fin_yearly(data, col, h):
    rows = []
    for year, g in data.groupby(data["signal_date"].dt.year):
        if year < FIN_FIRST_TEST_YEAR:
            continue
        ics, spreads, top_beat = [], [], []
        for _, d in g.groupby("signal_date"):
            d = d[[col, f"excess_{h}", f"beat_{h}"]].dropna()
            if len(d) < FIN_MIN_NAMES:
                continue
            ics.append(d[col].rank().corr(d[f"excess_{h}"].rank()))
            p = d[col].rank(pct=True)
            ex = d[f"excess_{h}"].clip(*CLIP)
            spreads.append(ex[p > 0.8].mean() - ex[p <= 0.2].mean())
            top_beat.append(d.loc[p > 0.8, f"beat_{h}"].mean())
        if ics:
            rows.append({"year": int(year), "ic": float(np.nanmean(ics)), "spread": float(np.nanmean(spreads)),
                         "top20_beat": float(np.nanmean(top_beat)), "dates": len(ics)})
    return pd.DataFrame(rows)


def adopt_fin_recipe(res):
    """Pre-declared: adopt only if not worse than trend on BOTH horizons (IC and quintile spread)."""
    ok = all(res[h]["recipe"]["ic_mean"] >= res[h]["trend"]["ic_mean"] - ADOPT_IC_TOL
             and res[h]["recipe"]["spread_mean"] >= res[h]["trend"]["spread_mean"] - ADOPT_SPREAD_TOL
             for h in res)
    return ok


# ---------------------------------------------------------
# Main
# ---------------------------------------------------------

def _fmt_table(per_year_by_method, cols=("ic", "spread", "top10_beat")):
    lines = []
    for m, t in per_year_by_method.items():
        for _, r in t.iterrows():
            lines.append(f"  {m:<14}{int(r.year):<6}" + "".join(f"{r[c]:>9.3f}" for c in cols))
    return "\n".join(lines)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.parse_args(argv)
    warnings.filterwarnings("ignore")
    t0 = time.time()
    from growth_model.labels import LABELS_FILE
    labels = pd.read_pickle(LABELS_FILE)
    out = {"w_grid": W_GRID, "stability_penalty": STABILITY_PENALTY, "news_weight": NEWS_WEIGHT,
           "news_backtest": "not possible: news rows start 2026-08; fixed weight"}

    # ---- Part A ----
    panel, stats = nonfin_panel(labels)
    print(f"A. non-financial panel: {len(panel):,} rows, {panel['company_id'].nunique():,} companies, "
          f"{panel['signal_date'].nunique()} dates; {stats}")
    out["nonfin"] = {"rows": len(panel), "companies": int(panel["company_id"].nunique()), "horizons": {}}
    all_obj = {}
    for h in HORIZONS:
        scored, chosen = walk_forward(panel, h)
        methods = {"combiner_wf": "combiner_wf", "trend6": "mix_1.0", "financial": "mix_0.0",
                   "prelim_v2": "prelim_v2", "mix_0.5": "mix_0.5", "mix_0.7": "mix_0.7"}
        per = {m: yearly(scored, col, h, FIRST_TEST_YEAR) for m, col in methods.items()}
        print(f"\n=== {h}: per test year (ic, top-bottom decile spread, top10 beat) ===")
        print(_fmt_table(per))
        print(f"\n{'ALL':<14}{'ic':>8}{'spread':>9}{'beat':>8}{'top10-all':>11}{'yrs ic>0':>10}{'yrs top>all':>13}")
        summ = {}
        for m, t in per.items():
            s = summary(t)
            summ[m] = s
            print(f"{m:<14}{s['ic_mean']:>8.3f}{s['spread_mean']:>+9.1%}{s['top10_beat_mean']:>8.1%}"
                  f"{s['top10_minus_universe_mean']:>+11.1%}{s['years_ic_positive']:>10}{s['years_top10_above_universe']:>13}")
        # every grid w on the same test years, for the record (not used to choose)
        grid = {str(x): summary(yearly(scored, f"mix_{x}", h, FIRST_TEST_YEAR)) for x in W_GRID}
        # final-fit objective on all labelled years
        data = panel[panel[f"excess_{h}"].notna() & panel[f"top_q_{h}"].notna()]
        _, obj = choose_w(data, h)
        all_obj[h] = obj
        out["nonfin"]["horizons"][h] = {
            "chosen_w_by_test_year": {str(y): w for y, w in chosen.items()},
            "summary": summ, "grid_on_test_years": grid,
            "per_year": {m: t.round(4).to_dict("records") for m, t in per.items()},
            "objective_all_years": {str(k): round(v, 4) for k, v in obj.items()},
        }
    avg_obj = {x: np.mean([all_obj[h][x] for h in HORIZONS]) for x in W_GRID}
    final_w = max(W_GRID, key=lambda x: (round(avg_obj[x], 12), x))
    out["nonfin"]["final_w"] = final_w
    out["nonfin"]["objective_avg"] = {str(k): round(v, 4) for k, v in avg_obj.items()}
    print(f"\nobjective on all labelled years (avg 6m/12m): "
          + ", ".join(f"{x}: {v:.4f}" for x, v in avg_obj.items()) + f"  -> live w = {final_w}")
    flags = flag_evidence(panel)
    out["nonfin"]["flags"] = flags
    print("\nred flags (flagged - unflagged excess, mean of years; years negative):")
    for f, r in flags.items():
        print(f"  {f:<38}" + "  ".join(f"{h} {r[h]['gap_mean']:+.3f} ({r[h]['years_negative']})" for h in HORIZONS)
              + f"   keep: {r['keep_penalty']}")

    # ---- Part B ----
    fpanel, _ = fin_panel(labels)
    print(f"\nB. financial-sector panel (eligible): {len(fpanel):,} rows, {fpanel['company_id'].nunique()} companies, "
          f"median names/date {int(fpanel.groupby('signal_date').size().median())}; segments "
          f"{fpanel.drop_duplicates('company_id')['segment'].value_counts().to_dict()}")
    res = {}
    out["fin_sector"] = {"rows": len(fpanel), "companies": int(fpanel["company_id"].nunique()), "horizons": {}}
    for h in HORIZONS:
        d = fpanel[fpanel[f"excess_{h}"].notna()]
        per = {m: fin_yearly(d, m, h) for m in ("recipe", "trend", "trend_pen")}
        res[h] = {m: {"ic_mean": float(t["ic"].mean()), "spread_mean": float(t["spread"].mean()),
                      "top20_beat_mean": float(t["top20_beat"].mean()),
                      "years_ic_positive": f"{int((t['ic'] > 0).sum())}/{len(t)}"} for m, t in per.items()}
        print(f"\n=== fin sector {h}: per year (ic, top-bottom quintile spread, top20 beat) ===")
        print(_fmt_table(per, cols=("ic", "spread", "top20_beat")))
        for m, s in res[h].items():
            print(f"  {m:<10} IC {s['ic_mean']:+.3f}  spread {s['spread_mean']:+.1%}  top20 beat {s['top20_beat_mean']:.1%}"
                  f"  yrs IC>0 {s['years_ic_positive']}")
        out["fin_sector"]["horizons"][h] = {"summary": res[h],
                                            "per_year": {m: t.round(4).to_dict("records") for m, t in per.items()}}
    adopt = adopt_fin_recipe(res)
    out["fin_sector"]["adopt_recipe"] = adopt
    print(f"\nfinancial-sector recipe adopted: {adopt}")
    OUT_FILE.write_text(json.dumps(out, indent=1, default=str))
    print(f"\nwrote {OUT_FILE} in {time.time() - t0:.0f}s")


if __name__ == "__main__":
    main()
