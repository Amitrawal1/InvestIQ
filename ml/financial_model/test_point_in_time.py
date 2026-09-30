"""Unit checks for the point-in-time join (no network, no DB).

    python3 -m financial_model.test_point_in_time            # synthetic cases
    python3 -m financial_model.test_point_in_time --panel    # also the full cached training panel

Synthetic company: Q1 (period 2023-06-30) filed 2023-08-10, Q2 (2023-09-30) filed 2023-11-10,
then a late filing of Q1's revision on 2023-12-20 (older period filed after a newer one) and Q3
(2023-12-31) filed 2024-02-10. Checks:
  - a signal date before the first filing sees nothing
  - a filing is not visible on its own filing day until the next signal date (midnight rule)
  - the late-filed older period never replaces a newer visible period
  - financials older than 275 days are marked stale
  - check_point_in_time rejects a panel that uses a future filing
"""

import sys

import pandas as pd

from .data import asof_join, check_point_in_time


def _features():
    rows = [
        (1, "AAA", "2023-08-10 17:00", "2023-06-30", 1.0),
        (1, "AAA", "2023-11-10 18:30", "2023-09-30", 2.0),
        (1, "AAA", "2023-12-20 12:00", "2023-06-30", 9.0),     # late re-filing of an older period
        (1, "AAA", "2024-02-10 16:00", "2023-12-31", 3.0),
    ]
    f = pd.DataFrame(rows, columns=["company_id", "symbol", "filing_date", "period_end", "x"])
    f["filing_date"] = pd.to_datetime(f["filing_date"])
    f["period_end"] = pd.to_datetime(f["period_end"])
    return f


def run_synthetic():
    dates = ["2023-08-01", "2023-08-10", "2023-08-16", "2023-11-16", "2024-01-01", "2024-02-16", "2024-12-01"]
    keys = pd.DataFrame({"company_id": 1, "signal_date": pd.to_datetime(dates)})
    out = asof_join(keys, _features()).set_index("signal_date")
    x = out["x"]
    assert pd.isna(x["2023-08-01"]), "nothing is public before the first filing"
    assert pd.isna(x["2023-08-10"]), "a filing made during D is only visible from the next signal date"
    assert x["2023-08-16"] == 1.0
    assert x["2023-11-16"] == 2.0
    assert x["2024-01-01"] == 2.0, "a late-filed older period must not replace a newer one"
    assert x["2024-02-16"] == 3.0
    assert bool(out.loc["2024-12-01", "fin_stale"]), "period 2023-12-31 is > 275 days old on 2024-12-01"
    assert not bool(out.loc["2024-02-16", "fin_stale"])
    check_point_in_time(out.reset_index())

    bad = out.reset_index()
    bad.loc[0, "filing_date"] = bad.loc[0, "signal_date"] + pd.Timedelta(days=1)
    bad.loc[0, "period_end"] = bad.loc[0, "signal_date"] - pd.Timedelta(days=30)
    try:
        check_point_in_time(bad)
    except AssertionError:
        pass
    else:
        raise AssertionError("check_point_in_time accepted a future filing")
    print("synthetic point-in-time checks: OK")


def run_panel():
    from .data import build_panel
    panel, stats = build_panel()
    check_point_in_time(panel)
    lag = (panel["signal_date"] - panel["filing_date"]).dt.days
    print(f"panel point-in-time check: OK ({len(panel):,} rows; filing_date <= signal_date everywhere; "
          f"median age of the filing used {lag.median():.0f} days)")


if __name__ == "__main__":
    run_synthetic()
    if "--panel" in sys.argv:
        run_panel()
