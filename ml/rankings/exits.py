"""Intra-rebalance exit rules for the InvestIQ Top list: sell a holding between the 1st/16th rebuilds?

Problem (docs/model-report.md section 5.2 item 4, reports/PORTFOLIO.md): the shipped Top list
(portfolio.RECOMMENDED) has deep drawdowns (-38% max, deeper than the Smallcap 250 in the 2022 and
2024-25 windows' worst days) and individual blow-ups (about 1 in 5 "stretched" names fall 30%+ within
a year). An exit rule sells a holding as soon as its own price says the trend broke, instead of
waiting for the next rebuild (where it is only dropped once it ranks below 150).

Everything here is PRE-DECLARED: the rules below were written before any result was computed
(rankings/exits_eval.py tests them on the same simulator and scores as portfolio_eval.py). Thresholds
are round numbers that traders actually use (200-day average, -15/-20/-25% stops), not tuned.

Rules (RULES; a rule may combine several triggers, the first to fire wins):
    X0   none                       the shipped Top list
    X1   close < 200-day average, checked WEEKLY (last trading day of each week). Weekly, because the
         200-day average is slow and the price wanders across it for days around a turn: a daily check
         sells on the first noisy dip, a weekly check needs the break to hold to the week's close
         (the usual way this rule is run). Only a *fresh* break counts: the name must have closed at or
         above its average at least once since entry (a name bought below its average is not sold the
         next day for a fact the ranking already saw).
    X1d  X1 checked daily (the same rule without the weekly confirmation; robustness of the choice)
    X2   trailing stop: close <= 0.80 x the highest close since entry
    X2b  trailing stop at -25%
    X3   fixed stop: close <= 0.85 x the entry close
    X4   X1 or X2 (whichever fires first)
    X5   the best of X1-X4 (exits_eval.pick_best) + a sold name may not be re-bought at the next
         rebuild (it is eligible again from the one after); every other variant lets a sold name back
         in at the next rebuild if the normal Top-list rules pick it

Prices: `price_paths` is a wide frame of break-adjusted closes (dates x company_id, the last row is
the check close), i.e. the cumulative product of portfolio_eval.load_daily's returns, so splits and
data breaks (one-day > +100% / < -60%, growth_model/labels.py) do not trigger stops. "Entry" is the
close the position was first bought at (a holding kept across rebuilds keeps its first entry; a
re-bought name starts a new one).

`exit_signals(price_paths, holdings, entry_info, rule, week_end=True)` is pure: it only reads closes up
to the check date and returns {company_id: reason} for the holdings to sell. The caller trades at the
NEXT close (no same-day look-ahead).
"""

from dataclasses import dataclass

import numpy as np
import pandas as pd

MA_DAYS = 200


@dataclass(frozen=True)
class ExitRule:
    name: str
    text: str
    ma: str | None = None            # None, "daily", "weekly": sell on a fresh close below the MA_DAYS average
    trail: float | None = None       # sell when close <= (1 - trail) x highest close since entry
    stop: float | None = None        # sell when close <= (1 - stop) x entry close
    no_reentry: bool = False         # a sold name is not re-bought at the next rebuild

    @property
    def active(self):
        return bool(self.ma or self.trail or self.stop)


NONE = ExitRule("X0", "none (shipped Top list)")
RULES = [
    NONE,
    ExitRule("X1", "close < 200-day average (weekly check)", ma="weekly"),
    ExitRule("X1d", "close < 200-day average (daily check)", ma="daily"),
    ExitRule("X2", "trailing stop -20% from the high since entry", trail=0.20),
    ExitRule("X2b", "trailing stop -25% from the high since entry", trail=0.25),
    ExitRule("X3", "fixed stop -15% from entry", stop=0.15),
    ExitRule("X4", "X1 or X2, whichever first", ma="weekly", trail=0.20),
]
# X5 = pick_best(X1..X4) with no_reentry=True, built in exits_eval once the X1-X4 results exist.
CANDIDATES = ["X1", "X2", "X2b", "X3", "X4"]
BY_NAME = {r.name: r for r in RULES}


def ma_break(path, entry_pos, ma_days=MA_DAYS):
    """Fresh close below the moving average on the last row of `path` (1-d array of closes)?

    entry_pos = index of the entry close in `path`. True iff the last close < its ma_days average AND
    some close from entry to the day before was >= its own average."""
    t = len(path) - 1
    if t + 1 < ma_days or t <= entry_pos:
        return False
    lo = max(entry_pos, ma_days - 1)
    csum = np.concatenate([[0.0], np.cumsum(path[lo - ma_days + 1:t + 1])])
    ma = (csum[ma_days:] - csum[:-ma_days]) / ma_days                 # averages for rows lo..t
    closes = path[lo:t + 1]
    if not closes[-1] < ma[-1]:
        return False
    return bool((closes[:-1] >= ma[:-1]).any())


def exit_signals(price_paths, holdings, entry_info, rule, week_end=True):
    """-> {company_id: reason} of holdings whose exit rule fires on the last close of `price_paths`.

    price_paths  DataFrame (dates x company_id) of break-adjusted closes up to the check date, or a
                 dict company_id -> 1-d array of closes ending on the check date (same calendar)
    holdings     iterable of company_id held at the check close
    entry_info   {company_id: {"entry_pos": row of the entry close in price_paths}}; optional
                 "entry_price" / "peak" override the values read from the path
    rule         ExitRule
    week_end     True if the check close is the last trading day of its week (weekly MA check)
    """
    if not rule.active:
        return {}
    out = {}
    for c in holdings:
        info = entry_info.get(c)
        if info is None:
            continue
        path = np.asarray(price_paths[c], dtype=float)
        e = int(info["entry_pos"])
        if e >= len(path) - 1:                 # bought on this close: nothing to check yet
            continue
        px = path[-1]
        entry = info.get("entry_price", path[e])
        if rule.stop and px <= (1 - rule.stop) * entry:
            out[c] = "stop"
            continue
        if rule.trail:
            peak = info.get("peak", np.nanmax(path[e:]))
            if px <= (1 - rule.trail) * peak:
                out[c] = "trail"
                continue
        if rule.ma and (rule.ma == "daily" or week_end) and ma_break(path, e):
            out[c] = "ma200"
    return out


def week_ends(calendar):
    """Boolean array: True on the last trading day of each ISO week of `calendar` (a DatetimeIndex).

    Uses the trading calendar one day ahead (is tomorrow a new week?), which the exchange publishes in
    advance; no prices are looked ahead."""
    iso = calendar.isocalendar()
    key = (iso["year"].astype(int) * 100 + iso["week"].astype(int)).values
    return np.r_[key[1:] != key[:-1], True]
