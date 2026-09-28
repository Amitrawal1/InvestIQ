// "Continue with Google": verifies a Google Identity Services ID token (a signed JWT) with
// Google's public keys and Node's crypto, so no Google SDK is needed.
// Docs: https://developers.google.com/identity/gsi/web/guides/verify-google-id-token
const crypto = require("crypto");
const axios = require("axios");

const CERTS_URL = "https://www.googleapis.com/oauth2/v3/certs";
const ISSUERS = new Set(["accounts.google.com", "https://accounts.google.com"]);
const CLOCK_SKEW_SECONDS = 300;

class GoogleTokenError extends Error {}

const googleClientId = () => (process.env.GOOGLE_CLIENT_ID || "").trim();
const isGoogleConfigured = () => Boolean(googleClientId());

// kid -> KeyObject, refreshed when Google's Cache-Control max-age runs out or an unknown kid appears
let certs = { keys: new Map(), expiresAt: 0 };

const loadCerts = async () => {
    const res = await axios.get(CERTS_URL, { timeout: 5000 });
    const maxAge = Number(/max-age=(\d+)/.exec(res.headers["cache-control"] || "")?.[1] || 3600);
    const keys = new Map();
    for (const jwk of res.data.keys || []) {
        keys.set(jwk.kid, crypto.createPublicKey({ key: jwk, format: "jwk" }));
    }
    certs = { keys, expiresAt: Date.now() + maxAge * 1000 };
    return keys;
};

const keyFor = async (kid) => {
    if (Date.now() < certs.expiresAt && certs.keys.has(kid)) return certs.keys.get(kid);
    const keys = await loadCerts();
    return keys.get(kid) || null;
};

const decodePart = (part) => {
    try {
        return JSON.parse(Buffer.from(part, "base64url").toString("utf8"));
    } catch {
        return null;
    }
};

// -> { sub, email, name, picture } of a Google account with a verified email, else throws
const verifyGoogleIdToken = async (credential) => {
    const clientId = googleClientId();
    if (!clientId) throw new GoogleTokenError("Google sign-in isn't configured");
    if (typeof credential !== "string" || credential.length > 4096) throw new GoogleTokenError("Missing Google credential");

    const parts = credential.split(".");
    if (parts.length !== 3) throw new GoogleTokenError("Malformed Google credential");
    const header = decodePart(parts[0]);
    const payload = decodePart(parts[1]);
    if (!header || !payload || header.alg !== "RS256" || !header.kid) throw new GoogleTokenError("Malformed Google credential");

    const key = await keyFor(header.kid);
    if (!key) throw new GoogleTokenError("Unknown Google signing key");
    const signed = crypto.verify("RSA-SHA256", Buffer.from(`${parts[0]}.${parts[1]}`), key, Buffer.from(parts[2], "base64url"));
    if (!signed) throw new GoogleTokenError("Google credential signature is invalid");

    const now = Math.floor(Date.now() / 1000);
    if (!ISSUERS.has(payload.iss)) throw new GoogleTokenError("Wrong issuer");
    if (payload.aud !== clientId) throw new GoogleTokenError("Credential is for another app");
    if (!Number.isFinite(payload.exp) || payload.exp < now - CLOCK_SKEW_SECONDS) throw new GoogleTokenError("Google credential has expired");
    if (Number.isFinite(payload.iat) && payload.iat > now + CLOCK_SKEW_SECONDS) throw new GoogleTokenError("Credential issued in the future");
    const emailVerified = payload.email_verified === true || payload.email_verified === "true";
    if (!payload.sub || !payload.email || !emailVerified) throw new GoogleTokenError("Google account email isn't verified");

    return {
        sub: String(payload.sub),
        email: String(payload.email).trim().toLowerCase(),
        name: typeof payload.name === "string" ? payload.name : "",
        picture: typeof payload.picture === "string" ? payload.picture : "",
    };
};

module.exports = { verifyGoogleIdToken, isGoogleConfigured, googleClientId, GoogleTokenError };
