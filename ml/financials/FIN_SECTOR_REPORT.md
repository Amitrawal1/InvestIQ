# Banks, NBFCs and insurers: coverage, parser extension, features, evaluation

Date: 2026-09-30. Scope: `ml/financials/` only. The DB was read with SELECT only; nothing was
collected or written to it.

## Summary

- **Coverage.** 236 of the 243 Financial Services companies in the 2026-09-28 snapshot are
  unranked ("Insufficient data"), because features.py only reads `non_financial` filings. 193 companies (176 of them in
  Financial Services) file mostly in lender formats: 40 banks, 142 NBFC-format filers (lenders plus
  brokers, AMCs and holding companies) and 11 insurers. They now have point-in-time features.
  At the 2026-09-28 snapshot, 183 of the 193 have a fresh row with at least 2 growth readings.
- **Parser.** A new `fin_sector` block (new keys only) adds interest earned and expended, NII,
  opex, pre-provision profit, provisions, GNPA and NNPA (amount and %), CET1, AT1, reported ROA,
  advances, deposits, borrowings and net worth. For insurers it adds premiums, claims, combined
  ratio and solvency.
  - All 61,962 cached non-financial filings produce byte-identical output.
  - All 4,815 bank and NBFC filings are identical apart from the new key.
  - Insurers' 62 filings, which all failed before, now parse.
- **Evaluation.** The financial features do not reliably predict 6m or 12m excess returns in this
  sector. Treat these results as **indicative only; this is not a usable model**.
  - The fixed equal-weight blend has mean IC -0.04 (6m) and -0.08 (12m).
  - Over the same names, the market model's price-trend score has IC +0.08 and +0.10.
  - Two things did hold up:
    - For banks, the growth features were mildly positive: pre-provision-profit growth had IC
      +0.09 (6m) and +0.12 (12m).
    - Banks flagged for worsening asset quality trailed their peers by 9% (6m) and 12% (12m),
      in 4 of 4-5 years.
  - For lending NBFCs (2022-2026), growth and ROA ranked in the *wrong* direction in almost every
    year.
- **Recommendation.** Rank these companies with their own sub-features mapped onto the existing
  components. Weight momentum most (0.50) and give the financial components 0.15 each (cash flow
  does not apply). Penalise worsening asset quality and near-minimum capital. Compare banks,
  lending NBFCs, other NBFC-format filers and insurers within their own peer groups.

## 1. Coverage audit

### Who files what

| Financial Services companies (`companies.sector_id = 3`) | count |
|---|---|
| total | 248 |
| with bank / NBFC / insurance filings | 185 (125 also have some `non_financial` filings) |
| no filings at all | 38 (mostly tiny NBFCs and investment companies, plus **INDUSINDBK**; 4 are SME-platform series SM/ST) |
| in scope of `fin_sector_features` (most parsed filings in a lender format) | 176 |
| left to `features.py` (mostly `non_financial` filings, e.g. MOTILALOFS, GFLLIMITED) | 72 (34 have `non_financial` filings) |

In scope overall there are 193 companies. The 17 outside Financial Services are holding and
investment companies in Services, Energy and Technology that file the NBFC format.

| format in `financial_filings` | filings | companies | parse_status |
|---|---|---|---|
| bank | 1,548 | 169 (incl. 2018 misdetections, below) | 1,216 partial, 332 failed |
| nbfc | 3,255 | 154 | all partial |
| insurance | 62 | 11 | **all failed** ("no profit-and-loss context found") |

There are two format-detection quirks. I found them and left them unfixed:

- The 332 failed "bank" filings are all 2018 old-GAAP (non-Ind-AS) files. Their schema name
  `other_than_banks_entry_point` contains "bank", so the parser labels them as banks. Their context
  layout also has no plain P&L context, so they fail either way.
- 542 quarters of NBFCs are detected as `non_financial` (Division II template, no
  `InterestEarned`). `fin_sector_features` re-parses them with the company's format. Net revenue and
  profit are still available for them; interest income, NII and provisions are not.

### Field fill rates (usable in-scope filings, re-parsed)

Balance-sheet rates are measured over the Sep and Mar (H1/FY) filings, since Jun and Dec filings
have no balance sheet.

| bank (40 cos, 1,187 filings) | filled | first year | 2024+ |
|---|---|---|---|
| interest earned / expended, opex, pre-provision profit, provisions | 100% | 2018 | 100% |
| net profit | 99% | 2018 | 100% |
| gross / net NPA %, NPA amounts | 77-80% | 2018 | 74-78% |
| CET1 ratio | 84% | 2018 | 80% |
| AT1 ratio | 49% | 2018 | 35% (inconsistent: some banks file Tier 1 here) |
| reported ROA | 80% | 2018 | 80% (annualised by some banks, not by others) |
| advances, deposits, net worth, total assets (H1/FY) | 45% | **Sep 2022** | 100% |

| NBFC format (142 cos, 3,679 filings) | filled | first year | 2024+ |
|---|---|---|---|
| finance costs, net profit | 100% | 2018 | 100% |
| interest income, fees, impairment (ECL), derived opex / PPOP | 85% | 2019 | 92% |
| loans, borrowings (H1/FY) | 54% | **Sep 2022** | 92% |
| deposits | 42% | Sep 2022 | 72% (only deposit-taking NBFCs) |
| GNPA / Stage 3, capital adequacy | **not in the XBRL** | - | - |

| insurance (11 cos, 62 filings) | filled | first year |
|---|---|---|
| gross / net premium, PAT, PBT, EPS, solvency ratio | 100% | **Apr 2025** (Integrated Filing only) |
| premium earned, incurred claims, claims ratio, combined ratio | 55% (non-life only) | 2025 |
| investments, net worth (H1/FY) | 100% | 2025 |

### What is reliably available

- **P&L history from 2018-2019** for banks and NBFCs: interest income and expense, NII, opex,
  provisions, PPOP and PAT.
- **Bank asset quality and capital from 2018**, except for 9 of 40 banks. BANKBARODA, BANKINDIA,
  FINOPB, HDFCBANK, IDFCFIRSTB, PNB, RBLBANK, SBIN and UNIONBANK file only their consolidated
  results, where these lines are 0.00 placeholders. The standalone filing (never downloaded: the
  collector keeps one statement type per period) has them.
- **Balance sheets only from Sep 2022.** Before that, lender XBRL has no balance sheet. So NIM,
  ROA, ROE, leverage, credit cost on loans and loan growth start in 2022-23, and their YoY changes
  start in 2023-24.
- **Insurers: 6 quarters.** YoY exists only for the last two quarters. Too short to evaluate.
- **Not available at all:** NBFC GNPA / Stage 3 and capital adequacy, bank total CRAR (only CET1
  and AT1), and a clean Tier 1.

## 2. Parser changes (`xbrl_parse.py`, plus one line in `store.py`)

- New tag maps: `FIN_FLOW_TAGS`, `FIN_RATIO_TAGS`, `FIN_POINT_TAGS` and `FIN_BALANCE_TAGS`, one per
  bank / nbfc / insurance format. The new top-level key `fin_sector` has this shape:
  `{format, quarter, ytd, balance_sheet, warnings}`. It is added only when the detected format is
  bank, nbfc or insurance, or when the caller passes `parse_xbrl(xml, fin_sector_format=...)`.
- Derived lines:
  - NII = interest earned - interest expended (NBFC: finance costs).
  - NBFC opex = total expenses - finance costs - impairment.
  - NBFC PPOP = profit before exceptional items and tax + impairment.
- Ratios are read as filed whatever their unit. ROA is often tagged `INR`, and the generic reader
  would have divided it by 1e7. Two cases are range-checked and become None:
  - Exact 0.00 values, which consolidated bank filings use as "not applicable".
  - Keying errors, e.g. CET1 of 0.0026 or 1.0.
- Insurer solvency filed as a percentage divided by 100 (0.0267 for 2.67x) is rescaled, with a
  block warning. The ranges can't overlap: plausible solvency is 0.5-10x.
- The block keeps its own `warnings` list, so the main `warnings` list is unchanged.
- Insurance only: P&L contexts are also found by insurer tags (`ProfitLossAfterTax`,
  `GrossPremiumsWritten`, ...). The existing income keys map `net_profit`, `profit_before_tax`,
  `tax` and EPS. This is the one change to existing keys. It applies only to `format = insurance`,
  where every filing failed before.
- `store.build_row` lists `fin_sector` as a known key. A future re-collection therefore neither
  stores it (there are no columns yet) nor logs it as "not stored".

### Regression proof

I compared the original parser (`git show HEAD:ml/financials/xbrl_parse.py`) with the new one on
**every cached file** (`ml/data/raw/xbrl/*/*.xml`), using the `json.dumps` of the output:

| detected format | files | byte-identical | identical without `fin_sector` | different |
|---|---|---|---|---|
| non_financial | 61,962 | **61,962** | - | 0 |
| bank | 1,567 | 332 (failed 2018 files) | 1,235 | 0 |
| nbfc | 3,248 | 0 | 3,248 | 0 |
| insurance | 62 | 0 | 0 | 62 (was a failed parse, now parses) |

`python3 -m financials.validate --samples` still reports 0 core-field mismatches on 1,815 checks.

### Spot checks (latest quarter, crore)

| | NII | Opex | Provisions | GNPA / NNPA | CET1 | Balance sheet (Mar 2026) |
|---|---|---|---|---|---|---|
| HDFCBANK (cons., Q1 FY27) | 42,950 | 54,489 | 3,803 | not filed in consolidated | not filed | advances 30.5L cr, deposits 31.0L cr |
| ICICIBANK (cons., Q1 FY27) | 29,177 | 34,021 | 1,297 | 1.38% / 0.38% | 16.1% | advances 16.4L cr, deposits 18.3L cr |
| UJJIVANSFB (std., Q1 FY27) | 1,187 | 895 | 127 | 2.16% / 0.34% | 19.2% | advances 39,761, deposits 45,668 |
| BAJFINANCE (cons., Q1 FY27) | 12,571 | 5,087 | 1,993 (ECL) | n/a | n/a | loans 4.99L cr |
| ARMANFIN (small NBFC) | 119 | 61 | 19.5 | n/a | n/a | loans 2,214 |
| ICICIGI (Q4 FY26) | GWP 8,074 | combined ratio 101.2% | claims ratio 70.8% | | solvency 2.67x | |
| SBILIFE (Q1 FY27) | GWP 21,290 | | | | solvency 1.96x | |

## 3. Features (`fin_sector_features.py`)

The point-in-time rules are the same as in features.py:

- One row per (company, period_end), stamped with the filing_date of that period's filing.
- Visible set: only filings with filing_date <= the row's filing_date are used.
- Consolidated is preferred over standalone, and each basis gets its own series.
- Quarters are derived from YTD blocks using the same grid, by subclassing `features._Company`.
- Missing values are NaN, never 0. Ratios are fractions and money is INR crore. Growth from a zero
  or negative base gives NaN plus a `*_neg_base` flag.
- One deviation: old single-context June filings with no start date are taken as Q1 (131 filings).

The module docstring has the full definitions. The features are:

| group | features |
|---|---|
| growth | `net_revenue_yoy`, `net_revenue_ttm_growth` (net revenue = total income - interest expended; insurers: net premium), `nii_yoy`, `nii_ttm_growth`, `ppop_yoy`, `ppop_ttm_growth`, `net_profit_yoy`, `net_profit_ttm_growth`, `net_profit_yoy_accel`, `eps_ttm_growth`, `advances_growth_1y`, `deposits_growth_1y` |
| profitability / efficiency | `nim` (NII TTM / avg total assets, a proxy), `cost_to_income_ttm`, `credit_cost` (provisions TTM / avg loans), `credit_cost_to_income_ttm`, `roa`, `roe`, `roa_reported` |
| capital / funding | `leverage` (assets / net worth), `cet1_ratio`, `cet1_change_1y`, `solvency_ratio`, `loan_to_deposit`, `loans_to_assets` (tells lending NBFCs from brokers, AMCs and holding companies) |
| asset quality (banks) | `gross_npa_pct`, `net_npa_pct`, `gross_npa_change_1y`, `net_npa_change_1y`, `provision_coverage` |
| insurers | `claims_ratio`, `combined_ratio` |
| size / staleness | `net_revenue_ttm`, `net_profit_ttm`, `total_assets`, `days_since_period_end`, `days_since_bs` |
| red flags | `flag_asset_quality_worsening` (GNPA +0.5 pt YoY, or provisions / net revenue +10 pts YoY), `flag_roa_collapse` (ROA, else PAT TTM, below half of a year ago), `flag_capital_near_minimum` (CET1 < 9%; solvency < 1.7x; NA for NBFCs), `flag_negative_equity`, `*_neg_base` |

The output has 4,210 rows for 193 companies, with period ends from 2018-03 to 2026-06.

Typical bank values (medians) are plausible:

| NIM | cost/income | credit cost | ROA | ROE | leverage | CET1 | GNPA | PCR |
|---|---|---|---|---|---|---|---|---|
| 3.2% | 56% | 0.8% | 1.1% | 12.4% | 10.3x | 14.2% | 3.5% | 70% |

**No look-ahead** is checked two ways:

- Every row asserts that its visible set holds no filing newer than itself.
- `--check N` recomputes N random rows from a history truncated at the row's filing_date and
  compares every feature: 300 rows, 0 mismatches.

## 4. Evaluation (`fin_sector_eval.py`)

**Method.**

- Signal dates are the 1st and 16th of each month, 2018-07 to 2026-09. Labels come from
  `growth_model/labels.py`: excess return vs NIFTY SMALLCAP 250, with entry the next trading day.
- Features are joined as-of: the latest period filed on or before the date, and dropped if the
  period ended more than 275 days earlier.
- Universe: companies in scope with at least 0.5 cr/day traded and at least 1 year listed.
- IC is Spearman per date, then averaged. Its sign is flipped so that **+ means the direction
  fixed in advance worked**.
- `blend_fixed` is an equal-weight percentile blend of 10 features with prior directions:
  - Growth: revenue TTM, PAT TTM and PPOP TTM growth.
  - ROA and ROE.
  - Cost/income and credit cost/income.
  - GNPA and GNPA change.
  - CET1.
- `blend_wf` is walk-forward. Each year it keeps the features whose IC on earlier, purged years
  was at least 0.02 in absolute value, with that sign.
- `trend6` is the market model's price-trend score, for scale.

### All financial-sector companies (165 companies, ~94 per date)

The bank-only features cover about 26 names.

| 6m | IC | years + | 2019 | 2020 | 2021 | 2022 | 2023 | 2024 | 2025 | 2026 |
|---|---|---|---|---|---|---|---|---|---|---|
| trend6 (price) | **+0.083** | 6/8 | .40 | -.12 | .07 | .05 | .03 | .07 | .11 | -.01 |
| blend_fixed | -0.039 | 4/8 | .40 | .11 | .04 | -.26 | -.24 | .08 | -.02 | -.12 |
| blend_wf | -0.069 | 2/7 | | .02 | .13 | -.12 | -.11 | -.19 | -.14 | -.09 |
| net_profit_yoy (best financial) | +0.059 | 5/7 | | .15 | .15 | .03 | .10 | -.01 | -.05 | .02 |

| 12m | IC | years + | 2019 | 2020 | 2021 | 2022 | 2023 | 2024 | 2025 |
|---|---|---|---|---|---|---|---|---|---|
| trend6 (price) | **+0.101** | 6/7 | .41 | -.03 | .06 | .02 | .05 | .06 | .14 |
| blend_fixed | -0.081 | 2/7 | -.02 | -.02 | .01 | -.25 | -.26 | .09 | -.05 |
| blend_wf | -0.134 | 0/5 | | | -.17 | -.16 | -.17 | -.12 | -.02 |
| credit_cost (lower better, 2022+) | +0.085 | 3/4 | | | | .00 | .21 | .14 | -.14 |
| provision_coverage (banks) | +0.070 | 4/7 | .32 | .08 | .06 | -.11 | .20 | -.04 | -.05 |

`blend_fixed` spread (top 20% minus bottom 20%, mean excess), 12m by year:
- 2019: -10%
- 2020: -8%
- 2021: -1%
- 2022: **-29%**
- 2023: **-40%**
- 2024: +3%
- 2025: -5%

`trend6` spread, 12m by year: +28%, -19%, +6%, +5%, +16%, +9% and +9%.

### Banks (40 companies, ~32 per date; financial features ~24-27 names)

| feature | 6m IC (yrs +) | 12m IC (yrs +) |
|---|---|---|
| trend6 | +0.096 (5/8) | +0.068 (4/7) |
| ppop_ttm_growth | +0.087 (5/7) | **+0.123 (4/6)** |
| net_profit_yoy | +0.075 (5/7) | +0.085 (5/6) |
| net_revenue_ttm_growth | +0.070 (3/7) | +0.070 (4/6) |
| roe (2023+ only) | +0.077 (2/4) | +0.147 (2/3) |
| provision_coverage | +0.048 (5/8) | +0.070 (4/7) |
| blend_fixed | +0.015 (5/8) | -0.049 (3/7) |
| gross_npa_pct (lower better) | -0.031 (3/8) | -0.082 (2/7) |
| cet1_ratio | -0.064 (4/8) | -0.149 (2/7) |
| nim | -0.074 (2/4) | -0.097 (1/3) |

For banks, **`flag_asset_quality_worsening` works**. About 7 of ~25 banks are flagged on a date, and
they trailed the unflagged banks by **-8.8% over 6m (worse in 4/5 years) and -12.3% over 12m (4/4
years)**. `flag_roa_collapse` shows -5.6% and -5.8% on few names. `flag_capital_near_minimum` is
mixed and only fires in 2019-2021.

### Lending NBFCs (loans / assets >= 0.5; 62 companies, ~40 per date, 2022-11 to 2026-09)

| feature | 6m IC (yrs +) | 12m IC (yrs +) |
|---|---|---|
| trend6 | **+0.129 (4/5)** | **+0.141 (3/4)** |
| cost_to_income_ttm (lower better) | +0.102 (3/5) | +0.148 (2/4) |
| credit_cost (lower better) | +0.063 (2/5) | +0.065 (1/4) |
| roa | -0.150 (0/5) | -0.131 (1/4) |
| net_revenue_ttm_growth | -0.169 (0/5) | -0.207 (0/4) |
| ppop_ttm_growth | -0.199 (0/5) | -0.218 (1/4) |
| blend_fixed | **-0.162 (0/5)** | **-0.181 (0/4)** |

For NBFCs, `flag_asset_quality_worsening` shows -0.2% (6m) and -15% (12m, driven by 2023). Over
the whole sector, `flag_roa_collapse` names *rebounded*: +3.8% (6m) and +14.5% (12m).

### Insurers

Insurers can't be evaluated. There are 6 quarters of data (from Apr 2025), and 6m / 12m labels for
those dates don't exist yet.

### Verdict

This is **only indicative, not usable as a predictive model**:

- **The sample is small.** About 25 banks or 40 NBFCs per date, 4-8 test years, and 24
  overlapping-window dates a year. A year is closer to one observation than to 24.
- **Results are regime-driven.**
  - The 2022-23 re-rating of state-owned banks rewarded exactly the banks with high NPAs, low CET1
    and low ROA. That is why quality levels have negative ICs, and why `blend_fixed` lost 29-40%
    (top vs bottom) in those two years.
  - Among NBFCs, the 2023-25 unsecured / microfinance stress de-rated the fastest-growing,
    highest-ROA lenders.
- **The walk-forward blend is worse than the fixed one.** Learning signs from past years chases the
  last regime.
- The only stable signals are price trend, and for banks, growth plus the asset-quality-worsening
  flag.

## 5. Recommendation for `rankings/build.py` (not implemented here)

1. **Source.** Use `fin_sector_features` rows for the 193 in-scope companies (column
   `company_format`) and `features.py` rows for everyone else. The staleness rule (275 days) is
   unchanged.
2. **Peer groups for percentiles.** Use four groups:
   - banks
   - lending NBFCs (`loans_to_assets >= 0.5`)
   - other NBFC-format filers (brokers, AMCs, holding companies)
   - insurers

   Compute percentiles within the group when it has at least 15 names on the snapshot date, and
   across all in-scope companies otherwise. Never percentile a bank's ROA against a software
   company's.
3. **Components.** These map onto the existing columns, with no schema change:

   | component | banks | NBFCs | insurers | min sub-features |
   |---|---|---|---|---|
   | growth | ppop_ttm_growth, net_profit_yoy, net_revenue_ttm_growth, net_profit_ttm_growth, nii_ttm_growth (x0.5) | net_revenue_ttm_growth, net_profit_ttm_growth, net_profit_yoy, ppop_ttm_growth | net_revenue_yoy (net premium), net_profit_yoy | 2 (insurers 1) |
   | profitability | roe, roa, cost_to_income (low), nim (x0.5) | cost_to_income (low), roe, roa (x0.5) | roe, combined_ratio (low) | 1 |
   | financial_health | gross_npa_pct (low), net_npa_pct (low), provision_coverage, credit_cost (low), cet1_ratio (x0.5) | credit_cost (low), credit_cost_to_income (low), leverage (low, x0.5) | solvency_ratio | 1 |
   | cash_flow | not applicable: NULL, and excluded from the coverage denominator | | | |
   | momentum, news | unchanged | | | |

4. **Weights** (fin-sector branch; momentum-led because it is the only consistent signal in this
   universe):

   | momentum | growth | profitability | financial_health | news |
   |---|---|---|---|---|
   | 0.50 | 0.15 | 0.15 | 0.15 | 0.05 |

   The financial components mainly make the reasons and risks honest. Revisit this after 2-3 more
   years of balance-sheet history.
5. **Penalties.**
   - `flag_asset_quality_worsening`: -4 (the flag with evidence, for banks).
   - `flag_capital_near_minimum`: -6 (regulatory risk; weak evidence).
   - `flag_negative_equity`: -6.
   - `flag_roa_collapse`: show it as a risk text line only, with no penalty. On average these
     names rebounded.
6. **Minimum coverage.** Coverage is computed over the applicable weight (cash flow excluded) and
   must be at least 0.6. The company also needs momentum plus a growth reading. At 2026-09-28,
   183 of the 193 in-scope companies have fresh financials with at least 2 growth readings. That
   includes 10 of the 11 insurers, via 2 YoY quarters.
7. **Suggested `key_metrics` for these companies.** `nim`, `cost_to_income_ttm`, `roa`, `roe`,
   `gross_npa_pct`, `net_npa_pct`, `cet1_ratio` or `solvency_ratio`, `advances_growth_1y`,
   `credit_cost`.
8. **Data fixes worth doing.**
   - Have the collector also download the **standalone** filing for bank-format companies. This
     restores NPA / CET1 for HDFCBANK, SBIN, PNB, BANKBARODA and 5 others.
   - Collect INDUSINDBK, which has no filings.
   - Backfill the `fin_sector` block into the DB (below).

## 6. Commands

```bash
cd ml
# Re-parse lender filings from the XBRL cache (SELECT-only DB read of listing metadata), build
# features, run the look-ahead check (~5 s)
caffeinate -i python3 -m financials.fin_sector_features --refresh-extract --check 300 \
    --out data/processed/fin_sector_features.csv
#   -> data/processed/fin_sector_filings.pkl (extract), fin_sector_features.csv
python3 -m financials.fin_sector_features --symbols HDFCBANK ICICIBANK BAJFINANCE --out /tmp/fin.csv

# Evaluation (~10 s; needs data/processed/growth_labels.pkl and growth_market_features.pkl)
python3 -m financials.fin_sector_eval                          # all financial-sector companies
python3 -m financials.fin_sector_eval --segment bank           # or lending_nbfc / nbfc

# Parser regression (old vs new on the whole cache)
git show HEAD:ml/financials/xbrl_parse.py > /tmp/xbrl_parse_orig.py
#   then for every data/raw/xbrl/*/*.xml compare json.dumps(old.parse_xbrl(x)) with the new output
#   (with the `fin_sector` key removed for bank/nbfc)
python3 -m financials.validate --samples
```

**DB backfill later.** This is not run: it writes to the live table.

1. Add `fs_*` columns for the `fin_sector` block to `store.py`: SECTIONS, DDL and an
   `ALTER TABLE financial_filings ADD COLUMN ...` migration.
2. Re-parse offline:
   `cd ml && caffeinate -i python3 -m financials.collect --from-cache data/raw/xbrl --all-in-cache --reparse`.

The re-parse leaves non-financial rows unchanged, adds the new lines to bank and NBFC rows, and
turns the 62 insurance rows from `failed` into `partial`. After that, `fin_sector_features` can
read the columns instead of the pickle extract.
