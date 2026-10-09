// IPO study (ml/ipo -> backend/data/ipos.json, built by `python3 -m ipo.export_site`).
// Loaded once per server instance. Read-only.
//
// What it answers: is an IPO priced above or below its listed peers, and what did earlier IPOs priced
// like it do? The study's test found neither cheapness vs peers nor QIB subscription predicted returns
// after listing, so this is a description with historical base rates, never a signal.
const fs = require("fs");
const path = require("path");

const FILE = path.join(__dirname, "..", "data", "ipos.json");
let data = null;

const load = () => {
    if (!data) data = JSON.parse(fs.readFileSync(FILE, "utf8"));
    return data;
};

// India date (YYYY-MM-DD), so an issue opens and closes on the IST calendar day
const todayIst = () => new Date(Date.now() + 5.5 * 3600 * 1000).toISOString().slice(0, 10);

const statusOf = (a, today = todayIst()) => {
    if (a.listing_date && a.listing_date <= today) return "listed";
    if (a.issue_start && today < a.issue_start) return "upcoming";
    if (a.issue_end && today <= a.issue_end) return "open";
    return "closed";
};

const qibBucket = (x) => {
    if (x == null) return null;
    if (x < 1) return "<1x";
    if (x < 10) return "1-10x";
    if (x < 50) return "10-50x";
    if (x < 100) return "50-100x";
    return ">100x";
};

// Base rates for one IPO: earlier IPOs with the same verdict and the same QIB subscription range
const historyFor = ({ verdict, sub_qib }) => {
    const br = load().base_rates;
    return {
        verdict: verdict ? br.verdict.find((r) => r.bucket === verdict) || null : null,
        qib: br.qib.find((r) => r.bucket === qibBucket(sub_qib)) || null,
        overall: br.overall,
    };
};

const overview = ({ limit = 60 } = {}) => {
    const d = load();
    const today = todayIst();
    const analyses = d.analyses.map((a) => ({ ...a, status: statusOf(a, today) }));
    return {
        as_of: d.as_of, today, market: d.market, disclaimer: d.disclaimer, source_note: d.source_note,
        summary: d.base_rates.summary,
        // open first, then upcoming, then closed, then the recently listed ones that were analysed
        current: analyses.filter((a) => a.status !== "listed")
            .sort((a, b) => ["open", "upcoming", "closed"].indexOf(a.status) - ["open", "upcoming", "closed"].indexOf(b.status)),
        analysed_listed: analyses.filter((a) => a.status === "listed"),
        listings_total: d.listings.length,
        listings: d.listings.slice(0, limit),
    };
};

const baseRates = () => {
    const d = load();
    return { ...d.base_rates, verdict_labels: d.verdict_labels, disclaimer: d.disclaimer };
};

const bySymbol = (symbol) => {
    const d = load();
    const s = String(symbol || "").toUpperCase();
    const a = d.analyses.find((x) => x.symbol === s);
    const l = d.listings.find((x) => x.symbol === s || x.site_symbol === s);
    if (!a && !l) return null;
    const merged = { ...(l || {}), ...(a || {}) };
    if (l) {
        merged.now = l.now;
        merged.exc = l.exc;
        merged.site_symbol = l.site_symbol;
    }
    merged.status = a ? statusOf(a) : "listed";
    merged.analysed = Boolean(a);
    merged.base_rates = historyFor({ verdict: merged.verdict, sub_qib: merged.sub_qib });
    merged.disclaimer = d.disclaimer;
    merged.source_note = d.source_note;
    merged.as_of = d.as_of;
    return merged;
};

module.exports = { overview, baseRates, bySymbol, statusOf };
