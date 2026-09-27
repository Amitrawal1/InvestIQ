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
                `SELECT ${RANKING_FIELDS} ${from} ORDER BY ${SORTS[sortKey]} LIMIT ? OFFSET ?`,
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
                    SUM(rank_overall IS NULL) AS unranked
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
                method: METHOD,
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
