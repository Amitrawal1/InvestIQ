const events = require("../services/eventsService");

const fail = (res, status, message) => res.status(status).json({ success: false, message });

const wrap = (fn) => async (req, res) => {
    try {
        await fn(req, res);
    } catch (error) {
        console.error("Events:", error.message);
        fail(res, 500, "Events data is unavailable right now");
    }
};

// GET /events?type=&limit=
const list = wrap((req, res) => {
    const limit = Math.min(Math.max(Number.parseInt(req.query.limit, 10) || 30, 1), 200);
    res.json(events.recent({ type: req.query.type || null, limit }));
});

// GET /events/types
const types = wrap((req, res) => res.json(events.types()));

// GET /events/playbook?type=&stance=&horizon=63d&level=sector
const playbook = wrap((req, res) => {
    const { type, stance, horizon = "63d", level = "sector" } = req.query;
    if (!type) return fail(res, 400, "type is required");
    const out = events.playbook({ type, stance: stance || null, horizon, level });
    if (!out) return fail(res, 400, `horizon must be one of ${events.HORIZONS.join(", ")} and level one of ${events.LEVELS.join(", ")}`);
    if (!out.n_events) return fail(res, 404, "Unknown event type");
    res.json(out);
});

// POST /events/classify { text, horizon? }
const classify = wrap((req, res) => {
    const text = typeof req.body.text === "string" ? req.body.text.trim() : "";
    if (text.length < 8) return fail(res, 400, "Paste a headline of at least a few words");
    const horizon = events.HORIZONS.includes(req.body.horizon) ? req.body.horizon : "63d";
    res.json(events.classify(text, horizon));
});

// GET /events/:id
const detail = wrap((req, res) => {
    const e = events.byId(req.params.id);
    if (!e) return fail(res, 404, "Event not found");
    res.json(e);
});

module.exports = { list, types, playbook, classify, detail };
