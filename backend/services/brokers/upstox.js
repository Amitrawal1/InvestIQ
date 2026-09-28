// Upstox (API v2) adapter for user broker linking. READ-ONLY: only the profile, holdings,
// positions and funds endpoints plus token exchange / logout are ever called.
const axios = require("axios");
const { exchangeCode } = require("../upstoxAuthService");
const {
    env, num, str, nextIstCutoff, makeHolding, makePosition, makeFunds, TokenExpiredError, asArray,
} = require("./common");

const API = "https://api.upstox.com/v2";
const AUTH_DIALOG_URL = `${API}/login/authorization/dialog`;
const TIMEOUT_MS = 15000;

const name = "upstox";
const label = "Upstox";

const isConfigured = () => ["UPSTOX_CLIENT_ID", "UPSTOX_CLIENT_SECRET", "UPSTOX_REDIRECT_URI"].every((key) => env(key));

// Same Upstox app and redirect URI as the admin market-data login; the callback tells the two
// apart by the shape of `state`
const buildConnectUrl = (state) => `${AUTH_DIALOG_URL}?${new URLSearchParams({
    client_id: env("UPSTOX_CLIENT_ID"),
    redirect_uri: env("UPSTOX_REDIRECT_URI"),
    response_type: "code",
    state,
})}`;

// Upstox tokens expire at 03:30 IST the next day (or today, if linked before 03:30)
const tokenExpiresAt = (now = new Date()) => nextIstCutoff(3, 30, now);

const isAuthFailure = (error) => {
    const status = error.response?.status;
    return status === 401 || status === 403;
};

const get = async (token, path, params) => {
    try {
        const res = await axios.get(`${API}${path}`, {
            params,
            headers: { Accept: "application/json", Authorization: `Bearer ${token}` },
            timeout: TIMEOUT_MS,
        });
        return res.data?.data;
    } catch (error) {
        if (isAuthFailure(error)) throw new TokenExpiredError("Upstox session expired");
        throw error;
    }
};

// { code } from the callback -> { access_token, broker_user_id, broker_user_name }
const exchange = async ({ code }) => {
    const data = await exchangeCode(code);
    if (!data?.access_token) throw new Error("Upstox returned no access token");
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

// GET /v2/portfolio/long-term-holdings item -> normalised holding
const normaliseHolding = (item = {}) => makeHolding({
    symbol: item.trading_symbol ?? item.tradingsymbol,
    isin: item.isin,
    exchange: item.exchange,
    company_name: item.company_name,
    quantity: item.quantity,
    t1_quantity: item.t1_quantity,
    average_price: item.average_price,
    last_price: item.last_price,
    close_price: item.close_price,
    day_change_pct: item.day_change_percentage,
});

// GET /v2/portfolio/short-term-positions item -> normalised position
const normalisePosition = (item = {}) => {
    const realised = num(item.realised);
    const unrealised = num(item.unrealised);
    return makePosition({
        symbol: item.trading_symbol ?? item.tradingsymbol,
        exchange: item.exchange,
        product: item.product,
        quantity: item.quantity,
        average_price: item.average_price,
        last_price: item.last_price,
        pnl: num(item.pnl) ?? (realised === null && unrealised === null ? null : (realised ?? 0) + (unrealised ?? 0)),
        realised,
        unrealised,
    });
};

// GET /v2/user/get-funds-and-margin?segment=SEC -> { equity: { available_margin, used_margin, ... } }
const normaliseFunds = (data) => {
    const equity = data?.equity;
    if (!equity) return null;
    return makeFunds({ available_cash: equity.available_margin, used_margin: equity.used_margin });
};

const fetchPortfolio = async (token) => {
    // Funds are best effort: Upstox's funds service is down for maintenance late at night
    const [holdings, positions, funds] = await Promise.allSettled([
        get(token, "/portfolio/long-term-holdings"),
        get(token, "/portfolio/short-term-positions"),
        get(token, "/user/get-funds-and-margin", { segment: "SEC" }),
    ]);

    for (const result of [holdings, positions]) {
        if (result.status === "rejected") throw result.reason;
    }
    if (funds.status === "rejected" && funds.reason instanceof TokenExpiredError) throw funds.reason;

    return {
        holdings: asArray(holdings.value).map(normaliseHolding),
        positions: asArray(positions.value).map(normalisePosition).filter((p) => p.quantity !== 0 || p.pnl),
        funds: funds.status === "fulfilled" ? normaliseFunds(funds.value) : null,
    };
};

// Invalidates the Upstox session (best effort; callers ignore failures)
const logout = async (token) => {
    await axios.delete(`${API}/logout`, {
        headers: { Accept: "application/json", Authorization: `Bearer ${token}` },
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
    normaliseHolding,
    normalisePosition,
    normaliseFunds,
};
