// Small standalone HTML page for browser-facing backend routes (broker/Upstox callbacks), styled
// like the InvestIQ frontend, so a person never lands on raw JSON or plain text.

const escapeHtml = (value) =>
    String(value ?? "").replace(/[&<>"']/g, (ch) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[ch]);

const TONES = { success: "#22c55e", error: "#f87171", info: "#a78bfa" };

// action: { href, label } | null; autoRedirect: seconds before following action.href
const resultPage = ({ title, message, tone = "info", action = null, autoRedirect = 0 }) => {
    const color = TONES[tone] || TONES.info;
    const href = action?.href ? escapeHtml(action.href) : "";
    const button = action
        ? href
            ? `<a class="btn" href="${href}">${escapeHtml(action.label)}</a>`
            : `<button class="btn" onclick="history.length > 1 ? history.back() : window.close()">${escapeHtml(action.label)}</button>`
        : "";
    const refresh = href && autoRedirect > 0 ? `<meta http-equiv="refresh" content="${autoRedirect};url=${href}">` : "";
    const note = href && autoRedirect > 0 ? `<p class="note">Taking you back in ${autoRedirect} seconds…</p>` : "";
    return `<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>${escapeHtml(title)} · InvestIQ</title>${refresh}
<style>
*{box-sizing:border-box}
body{margin:0;min-height:100vh;display:grid;place-items:center;padding:16px;background:#050011;color:#fff;
font-family:ui-sans-serif,system-ui,-apple-system,"Segoe UI",sans-serif}
.card{width:100%;max-width:440px;border:1px solid #1f2937;border-radius:16px;background:#0b0618;padding:36px 28px;text-align:center}
.brand{font:500 11px ui-monospace,monospace;letter-spacing:.3em;text-transform:uppercase;color:#6b7280;margin-bottom:28px}
.dot{width:44px;height:44px;border-radius:50%;margin:0 auto 20px;display:grid;place-items:center;
background:${color}1f;border:1px solid ${color}66;color:${color};font-size:20px}
h1{font-weight:500;font-size:20px;margin:0 0 10px}
p{color:#9ca3af;font-size:14px;line-height:1.6;margin:0}
.btn{display:inline-block;margin-top:28px;padding:11px 22px;border-radius:999px;border:1px solid #fff;background:#fff;color:#050011;
font:600 12px ui-monospace,monospace;letter-spacing:.15em;text-transform:uppercase;text-decoration:none;cursor:pointer}
.btn:hover{background:transparent;color:#fff}
.note{margin-top:14px;font-size:12px;color:#6b7280}
</style></head>
<body><main class="card">
<div class="brand">InvestIQ</div>
<div class="dot">${tone === "success" ? "&#10003;" : tone === "error" ? "!" : "i"}</div>
<h1>${escapeHtml(title)}</h1>
<p>${escapeHtml(message)}</p>
${button}${note}
</main></body></html>`;
};

module.exports = { resultPage, escapeHtml };
