const db = require("../config/db");


// GET /api/companies
// GET /api/companies?sector=solar-energy

const getCompanies = async (req, res) => {
    try {
        const { sector } = req.query;

        let query = `
            SELECT
                companies.id,
                companies.name,
                companies.symbol,
                companies.industry,
                companies.description,
                sectors.name AS sector
            FROM companies
            JOIN sectors
                ON companies.sector_id = sectors.id
        `;

        const values = [];

        if (sector) {
            query += ` WHERE sectors.slug = ?`;
            values.push(sector);
        }

        const [rows] = await db.query(query, values);

        res.json(rows);

    } catch (error) {
        console.error(error);

        res.status(500).json({
            message: "Failed to fetch companies"
        });
    }
};


// GET /api/companies/:id

const getCompanyById = async (req, res) => {
    try {
        const { id } = req.params;

        const [rows] = await db.query(
            `
            SELECT
                companies.id,
                companies.name,
                companies.symbol,
                companies.industry,
                companies.description,
                sectors.name AS sector
            FROM companies
            JOIN sectors
                ON companies.sector_id = sectors.id
            WHERE companies.id = ?
            `,
            [id]
        );

        if (rows.length === 0) {
            return res.status(404).json({
                message: "Company not found"
            });
        }

        res.json(rows[0]);

    } catch (error) {
        console.error(error);

        res.status(500).json({
            message: "Failed to fetch company"
        });
    }
};


module.exports = {
    getCompanies,
    getCompanyById
};