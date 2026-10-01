// Zerodha Kite Connect v3 adapter for user broker linking. READ-ONLY: only session token,
// profile, holdings, positions and margins endpoints are ever called.
const crypto = require("crypto");
const axios = require("axios");
const {
    env, num, str, nextIstCutoff, makeHolding, makePosition, makeFunds, TokenExpiredError, asArray,
} = require("./common");

const API = "https://api.kite.trade";
const LOGIN_URL = "https://kite.zerodha.com/connect/login";
const TIMEOUT_MS = 15000;

const name = "zerodha";
const label = "Zerodha";

// ZERODHA_* names, with the older KITE_* names (ml/kite_*.py era) as a fallback
const apiKey = () => env("ZERODHA_API_KEY") || env("KITE_API_KEY");
const apiSecret = () => env("ZERODHA_API_SECRET") || env("KITE_API_SECRET");

const isConfigured = () => Boolean(apiKey() && apiSecret());

// Kite passes `redirect_params` back to the app's registered redirect URL as query params,
// which is how our signed state reaches /brokers/zerodha/callback
const buildConnectUrl = (state) => `${LOGIN_URL}?${new URLSearchParams({
    v: "3",
    api_key: apiKey(),
    redirect_params: new URLSearchParams({ state }).toString(),
})}`;

// Kite tokens expire at 06:00 IST the next day (or today, if linked before 06:00)
const tokenExpiresAt = (now = new Date()) => nextIstCutoff(6, 0, now);

const kiteHeaders = (token) => ({
    "X-Kite-Version": "3",
    Authorization: `token ${apiKey()}:${token}`,
});

// Kite reports an invalid/expired session as 403 with error_type "TokenException"
const isAuthFailure = (error) => {
    const status = error.response?.status;
    return status === 401 || status === 403 || error.response?.data?.error_type === "TokenException";
};

const get = async (token, path) => {
    try {
        const res = await axios.get(`${API}${path}`, { headers: kiteHeaders(token), timeout: TIMEOUT_MS });
        return res.data?.data;
    } catch (error) {
        if (isAuthFailure(error)) throw new TokenExpiredError("Zerodha session expired");
        throw error;
    }
};

// checksum = SHA-256(api_key + request_token + api_secret)
const checksum = (requestToken) => crypto.createHash("sha256")
    .update(`${apiKey()}${requestToken}${apiSecret()}`)
    .digest("hex");

// { request_token } from the callback -> { access_token, broker_user_id, broker_user_name }
const exchange = async ({ request_token: requestToken }) => {
    const res = await axios.post(
        `${API}/session/token`,
        new URLSearchParams({ api_key: apiKey(), request_token: requestToken, checksum: checksum(requestToken) }),
        { headers: { "X-Kite-Version": "3" }, timeout: TIMEOUT_MS }
    );
    const data = res.data?.data;
    if (!data?.access_token) throw new Error("Kite returned no access token");
    return {
        access_token: data.access_token,
        broker_user_id: str(data.user_id),
        broker_user_name: str(data.user_name),
    };
};

const fetchProfile = async (token) => {
    const data = await get(token, "/user/profile");
    return { broker_user_id: str(data?.user_id), broker_user_name: str(data?.user_name) };
};

// GET /portfolio/holdings item -> normalised holding
const normaliseHolding = (item = {}) => makeHolding({
    symbol: item.tradingsymbol,
    isin: item.isin,
    exchange: item.exchange,
    company_name: null,
    quantity: item.quantity,
    t1_quantity: item.t1_quantity,
    average_price: item.average_price,
    last_price: item.last_price,
    close_price: item.close_price,
    day_change_pct: item.day_change_percentage,
});

// GET /portfolio/positions -> data.net[] item -> normalised position
const normalisePosition = (item = {}) => makePosition({
    symbol: item.tradingsymbol,
    exchange: item.exchange,
    product: item.product,
    quantity: item.quantity,
    average_price: item.average_price,
    last_price: item.last_price,
    pnl: item.pnl,
    realised: item.realised,
    unrealised: item.unrealised,
});

// GET /user/margins -> { equity: { net, available: { live_balance, cash, ... }, utilised: { debits, ... } } }
const normaliseFunds = (data) => {
    const equity = data?.equity;
    if (!equity) return null;
    return makeFunds({
        available_cash: num(equity.net) ?? num(equity.available?.live_balance) ?? num(equity.available?.cash),
        used_margin: equity.utilised?.debits,
    });
};

const fetchPortfolio = async (token) => {
    const [holdings, positions, funds] = await Promise.allSettled([
        get(token, "/portfolio/holdings"),
        get(token, "/portfolio/positions"),
        get(token, "/user/margins"),
    ]);

    for (const result of [holdings, positions]) {
        if (result.status === "rejected") throw result.reason;
    }
    if (funds.status === "rejected" && funds.reason instanceof TokenExpiredError) throw funds.reason;

    return {
        holdings: asArray(holdings.value).map(normaliseHolding),
        positions: asArray(positions.value?.net).map(normalisePosition).filter((p) => p.quantity !== 0 || p.pnl),
        funds: funds.status === "fulfilled" ? normaliseFunds(funds.value) : null,
    };
};

// DELETE /session/token invalidates the access token (best effort; callers ignore failures)
const logout = async (token) => {
    await axios.delete(`${API}/session/token`, {
        params: { api_key: apiKey(), access_token: token },
        headers: kiteHeaders(token),
        timeout: TIMEOUT_MS,
    });
};

module.exports = {
    name,
    label,
    isConfigured,
    buildConnectUrl,
    tokenExpiresAt,
    exchange,
    fetchProfile,
    fetchPortfolio,
    logout,
    checksum,
    normaliseHolding,
    normalisePosition,
    normaliseFunds,
};
