"""Baseline stock-direction model (XGBoost) for InvestIQ.

Modules:
    config    - horizons, windows, split fractions, model params
    data      - load / clean / validate stock_prices and financial_statements
    features  - price + point-in-time fundamental features, target
    modeling  - time-based split, training, evaluation, importance
"""
