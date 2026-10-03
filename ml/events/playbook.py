"""Pure functions over the event-study output: the historical playbook and a headline classifier.

    playbook(event_type, stance=None, subtype=None, horizon="63d", level="sector", measure="rel")
        -> one row per sector/industry/theme: n_events, mean, median, hit rate, sign-test p,
           bootstrap 95% CI, and a plain-language reliability label.
    classify(text) -> {"event_type", "subtype", "stance", "confidence", "matched", "mentioned_groups",
                       "historical_playbook": [...]}

Impacts are NEVER generated from the text: `classify` only decides which event type a headline is,
and the sectors it returns come from what happened after past events of that type (the playbook),
plus the groups the text explicitly names ("mentioned_groups"), kept separate.

Both functions read ml/events/results/event_returns.csv unless a DataFrame is passed in.
"""

import re
from functools import lru_cache
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.stats import binomtest

HERE = Path(__file__).resolve().parent
EVENT_RETURNS = HERE / "results" / "event_returns.csv"

TYPE_LABELS = {
    "war_geopolitics": "War / geopolitics",
    "monetary_policy": "Monetary policy (RBI)",
    "fiscal_budget": "Fiscal / budget / tax",
    "sector_policy": "Sector policy",
    "regulation": "Regulation",
    "election": "Election",
    "commodity_shock": "Commodity shock",
    "global_macro": "Global macro (Fed, trade war, US)",
    "pandemic": "Pandemic",
    "financial_stress": "Financial stress",
}
MIN_EVENTS_FOR_TABLE = 3


PLAYBOOK_TABLES = HERE / "results" / "playbook_tables.csv"


@lru_cache(maxsize=1)
def _load_default():
    return pd.read_csv(EVENT_RETURNS)


@lru_cache(maxsize=1)
def _load_tables():
    """Precomputed playbooks WITH placebo p-values (written by event_study); None if absent."""
    return pd.read_csv(PLAYBOOK_TABLES, keep_default_na=False, na_values=[""]) if PLAYBOOK_TABLES.exists() else None


def stored_playbook(event_type, stance=None, horizon="63d", level="sector"):
    """The placebo-checked playbook table from results/playbook_tables.csv (preferred for display)."""
    t = _load_tables()
    if t is None:
        return pd.DataFrame()
    t = t[(t.event_type == event_type) & (t.horizon == horizon) & (t.level == level)]
    t = t[t.stance.fillna("") == (stance or "")]
    return t.sort_values("mean", ascending=False).reset_index(drop=True)


def _bootstrap_ci(x, n=2000, seed=11):
    x = np.asarray(x, dtype=float)
    x = x[~np.isnan(x)]
    if len(x) < 3:
        return (np.nan, np.nan)
    rng = np.random.default_rng(seed)
    means = rng.choice(x, size=(n, len(x)), replace=True).mean(axis=1)
    return float(np.percentile(means, 2.5)), float(np.percentile(means, 97.5))


def reliability(n, sign_p, ci_lo, ci_hi, placebo_p=None):
    """Plain-language label. Deliberately strict.

    anecdotal            fewer than 5 events
    event-specific       the move is unusual even compared with random dates in the same months
                         (placebo p < 0.05, CI excludes 0, >= 8 events) -- 'weak' if only placebo
                         p < 0.10 plus CI or sign test
    trend, not event     the group moved this way after the events, but it moved the same way on
                         random nearby dates too (placebo p >= 0.10): a background trend
    no reliable pattern  otherwise
    """
    if n < 5:
        return "anecdotal (fewer than 5 events)"
    excludes_zero = (ci_lo > 0) or (ci_hi < 0)
    directional = excludes_zero or sign_p < 0.10
    has_placebo = placebo_p is not None and not (isinstance(placebo_p, float) and np.isnan(placebo_p))
    if not has_placebo:
        return "pattern (placebo not run)" if directional else "no reliable pattern"
    if excludes_zero and placebo_p < 0.05 and n >= 8:
        return "event-specific"
    if directional and placebo_p < 0.10:
        return "event-specific (weak)"
    if directional:
        return "trend, not event"
    return "no reliable pattern"


def filter_events(er, event_type, stance=None, subtype=None, horizon="63d", level="sector"):
    sub = er[(er.event_type == event_type) & (er.horizon == horizon) & (er.level == level)]
    if stance:
        sub = sub[sub.stance.isin(stance.split("|"))]
    if subtype:
        sub = sub[sub.subtype.isin(subtype.split("|"))]
    return sub


def playbook(event_type, stance=None, subtype=None, horizon="63d", level="sector", measure="rel",
             event_returns=None, min_events=MIN_EVENTS_FOR_TABLE):
    """Which groups did better/worse after past events of this type?

    measure: 'rel' (vs the average eligible stock: sector rotation), 'excess_sc' (vs NIFTY SMALLCAP
    250) or 'excess_n50' (vs NIFTY 50). Rows sorted by mean, best first."""
    er = _load_default() if event_returns is None else event_returns
    sub = filter_events(er, event_type, stance, subtype, horizon, level)
    if sub.empty:
        return pd.DataFrame()
    rows = []
    for g, d in sub.groupby("group"):
        x = d[measure].dropna()
        n = len(x)
        if n < min_events:
            continue
        wins = int((x > 0).sum())
        p = binomtest(wins, n, 0.5).pvalue if n else np.nan
        lo, hi = _bootstrap_ci(x)
        best = d.loc[x.idxmax()]
        worst = d.loc[x.idxmin()]
        rows.append({
            "event_type": event_type, "stance": stance or "", "subtype": subtype or "",
            "horizon": horizon, "level": level, "measure": measure, "group": g,
            "n_events": n, "mean": x.mean(), "median": x.median(), "hit_rate": wins / n,
            "sign_p": p, "ci_lo": lo, "ci_hi": hi,
            "mean_excess_sc": d["excess_sc"].mean(), "hit_excess_sc": float((d["excess_sc"] > 0).mean()),
            "mean_excess_n50": d["excess_n50"].mean(), "hit_excess_n50": float((d["excess_n50"] > 0).mean()),
            "abn_vol": d["abn_vol"].median(), "avg_members": d["n_stocks"].mean(),
            "best_event": f"{best.event_id} ({best[measure]:+.1%})",
            "worst_event": f"{worst.event_id} ({worst[measure]:+.1%})",
        })
    t = pd.DataFrame(rows)
    if t.empty:
        return t
    t["reliability"] = [reliability(r.n_events, r.sign_p, r.ci_lo, r.ci_hi) for r in t.itertuples()]
    return t.sort_values("mean", ascending=False).reset_index(drop=True)


def GROUPINGS(events, min_stance_events=4):
    """(event_type, stance) keys to tabulate: every type, plus type+stance with enough events."""
    keys = [(t, None) for t in sorted(events.event_type.unique())]
    for (t, s), n in events.groupby(["event_type", "stance"]).size().items():
        if n >= min_stance_events and events[events.event_type == t].stance.nunique() > 1:
            keys.append((t, s))
    return keys


def add_bh_qvalues(pb, p_col="sign_p"):
    """Benjamini-Hochberg q-values within each (horizon, level): many sectors x types are tested."""
    pb = pb.copy()
    pb["bh_q"] = np.nan
    for _, idx in pb.groupby(["horizon", "level"]).groups.items():
        p = pb.loc[idx, p_col].to_numpy()
        order = np.argsort(p)
        m = len(p)
        q = np.empty(m)
        prev = 1.0
        for rank, i in reversed(list(enumerate(order, start=1))):
            prev = min(prev, p[i] * m / rank)
            q[i] = prev
        pb.loc[idx, "bh_q"] = q
    if "placebo_p" in pb:
        pb["reliability"] = [reliability(r.n_events, r.sign_p, r.ci_lo, r.ci_hi, getattr(r, "placebo_p", None))
                             for r in pb.itertuples()]
    return pb


# --------------------------------------------------------------------------------- classifier
# Ordered rules: (event_type, subtype, stance, regex). First matching type wins, but every match is
# reported. Patterns are lower-case and matched on word boundaries where it matters.

RULES = [
    ("fiscal_budget", "union_budget", "neutral", r"union budget|interim budget|budget (speech|20\d\d)"),
    # monetary policy (RBI)
    ("monetary_policy", "rbi_rate", "tightening", r"\brbi\b.{0,40}(hike|rais|increas)|off-cycle hike"),
    ("monetary_policy", "rbi_rate", "easing", r"\brbi\b.{0,40}(cut|reduc|lower)\w*.{0,30}(rate|repo|bp|basis)|off-cycle cut"),
    ("monetary_policy", "rbi_rate", "tightening", r"(repo rate|policy rate|repo).{0,60}(increas|hike|rais)|(hike|rais|increas)\w*.{0,40}repo"),
    ("monetary_policy", "rbi_rate", "easing", r"(repo rate|policy rate|repo).{0,60}(reduc|cut|lower)|(cut|reduc|lower)\w*.{0,40}repo"),
    ("monetary_policy", "rbi_liquidity", "easing", r"\b(crr|cash reserve ratio)\b.{0,60}(reduc|cut|lower)"),
    ("monetary_policy", "rbi_rate", "hold", r"monetary policy (statement|committee)|\bmpc\b"),
    # regulation
    ("regulation", "consumer_credit", "tighten", r"risk weights?|unsecured (consumer )?(credit|loans)"),
    ("regulation", "capital_markets", "tighten", r"\bsebi\b.{0,80}(derivative|f&o|futures|options|lot size|expiry)|index derivatives|\bstt\b"),
    ("regulation", "online_gaming", "tighten", r"online (money )?gam(e|ing)|casino"),
    ("regulation", "banking", "tighten", r"stressed assets|moratorium on (the )?bank|supersed\w+ the board"),
    ("regulation", "telecom", "tighten", r"\bagr\b|adjusted gross revenue"),
    # fiscal / tax
    ("fiscal_budget", "union_budget", "neutral", r"union budget|interim budget|budget (speech|20\d\d)"),
    ("fiscal_budget", "tax_reform", "tax_down", r"\bgst\b.{0,80}(reduc|cut|rationali|slab|lower)|corporate tax.{0,40}(cut|reduc)|income tax relief"),
    ("fiscal_budget", "stimulus", "spend_up", r"(economic|relief|stimulus) package|lakh crore package|atma ?nirbhar"),
    ("fiscal_budget", "tax_reform", "tax_up", r"(surcharge|cess|excise|customs duty|capital gains).{0,40}(increas|hike|rais|impos)"),
    ("fiscal_budget", "demonetisation", "shock", r"demoneti[sz]ation|legal tender"),
    # sector policy
    ("sector_policy", "pli", "support", r"production[- ]linked incentive|\bpli\b"),
    ("sector_policy", "defence", "support", r"indigeni[sz]ation list|defence (procurement|acquisition|export|fdi)|positive list|\bdac\b|import embargo"),
    ("sector_policy", "semiconductors", "support", r"semiconductor|\bfab\b|\bosat\b"),
    ("sector_policy", "ev", "support", r"electric vehicle|\bev\b|\bfame\b|pm e-drive"),
    ("sector_policy", "renewables", "support", r"green hydrogen|rooftop solar|solar (module|power|park)|renewable energy|non-fossil|wind energy|net[- ]zero"),
    ("sector_policy", "agri_trade", "restrict", r"export (ban|prohibit\w*)|prohibit\w* .{0,40}export|\b(free|restricted) to .?prohibited"),
    ("sector_policy", "steel_trade", "restrict", r"export duty.{0,40}(steel|iron ore)|(steel|iron ore).{0,40}export duty"),
    ("sector_policy", "oil_tax", "restrict", r"windfall|special additional excise duty|\bsaed\b"),
    ("sector_policy", "sugar_ethanol", "restrict", r"(sugarcane|cane) juice|ethanol.{0,40}(ban|restrict|cap)"),
    ("sector_policy", "banking", "support", r"recapitali[sz]ation|amalgamation of .{0,40}banks|bank(s)? merger"),
    ("sector_policy", "telecom_auto", "support", r"telecom (reform|relief)|spectrum (dues|moratorium)"),
    ("sector_policy", "infrastructure", "support", r"infrastructure pipeline|gati shakti|capital expenditure|\bcapex\b"),
    # war / geopolitics
    ("war_geopolitics", "india_pakistan", "de_escalation", r"ceasefire|cease-fire|de-?escalat|truce"),
    ("war_geopolitics", "india_pakistan", "escalation", r"\b(terror|terrorist) attack|surgical strike|air ?strike|operation sindoor|\bloc\b|pakistan"),
    ("war_geopolitics", "india_china", "escalation", r"\bgalwan\b|\blac\b|china border|chinese troops"),
    ("war_geopolitics", "middle_east", "escalation", r"\biran\b|\bisrael\b|hormuz|hamas|houthi|red sea"),
    ("war_geopolitics", "war_abroad", "escalation", r"\binvasion\b|\binvade|\bwar\b|missile|military operation|airstrikes?"),
    # global macro
    ("global_macro", "trade_war", "restrict", r"tariffs?|trade war|reciprocal duty"),
    ("global_macro", "fed_rate", "tightening", r"(federal reserve|\bfomc\b|\bfed\b).{0,60}(rais|hike|increas)"),
    ("global_macro", "fed_rate", "easing", r"(federal reserve|\bfomc\b|\bfed\b).{0,60}(cut|lower|reduc)"),
    ("global_macro", "china_stimulus", "easing", r"(china|pboc|beijing).{0,60}(stimulus|rate cut|rrr)"),
    ("global_macro", "us_election", "uncertain", r"(us|u\.s\.|american) (presidential )?election"),
    # commodity / pandemic / stress / elections
    ("commodity_shock", "oil_up", "supply_cut", r"\bopec\b.{0,60}(cut|reduc)|oil (supply|output) (cut|disrupt)|brent.{0,30}(surge|spike|jump)"),
    ("commodity_shock", "oil_down", "price_war", r"oil price war|crude.{0,30}(crash|plunge|collapse)"),
    ("global_macro", "us_macro", "risk_off", r"\bbrexit\b|jackson hole|\bpowell\b|payrolls|us cpi|downgrades? (the )?us\b|yen carry"),
    ("commodity_shock", "oil_up", "supply_cut", r"\bopec\b|abqaiq|saudi.{0,40}(oil|attack)|crude (futures|oil).{0,30}(negative|spike|surge)"),
    ("financial_stress", "bank_failure", "shock", r"placed under moratorium|\bmoratorium\b|bank fails|\bfails\b|hindenburg|short[- ]sell|defaults?\b|\bcrash\b"),
    ("pandemic", "covid", "shock", r"pandemic|lockdown|covid|coronavirus|variant|outbreak|\bwho\b declares"),
    ("financial_stress", "bank_failure", "shock", r"bank (failure|collapse|run)|placed under moratorium|default(ed|s)? on|short[- ]seller report|fraud"),
    ("election", "general", "pro_incumbent", r"(lok sabha|general|assembly|state) election|exit polls?|election results?|counting of votes|\b(bjp|nda|congress|upa)\b.{0,40}(wins?|loses|sweeps|majority)"),
]

# Groups a text can NAME directly (kept separate from historical effects)
MENTION_RULES = {
    "Defence": r"defen[cs]e|military|armed forces|\bdrdo\b|warship|missile",
    "PSU banks": r"public sector banks?|\bpsbs?\b|psu banks?",
    "Oil marketing (OMCs)": r"\bomcs?\b|oil marketing|petrol|diesel",
    "Upstream oil & gas": r"crude (oil )?produc|\bongc\b|upstream",
    "Sugar & ethanol": r"sugar|ethanol",
    "Rice exporters": r"\brice\b|basmati",
    "Capital-market intermediaries": r"broker|exchange|derivative|f&o|depositor(y|ies)",
    "Gaming": r"gaming|casino",
    "Steel & iron ore": r"\bsteel\b|iron ore",
    "Telecom operators": r"telecom|spectrum",
    "Automakers": r"automobile|vehicle|\bauto\b|two-wheeler|car\b",
    "Cement": r"cement",
    "Real estate developers": r"real estate|housing|realty",
    "Retail NBFCs & HFCs": r"\bnbfcs?\b|consumer credit|personal loans?|housing finance",
    "Power PSUs & lenders": r"\bpower\b|electricity|transmission",
    "Renewables": r"solar|renewable|green hydrogen|\bwind\b",   # not "windfall"
    "Infra & rail EPC": r"infrastructure|railway|roads?|highway|capex",
    "Pharma majors": r"pharma|drug|medicine|\bapi\b",
    "Technology": r"\bit services\b|software|semiconductor|electronics",
}


def classify(text, event_returns=None, horizon="63d", top=5):
    """Map a headline / press-release text to an event type and the groups that, historically,
    did best and worst after events of that type. Keyword rules only; returns 'unclassified' when
    nothing matches. Never invents an impact: if the playbook has too few events it says so."""
    s = (text or "").lower()
    matches = []
    for etype, sub, stance, pat in RULES:
        if re.search(pat, s):
            matches.append((etype, sub, stance))
    mentioned = [g for g, pat in MENTION_RULES.items() if re.search(pat, s)]
    if not matches:
        return {"event_type": "unclassified", "subtype": None, "stance": None, "confidence": 0.0,
                "matched": [], "mentioned_groups": mentioned, "historical_playbook": [],
                "note": "No rule matched; route to manual review."}
    etype, sub, stance = matches[0]
    agree = sum(1 for m in matches if m[0] == etype) / len(matches)
    confidence = round(min(1.0, 0.5 + 0.25 * (len(matches) > 1) * agree + 0.25 * agree), 2)
    hist = []
    note = ""
    try:
        st = stance
        pb = stored_playbook(etype, st, horizon) if event_returns is None else pd.DataFrame()
        if pb.empty and event_returns is None:
            st = None
            pb = stored_playbook(etype, None, horizon)
        if pb.empty:
            er = _load_default() if event_returns is None else event_returns
            st = stance if stance in set(er[er.event_type == etype].stance) else None
            pb = playbook(etype, stance=st, horizon=horizon, level="sector", event_returns=er)
            if pb.empty:
                st = None
                pb = playbook(etype, horizon=horizon, level="sector", event_returns=er)
        if not pb.empty:
            pick = pd.concat([pb.head(top), pb.tail(top)]).drop_duplicates("group")
            hist = [{"group": r.group, "mean_rel": round(r.mean, 4), "hit_rate": round(r.hit_rate, 2),
                     "n_events": int(r.n_events), "reliability": r.reliability}
                    for r in pick.itertuples()]
            note = (f"Historical {horizon} sector returns vs the average stock after "
                    f"{int(pb.n_events.max())} past '{etype}{':' + st if st else ''}' events. "
                    "What happened before, not a forecast.")
    except FileNotFoundError:
        note = "Run `python3 -m events.event_study` first to build the playbook."
    return {"event_type": etype, "subtype": sub, "stance": stance, "confidence": confidence,
            "matched": [f"{a}:{b}:{c}" for a, b, c in matches], "mentioned_groups": mentioned,
            "historical_playbook": hist, "note": note}
