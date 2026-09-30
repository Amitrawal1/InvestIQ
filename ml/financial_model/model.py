"""Candidate financial scores, all computed per signal date from the point-in-time panel (data.py).

    baseline    prelim-v2's financial part (rankings/build.py), recomputed on every signal date:
                sub-feature percentiles -> growth / profitability / financial_health / cash_flow
                component scores (same sub-features, weights and minimum counts as build.py), blended
                0.30 / 0.20 / 0.15 / 0.15 renormalised over the available components, minus the
                red-flag penalty (3 points per flag, 6 for negative equity). Percentiles are taken
                within the model universe of each date (build.py ranks all EQ/BE companies).
                A row without a growth component (unranked in prelim-v2) gets the neutral 50.
    blend       transparent v1: equal-weight mean of the oriented percentiles of the selected
                features (missing -> neutral 0.5). Selection uses TRAINING years only (see
                `select_features`): a feature is kept when its mean per-year IC is >= MIN_IC in the
                direction economics expects (IC sign when the direction is unclear, e.g. size) and
                that sign held in >= MIN_SIGN_SHARE of the training years.
    xgb         XGBoost regressor on all ranked features (NaN kept), target = the per-date
                percentile of excess return; shallow trees, large leaves, strong L2, row/column
                subsampling, monotone constraints where the direction is economically obvious
                (profitability, leverage, liquidity, cash-flow quality, red flags; growth and size
                are left free because growth can mean-revert).
    blend_xgb   mean of the per-date percentiles of blend and xgb.

`evaluate` is growth_model.market_model.evaluate, so every number is directly comparable with the
market model (IC, top/bottom decile excess with the same clipping, AUC vs top_q).
"""

import numpy as np
import pandas as pd
from xgboost import XGBRegressor

from rankings.build import FINANCIAL_COMPONENTS, FLAG_PENALTY, SUBFEATURES, WEIGHTS

from .data import FEATURE_NAMES, MODEL_FEATURES

MIN_IC = 0.02
MIN_SIGN_SHARE = 2 / 3
MIN_DATES_PER_YEAR = 6          # a training year counts for a feature when it has this many IC dates
MIN_ROWS_PER_DATE = 50
SEED = 42

XGB_PARAMS = dict(
    n_estimators=300, max_depth=3, learning_rate=0.03, subsample=0.7, colsample_bytree=0.7,
    min_child_weight=1000, reg_lambda=10.0, tree_method="hist", objective="reg:squarederror",
    random_state=SEED, n_jobs=4,
)
MONOTONE_GROUPS = {"profitability", "financial_health", "cash_flow", "quality"}


# ---------------------------------------------------------
# Baseline: prelim-v2 financial blend
# ---------------------------------------------------------

def _pct_by_date(values, dates):
    """build.pct_rank per date: (rank - 1) / (n - 1) among non-null values, n == 1 -> 0.5."""
    g = values.groupby(dates)
    rank = g.rank(method="average")
    n = g.transform("count")
    out = (rank - 1) / (n - 1).where(n > 1)
    return out.where(~(n == 1) | values.isna(), 0.5)


def baseline_parts(panel):
    """prelim-v2 financial blend per row -> (score 0-100, contributions DataFrame in points).

    Rows without a growth component (unranked in prelim-v2) get the neutral 50. Contributions are
    an approximate linear split of the score around 50: sub-feature f in component c contributes
    (component weight share) x (sub-feature weight share within c) x (oriented percentile - 0.5) x 100,
    and each red flag contributes minus its penalty. (Exact only up to the component re-ranking.)
    """
    df = panel
    dates = df["signal_date"]
    comp, pcts, dens = {}, {}, {}
    for c in FINANCIAL_COMPONENTS:
        subs, min_n = SUBFEATURES[c]
        num = pd.Series(0.0, index=df.index)
        den = pd.Series(0.0, index=df.index)
        cnt = pd.Series(0, index=df.index)
        for feat, w, higher in subs:
            p = _pct_by_date(df[feat], dates)
            if not higher:
                p = 1 - p
            pcts[(c, feat, w)] = p
            has = p.notna()
            num += p.fillna(0) * w * has
            den += w * has
            cnt += has.astype(int)
        raw = (num / den.replace(0, np.nan)).where(cnt >= min_n)
        comp[c] = _pct_by_date(raw, dates) * 100
        dens[c] = den
    comp = pd.DataFrame(comp)
    avail = comp.notna()
    wsum = sum(avail[c] * WEIGHTS[c] for c in FINANCIAL_COMPONENTS)
    wscore = sum(comp[c].fillna(0) * WEIGHTS[c] for c in FINANCIAL_COMPONENTS)
    flags = {f: df[f].astype("boolean").fillna(False).astype(bool) for f in FLAG_PENALTY}
    penalty = sum(flags[f] * pts for f, pts in FLAG_PENALTY.items())
    score = (wscore / wsum.replace(0, np.nan) - penalty).clip(0, 100)
    score = score.where(avail["growth"]).fillna(50.0)

    contrib = {}
    for (c, feat, w), p in pcts.items():
        share = (WEIGHTS[c] * avail[c] / wsum.replace(0, np.nan)) * (w / dens[c].replace(0, np.nan))
        contrib[feat] = ((p - 0.5) * share * 100).fillna(0.0)
    for f, pts in FLAG_PENALTY.items():
        contrib[f] = -pts * flags[f].astype(float)
    return score, pd.DataFrame(contrib, index=df.index)


def baseline_score(panel):
    return baseline_parts(panel)[0]


def baseline_oriented(panel):
    """Oriented per-date percentile of every baseline sub-feature (for the text buckets)."""
    out = {}
    for c in FINANCIAL_COMPONENTS:
        for feat, _, higher in SUBFEATURES[c][0]:
            p = _pct_by_date(panel[feat], panel["signal_date"])
            out[feat] = p if higher else 1 - p
    return pd.DataFrame(out, index=panel.index)


# ---------------------------------------------------------
# Per-date / per-year information coefficients
# ---------------------------------------------------------

def daily_ics(data, h, features=FEATURE_NAMES):
    """Per signal date Spearman IC of each (already ranked) feature vs excess_h. -> DataFrame."""
    y = data.groupby("signal_date")[f"excess_{h}"].rank(pct=True)
    rows = []
    for d, idx in data.groupby("signal_date").groups.items():
        if len(idx) < MIN_ROWS_PER_DATE:
            continue
        yy = y.loc[idx].to_numpy()
        rec = {"signal_date": d}
        X = data.loc[idx, features].to_numpy(dtype=float)
        for j, f in enumerate(features):
            m = ~np.isnan(X[:, j])
            if m.sum() < MIN_ROWS_PER_DATE:
                rec[f] = np.nan
                continue
            # Spearman: features are percentiles already; re-rank on the common subset
            a = pd.Series(X[m, j]).rank().to_numpy()
            b = pd.Series(yy[m]).rank().to_numpy()
            rec[f] = np.corrcoef(a, b)[0, 1]
        rows.append(rec)
    return pd.DataFrame(rows)


def yearly_ics(ics):
    ics = ics.copy()
    ics["year"] = ics["signal_date"].dt.year
    g = ics.groupby("year")
    mean = g[FEATURE_NAMES].mean()
    enough = g[FEATURE_NAMES].count() >= MIN_DATES_PER_YEAR
    return mean.where(enough)


def select_features(yearly):
    """-> {feature: sign} from per-year training ICs (rows = years)."""
    chosen = {}
    for f in FEATURE_NAMES:
        s = yearly[f].dropna()
        if len(s) == 0:
            continue
        m = s.mean()
        prior = MODEL_FEATURES[f][1]
        sign = prior if prior != 0 else (1 if m > 0 else -1)
        if m * sign < MIN_IC:
            continue
        if ((s * sign) > 0).mean() < MIN_SIGN_SHARE:
            continue
        chosen[f] = sign
    return chosen


def blend_score(frame, chosen):
    """Equal-weight mean of oriented percentiles (missing -> 0.5). frame holds ranked features."""
    if not chosen:
        return pd.Series(0.5, index=frame.index)
    parts = [(frame[f] if s > 0 else 1 - frame[f]) for f, s in chosen.items()]
    return pd.concat(parts, axis=1).fillna(0.5).mean(axis=1)


def blend_contributions(frame, chosen):
    """Per-feature contribution to the blend in score points: (oriented pct - 0.5) / n x 100."""
    n = max(len(chosen), 1)
    return pd.DataFrame({f: ((frame[f] if s > 0 else 1 - frame[f]).fillna(0.5) - 0.5) / n * 100
                         for f, s in chosen.items()}, index=frame.index)


# ---------------------------------------------------------
# ML
# ---------------------------------------------------------

def monotone_constraints():
    return tuple(MODEL_FEATURES[f][1] if MODEL_FEATURES[f][0] in MONOTONE_GROUPS else 0
                 for f in FEATURE_NAMES)


def fit_xgb(train, h):
    y = train.groupby("signal_date")[f"excess_{h}"].rank(pct=True)
    model = XGBRegressor(**XGB_PARAMS, monotone_constraints=monotone_constraints())
    model.fit(train[FEATURE_NAMES].to_numpy(dtype=float), y.to_numpy())
    return model


def predict_xgb(model, frame):
    return pd.Series(model.predict(frame[FEATURE_NAMES].to_numpy(dtype=float)), index=frame.index)


def per_date_pct(score, dates):
    return score.groupby(dates).rank(pct=True)
