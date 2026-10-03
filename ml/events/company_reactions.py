"""Company level: do the same stocks react the same way to repeated events of one type?

For each event group with >= 8 events (e.g. war escalations, RBI cuts, budgets), every eligible
stock's return E -> E+h minus its sector's mean ("within-sector reaction") is recorded. Time-split
test, no look-ahead: for event k, a stock's "event beta" = its mean within-sector reaction over
earlier events of the group whose window had closed (needs >= 3); IC = Spearman correlation
between that and the stock's reaction to event k, across all stocks. Baseline: the stock's own
within-sector return over the previous h days (momentum).

If the event beta does not beat chance and momentum, it is NOT shown as a 'companies likely to
benefit' list. A research list (`research_list`) is then only "what reacted most before", joined
with the latest investiq-v1 score for context, and labelled as history.

CLI: cd ml && python3 -m events.company_reactions   -> results/company_validation.csv,
                                                       results/company_reactions_<group>.csv
"""

import numpy as np
import pandas as pd
from scipy.stats import spearmanr

from .event_study import (HORIZONS, RESULTS, build_panel, entry_and_ref, forward_returns, load_companies,
                          load_events)
from .validate import _signflip_p

GROUPS = [("war_geopolitics", "escalation"), ("monetary_policy", "easing"), ("monetary_policy", "tightening"),
          ("fiscal_budget", None), ("global_macro", None), ("sector_policy", "support"),
          ("regulation", None), ("election", None)]
MIN_PRIOR = 3


def stock_reactions(events, panel, companies, h):
    cal = panel["cal"]
    sector = companies.set_index("company_id")["sector"].reindex(panel["px_ff"].columns)
    out = {}
    for ev in events.itertuples():
        e, _ = entry_and_ref(ev.date, ev.time_ist, cal)
        if e is None:
            continue
        ei = cal.get_loc(e)
        fr = forward_returns(panel, ei, h)
        if fr is None:
            continue
        within = fr - fr.groupby(sector).transform("mean")
        # momentum baseline: within-sector return over the previous h days
        mom = None
        if ei - h >= 130:
            fb = forward_returns(panel, ei - h, h)
            mom = fb - fb.groupby(sector).transform("mean")
        out[ev.event_id] = (ei, within.where(sector.notna()), mom)
    return out


def main():
    events = load_events()
    panel = build_panel()
    companies = load_companies()
    rows = []
    for hz in ("21d", "63d"):
        h = HORIZONS[hz]
        R = stock_reactions(events, panel, companies, h)
        for et, stance in GROUPS:
            sel = events[(events.event_type == et) & ((events.stance == stance) if stance else True)]
            ids = [i for i in sel.event_id if i in R]
            ids.sort(key=lambda i: R[i][0])
            for k, eid in enumerate(ids):
                ek, real, mom = R[eid]
                prior = [j for j in ids[:k] if R[j][0] + h <= ek]
                if len(prior) < MIN_PRIOR:
                    continue
                M = pd.concat([R[j][1] for j in prior], axis=1)
                beta = M.mean(axis=1).where(M.notna().sum(axis=1) >= MIN_PRIOR)
                j = pd.concat([beta, real], axis=1, keys=["b", "r"]).dropna()
                ic = spearmanr(j.b, j.r).statistic if len(j) > 50 else np.nan
                icm = np.nan
                if mom is not None:
                    jm = pd.concat([mom, real], axis=1, keys=["m", "r"]).dropna()
                    icm = spearmanr(jm.m, jm.r).statistic if len(jm) > 50 else np.nan
                rows.append({"horizon": hz, "group": f"{et}{':' + stance if stance else ''}", "event_id": eid,
                             "n_prior": len(prior), "n_stocks": len(j), "ic_event_beta": ic, "ic_momentum": icm})
            # full-history reactions for the research list (history only)
            M = pd.concat({i: R[i][1] for i in ids}, axis=1)
            tab = pd.DataFrame({"mean_within_sector": M.mean(axis=1), "n_events": M.notna().sum(axis=1),
                                "hit_rate": (M > 0).sum(axis=1) / M.notna().sum(axis=1)})
            tab = tab[tab.n_events >= 5].join(companies.set_index("company_id")[["symbol", "name", "sector"]])
            key = f"{et}{'_' + stance if stance else ''}_{hz}"
            tab.sort_values("mean_within_sector", ascending=False).to_csv(RESULTS / f"company_reactions_{key}.csv")
    V = pd.DataFrame(rows)
    V.to_csv(RESULTS / "company_validation_events.csv", index=False)
    S = V.groupby(["horizon", "group"]).agg(n_tested=("ic_event_beta", "count"), ic_event_beta=("ic_event_beta", "mean"),
                                            ic_momentum=("ic_momentum", "mean")).reset_index()
    S["p_vs_chance"] = [(_signflip_p(V[(V.horizon == r.horizon) & (V.group == r.group)].ic_event_beta)) for r in S.itertuples()]
    for hz, d in V.groupby("horizon"):
        S.loc[len(S)] = {"horizon": hz, "group": "ALL (pooled)", "n_tested": d.ic_event_beta.count(),
                         "ic_event_beta": d.ic_event_beta.mean(), "ic_momentum": d.ic_momentum.mean(),
                         "p_vs_chance": _signflip_p(d.ic_event_beta)}
    S.to_csv(RESULTS / "company_validation.csv", index=False)
    pd.set_option("display.width", 200)
    print(S.round(3).to_string())


if __name__ == "__main__":
    main()


def latest_scores():
    """Latest investiq-v1 snapshot (DB SELECT): company_id, growth_score, growth_label, rank_overall."""
    from news_pipeline.db import get_connection
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute("""SELECT company_id, snapshot_date, growth_score, growth_label, rank_overall FROM company_rankings
                       WHERE model_version = 'investiq-v1'
                         AND snapshot_date = (SELECT MAX(snapshot_date) FROM company_rankings
                                              WHERE model_version = 'investiq-v1')""")
        return pd.DataFrame(cur.fetchall(), columns=["company_id", "snapshot_date", "growth_score", "growth_label",
                                                     "rank_overall"])
    finally:
        conn.close()


def research_list(group_key, sector=None, horizon="63d", top=10, min_events=8, scores=None):
    """'Companies to research' = HISTORY ONLY: stocks that reacted most (vs their sector) after past
    events of this group, among those with a current investiq-v1 label of Positive/Strong.
    The time-split test (company_validation.csv) found no reliable persistence, so this must be shown
    as 'reacted strongly before', never as 'will benefit'."""
    t = pd.read_csv(RESULTS / f"company_reactions_{group_key}_{horizon}.csv")
    t = t[t.n_events >= min_events]
    if sector:
        t = t[t.sector == sector]
    s = latest_scores() if scores is None else scores
    t = t.merge(s, on="company_id", how="left")
    t["growth_score"] = t["growth_score"].astype(float)
    t = t[t.growth_label.isin(["Strong", "Positive"])]
    return t.sort_values("mean_within_sector", ascending=False).head(top)[
        ["symbol", "name", "sector", "n_events", "mean_within_sector", "hit_rate", "growth_score", "growth_label",
         "rank_overall", "snapshot_date"]]
