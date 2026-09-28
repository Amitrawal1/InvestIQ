// Helpers shared by the broker adapters: number coercion, IST token expiry and the
// normalised holding / position / funds shapes from docs/auth-and-portfolio.md
const IST_OFFSET_MS = (5 * 60 + 30) * 60 * 1000;

const env = (name) => (process.env[name] || "").trim();

// Finite number or null (brokers sometimes send null, "", or omit fields)
const num = (value) => {
    if (value === null || value === undefined || value === "") return null;
    const parsed = Number(value);
    return Number.isFinite(parsed) ? parsed : null;
};

const round = (value, digits = 2) => {
    if (value === null || !Number.isFinite(value)) return null;
    const factor = 10 ** digits;
    return Math.round(value * factor) / factor;
};

const pct = (part, whole) => (part === null || !whole ? null : round((part / whole) * 100));

const str = (value) => (value === null || value === undefined || value === "" ? null : String(value));

// Broker access tokens die at a fixed IST wall-clock time each day (Upstox 03:30, Zerodha 06:00).
// Returns the next such instant after `now` as a Date.
const nextIstCutoff = (hour, minute, now = new Date()) => {
    const ist = new Date(now.getTime() + IST_OFFSET_MS); // read with getUTC* = IST wall clock
    let cutoff = Date.UTC(ist.getUTCFullYear(), ist.getUTCMonth(), ist.getUTCDate(), hour, minute) - IST_OFFSET_MS;
    if (cutoff <= now.getTime()) cutoff += 24 * 60 * 60 * 1000;
    return new Date(cutoff);
};

// Upstox / Kite send symbols like "INFY-EQ" or "RELIANCE"; strip the series suffix for matching
const baseSymbol = (symbol) => (symbol ? String(symbol).toUpperCase().replace(/-(EQ|BE|BZ|SM|ST)$/, "") : null);

// Builds a normalised holding; derived values are computed from quantity/prices so both
// brokers agree (quantity includes T1 shares that are bought but not yet delivered)
const makeHolding = ({ symbol, isin, exchange, company_name, quantity, t1_quantity, average_price, last_price, close_price, day_change_pct }) => {
    const settled = num(quantity) ?? 0;
    const t1 = num(t1_quantity) ?? 0;
    const qty = settled + t1;
    const avg = num(average_price);
    const last = num(last_price);
    const close = num(close_price);

    const invested = avg === null ? null : round(qty * avg);
    const current = last === null ? null : round(qty * last);
    const pnl = invested === null || current === null ? null : round(current - invested);
    const dayChange = last !== null && close ? round((last - close) * qty) : null;
    const dayChangePct = last !== null && close ? pct(last - close, close) : round(num(day_change_pct));

    return {
        symbol: baseSymbol(symbol),
        isin: str(isin)?.toUpperCase() ?? null,
        exchange: str(exchange),
        company_name: str(company_name),
        quantity: qty,
        t1_quantity: t1,
        average_price: avg,
        last_price: last,
        close_price: close,
        invested,
        current_value: current,
        pnl,
        pnl_pct: pct(pnl, invested),
        day_change: dayChange,
        day_change_pct: dayChangePct,
    };
};

const makePosition = ({ symbol, exchange, product, quantity, average_price, last_price, pnl, realised, unrealised }) => ({
    symbol: baseSymbol(symbol),
    exchange: str(exchange),
    product: str(product),
    quantity: num(quantity),
    average_price: num(average_price),
    last_price: num(last_price),
    pnl: round(num(pnl)),
    realised: round(num(realised)),
    unrealised: round(num(unrealised)),
});

const makeFunds = ({ available_cash, used_margin }) => {
    const available = num(available_cash);
    const used = num(used_margin);
    if (available === null && used === null) return null;
    return {
        available_cash: round(available),
        used_margin: round(used),
        total: round((available ?? 0) + (used ?? 0)),
    };
};

const sum = (items, key) => round(items.reduce((acc, item) => acc + (num(item[key]) ?? 0), 0));

// { invested, current, pnl, day_change, count } for a list of normalised holdings
const holdingTotals = (holdings) => ({
    invested: sum(holdings, "invested"),
    current: sum(holdings, "current_value"),
    pnl: sum(holdings, "pnl"),
    day_change: sum(holdings, "day_change"),
    count: holdings.length,
});

// Error thrown when the broker rejects the token (expired / revoked / logged out elsewhere)
class TokenExpiredError extends Error {}

const asArray = (value) => (Array.isArray(value) ? value : []);

module.exports = {
    env,
    num,
    round,
    pct,
    str,
    nextIstCutoff,
    baseSymbol,
    makeHolding,
    makePosition,
    makeFunds,
    holdingTotals,
    TokenExpiredError,
    asArray,
};
