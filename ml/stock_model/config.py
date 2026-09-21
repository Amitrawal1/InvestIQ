"""Central configuration for the stock-direction baseline model."""

from pathlib import Path

ML_DIR = Path(__file__).resolve().parent.parent
PROJECT_DIR = ML_DIR.parent
ENV_FILE = PROJECT_DIR / "backend" / ".env"
MODELS_DIR = ML_DIR / "models"

RANDOM_SEED = 42

# ---------------------------------------------------------
# Target
# ---------------------------------------------------------

# Predict whether close price is higher N trading days from now.
TARGET_HORIZON = 20

# ---------------------------------------------------------
# Price features
# ---------------------------------------------------------

RETURN_WINDOWS = (1, 5, 20)
MA_WINDOWS = (5, 20, 50)
VOLATILITY_WINDOWS = (5, 20)
VOLUME_WINDOWS = (5, 20)
RSI_WINDOW = 14

# Rows are kept once all features up to this lookback are available.
# Longer windows (e.g. SMA 50) stay NaN early on; XGBoost handles NaN natively.
MIN_LOOKBACK = 20

# ---------------------------------------------------------
# Fundamentals: point-in-time publication lag
# ---------------------------------------------------------

# SEBI LODR deadlines: quarterly results within 45 days of quarter end,
# annual results within 60 days of year end. A statement is only treated as
# "known" to the model from period_end_date + lag, to avoid look-ahead bias.
QUARTERLY_REPORT_LAG_DAYS = 45
YEARLY_REPORT_LAG_DAYS = 60

# ---------------------------------------------------------
# Time-based split
# ---------------------------------------------------------

TRAIN_FRAC = 0.6
VAL_FRAC = 0.2
# Test gets the remainder. Between consecutive splits we purge
# TARGET_HORIZON dates so a training label never overlaps validation/test prices.
PURGE_GAP = TARGET_HORIZON

# ---------------------------------------------------------
# XGBoost
# ---------------------------------------------------------

# Deliberately shallow and regularised: the current dataset is tiny.
XGB_PARAMS = {
    "n_estimators": 300,
    "max_depth": 3,
    "learning_rate": 0.05,
    "subsample": 0.8,
    "colsample_bytree": 0.8,
    "min_child_weight": 3,
    "reg_lambda": 1.0,
    "objective": "binary:logistic",
    "eval_metric": "logloss",
    "early_stopping_rounds": 30,
    "random_state": RANDOM_SEED,
    "n_jobs": -1,
}
