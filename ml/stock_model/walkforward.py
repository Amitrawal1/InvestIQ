"""Year-by-year (walk-forward) training and evaluation.

For each test year: train on everything before it, validate on the last year of
that training data, predict the test year. Rows whose label period would overlap
the test year are removed from training ("purging"), so a 6-month label can never
be built from prices the model is being tested on.

Reported alongside the model: two naive baselines and the ranking checks that
matter for a research platform (does the top of the ranking beat the bottom?).
"""

import numpy as np
import pandas as pd
from scipy.stats import spearmanr
from sklearn.metrics import accuracy_score, f1_score, precision_score, recall_score, roc_auc_score
from xgboost import XGBClassifier

from .config import RANDOM_SEED

WALK_PARAMS = {
    "n_estimators": 400,
    "max_depth": 4,
    "learning_rate": 0.05,
    "subsample": 0.8,
    "colsample_bytree": 0.8,
    "min_child_weight": 10,
    "reg_lambda": 2.0,
    "objective": "binary:logistic",
    "eval_metric": "logloss",
    "early_stopping_rounds": 40,
    "enable_categorical": True,
    "tree_method": "hist",
    "random_state": RANDOM_SEED,
    "n_jobs": -1,
}


def walk_forward(panel, feature_cols, horizon_months, target_col, fwd_col,
                 first_test_year=2006, min_train_rows=500, params=None, verbose=False):
    """Train/test once per year. Returns (predictions, per_year_stats)."""

    params = {**WALK_PARAMS, **(params or {})}
    data = panel[panel[target_col].notna()].copy()
    data[target_col] = data[target_col].astype(int)

    predictions, per_year = [], []
    years = sorted(y for y in data["date"].dt.year.unique() if y >= first_test_year)

    for year in years:
        test_start = pd.Timestamp(year=year, month=1, day=1)

        # Purge: a label needs `horizon_months` of future prices, so the last
        # months before the test period must not be trained on.
        train_cutoff = test_start - pd.DateOffset(months=horizon_months)
        train_all = data[data["date"] < train_cutoff]
        test = data[(data["date"] >= test_start) & (data["date"] < test_start + pd.DateOffset(years=1))]

        if len(train_all) < min_train_rows or test.empty:
            continue

        # Validation = last 12 months of training data (for early stopping)
        val_start = train_cutoff - pd.DateOffset(months=12)
        train = train_all[train_all["date"] < val_start]
        val = train_all[train_all["date"] >= val_start]

        if len(train) < min_train_rows or val.empty:
            train, val = train_all, train_all

        model = XGBClassifier(**params)
        model.fit(train[feature_cols], train[target_col],
                  eval_set=[(val[feature_cols], val[target_col])], verbose=False)

        probabilities = model.predict_proba(test[feature_cols])[:, 1]

        block = test[["date", "symbol", "sector", target_col, fwd_col]].copy()
        block["probability"] = probabilities
        block["prediction"] = (probabilities >= 0.5).astype(int)
        block["year"] = year
        predictions.append(block)

        per_year.append({
            "year": year,
            "train_rows": len(train),
            "test_rows": len(test),
            "best_iteration": int(model.best_iteration),
            "base_rate": float(test[target_col].mean()),
            **classification_scores(test[target_col], probabilities),
        })

        if verbose:
            print(f"{year}: train={len(train):5d} test={len(test):4d} "
                  f"auc={per_year[-1]['roc_auc']:.3f} acc={per_year[-1]['accuracy']:.3f}")

    return pd.concat(predictions, ignore_index=True), pd.DataFrame(per_year)


def classification_scores(y_true, probabilities, threshold=0.5):
    y_true = np.asarray(y_true).astype(int)
    y_pred = (np.asarray(probabilities) >= threshold).astype(int)

    return {
        "accuracy": accuracy_score(y_true, y_pred),
        "precision": precision_score(y_true, y_pred, zero_division=0),
        "recall": recall_score(y_true, y_pred, zero_division=0),
        "f1": f1_score(y_true, y_pred, zero_division=0),
        "roc_auc": roc_auc_score(y_true, probabilities) if len(np.unique(y_true)) > 1 else np.nan,
    }


# ---------------------------------------------------------
# Baselines: the model has to beat these to be worth anything
# ---------------------------------------------------------

def baseline_scores(panel, predictions, target_col):
    """Momentum ranking and always-predict-yes, on exactly the tested rows."""

    tested = panel.merge(predictions[["date", "symbol"]], on=["date", "symbol"], how="inner")
    y_true = tested[target_col].astype(int)

    # Momentum: within each month, stocks above the median 12-1 momentum
    momentum_rank = tested.groupby("date")["momentum_12_1"].rank(pct=True).fillna(0.5)

    rows = {
        "momentum_rank": classification_scores(y_true, momentum_rank),
        "always_yes": classification_scores(y_true, np.ones(len(y_true))),
    }
    return pd.DataFrame(rows).T


# ---------------------------------------------------------
# Ranking quality
# ---------------------------------------------------------

def rank_metrics(predictions, fwd_col, top_n=10):
    """Per month: rank by predicted probability, then measure the outcome.

    * rank_ic - Spearman correlation between the ranking and the actual forward return
    * top_minus_bottom - average forward return of the top N minus the bottom N
    """

    rows = []

    for date, group in predictions.groupby("date"):
        group = group.dropna(subset=[fwd_col])
        if len(group) < 2 * top_n:
            continue

        ordered = group.sort_values("probability", ascending=False)
        ic = spearmanr(ordered["probability"], ordered[fwd_col]).statistic

        rows.append({
            "date": date,
            "rank_ic": ic,
            "top_mean": ordered.head(top_n)[fwd_col].mean(),
            "bottom_mean": ordered.tail(top_n)[fwd_col].mean(),
            "all_mean": group[fwd_col].mean(),
        })

    monthly = pd.DataFrame(rows)
    monthly["top_minus_bottom"] = monthly["top_mean"] - monthly["bottom_mean"]

    return monthly


def rank_summary(monthly):
    ic = monthly["rank_ic"].dropna()
    spread = monthly["top_minus_bottom"].dropna()

    return pd.Series({
        "months": len(monthly),
        "mean_rank_ic": ic.mean(),
        "share_ic_positive": (ic > 0).mean(),
        "mean_top_minus_bottom": spread.mean(),
        "share_spread_positive": (spread > 0).mean(),
        "mean_top": monthly["top_mean"].mean(),
        "mean_bottom": monthly["bottom_mean"].mean(),
        "mean_all": monthly["all_mean"].mean(),
    })


def feature_importance(panel, feature_cols, target_col, horizon_months, params=None):
    """Importance from a single model trained on all labelled history (for inspection only)."""

    params = {**WALK_PARAMS, **(params or {})}
    params.pop("early_stopping_rounds", None)

    data = panel[panel[target_col].notna()]
    model = XGBClassifier(**params)
    model.fit(data[feature_cols], data[target_col].astype(int), verbose=False)

    gain = model.get_booster().get_score(importance_type="gain")
    importance = pd.DataFrame({
        "feature": feature_cols,
        "gain": [gain.get(f, 0.0) for f in feature_cols],
    })
    importance["gain_share"] = importance["gain"] / importance["gain"].sum()

    return importance.sort_values("gain", ascending=False).reset_index(drop=True)
