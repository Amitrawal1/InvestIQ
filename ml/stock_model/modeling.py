"""Time-based split, XGBoost training, evaluation and feature importance."""

import json

import numpy as np
import pandas as pd
from sklearn.metrics import (
    accuracy_score,
    confusion_matrix,
    f1_score,
    precision_score,
    recall_score,
    roc_auc_score,
)
from xgboost import XGBClassifier

from .config import MODELS_DIR, PURGE_GAP, TRAIN_FRAC, VAL_FRAC, XGB_PARAMS
from .features import TARGET_COL


# =========================================================
# SPLIT
# =========================================================

def time_split(df, train_frac=TRAIN_FRAC, val_frac=VAL_FRAC, gap=PURGE_GAP, date_col="price_date"):
    """Chronological train/val/test split on unique dates, with purged gaps.

    Splitting on dates (not rows) keeps all companies on the same day in the
    same split. `gap` dates are removed between splits so a training label,
    which looks `gap` days ahead, never overlaps validation or test prices.
    """

    dates = np.sort(df[date_col].unique())
    n = len(dates)

    # Fractions apply to the dates left after removing both purge gaps,
    # so the gaps don't silently shrink the test set.
    usable = n - 2 * gap

    if usable < 10:
        raise ValueError(
            f"Not enough dates ({n}) for this split with a purge gap of {gap}."
        )

    train_end = int(usable * train_frac)
    val_start = train_end + gap
    val_end = val_start + int(usable * val_frac)
    test_start = val_end + gap

    in_dates = lambda d: df[df[date_col].isin(d)]

    return (
        in_dates(dates[:train_end]),
        in_dates(dates[val_start:val_end]),
        in_dates(dates[test_start:]),
    )


def describe_splits(splits, date_col="price_date"):
    rows = []

    for name, part in splits.items():
        rows.append({
            "split": name,
            "rows": len(part),
            "start": part[date_col].min().date(),
            "end": part[date_col].max().date(),
            "pct_up": round(part[TARGET_COL].mean(), 3),
        })

    return pd.DataFrame(rows).set_index("split")


# =========================================================
# TRAIN
# =========================================================

def train_xgb(X_train, y_train, X_val, y_val, params=None):
    """Fit XGBoost with early stopping on the validation set."""

    model = XGBClassifier(**(params or XGB_PARAMS))

    model.fit(
        X_train,
        y_train,
        eval_set=[(X_train, y_train), (X_val, y_val)],
        verbose=False,
    )

    return model


# =========================================================
# EVALUATE
# =========================================================

def classification_metrics(y_true, y_prob, threshold=0.5):
    y_pred = (y_prob >= threshold).astype(int)

    # ROC-AUC is undefined when a split contains a single class.
    roc_auc = (
        roc_auc_score(y_true, y_prob)
        if len(np.unique(y_true)) > 1
        else np.nan
    )

    return {
        "accuracy": accuracy_score(y_true, y_pred),
        "precision": precision_score(y_true, y_pred, zero_division=0),
        "recall": recall_score(y_true, y_pred, zero_division=0),
        "f1": f1_score(y_true, y_pred, zero_division=0),
        "roc_auc": roc_auc,
        "n": len(y_true),
        "pct_up_actual": float(np.mean(y_true)),
        "pct_up_predicted": float(np.mean(y_pred)),
    }


def evaluate_splits(model, splits, feature_cols):
    """Metrics for each split plus naive baselines on each split."""

    rows = {}

    for name, part in splits.items():
        y = part[TARGET_COL].to_numpy()
        prob = model.predict_proba(part[feature_cols])[:, 1]
        rows[f"xgb_{name}"] = classification_metrics(y, prob)

    # A model is only useful if it beats "always predict up".
    for name in ("val", "test"):
        y = splits[name][TARGET_COL].to_numpy()
        rows[f"always_up_{name}"] = classification_metrics(y, np.ones(len(y)))

    return pd.DataFrame(rows).T


def confusion_frame(model, part, feature_cols, threshold=0.5):
    y_true = part[TARGET_COL].to_numpy()
    y_pred = (model.predict_proba(part[feature_cols])[:, 1] >= threshold).astype(int)

    cm = confusion_matrix(y_true, y_pred, labels=[0, 1])

    return pd.DataFrame(
        cm,
        index=["actual_down", "actual_up"],
        columns=["pred_down", "pred_up"],
    )


def feature_importance(model, feature_cols):
    """Gain-based importance (avg loss reduction per split), plus split counts."""

    booster = model.get_booster()
    gain = booster.get_score(importance_type="gain")
    weight = booster.get_score(importance_type="weight")

    imp = pd.DataFrame({
        "feature": feature_cols,
        "gain": [gain.get(f, 0.0) for f in feature_cols],
        "n_splits": [int(weight.get(f, 0)) for f in feature_cols],
    })

    imp["gain_share"] = imp["gain"] / imp["gain"].sum() if imp["gain"].sum() else 0.0

    return imp.sort_values("gain", ascending=False).reset_index(drop=True)


# =========================================================
# PERSIST
# =========================================================

def save_model(model, feature_cols, metrics, name="stock_direction_xgb_baseline"):
    MODELS_DIR.mkdir(parents=True, exist_ok=True)

    model_path = MODELS_DIR / f"{name}.json"
    meta_path = MODELS_DIR / f"{name}_meta.json"

    model.save_model(model_path)

    meta = {
        "feature_cols": feature_cols,
        "best_iteration": int(model.best_iteration),
        "params": model.get_params(),
        "metrics": json.loads(metrics.to_json(orient="index")),
    }
    meta_path.write_text(json.dumps(meta, indent=2, default=str))

    return model_path, meta_path
