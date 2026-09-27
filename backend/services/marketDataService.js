const axios = require("axios");
const { getAccessToken } = require("./upstoxAuthService");

const QUOTES_URL = "https://api.upstox.com/v2/market-quote/quotes";
const CACHE_MS = 15 * 1000;

const TICKER_INSTRUMENTS = [
    { name: "NIFTY 50", key: "NSE_INDEX|Nifty 50" },
    { name: "SENSEX", key: "BSE_INDEX|SENSEX" },
    { name: "BANK NIFTY", key: "NSE_INDEX|Nifty Bank" },
    { name: "RELIANCE", key: "NSE_EQ|INE002A01018" },
    { name: "TCS", key: "NSE_EQ|INE467B01029" },
    { name: "INFY", key: "NSE_EQ|INE009A01021" },
    { name: "HDFC BANK", key: "NSE_EQ|INE040A01034" },
    { name: "ICICI BANK", key: "NSE_EQ|INE090A01021" },
    { name: "ITC", key: "NSE_EQ|INE154A01025" },
];

class UpstoxTokenError extends Error {}

let cache = { at: 0, data: null };

const fetchQuotes = async (instrumentKeys) => {
    // Looked up on every fetch so a fresh login works without a restart
    const token = await getAccessToken();
    if (!token) throw new UpstoxTokenError("No Upstox access token yet: log in via /upstox/login");

    try {
        const res = await axios.get(QUOTES_URL, {
            params: { instrument_key: instrumentKeys.join(",") },
            headers: { Accept: "application/json", Authorization: `Bearer ${token}` },
            timeout: 8000,
        });
        return res.data.data || {};
    } catch (error) {
        if (error.response?.status === 401) {
            throw new UpstoxTokenError("Upstox access token is invalid or expired");
        }
        throw error;
    }
};

// Response is keyed "NSE_EQ:RELIANCE" style; match back to our keys via instrument_token
const getTickerQuotes = async () => {
    if (cache.data && Date.now() - cache.at < CACHE_MS) return cache.data;

    const quotes = await fetchQuotes(TICKER_INSTRUMENTS.map((i) => i.key));
    const byToken = {};
    for (const q of Object.values(quotes)) byToken[q.instrument_token] = q;

    const data = TICKER_INSTRUMENTS.map(({ name, key }) => {
        const q = byToken[key];
        if (!q) return { name, key, price: null, change: null, changePct: null };

        const prevClose = q.last_price - q.net_change;
        return {
            name,
            key,
            price: q.last_price,
            change: q.net_change,
            changePct: prevClose ? (q.net_change / prevClose) * 100 : null,
            timestamp: q.timestamp,
        };
    });

    cache = { at: Date.now(), data };
    return data;
};

module.exports = {
    getTickerQuotes,
    UpstoxTokenError,
};
