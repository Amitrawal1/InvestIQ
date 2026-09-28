// Crypto primitives for accounts and broker linking, built on Node's `crypto` only:
//   - scrypt password hashing
//   - HS256 JWT sessions
//   - HMAC-signed OAuth `state`
//   - AES-256-GCM encryption of broker access tokens at rest
// Every function that needs a secret throws a ConfigError when it is missing, so callers can
// answer 503 ("not configured") instead of silently running with a weak/empty key.
const crypto = require("crypto");

const env = (name) => (process.env[name] || "").trim();

class ConfigError extends Error {}

// ---------------------------------------------------------------------------------------------
// Configuration
// ---------------------------------------------------------------------------------------------

const MIN_JWT_SECRET_LENGTH = 32;

const isAuthConfigured = () => env("AUTH_JWT_SECRET").length >= MIN_JWT_SECRET_LENGTH;

const isTokenKeyConfigured = () => /^[0-9a-fA-F]{64}$/.test(env("BROKER_TOKEN_KEY"));

const jwtSecret = () => {
    if (!isAuthConfigured()) throw new ConfigError("AUTH_JWT_SECRET is not set");
    return env("AUTH_JWT_SECRET");
};

// Separate key for OAuth state (derived from the JWT secret) so a session token can never be
// replayed as a state value or vice versa
const stateKey = () => crypto.createHmac("sha256", jwtSecret()).update("investiq:oauth-state:v1").digest();

const tokenKey = () => {
    if (!isTokenKeyConfigured()) throw new ConfigError("BROKER_TOKEN_KEY is not set");
    return Buffer.from(env("BROKER_TOKEN_KEY"), "hex");
};

// ---------------------------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------------------------

const b64url = (input) => Buffer.from(input).toString("base64url");

const fromB64urlJson = (text) => {
    try {
        return JSON.parse(Buffer.from(String(text), "base64url").toString("utf8"));
    } catch {
        return null;
    }
};

// Constant-time string comparison (false for different lengths)
const safeEqual = (a, b) => {
    const left = Buffer.from(String(a));
    const right = Buffer.from(String(b));
    return left.length === right.length && crypto.timingSafeEqual(left, right);
};

const nowSeconds = () => Math.floor(Date.now() / 1000);

// ---------------------------------------------------------------------------------------------
// Passwords: scrypt$<salt hex>$<key hex>, N=16384 r=8 p=1, 64-byte key, 16-byte random salt
// ---------------------------------------------------------------------------------------------

const SCRYPT_PARAMS = { N: 16384, r: 8, p: 1, maxmem: 64 * 1024 * 1024 };
const SCRYPT_KEYLEN = 64;

const scrypt = (password, salt) => new Promise((resolve, reject) => {
    crypto.scrypt(String(password), salt, SCRYPT_KEYLEN, SCRYPT_PARAMS, (error, key) => {
        if (error) reject(error);
        else resolve(key);
    });
});

const hashPassword = async (password) => {
    const salt = crypto.randomBytes(16);
    const key = await scrypt(password, salt);
    return `scrypt$${salt.toString("hex")}$${key.toString("hex")}`;
};

// A fixed, valid-looking hash used when the email doesn't exist, so a login for an unknown
// account costs the same scrypt work as a real one (no user-enumeration timing signal)
const DUMMY_HASH = `scrypt$${"0".repeat(32)}$${"0".repeat(128)}`;

const verifyPassword = async (password, stored) => {
    const [scheme, saltHex, keyHex] = String(stored || DUMMY_HASH).split("$");
    if (scheme !== "scrypt" || !saltHex || !keyHex) return false;

    const expected = Buffer.from(keyHex, "hex");
    const actual = await scrypt(password, Buffer.from(saltHex, "hex"));
    return expected.length === actual.length && crypto.timingSafeEqual(expected, actual) && Boolean(stored);
};

// ---------------------------------------------------------------------------------------------
// JWT (HS256): payload { sub, email, iat, exp }
// ---------------------------------------------------------------------------------------------

const JWT_TTL_SECONDS = 7 * 24 * 60 * 60;
const JWT_HEADER = b64url(JSON.stringify({ alg: "HS256", typ: "JWT" }));

const hmacB64url = (key, data) => crypto.createHmac("sha256", key).update(data).digest("base64url");

const signJwt = ({ sub, email }) => {
    const iat = nowSeconds();
    const payload = b64url(JSON.stringify({ sub: String(sub), email, iat, exp: iat + JWT_TTL_SECONDS }));
    const body = `${JWT_HEADER}.${payload}`;
    return `${body}.${hmacB64url(jwtSecret(), body)}`;
};

// Returns the payload, or null for anything malformed, tampered with or expired.
// Only HS256 is accepted (the header is compared byte-for-byte, so "alg: none" can't sneak in).
const verifyJwt = (token) => {
    const parts = String(token || "").split(".");
    if (parts.length !== 3) return null;

    const [header, payload, signature] = parts;
    if (header !== JWT_HEADER) return null;
    if (!safeEqual(signature, hmacB64url(jwtSecret(), `${header}.${payload}`))) return null;

    const claims = fromB64urlJson(payload);
    if (!claims || !claims.sub || typeof claims.exp !== "number" || claims.exp <= nowSeconds()) return null;
    return claims;
};

// ---------------------------------------------------------------------------------------------
// OAuth state: base64url(JSON { uid, p: purpose, b: broker, n: nonce, exp }).<HMAC>
// ---------------------------------------------------------------------------------------------

const STATE_TTL_SECONDS = 10 * 60;

const signState = ({ userId, purpose, broker }) => {
    const payload = b64url(JSON.stringify({
        uid: String(userId),
        p: purpose,
        b: broker,
        n: crypto.randomBytes(12).toString("base64url"),
        exp: nowSeconds() + STATE_TTL_SECONDS,
    }));
    return `${payload}.${hmacB64url(stateKey(), payload)}`;
};

// Cheap check (no secret needed) for "this is one of our user-link states", used by the shared
// Upstox callback to tell user links apart from the admin market-data login
const looksLikeUserState = (state) => {
    const [payload, signature, extra] = String(state || "").split(".");
    if (!payload || !signature || extra !== undefined) return false;
    const decoded = fromB64urlJson(payload);
    return Boolean(decoded && typeof decoded === "object" && decoded.p);
};

// Returns { userId, purpose, broker } or null when forged / expired / malformed
const verifyState = (state) => {
    const [payload, signature, extra] = String(state || "").split(".");
    if (!payload || !signature || extra !== undefined) return null;
    if (!safeEqual(signature, hmacB64url(stateKey(), payload))) return null;

    const decoded = fromB64urlJson(payload);
    if (!decoded || typeof decoded.exp !== "number" || decoded.exp <= nowSeconds()) return null;
    return { userId: decoded.uid, purpose: decoded.p, broker: decoded.b };
};

// ---------------------------------------------------------------------------------------------
// AES-256-GCM for broker access tokens: "v1:<iv>:<tag>:<ciphertext>" (base64url parts).
// The additional authenticated data binds a ciphertext to its user + broker, so a value copied
// into another row fails to decrypt.
// ---------------------------------------------------------------------------------------------

const encryptToken = (plaintext, aad) => {
    const iv = crypto.randomBytes(12);
    const cipher = crypto.createCipheriv("aes-256-gcm", tokenKey(), iv);
    cipher.setAAD(Buffer.from(String(aad)));
    const ciphertext = Buffer.concat([cipher.update(String(plaintext), "utf8"), cipher.final()]);
    const tag = cipher.getAuthTag();
    return ["v1", iv, tag, ciphertext].map((part) => (typeof part === "string" ? part : part.toString("base64url"))).join(":");
};

// Returns the plaintext or null if the value is corrupt, tampered with, or the key changed
const decryptToken = (stored, aad) => {
    const [version, iv, tag, ciphertext] = String(stored || "").split(":");
    if (version !== "v1" || !iv || !tag || ciphertext === undefined) return null;
    try {
        const decipher = crypto.createDecipheriv("aes-256-gcm", tokenKey(), Buffer.from(iv, "base64url"));
        decipher.setAAD(Buffer.from(String(aad)));
        decipher.setAuthTag(Buffer.from(tag, "base64url"));
        return Buffer.concat([decipher.update(Buffer.from(ciphertext, "base64url")), decipher.final()]).toString("utf8");
    } catch (error) {
        if (error instanceof ConfigError) throw error;
        return null;
    }
};

module.exports = {
    ConfigError,
    isAuthConfigured,
    isTokenKeyConfigured,
    hashPassword,
    verifyPassword,
    signJwt,
    verifyJwt,
    signState,
    verifyState,
    looksLikeUserState,
    encryptToken,
    decryptToken,
    safeEqual,
};
