const { resultPage } = require("../services/resultPage");
const { signState, verifyState, ConfigError } = require("../services/cryptoService");
const { getBroker } = require("../services/brokers");
const { findUserById } = require("../services/authService");
const {
    ServiceError,
    frontendUrl,
    isBrokerConfigured,
    listConnections,
    completeLink,
    syncBroker,
    disconnect,
} = require("../services/portfolioService");

const fail = (res, status, message, code) => res.status(status).json({ success: false, message, ...(code ? { code } : {}) });

const handleError = (res, error, what) => {
    if (error instanceof ServiceError) return fail(res, error.status, error.message, error.code);
    if (error instanceof ConfigError) return fail(res, 503, "Broker linking isn't configured yet", "NOT_CONFIGURED");
    console.error(`${what} failed:`, error.message);
    return fail(res, 500, "Something went wrong. Try again.");
};

// Resolves :broker or answers 404
const brokerParam = (req, res) => {
    const broker = getBroker(req.params.broker);
    if (!broker) fail(res, 404, "Unknown broker", "UNKNOWN_BROKER");
    return broker;
};

// GET /brokers
const list = async (req, res) => {
    try {
        res.json(await listConnections(req.user.id));
    } catch (error) {
        handleError(res, error, "Broker list");
    }
};

// POST /brokers/:broker/connect -> { url } of the broker's own login page
const connect = (req, res) => {
    const broker = brokerParam(req, res);
    if (!broker) return;
    if (!isBrokerConfigured(broker)) {
        return fail(res, 503, `${broker.label} linking isn't configured yet`, "NOT_CONFIGURED");
    }
    const state = signState({ userId: req.user.id, purpose: "link", broker: broker.name });
    res.json({ success: true, url: broker.buildConnectUrl(state) });
};

// POST /brokers/:broker/sync -> { synced_at, totals }
const sync = async (req, res) => {
    const broker = brokerParam(req, res);
    if (!broker) return;
    try {
        res.json({ success: true, ...(await syncBroker(req.user.id, broker.name)) });
    } catch (error) {
        handleError(res, error, "Broker sync");
    }
};

// DELETE /brokers/:broker[?delete_data=1]
const remove = async (req, res) => {
    const broker = brokerParam(req, res);
    if (!broker) return;
    try {
        const deleteData = ["1", "true"].includes(String(req.query.delete_data || "").toLowerCase());
        res.json({ success: true, ...(await disconnect(req.user.id, broker.name, deleteData)) });
    } catch (error) {
        handleError(res, error, "Broker disconnect");
    }
};

// ---------------------------------------------------------------------------------------------
// OAuth callbacks (no JWT: the browser arrives from the broker; the signed state identifies the user)
// ---------------------------------------------------------------------------------------------

const backToFrontend = (res, query) => {
    const base = frontendUrl();
    if (!base) {
        return res.status(503).send(resultPage({
            title: query.linked ? "Account linked" : "Couldn't finish linking",
            message: "InvestIQ doesn't know its website address yet (FRONTEND_URL). Go back to the InvestIQ site and open Portfolio.",
            tone: query.linked ? "success" : "error",
            action: { label: "Go back" },
        }));
    }
    res.redirect(`${base}/portfolio?${new URLSearchParams(query)}`);
};

// Shared by /upstox/callback (purpose "link") and /brokers/zerodha/callback
// Any unexpected failure still sends the browser back to Portfolio (never a JSON error page)
const finishLink = async (res, brokerName, state, params, cancelled) => {
    try {
        return await finishLinkSteps(res, brokerName, state, params, cancelled);
    } catch (error) {
        console.log(`${brokerName} callback failed:`, error.message);
        if (!res.headersSent) backToFrontend(res, { error: "link_failed" });
    }
};

const finishLinkSteps = async (res, brokerName, state, params, cancelled) => {
    const broker = getBroker(brokerName);
    let claims = null;
    try {
        claims = verifyState(state);
    } catch (error) {
        if (!(error instanceof ConfigError)) throw error;
        return backToFrontend(res, { error: "not_configured" });
    }

    if (!claims || claims.purpose !== "link" || claims.broker !== broker.name) {
        return backToFrontend(res, { error: "invalid_state" });
    }
    if (cancelled) return backToFrontend(res, { error: "cancelled" });
    if (!isBrokerConfigured(broker)) return backToFrontend(res, { error: "not_configured" });

    try {
        if (!(await findUserById(claims.userId))) return backToFrontend(res, { error: "account_not_found" });
        await completeLink(claims.userId, broker, params);
        backToFrontend(res, { linked: broker.name });
    } catch (error) {
        // Status only: token exchange error bodies may include request details
        console.log(`${broker.label} link failed:`, error.response?.status || error.message);
        backToFrontend(res, { error: "link_failed" });
    }
};

// GET /upstox/callback with a user-link state (dispatched from upstoxController)
const upstoxLinkCallback = (req, res) => {
    const { code, state, error } = req.query;
    return finishLink(res, "upstox", state, { code: String(code || "") }, Boolean(error) || !code);
};

// GET /brokers/zerodha/callback?request_token=...&status=success&state=...
const zerodhaCallback = (req, res) => {
    const { request_token: requestToken, status, state } = req.query;
    return finishLink(res, "zerodha", state, { request_token: String(requestToken || "") }, status !== "success" || !requestToken);
};

module.exports = { list, connect, sync, remove, upstoxLinkCallback, zerodhaCallback };
