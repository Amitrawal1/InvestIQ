# News pipeline

Keeps the `news` table up to date with NSE corporate announcements, scores each one with FinBERT,
and keeps only the last 30 days.

```
every 15 min (launchd)
  1. fetch   NSE announcements since the newest stored one (minus 1 day overlap)
  2. store   upsert into `news` (unique on source + nse_seq_id, so re-fetching is safe)
  3. purge   permanently delete news published > 30 days ago, plus its news_attachment_text
  4. score   FinBERT sentiment for every row with sentiment IS NULL
  5. log     one row per run in `news_ingestion_runs`
```

## Commands (run from `ml/`)

| Command | What it does |
|---|---|
| `python3 -m news_pipeline.run` | One normal run: catch up + score up to 5,000 rows |
| `python3 -m news_pipeline.run --from 2026-09-01` | Re-fetch from a date (backfill; anything older than 30 days is deleted again) |
| `python3 -m news_pipeline.run --no-fetch --score-limit 0` | Score the whole backlog |
| `python3 -m news_pipeline.run --retention-days 0` | One run without deleting old news |
| `./news_pipeline/schedule.sh install` | Start the 15-minute schedule |
| `./news_pipeline/schedule.sh status` | Check the schedule and recent log |
| `./news_pipeline/schedule.sh uninstall` | Stop the schedule |

Logs: `ml/logs/news_pipeline.log`

## Retention

Set in `config.py`: `RETENTION_DAYS = 30` (0 = keep everything). Deletion is permanent.
Rows with no `published_at` use `created_at` instead. Each run's count is in
`news_ingestion_runs.deleted`.

## Columns added to `news`

| Column | Meaning |
|---|---|
| `sentiment` | `POSITIVE` / `NEGATIVE` / `NEUTRAL` |
| `sentiment_confidence` | FinBERT's probability for that label (0–1) |
| `sentiment_confident` | `1` if confidence ≥ 0.95, otherwise `0` (review) |
| `sentiment_scores` | All three probabilities as JSON |
| `sentiment_model`, `sentiment_at` | Which model scored it, and when |

If an announcement's text changes on a later fetch, its sentiment is cleared and re-scored.

## Useful checks

```sql
-- Did every run succeed?
SELECT id, started_at, status, fetched, inserted, unmapped, deleted, scored, pending_sentiment
FROM news_ingestion_runs ORDER BY id DESC LIMIT 20;

-- Confident vs. needs-review
SELECT sentiment, sentiment_confident, COUNT(*) FROM news
WHERE sentiment IS NOT NULL GROUP BY 1, 2;
```

Announcements for companies missing from `companies` can't be stored (`news.company_id`
is required); each run lists them in `news_ingestion_runs.unmapped_symbols`.
