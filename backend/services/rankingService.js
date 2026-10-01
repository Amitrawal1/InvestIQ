// Shared helpers for the growth-ranking endpoints (rankings, sector industries, company details)

// mysql2 returns DECIMAL / SUM() as strings; convert to numbers (null stays null)
const toNum = (value) => {
    if (value === null || value === undefined || value === "") {
        return null;
    }

    const parsed = Number(value);

    return Number.isFinite(parsed) ? parsed : null;
};

// JSON columns normally arrive parsed; tolerate strings just in case
const parseJson = (value, fallback = null) => {
    if (value === null || value === undefined) {
        return fallback;
    }

    if (typeof value === "string") {
        try {
            return JSON.parse(value);
        } catch (error) {
            return fallback;
        }
    }

    return value;
};

// Tiny in-memory TTL cache (per server instance)
const CACHE_TTL_MS = 5 * 60 * 1000;
const cache = new Map();

// shouldCache lets callers skip caching e.g. "no snapshot yet" while the ranking job is running
const cached = async (key, loader, shouldCache = () => true, ttlMs = CACHE_TTL_MS) => {
    const hit = cache.get(key);

    if (hit && hit.expires > Date.now()) {
        return hit.value;
    }

    const value = await loader();

    if (shouldCache(value)) {
        cache.set(key, { value, expires: Date.now() + ttlMs });
    }

    return value;
};

// Columns shared by list rows and the detail view. Expects aliases r, c, s, i.
const RANKING_FIELDS = `
    r.company_id,
    r.symbol,
    c.name,
    s.name AS sector,
    s.slug AS sector_slug,
    i.name AS industry,
    r.growth_score,
    r.growth_label,
    r.rank_overall,
    r.rank_in_sector,
    r.rank_in_industry,
    r.coverage,
    r.score_growth,
    r.score_profitability,
    r.score_financial_health,
    r.score_cash_flow,
    r.score_momentum,
    r.score_news,
    r.key_metrics
`;


const LIST_METRICS = ["last_price", "return_1y", "revenue_growth_yoy", "roe", "market_cap_est"];

const pick = (source, keys) => {
    const out = {};

    for (const key of keys) {
        out[key] = source && source[key] !== undefined ? source[key] : null;
    }

    return out;
};

// Normalise a company_rankings row. full=false keeps only the list subset of key_metrics.
const formatRankingRow = (row, full = false) => {
    const out = {
        company_id: row.company_id,
        symbol: row.symbol,
        name: row.name,
        sector: row.sector,
        sector_slug: row.sector_slug,
        industry: row.industry,
        growth_score: toNum(row.growth_score),
        growth_label: row.growth_label,
        rank_overall: row.rank_overall,
        rank_in_sector: row.rank_in_sector,
        rank_in_industry: row.rank_in_industry,
        coverage: toNum(row.coverage),
        score_growth: toNum(row.score_growth),
        score_profitability: toNum(row.score_profitability),
        score_financial_health: toNum(row.score_financial_health),
        score_cash_flow: toNum(row.score_cash_flow),
        score_momentum: toNum(row.score_momentum),
        score_news: toNum(row.score_news),
    };

    const metrics = parseJson(row.key_metrics, {}) || {};
    out.key_metrics = full ? metrics : pick(metrics, LIST_METRICS);
    // investiq-v1: { eligible, not_eligible_reason, in_list, position, status: "new"|"kept" } (null before)
    out.top_list = metrics.top_list || null;
    // { in_list, position, status } (null before the Steady list existed)
    out.steady_list = metrics.steady_list || null;

    return out;
};

// Next scheduled rebuild: the first 1st or 16th strictly after the given YYYY-MM-DD date
const nextUpdateAfter = (dateStr) => {
    const base = dateStr ? new Date(`${dateStr}T00:00:00Z`) : new Date();
    const y = base.getUTCFullYear();
    const m = base.getUTCMonth();
    const d = base.getUTCDate();

    const next = d < 16
        ? new Date(Date.UTC(y, m, 16))
        : new Date(Date.UTC(y, m + 1, 1));

    return next.toISOString().slice(0, 10);
};

module.exports = {
    toNum,
    parseJson,
    cached,
    RANKING_FIELDS,
    formatRankingRow,
    nextUpdateAfter,
};
