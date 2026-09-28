const {
    saveAccessToken,
    hasAdminKey,
    isAdminKey,
    buildLoginUrl,
    isValidState,
    exchangeCode,
    requestAccessToken,
    acceptNotifiedToken,
    UpstoxRenewError,
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

// Admin key from the X-Admin-Key header (scheduled job) or ?key= (phone bookmark)
const adminKeyFrom = (req) => req.get("x-admin-key") || req.body?.key || req.query.key;

// POST /upstox/request-token (X-Admin-Key) [?force=1]: ask Upstox to send the owner an approval
// notification. Skips when today's token still works. Used by .github/workflows/upstox-token.yml.
const requestToken = async (req, res) => {
    if (!hasAdminKey() || !isAdminKey(adminKeyFrom(req))) {
        return res.status(403).json({ success: false, message: "Missing or wrong admin key" });
    }
    try {
        const result = await requestAccessToken({ force: req.query.force === "1" });
        res.json({ success: true, ...result });
    } catch (error) {
        console.log("Upstox token request failed:", error.message);
        const known = error instanceof UpstoxRenewError;
        res.status(known ? 502 : 500).json({ success: false, message: known ? error.message : "Token request failed" });
    }
};

// GET /upstox/request?key=...: the same from a phone, as a page
const requestTokenPage = async (req, res) => {
    if (!hasAdminKey()) return res.status(503).send(page("Not set up", "UPSTOX_ADMIN_KEY is not set on the server.", "error"));
    if (!isAdminKey(req.query.key)) return res.status(403).send(page("Not allowed", "Missing or wrong admin key.", "error"));
    try {
        const result = await requestAccessToken({ force: req.query.force === "1" });
        if (result.skipped) {
            return res.send(page("Already connected", `Live market data is on today (${result.user}). Nothing to approve.`, "success"));
        }
        res.send(page("Check your phone", "Upstox sent an approval request to the Upstox app and WhatsApp. Tap Approve and live prices start within a minute.", "info"));
    } catch (error) {
        console.log("Upstox token request failed:", error.message);
        res.status(502).send(page("Request failed", error instanceof UpstoxRenewError ? error.message : "Try again, or use /upstox/login.", "error"));
    }
};

// POST /upstox/notifier: Upstox delivers the approved token here (no auth by design, so
// acceptNotifiedToken verifies the token with Upstox and checks it's the owner's account)
const notifier = async (req, res) => {
    try {
        const result = await acceptNotifiedToken(req.body);
        console.log(`Upstox token renewed via approval for ${result.user}`);
        res.json({ status: "success" });
    } catch (error) {
        const known = error instanceof UpstoxRenewError;
        console.log("Upstox notifier rejected:", known ? error.message : error.message || error);
        res.status(known ? 400 : 500).json({ status: "error" });
    }
};

module.exports = { login, callback, requestToken, requestTokenPage, notifier };
