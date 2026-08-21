const db = require("../config/db");

const getStockPricesByCompany = async (companyId) => {
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

    return rows;
};

module.exports = {
    getStockPricesByCompany
};