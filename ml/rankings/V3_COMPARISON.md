# investiq-v1 (InvestIQ combiner) vs prelim-v2

Date: 2026-09-30. **Dry run only.** Nothing was written to `company_rankings` or any other table;
the database was read with SELECT only.

Code:
- `ml/rankings/combiner_eval.py`: the walk-forward test. Run it with
  `caffeinate -i python3 -m rankings.combiner_eval` (about 30 s). It writes
  `ml/data/processed/combiner_walkforward.json`.
- `ml/rankings/build_v3.py`: the new model version. It reuses build.py's loaders, `score`,
  `explain`, `key_metrics`, labels, ranks and `write`.

`rankings/build.py` (prelim-v2) is **unchanged** and still builds with `python3 -m rankings.build`.

Dry-run files (snapshot 2026-09-30):
- `ml/data/processed/rankings_investiq_v1_2026-09-30.csv`: one row per company. It has every
  table column, plus `market_score`, `financial_score`, `penalty`, `is_fin_sector` and
  `peer_group`.
- `ml/data/processed/rankings_investiq_v1_2026-09-30.json`: counts, labels, weights and the
  method text.
- `ml/data/processed/rankings_prelim_v2_2026-09-30.csv`: prelim-v2 recomputed from the **same
  inputs**, so the comparison below is like-for-like.

## 1. The rule and the result

The score is a blend of two models:
`growth_score = 0.95 x [w x market + (1-w) x financial] + 0.05 x news - penalties`

The two models are:
- **market**: trend6 from the market model.
- **financial**: fin-v1, which is prelim-v2's financial blend, including its flag penalties.

The weight `w` is chosen from the grid {0, .5, .6, .65, .7, .75, .8, 1}. The grid and the rule
were written into `combiner_eval.py` before the first run.

The rule is `choose_w`. It picks the `w` with the highest mean(yearly IC) - 0.5 x std(yearly IC),
using the training years of each fold only:
- The window is expanding and purged (190 days for 6m, 375 days for 12m), the same as
  market_model and financial_model.
- Ties go to the larger `w`.
- The live weight is the same rule applied to all labelled years, averaged over 6m and 12m.

**Result: w = 1.0, so the financial model gets no weight in the score.**

| objective on all labelled years | w=0 | .5 | .6 | .65 | .7 | .75 | .8 | **1.0** |
|---|---|---|---|---|---|---|---|---|
| 6m | .023 | .044 | .046 | .047 | **.047** | .047 | .046 | .044 |
| 12m | -.019 | .021 | .028 | .031 | .034 | .036 | .038 | **.042** |
| average | .002 | .033 | .037 | .039 | .040 | .041 | .042 | **.043** |

The 6m horizon alone would pick about 0.7, and the 12m horizon picks 1.0. Between 0.7 and 1.0
the differences are within noise.

Out of sample, the financial blend did not add reliable ranking power on top of price trend.
The per-fold choices were:
- 6m: 1.0, 0.0, 1.0, 1.0, 1.0, 0.8, 0.7
- 12m: 0.6, 1.0, 1.0, 1.0, 1.0

The 2021 6m fold had only one year of training data and chose 0.0. That is why the walk-forward
rule scores slightly below trend6 alone.

Financial statements still do three jobs:
- **Eligibility.** A company needs a fresh growth reading to be ranked.
- **Penalties.** Only where the evidence supports them (section 1c).
- **Text.** They supply the reasons and risks.

If you want a minority financial weight anyway, set `MARKET_WEIGHT = 0.7` in `build_v3.py`
(one line). By the tables below, that costs about 0.005 IC at 12m and gains about 0.004 IC at 6m.

### 1a. Walk-forward, non-financial companies

The universe is liquid companies (>= 0.5 cr/day traded, >= 1 year listed) with fresh financials
and a growth reading: 158,426 rows, 1,718 companies. There are 5-7 test years.

Each cell is IC / top-decile minus bottom-decile excess return / top-decile beat rate.

**6m**

| method | 2020 | 2021 | 2022 | 2023 | 2024 | 2025 | 2026 |
|---|---|---|---|---|---|---|---|
| chosen rule (walk-forward w) | -.051 / +0% / 48% | .058 / +9% / 54% | .079 / +7% / 48% | .145 / +20% / 54% | .046 / +6% / 42% | .062 / +6% / 41% | .065 / +10% / 51% |
| trend6 alone (w=1, **live**) | -.051 / +0% / 48% | .106 / +16% / 54% | .079 / +7% / 48% | .145 / +20% / 54% | .046 / +6% / 42% | .055 / +5% / 41% | .050 / +10% / 45% |
| financial alone (w=0) | -.076 / -10% / 37% | .058 / +9% / 54% | .048 / +6% / 44% | .027 / -4% / 41% | .088 / +7% / 47% | .056 / +3% / 38% | .077 / +10% / 45% |
| prelim-v2 weights | -.080 / -11% / 39% | .084 / +11% / 56% | .064 / +6% / 45% | .061 / +3% / 44% | .090 / +7% / 46% | .064 / +4% / 39% | .079 / +11% / 48% |
| fixed w = 0.7 (reference) | -.068 / -3% / 45% | .111 / +13% / 55% | .082 / +8% / 46% | .131 / +16% / 52% | .070 / +7% / 43% | .066 / +6% / 41% | .065 / +10% / 51% |

**12m**

| method | 2021 | 2022 | 2023 | 2024 | 2025 |
|---|---|---|---|---|---|
| chosen rule (walk-forward w) | .060 / +12% / 50% | .080 / +14% / 46% | .189 / +42% / 56% | .060 / +7% / 40% | .087 / +9% / 39% |
| trend6 alone (w=1, **live**) | .093 / +25% / 53% | .080 / +14% / 46% | .189 / +42% / 56% | .060 / +7% / 40% | .087 / +9% / 39% |
| financial alone (w=0) | -.022 / -1% / 48% | .034 / +6% / 41% | .001 / -13% / 41% | .098 / +8% / 47% | .052 / +6% / 36% |
| prelim-v2 weights | .010 / +8% / 50% | .053 / +9% / 42% | .048 / +4% / 44% | .102 / +9% / 46% | .070 / +8% / 37% |
| fixed w = 0.7 (reference) | .071 / +16% / 51% | .078 / +14% / 45% | .159 / +33% / 53% | .085 / +7% / 42% | .090 / +10% / 39% |

**Summary (means of the yearly values)**

| | 6m IC | 6m spread | 6m top10 beat | 6m top10 − avg | 12m IC | 12m spread | 12m top10 beat | 12m top10 − avg | yrs top10 > avg (6m / 12m) |
|---|---|---|---|---|---|---|---|---|---|
| chosen rule (walk-forward) | .058 | +8.1% | 48.3% | +5.4% | .095 | +16.8% | 46.1% | +7.3% | 7/7, 5/5 |
| **trend6 alone (live w)** | .061 | +9.1% | 47.4% | +5.3% | **.102** | **+19.3%** | 46.7% | **+8.1%** | 7/7, 5/5 |
| financial alone | .040 | +3.1% | 43.6% | +0.7% | .033 | +1.1% | 42.4% | -0.2% | 4/7, 2/5 |
| prelim-v2 weights | .052 | +4.5% | 45.2% | +1.8% | .057 | +7.9% | 43.9% | +2.9% | 5/7, 4/5 |
| w = 0.7 | .065 | +8.1% | 47.7% | +4.5% | .097 | +16.0% | 45.8% | +6.4% | 7/7, 5/5 |

prelim-v2's 80% financial weighting has half the 12m IC of trend6, and less than half its
top-decile excess return.

Caveats:
- **Survivorship.** Prices exist only for companies listed today.
- **Overlapping windows.** The label windows overlap, so each year is closer to one observation
  than to 24 dates.
- **Signal choice.** The six trend signals were chosen after looking at 2018-2026 single-signal
  results (see market_model).

### 1b. News

`news` has company-mapped, sentiment-scored rows only since **2026-08**: 299 in August and 16,159
in September. That leaves no labelled history, so news **cannot be backtested**. It keeps a
**fixed weight of 0.05**, as in prelim-v2, and is centred on 50, so a company with no news loses
nothing.

### 1c. Red-flag penalties

The test was flagged minus unflagged mean excess return on the same date, per year. The pre-declared
rule keeps a penalty only if that gap is negative in at least 2/3 of years **on both horizons**.

| features.py flag | 6m gap (years negative) | 12m gap (years negative) | penalty in investiq-v1 |
|---|---|---|---|
| negative equity | -3.5% (4/5) | -2.2% (3/4) | **-6 points** |
| profit up, OCF negative | +3.9% (2/6) | +3.2% (3/5) | risk text only |
| receivables outpacing revenue | +2.1% (1/4) | -1.5% (2/3) | risk text only |
| debt/equity rising | +4.7% (2/4) | +5.1% (1/3) | risk text only |
| low interest coverage | +3.3% (3/7) | +7.4% (2/6) | risk text only |

prelim-v2's -3 penalties for the last four flags pointed the wrong way on average. Those flags
still appear first in the risks list.

## 2. Banks, NBFCs and insurers

I tested the FIN_SECTOR_REPORT recipe as specified:
- **Peer-group percentiles.** Banks, lending NBFCs, other NBFC-format companies and NBFCs without
  a balance sheet yet (pre-2022) are separate groups. A group with fewer than 15 names is pooled
  with the rest.
- **Weights.** Momentum .50, growth .15, profitability .15 and health .15.
- **Penalties.** Asset-quality worsening -4, capital near minimum -6, negative equity -6.
- **Eligibility.** Coverage >= 0.6, plus momentum and a growth reading.

It was compared with the market percentile alone on the same eligible rows: 12,129 rows,
159 companies, about 75 names per date.

| | 6m IC | 6m Q1−Q5 spread | yrs IC>0 | 12m IC | 12m spread | yrs IC>0 |
|---|---|---|---|---|---|---|
| recipe | -0.018 | -2.3% | 3/7 | -0.001 | -5.6% | 3/6 |
| trend alone | +0.014 | +1.8% | 5/7 | +0.050 | +5.6% | 4/6 |
| **trend + recipe penalties** | +0.014 | +2.2% | 5/7 | **+0.053** | **+6.2%** | **5/6** |

The recipe is worse than trend alone, so under the pre-declared rule (`adopt_fin_recipe`) it is
**not adopted**. Financial-sector companies are scored like everyone else:
0.95 x momentum + 0.05 x news, minus the recipe's penalties. The penalties are kept because they
improved trend slightly, most in 12m 2020.

Their bank, NBFC and insurer features are used for display and text:
- the peer-group component scores (growth, profitability, financial_health; cash_flow is NULL)
- reasons and risks: PPOP / profit / NII growth, ROE / ROA versus their peer group,
  cost-to-income, gross / net NPA, provision coverage, credit cost, CET1, solvency, combined
  ratio, the red flags, and ROA collapse as text only
- key_metrics: nim, cost_to_income_ttm, roa, roe, gross_npa_pct, net_npa_pct, cet1_ratio,
  solvency_ratio, advances_growth_1y and credit_cost

For these companies, `revenue_*` in key_metrics means net revenue.

The trend IC here (+0.01 / +0.05) is lower than in FIN_SECTOR_REPORT (+0.08 / +0.10). This
universe is smaller: only names that pass the recipe's eligibility, visibility at midnight on D
as in build.py, and no 2019 rows. The comparison between the rows of the table is the fair part.

## 3. Snapshot comparison (2026-09-30, same inputs)

The live DB snapshot (2026-09-28, prelim-v2) ranks only 648 of 2,525 companies. It was built
before much of the financial download landed. prelim-v2 recomputed today ranks 1,866, so the
comparison below uses that.

### Coverage (ranked companies)

| sector | companies | prelim-v2 | investiq-v1 |
|---|---|---|---|
| Industrials & Infrastructure | 627 | 513 | 512 |
| Metals, Mining & Chemicals | 315 | 252 | 250 |
| Consumer & FMCG | 281 | 226 | 225 |
| Services & Others | 268 | 193 | 204 |
| **Financial Services** | 243 | **22** | **170** |
| Technology | 221 | 181 | 182 |
| Healthcare & Pharmaceuticals | 177 | 146 | 146 |
| Automobile & Mobility | 141 | 118 | 117 |
| Energy | 128 | 106 | 106 |
| Real Estate & Construction | 95 | 84 | 83 |
| (no sector) | 29 | 25 | 25 |
| **total** | 2,525 | **1,866** | **2,020** |

Changes:
- **164 newly ranked lender-format companies:** 38 banks, 53 lending NBFCs, 62 other
  NBFC-format companies and 11 pooled (including insurers).
- **29 in-scope companies still unranked,** all because they have no fresh growth reading.
- **9 companies lose their rank** because they have no momentum score (a price-series break):
  ALLCARGO, CLCIND, DSKULKARNI, INDIAGLYCO, KALYANI, SADHNANIQ, TDPOWERSYS, UEL and VEDL. Their
  risks say so.

Of the 505 still unranked:
- 496 have no growth reading
- 303 have no momentum
- 294 have neither

### Labels

| | Strong | Positive | Neutral | Weak | Insufficient data |
|---|---|---|---|---|---|
| prelim-v2 | 84 | 429 | 761 | 592 | 659 |
| investiq-v1 | 465 | 318 | 417 | 820 | 505 |

The score is now essentially a percentile, whereas prelim-v2 averaged six percentiles, which
squeezed scores toward 50. As a result investiq-v1 uses the whole 0-100 range: about 23% Strong
and 41% Weak among ranked companies.

The thresholds are unchanged, as the contract requires. If this looks too many "Strong" for the
UI, the fix is a label decision, not a model decision.

### Rank agreement

- Spearman correlation of growth_score on the 1,857 companies ranked by both: **0.60**.
- Overlap of the two top-100 lists: **23**.
- investiq-v1 versus prelim-v2's own momentum component: 0.999, as expected.

### Top 20

| # | prelim-v2 | investiq-v1 (old rank) |
|---|---|---|
| 1 | INDOBORAX | SHREEJISPG (114) |
| 2 | OFSS | WELCORP (63) |
| 3 | VENUSREM | SHILPAMED (110) |
| 4 | APCOTEXIND | OPTIEMUS (606) |
| 5 | KIRIINDUS | GANDHAR (10) |
| 6 | SJS | INDSWFTLAB (466) |
| 7 | GLENMARK | FILATEX (509) |
| 8 | SIL | KABRAEXTRU (1249) |
| 9 | ANTELOPUS | SPECTRUM (81) |
| 10 | GANDHAR | NRL (113) |
| 11 | AEGISLOG | SSWL (398) |
| 12 | ARROWGREEN | BODALCHEM (244) |
| 13 | SOTL | IRISDOREME (247) |
| 14 | RPEL | TFCILTD (unranked: NBFC) |
| 15 | SIGMA | INDORAMA (1078) |
| 16 | NAVINFLUOR | CYIENTDLM (318) |
| 17 | DIVISLAB | SIGMAADV (719) |
| 18 | ENRIN | MOREPENLAB (211) |
| 19 | ADOR | STLTECH (109) |
| 20 | CUPID | OAL (1147) |

prelim-v2's top 20 now rank between 5 and 1,024. For example:
- GANDHAR: 5
- ANTELOPUS: 43
- SIGMA: 919
- ENRIN: 1,024

The new top 20 are all strong-trend names:
- median 6-month return +185%
- median traded value about Rs 48 cr/day
- 5% of the top 100 trade below Rs 0.5 cr/day, against 24% of all ranked companies

Every thinly traded company now gets a "Thinly traded" risk line, because it is outside the
backtested universe.

### Biggest movers (among companies ranked by both)

Up:

| company | prelim-v2 score (rank) | investiq-v1 score (rank) | reasons / risks |
|---|---|---|---|
| RAYMOND | 22.5 (1,701) | 94.5 (55) | price trend better than 95% of stocks, +236% in 6m / receivables outpacing revenue, operating profit doesn't cover interest (**check the price series: the jump may be a corporate action**) |
| BAFNAPH | 33.8 (1,466) | 96.1 (25) | +219% in 6m / net profit -98% YoY, revenue -23% YoY |
| OILCOUNTUB | 29.8 (1,555) | 89.1 (155) | +88% in 6m / operating profit doesn't cover interest, ROCE -32% |
| MAXESTATES | 29.5 (1,561) | 93.5 (74) | trend better than 94% of stocks, 41% operating margin / interest coverage 1.3x, FCF -Rs 697 cr |
| TI | 31.2 (1,522) | 85.4 (250) | revenue +161% YoY / debt/equity 0.0 → 0.8, receivables +142 pts |

Down:

| company | prelim-v2 score (rank) | investiq-v1 score (rank) | reasons / risks |
|---|---|---|---|
| HINDCOPPER | 79.6 (29) | 30.4 (1,274) | ROCE 44%, ROE 38% / momentum only 32nd percentile |
| JSLL | 69.1 (215) | 7.9 (1,725) | ROE 58%, ROCE 71% / trend weaker than 92% of stocks, -15% in 6m |
| EUROPRATIK | 68.5 (231) | 9.7 (1,688) | ROCE 36% / trend weaker than 92% of stocks |
| GUJENERGY | 61.3 (469) | 4.4 (1,797) | revenue +140% YoY / trend weaker than 98% of stocks |
| BDL | 68.0 (243) | 18.3 (1,521) | revenue +131% YoY / trend weaker than 81%, TTM revenue -19% |

The pattern is the point of the change:
- **Up:** companies with weak or even deteriorating financials but a strong price trend. The
  flags now show as risks, not as score deductions.
- **Down:** fundamentally strong companies whose price trend is weak.

Users will see "Strong" on a company whose own risks list flags poor financials. The reasons and
risks make that explicit, but it is a real UX consideration.

## 4. /rankings/meta method text

The `method` paragraph is **not** read from the table or from build.py. It is a hard-coded
`METHOD` constant in `backend/controllers/rankingController.js` (lines 26-36; it still describes
prelim-v1). I did not touch backend/.

The new text is `rankings/build_v3.py: METHOD_TEXT`, also saved in the dry-run .json. To show it,
the backend needs a small change, for example:

```js
const METHODS = { "investiq-v1": "<METHOD_TEXT from ml/rankings/build_v3.py>", "prelim-v2": METHOD };
// in getRankingsMeta:
method: METHODS[latest?.model_version] || METHOD,
```

## 5. Publishing later (needs your approval)

```bash
cd /Users/amit/InvestIQ/ml
caffeinate -i python3 -m rankings.build_v3 --date 2026-09-30 --publish
```

Before running it:
- **It replaces every row of that snapshot date** (`build.write` deletes by date, whatever the
  model_version).
- **Run it on this Mac.** The bank / NBFC / insurer lines come from
  `ml/data/processed/fin_sector_filings.pkl`, which is built from the local XBRL cache and is
  gitignored. On GitHub Actions those 193 companies would stay unranked (with a warning) until
  the `fin_sector` block is backfilled into `financial_filings` (FIN_SECTOR_REPORT section 6).
- **The scheduled workflow will overwrite it.** `.github/workflows/rankings.yml` still runs
  prelim-v2 (`python -m rankings.build`) on the 1st and 16th. The next run is 2026-10-01 08:00
  IST, and it creates a newer prelim-v2 snapshot that becomes "latest". To switch for good,
  change the step to `python -m rankings.build_v3 --publish` after the backfill. Alternatively,
  publish with the same `--date` as the workflow run, after it has finished.
- **Score history will mix versions.** `score_history` on the company page and the snapshot list
  in /rankings/meta will then mix prelim-v2 and investiq-v1 snapshots, and scores are not
  comparable across them.
- **Update the docs.** Update PROJECT_HANDBOOK section 8 and docs/company-rankings.md (they
  mention `prelim-v1` / `prelim-v2`).

## 6. Things noticed, not changed

- build.py `explain` prints "Trading within -0% of its 52-week high" when a stock closes exactly
  at its high (`max(-d * 100, 0)` gives -0.0). investiq-v1 rewrites that line as "Trading at its
  52-week high". prelim-v2 is left as is.
- Growth from a tiny base produces lines like "PPOP up 17290%" (VIJIFIN). These are factual but
  noisy, and prelim-v2 has the same behaviour ("Net profit up 1870%").
- The series-break rule (+100% / -60% in one day) does not catch every corporate action.
  RAYMOND's +236% in 6 months is worth checking, because investiq-v1 relies more on price than
  prelim-v2 did.
