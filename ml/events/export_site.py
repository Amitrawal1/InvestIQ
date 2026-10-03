"""Export the events study to one JSON file the website backend serves (backend/data/events.json).

The study is history, not live data, so it ships as a static file instead of database tables:
    types        event types with counts and labels
    events       every event (newest first) with its sector / theme reactions per horizon
                 (return vs the average eligible stock, `rel`) and the whole-market move
    playbook     playbook_tables.csv rows (sector + theme level, 5d..126d, measure `rel`)
    validation   the headline verdict numbers (validate.py): what is priced in on day 0 vs later
    rules        the classifier's keyword rules (playbook.RULES / MENTION_RULES) for the backend's
                 headline classifier, so the site and the Python prototype classify the same way

Re-run after `python3 -m events.event_study` and `python3 -m events.validate`:
    cd ml && python3 -m events.export_site
"""

import json
import math
from pathlib import Path

import pandas as pd

from .playbook import MENTION_RULES, RULES, TYPE_LABELS

HERE = Path(__file__).resolve().parent
RESULTS = HERE / "results"
OUT = HERE.parent.parent / "backend" / "data" / "events.json"
HORIZONS = ["day0", "5d", "21d", "63d", "126d"]
PLAYBOOK_HORIZONS = ["21d", "63d", "126d"]


def _num(x, digits=4):
    if x is None or (isinstance(x, float) and math.isnan(x)):
        return None
    return round(float(x), digits)


def _events():
    ev = pd.read_csv(HERE / "events.csv", dtype=str).fillna("")
    er = pd.read_csv(RESULTS / "event_returns.csv")
    er = er[er["level"].isin(["all", "sector", "theme"])]
    out = []
    for e in ev.itertuples():
        rows = er[er["event_id"] == e.event_id]
        entry = rows["entry_date"].iloc[0] if len(rows) else None
        market = {}
        groups = {"sector": {}, "theme": {}}
        for h in HORIZONS:
            r = rows[rows["horizon"] == h]
            m = r[r["level"] == "all"]
            if len(m):
                market[h] = {"ret": _num(m["ret"].iloc[0]), "index_sc": _num(m["index_sc"].iloc[0]),
                             "index_n50": _num(m["index_n50"].iloc[0])}
            for lvl in ("sector", "theme"):
                g = r[r["level"] == lvl].sort_values("rel", ascending=False)
                if len(g):
                    groups[lvl][h] = [{"group": x.group, "rel": _num(x.rel), "n": int(x.n_stocks)} for x in g.itertuples()]
        out.append({
            "id": e.event_id, "date": e.date, "time_ist": e.time_ist or None, "entry_date": entry,
            "type": e.event_type, "type_label": TYPE_LABELS.get(e.event_type, e.event_type),
            "subtype": e.subtype or None, "stance": e.stance or None, "scope": e.scope, "surprise": e.surprise or None,
            "title": e.title, "description": e.description, "source_url": e.source_url, "source_kind": e.source_kind,
            "date_confidence": e.date_confidence, "confounders": e.confounders or None,
            "market": market, "sectors": groups["sector"], "themes": groups["theme"],
        })
    return sorted(out, key=lambda x: x["date"], reverse=True)


def _playbook():
    pb = pd.read_csv(RESULTS / "playbook_tables.csv")
    pb = pb[(pb["measure"] == "rel") & pb["level"].isin(["sector", "theme"]) & pb["horizon"].isin(PLAYBOOK_HORIZONS)
            & pb["subtype"].isna()]
    rows = []
    for r in pb.itertuples():
        rows.append({
            "type": r.event_type, "stance": r.stance if isinstance(r.stance, str) else None,
            "horizon": r.horizon, "level": r.level, "group": r.group, "n_events": int(r.n_events),
            "mean": _num(r.mean), "median": _num(r.median), "hit_rate": _num(r.hit_rate, 3),
            "ci_lo": _num(r.ci_lo), "ci_hi": _num(r.ci_hi), "mean_excess_sc": _num(r.mean_excess_sc),
            "placebo_p": _num(r.placebo_p, 3), "reliability": r.reliability,
            "best_event": r.best_event if isinstance(r.best_event, str) else None,
            "worst_event": r.worst_event if isinstance(r.worst_event, str) else None,
        })
    return rows


def _validation():
    t = pd.read_csv(RESULTS / "validation_targets_summary.csv")
    s = pd.read_csv(RESULTS / "validation_summary.csv")
    pooled = s[s["group_key"].astype(str).str.contains("ALL TYPES")][
        ["level", "horizon", "n_tested", "ic_playbook", "ic_any_event", "ic_usual", "ic_momentum", "p_vs_chance"]]
    return {
        "targets": json.loads(t.to_json(orient="records")),
        "pooled": json.loads(pooled.to_json(orient="records")),
        "verdict": ("Policy and geopolitical news is mostly priced in on the first trading day: the sector a "
                    "policy names moved the expected way about 72% of the time that day. From the next close on, "
                    "the historical pattern picked sector winners no better than chance over 1-6 months, and plain "
                    "sector momentum did better. These tables show what happened before, not a forecast."),
    }


def main():
    types = pd.read_csv(HERE / "events.csv")["event_type"].value_counts()
    data = {
        "built_from": "ml/events (event_study.py, validate.py)",
        "types": [{"id": k, "label": TYPE_LABELS.get(k, k), "count": int(v)} for k, v in types.items()],
        "events": _events(),
        "playbook": _playbook(),
        "validation": _validation(),
        "rules": [{"type": a, "subtype": b, "stance": c, "pattern": p} for a, b, c, p in RULES],
        "mention_rules": [{"group": g, "pattern": p} for g, p in MENTION_RULES.items()],
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(data, separators=(",", ":")))
    print(f"wrote {OUT} ({OUT.stat().st_size / 1e6:.1f} MB): {len(data['events'])} events, "
          f"{len(data['playbook'])} playbook rows, {len(data['rules'])} rules")


if __name__ == "__main__":
    main()
