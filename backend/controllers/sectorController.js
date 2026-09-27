const db = require("../config/db");
const { toNum, cached } = require("../services/rankingService");

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

// GET /sectors/:slug/industries -> industry chips with ranking stats from the latest snapshot
const getSectorIndustries = async (req, res) => {
    try {
        const slug = String(req.params.slug || "").toLowerCase();

        const result = await cached(`sector-industries:${slug}`, async () => {
            const [sectors] = await db.query(
                "SELECT id FROM sectors WHERE slug = ? LIMIT 1",
                [slug]
            );

            if (!sectors.length) {
                return null;
            }

            // One row per company (plus industries without companies), aggregated below
            const [rows] = await db.query(`
                SELECT
                    i.id AS industry_id,
                    i.name AS industry,
                    c.id AS company_id,
                    c.symbol,
                    r.growth_score,
                    r.rank_overall
                FROM industries i
                LEFT JOIN companies c
                    ON c.industry_id = i.id
                LEFT JOIN company_rankings r
                    ON r.company_id = c.id
                    AND r.snapshot_date = (SELECT MAX(snapshot_date) FROM company_rankings)
                WHERE i.sector_id = ?
            `, [sectors[0].id]);

            const byIndustry = new Map();

            for (const row of rows) {
                if (!byIndustry.has(row.industry_id)) {
                    byIndustry.set(row.industry_id, {
                        industry: row.industry,
                        company_count: 0,
                        ranked_count: 0,
                        score_sum: 0,
                        top: null,
                    });
                }

                const item = byIndustry.get(row.industry_id);

                if (row.company_id === null) {
                    continue;
                }

                item.company_count += 1;

                const score = toNum(row.growth_score);

                if (row.rank_overall !== null && score !== null) {
                    item.ranked_count += 1;
                    item.score_sum += score;

                    if (!item.top || row.rank_overall < item.top.rank_overall) {
                        item.top = row;
                    }
                }
            }

            return [...byIndustry.values()]
                .map((item) => ({
                    industry: item.industry,
                    company_count: item.company_count,
                    ranked_count: item.ranked_count,
                    avg_score: item.ranked_count
                        ? Math.round((item.score_sum / item.ranked_count) * 100) / 100
                        : null,
                    top_symbol: item.top ? item.top.symbol : null,
                }))
                .sort((a, b) => b.company_count - a.company_count || a.industry.localeCompare(b.industry));
        });

        if (!result) {
            return res.status(404).json({
                success: false,
                message: "Sector not found"
            });
        }

        res.json(result);
    } catch (error) {
        console.error(error);

        res.status(500).json({
            success: false,
            message: "Failed to fetch sector industries"
        });
    }
};

module.exports = {
    getSectors,
    getSectorIndustries
};
