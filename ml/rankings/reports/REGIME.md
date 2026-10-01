# Market-regime switch: walk-forward and time-machine test

Generated 2026-10-01 by `python3 -m rankings.regime_eval` (rules: `ml/rankings/regime.py`, pre-declared; evaluation logic: combiner_eval Part A).

**Verdict: no rule passed the pre-declared criteria; keep investiq-v1 (MARKET_WEIGHT 0.7 always)**

## 1. Pre-declared rules and alternatives

| rule | definition | risk dates 2017-2026 | trigger dates |
|---|---|---|---|
| `dd25` | Smallcap 250 >= 25% below its 52-week high | 23 | 2018-07-16 (1), 2018-10-01..2019-03-01 (11), 2019-08-01..2019-09-01 (3), 2020-03-16..2020-06-16 (7), 2025-03-01 (1) |
| `dd20` | Smallcap 250 >= 20% below its 52-week high | 37 | 2018-07-01..2018-08-16 (4), 2018-09-16..2019-03-16 (13), 2019-05-01..2019-05-16 (2), 2019-08-01..2019-09-16 (4), 2020-03-16..2020-07-16 (9), 2022-06-16..2022-07-01 (2), 2025-02-16..2025-03-16 (3) |
| `breadth15` | < 15% of stocks above their 200-day average | 13 | 2018-10-01 (1), 2018-11-01 (1), 2019-02-01..2019-02-16 (2), 2020-03-16..2020-05-16 (5), 2025-03-01..2025-03-16 (2), 2026-03-16..2026-04-01 (2) |
| `breadth20` | < 20% of stocks above their 200-day average | 30 | 2018-07-01..2018-07-16 (2), 2018-10-01..2018-12-16 (6), 2019-02-01..2019-03-01 (3), 2019-05-16 (1), 2019-08-01..2019-09-01 (3), 2020-03-16..2020-06-01 (6), 2025-02-16..2025-05-01 (6), 2026-02-01 (1), 2026-03-16..2026-04-01 (2) |
| `ret3m_m20` | Smallcap 250 down >= 20% in 3 months | 7 | 2020-04-01..2020-06-01 (5), 2025-03-01..2025-03-16 (2) |
| `stress` | Smallcap 250 down >= 15% in 3 months with >= 30% annualised volatility | 5 | 2020-04-01..2020-06-01 (5) |
| `bear12` | Smallcap 250 down >= 20% over 12 months (bear state) | 23 | 2018-11-01..2019-03-01 (9), 2019-05-01..2019-05-16 (2), 2019-08-01..2019-10-01 (5), 2020-03-16..2020-06-16 (7) |
| `dd25_or_b15` | dd25 or breadth15 | 26 | 2018-07-16 (1), 2018-10-01..2019-03-01 (11), 2019-08-01..2019-09-01 (3), 2020-03-16..2020-06-16 (7), 2025-03-01..2025-03-16 (2), 2026-03-16..2026-04-01 (2) |
| `dd25_and_vol30` | dd25 and >= 30% annualised volatility (panic, not a slow grind) | 6 | 2020-04-01..2020-06-16 (6) |
| `dd25_exit_b50` | enter at dd25; stay until breadth >= 50% | 55 | 2018-07-16..2020-01-01 (36), 2020-03-16..2020-08-01 (10), 2025-03-01..2025-07-01 (9) |
| `b15_exit_b50` | enter at breadth < 15%; stay until breadth >= 50% | 60 | 2018-10-01..2020-01-01 (31), 2020-03-16..2020-08-01 (10), 2025-03-01..2025-07-01 (9), 2026-03-16..2026-08-01 (10) |
| `stress_exit_ma200` | enter at stress; stay until Smallcap 250 is back above its 200-day average | 9 | 2020-04-01..2020-08-01 (9) |

Risk-regime alternatives (normal regime: market .7, financial .3): `w0.5` = market 0.5, financial 0.5; `w0.3` = market 0.3, financial 0.7; `w0.0` = market 0.0, financial 1.0; `w0.3_lowvol` = market 0.3, financial 0.4, lowvol 0.3; `w0.3_reversal` = market 0.3, financial 0.4, reversal 0.3
Primary hypothesis (fixed before testing): `dd25_exit_b50|w0.3`.

## 2. Does a risk state reverse trend? (market-model universe from 2017, trend6 only)

Mean per-date IC of trend6 on each rule's risk dates, by episode (number of dates), vs its normal dates; last two columns: IC of the reversal and low-volatility tilts on all risk dates. This uses no financial data, so it covers the 2018-19 bear that the walk-forward panel (financials from 2019-05) cannot see.

**6m**

| rule | 2018-19 | 2020 | 2022 | 2025-26 | all risk dates | normal dates | reversal (risk) | lowvol (risk) |
|---|---|---|---|---|---|---|---|---|
| `dd25` | +0.215 (15) | -0.147 (7) | — | -0.081 (1) | +0.092 | +0.106 | -0.031 | +0.082 |
| `dd20` | +0.232 (23) | -0.156 (9) | +0.061 (2) | -0.097 (3) | +0.102 | +0.105 | -0.012 | +0.125 |
| `breadth15` | +0.219 (4) | -0.108 (5) | — | -0.082 (3) | +0.007 | +0.110 | +0.037 | -0.028 |
| `breadth20` | +0.197 (15) | -0.127 (6) | — | -0.050 (8) | +0.062 | +0.111 | -0.022 | +0.069 |
| `ret3m_m20` | — | -0.125 (5) | — | -0.131 (2) | -0.126 | +0.112 | +0.105 | -0.115 |
| `stress` | — | -0.125 (5) | — | — | -0.125 | +0.110 | +0.094 | -0.156 |
| `bear12` | +0.264 (16) | -0.147 (7) | — | — | +0.139 | +0.101 | -0.037 | +0.126 |
| `dd25_or_b15` | +0.215 (15) | -0.147 (7) | — | -0.082 (3) | +0.078 | +0.108 | -0.022 | +0.068 |
| `dd25_and_vol30` | — | -0.148 (6) | — | — | -0.148 | +0.112 | +0.073 | -0.153 |
| `dd25_exit_b50` | +0.244 (35) | -0.134 (11) | — | +0.034 (9) | +0.134 | +0.095 | -0.017 | +0.170 |
| `b15_exit_b50` | +0.249 (30) | -0.134 (11) | — | +0.032 (10) | +0.124 | +0.099 | -0.015 | +0.151 |
| `stress_exit_ma200` | — | -0.171 (9) | — | — | -0.171 | +0.116 | +0.059 | -0.118 |

**12m**

| rule | 2018-19 | 2020 | 2022 | 2025-26 | all risk dates | normal dates | reversal (risk) | lowvol (risk) |
|---|---|---|---|---|---|---|---|---|
| `dd25` | +0.264 (15) | -0.254 (7) | — | +0.066 (1) | +0.098 | +0.110 | -0.068 | +0.126 |
| `dd20` | +0.268 (23) | -0.218 (9) | +0.073 (2) | +0.051 (3) | +0.122 | +0.105 | -0.069 | +0.162 |
| `breadth15` | +0.298 (4) | -0.257 (5) | — | +0.059 (2) | +0.002 | +0.114 | -0.007 | +0.040 |
| `breadth20` | +0.255 (15) | -0.264 (6) | — | +0.060 (6) | +0.096 | +0.110 | -0.084 | +0.144 |
| `ret3m_m20` | — | -0.263 (5) | — | +0.059 (2) | -0.171 | +0.118 | +0.048 | -0.072 |
| `stress` | — | -0.263 (5) | — | — | -0.263 | +0.117 | +0.102 | -0.161 |
| `bear12` | +0.242 (16) | -0.254 (7) | — | — | +0.091 | +0.110 | -0.053 | +0.125 |
| `dd25_or_b15` | +0.264 (15) | -0.254 (7) | — | +0.059 (2) | +0.096 | +0.110 | -0.069 | +0.128 |
| `dd25_and_vol30` | — | -0.251 (6) | — | — | -0.251 | +0.119 | +0.068 | -0.154 |
| `dd25_exit_b50` | +0.230 (35) | -0.171 (11) | — | +0.124 (9) | +0.133 | +0.100 | -0.054 | +0.159 |
| `b15_exit_b50` | +0.218 (30) | -0.171 (11) | — | +0.124 (9) | +0.115 | +0.106 | -0.049 | +0.140 |
| `stress_exit_ma200` | — | -0.198 (9) | — | — | -0.198 | +0.122 | +0.022 | -0.145 |

## 3. Walk-forward (test years 2020+, rule chosen on purged training years per fold)

### 6m

Chosen per test year: 2020: `dd25_exit_b50|w0.3_lowvol`, 2021: `dd25|w0.0`, 2022: `stress_exit_ma200|w0.0`, 2023: `stress_exit_ma200|w0.0`, 2024: `stress_exit_ma200|w0.0`, 2025: `stress_exit_ma200|w0.0`, 2026: `breadth20|w0.0`

| method | year | IC | top-bottom decile | top-decile beat |
|---|---|---|---|---|
| investiq-v1 | 2020 | -0.068 | -2.9% | 45.4% |
| investiq-v1 | 2021 | +0.111 | +12.6% | 54.8% |
| investiq-v1 | 2022 | +0.082 | +8.3% | 46.5% |
| investiq-v1 | 2023 | +0.131 | +16.2% | 52.5% |
| investiq-v1 | 2024 | +0.070 | +6.6% | 42.9% |
| investiq-v1 | 2025 | +0.066 | +5.7% | 41.1% |
| investiq-v1 | 2026 | +0.065 | +10.2% | 51.0% |
| regime_wf | 2020 | -0.075 | -8.9% | 42.5% |
| regime_wf | 2021 | +0.111 | +12.6% | 54.8% |
| regime_wf | 2022 | +0.082 | +8.3% | 46.5% |
| regime_wf | 2023 | +0.131 | +16.2% | 52.5% |
| regime_wf | 2024 | +0.070 | +6.6% | 42.9% |
| regime_wf | 2025 | +0.066 | +5.7% | 41.1% |
| regime_wf | 2026 | +0.070 | +10.0% | 47.0% |
| primary | 2020 | -0.054 | -6.1% | 44.5% |
| primary | 2021 | +0.111 | +12.6% | 54.8% |
| primary | 2022 | +0.082 | +8.3% | 46.5% |
| primary | 2023 | +0.131 | +16.2% | 52.5% |
| primary | 2024 | +0.070 | +6.6% | 42.9% |
| primary | 2025 | +0.069 | +6.3% | 41.5% |
| primary | 2026 | +0.065 | +10.2% | 51.0% |
| trend6 | 2020 | -0.051 | +0.2% | 47.8% |
| trend6 | 2021 | +0.106 | +16.3% | 53.9% |
| trend6 | 2022 | +0.079 | +7.0% | 47.6% |
| trend6 | 2023 | +0.145 | +19.7% | 53.9% |
| trend6 | 2024 | +0.046 | +5.6% | 42.2% |
| trend6 | 2025 | +0.055 | +4.8% | 41.2% |
| trend6 | 2026 | +0.050 | +9.8% | 45.2% |

| method | mean IC | mean spread | top-decile beat | years IC > 0 | years top10 > all |
|---|---|---|---|---|---|
| investiq-v1 | +0.0653 | +8.1% | 47.7% | 6/7 | 7/7 |
| regime_wf | +0.0650 | +7.2% | 46.8% | 6/7 | 7/7 |
| primary | +0.0678 | +7.7% | 47.7% | 6/7 | 7/7 |
| trend6 | +0.0614 | +9.1% | 47.4% | 6/7 | 7/7 |

Per-date IC on test-year dates where the walk-forward choice was in the risk regime (6m):

| signal date | rule in force | investiq-v1 IC | regime IC | primary IC |
|---|---|---|---|---|
| 2020-01-01 | `dd25_exit_b50|w0.3_lowvol` | +0.171 | +0.231 | +0.207 |
| 2020-03-16 | `dd25_exit_b50|w0.3_lowvol` | -0.201 | -0.282 | -0.145 |
| 2020-04-01 | `dd25_exit_b50|w0.3_lowvol` | -0.170 | -0.240 | -0.135 |
| 2020-04-16 | `dd25_exit_b50|w0.3_lowvol` | -0.021 | -0.057 | +0.010 |
| 2020-05-01 | `dd25_exit_b50|w0.3_lowvol` | -0.144 | -0.173 | -0.110 |
| 2020-05-16 | `dd25_exit_b50|w0.3_lowvol` | -0.219 | -0.242 | -0.173 |
| 2020-06-01 | `dd25_exit_b50|w0.3_lowvol` | -0.220 | -0.253 | -0.175 |
| 2020-06-16 | `dd25_exit_b50|w0.3_lowvol` | -0.264 | -0.264 | -0.220 |
| 2020-07-01 | `dd25_exit_b50|w0.3_lowvol` | -0.158 | -0.142 | -0.127 |
| 2020-07-16 | `dd25_exit_b50|w0.3_lowvol` | -0.228 | -0.212 | -0.222 |
| 2020-08-01 | `dd25_exit_b50|w0.3_lowvol` | -0.299 | -0.295 | -0.333 |
| 2026-02-01 | `breadth20|w0.0` | +0.054 | +0.059 | +0.054 |
| 2026-03-16 | `breadth20|w0.0` | +0.063 | +0.089 | +0.063 |

Key dates (6m, per-date IC; every candidate equals investiq-v1 on its normal dates):

| signal date | investiq-v1 | `w0.5` | `w0.3` | `w0.0` | `w0.3_lowvol` | `w0.3_reversal` |
|---|---|---|---|---|---|---|
| 2020-03-01 | -0.032 | -0.039 | -0.042 | -0.048 | -0.096 | +0.004 |
| 2020-03-16 | -0.201 | -0.172 | -0.145 | -0.103 | -0.282 | -0.012 |
| 2020-04-01 | -0.170 | -0.152 | -0.135 | -0.102 | -0.240 | -0.061 |
| 2020-04-16 | -0.021 | -0.003 | +0.010 | +0.022 | -0.057 | +0.029 |
| 2020-05-01 | -0.144 | -0.130 | -0.110 | -0.070 | -0.173 | -0.126 |
| 2020-05-16 | -0.219 | -0.205 | -0.173 | -0.115 | -0.242 | -0.166 |
| 2020-06-01 | -0.220 | -0.205 | -0.175 | -0.116 | -0.253 | -0.160 |
| 2020-06-16 | -0.264 | -0.255 | -0.220 | -0.157 | -0.264 | -0.252 |
| 2022-06-16 | +0.093 | +0.067 | +0.036 | +0.003 | +0.040 | +0.070 |
| 2022-07-01 | +0.070 | +0.055 | +0.038 | +0.020 | +0.036 | +0.075 |
| 2025-02-16 | -0.020 | -0.001 | +0.020 | +0.042 | +0.033 | +0.039 |
| 2025-03-01 | -0.070 | -0.053 | -0.031 | -0.002 | -0.036 | +0.018 |
| 2025-03-16 | -0.183 | -0.158 | -0.120 | -0.064 | -0.137 | -0.064 |
| 2025-04-01 | -0.120 | -0.110 | -0.090 | -0.062 | -0.068 | -0.099 |
| 2026-03-16 | +0.063 | +0.075 | +0.085 | +0.089 | +0.000 | +0.078 |

### 12m

Chosen per test year: 2021: `dd25_exit_b50|w0.3_lowvol`, 2022: `dd25|w0.0`, 2023: `dd25|w0.0`, 2024: `dd25|w0.0`, 2025: `dd25|w0.0`

| method | year | IC | top-bottom decile | top-decile beat |
|---|---|---|---|---|
| investiq-v1 | 2021 | +0.071 | +16.1% | 50.8% |
| investiq-v1 | 2022 | +0.078 | +13.8% | 44.6% |
| investiq-v1 | 2023 | +0.159 | +32.9% | 53.5% |
| investiq-v1 | 2024 | +0.085 | +7.3% | 41.6% |
| investiq-v1 | 2025 | +0.090 | +9.8% | 38.5% |
| regime_wf | 2021 | +0.071 | +16.1% | 50.8% |
| regime_wf | 2022 | +0.078 | +13.8% | 44.6% |
| regime_wf | 2023 | +0.159 | +32.9% | 53.5% |
| regime_wf | 2024 | +0.085 | +7.3% | 41.6% |
| regime_wf | 2025 | +0.090 | +10.0% | 38.3% |
| primary | 2021 | +0.071 | +16.1% | 50.8% |
| primary | 2022 | +0.078 | +13.8% | 44.6% |
| primary | 2023 | +0.159 | +32.9% | 53.5% |
| primary | 2024 | +0.085 | +7.3% | 41.6% |
| primary | 2025 | +0.077 | +10.6% | 39.1% |
| trend6 | 2021 | +0.093 | +24.5% | 53.5% |
| trend6 | 2022 | +0.080 | +13.9% | 45.9% |
| trend6 | 2023 | +0.189 | +42.1% | 55.9% |
| trend6 | 2024 | +0.060 | +6.7% | 39.7% |
| trend6 | 2025 | +0.087 | +9.0% | 38.8% |

| method | mean IC | mean spread | top-decile beat | years IC > 0 | years top10 > all |
|---|---|---|---|---|---|
| investiq-v1 | +0.0965 | +16.0% | 45.8% | 5/5 | 5/5 |
| regime_wf | +0.0966 | +16.0% | 45.8% | 5/5 | 5/5 |
| primary | +0.0939 | +16.1% | 45.9% | 5/5 | 5/5 |
| trend6 | +0.1019 | +19.3% | 46.7% | 5/5 | 5/5 |

Per-date IC on test-year dates where the walk-forward choice was in the risk regime (12m):

| signal date | rule in force | investiq-v1 IC | regime IC | primary IC |
|---|---|---|---|---|
| 2025-03-01 | `dd25|w0.0` | +0.049 | +0.050 | +0.055 |

Key dates (12m, per-date IC; every candidate equals investiq-v1 on its normal dates):

| signal date | investiq-v1 | `w0.5` | `w0.3` | `w0.0` | `w0.3_lowvol` | `w0.3_reversal` |
|---|---|---|---|---|---|---|
| 2020-03-01 | -0.142 | -0.152 | -0.154 | -0.149 | -0.194 | -0.059 |
| 2020-03-16 | -0.336 | -0.307 | -0.266 | -0.200 | -0.355 | -0.111 |
| 2020-04-01 | -0.322 | -0.291 | -0.246 | -0.177 | -0.313 | -0.115 |
| 2020-04-16 | -0.242 | -0.216 | -0.179 | -0.120 | -0.226 | -0.125 |
| 2020-05-01 | -0.306 | -0.289 | -0.255 | -0.189 | -0.315 | -0.282 |
| 2020-05-16 | -0.360 | -0.341 | -0.296 | -0.209 | -0.359 | -0.332 |
| 2020-06-01 | -0.329 | -0.315 | -0.280 | -0.204 | -0.339 | -0.301 |
| 2020-06-16 | -0.257 | -0.266 | -0.254 | -0.214 | -0.278 | -0.295 |
| 2022-06-16 | +0.092 | +0.085 | +0.076 | +0.059 | +0.090 | +0.049 |
| 2022-07-01 | +0.108 | +0.097 | +0.083 | +0.060 | +0.093 | +0.070 |
| 2025-02-16 | +0.021 | +0.034 | +0.045 | +0.052 | +0.106 | +0.006 |
| 2025-03-01 | +0.049 | +0.054 | +0.055 | +0.050 | +0.100 | +0.040 |
| 2025-03-16 | +0.034 | +0.032 | +0.030 | +0.023 | +0.085 | -0.006 |
| 2025-04-01 | +0.042 | +0.034 | +0.023 | +0.008 | +0.087 | -0.010 |

## 4. Whole grid on test years (record only; not used to choose)

Mean yearly IC minus investiq-v1's on the same test years (6m / 12m), and test years where the candidate's IC is more than 0.01 worse.

| rule | `w0.5` | `w0.3` | `w0.0` | `w0.3_lowvol` | `w0.3_reversal` |
|---|---|---|---|---|---|
| `dd25` | +0.0008 / +0.0009 (0/0) | +0.0020 / +0.0027 (0/0) | +0.0040 / +0.0058 (0/0) | -0.0014 / +0.0002 (1/0) | +0.0035 / +0.0040 (0/0) |
| `dd20` | +0.0008 / +0.0006 (0/0) | +0.0023 / +0.0021 (0/0) | +0.0049 / +0.0052 (0/0) | -0.0011 / +0.0008 (0/0) | +0.0048 / +0.0022 (0/0) |
| `breadth15` | +0.0011 / +0.0009 (0/0) | +0.0023 / +0.0023 (0/0) | +0.0040 / +0.0046 (0/0) | -0.0024 / +0.0009 (1/0) | +0.0041 / +0.0037 (0/0) |
| `breadth20` | +0.0015 / +0.0009 (0/0) | +0.0033 / +0.0023 (0/0) | +0.0057 / +0.0049 (0/0) | -0.0026 / +0.0023 (2/0) | +0.0057 / +0.0032 (0/0) |
| `ret3m_m20` | +0.0007 / +0.0008 (0/0) | +0.0018 / +0.0021 (0/0) | +0.0035 / +0.0045 (0/0) | -0.0006 / +0.0010 (0/0) | +0.0030 / +0.0023 (0/0) |
| `stress` | +0.0005 / +0.0007 (0/0) | +0.0011 / +0.0021 (0/0) | +0.0023 / +0.0046 (0/0) | -0.0011 / +0.0000 (0/0) | +0.0017 / +0.0028 (0/0) |
| `bear12` | +0.0007 / +0.0009 (0/0) | +0.0017 / +0.0026 (0/0) | +0.0036 / +0.0058 (0/0) | -0.0016 / -0.0002 (1/0) | +0.0029 / +0.0041 (0/0) |
| `dd25_or_b15` | +0.0012 / +0.0009 (0/0) | +0.0029 / +0.0026 (0/0) | +0.0053 / +0.0057 (0/0) | -0.0026 / +0.0007 (2/0) | +0.0045 / +0.0036 (0/0) |
| `dd25_and_vol30` | +0.0005 / +0.0007 (0/0) | +0.0014 / +0.0021 (0/0) | +0.0030 / +0.0049 (0/0) | -0.0011 / -0.0001 (0/0) | +0.0018 / +0.0025 (0/0) |
| `dd25_exit_b50` | +0.0010 / -0.0006 (0/0) | +0.0025 / -0.0006 (0/1) | +0.0048 / +0.0003 (0/1) | +0.0015 / -0.0007 (0/0) | +0.0054 / -0.0001 (0/1) |
| `b15_exit_b50` | +0.0013 / -0.0006 (0/0) | +0.0030 / -0.0006 (0/1) | +0.0054 / +0.0003 (0/1) | +0.0000 / -0.0007 (1/0) | +0.0057 / -0.0001 (0/1) |
| `stress_exit_ma200` | +0.0003 / +0.0000 (0/0) | +0.0014 / +0.0012 (0/0) | +0.0036 / +0.0040 (0/0) | -0.0009 / -0.0013 (0/0) | +0.0019 / +0.0011 (0/0) |

## 5. Live choice (same objective on all labelled years, 6m and 12m averaged)

| candidate | objective 6m | objective 12m | average |
|---|---|---|---|
| `dd25_or_b15|w0.0` | 0.0545 | 0.0443 | 0.0494 |
| `dd25|w0.0` | 0.0532 | 0.0444 | 0.0488 |
| `dd20|w0.0` | 0.0544 | 0.0427 | 0.0485 |
| `breadth20|w0.0` | 0.0542 | 0.0426 | 0.0484 |
| `bear12|w0.0` | 0.0524 | 0.0437 | 0.0480 |
| `breadth15|w0.0` | 0.0525 | 0.0419 | 0.0472 |
| `dd25_and_vol30|w0.0` | 0.0520 | 0.0424 | 0.0472 |
| `stress_exit_ma200|w0.0` | 0.0531 | 0.0408 | 0.0469 |
| `ret3m_m20|w0.0` | 0.0520 | 0.0418 | 0.0469 |
| `breadth15|w0.3_reversal` | 0.0527 | 0.0407 | 0.0467 |
| `investiq-v1` | 0.0467 | 0.0335 | 0.0401 |

Live choice: `dd25_or_b15|w0.0`.

Ship criteria (pre-declared):

- 6m: ic_not_worse NO, spread_not_worse NO, no_year_worse_by_0.01 yes, trigger_dates_better NO
- 12m: ic_not_worse yes, spread_not_worse yes, no_year_worse_by_0.01 yes, trigger_dates_better yes

## 6. Time-machine windows

Label-panel proxy for `dd25_or_b15|w0.0` (nearest grid date, 12m label when the window is > 250 days else 6m; top 50 by score, raw return; non-financial rows only):

| window | grid date | h | state | IC investiq-v1 | IC regime | top 50 v1 | top 50 regime | all | Smallcap 250 |
|---|---|---|---|---|---|---|---|---|---|
| One year ago | 2025-09-16 | 12m | normal | +0.114 | +0.114 | +11.7% | +11.7% | +2.4% | +3.9% |
| COVID crash | 2020-01-16 | 6m | normal | +0.160 | +0.160 | -7.9% | -7.9% | -10.3% | -18.4% |
| COVID crash and rebound | 2020-01-16 | 12m | normal | +0.142 | +0.142 | +40.2% | +40.2% | +33.9% | +20.1% |
| Post-COVID rally | 2020-04-16 | 12m | risk | -0.242 | -0.120 | +87.5% | +101.2% | +105.7% | +92.2% |
| 2022 rate-hike sell-off | 2021-12-16 | 6m | normal | +0.078 | +0.078 | -14.0% | -14.0% | -10.2% | -17.0% |
| 2024-25 small-cap correction | 2024-09-16 | 6m | normal | +0.142 | +0.142 | -19.4% | -19.4% | -22.5% | -20.1% |
| COVID low, 6m | 2020-04-01 | 6m | risk | -0.170 | -0.102 | +82.7% | +74.2% | +77.1% | +62.4% |
| May 2020, 12m | 2020-05-16 | 12m | risk | -0.360 | -0.209 | +105.2% | +111.9% | +138.2% | +131.9% |
| March 2025 low, 12m | 2025-03-16 | 12m | risk | +0.034 | +0.023 | -3.8% | +2.1% | -4.4% | +0.6% |
| 2026 spring low, to date | 2026-04-01 | 6m | nan | — | — | — | — | — | — |

## 7. Assessment

- **The pre-declared walk-forward does not pass.** On 6m the regime model is slightly worse than investiq-v1 (mean yearly IC and decile spread lower): the 2020 fold had only 3 usable training dates (2019-05/06, all inside the 2018-19 bear) and picked `dd25_exit_b50|w0.3_lowvol`, which made 2020 worse (spread -2.9% -> -8.9%). From 2021 the chosen rules rarely trigger in their test year, so 2021-2026 are identical or within +-0.005 IC: neutral, not better. 12m passes, but only because one date (2025-03-01) differs.
- **No fold could learn from COVID before 2020.** The financial panel starts 2019-05, so the only crash the walk-forward can test out of sample is the one used to motivate the idea. Every claim that a rule "fixes" April 2020 is in-sample.
- **Deep-fall states do not reliably reverse trend.** On the 2017+ market universe (section 2), trend6 IC on dd25 / breadth / bear12 risk dates in the 2018-19 bear was +0.20 to +0.30, *higher* than on normal dates (+0.11). Only the COVID V-rebound (and, on 6m only, March 2025) reversed. A rule keyed to drawdown or breadth would have cut the trend weight exactly when trend worked best in 2018-19. Panic rules (stress, ret3m_m20, dd25_and_vol30) avoid 2018-19 but fire on 5-9 dates in one or two episodes: there is nothing to validate them on.
- **Even in-sample the fix is partial.** With trend weight 0 on COVID dates the IC goes from -0.19 to -0.06 (time machine, 2020-04-16) but stays negative: fin-v1 also failed in 2020. The reversal tilt helped in March 2020 only; the low-vol tilt made 2020 worse (the rebound was led by high-volatility stocks).
- **Time machine with the in-sample favourite `dd25_or_b15|w0.0`:** windows ranked in a normal state are unchanged by construction (one year ago, COVID crash, crash + rebound, 2022, 2024-25). Ranked in the risk state: Post-COVID IC -0.19 -> -0.06 and top 50 +101% -> +122%; COVID low 6m IC -0.17 -> -0.03 but top 50 +94% -> +88%; May 2020 IC -0.26 -> -0.12, top 50 +119% -> +131%; March 2025 12m IC +0.08 -> +0.07 but top 50 -5% -> +9%; spring 2026 about the same. Mixed on the top-50 measure and always in-sample.
- **Recommendation: do not ship a regime switch now.** Keep investiq-v1 (MARKET_WEIGHT 0.7 always) and keep regime.RECOMMENDED = None. Re-run `python3 -m rankings.regime_eval --tm` after the next deep fall adds an out-of-sample episode, or once financial history before 2019 (or a trend-only fallback panel) lets the 2018-19 bear enter the training folds. If the owner still wants a guard, the least risky ex-post option is a panic-only rule (`stress_exit_ma200` or `ret3m_m20`, market weight 0.3), presented as a judgement call, not a tested result.
