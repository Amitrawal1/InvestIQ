const db = require("../config/db");

const getSectors = async (req, res) => {
    try {
        const [rows] = await db.query(`
            SELECT
                s.id,
                s.name,
                s.slug,
                (
                    SELECT COUNT(*)
                    FROM companies c
                    WHERE c.sector_id = s.id
                ) AS company_count,
                (
                    SELECT COUNT(*)
                    FROM industries i
                    WHERE i.sector_id = s.id
                ) AS industry_count
            FROM sectors s
            ORDER BY s.id
        `);

        res.json(rows);
    } catch (error) {
        console.error(error);

        res.status(500).json({
            message: "Failed to fetch sectors"
        });
    }
};

module.exports = {
    getSectors
};
