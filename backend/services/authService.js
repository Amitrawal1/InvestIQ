// User accounts: the `users` table, validation and a best-effort login rate limiter
const db = require("../config/db");

const USERS_SQL = `
CREATE TABLE IF NOT EXISTS users (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    email VARCHAR(255) NOT NULL UNIQUE,
    username VARCHAR(80) NOT NULL,
    password_hash VARCHAR(255) NULL,              -- NULL for accounts that only use Google
    google_sub VARCHAR(64) NULL UNIQUE,           -- Google account id ("sub"), when linked
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    last_login_at DATETIME NULL
)`;

// Tables created before Google sign-in: add google_sub and allow password-less accounts
const migrateUsersTable = async () => {
    const [cols] = await db.query(
        `SELECT COLUMN_NAME, IS_NULLABLE FROM information_schema.COLUMNS
         WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'users'`
    );
    const byName = Object.fromEntries(cols.map((c) => [c.COLUMN_NAME, c]));
    if (!byName.google_sub) {
        await db.query("ALTER TABLE users ADD COLUMN google_sub VARCHAR(64) NULL");
        await db.query("ALTER TABLE users ADD UNIQUE KEY uq_users_google_sub (google_sub)");
    }
    if (byName.password_hash && byName.password_hash.IS_NULLABLE === "NO") {
        await db.query("ALTER TABLE users MODIFY password_hash VARCHAR(255) NULL");
    }
};

// Created lazily, once per process (retried if the first attempt fails)
let usersReady = null;
const ensureUsersTable = () => {
    if (!usersReady) {
        usersReady = db.query(USERS_SQL).then(migrateUsersTable);
        usersReady.catch(() => { usersReady = null; });
    }
    return usersReady;
};

// Public shape only: never includes password_hash or google_sub themselves
const PUBLIC_FIELDS = `id, username, email, created_at,
    password_hash IS NOT NULL AS has_password, google_sub IS NOT NULL AS google_linked`;

const toPublicUser = (row) => (row ? {
    id: Number(row.id),
    username: row.username,
    email: row.email,
    created_at: row.created_at,
    has_password: Boolean(Number(row.has_password)),
    google_linked: Boolean(Number(row.google_linked)),
} : null);

const findUserById = async (id) => {
    await ensureUsersTable();
    const [rows] = await db.query(`SELECT ${PUBLIC_FIELDS} FROM users WHERE id = ?`, [id]);
    return toPublicUser(rows[0]);
};

// Includes the hash: for password checks inside the backend only
const findUserWithHash = async ({ id, email }) => {
    await ensureUsersTable();
    const [rows] = id !== undefined
        ? await db.query(`SELECT ${PUBLIC_FIELDS}, password_hash, google_sub FROM users WHERE id = ?`, [id])
        : await db.query(`SELECT ${PUBLIC_FIELDS}, password_hash, google_sub FROM users WHERE email = ?`, [email]);
    return rows[0] || null;
};

const findUserByGoogleSub = async (sub) => {
    await ensureUsersTable();
    const [rows] = await db.query(`SELECT ${PUBLIC_FIELDS}, google_sub FROM users WHERE google_sub = ?`, [sub]);
    return rows[0] || null;
};

// ---------------------------------------------------------------------------------------------
// Validation
// ---------------------------------------------------------------------------------------------

const EMAIL_RE = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
const MIN_PASSWORD = 8;
const MAX_PASSWORD = 200; // scrypt cost is fixed, but don't accept megabyte "passwords"

const normaliseEmail = (value) => (typeof value === "string" ? value.trim().toLowerCase() : "");
const normaliseUsername = (value) => (typeof value === "string" ? value.trim().replace(/\s+/g, " ") : "");

const emailError = (email) => {
    if (!email || email.length > 255 || !EMAIL_RE.test(email)) return "Enter a valid email address";
    return null;
};

const usernameError = (username) => {
    if (!username) return "Username is required";
    if (username.length > 80) return "Username must be at most 80 characters";
    return null;
};

const passwordError = (password, label = "Password") => {
    if (typeof password !== "string" || password.length < MIN_PASSWORD) return `${label} must be at least ${MIN_PASSWORD} characters`;
    if (password.length > MAX_PASSWORD) return `${label} must be at most ${MAX_PASSWORD} characters`;
    return null;
};

const isDuplicateKey = (error) => error && (error.code === "ER_DUP_ENTRY" || error.errno === 1062);

// ---------------------------------------------------------------------------------------------
// Brute-force limiter (in memory: per server instance, so best effort on serverless).
// Failures are counted per IP+account and per account alone (the second catches IP rotation).
// ---------------------------------------------------------------------------------------------

const WINDOW_MS = 15 * 60 * 1000;
const LIMITS = { pair: 5, account: 20 };
const failures = new Map();

const bucket = (key) => {
    const now = Date.now();
    const entry = failures.get(key);
    if (!entry || entry.resetAt <= now) return { count: 0, resetAt: now + WINDOW_MS };
    return entry;
};

const keysFor = (ip, account) => [[`pair:${ip}|${account}`, LIMITS.pair], [`acct:${account}`, LIMITS.account]];

// Seconds until the caller may retry, or 0 if allowed
const retryAfter = (ip, account) => {
    let wait = 0;
    for (const [key, limit] of keysFor(ip, account)) {
        const entry = bucket(key);
        if (entry.count >= limit) wait = Math.max(wait, Math.ceil((entry.resetAt - Date.now()) / 1000));
    }
    return wait;
};

const recordFailure = (ip, account) => {
    for (const [key] of keysFor(ip, account)) {
        const entry = bucket(key);
        failures.set(key, { count: entry.count + 1, resetAt: entry.resetAt });
    }
    // Keep the map from growing without bound on a long-lived server
    if (failures.size > 10000) {
        const now = Date.now();
        for (const [key, entry] of failures) if (entry.resetAt <= now) failures.delete(key);
    }
};

const clearFailures = (ip, account) => {
    failures.delete(`pair:${ip}|${account}`);
};

module.exports = {
    ensureUsersTable,
    toPublicUser,
    findUserById,
    findUserWithHash,
    findUserByGoogleSub,
    normaliseEmail,
    normaliseUsername,
    emailError,
    usernameError,
    passwordError,
    isDuplicateKey,
    retryAfter,
    recordFailure,
    clearFailures,
};
