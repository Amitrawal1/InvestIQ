const { getPortfolio: buildPortfolio } = require("../services/portfolioService");

// GET /portfolio -> merged latest snapshot per broker with InvestIQ scores and insights
const getPortfolio = async (req, res) => {
    try {
        res.json({ success: true, ...(await buildPortfolio(req.user.id)) });
    } catch (error) {
        console.error("Portfolio failed:", error.message);
        res.status(500).json({ success: false, message: "Couldn't load your portfolio. Try again." });
    }
};

module.exports = { getPortfolio };
