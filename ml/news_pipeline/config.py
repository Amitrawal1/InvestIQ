"""Settings for the automatic NSE news pipeline."""

from pathlib import Path

ML_DIR = Path(__file__).resolve().parent.parent
PROJECT_DIR = ML_DIR.parent
ENV_FILE = PROJECT_DIR / "backend" / ".env"

LOG_DIR = ML_DIR / "logs"
LOG_FILE = LOG_DIR / "news_pipeline.log"
LOCK_FILE = LOG_DIR / "news_pipeline.lock"

TIMEZONE = "Asia/Kolkata"

# ---------------------------------------------------------
# Fetching
# ---------------------------------------------------------

SOURCE = "NSE"

# Same value as the rows loaded from the notebook, so existing queries
# that filter on it keep covering new announcements too.
FEED_TYPE = "historical_announcement"

# Each run re-fetches this many days before the newest stored announcement.
# Re-fetching is safe (unique key on source + nse_seq_id) and catches late filings.
OVERLAP_DAYS = 1

# Only used when the news table has no NSE announcements at all:
# start this many days back (same window the retention step keeps).
DEFAULT_LOOKBACK_DAYS = 30

REQUEST_PAUSE_SECONDS = 1.0
MAX_RETRIES = 4

# ---------------------------------------------------------
# Sentiment
# ---------------------------------------------------------

SENTIMENT_MODEL = "ProsusAI/finbert"

# Predictions at or above this confidence are marked sentiment_confident = 1;
# the rest are kept but flagged for review.
CONFIDENCE_THRESHOLD = 0.95

SENTIMENT_BATCH_SIZE = 32
SENTIMENT_MAX_LENGTH = 256

# Cap per scheduled run so a big backlog can't make one run take too long.
# The remaining rows are picked up by the next runs. 0 = no limit.
SCORE_LIMIT_PER_RUN = 5000

# ---------------------------------------------------------
# Retention
# ---------------------------------------------------------

# Each run permanently deletes announcements (and their extracted attachment text)
# published more than this many days ago. 0 = keep everything.
RETENTION_DAYS = 30

# Rows deleted per transaction, so a big purge doesn't lock the table for long
PURGE_BATCH_SIZE = 5000
