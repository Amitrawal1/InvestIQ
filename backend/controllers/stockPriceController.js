const {getStockPricesByCompany} = require("../services/stockPriceService");


const getStockPrices = async (req, res) => {
    try {
        const { companyId } = req.params;

        const prices = await getStockPricesByCompany(companyId);

        res.json(prices);

    } catch (error) {
        console.error(error);

        res.status(500).json({
            message: "Failed to fetch stock prices"
        });
    }
};


module.exports = {
    getStockPrices,
};