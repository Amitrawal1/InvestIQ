"""MySQL access: connection, schema upgrades, upserts and run log."""

import json
import os
from datetime import datetime

import mysql.connector
from dotenv import load_dotenv

from .config import ENV_FILE, FEED_TYPE, PURGE_BATCH_SIZE, SOURCE

# Columns added to `news` for sentiment results
SENTIMENT_COLUMNS = {
    "sentiment": "ENUM('POSITIVE','NEGATIVE','NEUTRAL') NULL",
    "sentiment_confidence": "DECIMAL(5,4) NULL",
    "sentiment_scores": "JSON NULL",
    "sentiment_confident": "TINYINT(1) NULL",
    "sentiment_model": "VARCHAR(100) NULL",
    "sentiment_at": "DATETIME NULL",
}

RUNS_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS news_ingestion_runs (
    id BIGINT NOT NULL AUTO_INCREMENT PRIMARY KEY,
    started_at DATETIME NOT NULL,
    finished_at DATETIME NULL,
    status ENUM('running', 'success', 'failed') NOT NULL,
    from_date DATE NULL,
    to_date DATE NULL,
    fetched INT NOT NULL DEFAULT 0,
    inserted INT NOT NULL DEFAULT 0,
    existing INT NOT NULL DEFAULT 0,
    unmapped INT NOT NULL DEFAULT 0,
    unmapped_symbols TEXT NULL,
    scored INT NOT NULL DEFAULT 0,
    deleted INT NOT NULL DEFAULT 0,
    pending_sentiment INT NULL,
    day_counts JSON NULL,
    error TEXT NULL,
    KEY idx_runs_started (started_at)
)
"""

NEWS_COLUMNS = [
    "company_id", "symbol", "isin", "company_name", "headline", "content",
    "event_type", "importance", "feed_type", "published_at", "event_date",
    "date_status", "url", "source", "nse_seq_id", "attachment_url", "has_xbrl",
]

# Existing rows are refreshed; if the announcement text changed, its sentiment is
# cleared so it gets re-scored. (Assignments run left to right, so the sentiment
# checks must come before `content` is overwritten.)
_reset_if_changed = ",\n    ".join(
    f"{col} = IF(content <=> VALUES(content), {col}, NULL)" for col in SENTIMENT_COLUMNS
)

UPSERT_SQL = f"""
INSERT INTO news ({", ".join(NEWS_COLUMNS)})
VALUES ({", ".join(["%s"] * len(NEWS_COLUMNS))})
ON DUPLICATE KEY UPDATE
    {_reset_if_changed},
    content = VALUES(content),
    headline = VALUES(headline),
    event_type = VALUES(event_type),
    importance = VALUES(importance),
    published_at = VALUES(published_at),
    event_date = VALUES(event_date),
    url = VALUES(url),
    attachment_url = VALUES(attachment_url),
    has_xbrl = VALUES(has_xbrl)
"""


def get_connection():
    load_dotenv(ENV_FILE, override=True)

    return mysql.connector.connect(
        host=os.getenv("DB_HOST"),
        user=os.getenv("DB_USER"),
        password=os.getenv("DB_PASSWORD"),
        database=os.getenv("DB_NAME"),
        autocommit=False,
    )


def ensure_schema(conn):
    """Add sentiment columns and the run-log table if they don't exist yet."""

    cur = conn.cursor()

    cur.execute("""
        SELECT COLUMN_NAME FROM information_schema.COLUMNS
        WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'news'
    """)
    existing = {row[0] for row in cur.fetchall()}

    missing = [f"ADD COLUMN {name} {ddl}" for name, ddl in SENTIMENT_COLUMNS.items() if name not in existing]
    if missing:
        cur.execute("ALTER TABLE news " + ", ".join(missing))

    cur.execute("""
        SELECT 1 FROM information_schema.STATISTICS
        WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'news' AND INDEX_NAME = 'idx_news_sentiment'
    """)
    if not cur.fetchall():
        cur.execute("CREATE INDEX idx_news_sentiment ON news (sentiment)")

    # Used by the News API ordering and the retention purge
    cur.execute("""
        SELECT 1 FROM information_schema.STATISTICS
        WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'news' AND INDEX_NAME = 'idx_news_published'
    """)
    if not cur.fetchall():
        cur.execute("CREATE INDEX idx_news_published ON news (published_at)")

    cur.execute(RUNS_TABLE_SQL)

    cur.execute("""
        SELECT 1 FROM information_schema.COLUMNS
        WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'news_ingestion_runs' AND COLUMN_NAME = 'deleted'
    """)
    if not cur.fetchall():
        cur.execute("ALTER TABLE news_ingestion_runs ADD COLUMN deleted INT NOT NULL DEFAULT 0 AFTER scored")

    conn.commit()
    cur.close()


def load_company_maps(conn):
    """ISIN -> company id, SYMBOL -> company id, company id -> ISIN (same rules as the notebook)."""

    cur = conn.cursor()
    cur.execute("SELECT id, symbol, isin FROM companies ORDER BY id")

    isin_map, symbol_map, isin_by_id = {}, {}, {}
    for company_id, symbol, isin in cur.fetchall():
        if isin:
            isin_map.setdefault(isin.strip(), company_id)
            isin_by_id[company_id] = isin.strip()
        if symbol:
            symbol_map.setdefault(symbol.strip().upper(), company_id)

    cur.close()
    return isin_map, symbol_map, isin_by_id


def latest_announcement_time(conn):
    cur = conn.cursor()
    cur.execute(
        "SELECT MAX(published_at) FROM news WHERE source = %s AND feed_type = %s",
        (SOURCE, FEED_TYPE),
    )
    value = cur.fetchone()[0]
    cur.close()
    return value


def upsert_news(conn, rows):
    """Insert new announcements, refresh existing ones. Returns (inserted, existing)."""

    if not rows:
        return 0, 0

    seq_ids = [row["nse_seq_id"] for row in rows]
    cur = conn.cursor()

    placeholders = ", ".join(["%s"] * len(seq_ids))
    cur.execute(
        f"SELECT nse_seq_id FROM news WHERE source = %s AND nse_seq_id IN ({placeholders})",
        [SOURCE, *seq_ids],
    )
    already = {row[0] for row in cur.fetchall()}

    cur.executemany(UPSERT_SQL, [tuple(row[col] for col in NEWS_COLUMNS) for row in rows])
    conn.commit()
    cur.close()

    existing = sum(1 for s in seq_ids if s in already)
    return len(rows) - existing, existing


# ---------------------------------------------------------
# Retention
# ---------------------------------------------------------

def purge_old_news(conn, days):
    """Permanently delete news older than `days` (plus its attachment text). Returns rows deleted.

    Rows without a published_at fall back to when they were stored.
    """

    cur = conn.cursor()
    deleted = 0

    while True:
        cur.execute(
            """
            SELECT id FROM news
            WHERE COALESCE(published_at, created_at) < NOW() - INTERVAL %s DAY
            LIMIT %s
            """,
            (days, PURGE_BATCH_SIZE),
        )
        ids = [row[0] for row in cur.fetchall()]
        if not ids:
            break

        placeholders = ", ".join(["%s"] * len(ids))
        cur.execute(f"DELETE FROM news_attachment_text WHERE news_id IN ({placeholders})", ids)
        cur.execute(f"DELETE FROM news WHERE id IN ({placeholders})", ids)
        conn.commit()
        deleted += len(ids)

    # Attachment text whose announcement is already gone
    cur.execute("""
        DELETE nat FROM news_attachment_text nat
        LEFT JOIN news n ON n.id = nat.news_id
        WHERE n.id IS NULL
    """)
    conn.commit()
    cur.close()
    return deleted


# ---------------------------------------------------------
# Sentiment storage
# ---------------------------------------------------------

def count_pending_sentiment(conn):
    cur = conn.cursor()
    cur.execute("SELECT COUNT(*) FROM news WHERE is_duplicate = 0 AND sentiment IS NULL")
    value = cur.fetchone()[0]
    cur.close()
    return value


def fetch_pending_sentiment(conn, limit):
    """Newest unscored announcements first."""

    cur = conn.cursor(dictionary=True)
    sql = """
        SELECT id, event_type, content FROM news
        WHERE is_duplicate = 0 AND sentiment IS NULL
        ORDER BY published_at DESC
    """
    if limit:
        sql += " LIMIT %s"
        cur.execute(sql, (limit,))
    else:
        cur.execute(sql)
    rows = cur.fetchall()
    cur.close()
    return rows


def save_sentiment(conn, results, model_name):
    """results: list of (news_id, prediction dict)."""

    cur = conn.cursor()
    cur.executemany(
        """
        UPDATE news SET
            sentiment = %s,
            sentiment_confidence = %s,
            sentiment_scores = %s,
            sentiment_confident = %s,
            sentiment_model = %s,
            sentiment_at = NOW()
        WHERE id = %s
        """,
        [
            (
                p["sentiment"],
                round(p["confidence"], 4),
                json.dumps({k: round(v, 4) for k, v in p["scores"].items()}),
                int(p["confident"]),
                model_name,
                news_id,
            )
            for news_id, p in results
        ],
    )
    conn.commit()
    cur.close()


# ---------------------------------------------------------
# Run log
# ---------------------------------------------------------

def start_run(conn):
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO news_ingestion_runs (started_at, status) VALUES (%s, 'running')",
        (datetime.now(),),
    )
    conn.commit()
    run_id = cur.lastrowid
    cur.close()
    return run_id


def finish_run(conn, run_id, status, stats, error=None):
    cur = conn.cursor()
    cur.execute(
        """
        UPDATE news_ingestion_runs SET
            finished_at = %s, status = %s, from_date = %s, to_date = %s,
            fetched = %s, inserted = %s, existing = %s, unmapped = %s,
            unmapped_symbols = %s, scored = %s, deleted = %s, pending_sentiment = %s,
            day_counts = %s, error = %s
        WHERE id = %s
        """,
        (
            datetime.now(), status, stats.get("from_date"), stats.get("to_date"),
            stats.get("fetched", 0), stats.get("inserted", 0), stats.get("existing", 0),
            stats.get("unmapped", 0),
            ", ".join(sorted(stats.get("unmapped_symbols", set())))[:5000] or None,
            stats.get("scored", 0), stats.get("deleted", 0), stats.get("pending_sentiment"),
            json.dumps(stats.get("day_counts", {})), error, run_id,
        ),
    )
    conn.commit()
    cur.close()
