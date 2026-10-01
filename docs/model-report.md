# InvestIQ model report: results, failures, fixes and next steps

Last updated: 2026-10-01. Live model: `investiq-v1` (rankings snapshot of 2026-09-30).

**Verdict in one line:** the model works as a *filter* (it reliably separates weak companies from strong
ones and fell less than the market in normal crashes), but it is only *average* as a *stock picker*
(its top 50 don't reliably beat the NIFTY Smallcap 250), and it is *weak at market turning points*.

---

## 1. What the model is

Every NSE-listed company (EQ/BE series) gets a growth score from 0 to 100 on the 1st and 16th of each
month:

```
growth_score = 0.95 x [ 0.70 x market model  +  0.30 x financial model ]  +  0.05 x news
               - red-flag penalties
```

| Part | What it measures | Code |
|---|---|---|
| Market model (`market-trend6-v1`) | Price trend vs NIFTY Smallcap 250: distance from 52-week high, vs 200-day and 50-day averages, 3m and 6m relative return, few down days | `ml/growth_model/market_model.py` |
| Financial model (`fin-v1`) | Growth, profitability, balance-sheet health and cash-flow quality from XBRL filings, point-in-time | `ml/financial_model/` |
| Banks, NBFCs, insurers | NII, NIM, credit cost, NPAs, CET1, ROA/ROE, solvency vs their own peer group (shown as reasons/risks; score is trend-led) | `ml/financials/fin_sector_features.py` |
| News | NSE announcements every 15 min, FinBERT sentiment and importance (small fixed weight: too little history to test) | `ml/news_pipeline/` |
| Combiner | Weights, penalties, labels, ranks, reasons and risks | `ml/rankings/build_v3.py` |

Penalties: negative equity −6; for lenders, worsening asset quality −4 and capital near the regulatory
minimum −6. Risk text only (no score change): "price already stretched" (up >100% in 6m or 60%+ above
the 200-day average) and "profit growth off a small base" (>300%).

Coverage: 2,020 of 2,525 companies ranked (Financial Services: 170 of 243).

---

## 2. Results

### 2.1 Walk-forward test (averages over 2019-2026)

Each year is scored with a model fitted only on earlier years, then compared with the next 6 and 12
months. IC = rank correlation between score and later return vs the index (0 = no skill; above 0.05 is
useful for stock ranking).

| Method | 6m IC | 12m IC | 12m top-10% minus bottom-10% |
|---|---|---|---|
| Financial statements only | 0.040 | 0.033 | +1.1% |
| Old live score `prelim-v2` (80% financial) | 0.052 | 0.057 | +7.9% |
| **`investiq-v1` (70% trend / 30% financial)** | **0.065** | **0.097** | **+16.0%** |
| Price trend only | 0.061 | 0.102 | +19.3% |

### 2.2 Time machine: rank on a past date, check what really happened

`python3 -m rankings.time_machine --events` (full tables and names: `ml/rankings/reports/TIME_MACHINE.md`).
Top 50 = equal-weight buy-and-hold of the 50 highest scores, bought at the next day's close.

| Window | IC | Top 50 | All ranked stocks | Smallcap 250 | Verdict |
|---|---|---|---|---|---|
| 1 year ago (Sep 2025 → Sep 2026) | **+0.18** | +4.1% | +0.6% | **+5.9%** | Ranks well; top 50 beat the average stock, not the index |
| COVID crash (Jan → Mar 2020) | **+0.29** | **−33%** | −40% | −39% | Protected in the crash |
| COVID crash + rebound (1 year) | +0.06 | **+69%** | +40% | +20% | Strong |
| Post-COVID rally (Apr 2020 → Apr 2021) | **−0.19** | +101% | **+111%** | +95% | Fails at the bottom: junk led the rebound |
| 2022 rate-hike sell-off | +0.06 | −11% | **−5%** | −15% | Beat the index, deeper drawdown (−34%) |
| 2024-25 small-cap correction | +0.08 | **−21%** | −26% | −26% | Protected |
| 2018 small-cap crash | — | — | — | — | Not testable: no financial growth data before 2019 |

Last year by label: Strong +8.4% average, Positive +8.0%, Neutral +0.9%, Weak −7.1%. Bottom 50: −20.5%.

### 2.3 Scorecard

| Job | Grade | Evidence |
|---|---|---|
| Avoiding losers | **Good** | Lowest-score decile the worst in 4 of 6 windows and second-worst in a 5th; bottom 50 −20.5% last year |
| Ranking (ordering) | **Good** | IC positive in 5 of 6 windows, 0.18 last year |
| Protecting in normal crashes | **Good** | Top 50 fell less than the index in COVID and 2024-25 |
| Beating the index with the top 50 | **Average** | Beat it in 5 of 6 windows, but not last year (+4.1% vs +5.9%) |
| Smoothness (drawdowns) | **Weak** | Top 50 drew down more than the index last year and in 2022 |
| Market turning points | **Weak** | IC −0.19 when ranked at the COVID bottom |

---

## 3. What failed, and why

| # | Failure | Why it happened | How it was solved |
|---|---|---|---|
| 1 | Old live score weighted 80% on financials | Assumed fundamentals predict returns best | Walk-forward showed financial statements alone are weak (IC 0.04, 2020 broke every financial signal). Switched to 70% trend / 30% financial: ranking power roughly doubled |
| 2 | XGBoost lost to simple blends (market and financial) | Too many features let it memorise a few market regimes (e.g. the 2020 rebound) | Kept transparent equal-weight blends of signals that worked in most years; ML kept only as a comparison |
| 3 | A "smarter" data-selected financial blend lost | Trained on 2018-19 only, it picked margin/quality features that reversed in 2020-21 | Shipped the tested baseline; re-test the blend once more years exist |
| 4 | Banks/NBFCs/insurers unranked (236 of 243 Financial Services) | Parser and features only handled non-financial filings | New parser block and features (NII, NIM, NPAs, CET1, solvency); trend-led score with peer-group reasons and lender penalties. 170 of 243 now ranked |
| 5 | Bank financials didn't predict returns (lending NBFCs ranked backwards) | 2022-23 PSU-bank re-rating rewarded weak balance sheets; small sample | Not used for the score; used for reasons/risks and penalties (asset-quality flag did work: flagged banks trailed by ~9% over 6m) |
| 6 | Top picks looked risk-free (GANDHAR #1 with zero risks after +110% in 6 months) | Trend model rewards stocks that already ran; risks only covered weak trends | Added "price already stretched" and "small-base profit" risk text, from data: ~1 in 5 such stocks fell 30%+ within a year vs 1 in 6 others |
| 7 | Four of five red-flag penalties hurt ranking | Flags like "receivables outpacing revenue" pointed the wrong way on average | Only negative equity (and the lender flags) keep a penalty; the rest are risk text |
| 8 | No balance sheets before Sep 2022 | XBRL filings/parser gap | Open: ROE, ROCE, debt only exist from late 2022 (see 4.3) |
| 9 | Bad price candles (fake 1000x returns) | Placeholder prices, unadjusted relistings | One-day moves > +100% / < −60% treated as data breaks |
| 10 | CI couldn't rank banks | Their data came from a local file | `fin_sector_extract` DB table, identical output verified in a clean environment |
| 11 | Survivorship bias | `stock_prices` only has companies listed today | Not solved; every result is somewhat optimistic. Comparisons between methods are still fair |

---

## 4. How to improve (best ideas, in priority order)

Each idea must pass the same walk-forward and time-machine tests before it ships.

### 4.1 Highest impact

1. **Market-regime switch (fixes the turning-point failure).** After a deep market fall (e.g. Smallcap
   250 down >25% from its high, or fewer than 30% of stocks above their 200-day average), trend
   signals reverse for months ("momentum crash"). In that regime, cut the trend weight (e.g. 70% → 40%)
   and lean on financial quality and cheapness until breadth recovers. Test: the Post-COVID window should
   stop being negative without hurting the others.

2. **Better portfolio rules for the top list (fixes "top 50 trailed the index" and the drawdowns).**
   - Minimum liquidity: ~₹5 crore traded per day (tiny, jumpy stocks hurt the equal-weight top 50).
   - Sector cap: at most ~20% of the list from one sector.
   - Risk-adjusted trend: rank trend divided by volatility, so smooth risers beat wild ones.
   - Turnover buffer: keep a holding until it drops below rank ~100, instead of swapping every 15 days.

3. **"Early Movers" list (enter before the stretch).** Tested pattern: a stock near its 52-week high but
   up less than 30% in 6 months (a base breakout) had the best typical outcome (median −0.6% vs −7.9%
   for all stocks) and half the crash rate (9% vs 20% for stretched stocks). Adding accelerating growth,
   widening margins and cash conversion cut the crash rate to ~4% (small sample since 2020). Ship as a
   separate tab, not a replacement for the score.

### 4.2 Medium impact

4. **Exit rules, tested.** Compare no exit vs "close below the 200-day average" vs "−20% from entry".
   Aim: lower the 30%+ crash rate of the top list without giving up the winners.
5. **Live track record.** Every published snapshot is stored, so run the time machine on each one as it
   ages and show a public "how our picks did" page. Honest, and it catches decay early.
6. **Valuation.** The model never asks whether a stock is cheap or expensive (P/E, P/B vs sector and its
   own history). Valuation helps most exactly where trend fails (after crashes).
7. **Earnings surprise and estimate drift.** Result-day price reaction and the size of growth vs the
   last few quarters are among the strongest known short-term signals, and the data already exists.

### 4.3 Data fixes (make every model better)

8. **Balance sheets before 2022:** find why `financial_filings` has none before Sep 2022 (parser or
   source). Four more years of ROE/ROCE/debt history for training and testing.
9. **Delisted companies:** add historical prices of delisted names to remove survivorship bias.
10. **Banks:** collect standalone filings (9 large banks report NPA only there) and INDUSINDBK.
11. **Sector/industry cleanup:** a few companies are misclassified (e.g. Chennai Petroleum).

### 4.4 Operations

12. Schedule the daily price collector (it is manual today).
13. Move the Upstox token request to Vercel Cron (GitHub's schedule ran 6+ hours late).

### 4.5 Later features (not started)

- Short-term (3-6 month) event analysis: wars, policies, budgets → which sectors benefit.
- IPO analysis: is the valuation reasonable vs financials, peers and market conditions.

---

## 5. How to reproduce

```bash
cd ml
python3 -m growth_model.market_model          # market model walk-forward
python3 -m financial_model.train              # financial model walk-forward (+ point-in-time checks)
python3 -m financials.fin_sector_eval         # banks / NBFCs / insurers evaluation
python3 -m rankings.combiner_eval             # combiner weights walk-forward
python3 -m rankings.time_machine --events     # time-machine and stress windows
python3 -m rankings.build_v3 --date YYYY-MM-DD [--publish]
```

Caveats for every number above: survivorship bias (today's company list), price returns before costs,
taxes and dividends, and short history (6-8 test years, one of them extreme).
