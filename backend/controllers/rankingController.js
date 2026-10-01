const db = require("../config/db");
const {
    toNum,
    cached,
    RANKING_FIELDS,
    formatRankingRow,
    nextUpdateAfter,
} = require("../services/rankingService");

const DEFAULT_LIMIT = 50;
const MAX_LIMIT = 200;

// Unranked companies (rank_overall NULL) always sort after ranked ones
const SORTS = {
    rank: "r.rank_overall IS NULL, r.rank_overall ASC, c.name ASC",
    score: "r.rank_overall IS NULL, r.growth_score IS NULL, r.growth_score DESC, c.name ASC",
    name: "r.rank_overall IS NULL, c.name ASC",
    return_1y: `
        r.rank_overall IS NULL,
        JSON_EXTRACT(r.key_metrics, '$.return_1y') IS NULL,
        CAST(JSON_EXTRACT(r.key_metrics, '$.return_1y') AS DOUBLE) DESC,
        c.name ASC
    `,
};

const METHOD = "Preliminary growth score (to be replaced by InvestIQ's machine-learning model): "
    + "every company is compared with all other listed companies on six groups of signals, "
    + "each converted to a percentile from 0 to 100 so that no single number dominates. "
    + "Financial growth looks at year-on-year and trailing-twelve-month growth in revenue, profit and EPS; "
    + "profitability at operating and net margins, return on equity and return on capital employed; "
    + "financial health at debt-to-equity, current ratio and interest coverage; "
    + "cash flow at operating and free cash flow and how much of reported profit turns into cash; "
    + "price momentum at 1, 3, 6 and 12-month returns relative to the NIFTY Smallcap 250 index, "
    + "adjusted for volatility; and news sentiment at the tone of recent company announcements and news. "
    + "The group percentiles are averaged into a 0-100 score, companies with too little data are shown "
    + "as unranked, and the score is a screening aid, not investment advice.";

const INVESTIQ_V1_METHOD = "InvestIQ score (investiq-v1): 70% market model, 30% financial model, plus a small news weight. "
    + "The market model measures how strongly the price trend confirms the business - distance from "
    + "the 52-week high, position versus the 200-day and 50-day averages, 3- and 6-month returns "
    + "relative to the NIFTY Smallcap 250 and how few down days the stock has had. The financial model "
    + "scores revenue and profit growth, profitability, balance-sheet health and cash-flow quality "
    + "from the company's own filings, using only results that were public at the time. In "
    + "walk-forward tests over 2019-2026 this mix ranked future 6- and 12-month out-performers about "
    + "twice as well as the earlier preliminary score. A fresh financial reading is required to be "
    + "ranked, and red flags that have historically preceded under-performance (negative equity; for "
    + "banks, NBFCs and insurers also worsening asset quality and capital near the regulatory minimum) "
    + "cost points. Banks, NBFCs and insurers are scored mainly on price trend, with their NPAs, "
    + "capital, ROA/ROE and cost ratios shown against their own peer group. Scores are percentiles "
    + "from 0 to 100; companies with too little data are shown as unranked. This is a screening aid, "
    + "not investment advice.";

// Text shown on /rankings/meta, by the latest snapshot's model_version (prelim text as fallback)
const methodFor = (modelVersion) => (modelVersion === "investiq-v1" ? INVESTIQ_V1_METHOD : METHOD);

// Top list (investiq-v1, key_metrics.top_list): rules shown next to the list on the site
const TOP_LIST_RULES = [
    "50 companies, refreshed with each snapshot on the 1st and 16th.",
    "Only companies trading at least Rs 0.5 crore a day and listed for at least a year: the universe the score was tested on.",
    "No new entries among the 5% most volatile stocks.",
    "A company already on the list stays while it ranks in the top 150 eligible names, so the list doesn't churn every 15 days.",
];
const TOP_POSITION = "CAST(JSON_EXTRACT(r.key_metrics, '$.top_list.position') AS UNSIGNED)";

const toInt = (value, fallback, min, max) => {
    const parsed = Number.parseInt(value, 10);

    if (!Number.isFinite(parsed)) {
        return fallback;
    }

    return Math.min(Math.max(parsed, min), max);
};

const getLatestSnapshot = async () => {
    const [rows] = await db.query(`
        SELECT
            DATE_FORMAT(snapshot_date, '%Y-%m-%d') AS snapshot_date,
            model_version
        FROM company_rankings
        WHERE snapshot_date = (SELECT MAX(snapshot_date) FROM company_rankings)
        LIMIT 1
    `);

    return rows[0] || null;
};

// GET /rankings
const getRankings = async (req, res) => {
    try {
        const { sector, industry, search, label } = req.query;
        const topList = req.query.list === "top";
        const sortKey = SORTS[req.query.sort] ? req.query.sort : "rank";
        const page = toInt(req.query.page, 1, 1, 100000);
        const limit = toInt(req.query.limit, DEFAULT_LIMIT, 1, MAX_LIMIT);

        const snapshot = await getLatestSnapshot();

        if (!snapshot) {
            return res.json({
                snapshot_date: null,
                model_version: null,
                total: 0,
                page,
                limit,
                data: [],
            });
        }

        let where = "WHERE r.snapshot_date = ?";
        const params = [snapshot.snapshot_date];

        if (sector) {
            where += " AND s.slug = ?";
            params.push(sector);
        }

        if (industry) {
            where += " AND i.name = ?";
            params.push(industry);
        }

        if (label) {
            where += " AND r.growth_label = ?";
            params.push(label);
        }

        if (topList) {
            where += " AND JSON_EXTRACT(r.key_metrics, '$.top_list.in_list') = true";
        }

        if (search && search.trim()) {
            where += " AND (c.name LIKE ? OR c.symbol LIKE ?)";
            params.push(`%${search.trim()}%`, `%${search.trim()}%`);
        }

        const from = `
            FROM company_rankings r
            JOIN companies c ON c.id = r.company_id
            LEFT JOIN sectors s ON s.id = c.sector_id
            LEFT JOIN industries i ON i.id = c.industry_id
            ${where}
        `;

        const [[countRow], [rows]] = await Promise.all([
            db.query(`SELECT COUNT(*) AS total ${from}`, params),
            db.query(
                // The Top list keeps its own order (kept holdings and new entries by position) unless a sort is asked for
                `SELECT ${RANKING_FIELDS} ${from} ORDER BY ${topList && !req.query.sort ? `${TOP_POSITION} ASC` : SORTS[sortKey]} LIMIT ? OFFSET ?`,
                [...params, limit, (page - 1) * limit]
            ),
        ]);

        res.json({
            snapshot_date: snapshot.snapshot_date,
            model_version: snapshot.model_version,
            total: toNum(countRow[0].total) || 0,
            page,
            limit,
            data: rows.map((row) => formatRankingRow(row)),
        });
    } catch (error) {
        console.error(error);

        res.status(500).json({
            success: false,
            message: "Failed to fetch rankings",
        });
    }
};

// GET /rankings/meta
const getRankingsMeta = async (req, res) => {
    try {
        const meta = await cached("rankings:meta", async () => {
            const [rows] = await db.query(`
                SELECT
                    DATE_FORMAT(snapshot_date, '%Y-%m-%d') AS snapshot_date,
                    MAX(model_version) AS model_version,
                    SUM(rank_overall IS NOT NULL) AS ranked,
                    SUM(rank_overall IS NULL) AS unranked,
                    SUM(JSON_EXTRACT(key_metrics, '$.top_list.in_list') = true) AS top_list_count
                FROM company_rankings
                GROUP BY snapshot_date
                ORDER BY snapshot_date DESC
            `);

            const latest = rows[0];

            return {
                snapshot_date: latest ? latest.snapshot_date : null,
                model_version: latest ? latest.model_version : null,
                next_update: nextUpdateAfter(latest ? latest.snapshot_date : null),
                ranked: latest ? toNum(latest.ranked) : 0,
                unranked: latest ? toNum(latest.unranked) : 0,
                method: methodFor(latest ? latest.model_version : null),
                top_list: {
                    count: latest ? toNum(latest.top_list_count) || 0 : 0,
                    rules: TOP_LIST_RULES,
                },
                snapshots: rows.map((row) => row.snapshot_date),
            };
        }, (value) => value.snapshot_date !== null);

        res.json(meta);
    } catch (error) {
        console.error(error);

        res.status(500).json({
            success: false,
            message: "Failed to fetch rankings metadata",
        });
    }
};

module.exports = {
    getRankings,
    getRankingsMeta,
};
