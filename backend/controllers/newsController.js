const db = require("../config/db");

const MAX_LIMIT = 100;
const DEFAULT_LIMIT = 20;

// Columns returned by every news endpoint (sentiment included)
const NEWS_FIELDS = `
    n.id,
    n.company_id,
    n.symbol,
    n.isin,
    n.company_name,
    n.headline,
    n.content,
    n.event_type,
    n.importance,
    n.feed_type,
    n.published_at,
    n.event_date,
    n.date_status,
    n.url,
    n.attachment_url,
    n.source,
    n.created_at,
    n.sentiment,
    n.sentiment_confidence,
    n.sentiment_confident,
    n.sentiment_scores,
    n.sentiment_model,
    n.sentiment_at
`;

const SENTIMENTS = ["POSITIVE", "NEGATIVE", "NEUTRAL"];
const IMPORTANCES = ["HIGH", "MEDIUM", "LOW"];

// Clamp a query-string number into a safe range
const toInt = (value, fallback, min, max) => {
    const parsed = Number.parseInt(value, 10);

    if (!Number.isFinite(parsed)) {
        return fallback;
    }

    return Math.min(Math.max(parsed, min), max);
};

const getNews = async (req, res) => {
    try {
        const {
            page,
            limit,
            offset,
            company_id,
            symbol,
            sector,
            importance,
            sentiment,
            confident,
            feed_type,
            search,
            from,
            to
        } = req.query;

        const safeLimit = toInt(limit, DEFAULT_LIMIT, 1, MAX_LIMIT);

        // `offset` wins; `page` is kept for the older callers
        const safeOffset =
            offset !== undefined
                ? toInt(offset, 0, 0, Number.MAX_SAFE_INTEGER)
                : (toInt(page, 1, 1, Number.MAX_SAFE_INTEGER) - 1) * safeLimit;

        // Duplicates are never surfaced
        let where = ["n.is_duplicate = 0"];
        let params = [];

        // A sector filter needs the company -> sector chain
        const joins = sector
            ? `
            JOIN companies c
                ON c.id = n.company_id
            JOIN sectors s
                ON s.id = c.sector_id
            `
            : "";

        if (sector) {
            where.push("s.name = ?");
            params.push(sector);
        }

        // Company filter
        if (company_id) {
            where.push("n.company_id = ?");
            params.push(company_id);
        }

        // Symbol filter
        if (symbol) {
            where.push("n.symbol = ?");
            params.push(symbol.toUpperCase());
        }

        // Importance filter
        if (importance && IMPORTANCES.includes(importance.toUpperCase())) {
            where.push("n.importance = ?");
            params.push(importance.toUpperCase());
        }

        // Sentiment filter
        if (sentiment && SENTIMENTS.includes(sentiment.toUpperCase())) {
            where.push("n.sentiment = ?");
            params.push(sentiment.toUpperCase());
        }

        // Only rows the model was confident about (confidence >= 0.95)
        if (confident === "1" || confident === "true") {
            where.push("n.sentiment_confident = 1");
        }

        // Feed type filter
        if (feed_type) {
            where.push("n.feed_type = ?");
            params.push(feed_type);
        }

        // Free text search
        if (search) {
            where.push(`
                (
                    n.headline LIKE ?
                    OR n.company_name LIKE ?
                    OR n.symbol LIKE ?
                    OR n.event_type LIKE ?
                )
            `);

            const like = `%${search}%`;
            params.push(like, like, like, like);
        }

        // Date filters
        if (from) {
            where.push("n.published_at >= ?");
            params.push(`${from} 00:00:00`);
        }

        if (to) {
            where.push("n.published_at <= ?");
            params.push(`${to} 23:59:59`);
        }

        const whereClause = `WHERE ${where.join(" AND ")}`;

        // Total matching records
        const [countResult] = await db.query(
            `
            SELECT COUNT(*) AS total
            FROM news n
            ${joins}
            ${whereClause}
            `,
            params
        );

        const total = countResult[0].total;

        // News records, newest first
        const [news] = await db.query(
            `
            SELECT
                ${NEWS_FIELDS}
            FROM news n
            ${joins}
            ${whereClause}
            ORDER BY n.published_at DESC, n.id DESC
            LIMIT ? OFFSET ?
            `,
            [...params, safeLimit, safeOffset]
        );

        res.json({
            success: true,
            count: news.length,
            total,
            limit: safeLimit,
            offset: safeOffset,
            data: news
        });

    } catch (error) {
        console.error("Get news error:", error);

        res.status(500).json({
            success: false,
            message: "Failed to fetch news"
        });
    }
};


const getNewsStats = async (req, res) => {
    try {
        const [sentimentRows] = await db.query(
            `
            SELECT
                COALESCE(sentiment, 'UNSCORED') AS sentiment,
                COUNT(*) AS count
            FROM news
            WHERE is_duplicate = 0
            GROUP BY sentiment
            `
        );

        const [importanceRows] = await db.query(
            `
            SELECT
                COALESCE(importance, 'UNKNOWN') AS importance,
                COUNT(*) AS count
            FROM news
            WHERE is_duplicate = 0
            GROUP BY importance
            `
        );

        const [totals] = await db.query(
            `
            SELECT
                COUNT(*) AS total,
                SUM(sentiment_confident = 1) AS confident,
                SUM(sentiment IS NOT NULL AND sentiment_confident = 0) AS not_confident,
                MAX(published_at) AS newest_published_at
            FROM news
            WHERE is_duplicate = 0
            `
        );

        // Last 14 days of activity for a sparkline / bar strip
        const [daily] = await db.query(
            `
            SELECT
                DATE_FORMAT(published_at, '%Y-%m-%d') AS day,
                COUNT(*) AS count
            FROM news
            WHERE is_duplicate = 0
                AND published_at >= DATE_SUB(CURDATE(), INTERVAL 13 DAY)
            GROUP BY day
            ORDER BY day ASC
            `
        );

        const bySentiment = { POSITIVE: 0, NEGATIVE: 0, NEUTRAL: 0, UNSCORED: 0 };
        sentimentRows.forEach((row) => {
            bySentiment[row.sentiment] = Number(row.count);
        });

        const byImportance = { HIGH: 0, MEDIUM: 0, LOW: 0, UNKNOWN: 0 };
        importanceRows.forEach((row) => {
            byImportance[row.importance] = Number(row.count);
        });

        res.json({
            success: true,
            data: {
                total: Number(totals[0].total),
                confident: Number(totals[0].confident || 0),
                not_confident: Number(totals[0].not_confident || 0),
                newest_published_at: totals[0].newest_published_at,
                by_sentiment: bySentiment,
                by_importance: byImportance,
                daily: daily.map((row) => ({
                    day: row.day,
                    count: Number(row.count)
                }))
            }
        });

    } catch (error) {
        console.error("Get news stats error:", error);

        res.status(500).json({
            success: false,
            message: "Failed to fetch news stats"
        });
    }
};


const getNewsById = async (req, res) => {
    try {
        const { id } = req.params;

        const [news] = await db.query(
            `
            SELECT
                ${NEWS_FIELDS}
            FROM news n
            WHERE n.id = ?
            `,
            [id]
        );

        if (news.length === 0) {
            return res.status(404).json({
                success: false,
                message: "News not found"
            });
        }

        res.json({
            success: true,
            data: news[0]
        });

    } catch (error) {
        console.error("Get news by ID error:", error);

        res.status(500).json({
            success: false,
            message: "Failed to fetch news"
        });
    }
};


const getCompanyNews = async (req, res) => {
    try {
        const { companyId } = req.params;
        const safeLimit = toInt(req.query.limit, MAX_LIMIT, 1, MAX_LIMIT);

        const [news] = await db.query(
            `
            SELECT
                ${NEWS_FIELDS}
            FROM news n
            WHERE n.company_id = ?
                AND n.is_duplicate = 0
            ORDER BY n.published_at DESC, n.id DESC
            LIMIT ?
            `,
            [companyId, safeLimit]
        );

        res.json({
            success: true,
            count: news.length,
            data: news
        });

    } catch (error) {
        console.error("Get company news error:", error);

        res.status(500).json({
            success: false,
            message: "Failed to fetch company news"
        });
    }
};


module.exports = {
    getNews,
    getNewsStats,
    getNewsById,
    getCompanyNews
};
