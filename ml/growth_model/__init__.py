"""InvestIQ growth model: which small/mid companies beat the NIFTY SMALLCAP 250 over 6-12 months.

Modules:
    prices  - load daily closes/volumes from `stock_prices` + `index_prices` (cached locally)
    labels  - forward returns and "beat the benchmark" labels on the 1st/16th rebalance grid
    market_features - price/volume features per (company, signal date), point-in-time
    market_model    - walk-forward test + market_score (v1: blend of six trend signals)
"""
