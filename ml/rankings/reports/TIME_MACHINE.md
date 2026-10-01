# InvestIQ time-machine validation (investiq-v1)

Generated 2026-10-01. Each window ranks companies with only the data public on its start date, then measures what actually happened.

| window | ranked → held to | IC | top 50 | all ranked | Smallcap 250 | top / bottom decile avg | worst drawdown top 50 / index |
|---|---|---|---|---|---|---|---|
| One year ago | 2025-09-30 → 2026-09-28 | +0.179 | +4.1% | +0.6% | +5.9% | +8.5% / -9.5% | -23.4% / -18.4% |
| COVID crash | 2020-01-16 → 2020-03-31 | +0.287 | -33.3% | -39.7% | -39.1% | -33.7% / -45.9% | -39.2% / -43.8% |
| COVID crash and rebound | 2020-01-16 → 2021-01-15 | +0.063 | +69.2% | +39.8% | +20.3% | +55.6% / +26.9% | -39.2% / -43.8% |
| Post-COVID rally | 2020-04-16 → 2021-04-16 | -0.194 | +101.2% | +111.4% | +94.6% | +99.4% / +130.3% | -7.9% / -8.5% |
| 2018 small-cap crash | 2018-01-16 → 2019-01-16 | not testable: only 0 companies rankable on 2018-01-16: a fresh financial growth reading is required, and filings only support year-on-year growth from about 2019 | | | | | |
| 2022 rate-hike sell-off | 2021-12-16 → 2022-06-30 | +0.060 | -11.2% | -5.4% | -15.0% | -9.1% / -14.0% | -34.2% / -26.9% |
| 2024-25 small-cap correction | 2024-09-16 → 2025-03-03 | +0.083 | -21.4% | -25.9% | -25.8% | -24.1% / -28.3% | -29.0% / -26.1% |

**Read with care**
- Scores use only data public on the ranking date, but the company list and sector labels are today's:
  companies that later delisted are missing (survivorship bias), which flatters every row, not one more than another.
- Balance-sheet data starts in late 2022 and company news in 2026-08, so pre-2023 snapshots are mostly price
  trend plus income-statement growth; the 2025-26 window is the closest to today's full model.
- One window is one draw of luck. The walk-forward test (ml/rankings/combiner_eval.py) averages over 2019-2026.
- Returns are price returns before costs and taxes; dividends are not included.

## One year ago: 2025-09-30 → 2026-09-28

Ranked a year ago, held to today.

Ranked 1,837 companies as of 2025-09-30 (bought at the 2025-10-01 close); 1,831 have a clean price path to 2026-09-28. NIFTY SMALLCAP 250: +5.9%. Spearman IC (score vs actual return): **+0.179**.

| portfolio (equal weight, buy and hold) | return | worst drawdown on the way |
|---|---|---|
| Top 50 by InvestIQ score | +4.1% | -23.4% |
| All ranked stocks | +0.6% | -25.0% |
| Bottom 50 | -20.5% | -37.5% |
| NIFTY SMALLCAP 250 | +5.9% | -18.4% |

**By score decile** (10 = highest scores)

| decile | stocks | avg return | median return | beat index | fell 30%+ | median worst drawdown |
|---|---|---|---|---|---|---|
| 10 | 183 | +8.5% | -1.5% | 45% | 11% | -31.8% |
| 9 | 183 | +10.7% | -6.4% | 37% | 15% | -32.2% |
| 8 | 183 | +7.9% | -9.0% | 39% | 14% | -32.7% |
| 7 | 183 | +5.8% | -7.9% | 34% | 17% | -31.2% |
| 6 | 183 | +3.5% | -6.7% | 31% | 19% | -33.5% |
| 5 | 183 | -5.2% | -12.9% | 30% | 21% | -35.7% |
| 4 | 183 | -1.5% | -12.9% | 27% | 26% | -38.5% |
| 3 | 183 | -8.5% | -18.5% | 25% | 32% | -40.2% |
| 2 | 183 | -5.9% | -14.4% | 28% | 30% | -40.8% |
| 1 | 184 | -9.5% | -19.4% | 26% | 36% | -45.9% |

**By label**

| growth_label | stocks | avg return | median return | beat index | fell 30%+ | median worst drawdown |
|---|---|---|---|---|---|---|
| Strong | 316 | +8.4% | -2.4% | 41% | 14% | -31.8% |
| Positive | 347 | +8.0% | -8.8% | 37% | 15% | -32.3% |
| Neutral | 488 | +0.9% | -8.0% | 31% | 19% | -34.5% |
| Weak | 680 | -7.1% | -16.4% | 26% | 31% | -40.9% |

**"Price already stretched" risk flag**

| flag | stocks | avg return | median return | beat index | fell 30%+ | median worst drawdown |
|---|---|---|---|---|---|---|
| flagged | 26 | -0.8% | -7.0% | 46% | 27% | -47.7% |
| not flagged | 1805 | +0.6% | -10.8% | 32% | 22% | -36.1% |

**Top 15 picks on 2025-09-30 and what happened**

| rank | company | sector | score | label | actual return | vs index |
|---|---|---|---|---|---|---|
| 1 | TFCILTD | Financial Services | 97 | Strong | +90% | +84% |
| 2 | LTF | Financial Services | 96 | Strong | +9% | +3% |
| 3 | TATAINVEST | Financial Services | 96 | Strong | -39% | -45% |
| 4 | GVT&D | Industrials & Infrastructure | 96 | Strong | +37% | +31% |
| 5 | SIGMA | Technology | 95 | Strong | -23% | -29% |
| 6 | HBLENGINE | Automobile & Mobility | 95 | Strong | -6% | -12% |
| 7 | SIRCA | Metals, Mining & Chemicals | 95 | Strong | -16% | -22% |
| 8 | GANDHITUBE | Metals, Mining & Chemicals | 95 | Strong | -1% | -7% |
| 9 | CARTRADE | Automobile & Mobility | 95 | Strong | +18% | +12% |
| 10 | NETWEB | Technology | 95 | Strong | +12% | +7% |
| 11 | TERASOFT | Technology | 94 | Strong | -55% | -61% |
| 12 | GARUDA | Industrials & Infrastructure | 94 | Strong | -6% | -12% |
| 13 | SJS | Automobile & Mobility | 94 | Strong | +50% | +44% |
| 14 | KAVDEFENCE | Technology | 94 | Strong | -46% | -52% |
| 15 | ANANDRATHI | Financial Services | 94 | Strong | +49% | +43% |

**Bottom 15 on 2025-09-30**

| rank | company | sector | score | label | actual return | vs index |
|---|---|---|---|---|---|---|
| 1837 | PARSVNATH | Industrials & Infrastructure | 0 | Weak | -85% | -90% |
| 1836 | SPARC | Healthcare & Pharmaceuticals | 0 | Weak | +53% | +48% |
| 1835 | DISHTV | Services & Others | 1 | Weak | -54% | -60% |
| 1834 | RADAAN | Services & Others | 3 | Weak | -12% | -18% |
| 1833 | CAPTRUST | Financial Services | 3 | Weak | -50% | -56% |
| 1832 | SPENCERS | Consumer & FMCG | 3 | Weak | -51% | -57% |
| 1831 | SHAREINDIA | Services & Others | 3 | Weak | +53% | +47% |
| 1830 | GSS | Technology | 3 | Weak | -59% | -65% |
| 1829 | FMNL | Real Estate & Construction | 3 | Weak | -18% | -24% |
| 1828 | FLEXITUFF | Industrials & Infrastructure | 3 | Weak | -87% | -93% |
| 1827 | EXICOM | Industrials & Infrastructure | 4 | Weak | +6% | +0% |
| 1826 | ALMONDZ | Services & Others | 4 | Weak | +15% | +9% |
| 1825 | UMAEXPORTS | Consumer & FMCG | 4 | Weak | -52% | -58% |
| 1824 | VPRPL | Industrials & Infrastructure | 4 | Weak | -68% | -74% |
| 1823 | ABMINTLLTD | Services & Others | 4 | Weak | +12% | +6% |

## COVID crash: 2020-01-16 → 2020-03-31

Ranked before COVID hit India; held through the March 2020 crash.

Ranked 687 companies as of 2020-01-16 (bought at the 2020-01-17 close); 682 have a clean price path to 2020-03-31. NIFTY SMALLCAP 250: -39.1%. Spearman IC (score vs actual return): **+0.287**.

| portfolio (equal weight, buy and hold) | return | worst drawdown on the way |
|---|---|---|
| Top 50 by InvestIQ score | -33.3% | -39.2% |
| All ranked stocks | -39.7% | -43.4% |
| Bottom 50 | -44.6% | -46.2% |
| NIFTY SMALLCAP 250 | -39.1% | -43.8% |

**By score decile** (10 = highest scores)

| decile | stocks | avg return | median return | beat index | fell 30%+ | median worst drawdown |
|---|---|---|---|---|---|---|
| 10 | 69 | -33.7% | -36.3% | 54% | 62% | -49.4% |
| 9 | 68 | -30.9% | -33.1% | 66% | 54% | -45.5% |
| 8 | 68 | -35.7% | -37.4% | 56% | 65% | -48.6% |
| 7 | 68 | -39.1% | -38.6% | 56% | 75% | -49.9% |
| 6 | 68 | -37.4% | -40.9% | 49% | 68% | -48.6% |
| 5 | 68 | -40.4% | -41.7% | 43% | 76% | -52.0% |
| 4 | 68 | -45.2% | -46.9% | 21% | 90% | -54.8% |
| 3 | 68 | -42.9% | -44.6% | 32% | 76% | -53.9% |
| 2 | 68 | -45.8% | -50.9% | 28% | 85% | -56.8% |
| 1 | 69 | -45.9% | -49.1% | 32% | 84% | -55.6% |

**By label**

| growth_label | stocks | avg return | median return | beat index | fell 30%+ | median worst drawdown |
|---|---|---|---|---|---|---|
| Strong | 121 | -32.3% | -33.6% | 60% | 57% | -47.0% |
| Positive | 131 | -35.6% | -37.2% | 57% | 68% | -47.3% |
| Neutral | 187 | -40.5% | -43.2% | 41% | 76% | -51.7% |
| Weak | 243 | -45.0% | -48.9% | 30% | 83% | -55.6% |

**"Price already stretched" risk flag**

| flag | stocks | avg return | median return | beat index | fell 30%+ | median worst drawdown |
|---|---|---|---|---|---|---|
| flagged | 9 | -26.2% | -44.0% | 44% | 56% | -50.4% |
| not flagged | 673 | -39.9% | -42.8% | 44% | 74% | -51.9% |

**Top 15 picks on 2020-01-16 and what happened**

| rank | company | sector | score | label | actual return | vs index |
|---|---|---|---|---|---|---|
| 1 | CUPID | Consumer & FMCG | 97 | Strong | -44% | -5% |
| 2 | AVANTIFEED | Consumer & FMCG | 97 | Strong | -59% | -20% |
| 3 | DIXON | Technology | 96 | Strong | -14% | +25% |
| 4 | ADANIGREEN | Energy | 96 | Strong | -19% | +20% |
| 5 | GRANULES | Healthcare & Pharmaceuticals | 94 | Strong | +1% | +40% |
| 6 | LALPATHLAB | Healthcare & Pharmaceuticals | 94 | Strong | -16% | +23% |
| 7 | ANANTRAJ | Industrials & Infrastructure | 93 | Strong | -48% | -9% |
| 8 | ADANIENSOL | Energy | 93 | Strong | -45% | -5% |
| 9 | RELAXO | Consumer & FMCG | 93 | Strong | -12% | +27% |
| 10 | NH | Healthcare & Pharmaceuticals | 93 | Strong | -31% | +8% |
| 11 | BIRLACORPN | Real Estate & Construction | 92 | Strong | -48% | -9% |
| 12 | ALKEM | Healthcare & Pharmaceuticals | 92 | Strong | -1% | +39% |
| 13 | ADSL | Technology | 92 | Strong | -37% | +2% |
| 14 | AMRUTANJAN | Healthcare & Pharmaceuticals | 92 | Strong | -33% | +6% |
| 15 | TRIVENI | Consumer & FMCG | 92 | Strong | -56% | -16% |

**Bottom 15 on 2020-01-16**

| rank | company | sector | score | label | actual return | vs index |
|---|---|---|---|---|---|---|
| 687 | JISLJALEQS | Industrials & Infrastructure | 4 | Weak | -59% | -20% |
| 686 | NEXTMEDIA | Services & Others | 4 | Weak | -63% | -24% |
| 685 | JISLDVREQS | Industrials & Infrastructure | 4 | Weak | -59% | -19% |
| 684 | KRIDHANINF | Metals, Mining & Chemicals | 5 | Weak | -56% | -16% |
| 683 | CHENNPETRO | Technology | 5 | Weak | -58% | -19% |
| 682 | OILCOUNTUB | Energy | 5 | Weak | -46% | -7% |
| 681 | SADBHIN | Industrials & Infrastructure | 6 | Weak | -69% | -29% |
| 680 | SHAKTIPUMP | Industrials & Infrastructure | 6 | Weak | -56% | -17% |
| 679 | INCREDIBLE | Metals, Mining & Chemicals | 6 | Weak | -74% | -35% |
| 678 | ALPHAGEO | Industrials & Infrastructure | 6 | Weak | -43% | -4% |
| 677 | DISHTV | Services & Others | 6 | Weak | -69% | -30% |
| 676 | GVT&D | Industrials & Infrastructure | 8 | Weak | -56% | -17% |
| 675 | AUTOIND | Automobile & Mobility | 8 | Weak | -61% | -22% |
| 674 | THOMASCOTT | Consumer & FMCG | 8 | Weak | -12% | +27% |
| 673 | INTELLECT | Technology | 8 | Weak | -66% | -27% |

## COVID crash and rebound: 2020-01-16 → 2021-01-15

Same picks, held for a year through the crash and the rebound.

Ranked 687 companies as of 2020-01-16 (bought at the 2020-01-17 close); 680 have a clean price path to 2021-01-15. NIFTY SMALLCAP 250: +20.3%. Spearman IC (score vs actual return): **+0.063**.

| portfolio (equal weight, buy and hold) | return | worst drawdown on the way |
|---|---|---|
| Top 50 by InvestIQ score | +69.2% | -39.2% |
| All ranked stocks | +39.8% | -43.5% |
| Bottom 50 | +34.6% | -46.2% |
| NIFTY SMALLCAP 250 | +20.3% | -43.8% |

**By score decile** (10 = highest scores)

| decile | stocks | avg return | median return | beat index | fell 30%+ | median worst drawdown |
|---|---|---|---|---|---|---|
| 10 | 68 | +55.6% | +25.6% | 53% | 3% | -49.7% |
| 9 | 68 | +51.1% | +32.6% | 65% | 1% | -45.9% |
| 8 | 68 | +45.6% | +22.9% | 53% | 0% | -48.6% |
| 7 | 68 | +35.1% | +19.0% | 50% | 0% | -50.8% |
| 6 | 68 | +29.6% | +12.4% | 37% | 4% | -48.9% |
| 5 | 68 | +43.3% | +24.5% | 53% | 3% | -52.5% |
| 4 | 68 | +28.6% | +17.0% | 44% | 3% | -56.2% |
| 3 | 68 | +50.7% | +29.3% | 54% | 9% | -55.5% |
| 2 | 68 | +31.3% | +18.7% | 49% | 3% | -58.3% |
| 1 | 68 | +26.9% | +11.7% | 46% | 12% | -57.1% |

**By label**

| growth_label | stocks | avg return | median return | beat index | fell 30%+ | median worst drawdown |
|---|---|---|---|---|---|---|
| Strong | 120 | +55.6% | +32.1% | 61% | 2% | -48.1% |
| Positive | 131 | +42.5% | +20.6% | 51% | 0% | -48.4% |
| Neutral | 187 | +31.8% | +18.2% | 45% | 3% | -52.6% |
| Weak | 242 | +36.6% | +17.7% | 48% | 7% | -57.1% |

**"Price already stretched" risk flag**

| flag | stocks | avg return | median return | beat index | fell 30%+ | median worst drawdown |
|---|---|---|---|---|---|---|
| flagged | 9 | +225.5% | +110.4% | 67% | 11% | -50.4% |
| not flagged | 671 | +37.3% | +20.5% | 50% | 4% | -52.8% |

**Top 15 picks on 2020-01-16 and what happened**

| rank | company | sector | score | label | actual return | vs index |
|---|---|---|---|---|---|---|
| 1 | CUPID | Consumer & FMCG | 97 | Strong | -8% | -28% |
| 2 | AVANTIFEED | Consumer & FMCG | 97 | Strong | -29% | -49% |
| 3 | DIXON | Technology | 96 | Strong | +258% | +237% |
| 4 | ADANIGREEN | Energy | 96 | Strong | +402% | +382% |
| 5 | GRANULES | Healthcare & Pharmaceuticals | 94 | Strong | +151% | +130% |
| 6 | LALPATHLAB | Healthcare & Pharmaceuticals | 94 | Strong | +37% | +17% |
| 7 | ANANTRAJ | Industrials & Infrastructure | 93 | Strong | +55% | +35% |
| 8 | ADANIENSOL | Energy | 93 | Strong | +27% | +7% |
| 9 | RELAXO | Consumer & FMCG | 93 | Strong | +25% | +5% |
| 10 | NH | Healthcare & Pharmaceuticals | 93 | Strong | +30% | +10% |
| 11 | BIRLACORPN | Real Estate & Construction | 92 | Strong | -9% | -30% |
| 12 | ALKEM | Healthcare & Pharmaceuticals | 92 | Strong | +33% | +12% |
| 13 | ADSL | Technology | 92 | Strong | +101% | +80% |
| 14 | AMRUTANJAN | Healthcare & Pharmaceuticals | 92 | Strong | +10% | -10% |
| 15 | TRIVENI | Consumer & FMCG | 92 | Strong | -9% | -30% |

**Bottom 15 on 2020-01-16**

| rank | company | sector | score | label | actual return | vs index |
|---|---|---|---|---|---|---|
| 687 | JISLJALEQS | Industrials & Infrastructure | 4 | Weak | +168% | +148% |
| 686 | NEXTMEDIA | Services & Others | 4 | Weak | -32% | -52% |
| 685 | JISLDVREQS | Industrials & Infrastructure | 4 | Weak | +79% | +59% |
| 684 | KRIDHANINF | Metals, Mining & Chemicals | 5 | Weak | +50% | +30% |
| 683 | CHENNPETRO | Technology | 5 | Weak | -15% | -35% |
| 682 | OILCOUNTUB | Energy | 5 | Weak | -4% | -25% |
| 681 | SADBHIN | Industrials & Infrastructure | 6 | Weak | -52% | -73% |
| 680 | SHAKTIPUMP | Industrials & Infrastructure | 6 | Weak | +34% | +14% |
| 679 | INCREDIBLE | Metals, Mining & Chemicals | 6 | Weak | -47% | -67% |
| 678 | ALPHAGEO | Industrials & Infrastructure | 6 | Weak | -10% | -30% |
| 677 | DISHTV | Services & Others | 6 | Weak | -3% | -23% |
| 676 | GVT&D | Industrials & Infrastructure | 8 | Weak | -23% | -44% |
| 675 | AUTOIND | Automobile & Mobility | 8 | Weak | +36% | +16% |
| 674 | THOMASCOTT | Consumer & FMCG | 8 | Weak | +101% | +81% |
| 673 | INTELLECT | Technology | 8 | Weak | +109% | +88% |

## Post-COVID rally: 2020-04-16 → 2021-04-16

Ranked near the bottom; the junk-led rebound year.

Ranked 696 companies as of 2020-04-16 (bought at the 2020-04-17 close); 692 have a clean price path to 2021-04-16. NIFTY SMALLCAP 250: +94.6%. Spearman IC (score vs actual return): **-0.194**.

| portfolio (equal weight, buy and hold) | return | worst drawdown on the way |
|---|---|---|
| Top 50 by InvestIQ score | +101.2% | -7.9% |
| All ranked stocks | +111.4% | -8.7% |
| Bottom 50 | +127.9% | -11.3% |
| NIFTY SMALLCAP 250 | +94.6% | -8.5% |

**By score decile** (10 = highest scores)

| decile | stocks | avg return | median return | beat index | fell 30%+ | median worst drawdown |
|---|---|---|---|---|---|---|
| 10 | 70 | +99.4% | +52.1% | 26% | 0% | -23.2% |
| 9 | 69 | +91.3% | +58.8% | 32% | 0% | -22.2% |
| 8 | 69 | +103.3% | +79.1% | 41% | 1% | -22.9% |
| 7 | 69 | +101.6% | +57.9% | 30% | 0% | -25.5% |
| 6 | 69 | +101.6% | +55.5% | 33% | 0% | -26.7% |
| 5 | 69 | +99.4% | +64.8% | 35% | 0% | -27.3% |
| 4 | 69 | +131.4% | +82.4% | 43% | 0% | -28.3% |
| 3 | 69 | +130.2% | +105.5% | 57% | 1% | -26.9% |
| 2 | 69 | +125.4% | +112.6% | 59% | 0% | -27.0% |
| 1 | 70 | +130.3% | +102.7% | 57% | 0% | -29.5% |

**By label**

| growth_label | stocks | avg return | median return | beat index | fell 30%+ | median worst drawdown |
|---|---|---|---|---|---|---|
| Strong | 128 | +92.9% | +57.0% | 29% | 0% | -22.4% |
| Positive | 135 | +92.8% | +68.5% | 36% | 1% | -23.2% |
| Neutral | 164 | +110.0% | +63.8% | 34% | 0% | -26.8% |
| Weak | 265 | +130.6% | +104.4% | 55% | 0% | -28.3% |

**"Price already stretched" risk flag**

| flag | stocks | avg return | median return | beat index | fell 30%+ | median worst drawdown |
|---|---|---|---|---|---|---|
| flagged | 5 | +297.1% | +434.5% | 60% | 0% | -30.9% |
| not flagged | 687 | +110.0% | +74.4% | 41% | 0% | -25.9% |

**Top 15 picks on 2020-04-16 and what happened**

| rank | company | sector | score | label | actual return | vs index |
|---|---|---|---|---|---|---|
| 1 | CPCAP | Services & Others | 97 | Strong | -7% | -102% |
| 2 | MIDHANI | Metals, Mining & Chemicals | 96 | Strong | -19% | -114% |
| 3 | ALKEM | Healthcare & Pharmaceuticals | 96 | Strong | +4% | -90% |
| 4 | AJANTPHARM | Healthcare & Pharmaceuticals | 95 | Strong | +28% | -67% |
| 5 | IOLCP | Healthcare & Pharmaceuticals | 95 | Strong | +121% | +27% |
| 6 | CORALFINAC | Financial Services | 95 | Strong | +53% | -42% |
| 7 | APLLTD | Healthcare & Pharmaceuticals | 95 | Strong | +62% | -32% |
| 8 | LAURUSLABS | Healthcare & Pharmaceuticals | 94 | Strong | +452% | +358% |
| 9 | RALLIS | Metals, Mining & Chemicals | 94 | Strong | +27% | -68% |
| 10 | SHILPAMED | Healthcare & Pharmaceuticals | 94 | Strong | +1% | -94% |
| 11 | SANOFI | Healthcare & Pharmaceuticals | 93 | Strong | +1% | -93% |
| 12 | DHANUKA | Metals, Mining & Chemicals | 93 | Strong | +62% | -32% |
| 13 | COROMANDEL | Metals, Mining & Chemicals | 93 | Strong | +37% | -57% |
| 14 | CUPID | Consumer & FMCG | 92 | Strong | +22% | -72% |
| 15 | TASTYBITE | Consumer & FMCG | 92 | Strong | +45% | -49% |

**Bottom 15 on 2020-04-16**

| rank | company | sector | score | label | actual return | vs index |
|---|---|---|---|---|---|---|
| 696 | NEXTMEDIA | Services & Others | 3 | Weak | +8% | -86% |
| 695 | SADBHIN | Industrials & Infrastructure | 3 | Weak | +62% | -32% |
| 694 | DISHTV | Services & Others | 5 | Weak | +111% | +17% |
| 693 | BHARATGEAR | Automobile & Mobility | 5 | Weak | +102% | +7% |
| 692 | ISFT | Technology | 7 | Weak | +280% | +185% |
| 691 | TEJASNET | Technology | 7 | Weak | +289% | +195% |
| 690 | RANEHOLDIN | Financial Services | 7 | Weak | +41% | -54% |
| 689 | JISLDVREQS | Industrials & Infrastructure | 8 | Weak | +155% | +60% |
| 688 | INTELLECT | Technology | 8 | Weak | +717% | +622% |
| 687 | KRIDHANINF | Metals, Mining & Chemicals | 8 | Weak | +160% | +65% |
| 686 | JISLJALEQS | Industrials & Infrastructure | 8 | Weak | +268% | +173% |
| 685 | INCREDIBLE | Metals, Mining & Chemicals | 8 | Weak | +56% | -38% |
| 684 | GVT&D | Industrials & Infrastructure | 8 | Weak | +21% | -74% |
| 683 | THOMASCOOK | Consumer & FMCG | 8 | Weak | +32% | -62% |
| 682 | VARROC | Automobile & Mobility | 9 | Weak | +132% | +38% |

## 2022 rate-hike sell-off: 2021-12-16 → 2022-06-30

Ranked before global rate hikes and the Ukraine war.

Ranked 1,316 companies as of 2021-12-16 (bought at the 2021-12-17 close); 1,310 have a clean price path to 2022-06-30. NIFTY SMALLCAP 250: -15.0%. Spearman IC (score vs actual return): **+0.060**.

| portfolio (equal weight, buy and hold) | return | worst drawdown on the way |
|---|---|---|
| Top 50 by InvestIQ score | -11.2% | -34.2% |
| All ranked stocks | -5.4% | -23.7% |
| Bottom 50 | -22.2% | -32.2% |
| NIFTY SMALLCAP 250 | -15.0% | -26.9% |

**By score decile** (10 = highest scores)

| decile | stocks | avg return | median return | beat index | fell 30%+ | median worst drawdown |
|---|---|---|---|---|---|---|
| 10 | 131 | -9.1% | -16.5% | 48% | 24% | -41.6% |
| 9 | 131 | -3.6% | -6.5% | 66% | 15% | -36.5% |
| 8 | 131 | -1.2% | -8.9% | 63% | 17% | -37.2% |
| 7 | 131 | +0.2% | -6.7% | 66% | 10% | -34.7% |
| 6 | 131 | -2.3% | -8.8% | 60% | 16% | -34.7% |
| 5 | 131 | -5.9% | -9.3% | 57% | 17% | -36.6% |
| 4 | 131 | -6.1% | -10.4% | 63% | 12% | -34.0% |
| 3 | 131 | -4.8% | -10.8% | 60% | 8% | -34.6% |
| 2 | 131 | -6.6% | -11.2% | 63% | 8% | -33.0% |
| 1 | 131 | -14.0% | -16.9% | 43% | 21% | -34.9% |

**By label**

| growth_label | stocks | avg return | median return | beat index | fell 30%+ | median worst drawdown |
|---|---|---|---|---|---|---|
| Strong | 211 | -6.9% | -12.2% | 54% | 20% | -39.4% |
| Positive | 265 | -0.9% | -7.2% | 65% | 14% | -36.2% |
| Neutral | 363 | -4.1% | -9.3% | 60% | 15% | -35.0% |
| Weak | 471 | -8.2% | -12.3% | 56% | 13% | -34.6% |

**"Price already stretched" risk flag**

| flag | stocks | avg return | median return | beat index | fell 30%+ | median worst drawdown |
|---|---|---|---|---|---|---|
| flagged | 114 | -9.2% | -17.7% | 45% | 25% | -43.5% |
| not flagged | 1196 | -5.0% | -10.3% | 60% | 14% | -34.9% |

**Top 15 picks on 2021-12-16 and what happened**

| rank | company | sector | score | label | actual return | vs index |
|---|---|---|---|---|---|---|
| 1 | LYKALABS | Healthcare & Pharmaceuticals | 97 | Strong | -50% | -35% |
| 2 | VIJIFIN | Financial Services | 97 | Strong | -28% | -13% |
| 3 | CALSOFT | Technology | 97 | Strong | -57% | -42% |
| 4 | THOMASCOTT | Consumer & FMCG | 95 | Strong | -10% | +5% |
| 5 | TANLA | Technology | 95 | Strong | -44% | -29% |
| 6 | MANINFRA | Industrials & Infrastructure | 95 | Strong | -18% | -3% |
| 7 | BORORENEW | Energy | 95 | Strong | -13% | +2% |
| 8 | TRIDENT | Industrials & Infrastructure | 95 | Strong | -29% | -14% |
| 9 | BIGBLOC | Real Estate & Construction | 95 | Strong | +126% | +141% |
| 10 | ENERGYDEV | Energy | 95 | Strong | -33% | -18% |
| 11 | SHAHALLOYS | Metals, Mining & Chemicals | 94 | Strong | +34% | +49% |
| 12 | BSE | Services & Others | 94 | Strong | -9% | +6% |
| 13 | UNIVPHOTO | Industrials & Infrastructure | 93 | Strong | -34% | -19% |
| 14 | OLECTRA | Technology | 93 | Strong | -32% | -17% |
| 15 | HUBTOWN | Industrials & Infrastructure | 93 | Strong | +38% | +53% |

**Bottom 15 on 2021-12-16**

| rank | company | sector | score | label | actual return | vs index |
|---|---|---|---|---|---|---|
| 1316 | STAR | Healthcare & Pharmaceuticals | 4 | Weak | -21% | -6% |
| 1315 | HUHTAMAKI | Industrials & Infrastructure | 5 | Weak | -23% | -8% |
| 1314 | HDFCAMC | Financial Services | 5 | Weak | -25% | -10% |
| 1313 | MCL | Metals, Mining & Chemicals | 5 | Weak | -28% | -13% |
| 1312 | WELINV | Financial Services | 5 | Weak | -0% | +15% |
| 1311 | VIYASH | Healthcare & Pharmaceuticals | 5 | Weak | -41% | -26% |
| 1310 | GVPIL | Energy | 6 | Weak | -48% | -33% |
| 1309 | RAMCOSYS | Technology | 6 | Weak | -35% | -20% |
| 1308 | AARTISURF | Consumer & FMCG | 6 | Weak | -39% | -24% |
| 1307 | MAHEPC | Industrials & Infrastructure | 7 | Weak | -16% | -1% |
| 1306 | SOLARA | Energy | 7 | Weak | -67% | -52% |
| 1305 | IOLCP | Healthcare & Pharmaceuticals | 7 | Weak | -27% | -12% |
| 1304 | NECLIFE | Healthcare & Pharmaceuticals | 7 | Weak | -17% | -2% |
| 1303 | BIOFILCHEM | Healthcare & Pharmaceuticals | 7 | Weak | -16% | -1% |
| 1302 | UNICHEMLAB | Healthcare & Pharmaceuticals | 7 | Weak | -4% | +11% |

## 2024-25 small-cap correction: 2024-09-16 → 2025-03-03

Ranked at the September 2024 peak; held through the fall.

Ranked 1,689 companies as of 2024-09-16 (bought at the 2024-09-17 close); 1,684 have a clean price path to 2025-03-03. NIFTY SMALLCAP 250: -25.8%. Spearman IC (score vs actual return): **+0.083**.

| portfolio (equal weight, buy and hold) | return | worst drawdown on the way |
|---|---|---|
| Top 50 by InvestIQ score | -21.4% | -29.0% |
| All ranked stocks | -25.9% | -27.2% |
| Bottom 50 | -26.4% | -27.1% |
| NIFTY SMALLCAP 250 | -25.8% | -26.1% |

**By score decile** (10 = highest scores)

| decile | stocks | avg return | median return | beat index | fell 30%+ | median worst drawdown |
|---|---|---|---|---|---|---|
| 10 | 169 | -24.1% | -28.4% | 45% | 49% | -40.3% |
| 9 | 168 | -21.4% | -26.5% | 49% | 42% | -37.4% |
| 8 | 168 | -25.3% | -29.0% | 42% | 45% | -39.0% |
| 7 | 169 | -22.9% | -28.3% | 46% | 47% | -36.1% |
| 6 | 168 | -28.2% | -30.4% | 35% | 51% | -38.3% |
| 5 | 168 | -25.3% | -27.1% | 48% | 45% | -37.5% |
| 4 | 169 | -27.8% | -30.2% | 37% | 51% | -38.1% |
| 3 | 168 | -26.6% | -32.3% | 39% | 55% | -38.5% |
| 2 | 168 | -29.0% | -31.9% | 33% | 57% | -38.0% |
| 1 | 169 | -28.3% | -31.2% | 34% | 54% | -39.6% |

**By label**

| growth_label | stocks | avg return | median return | beat index | fell 30%+ | median worst drawdown |
|---|---|---|---|---|---|---|
| Strong | 296 | -22.8% | -28.4% | 46% | 47% | -39.6% |
| Positive | 346 | -24.4% | -28.7% | 44% | 46% | -37.5% |
| Neutral | 431 | -26.3% | -29.0% | 42% | 48% | -37.7% |
| Weak | 611 | -27.9% | -31.3% | 36% | 54% | -38.9% |

**"Price already stretched" risk flag**

| flag | stocks | avg return | median return | beat index | fell 30%+ | median worst drawdown |
|---|---|---|---|---|---|---|
| flagged | 133 | -20.3% | -31.0% | 40% | 53% | -42.8% |
| not flagged | 1551 | -26.4% | -29.8% | 41% | 49% | -37.9% |

**Top 15 picks on 2024-09-16 and what happened**

| rank | company | sector | score | label | actual return | vs index |
|---|---|---|---|---|---|---|
| 1 | NAVA | Energy | 97 | Strong | -38% | -13% |
| 2 | NEULANDLAB | Healthcare & Pharmaceuticals | 96 | Strong | -18% | +7% |
| 3 | INDRAMEDCO | Healthcare & Pharmaceuticals | 96 | Strong | -25% | +1% |
| 4 | SUMMITSEC | Financial Services | 96 | Strong | -47% | -21% |
| 5 | KEEPLEARN | Services & Others | 95 | Strong | -41% | -16% |
| 6 | SUPRIYA | Healthcare & Pharmaceuticals | 95 | Strong | -7% | +19% |
| 7 | PGEL | Consumer & FMCG | 95 | Strong | +30% | +56% |
| 8 | PRIMESECU | Services & Others | 95 | Strong | -31% | -5% |
| 9 | GEOJITFSL | Financial Services | 95 | Strong | -54% | -28% |
| 10 | IIFLCAPS | Financial Services | 95 | Strong | -39% | -13% |
| 11 | DHUNINV | Financial Services | 94 | Strong | -41% | -15% |
| 12 | GOLDIAM | Consumer & FMCG | 94 | Strong | -3% | +23% |
| 13 | SUZLON | Industrials & Infrastructure | 94 | Strong | -39% | -13% |
| 14 | POCL | Metals, Mining & Chemicals | 94 | Strong | -45% | -19% |
| 15 | TRENT | Consumer & FMCG | 94 | Strong | -33% | -7% |

**Bottom 15 on 2024-09-16**

| rank | company | sector | score | label | actual return | vs index |
|---|---|---|---|---|---|---|
| 1689 | TAKE | Technology | 0 | Weak | -50% | -24% |
| 1688 | SECURKLOUD | Technology | 0 | Weak | -39% | -13% |
| 1687 | FUSION | Financial Services | 0 | Weak | -53% | -27% |
| 1686 | DISHTV | Services & Others | 0 | Weak | -55% | -29% |
| 1685 | ALOKINDS | Industrials & Infrastructure | 1 | Weak | -42% | -16% |
| 1684 | UNITECH | Industrials & Infrastructure | 1 | Weak | -39% | -14% |
| 1683 | TIJARIA | Industrials & Infrastructure | 2 | Weak | -37% | -11% |
| 1682 | PALREDTEC | Technology | 3 | Weak | -49% | -23% |
| 1681 | SEMAC | Industrials & Infrastructure | 4 | Weak | -16% | +10% |
| 1680 | J&KBANK | Financial Services | 4 | Weak | -11% | +15% |
| 1679 | NACLIND | Metals, Mining & Chemicals | 5 | Weak | +8% | +33% |
| 1678 | ARMANFIN | Financial Services | 5 | Weak | -29% | -3% |
| 1677 | VALIANTLAB | Healthcare & Pharmaceuticals | 5 | Weak | -33% | -7% |
| 1676 | UNIONBANK | Financial Services | 5 | Weak | -12% | +14% |
| 1675 | OSWALSEEDS | Services & Others | 5 | Weak | -58% | -32% |
