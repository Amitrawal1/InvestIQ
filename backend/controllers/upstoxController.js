const {
    saveAccessToken,
    isAdminKey,
    buildLoginUrl,
    isValidState,
    exchangeCode,
} = require("../services/upstoxAuthService");

const page = (title, message) => `<!doctype html>
<html><head><meta charset="utf-8"><title>${title}</title>
<style>body{background:#050011;color:#fff;font-family:ui-monospace,monospace;display:grid;place-items:center;min-height:100vh;margin:0;padding:16px}
div{max-width:480px;text-align:center}h1{font-weight:400;letter-spacing:.1em;text-transform:uppercase;font-size:18px}p{color:#9ca3af;font-size:13px;line-height:1.6}</style>
</head><body><div><h1>${title}</h1><p>${message}</p></div></body></html>`;

// Daily login: open /upstox/login?key=<UPSTOX_ADMIN_KEY>, sign in to Upstox, done
const login = (req, res) => {
    if (!isAdminKey(req.query.key)) {
        return res.status(403).send(page("Not allowed", "Missing or wrong admin key."));
    }
    res.redirect(buildLoginUrl());
};

const callback = async (req, res) => {
    const { code, state, error } = req.query;

    if (error) return res.status(400).send(page("Upstox login cancelled", String(error)));
    if (!code || !isValidState(state)) {
        return res.status(400).send(page("Invalid login", "This login link expired or wasn't started from /upstox/login. Start again."));
    }

    try {
        const token = await exchangeCode(code);
        await saveAccessToken(token);
        res.send(page("Upstox connected", "Live market data is on until Upstox expires the token (around 3:30 AM IST). You can close this tab."));
    } catch (err) {
        console.log("Upstox token exchange failed:", err.response?.data || err.message);
        res.status(502).send(page("Upstox login failed", "Upstox rejected the code. Start again from /upstox/login."));
    }
};

module.exports = { login, callback };
