# Data fixes: pre-2022 balance sheets, bank NPA / CET1, missing INDUSINDBK

Two known gaps in `financial_filings`, what causes them, what changed in the code, the proof that
nothing else moved, and the exact commands to backfill. Investigated 2026-10-02 on the local XBRL
cache (66,839 files) with SELECT-only database access; no table was written.

## A. No balance sheet before the Sep-2022 half-year

### Root cause: the source

**NSE's results XBRL for periods before 30 Sep 2022 does not contain a balance sheet.** It is not
the parser and not the collector.

- Scan of all 66,839 cached XBRL files for any balance-sheet element (`Assets`, `Equity`,
  `EquityAndLiabilities`, `CurrentAssets`, `BorrowingsCurrent`, ...): 0% of the files for periods
  2018-03 .. 2022-06 carry one (the few hits are lenders' P&L `Deposits` lines), against 98-100% of
  the Sep and Mar files from Sep 2022 on.
- It is not a taxonomy problem: pre- and post-2022 files use the same schema
  (`Ind-AS_entry_point_2020-03-31.xsd`, which has the balance-sheet elements). The difference is
  NSE's filing template. NSE moved results filing to a new system in mid-2022 (its seq numbers
  restarted at 1: RELIANCE's Jun-2022 filing is seq 595, Sep-2022 is 4823), and that template added
  the Statement of Assets and Liabilities. The proof: the ~40 pre-Sep-2022 periods that were filed
  or re-filed on the new system (e.g. ATLASCYCLE Sep-2020 re-filed in 2023, AHLWEST FY21, J&KBANK
  FY22, Dec-year companies' Jun-2022 half-year like ABB, CRISIL, VBL) do carry a full balance sheet.
- Example: RELIANCE FY21 consolidated (seq 1106825) has 160 element types (P&L, segments, cash flow,
  `ReserveExcludingRevaluationReserves`, `PaidUpValueOfEquityShareCapital`, `NetSegmentAssets`) but
  no `Assets`/`Equity`/`Borrowings*` at all. Same for TCS, DIXON (2020-2022) and every small cap
  checked. KAYNES listed in Nov 2022, so it has no pre-2022 filings.
- Later filings do not carry the earlier balance sheet either: the Sep-2022 filing's only prior-date
  instant (`PY_I`, 2022-03-31) holds just the opening cash of the cash flow, and Mar filings have no
  prior-year balance-sheet column.
- NSE's other endpoints don't have it: `corporates-financial-results-data` for RELIANCE FY21
  returns the same P&L fields (`re_*`, incl. `re_pdup` paid-up capital and `re_res_reval` reserves)
  and segment data, no balance sheet. The listing's other attachment
  (`na_attachments/RELIANCE_NA_30042021200201_1.zip`) is the PDF of the results: the balance sheet
  is only there, unstructured. The collector already downloads the only XBRL each filing has.
- The cash flow follows the same pattern: the 2017 taxonomy template (used until FY2019-20) has no
  cash-flow section; it appears from the Sep-2020 half-year. Nothing to recover there either.

So a full pre-2022 balance sheet (debt, current assets/liabilities, receivables) **cannot be
recovered from NSE XBRL**. ROCE, debt/equity and current ratio stay unavailable before Sep 2022
unless the PDFs are parsed (not attempted) or another source (MCA AOC-4 XBRL, BSE) is added.

### What is recoverable: two balance-sheet totals that the legacy filings repeat

| field | legacy source line | checked on filings that carry both (period >= Sep 2022) |
|---|---|---|
| `total_assets` | `NetSegmentAssets` (segment assets + unallocable assets, instant at the period end; filed by multi-segment companies) | 5,871 filings: equal (within 0.5%) in 94.2%, within 2% in 95.5% |
| `equity_owners` | `PaidUpValueOfEquityShareCapital` + `ReserveExcludingRevaluationReserves`, in the 12-month (financial-year) column of the annual results | 7,756 filings: equal in 86.9%, within 10% in 92.4%, more than 2x off in 1.4%; after the sanity checks below: 88.1% / 93.6% / 0.46% |
| `total_equity` | the same number, **standalone results only** (no non-controlling interest exists) | (same check) |

The equity mismatches are mostly companies whose "reserves" line excludes part of other equity
(securities premium, retained losses), ~1% that report total equity including NCI (e.g. TCS: 91,206
vs owners' 90,424 in FY23), and unit/keying errors. Sanity checks drop owners' equity above total
assets and above 200x the year's total income (on the check set this removes 65 of 7,756 values, 42
of them grossly wrong; the real 99.5th percentile of equity / income is ~130x). Negative proxies are
kept: 275 of 304 are real negative equity.

Known values reproduced (consolidated owners' equity, INR crore): RELIANCE FY20 4,53,331 and FY21
7,00,172; INFY FY21 76,351; RELIANCE FY23 parsed both ways = 8,21,153 (proxy) vs 8,21,153 (balance
sheet), total assets 17,13,506 = 17,13,506.

### Code change (`xbrl_parse.py`)

`_legacy_balance_sheet` / `_legacy_segment_assets`, used only when **all** of these hold: the
filing has no balance sheet of its own, format `non_financial`, no `fin_sector_format` override (so
the fin_sector extract is unaffected), period end before `LEGACY_TEMPLATE_END = 2022-09-30`, and a
12-month P&L context ending at the period end exists (the annual results; Mar for most, Dec for
Dec-year companies). It fills `total_assets`, `equity_owners`, `total_equity` (standalone) and
leaves every other balance-sheet key None. Legacy files often leave the plain instant context
undefined, so an undefined context carrying `NetSegmentAssets` (and no reporting dates) is accepted
when it is the only one. No warning is added, so `parse_status` never changes; the rows are
recognisable by `period_end < '2022-09-30' AND bs_current_assets IS NULL`.

Why only annual filings: features.py uses the *latest* visible balance sheet, so a quarter with only
segment assets would hide the March equity and blank ROE for the next quarters.

### Regression proof

Old parser (copy of HEAD) vs new parser on every cached file, compared as `json.dumps(sort_keys)`,
default call on all 66,839 files plus `fin_sector_format=<company format>` on all 5,937 filings of
the fin_sector extract (72,776 parses):

| result | default call | fin_sector call |
|---|---|---|
| byte-identical | 57,333 | 5,924 |
| `balance_sheet` None -> legacy totals (all period end 2018-03-31 .. 2022-03-31, all non_financial, 1,415 companies) | 9,493 | 0 |
| `fin_sector.quarter.cet1_ratio` None -> value (FINOPB only, see B) | 13 | 13 |
| anything else | 0 | 0 |

**All 35,034 cached files with period end on/after 2022-09-30 are byte-identical**, except FINOPB's
13 CET1 values inside the `fin_sector` block (which has no table columns). At the table level
(`store.build_row` old vs new on the 9,506 changed parses): only `bs_equity_owners` (8,766 rows),
`bs_total_assets` (3,064) and `bs_total_equity` (2,709) change; `parse_status` is identical for all.

### Coverage before / after (stored non_financial filings; "after" = new parser on the cache)

| March filings of FY | n | any balance-sheet value before | after | owners' equity after |
|---|---|---|---|---|
| 2018 | 2,814 | 0.0% | 47.5% | 45.7% |
| 2019 | 1,998 | 0.0% | 76.0% | 71.5% |
| 2020 | 2,545 | 0.0% | 79.5% | 73.8% |
| 2021 | 2,646 | 0.2% | 78.6% | 71.3% |
| 2022 | 2,988 | 0.3% | 79.7% | 71.8% |
| 2023-2026 | | 99-99.5% | unchanged | |

Pre-Sep-2022 March filings: total_assets 23.2%, equity_owners 66.4%, total_equity 20.3%.
Quarterly (Jun/Sep/Dec) filings before Sep 2022 stay without a balance sheet by design.

| company (Mar, consolidated unless noted) | FY19 | FY20 | FY21 | FY22 |
|---|---|---|---|---|
| RELIANCE assets / owners' equity | 10,02,406 / 3,87,112 | 11,65,915 / 4,53,331 | 13,39,390 / 7,00,172 | standalone only filed: 8,95,562 / 4,71,527 |
| TCS owners' equity (no segment assets filed after FY19) | 1,14,943 assets / 89,254 | 84,749 | 87,108 | 89,846 |
| DIXON owners' equity | - | 541 | 737 | 997 |
| SAFARI owners' equity | - | 231 | 279 | 301 |
| CERA owners' equity | 700 (standalone) | 771 | 872 | 1,015 |
| TANLA | 733 | 702 | none (reserves filed 0.00) | none |

### What it does and doesn't fix downstream

- features.py (non_financial, unchanged code): ROE needs `bs_total_equity`, so from FY2018-FY2022 it
  now works for standalone-basis companies; for consolidated-basis companies `bs_total_equity` stays
  NULL (NCI unknown) and ROE stays NaN unless features.py falls back to `equity_owners` with
  `net_profit_owners` (a one-line change in `_features`, not made here since it changes the model's
  inputs). `accruals_ratio` gains total assets where segments are filed. ROCE, debt/equity, current
  ratio, receivables growth: still from Nov 2022 only.
- The backend company page (`pickPerPeriod`) will show these March rows with total assets / equity.
- financial_model (train/score) reads features: retrain only after you decide on the ROE fallback.

## B. Banks' NPA / CET1 missing; INDUSINDBK without filings

### Root causes

1. **Collector keeps one statement type per period.** `select_filings` keeps the consolidated filing
   when one exists. HDFCBANK, SBIN, PNB, BANKBARODA, BANKINDIA, UNIONBANK, IDFCFIRSTB and RBLBANK
   leave `PercentageOfGrossNpa`, `PercentageOfNpa`, `GrossNonPerformingAssets`, `CET1Ratio` and
   `ReturnOnAssets` as 0.00 in their consolidated XBRL (RBI ratios are reported on the bank's own
   books), and their standalone XBRL, which has them, was never downloaded (2-5 of ~35 per bank
   were in the cache).
2. **FINOPB is a different case.** Fino is a payments bank: it files only standalone results (all 16
   collected). Its NPA is genuinely 0.00 (payments banks can't lend), so None ("not applicable") is
   right. Its CET1 (61-79%) was rejected by the parser's plausibility bound of 60%; it is the only
   bank in the cache above 0.6 (the 1.00 it filed in 2022 is a placeholder).
3. **INDUSINDBK: a database outage, not a symbol/ISIN problem.** Symbol and ISIN map fine
   (`companies.id` 1048, INE095A01012) and NSE lists it normally (bank='B', 65 XBRL filings). In the
   2026-09-28 21:10 run the TiDB connection dropped while it was being collected: every upsert logged
   `not stored: MySQL Connection not available.`, the company commit failed with `Lost connection to
   MySQL server during query`, so nothing was stored, although all 28 XBRL files were downloaded and
   cached. The collector then moved on. The same outage left **RKDL (40 cached files), INDTERRAIN
   (29), INDIGOPNTS (22) and SEDEMAC (2)** with no rows; they are the only cached companies without
   rows. (Six of INDUSINDBK's links are 404 on NSE's archive; those quarters stay missing.)

### Code changes

- `collect.py`
  - `is_bank(records)`: NSE's listing field `bank == 'B'`, or a `BANKING_*` XBRL file name
    (integrated-filing records have no `bank` field). Matches exactly the 41 banks in the cache.
  - `select_filings(..., bank_standalone=True)`: banks keep **both** statement types per period
    (default; `--no-bank-standalone` restores the old behaviour). Proof on all 2,525 cached listings
    (offline, old vs new function): 2,493 companies select exactly the same filings; the 32 that
    change are all banks, and each new selection is a superset of the old one.
  - `--download-only`: list + download into the XBRL cache, no parsing, no table writes (no
    `CREATE TABLE`, no upsert, no commit; the DB is only read for already-stored seq numbers).
  - DB connection loss (`mysql.connector` OperationalError / InterfaceError) during an upsert now
    aborts the company instead of logging every remaining row as "not stored"; the main loop
    reconnects and retries the company once (from the cache, so no extra downloads). Other upsert
    errors are handled as before.
- `xbrl_parse.py`: `FIN_RATIO_ACCEPT_UP_TO = {"cet1_ratio": 0.9}` lets payments-bank CET1 through.
  Kept outside `FIN_RATIO_TAGS` so the out-of-range warning text for real keying errors (e.g. CET1
  0.0026) is byte-identical. Only FINOPB's 13 files change (table above).
- `fin_sector_features.py`: `fill_bank_ratios_from_standalone` (called at the end of
  `raw_from_extract`). For `bank`-format consolidated rows, NaN `fsq_gross_npa_pct`, `fsq_net_npa_pct`,
  `fsq_gross_npa`, `fsq_net_npa`, `fsq_cet1_ratio`, `fsq_roa_reported` are filled from the earliest
  standalone filing of the same company and period that has them; filed consolidated values are never
  replaced. Point in time: if that standalone filing was published later than the consolidated one
  (they are minutes apart), the row takes the later `filing_date`. Look-ahead check
  (`--check 100`): 0 mismatches.
  Regression on the current extract (no new data): 4,210 rows, identical except 6 rows that already
  had both filings in the cache, which gain their (correct) ratios: AXISBANK FY19 GNPA 5.26%,
  FEDERALBNK FY18/FY19, HDFCBANK FY19 GNPA 1.36% / NNPA 0.39% / CET1 17.1%, PNB FY19 GNPA 15.5%,
  SBIN FY19 GNPA 7.53% (two of them with a filing_date a few seconds/minutes later).

### Test on the 10 banks (download into the local cache only)

BANK_TEST_RESULTS

## Backfill commands (run from `ml/`, in this order)

BACKFILL

## Files changed

- `ml/financials/xbrl_parse.py`: legacy balance-sheet totals; payments-bank CET1 bound.
- `ml/financials/collect.py`: banks keep both statement types; `--download-only`;
  `--no-bank-standalone`; reconnect-and-retry on a lost DB connection.
- `ml/financials/fin_sector_features.py`: bank ratios from the standalone filing.
- `ml/financials/README.md`: documents the above.
- `ml/financials/DATA_FIXES.md`: this file.

Not touched: ml/rankings, ml/financial_model, backend, frontend, workflows, store.py, features.py.

## Other finding (not fixed)

252 cached companies have no XBRL at all because NSE's results listing returns nothing for them
(e.g. MCX, HEG: empty for Quarterly, Annual and Integrated, re-checked today; ABBOTINDIA: one 2010
record without XBRL). That is a separate coverage gap worth a look (different symbol on NSE's
results API, or results filed only to BSE).
