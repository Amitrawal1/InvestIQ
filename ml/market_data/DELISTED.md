# Delisted companies: removing survivorship bias from the backtests

Last updated: 2026-10-02. Code: `ml/market_data/delisted.py` (sources, list, prices, loaders, DDL),
`ml/market_data/delisted_eval.py` (survivorship estimate). Nothing here writes to the database unless
you run `upload --yes` yourself.

## Problem

`stock_prices` is filled from Upstox for companies in `companies`, i.e. companies listed **today**.
Every company that left NSE since 2016 (delisted, suspended, merged, liquidated) is missing from every
backtest (`growth_model/labels.py`, `rankings/combiner_eval.py`, `time_machine.py`, `portfolio_eval.py`).
They are mostly the blow-ups.

## Sources (tested 2026-10-02, all public, no login)

| Source | URL | What it gives | Verdict |
|---|---|---|---|
| Upstox v3 historical candles | `api.upstox.com/v3/historical-candle/NSE_EQ\|<ISIN>/...` | Nothing for delisted ISINs: `400 UDAPI100011 Invalid Instrument key` (tested DHFL, HEXAWARE, BHUSANSTL, JETAIRWAYS, ALOKTEXT, ABGSHIP, on both `NSE_EQ` and `BSE_EQ`; RELIANCE works) | **Dead end** |
| NSE delisted list | `nsearchives.nseindia.com/content/equities/delisted.csv` | 329 rows: symbol, name, delisting date, type (voluntary / compulsory / liquidation). **NSE stopped updating it in Nov 2020** and it has no mergers or suspensions | Used for the exit **reason** only |
| NSE listed today | `nsearchives.nseindia.com/content/equities/EQUITY_L.csv` | Current EQ list with ISIN | Used with `companies` to decide who is gone |
| NSE CM bhavcopy (daily) | `≤ 2024-07-05`: `nsearchives.nseindia.com/content/historical/EQUITIES/YYYY/MON/cmDDMONYYYYbhav.csv.zip`; `≥ 2024-07-08` (UDiFF): `nsearchives.nseindia.com/content/cm/BhavCopy_NSE_CM_0_0_0_YYYYMMDD_F_0000.csv.zip` | Every symbol traded that day, with ISIN, series, OHLC, volume, value. 404 on holidays. 75 KB/day (old), 179 KB/day (UDiFF) | **Primary source** for the list and for the full backfill |
| NSE security-wise history API | `www.nseindia.com/api/historicalOR/generateSecurityWiseHistoricalData?from=DD-MM-YYYY&to=...&symbol=X&type=priceVolumeDeliverable&series=EQ` | Daily rows of one symbol, **works for delisted symbols**. Needs the home-page cookies; ≤ ~70 rows per call (so 90-day windows); one series per call (`series=ALL` returns the company's NCDs too and they eat the row cap) | Used for the 20-name sample |

Checks: on the 117 overlapping rows (13 names, 10 days in June 2019) bhavcopy and the history API give
**identical** closes and volumes. `www.nseindia.com/robots.txt` allows everything except `/market-data-test`;
`nsearchives` has no robots.txt. All requests are throttled to one every 2 s with a browser User-Agent.

**Prices are raw.** Neither bhavcopy `PREVCLOSE` nor the API adjusts on ex-dates (RELIANCE 1:1 bonus,
2017-09-07: PREVCLOSE 1645.4, close 818.1). `adjust_closes` detects splits/bonuses from the overnight
ratio (open / previous close within 6% of 1/2, 1/3, 1/4, 1/5, 1/10, 2/3, 2/5, on a day ≤ 7 calendar days
after the previous trade; every circuit band is ≤ 20%, so such a drop is a corporate action) and
back-adjusts. Check against Upstox (RELIANCE 2016-2026): both bonuses found, adjusted closes match Upstox
to 0.01%. The one remaining 4.9% gap before July 2023 is the Jio Financial **demerger**, which Upstox
adjusts and we don't (see Risks).

## The list: `delisted_companies.csv`

Built from **monthly bhavcopy snapshots** (first trading day of each month, 2016-01 → 2026-10, 130 files,
12 MB): every company ISIN (`INE…`; ETFs trade in EQ with `INF…` ISINs and are excluded) seen in series
EQ/BE/BZ, minus everything listed today (ISIN or symbol in `companies` or `EQUITY_L.csv` or today's
bhavcopy). A symbol still listed under a new ISIN (face-value split) is not an exit.

**535 companies left NSE's main board between 2016 and today**; 350 of them were already listed in Jan 2016.

| Exits per year | 2016 | 2017 | 2018 | 2019 | 2020 | 2021 | 2022 | 2023 | 2024 | 2025 | 2026 |
|---|---|---|---|---|---|---|---|---|---|---|---|
| companies | 38 | 50 | 47 | 56 | 42 | 70 | 48 | 59 | 44 | 44 | 37 |

| `exit_kind` | n | ≥ 90% below 2016+ peak at exit | median last close / peak | last close < ₹5 |
|---|---|---|---|---|
| `suspended_bz` (last seen in BZ = trade-for-trade for non-compliance) | 143 | 88 | 0.07 | 118 |
| `liquidation` (delisted.csv) | 32 | 9 | 0.22 | 25 |
| `compulsory_delisting` (delisted.csv) | 30 | 1 | 0.52 | 25 |
| `voluntary_delisting` (delisted.csv) | 21 | 3 | 0.59 | 7 |
| `unknown` (mergers, schemes, IBC resolutions, capital reductions; everything after Nov 2020) | 309 | 35 | 0.89 | 82 |
| **total** | **535** | **136 (25%)** | | **257** |

277 (52%) exited ≥ 50% below their peak; 208 (39%) within 30% of it (mostly mergers: HDFC, MINDTREE, IDFC…).
`distress = 1` for liquidation / compulsory / BZ. Of the 252 delisted.csv rows dated 2016+, 82 are in the
list; the other 170 never traded on EQ/BE/BZ after 2016 (long-suspended shells) and don't matter for a backtest.

Side finding: 45 companies trade today in EQ/BE but are missing from `companies` (AONESTEELS, ADROITIND,
ANNU, ESDS…). They are a separate gap in `stock_prices`, not handled here.

## Price coverage

* Monthly closes: all 535 (by construction); 484 have at least one 12-month window with entry ≥ ₹1.
* Daily, sample: **20 / 20** names have full daily history 2016 → exit via the history API (550 requests
  incl. the RELIANCE control, 18.7 min, 11.7 MB) → `delisted_prices_sample.csv` (27,689 rows).
* Daily, everyone: the bhavcopy backfill below. Coverage should be ~100%: bhavcopy is NSE's own record
  of every traded day. BZ names trade only on some days (AMTEKAUTO: 694 days in 3.25 years); labels
  already allow stale prices for 5 days at entry and 10 days at exit.

## Sample outcomes (daily, adjusted, 2016-01-01 → last trade)

| Symbol | Kind | Last trade | First → last | From peak | Worst 12m |
|---|---|---|---|---|---|
| DHFL | unknown (IBC 2021, equity extinguished) | 2021-06-11 | −93% | −98% | −95% |
| RELCAPITAL | unknown (IBC) | 2024-02-12 | −97% | −99% | −98% |
| SREINFRA | unknown (IBC) | 2023-08-11 | −97% | −98% | −88% |
| SINTEX | unknown (IBC) | 2023-02-10 | −98% | −98% | −95% |
| JPINFRATEC | unknown (IBC) | 2023-03-06 | −90% | −95% | −86% |
| LAKSHVILAS | unknown (merged into DBS, equity written off) | 2020-11-25 | −92% | −96% | −86% |
| JETAIRWAYS | suspended_bz (liquidation ordered Nov 2024) | 2024-11-07 | −96% | −96% | −94% |
| AMTEKAUTO | suspended_bz | 2019-04-01 | −95% | −95% | −88% |
| GITANJALI | suspended_bz | 2019-04-01 | −98% | −99% | −99% |
| VIDEOIND | suspended_bz | 2021-06-15 | −94% | −94% | −90% |
| ABGSHIP | liquidation | 2019-05-15 | −98% | −98% | −88% |
| GTOFFSHORE | liquidation | 2017-07-18 | −81% | −81% | −77% |
| UBHOLDINGS | liquidation | 2018-02-12 | −65% | −83% | −79% |
| ORBITCORP | compulsory_delisting | 2018-02-05 | −77% | −80% | −81% |
| ALOKTEXT | unknown (capital reduction + new ISIN, now ALOKINDS) | 2020-01-30 | −48% | −50% | −62% |
| HEXAWARE | voluntary_delisting | 2020-10-30 | +94% | −8% | −39% |
| POLARIS | voluntary_delisting | 2018-07-24 | +124% | −0% | −26% |
| HDFC | unknown (merged into HDFCBANK) | 2023-07-12 | +116% | −9% | −24% |
| MINDTREE | unknown (merged into LTIM) | 2022-11-22 | +376% | −31% | −41% |
| IDFC | unknown (merged into IDFCFIRSTB) | 2024-10-09 | +123% | −17% | −70% |

**14 of 20 ended ≥ 80% below their peak, 11 of them ≥ 90%**; ALOKTEXT −50% (capital reduction); the other 5 are mergers / buy-outs at good prices.

## Survivorship effect

### Full list, monthly method (`delisted_eval.py`, part 1)

Every EQ/BE/BZ company on the first trading day of each month (entry ≥ ₹1), 12-month return to the
snapshot 12 months later, minus NIFTY SMALLCAP 250; 118 windows, 195,618 rows, of which 19,108 (9.8%)
belong to departed companies (3,653 rows exit inside the window). The method is checked against the
real labels on survivors: correlation 0.978, mean 12m return 21.1% vs 23.7% in the labels (unadjusted
bonuses/demergers; the same noise hits both groups).

Terminal value for a company that left inside the window: **last** = last monthly close; **distress** = 0
for liquidation / compulsory / BZ; **collapse** = distress + 0 for any exit ≤ 20% of its 3-year peak.

| 12m excess vs SC250 | survivors only (today's backtests) | + departed, last | + departed, distress | + departed, collapse |
|---|---|---|---|---|
| mean | **+4.6%** | +2.6% | +2.0% | +1.9% |
| median | −9.8% | −11.2% | −11.3% | −11.4% |
| beat rate | 40.1% | 38.9% | 38.7% | 38.7% |
| rows with return ≤ −90% | 0.12% | 0.24% | 0.89% | 1.05% |
| departed rows alone: mean / median excess | | −16% / −27% | −22% / −30% | −23% / −31% |

**Survivorship inflates the market universe's mean 12-month excess return by about 2.0-2.7 percentage
points (median by 1.4-1.6 pp).** In the liquid subset (≥ ₹0.5 cr traded on the snapshot day) the effect is
about half: +1.0 pp mean, +0.6 pp median.

**It also hides skill at the bottom.** 6-month momentum (the core of the market model) vs 12m return,
mean per-date rank IC: **0.073 survivors only → 0.101 with departed names**; top-minus-bottom decile
spread **15.0 pp → 20.8 pp**. The companies that disappear were mostly in the bottom decile, so today's
backtests understate how well a trend-led score avoids losers. The model report's statement that
"comparisons between methods are still fair" holds only if all methods rank the departed names alike;
trend-led methods probably gain most from fixing this. Re-run the evals after the backfill.

### Sample through the real label pipeline (`delisted_eval.py`, part 2)

`build_labels` on `stock_prices` + the 20 sample names (1,995 extra 12m rows, 0.6% of all):

| 12m | baseline | + sample, last close | + sample, 0 for distress | + sample, 0 for distress or collapse |
|---|---|---|---|---|
| mean excess, all rows | 8.78% | 8.62% | 8.57% | 8.55% |
| sample rows: mean / median excess | | −17.5% / −29.4% | −25.3% / −36.7% | −28.3% / −37.0% |
| sample rows ≤ −90% | | 3.9% | 13.2% | 17.3% |

The pooled shift is tiny because 20 names are 0.6% of rows; the full backfill adds ~10% of rows (as in
the monthly method).

## Design: how they enter the pipeline without touching the website

* Two **separate** tables, `delisted_companies` and `delisted_prices` (DDL below, also in
  `delisted.py` as `DELISTED_COMPANIES_SQL` / `DELISTED_PRICES_SQL`). The website and the collector only
  read `companies` / `stock_prices`, so the names can never appear on the site, in rankings or in the
  Predictor. No flag in `companies`, because every backend query would need to filter it.
* Backtest loaders opt in:
  * `growth_model.prices.load_prices(include_delisted=True, delisted_source="local"|"db")` appends the
    delisted prices with **negative `company_id` (= −delisted_companies.id)**, so ids never collide.
    They are appended after the pickle cache is read/written, so `growth_stock_prices.pkl` stays
    survivors-only.
  * `growth_model.labels.build_labels(..., terminal=...)`: for a delisted company, after its last trade
    the exit price is a terminal value (`delisted.terminal_prices`): last close for mergers / voluntary
    delistings, `distress_value × last close` (default 0) for liquidation, compulsory delisting, BZ
    suspension, or a last close ≤ 20% of its 3-year peak. The break detector runs on real closes only,
    so a terminal 0 is not mistaken for a data break.
  * CLI: `python3 -m growth_model.labels --include-delisted [--distress-value 0] [--delisted-source db]`
    writes `growth_labels_delisted.pkl`; it never overwrites `growth_labels.pkl`.
* **Default behaviour is byte-identical**: `build_labels(load_prices())` gives sha256
  `9f25f235a8c11ab27ff53d10142ad22f733cd90db62c4475b2085434bc5695b4` over `pd.util.hash_pandas_object`
  (389,352 × 31, 261 breaks) and the same prices hash (`484b7f47…`) before and after the change.
* The rankings evals (`ml/rankings/*`) were not touched. To use the delisted names there, call
  `load_prices(include_delisted=True)` and pass `terminal=` to `build_labels`; companies with negative
  ids have no financials, so they enter only market-model / price-based tests unless their XBRL is
  fetched by ISIN too.

```sql
CREATE TABLE IF NOT EXISTS delisted_companies (
    id INT NOT NULL AUTO_INCREMENT PRIMARY KEY,
    symbol VARCHAR(32) NOT NULL,
    isin VARCHAR(12) NOT NULL,
    name VARCHAR(255) NULL,
    first_seen DATE NULL,
    last_traded DATE NULL,
    last_series VARCHAR(4) NULL,
    last_close DECIMAL(14,4) NULL,
    nse_delisted_date DATE NULL,
    nse_delisting_type VARCHAR(64) NULL,
    exit_kind VARCHAR(32) NOT NULL,
    distress TINYINT(1) NOT NULL DEFAULT 0,
    source VARCHAR(255) NULL,
    UNIQUE KEY uq_delisted_isin (isin),
    KEY idx_delisted_symbol (symbol)
);

CREATE TABLE IF NOT EXISTS delisted_prices (
    delisted_id INT NOT NULL,            -- delisted_companies.id; backtests use company_id = -delisted_id
    price_date DATE NOT NULL,
    series VARCHAR(4) NULL,
    open_price DECIMAL(14,4) NULL,
    high_price DECIMAL(14,4) NULL,
    low_price DECIMAL(14,4) NULL,
    close_price DECIMAL(14,4) NULL,      -- raw, as traded
    prev_close DECIMAL(14,4) NULL,
    adj_close DECIMAL(18,6) NULL,        -- split/bonus adjusted (what the backtests use)
    volume BIGINT NULL,
    PRIMARY KEY (delisted_id, price_date)
);
```

## Backfill commands (run from `ml/`)

| # | Command | Time | Writes |
|---|---|---|---|
| 1 | `caffeinate -i python3 -m market_data.delisted list` | ~1 min (snapshots cached), ~5 min cold | `data/raw/delisted/delisted_companies.csv`, `bhav_monthly.csv.gz`, `nse_delisted.csv`, `nse_equity_l.csv`; `SELECT isin, symbol FROM companies` only |
| 2 | `caffeinate -i python3 -m market_data.delisted backfill --from 2016-01-01 --to 2026-10-01` | **~95-100 min** (~2,800 weekday requests at one every 2 s; holidays are a quick 404) | ~2,560 zips, **~260 MB** in `data/raw/bhavcopy/YYYY/` (now git-ignored); `data/raw/delisted/delisted_prices.csv.gz` (~0.5M rows, adjusted). Resumable: cached zips are not downloaded again. Measured: 10 days in 0.3 min, 0.5 MB |
| 3 | `python3 -m growth_model.labels --include-delisted` | ~10 s | `data/processed/growth_labels_delisted.pkl` (local `delisted_prices.csv.gz` is picked up automatically; falls back to the sample) |
| 4 | `python3 -m market_data.delisted_eval` | ~1 min | `data/raw/delisted/delisted_eval.json` (re-run to replace the monthly estimate with daily numbers) |
| 5 | (optional, **DB write**) `python3 -m market_data.delisted upload --yes` | ~5-10 min (~100 batches of 5,000) | creates `delisted_companies` + `delisted_prices` and upserts; nothing else. Then use `--delisted-source db` |

Smaller test first: `python3 -m market_data.delisted backfill --from 2019-06-03 --to 2019-06-14 --max-files 10 --out /tmp/bf.csv.gz`.
To add new sample names: `python3 -m market_data.delisted sample --symbols DHFL ... --controls RELIANCE`
(~40 s per name, overwrites `delisted_prices_sample.csv`).

## Risks and limits

* **Terms of use.** The NSE website/archives are published for public download, but NSE's website terms
  restrict automated access and commercial reuse of its data. Redistribution or commercial display needs
  an NSE data licence. Here the data is used only offline in backtests and never shown on the site;
  keep it that way, keep the 2 s throttle, and read nseindia.com's Terms of Use before running the
  backfill on a schedule. The per-symbol API is undocumented, needs cookies and may change or block
  without notice. The bhavcopy archive is the stable route.
* **Demergers are not adjusted** (RELIANCE/Jio Financial −4.9%; SINTEX 2017 −75%, which the labels'
  −60% break rule turns into NaN). Bonuses smaller than 1:2 (e.g. 1:4 → 0.8) are inside the circuit
  band and stay unadjusted. Upstox adjusts both, so delisted names are slightly harsher than survivors.
* **Exit reason after Nov 2020 is unknown** (delisted.csv is stale). The `collapse` price rule
  stands in for it, but it is a judgement call: an IBC resolution usually extinguishes equity (DHFL,
  Reliance Capital, Lakshmi Vilas), while a merger pays out at the last price. `--distress-value` lets
  you test the sensitivity.
* **Capital reductions with a new ISIN** (ALOKTEXT → ALOKINDS, MONNETISPA) count as exits. That is correct
  for the old shareholders. The continuation is in `stock_prices` as a new listing whose Upstox history
  may start at the new ISIN.
* **Symbol renames** inside the departed set (26 ISINs have more than one symbol) are handled by ISIN in
  the bhavcopy route; the per-symbol API only fetches the last symbol.
* The monthly estimate uses unadjusted month-start closes and the last monthly close as the exit price
  (up to a month early). The daily backfill removes both.
* `ml/data/raw/` is not git-ignored (`.gitignore` line 2 reads `ml/data/raw/git `, which looks like a
  typo), so commit `4e1ad5f0` included 151 cached bhavcopy zips and the delisted CSVs. `.gitignore` now ignores
  `ml/data/raw/bhavcopy/` and `delisted_prices.csv.gz`; run `git rm -r --cached ml/data/raw/bhavcopy` to
  untrack the zips already committed.
