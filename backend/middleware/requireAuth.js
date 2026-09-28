// Requires `Authorization: Bearer <JWT>`; sets req.user = { id, username, email, created_at }.
// Fails closed: 503 if AUTH_JWT_SECRET isn't configured, 401 for anything else that's wrong
// (missing / malformed / tampered / expired token, or the account no longer exists).
const { isAuthConfigured, verifyJwt } = require("../services/cryptoService");
const { findUserById } = require("../services/authService");

const unauthorized = (res) => res.status(401).json({
    success: false,
    message: "Please sign in again",
    code: "UNAUTHORIZED",
});

const requireAuth = async (req, res, next) => {
    if (!isAuthConfigured()) {
        return res.status(503).json({ success: false, message: "Accounts aren't configured on this server yet", code: "NOT_CONFIGURED" });
    }

    const match = /^Bearer\s+(\S+)$/i.exec(req.headers.authorization || "");
    const claims = match ? verifyJwt(match[1]) : null;
    if (!claims) return unauthorized(res);

    try {
        const user = await findUserById(claims.sub);
        if (!user) return unauthorized(res);
        req.user = user;
        next();
    } catch (error) {
        console.error("Auth lookup failed:", error.message);
        res.status(500).json({ success: false, message: "Something went wrong. Try again." });
    }
};

module.exports = requireAuth;
