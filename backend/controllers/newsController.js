const db = require("../config/db");

const getNews = async (req, res) => {
    try {
        const {
            page = 1,
            limit = 20,
            company_id,
            symbol,
            feed_type,
            from,
            to
        } = req.query;

        const offset = (page - 1) * limit;

        let where = [];
        let params = [];

        // Company filter
        if (company_id) {
            where.push("company_id = ?");
            params.push(company_id);
        }

        // Symbol filter
        if (symbol) {
            where.push("symbol = ?");
            params.push(symbol);
        }

        // Feed type filter
        if (feed_type) {
            where.push("feed_type = ?");
            params.push(feed_type);
        }

        // Date filters
        if (from) {
            where.push("published_at >= ?");
            params.push(`${from} 00:00:00`);
        }

        if (to) {
            where.push("published_at <= ?");
            params.push(`${to} 23:59:59`);
        }

        const whereClause =
            where.length > 0
                ? `WHERE ${where.join(" AND ")}`
                : "";

        // Total records
        const [countResult] = await db.query(
            `
            SELECT COUNT(*) AS total
            FROM news
            ${whereClause}
            `,
            params
        );

        const total = countResult[0].total;

        // News records
        const [news] = await db.query(
            `
            SELECT
                id,
                company_id,
                symbol,
                isin,
                company_name,
                headline,
                feed_type,
                published_at,
                event_date,
                date_status,
                url,
                source,
                created_at
            FROM news
            ${whereClause}
            ORDER BY published_at DESC, id DESC
            LIMIT ? OFFSET ?
            `,
            [...params, Number(limit), Number(offset)]
        );

        res.json({
            success: true,
            data: news,
            pagination: {
                page: Number(page),
                limit: Number(limit),
                total,
                totalPages: Math.ceil(total / limit)
            }
        });

    } catch (error) {
        console.error("Get news error:", error);

        res.status(500).json({
            success: false,
            message: "Failed to fetch news"
        });
    }
};


const getNewsById = async (req, res) => {
    try {
        const { id } = req.params;

        const [news] = await db.query(
            `
            SELECT
                id,
                company_id,
                symbol,
                isin,
                company_name,
                headline,
                feed_type,
                published_at,
                event_date,
                date_status,
                url,
                source,
                created_at
            FROM news
            WHERE id = ?
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

        const [news] = await db.query(
            `
            SELECT
                id,
                company_id,
                symbol,
                isin,
                company_name,
                headline,
                feed_type,
                published_at,
                event_date,
                date_status,
                url,
                source,
                created_at
            FROM news
            WHERE company_id = ?
            ORDER BY published_at DESC, id DESC
            `,
            [companyId]
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
    getNewsById,
    getCompanyNews
};