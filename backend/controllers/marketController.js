const { getTickerQuotes, UpstoxTokenError } = require("../services/marketDataService");

const getTicker = async (req, res) => {
    try {
        const data = await getTickerQuotes();
        res.json({ success: true, data });
    } catch (error) {
        const tokenProblem = error instanceof UpstoxTokenError;
        console.log("Market ticker fetch failed:", error.message);
        res.status(tokenProblem ? 503 : 502).json({
            success: false,
            error: tokenProblem ? "UPSTOX_TOKEN_INVALID" : "UPSTOX_UNAVAILABLE",
            message: error.message,
        });
    }
};

module.exports = { getTicker };
