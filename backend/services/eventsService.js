// Market events study (ml/events -> backend/data/events.json, built by `python3 -m events.export_site`).
// History, not live data: loaded once per server instance. Read-only.
//
// What it answers: after past events of a type (war, RBI decision, budget, sector policy, ...), how did
// each sector / theme do against the average stock? The study's validation found this is NOT predictive
// after the first trading day, so every response carries that verdict and the reliability labels.
const fs = require("fs");
const path = require("path");

const FILE = path.join(__dirname, "..", "data", "events.json");
let data = null;

const load = () => {
    if (!data) {
        data = JSON.parse(fs.readFileSync(FILE, "utf8"));
        data.byId = new Map(data.events.map((e) => [e.id, e]));
        // Python regexes from ml/events/playbook.py; same syntax for these patterns in JS
        data.compiledRules = data.rules.map((r) => ({ ...r, re: new RegExp(r.pattern, "i") }));
        data.compiledMentions = data.mention_rules.map((r) => ({ ...r, re: new RegExp(r.pattern, "i") }));
    }
    return data;
};

const HORIZONS = ["21d", "63d", "126d"];
const LEVELS = ["sector", "theme"];

// List view: one row per event, with the market's first-day move and the best / worst sectors
const summary = (e, horizon = "63d") => {
    const pick = (rows) => (rows || []);
    const h = e.sectors[horizon] ? horizon : ["126d", "63d", "21d", "5d"].find((x) => e.sectors[x]);
    const rows = pick(e.sectors[h]);
    return {
        id: e.id, date: e.date, time_ist: e.time_ist, entry_date: e.entry_date, type: e.type, type_label: e.type_label,
        subtype: e.subtype, stance: e.stance, scope: e.scope, title: e.title, source_url: e.source_url, source_kind: e.source_kind,
        day0_market: e.market.day0 || null,
        horizon: h || null,
        best: rows.slice(0, 2),
        worst: rows.slice(-2).reverse(),
    };
};

const recent = ({ type, limit = 30 } = {}) => {
    const d = load();
    const list = d.events.filter((e) => !type || e.type === type);
    return { total: list.length, data: list.slice(0, limit).map((e) => summary(e)) };
};

const byId = (id) => load().byId.get(String(id).toUpperCase()) || null;

// Playbook rows for a type (+ optional stance), horizon and level, best first
const playbook = ({ type, stance = null, horizon = "63d", level = "sector" }) => {
    const d = load();
    if (!HORIZONS.includes(horizon) || !LEVELS.includes(level)) return null;
    let rows = d.playbook.filter((r) => r.type === type && r.horizon === horizon && r.level === level && (r.stance || null) === (stance || null));
    let usedStance = stance || null;
    if (!rows.length && stance) {
        rows = d.playbook.filter((r) => r.type === type && r.horizon === horizon && r.level === level && !r.stance);
        usedStance = null;
    }
    const events = d.events.filter((e) => e.type === type && (!usedStance || e.stance === usedStance))
        .map((e) => ({ id: e.id, date: e.date, title: e.title }));
    return {
        type, type_label: (d.types.find((t) => t.id === type) || {}).label || type, stance: usedStance, horizon, level,
        n_events: events.length, events, verdict: d.validation.verdict,
        rows: rows.sort((a, b) => (b.mean ?? -9) - (a.mean ?? -9)),
    };
};

const types = () => {
    const d = load();
    const stances = {};
    d.events.forEach((e) => {
        if (!e.stance) return;
        stances[e.type] = stances[e.type] || {};
        stances[e.type][e.stance] = (stances[e.type][e.stance] || 0) + 1;
    });
    return { types: d.types.map((t) => ({ ...t, stances: stances[t.id] || {} })), validation: d.validation };
};

// Headline / press release -> event type + the historical table (never invents an impact)
const classify = (text, horizon = "63d") => {
    const d = load();
    const s = String(text || "").slice(0, 2000);
    const matches = d.compiledRules.filter((r) => r.re.test(s));
    const mentioned = d.compiledMentions.filter((r) => r.re.test(s)).map((r) => r.group);
    if (!matches.length) {
        return { event_type: null, mentioned_groups: mentioned, note: "No event type recognised. Try a fuller headline." };
    }
    const top = matches[0];
    const agree = matches.filter((m) => m.type === top.type).length / matches.length;
    const confidence = Math.round(Math.min(1, 0.5 + 0.25 * (matches.length > 1 ? agree : 0) + 0.25 * agree) * 100) / 100;
    const pb = playbook({ type: top.type, stance: top.stance, horizon, level: "sector" });
    return {
        event_type: top.type, subtype: top.subtype, stance: top.stance, confidence, mentioned_groups: mentioned,
        playbook: pb,
        note: "What happened after similar events before, not a forecast. In testing, these patterns did not predict the next event better than chance after the first trading day.",
    };
};

module.exports = { recent, byId, playbook, types, classify, HORIZONS, LEVELS };
