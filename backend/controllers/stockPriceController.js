const {getStockPricesByCompany} = require("../services/stockPriceService");


const getStockPrices = async (req, res) => {
    try {
        const { companyId } = req.params;

        // Company ids are positive integers; anything else is a bad request, not an empty result
        if (!/^\d+$/.test(companyId)) {
            return res.status(400).json({ success: false, message: "companyId must be a positive integer" });
        }

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