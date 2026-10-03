"""Does the playbook learned on EARLIER events predict sector winners for LATER events of the same type?

For every event k of a group (event type, or type+stance), in date order:
    train     = earlier events of the same group whose outcome window had fully closed before k's entry
                day (entry_j + h trading days <= entry_k): strictly no look-ahead. Needs >= 3.
    predict   = each group's (sector/theme) mean `rel` over the training events
    realised  = each group's `rel` after event k
    score     = Spearman rank IC across groups, and the realised spread top-3 minus bottom-3 picks
Baselines, all point-in-time at k's entry day:
    momentum      each group's `rel` over the previous h trading days (ends at entry; known)
    usual         each group's average forward `rel` over ALL past days whose window had closed
                  ("what this sector normally does"), from the daily panels
    any_event     mean `rel` over ALL earlier closed events of ANY type (is the TYPE informative?)
    chance        IC 0; p-value from a sign-flip test of the per-event ICs
Leave-one-out (LOO) is also reported: train on every other event of the group, past and future.
It is optimistic (uses the future regime) and is shown only as an upper bound.

CLI: cd ml && python3 -m events.validate    -> results/validation_*.csv and a printed summary
"""

import argparse

import numpy as np
import pandas as pd
from scipy.stats import spearmanr

from growth_model.prices import CACHE_DIR

from .event_study import HORIZONS, RESULTS, build_panel, load_events
from .playbook import GROUPINGS

MIN_TRAIN = 3
TOPK = 3


def _ic(pred, real):
    j = pd.concat([pred, real], axis=1, keys=["p", "r"]).dropna()
    if len(j) < 5 or j["p"].nunique() < 2:
        return np.nan, np.nan
    ic = spearmanr(j["p"], j["r"]).statistic
    top = j.nlargest(TOPK, "p")["r"].mean()
    bot = j.nsmallest(TOPK, "p")["r"].mean()
    return ic, top - bot


def _signflip_p(x, n=20000, seed=3):
    x = np.asarray([v for v in x if not np.isnan(v)])
    if len(x) < 3:
        return np.nan
    rng = np.random.default_rng(seed)
    signs = rng.choice([-1, 1], size=(n, len(x)))
    sims = (signs * x).mean(axis=1)
    return float((np.abs(sims) >= abs(x.mean())).mean())


def run(level="sector", horizon="63d", er=None, daily=None, cal=None, events=None):
    h = HORIZONS[horizon]
    er = er[(er.level == level) & (er.horizon == horizon)].copy()
    er["entry_date"] = pd.to_datetime(er["entry_date"])
    pos = {d: i for i, d in enumerate(cal)}
    er["entry_i"] = er["entry_date"].map(pos)
    wide = er.pivot_table(index="event_id", columns="group", values="rel")
    meta = er.drop_duplicates("event_id").set_index("event_id")[["entry_date", "entry_i", "event_type", "stance"]]
    meta = meta.loc[wide.index].sort_values("entry_i")
    dpanel = daily[level]["rel"]
    dpos = np.array([pos[d] for d in dpanel.index])
    rows = []
    for et, stance in GROUPINGS(events):
        sel = meta[(meta.event_type == et) & ((meta.stance == stance) if stance else True)]
        for k, (eid, m) in enumerate(sel.iterrows()):
            ek = m.entry_i
            closed = sel[(sel.entry_i + h) <= ek]
            real = wide.loc[eid]
            rec = {"group_key": f"{et}{':' + stance if stance else ''}", "event_type": et, "stance": stance or "",
                   "event_id": eid, "entry_date": m.entry_date.date(), "n_train": len(closed)}
            if len(closed) >= MIN_TRAIN:
                rec["ic_playbook"], rec["spread_playbook"] = _ic(wide.loc[closed.index].mean(), real)
                # baselines
                any_closed = meta[(meta.entry_i + h) <= ek]
                rec["ic_any_event"], rec["spread_any_event"] = _ic(wide.loc[any_closed.index].mean(), real)
                past = dpanel[(dpos + h) <= ek]
                rec["ic_usual"], rec["spread_usual"] = _ic(past.mean(), real) if len(past) > 60 else (np.nan, np.nan)
                # momentum: rel over the previous h days = forward rel measured from day ek - h
                mom_day = ek - h
                mom_rows = dpanel[dpos == mom_day]
                rec["ic_momentum"], rec["spread_momentum"] = (_ic(mom_rows.iloc[0], real) if len(mom_rows)
                                                              else (np.nan, np.nan))
            others = sel.drop(index=eid)
            if len(others) >= MIN_TRAIN:
                rec["ic_loo"], rec["spread_loo"] = _ic(wide.loc[others.index].mean(), real)
            rows.append(rec)
    return pd.DataFrame(rows)


def summarise(v):
    out = []
    # pooled = base types only (type:stance rows repeat the same events)
    for key, d in list(v.groupby("group_key")) + [("ALL TYPES (pooled)", v[v.stance.fillna("") == ""])]:
        rec = {"group_key": key, "n_events": len(d), "n_tested": int(d["ic_playbook"].notna().sum())}
        for col in ("playbook", "any_event", "usual", "momentum", "loo"):
            x = d[f"ic_{col}"].dropna()
            rec[f"ic_{col}"] = x.mean() if len(x) else np.nan
            rec[f"spread_{col}"] = d[f"spread_{col}"].dropna().mean() if len(x) else np.nan
        x = d["ic_playbook"].dropna()
        rec["share_ic_pos"] = (x > 0).mean() if len(x) else np.nan
        rec["p_vs_chance"] = _signflip_p(x)
        diff = (d["ic_playbook"] - d["ic_usual"]).dropna()
        rec["p_vs_usual"] = _signflip_p(diff)
        out.append(rec)
    return pd.DataFrame(out)


def targets(er, daily, cal, n_draws=2000, window=63, seed=5):
    """A-priori targets (event_targets.csv, written from the event text before looking at the
    group's outcome): did the named group move the expected way? Sign-adjusted `rel` per horizon,
    day-0 reaction, and a placebo p-value (random entry days within +-63 trading days)."""
    from .event_study import HERE
    tg = pd.read_csv(HERE / "event_targets.csv")
    rng = np.random.default_rng(seed)
    pos = {d: i for i, d in enumerate(cal)}
    rows = []
    for t in tg.itertuples():
        d = er[(er.event_id == t.event_id) & (er.level == t.level) & (er.group == t.group)]
        rec = {"event_id": t.event_id, "group": t.group, "expected_sign": t.expected_sign, "rationale": t.rationale}
        for hz in ("day0", "5d", "21d", "63d", "126d"):
            x = d[d.horizon == hz]["rel"]
            rec[f"adj_{hz}"] = float(x.iloc[0]) * t.expected_sign if len(x) else np.nan
            if hz in daily and len(x):
                panel = daily[hz][t.level]["rel"]
                if t.group in panel.columns:
                    e = pos[pd.Timestamp(d["entry_date"].iloc[0])]
                    dates = panel.index
                    ip = dates.searchsorted(cal[e])
                    lo, hi = max(0, ip - window), min(len(dates) - 1, ip + window)
                    sims = panel[t.group].to_numpy()[rng.integers(lo, hi + 1, n_draws)] * t.expected_sign
                    rec[f"placebo_mean_{hz}"] = float(np.nanmean(sims))
        rows.append(rec)
    T = pd.DataFrame(rows)
    summ = []
    for hz in ("day0", "5d", "21d", "63d", "126d"):
        x = T[f"adj_{hz}"].dropna()
        rec = {"horizon": hz, "n": len(x), "hit_rate": (x > 0).mean(), "mean_adj_rel": x.mean(),
               "median_adj_rel": x.median(), "p_signflip": _signflip_p(x)}
        if f"placebo_mean_{hz}" in T:
            base = T.loc[x.index, f"placebo_mean_{hz}"]
            rec["placebo_mean"] = base.mean()
            rec["p_vs_placebo"] = _signflip_p((x - base).dropna())
        summ.append(rec)
    return T, pd.DataFrame(summ)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.parse_args(argv)
    er = pd.read_csv(RESULTS / "event_returns.csv")
    events = load_events()
    cal = build_panel()["cal"]
    allsum = []
    for horizon in ("21d", "63d", "126d"):
        daily = pd.read_pickle(CACHE_DIR / f"events_daily_{HORIZONS[horizon]}.pkl")
        for level in ("sector", "theme"):
            v = run(level, horizon, er, daily, cal, events)
            v.insert(0, "level", level)
            v.insert(1, "horizon", horizon)
            v.to_csv(RESULTS / f"validation_events_{level}_{horizon}.csv", index=False)
            s = summarise(v)
            s.insert(0, "level", level)
            s.insert(1, "horizon", horizon)
            allsum.append(s)
    S = pd.concat(allsum, ignore_index=True)
    dailies = {hz: pd.read_pickle(CACHE_DIR / f"events_daily_{HORIZONS[hz]}.pkl") for hz in ("21d", "63d", "126d")}
    T, TS = targets(er, dailies, cal)
    T.to_csv(RESULTS / "validation_targets_events.csv", index=False)
    TS.to_csv(RESULTS / "validation_targets_summary.csv", index=False)
    print(TS.round(3).to_string())
    S.to_csv(RESULTS / "validation_summary.csv", index=False)
    pd.set_option("display.width", 250)
    pd.set_option("display.max_columns", 30)
    pd.set_option("display.max_rows", 200)
    cols = ["level", "horizon", "group_key", "n_events", "n_tested", "ic_playbook", "share_ic_pos", "p_vs_chance",
            "ic_any_event", "ic_usual", "ic_momentum", "p_vs_usual", "ic_loo", "spread_playbook", "spread_usual"]
    print(S[cols].round(3).to_string())


if __name__ == "__main__":
    main()
