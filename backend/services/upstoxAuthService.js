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

// `state` proves the login was started by someone holding UPSTOX_ADMIN_KEY, so a
// stranger can't finish an OAuth flow and replace the token with their own account's
const signState = (timestamp) =>
    crypto.createHmac("sha256", process.env.UPSTOX_ADMIN_KEY).update(String(timestamp)).digest("hex");

const isAdminKey = (key) => {
    const expected = process.env.UPSTOX_ADMIN_KEY || "";
    if (!expected || typeof key !== "string" || key.length !== expected.length) return false;
    return crypto.timingSafeEqual(Buffer.from(key), Buffer.from(expected));
};

const buildLoginUrl = () => {
    const timestamp = Date.now();
    const params = new URLSearchParams({
        client_id: process.env.UPSTOX_CLIENT_ID,
        redirect_uri: process.env.UPSTOX_REDIRECT_URI,
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
            client_id: process.env.UPSTOX_CLIENT_ID,
            client_secret: process.env.UPSTOX_CLIENT_SECRET,
            redirect_uri: process.env.UPSTOX_REDIRECT_URI,
            grant_type: "authorization_code",
        }),
        { headers: { Accept: "application/json" }, timeout: 10000 }
    );
    return res.data;
};

module.exports = {
    getAccessToken,
    saveAccessToken,
    isAdminKey,
    buildLoginUrl,
    isValidState,
    exchangeCode,
};
