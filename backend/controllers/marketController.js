const { getTickerQuotes, UpstoxTokenError } = require("../services/marketDataService");

const getTicker = async (req, res) => {
    try {
        const data = await getTickerQuotes();
        // Vercel's CDN serves the same response to every visitor for 2 s, so the function
        // (and Upstox) is called about once per 2 s no matter how many people are watching
        res.set("Cache-Control", "public, max-age=0, s-maxage=2, stale-while-revalidate=2");
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
