const {
    saveAccessToken,
    hasAdminKey,
    isAdminKey,
    buildLoginUrl,
    isValidState,
    exchangeCode,
} = require("../services/upstoxAuthService");
const { looksLikeUserState } = require("../services/cryptoService");
const { upstoxLinkCallback } = require("./brokerController");

const { resultPage } = require("../services/resultPage");

const siteLink = () => {
    const base = (process.env.FRONTEND_URL || "").trim().replace(/\/+$/, "");
    return base ? { href: `${base}/portfolio`, label: "Return to Portfolio" } : { label: "Go back" };
};
const page = (title, message, tone = "info") => resultPage({ title, message, tone, action: siteLink() });

// Daily login: open /upstox/login?key=<UPSTOX_ADMIN_KEY>, sign in to Upstox, done
const login = (req, res) => {
    if (!hasAdminKey()) {
        return res.status(503).send(page("Not set up", "UPSTOX_ADMIN_KEY is not set on the server. Add it in the hosting environment variables and redeploy."));
    }
    if (!isAdminKey(req.query.key)) {
        return res.status(403).send(page("Not allowed", "Missing or wrong admin key."));
    }

    const missing = ["UPSTOX_CLIENT_ID", "UPSTOX_CLIENT_SECRET", "UPSTOX_REDIRECT_URI"].filter((name) => !(process.env[name] || "").trim());
    if (missing.length) {
        return res.status(503).send(page("Not set up", `Missing on the server: ${missing.join(", ")}. Add them and redeploy.`));
    }

    res.redirect(buildLoginUrl());
};

// One redirect URI serves two flows: user broker linking (signed JSON state, purpose "link")
// and the admin market-data login below (state "<timestamp>.<hex hmac>"), unchanged
const callback = async (req, res) => {
    if (looksLikeUserState(req.query.state)) return upstoxLinkCallback(req, res);
    try {
        return await adminCallback(req, res);
    } catch (err) {
        console.log("Upstox admin callback failed:", err.message);
        if (!res.headersSent) res.status(500).send(page("Something went wrong", "Start again from /upstox/login.", "error"));
    }
};

const adminCallback = async (req, res) => {
    const { code, state, error } = req.query;

    if (error) return res.status(400).send(page("Upstox login cancelled", String(error), "error"));
    if (!code || !isValidState(state)) {
        return res.status(400).send(page("Link expired", "This login link expired or wasn't started from InvestIQ. Start again from Portfolio.", "error"));
    }

    try {
        const token = await exchangeCode(code);
        await saveAccessToken(token);
        res.send(page("Upstox connected", "Live market data is on until Upstox expires the token (around 3:30 AM IST). You can close this tab.", "success"));
    } catch (err) {
        console.log("Upstox token exchange failed:", err.response?.data || err.message);
        res.status(502).send(page("Upstox login failed", "Upstox rejected the code. Start again from /upstox/login.", "error"));
    }
};

module.exports = { login, callback };
