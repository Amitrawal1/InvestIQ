"""IPO valuation vs listed peers: a PURE function (no I/O), used by the dataset builder, the
historical test (eval.py) and the live prototype (live.py).

    ipo_valuation(ipo, peers, date) -> dict

ipo (dict-like):
    issue_price        Rs per share (upper band for an open issue, final price after it closes)
    shares_post        post-issue share count (crore shares), or `mcap_cr` directly
    revenue_ann        annual revenue (crore Rs): latest full year, or a part-year annualised
    net_profit_ann     annual net profit to owners (crore Rs); <= 0 means loss-making
    equity             post-issue net worth / book value (crore Rs), optional
    industry, sector   for the label in the output (peer selection is done by the caller)

peers (DataFrame, one row per listed peer as of `date`, already point-in-time):
    symbol, mcap_cr, pe, pb, ps     (pe NaN or <= 0 for loss-makers; pb NaN for negative equity)

Conventions (same as ml/valuation/features.py so IPO and peer multiples are comparable):
    P/E = market cap / annual net profit (post-issue shares, i.e. diluted for the fresh issue; the RHP's
          "P/E at the upper band" uses pre-issue EPS and so reads lower when there is a fresh issue)
    P/B = market cap / equity,  P/S = market cap / revenue
    peer_median_* = median over peers with a positive multiple (loss-makers have no P/E)
    rel_* = log(IPO multiple / peer median): 0 = in line, +0.69 = twice the peer multiple
    pct_in_peers_* = share of peers with a LOWER multiple (0 = cheapest of the set, 1 = dearest)

Verdict wording is descriptive, never advice (InvestIQ is not a SEBI-registered research analyst):
    "priced below its listed peers" / "in line with" / "above" / "well above", by the median of the
    available rel_* values with bands of +-0.15 (about +-15%) and +0.50 (about 1.65x).
"""

import math

import numpy as np
import pandas as pd

METRICS = ("pe", "pb", "ps")
MIN_PEERS = 5
IN_LINE = 0.15          # |rel| below this: "in line with its listed peers"
WELL_ABOVE = 0.50
LABELS = {"pe": "P/E", "pb": "P/B", "ps": "P/S"}


def _pos(x):
    try:
        x = float(x)
    except (TypeError, ValueError):
        return None
    return x if x > 0 and math.isfinite(x) else None


def ipo_multiples(ipo):
    price = _pos(ipo.get("issue_price"))
    mcap = _pos(ipo.get("mcap_cr"))
    if mcap is None and price is not None and _pos(ipo.get("shares_post")) is not None:
        mcap = price * float(ipo["shares_post"])
    out = {"mcap_cr": mcap, "pe": None, "pb": None, "ps": None, "loss_making": None}
    if mcap is None:
        return out
    np_ann = ipo.get("net_profit_ann")
    if np_ann is not None and not (isinstance(np_ann, float) and math.isnan(np_ann)):
        out["loss_making"] = float(np_ann) <= 0
        out["pe"] = mcap / float(np_ann) if float(np_ann) > 0 else None
    eq = _pos(ipo.get("equity"))
    out["pb"] = mcap / eq if eq else None
    rev = _pos(ipo.get("revenue_ann"))
    out["ps"] = mcap / rev if rev else None
    return out


def ipo_valuation(ipo, peers, date):
    """-> dict with the IPO's multiples, peer medians, relative premia, verdict and wording."""
    m = ipo_multiples(ipo)
    peers = peers if peers is not None else pd.DataFrame(columns=["symbol", *METRICS])
    out = {"date": str(pd.Timestamp(date).date()), "mcap_cr": m["mcap_cr"], "loss_making": m["loss_making"],
           "n_peers": int(len(peers))}
    rels = {}
    rows = []
    for k in METRICS:
        col = peers[k] if k in peers else pd.Series(dtype=float)
        v = pd.to_numeric(col, errors="coerce")
        v = v[(v > 0) & np.isfinite(v)]
        med = float(v.median()) if len(v) >= MIN_PEERS else None
        own = m[k]
        out[f"ipo_{k}"] = own
        out[f"peer_median_{k}"] = med
        out[f"peer_n_{k}"] = int(len(v))
        rel = math.log(own / med) if (own and med) else None
        if k == "pe" and m["loss_making"] and med:
            rel = None                      # no P/E for a loss-maker: reported separately
        out[f"rel_{k}"] = rel
        out[f"pct_in_peers_{k}"] = float((v < own).mean()) if (own and len(v) >= MIN_PEERS) else None
        if rel is not None:
            rels[k] = rel
        rows.append({"metric": LABELS[k], "ipo": own, "peer_median": med, "peers": int(len(v)),
                     "premium_pct": (math.exp(rel) - 1) * 100 if rel is not None else None})
    out["table"] = rows
    if rels:
        r = float(np.median(list(rels.values())))
        out["rel_median"] = r
        if r < -IN_LINE:
            v = "below"
        elif r <= IN_LINE:
            v = "in_line"
        elif r <= WELL_ABOVE:
            v = "above"
        else:
            v = "well_above"
    else:
        out["rel_median"], v = None, "insufficient_data"
    if m["loss_making"] and v in ("below", "in_line"):
        v = v + "_loss_making"
    out["verdict"] = v
    out["wording"] = wording(v, rels, m["loss_making"], ipo.get("industry") or ipo.get("sector") or "its industry")
    return out


def wording(verdict, rels, loss_making, group):
    parts = ", ".join(f"{LABELS[k]} {math.exp(r) - 1:+.0%}" for k, r in rels.items())
    base = {
        "below": f"Priced below its listed {group} peers",
        "in_line": f"Priced in line with its listed {group} peers",
        "above": f"Priced above its listed {group} peers",
        "well_above": f"Priced well above its listed {group} peers",
        "below_loss_making": f"Priced below its listed {group} peers on sales and book value, but it is loss-making",
        "in_line_loss_making": f"Priced in line with its listed {group} peers on sales and book value, but it is loss-making",
        "insufficient_data": f"Not enough data to compare with listed {group} peers",
    }[verdict]
    if loss_making and verdict in ("above", "well_above"):
        base += " and it is loss-making"
    return base + (f" (vs peer median: {parts})." if parts else ".") + \
        " This is a description of the price, not a recommendation to apply or not."
