const db = require("../config/db");

const getCompanies = async (req, res) => {
    try {
        const {
            search,
            segment,
            sector,
            industry
        } = req.query;

        let query = `
            SELECT
                c.id,
                c.name,
                c.symbol,
                c.isin,
                c.exchange,
                c.market_segment,
                c.listing_date,
                c.series,
                s.name AS sector,
                i.name AS industry
            FROM companies c
            LEFT JOIN sectors s
                ON c.sector_id = s.id
            LEFT JOIN industries i
                ON c.industry_id = i.id
            WHERE 1 = 1
        `;

        const params = [];

        if (search) {
            query += `
                AND (
                    c.name LIKE ?
                    OR c.symbol LIKE ?
                )
            `;

            params.push(
                `%${search}%`,
                `%${search}%`
            );
        }

        if (segment) {
            query += ` AND c.market_segment = ?`;
            params.push(segment);
        }

        if (sector) {
            query += ` AND s.name = ?`;
            params.push(sector);
        }

        if (industry) {
            query += ` AND i.name = ?`;
            params.push(industry);
        }

        query += ` ORDER BY c.name ASC`;

        const [companies] = await db.query(query, params);

        res.status(200).json({
            success: true,
            count: companies.length,
            data: companies
        });

    } catch (error) {
        console.error(error);

        res.status(500).json({
            success: false,
            message: "Failed to fetch companies"
        });
    }
};

module.exports = {
    getCompanies
};