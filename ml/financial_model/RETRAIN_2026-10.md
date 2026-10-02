# Financial model retrain after the 2026-10-02 backfill

Date: 2026-10-02. Code: `ml/financial_model/retrain_eval.py` (variants, metrics and pass rule written
before any test was run). Raw output: `ml/data/processed/retrain_eval_2026-10.json`.
Reproduce from `ml/`:

```bash
caffeinate -i python3 -m financial_model.train --refresh --no-final      # one SELECT on financial_filings
caffeinate -i python3 -m financial_model.retrain_eval --old-features <pre-refresh financial_features.pkl> \
    --old-raw <pre-refresh financial_raw.pkl>
```

(`--no-final` was used so the live spec `ml/models/financial_model.json` was not rewritten; the winner
is `baseline` = fin-v1 again, so a final fit would write the same spec.)

**Verdict: keep fin-v1 unchanged. No candidate passed. The ROE fallback (F1) stays opt-in and off.
The bank recipe still loses to trend-only. No change to `build_v3.py`.**

## 1. What the refresh changed

`financial_filings` (non_financial, usable): 61,981 → 62,090 filings; feature rows 51,505 → 51,597;
model panel 186,320 → 186,519 rows (1,808 → 1,810 companies).

March filings with balance-sheet totals (share of filings):

| FY (Mar) | total assets old → new | total equity old → new | owners' equity (new) |
|---|---|---|---|
| 2018 | 0% → 5.7% | 0% → 15.8% | 45.7% |
| 2019 | 0% → 20.2% | 0% → 35.8% | 71.5% |
| 2020 | 0% → 29.0% | 0% → 18.2% | 73.8% |
| 2021 | 0.2% → 30.3% | 0.2% → 18.2% | 71.3% |
| 2022 | 0.3% → 30.2% | 0.3% → 18.4% | 71.8% |
| 2023-26 | 99% (unchanged) | 98-99% | 98-99% |

Feature coverage in the **model panel** (signal dates in the universe, share of rows non-null):

| signal year | ROE old | ROE new (F0) | ROE with fallback (F1) | accruals ratio old → new | negative-equity flag old → new | ROCE, D/E, current ratio |
|---|---|---|---|---|---|---|
| 2018 | 0% | 3.9% | 27.0% | 0 → 0 | 0 → 21.0% | 0 (unchanged) |
| 2019 | 0% | 16.8% | 44.8% | 0 → 0 | 0 → 20.8% | 0 |
| 2020 | 0% | 11.2% | 59.9% | 0 → 0 | 0 → 11.6% | 0 |
| 2021 | 0% | 12.8% | 72.5% | 0 → 20.8% | 0 → 13.3% | 0 |
| 2022 | 12.7% | 23.3% | 73.1% | 12.8 → 41.9% | 13.8 → 24.7% | 13-14% (unchanged) |
| 2023-26 | 94-96% | unchanged | unchanged (2023: 93.6 → 94.0%) | unchanged | unchanged | unchanged |

- ROE in fin-v1 needs **total** equity, which legacy rows only have for standalone filers; the
  owners'-equity fallback (F1) is what lifts 2019-2022 ROE coverage to 45-73%.
- "Equity growth" and "asset turnover" are not fin-v1 / features.py inputs, so there is no
  coverage to report for them; their inputs (owners' equity, total assets) are in the first table.
  Debt, current assets/liabilities and receivables are still NULL before Sep 2022, so ROCE, D/E,
  current ratio, D/E change and the receivables flag gained nothing.
- Growth and cash-flow features are unchanged (they never depended on the balance sheet).

## 2. ROE fallback: implementation and default-identity proof

`ml/financials/features.py`: new keyword `roe_owners_fallback=False` on `build_feature_table` /
`compute_features` (threaded to `_features`), helper `_roe_owners`, and `_load_raw` now also selects
`bs_equity_owners`. With the flag on, a row whose balance sheet has no total equity (or that has no
balance sheet) gets ROE = TTM profit attributable to owners (net profit if not filed) / owners'
equity of the latest visible statement within 4 quarters (never older than the latest balance
sheet), averaged with the owners' equity 4 (else 2) quarters earlier. Only visible (already filed)
records are used. `ml/financial_model/data.py`: `load_feature_table(..., roe_owners_fallback=False)`
(separate cache `financial_features_roe_owners.pkl`) and `build_panel(..., roe_owners_fallback=False,
features=None)`.

Proof (refreshed raw, 62,090 filings; original `features.py` copied before editing):

| comparison | `DataFrame.equals` | dtypes | pickle sha256 |
|---|---|---|---|
| new code default vs original code | True | same | identical (4a8e56fc…) |
| original code, raw without the new column | True | same | identical |
| new code default, raw without the new column | True | same | identical |
| refreshed `financial_features.pkl` (written by train.py with the new code) vs original code | True | same | identical file bytes |

With the flag on, only the `roe` column changes, on 8,583 rows, all of which were NaN by default
(median fallback ROE 10.7% vs 10.6% for the default rows; distribution sane).

## 3. Walk-forward results (train.py protocol, test years 2020-2026 for 6m, 2020-2025 for 12m)

Variants (pre-declared): **F0** = fin-v1 on the refreshed data (reference), **F1** = F0 + ROE
fallback, **F2** = data-selected blend on the refreshed data, **F3** = blend + ROE fallback;
F0_old / blend_old = the same on the pre-refresh cache, for reference. Combined = investiq-v1
0.7 × trend + 0.3 × financial on the rankable rows (combiner_eval Part A rows), years 2020+.

| variant | 6m fin IC | 6m spread | 6m yrs IC>0 | 12m fin IC | 12m spread | 12m yrs IC>0 | combined 6m IC | combined 12m IC | pass |
|---|---|---|---|---|---|---|---|---|---|
| F0_old (fin-v1, before) | 0.0394 | +2.8% | 6/7 | 0.0080 | −3.5% | 4/6 | 0.0653 | 0.0642 | ref |
| blend_old | 0.0347 | −0.5% | 5/7 | 0.0062 | −2.2% | 3/6 | 0.0623 | 0.0622 | ref |
| **F0 (fin-v1, refreshed)** | **0.0395** | **+3.0%** | **6/7** | **0.0084** | **−3.2%** | **4/6** | **0.0651** | **0.0644** | reference |
| F1 (ROE fallback) | 0.0377 | +3.0% | 6/7 | 0.0048 | −3.8% | 4/6 | 0.0645 | 0.0633 | **fail** |
| F2 (blend, longer history) | 0.0327 | −0.1% | 5/7 | 0.0073 | −1.9% | 3/6 | 0.0618 | 0.0632 | **fail** |
| F3 (blend + fallback) | 0.0330 | −0.0% | 5/7 | 0.0020 | −2.0% | 3/6 | 0.0618 | 0.0612 | **fail** |

(Combined 12m over 2021+ only, the combiner_eval convention behind the published 0.097: F0 0.0967,
F1 0.0956, F2 0.0968, F3 0.0944; F2's +0.0001 is noise and it fails the financial-only checks anyway.)

Why each failed (pre-declared rule: fin IC and spread higher on both horizons, no fewer positive
years, combined IC higher on both horizons):
- **F1**: lower on every check except 6m spread (tie, +2.96% vs +3.05%). The extra ROE only exists in
  2018-2022 rows; it changes 2020-2022 scores and those years got slightly worse (12m 2022 IC 0.031 →
  0.021). On 2023+ it is identical to F0.
- **F2/F3**: the blend again loses 2020-2021 badly (6m 2021 IC −0.059 vs +0.055; 12m 2020 −0.134 vs
  −0.105) and 2026 (6m 0.032 vs 0.075). It wins 2023 (IC 0.111 vs 0.026) and 2025, so its 2022+ mean
  is higher (6m 0.072 vs 0.057, 12m 0.062 vs 0.045), as in September, but the rule is all years.
  The longer history did **not** fix the early folds: growth features (which the blend selects on)
  still start in 2019, and the new balance-sheet totals don't add the features that failed (margins,
  quality). F2's numbers are within ~0.005 IC of blend_old's.

Per year, financial-only IC / top-minus-bottom decile spread:

| 6m | 2020 | 2021 | 2022 | 2023 | 2024 | 2025 | 2026 |
|---|---|---|---|---|---|---|---|
| F0_old | −.066 / −11.7% | .055 / +8.7% | .046 / +5.6% | .027 / −2.7% | .085 / +7.1% | .054 / +2.2% | .075 / +10.7% |
| F0 | −.063 / −11.8% | .055 / +9.7% | .044 / +5.6% | .026 / −2.7% | .086 / +7.3% | .054 / +2.2% | .075 / +10.9% |
| F1 | −.069 / −11.5% | .052 / +10.1% | .040 / +4.4% | .026 / −2.7% | .086 / +7.3% | .054 / +2.2% | .075 / +10.9% |
| F2 | −.071 / −15.6% | −.059 / −8.4% | .056 / +4.8% | .111 / +8.1% | .094 / +7.5% | .066 / +4.8% | .032 / −1.6% |
| F3 | −.073 / −17.2% | −.058 / −7.2% | .059 / +5.4% | .111 / +8.1% | .094 / +7.5% | .066 / +4.8% | .032 / −1.6% |

| 12m | 2020 | 2021 | 2022 | 2023 | 2024 | 2025 |
|---|---|---|---|---|---|---|
| F0_old | −.108 / −28.5% | −.022 / −1.1% | .032 / +6.4% | .002 / −11.5% | .094 / +8.4% | .050 / +5.2% |
| F0 | −.105 / −29.7% | −.024 / −0.6% | .031 / +8.1% | .002 / −11.1% | .096 / +8.7% | .050 / +5.3% |
| F1 | −.111 / −30.3% | −.030 / −1.5% | .021 / +6.6% | .002 / −11.3% | .096 / +8.7% | .050 / +5.3% |
| F2 | −.134 / −37.0% | −.069 / −5.5% | −.031 / −5.5% | .111 / +15.5% | .093 / +11.7% | .074 / +9.5% |
| F3 | −.134 / −38.0% | −.077 / −6.9% | −.055 / −3.7% | .111 / +15.5% | .093 / +11.7% | .074 / +9.5% |

Combined (0.7/0.3) per year IC: F0 6m −.067, .111, .081, .130, .070, .065, .065; 12m −.097, .071,
.078, .159, .085, .090. F1 is within ±0.003 of F0 in every year; F2 is lower in 2020-2021 and
higher in 2023 (full numbers in the JSON).

The refresh itself (F0 vs F0_old) moved fin-v1 by ≤ 0.0004 IC: the new legacy totals mostly affect
2018-2021 rows, where fin-v1's profitability component is dominated by margins, and the new
negative-equity flags (−6 points) fire on 1.2% of pre-2022 feature rows (6.4% of those where
equity is known).

## 4. Combiner weight (combiner_eval Part A, re-run on the refreshed data)

Best financial variant = F0, so the weight test was re-run on F0 (nothing to re-run for a candidate).

| | w=0 | .5 | .6 | .65 | .7 | .75 | .8 | 1.0 |
|---|---|---|---|---|---|---|---|---|
| objective (avg 6m/12m), refreshed | .0022 | .0330 | .0374 | .0391 | .0403 | .0413 | .0422 | **.0430** |
| same on 30 Sep data | .0019 | .0327 | .0371 | .0388 | .0401 | .0411 | .0420 | .0429 |

Walk-forward choice by year: 6m 1.0, 0.0, 1.0, 1.0, 1.0, 0.8, 0.7; 12m 0.6, 1.0, 1.0, 1.0, 1.0 (identical
to September). Out of sample: walk-forward combiner 6m IC 0.058 / 12m 0.095; fixed 0.7 0.065 / 0.097;
trend only 0.061 / 0.102.

**Does w stay 0.7?** The combiner rule picks **w = 1.0, exactly as it did on 30 Sep** (V3_COMPARISON.md:
0.7 was a deliberate choice over the rule's 1.0). The new data changed the objective by ≤ 0.0003 and
did not change the ordering, so there is no new evidence either way: 0.7 remains a judgment call
(it is the best of the grid on 6m, trend-only is best on 12m).

## 5. Banks (combiner_eval Part B and fin_sector_eval, refreshed fin_sector extract)

Bank coverage in the eligible fin-sector panel: 41 banks (INDUSINDBK now in), median 24 per date;
gross NPA % 73% → 97% of bank rows, net NPA 75% → 98%, CET1 83% → 97%, provision coverage 75% → 99%.
"Before" is the refreshed extract minus INDUSINDBK and minus bank standalone filings for periods
that also have a consolidated filing (an approximation: the old file was overwritten).

Recipe (momentum .50 + growth/profitability/health .15 each, lender penalties) vs trend only, mean
yearly IC / top-minus-bottom quintile spread:

| scope | h | recipe before → after | trend before → after | trend + penalties after | recipe adopted? |
|---|---|---|---|---|---|
| all fin sector | 6m | −0.017 / −2.3% → −0.019 / −2.2% | +0.014 / +1.8% → +0.011 / +1.1% | +0.010 / +1.4% | no |
| all fin sector | 12m | −0.000 / −5.6% → −0.002 / −6.0% | +0.050 / +5.8% → +0.044 / +3.9% | +0.046 / +4.6% | no |
| banks only | 6m | +0.048 / −0.5% → +0.055 / +0.3% | +0.076 / +4.5% → +0.073 / +4.3% | +0.075 / +4.4% | no |
| banks only | 12m | +0.025 / −4.8% → +0.039 / −3.6% | +0.080 / +7.5% → +0.101 / +9.3% | +0.108 / +9.9% | no |

**The bank recipe still does not beat trend-only** (it improved by 0.007-0.014 IC with complete
NPA/CET1, but trails trend by 0.02-0.06 IC and 4-13 points of spread). Trend + penalties is the
best bank score on both horizons, which is what build_v3 already does.

Per-feature ICs for banks (fin_sector_eval, signed so + = the textbook direction worked), after:
- **NPA change works**: net NPA 1-year change 6m +0.065 (5/7 years), 12m +0.168 (5/6); gross NPA
  change 12m +0.122 (4/6). Before the backfill these were −0.02 / +0.03, i.e. the complete data
  turned the asset-quality-trend signal from noise into the strongest bank feature. Provision
  coverage +0.071 / +0.077 (6/7 years at 12m).
- **Levels don't**: CET1 level −0.07 / −0.17 (well-capitalised banks did worse: the 2022-23 PSU
  re-rating), gross NPA level −0.03 / −0.10. So the recipe's health component (levels + CET1) is
  the wrong shape.
- This supports the existing −4 "asset quality worsening" penalty (it is the change signal) and
  is a lead for a future pre-declared test (an NPA-change-only health component), not a change now.

## 6. Verdict and exact change

- **fin-v1 stays as is** (F0). F1, F2 and F3 each fail the pre-declared rule on both horizons.
- **ROE fallback**: keep the opt-in flag, default off. Note it would barely touch live scores
  anyway: the live date only uses filings from the last 275 days, 98-99% of which have total equity.
- **build_v3.py: no change.** The live financial score already reads `financial_filings` at build
  time, so the backfilled rows are picked up automatically (they are pre-Sep-2022 rows, older than
  the 275-day freshness window, so current scores are unaffected). `MARKET_WEIGHT` stays 0.7 (the rule still prefers 1.0, as before). Banks stay
  trend-led with the lender penalties.
- Local caches are refreshed (`financial_raw.pkl` now carries `bs_equity_owners`;
  `financial_features.pkl` is byte-identical to what the old code produces on the new data).
- Caveats as always: survivorship bias, overlapping windows, 6-7 test years; the bank "before" is
  approximate.
