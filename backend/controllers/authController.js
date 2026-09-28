const db = require("../config/db");
const {
    isAuthConfigured,
    hashPassword,
    verifyPassword,
    signJwt,
} = require("../services/cryptoService");
const {
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
} = require("../services/authService");
const { deleteAllForUser } = require("../services/portfolioService");
const { verifyGoogleIdToken, isGoogleConfigured, googleClientId, GoogleTokenError } = require("../services/googleAuth");

const fail = (res, status, message, code) => res.status(status).json({ success: false, message, ...(code ? { code } : {}) });

const serverError = (res, error, what) => {
    console.error(`${what} failed:`, error.message);
    return fail(res, 500, "Something went wrong. Try again.");
};

const EMAIL_TAKEN = "An account with this email already exists";
// Same text whether the account is missing, the password is wrong or the account only uses Google
const BAD_LOGIN = "Invalid email or password. If you signed up with Google, use Continue with Google.";

const clientIp = (req) => req.ip || req.socket?.remoteAddress || "unknown";

// Answers 429 (and returns true) when this IP+account is over the failure limit
const rateLimited = (req, res, account) => {
    const wait = retryAfter(clientIp(req), account);
    if (!wait) return false;
    res.set("Retry-After", String(wait));
    fail(res, 429, `Too many attempts. Try again in ${Math.ceil(wait / 60)} minute(s).`, "RATE_LIMITED");
    return true;
};

// Fail closed when the signing secret is missing (register/login would mint unusable tokens)
const ensureConfigured = (res) => {
    if (isAuthConfigured()) return true;
    fail(res, 503, "Accounts aren't configured on this server yet", "NOT_CONFIGURED");
    return false;
};

const session = (user) => ({ success: true, token: signJwt({ sub: user.id, email: user.email }), user });

// POST /auth/register { username, email, password }
const register = async (req, res) => {
    if (!ensureConfigured(res)) return;
    const username = normaliseUsername(req.body?.username);
    const email = normaliseEmail(req.body?.email);
    const password = req.body?.password;

    const invalid = usernameError(username) || emailError(email) || passwordError(password);
    if (invalid) return fail(res, 400, invalid, "VALIDATION");

    try {
        await ensureUsersTable();
        const passwordHash = await hashPassword(password);
        const [result] = await db.query(
            "INSERT INTO users (email, username, password_hash, last_login_at) VALUES (?, ?, ?, ?)",
            [email, username, passwordHash, new Date()]
        );
        const user = await findUserById(result.insertId);
        res.status(201).json(session(user));
    } catch (error) {
        if (isDuplicateKey(error)) return fail(res, 409, EMAIL_TAKEN, "EMAIL_TAKEN");
        serverError(res, error, "Register");
    }
};

// POST /auth/login { email, password }
const login = async (req, res) => {
    if (!ensureConfigured(res)) return;
    const email = normaliseEmail(req.body?.email);
    const password = typeof req.body?.password === "string" ? req.body.password : "";
    if (!email || !password || password.length > 200) return fail(res, 401, BAD_LOGIN);
    if (rateLimited(req, res, email)) return;

    try {
        const row = await findUserWithHash({ email });
        // verifyPassword runs scrypt even when the account doesn't exist (equal timing)
        const ok = await verifyPassword(password, row?.password_hash);
        if (!row || !ok) {
            recordFailure(clientIp(req), email);
            return fail(res, 401, BAD_LOGIN);
        }

        clearFailures(clientIp(req), email);
        await db.query("UPDATE users SET last_login_at = ? WHERE id = ?", [new Date(), row.id]);
        res.json(session(toPublicUser(row)));
    } catch (error) {
        serverError(res, error, "Login");
    }
};

// GET /auth/config -> public sign-in options for the frontend (the Google client id isn't secret)
const config = (req, res) => res.json({
    success: true,
    google_client_id: isAuthConfigured() && isGoogleConfigured() ? googleClientId() : null,
});

// Google display name -> username (the same rules as a typed one)
const usernameFromGoogle = (profile) => {
    const name = normaliseUsername(profile.name) || profile.email.split("@")[0];
    return name.slice(0, 80) || "investor";
};

// POST /auth/google { credential } (a Google Identity Services ID token)
// Signs in the account linked to this Google id; else links Google to the account with the same
// (Google-verified) email; else creates a new password-less account.
const google = async (req, res) => {
    if (!ensureConfigured(res)) return;
    if (!isGoogleConfigured()) return fail(res, 503, "Google sign-in isn't set up yet", "GOOGLE_NOT_CONFIGURED");

    let profile;
    try {
        profile = await verifyGoogleIdToken(req.body?.credential);
    } catch (error) {
        if (error instanceof GoogleTokenError) return fail(res, 401, "Google sign-in failed. Try again.", "GOOGLE_INVALID");
        return serverError(res, error, "Google token check");
    }

    try {
        let row = await findUserByGoogleSub(profile.sub);
        if (!row) {
            const existing = await findUserWithHash({ email: profile.email });
            if (existing && existing.google_sub && existing.google_sub !== profile.sub) {
                return fail(res, 409, "This email is linked to a different Google account", "GOOGLE_MISMATCH");
            }
            if (existing) {
                await db.query("UPDATE users SET google_sub = ? WHERE id = ?", [profile.sub, existing.id]);
                row = existing;
            } else {
                try {
                    const [result] = await db.query(
                        "INSERT INTO users (email, username, password_hash, google_sub, last_login_at) VALUES (?, ?, NULL, ?, ?)",
                        [profile.email, usernameFromGoogle(profile), profile.sub, new Date()]
                    );
                    return res.status(201).json(session(await findUserById(result.insertId)));
                } catch (error) {
                    // Two sign-ins at once: the other request created the account first
                    if (!isDuplicateKey(error)) throw error;
                    row = await findUserByGoogleSub(profile.sub);
                    if (!row) return fail(res, 409, EMAIL_TAKEN, "EMAIL_TAKEN");
                }
            }
        }
        await db.query("UPDATE users SET last_login_at = ? WHERE id = ?", [new Date(), row.id]);
        res.json(session(await findUserById(row.id)));
    } catch (error) {
        serverError(res, error, "Google sign-in");
    }
};

// GET /auth/me
const me = (req, res) => res.json({ success: true, user: req.user });

// PATCH /auth/me { username?, email? }
const updateMe = async (req, res) => {
    const updates = {};
    if (req.body?.username !== undefined) {
        const username = normaliseUsername(req.body.username);
        const invalid = usernameError(username);
        if (invalid) return fail(res, 400, invalid, "VALIDATION");
        updates.username = username;
    }
    if (req.body?.email !== undefined) {
        const email = normaliseEmail(req.body.email);
        const invalid = emailError(email);
        if (invalid) return fail(res, 400, invalid, "VALIDATION");
        updates.email = email;
    }
    if (!Object.keys(updates).length) return fail(res, 400, "Nothing to update", "VALIDATION");

    try {
        const columns = Object.keys(updates);
        await db.query(
            `UPDATE users SET ${columns.map((column) => `${column} = ?`).join(", ")} WHERE id = ?`,
            [...columns.map((column) => updates[column]), req.user.id]
        );
        res.json({ success: true, user: await findUserById(req.user.id) });
    } catch (error) {
        if (isDuplicateKey(error)) return fail(res, 409, EMAIL_TAKEN, "EMAIL_TAKEN");
        serverError(res, error, "Profile update");
    }
};

// Checks the signed-in user's password, with the same brute-force limit as login
const checkOwnPassword = async (req, res, password) => {
    const account = `user:${req.user.id}`;
    if (rateLimited(req, res, account)) return false;

    const row = await findUserWithHash({ id: req.user.id });
    if (typeof password !== "string" || password.length > 200 || !(await verifyPassword(password, row?.password_hash))) {
        recordFailure(clientIp(req), account);
        fail(res, 401, "Current password is incorrect", "WRONG_PASSWORD");
        return false;
    }
    clearFailures(clientIp(req), account);
    return true;
};

// POST /auth/password { current_password, new_password }
// Google-only accounts (no password yet) set their first password without current_password.
const changePassword = async (req, res) => {
    const invalid = passwordError(req.body?.new_password, "New password");
    if (invalid) return fail(res, 400, invalid, "VALIDATION");

    try {
        const row = await findUserWithHash({ id: req.user.id });
        if (row?.password_hash && !(await checkOwnPassword(req, res, req.body?.current_password))) return;
        await db.query("UPDATE users SET password_hash = ? WHERE id = ?", [await hashPassword(req.body.new_password), req.user.id]);
        res.json({ success: true });
    } catch (error) {
        serverError(res, error, "Password change");
    }
};

// DELETE /auth/me { password } -> disconnects brokers, deletes snapshots and the account
// Accounts without a password (Google-only) confirm by typing their email: { confirm_email }
const deleteMe = async (req, res) => {
    try {
        const row = await findUserWithHash({ id: req.user.id });
        if (row?.password_hash) {
            if (!(await checkOwnPassword(req, res, req.body?.password))) return;
        } else if (normaliseEmail(req.body?.confirm_email) !== row?.email) {
            return fail(res, 400, "Type your account email to confirm", "CONFIRM_EMAIL");
        }
        await deleteAllForUser(req.user.id);
        await db.query("DELETE FROM users WHERE id = ?", [req.user.id]);
        res.json({ success: true });
    } catch (error) {
        serverError(res, error, "Account deletion");
    }
};

module.exports = { register, login, google, config, me, updateMe, changePassword, deleteMe };
