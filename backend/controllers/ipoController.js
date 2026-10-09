const ipos = require("../services/ipoService");

const fail = (res, status, message) => res.status(status).json({ success: false, message });

const wrap = (fn) => async (req, res) => {
    try {
        await fn(req, res);
    } catch (error) {
        console.error("IPOs:", error.message);
        fail(res, 500, "IPO data is unavailable right now");
    }
};

// GET /ipos?limit=
const list = wrap((req, res) => {
    const limit = Math.min(Math.max(Number.parseInt(req.query.limit, 10) || 60, 1), 300);
    res.json(ipos.overview({ limit }));
});

// GET /ipos/base-rates
const baseRates = wrap((req, res) => res.json(ipos.baseRates()));

// GET /ipos/:symbol
const detail = wrap((req, res) => {
    if (!/^[A-Za-z0-9&-]{1,32}$/.test(req.params.symbol)) return fail(res, 400, "Invalid symbol");
    const ipo = ipos.bySymbol(req.params.symbol);
    if (!ipo) return fail(res, 404, "IPO not found");
    res.json(ipo);
});

module.exports = { list, baseRates, detail };
