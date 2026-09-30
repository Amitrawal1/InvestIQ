"""InvestIQ Financial Model: which non-financial small/mid companies beat the NIFTY SMALLCAP 250,
judged from their financial statements alone (point-in-time, walk-forward tested).

Modules:
    data   - point-in-time panel: features.py rows joined as-of filing_date onto the label grid
    model  - candidate scores: prelim-v2 financial blend (baseline), transparent blend, XGBoost
    train  - walk-forward test, winner rule, final fit, meta + latest scores (python3 -m financial_model.train)
    score  - score every eligible company as of a date (python3 -m financial_model.score --date --out)
    test_point_in_time - no-look-ahead checks
"""
