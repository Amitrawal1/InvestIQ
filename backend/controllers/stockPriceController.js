const db = require("../config/db");

const getStockPrices = async (req, res) => {
    try {
        const { companyId } = req.params;

        const [rows] = await db.query(
            `
            SELECT
                price_date,
                open_price,
                high_price,
                low_price,
                close_price,
                volume
            FROM stock_prices
            WHERE company_id = ?
            ORDER BY price_date ASC
            `,
            [companyId]
        );

        res.json(rows);

    } catch (error) {
        console.error(error);

        res.status(500).json({
            message: "Failed to fetch stock prices"
        });
    }
};

module.exports = {
    getStockPrices
};