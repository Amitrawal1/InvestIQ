const crypto = require("crypto");
const fs = require("fs");
const path = require("path");
const axios = require("axios");
const db = require("../config/db");

// Legacy location written by ml/upstox_token.py; only exists on a dev machine
const TOKEN_FILE = path.join(__dirname, "..", "..", "ml", "upstox_access_token.txt");
const AUTH_DIALOG_URL = "https://api.upstox.com/v2/login/authorization/dialog";
const TOKEN_URL = "https://api.upstox.com/v2/login/authorization/token";
const STATE_MAX_AGE_MS = 10 * 60 * 1000;

const TABLE_SQL = `
CREATE TABLE IF NOT EXISTS upstox_tokens (
    id TINYINT NOT NULL PRIMARY KEY,
    access_token TEXT NOT NULL,
    user_id VARCHAR(50) NULL,
    user_name VARCHAR(120) NULL,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
)`;

let tableReady = null;
const ensureTable = () => {
    if (!tableReady) {
        tableReady = db.query(TABLE_SQL);
        tableReady.catch(() => { tableReady = null; });
    }
    return tableReady;
};

// Latest token from the DB (shared by Render and local dev), falling back to the local file
const getAccessToken = async () => {
    try {
        await ensureTable();
        const [rows] = await db.query("SELECT access_token FROM upstox_tokens WHERE id = 1");
        if (rows[0]?.access_token) return rows[0].access_token;
    } catch (error) {
        console.log("Upstox token lookup failed:", error.message);
    }

    try {
        return fs.readFileSync(TOKEN_FILE, "utf8").trim();
    } catch {
        return "";
    }
};

const saveAccessToken = async ({ access_token, user_id, user_name }) => {
    await ensureTable();
    await db.query(
        `INSERT INTO upstox_tokens (id, access_token, user_id, user_name) VALUES (1, ?, ?, ?)
         ON DUPLICATE KEY UPDATE access_token = VALUES(access_token), user_id = VALUES(user_id),
             user_name = VALUES(user_name), created_at = CURRENT_TIMESTAMP`,
        [access_token, user_id || null, user_name || null]
    );
};

// Trimmed because values pasted into a dashboard often carry a stray space or newline
const env = (name) => (process.env[name] || "").trim();

const adminKey = () => env("UPSTOX_ADMIN_KEY");

const hasAdminKey = () => adminKey().length > 0;

// `state` proves the login was started by someone holding UPSTOX_ADMIN_KEY, so a
// stranger can't finish an OAuth flow and replace the token with their own account's
const signState = (timestamp) =>
    crypto.createHmac("sha256", adminKey()).update(String(timestamp)).digest("hex");

const isAdminKey = (key) => {
    const expected = adminKey();
    const given = typeof key === "string" ? key.trim() : "";
    if (!expected || given.length !== expected.length) return false;
    return crypto.timingSafeEqual(Buffer.from(given), Buffer.from(expected));
};

const buildLoginUrl = () => {
    const timestamp = Date.now();
    const params = new URLSearchParams({
        client_id: env("UPSTOX_CLIENT_ID"),
        redirect_uri: env("UPSTOX_REDIRECT_URI"),
        response_type: "code",
        state: `${timestamp}.${signState(timestamp)}`,
    });
    return `${AUTH_DIALOG_URL}?${params}`;
};

const isValidState = (state) => {
    const [timestamp, signature] = String(state || "").split(".");
    if (!timestamp || !signature || Date.now() - Number(timestamp) > STATE_MAX_AGE_MS) return false;

    const expected = signState(timestamp);
    return signature.length === expected.length
        && crypto.timingSafeEqual(Buffer.from(signature), Buffer.from(expected));
};

const exchangeCode = async (code) => {
    const res = await axios.post(
        TOKEN_URL,
        new URLSearchParams({
            code,
            client_id: env("UPSTOX_CLIENT_ID"),
            client_secret: env("UPSTOX_CLIENT_SECRET"),
            redirect_uri: env("UPSTOX_REDIRECT_URI"),
            grant_type: "authorization_code",
        }),
        { headers: { Accept: "application/json" }, timeout: 10000 }
    );
    return res.data;
};

// ---------------------------------------------------------------------------------------------
// Tap-to-approve renewal (Upstox "Access Token Request", v3, beta):
//   1. requestAccessToken() asks Upstox for a token; Upstox notifies the account owner in the
//      Upstox app and on WhatsApp.
//   2. The owner taps Approve; Upstox POSTs the token to our Notifier Webhook (/upstox/notifier).
//   3. acceptNotifiedToken() checks the token with Upstox before saving it: the webhook has no
//      authentication, so anyone could POST to it.
// Docs: https://upstox.com/developer/api-documentation/access-token-request/
// ---------------------------------------------------------------------------------------------

const TOKEN_REQUEST_URL = "https://api.upstox.com/v3/login/auth/token/request";
const PROFILE_URL = "https://api.upstox.com/v2/user/profile";

class UpstoxRenewError extends Error {}

// -> profile ({ user_id, user_name, ... }) when the token works, else null
const tokenProfile = async (token) => {
    if (!token) return null;
    try {
        const res = await axios.get(PROFILE_URL, {
            headers: { Accept: "application/json", Authorization: `Bearer ${token}` },
            timeout: 8000,
        });
        return res.data?.data || null;
    } catch (error) {
        if (error.response?.status === 401) return null;
        throw error;
    }
};

// Whose token the site may use: UPSTOX_OWNER_USER_ID, else the account of the last saved token
const ownerUserId = async () => {
    if (env("UPSTOX_OWNER_USER_ID")) return env("UPSTOX_OWNER_USER_ID").toUpperCase();
    await ensureTable();
    const [rows] = await db.query("SELECT user_id FROM upstox_tokens WHERE id = 1");
    return (rows[0]?.user_id || "").toUpperCase();
};

// -> { skipped: true, user } when today's token still works (unless force), else
//    { requested: true, expires } after Upstox has sent the approval notification
const requestAccessToken = async ({ force = false } = {}) => {
    if (!force) {
        const current = await tokenProfile(await getAccessToken()).catch(() => null);
        if (current) return { skipped: true, user: current.user_name || current.user_id };
    }
    const clientId = env("UPSTOX_CLIENT_ID");
    const clientSecret = env("UPSTOX_CLIENT_SECRET");
    if (!clientId || !clientSecret) throw new UpstoxRenewError("UPSTOX_CLIENT_ID / UPSTOX_CLIENT_SECRET are not set");
    try {
        const res = await axios.post(
            `${TOKEN_REQUEST_URL}/${encodeURIComponent(clientId)}`,
            { client_secret: clientSecret },
            { headers: { Accept: "application/json", "Content-Type": "application/json" }, timeout: 10000 }
        );
        return { requested: true, expires: res.data?.data?.authorization_expiry || null };
    } catch (error) {
        const detail = error.response?.data?.errors?.[0]?.message || error.response?.status || error.message;
        throw new UpstoxRenewError(`Upstox refused the token request: ${detail}`);
    }
};

// Webhook payload: { client_id, user_id, access_token, token_type, expires_at, issued_at, message_type }
// -> { saved: true, user } or throws UpstoxRenewError (the caller answers 400)
const acceptNotifiedToken = async (payload) => {
    if (!payload || typeof payload !== "object") throw new UpstoxRenewError("Empty payload");
    if (payload.message_type && payload.message_type !== "access_token") {
        throw new UpstoxRenewError(`Ignored message_type ${payload.message_type}`);
    }
    if (payload.client_id !== env("UPSTOX_CLIENT_ID")) throw new UpstoxRenewError("Token is for another app");
    const token = typeof payload.access_token === "string" ? payload.access_token.trim() : "";
    if (!token || token.length > 4096) throw new UpstoxRenewError("Missing access_token");

    const owner = await ownerUserId();
    if (!owner) throw new UpstoxRenewError("Owner unknown: set UPSTOX_OWNER_USER_ID or log in once via /upstox/login");

    // The token must actually work and belong to the owner's Upstox account
    const profile = await tokenProfile(token);
    if (!profile) throw new UpstoxRenewError("Upstox rejected the token");
    if (String(profile.user_id || "").toUpperCase() !== owner) throw new UpstoxRenewError("Token belongs to a different Upstox account");

    await saveAccessToken({ access_token: token, user_id: profile.user_id, user_name: profile.user_name });
    return { saved: true, user: profile.user_name || profile.user_id };
};

module.exports = {
    requestAccessToken,
    acceptNotifiedToken,
    UpstoxRenewError,
    getAccessToken,
    saveAccessToken,
    hasAdminKey,
    isAdminKey,
    buildLoginUrl,
    isValidState,
    exchangeCode,
};
