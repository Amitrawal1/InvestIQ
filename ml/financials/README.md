# Financials from NSE XBRL filings

Collects each listed company's **income statement, balance sheet and cash flow** from the XBRL
files attached to its NSE result filings, and stores one row per filing in the `financial_filings`
table. Every row keeps its `filing_date`, so features can be joined point-in-time (on any date, only
filings already public by that date are visible).

This is the data layer of the Financial Model. Features (growth, margins, ROE/ROCE, leverage,
liquidity, cash-flow quality) and models are built on top of it later.

## Modules

| File | Role |
|---|---|
| `config.py` | Paths, sample symbols, shared constants |
| `fetch_samples.py` | One-off: downloads a fixed sample of filings to `ml/data/raw/xbrl_samples/` for offline development |
| `xbrl_parse.py` | `parse_xbrl(xml_text) -> dict` - pure function, no network, no DB |
| `store.py` | `financial_filings` table DDL and upserts |
| `collect.py` | CLI: list filings per company, download XBRL (cached), parse, store. Resumable, rate-limited |
| `validate.py` | CLI: checks parser output against NSE's JSON figures and accounting identities |

## Parser contract: `parse_xbrl(xml_text: str) -> dict`

All money values are **INR crore** (XBRL reports rupees: divide by 1e7). Per-share values stay in
rupees. A value that isn't reported is `None`, never 0.

```python
{
  "symbol": str | None,            # from the filing's dei/general tags when present
  "isin": str | None,
  "statement_type": "consolidated" | "standalone" | None,
  "format": "non_financial" | "bank" | "nbfc" | "insurance" | "unknown",
  "period_start": "YYYY-MM-DD",    # of the current-quarter (or current-period) P&L context
  "period_end": "YYYY-MM-DD",
  "months": int,                   # length of that P&L period: 3 for a quarter, 12 for annual-only filings

  "income": {                      # current quarter (the shortest current P&L context)
    "revenue", "other_income", "total_income", "total_expenses",
    "cost_of_materials", "employee_expense", "finance_costs", "depreciation",
    "profit_before_exceptional", "exceptional_items", "profit_before_tax",
    "tax", "net_profit", "net_profit_owners", "eps_basic", "eps_diluted",
  },
  "income_ytd": None | {            # year-to-date P&L context when present (e.g. 6 or 12 months)
    "months": int, ...same keys as income...
  },
  "balance_sheet": None | {         # as of period_end; usually only in Sep (H1) and Mar (FY) filings
    "total_assets", "non_current_assets", "current_assets",
    "cash_and_equivalents", "inventories", "trade_receivables",
    "total_equity", "equity_owners", "non_controlling_interest",
    "borrowings_current", "borrowings_noncurrent", "total_debt",
    "non_current_liabilities", "current_liabilities", "trade_payables",
  },
  "cash_flow": None | {             # cumulative year-to-date, as filed (6 months in Sep, 12 in Mar)
    "months": int,
    "operating_cf", "investing_cf", "financing_cf",
    "capex",                        # purchase of PP&E + intangibles, as a POSITIVE number
    "net_change_in_cash",
  },
  "warnings": [str],                # anything odd: missing context, unit guess, sign flips, ...
}
```

Rules:
- Pick contexts by their dates, not by context-id names (`OneD`, `FourD`, `OneI` are common but not
  guaranteed). Duration contexts ending at the period end: shortest = quarter, longest = YTD.
  Instant context at the period end = balance sheet.
- Ignore contexts with dimensions/segments (segment reporting), except where needed for
  owners vs non-controlling interest.
- `total_debt = borrowings_current + borrowings_noncurrent` (treat a missing part as 0 only if the
  other part is present).
- Banks/NBFCs/insurers use different tags. Detect the format; fill what maps cleanly
  (interest earned -> revenue, etc.), leave the rest `None`, and add a warning. Do not guess.

## Table: `financial_filings`

One row per NSE filing (`nse_seq_number` unique). Columns mirror the parser output flattened with
prefixes: `inc_*` (quarter), `ytd_*` (YTD P&L, plus `ytd_months`), `bs_*` (balance sheet),
`cf_*` (cash flow, plus `cf_months`). Plus: `company_id`, `symbol`, `isin`, `statement_type`,
`format`, `period_start`, `period_end`, `months`, `filing_date` (DATETIME, IST, from the NSE
listing record), `xbrl_url`, `parse_status` (`ok` / `partial` / `failed`), `warnings` (JSON),
`created_at`, `updated_at`.

## NSE access rules

- NSE blocks aggressive clients. **One process talks to NSE at a time, ~1 request/second**, via
  `fundamentals.nse_client.NSEResultsClient` (reuse it; it handles cookies and retries).
- Everything downloaded is cached on disk (`ml/data/raw/xbrl/<SYMBOL>/<seq>.xml`) and never
  re-downloaded unless `--refresh` is given.
- Development and tests use `ml/data/raw/xbrl_samples/` only (no network).
