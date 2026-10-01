# Company rankings: shared contract

InvestIQ ranks listed companies by **estimated growth potential**. A ranking job writes dated
snapshots to `company_rankings`; the backend serves them; the frontend shows them on sector pages,
industry (category) filters, the Predictor list and each Company Details page.

Until the ML model is trained, scores come from a transparent **preliminary** method
(`model_version = 'prelim-v1'`): percentile ranks of financial, market and news signals. When the
ML model is ready it writes the same table with a new `model_version`; nothing else changes.

Snapshots are rebuilt every 15 days (1st and 16th of the month) and can be run on demand.

## Table `company_rankings` (TiDB)

```sql
CREATE TABLE IF NOT EXISTS company_rankings (
    snapshot_date DATE NOT NULL,
    company_id INT NOT NULL,
    symbol VARCHAR(50) NOT NULL,
    model_version VARCHAR(30) NOT NULL,

    growth_score DECIMAL(5,2) NULL,          -- 0-100, NULL when too little data to rank
    growth_label VARCHAR(20) NOT NULL,       -- 'Strong' | 'Positive' | 'Neutral' | 'Weak' | 'Insufficient data'
    rank_overall INT NULL,                   -- 1 = best, among ranked companies; NULL if unranked
    rank_in_sector INT NULL,
    rank_in_industry INT NULL,
    coverage DECIMAL(4,2) NOT NULL,          -- share of components available, 0-1

    -- component scores, 0-100 (NULL = not available)
    score_growth DECIMAL(5,2) NULL,
    score_profitability DECIMAL(5,2) NULL,
    score_financial_health DECIMAL(5,2) NULL, -- leverage + liquidity
    score_cash_flow DECIMAL(5,2) NULL,
    score_momentum DECIMAL(5,2) NULL,         -- market/price behaviour
    score_news DECIMAL(5,2) NULL,

    reasons JSON NULL,      -- ["Revenue up 34% YoY", "ROCE 24%, top 10% of peers", ...] strengths, max ~5
    risks JSON NULL,        -- ["Debt/equity rose from 0.4 to 1.1 in a year", ...] red flags, max ~5
    key_metrics JSON NULL,  -- see below
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,

    PRIMARY KEY (snapshot_date, company_id),
    KEY idx_rank (snapshot_date, rank_overall),
    KEY idx_symbol (symbol, snapshot_date)
);
```

`key_metrics` (all optional; money in INR crore, ratios as fractions, returns as fractions):
```json
{
  "as_of_period": "2026-06-30", "last_filing_date": "2026-07-31",
  "revenue_ttm": 48872.8, "net_profit_ttm": 1650.2,
  "revenue_growth_yoy": 0.34, "profit_growth_yoy": 0.21, "revenue_ttm_growth": 0.28,
  "op_margin_ttm": 0.041, "net_margin_ttm": 0.034, "roe": 0.29, "roce": 0.35,
  "debt_to_equity": 0.12, "current_ratio": 1.4, "ocf_ttm": 1782.3, "fcf_ttm": 714.8,
  "market_cap_est": 91200.0, "last_price": 15320.5, "price_date": "2026-09-25",
  "return_1m": 0.03, "return_3m": 0.11, "return_6m": 0.18, "return_1y": 0.42,
  "return_1y_vs_smallcap": 0.25, "volatility_1y": 0.38, "avg_traded_value_3m_cr": 812.4,
  "news_count_90d": 14, "news_sentiment_90d": 0.21
}
```

### `key_metrics.top_list` (investiq-v1, `ml/rankings/build_v3.py` + `ml/rankings/portfolio.py`)

```json
{ "eligible": true, "not_eligible_reason": null, "in_list": true, "position": 4, "status": "new" }
```
The Top list is the 50 names chosen by `portfolio.RECOMMENDED` (backtest: `ml/rankings/reports/PORTFOLIO.md`):
>= Rs 0.5 cr traded a day and >= 1 year of prices (else `eligible: false` with the reason), no new entries
among the 5% most volatile stocks, holdings kept while ranked within the top 150 eligible names
(`status: "kept"`), vacancies filled from the top (`status: "new"`). Previous holdings are read from the
previous investiq-v1 snapshot. Rows of older snapshots have no `top_list` (API returns `null`).

## Backend API (Express, mounted without /api; the frontend calls /api/...)

| Route | Returns |
|---|---|
| `GET /rankings?sector=<slug>&industry=<name>&search=<text>&label=<growth_label>&sort=rank\|score\|name\|return_1y&page=1&limit=50` | `{ snapshot_date, model_version, total, page, limit, data: [RankingRow] }`, latest snapshot only; unranked companies last |
| `GET /rankings?list=top` | Same shape, only Top list rows, ordered by `top_list.position` unless `sort` is given (other filters still apply) |
| `GET /rankings/meta` | `{ snapshot_date, model_version, next_update, ranked, unranked, method: "<one paragraph>", top_list: { count, rules: [str] }, snapshots: ["2026-09-28", ...] }` |
| `GET /sectors/:slug/industries` | `[{ industry, company_count, ranked_count, avg_score, top_symbol }]` |
| `GET /companies/:symbol` | `{ profile, ranking: RankingDetail \| null, score_history: [{snapshot_date, growth_score, rank_overall}] }` |
| `GET /companies/:symbol/financials` | `{ quarterly: [...], half_yearly: [...], latest_ratios: {...} }` (see below) |
| `GET /companies/:symbol/prices?range=6m\|1y\|3y\|5y\|max` | `{ symbol, data: [{date, close, volume}], benchmark: {name: "NIFTY SMALLCAP 250", data: [{date, close}]} }` |
| News | existing `GET /news/company/:companyId` and `GET /news?symbol=` |

`RankingRow`: `company_id, symbol, name, sector, sector_slug, industry, growth_score, growth_label,
rank_overall, rank_in_sector, rank_in_industry, coverage, score_growth, score_profitability,
score_financial_health, score_cash_flow, score_momentum, score_news, key_metrics` (subset:
last_price, return_1y, revenue_growth_yoy, roe, market_cap_est), `top_list` (object above or null).

`RankingDetail` = RankingRow + `reasons`, `risks`, full `key_metrics`, `model_version`, `snapshot_date`.

`profile`: `id, symbol, name, isin, series, market_segment, listing_date, sector, sector_slug,
industry, website, description`.

`financials.quarterly[]`: `period_end, filing_date, statement_type, revenue, net_profit, eps_basic,
op_margin, net_margin` (from `financial_filings` quarter P&L, newest last, up to 12).
`financials.half_yearly[]`: `period_end, total_assets, total_equity, total_debt, current_assets,
current_liabilities, cash_and_equivalents, operating_cf, capex, free_cash_flow, cf_months`.
`latest_ratios`: the ratio fields from the latest feature row (growth, margins, ROE, ROCE, D/E,
current ratio, interest coverage, cash conversion).

Unknown symbol -> 404 `{ success: false, message }`. Symbols are case-insensitive.

## Frontend routes

| Route | Page |
|---|---|
| `/sectors/:slug` | Sector: industry chips (`?industry=<name>` selects a category), companies ranked by growth signal |
| `/predictor` | Full ranked list: search, sector/industry/label filters, sort, pagination, snapshot date + "updated every 15 days" |
| `/company/:symbol` | Company Details: header, InvestIQ analysis, market data, financials, news |

Every company row links to `/company/:symbol`. Pages show a short disclaimer: research/screening
tool, not investment advice.
