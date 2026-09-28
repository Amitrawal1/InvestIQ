// Broker connections, portfolio snapshots and the merged /portfolio view
const db = require("../config/db");
const { encryptToken, decryptToken, isTokenKeyConfigured, isAuthConfigured } = require("./cryptoService");
const { BROKER_NAMES, getBroker } = require("./brokers");
const { num, round, pct, holdingTotals, TokenExpiredError } = require("./brokers/common");
const { toNum, parseJson } = require("./rankingService");

const CONNECTIONS_SQL = `
CREATE TABLE IF NOT EXISTS broker_connections (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    user_id BIGINT NOT NULL,
    broker ENUM('upstox','zerodha') NOT NULL,
    broker_user_id VARCHAR(50) NULL,
    broker_user_name VARCHAR(120) NULL,
    access_token_enc TEXT NULL,
    token_expires_at DATETIME NULL,
    connected_at DATETIME NOT NULL,
    last_synced_at DATETIME NULL,
    last_error VARCHAR(500) NULL,
    UNIQUE KEY uq_user_broker (user_id, broker)
)`;

const SNAPSHOTS_SQL = `
CREATE TABLE IF NOT EXISTS portfolio_snapshots (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    user_id BIGINT NOT NULL,
    broker ENUM('upstox','zerodha') NOT NULL,
    synced_at DATETIME NOT NULL,
    holdings JSON NOT NULL,
    positions JSON NOT NULL,
    funds JSON NULL,
    totals JSON NOT NULL,
    KEY idx_user_time (user_id, synced_at)
)`;

let tablesReady = null;
const ensureTables = () => {
    if (!tablesReady) {
        tablesReady = (async () => {
            await db.query(CONNECTIONS_SQL);
            await db.query(SNAPSHOTS_SQL);
        })();
        tablesReady.catch(() => { tablesReady = null; });
    }
    return tablesReady;
};

// Error with an HTTP status and optional machine-readable code, for controllers to relay
class ServiceError extends Error {
    constructor(status, message, code) {
        super(message);
        this.status = status;
        this.code = code;
    }
}

const frontendUrl = () => (process.env.FRONTEND_URL || "").trim().replace(/\/+$/, "");

// A broker can be linked only when its app credentials and our own secrets are all present
const isBrokerConfigured = (broker) => Boolean(
    broker.isConfigured() && isTokenKeyConfigured() && isAuthConfigured() && frontendUrl()
);

// AAD binding each encrypted token to its owner and broker
const tokenAad = (userId, broker) => `${userId}:${broker}`;

const clip = (text, max = 500) => (text ? String(text).slice(0, max) : null);

// ---------------------------------------------------------------------------------------------
// Connections
// ---------------------------------------------------------------------------------------------

const getConnectionRow = async (userId, broker) => {
    await ensureTables();
    const [rows] = await db.query("SELECT * FROM broker_connections WHERE user_id = ? AND broker = ?", [userId, broker]);
    return rows[0] || null;
};

const isTokenValid = (row) => Boolean(
    row?.access_token_enc && row.token_expires_at && new Date(row.token_expires_at).getTime() > Date.now()
);

// Public connection status for both brokers (never includes the token)
const listConnections = async (userId) => {
    await ensureTables();
    const [rows] = await db.query("SELECT * FROM broker_connections WHERE user_id = ?", [userId]);
    return BROKER_NAMES.map((name) => {
        const row = rows.find((r) => r.broker === name);
        const valid = isTokenValid(row);
        return {
            broker: name,
            connected: Boolean(row),
            broker_user_name: row?.broker_user_name ?? null,
            broker_user_id: row?.broker_user_id ?? null,
            token_valid: valid,
            token_expires_at: valid ? row.token_expires_at : null,
            connected_at: row?.connected_at ?? null,
            last_synced_at: row?.last_synced_at ?? null,
            last_error: row?.last_error ?? null,
            configured: isBrokerConfigured(getBroker(name)),
        };
    });
};

const saveConnection = async (userId, broker, { access_token, broker_user_id, broker_user_name }) => {
    await ensureTables();
    const expiresAt = broker.tokenExpiresAt(new Date());
    await db.query(
        `INSERT INTO broker_connections
            (user_id, broker, broker_user_id, broker_user_name, access_token_enc, token_expires_at, connected_at, last_error)
         VALUES (?, ?, ?, ?, ?, ?, ?, NULL)
         ON DUPLICATE KEY UPDATE broker_user_id = VALUES(broker_user_id), broker_user_name = VALUES(broker_user_name),
             access_token_enc = VALUES(access_token_enc), token_expires_at = VALUES(token_expires_at),
             connected_at = VALUES(connected_at), last_error = NULL`,
        [
            userId, broker.name, clip(broker_user_id, 50), clip(broker_user_name, 120),
            encryptToken(access_token, tokenAad(userId, broker.name)), expiresAt, new Date(),
        ]
    );
};

const clearToken = async (userId, brokerName, message) => {
    await db.query(
        "UPDATE broker_connections SET access_token_enc = NULL, token_expires_at = NULL, last_error = ? WHERE user_id = ? AND broker = ?",
        [clip(message), userId, brokerName]
    );
};

// Plain token for server-side use, or null (expired tokens are cleared on the way)
const usableToken = async (userId, row) => {
    if (!row?.access_token_enc) return null;
    if (!isTokenValid(row)) {
        await clearToken(userId, row.broker, "Session expired. Reconnect to sync.");
        return null;
    }
    const token = decryptToken(row.access_token_enc, tokenAad(userId, row.broker));
    if (!token) await clearToken(userId, row.broker, "Stored session couldn't be read. Reconnect to sync.");
    return token;
};

// ---------------------------------------------------------------------------------------------
// Sync
// ---------------------------------------------------------------------------------------------

const syncBroker = async (userId, brokerName) => {
    const broker = getBroker(brokerName);
    if (!broker) throw new ServiceError(404, "Unknown broker");
    if (!isTokenKeyConfigured() || !broker.isConfigured()) {
        throw new ServiceError(503, `${broker.label} linking isn't configured yet`, "NOT_CONFIGURED");
    }

    const row = await getConnectionRow(userId, broker.name);
    if (!row) throw new ServiceError(404, `${broker.label} isn't linked`, "NOT_CONNECTED");

    const token = await usableToken(userId, row);
    if (!token) throw new ServiceError(409, `Your ${broker.label} session has expired. Reconnect to sync.`, "TOKEN_EXPIRED");

    let data;
    try {
        data = await broker.fetchPortfolio(token);
    } catch (error) {
        if (error instanceof TokenExpiredError) {
            await clearToken(userId, broker.name, "Session expired. Reconnect to sync.");
            throw new ServiceError(409, `Your ${broker.label} session has expired. Reconnect to sync.`, "TOKEN_EXPIRED");
        }
        // Log status only: broker error bodies can echo request details
        console.log(`${broker.label} sync failed:`, error.response?.status || error.message);
        await db.query(
            "UPDATE broker_connections SET last_error = ? WHERE user_id = ? AND broker = ?",
            [`Couldn't reach ${broker.label}. Try again in a minute.`, userId, broker.name]
        );
        throw new ServiceError(502, `Couldn't fetch your ${broker.label} portfolio. Try again in a minute.`, "BROKER_ERROR");
    }

    const syncedAt = new Date();
    const totals = holdingTotals(data.holdings);
    await db.query(
        `INSERT INTO portfolio_snapshots (user_id, broker, synced_at, holdings, positions, funds, totals)
         VALUES (?, ?, ?, ?, ?, ?, ?)`,
        [
            userId, broker.name, syncedAt, JSON.stringify(data.holdings), JSON.stringify(data.positions),
            data.funds ? JSON.stringify(data.funds) : null, JSON.stringify(totals),
        ]
    );
    await db.query(
        "UPDATE broker_connections SET last_synced_at = ?, last_error = NULL WHERE user_id = ? AND broker = ?",
        [syncedAt, userId, broker.name]
    );
    return { synced_at: syncedAt, totals };
};

// Callback step shared by both brokers: exchange the one-time code, save the encrypted token,
// fill in the profile if the token response lacked it, then run a first sync (failure there
// doesn't undo the link; it's recorded in last_error)
const completeLink = async (userId, broker, params) => {
    const session = await broker.exchange(params);
    if (!session.broker_user_id || !session.broker_user_name) {
        try {
            const profile = await broker.fetchProfile(session.access_token);
            session.broker_user_id = session.broker_user_id || profile.broker_user_id;
            session.broker_user_name = session.broker_user_name || profile.broker_user_name;
        } catch {
            // Profile is cosmetic; ignore
        }
    }
    await saveConnection(userId, broker, session);
    try {
        await syncBroker(userId, broker.name);
    } catch (error) {
        console.log(`${broker.label} first sync failed:`, error.message);
    }
};

// ---------------------------------------------------------------------------------------------
// Disconnect / delete
// ---------------------------------------------------------------------------------------------

const disconnect = async (userId, brokerName, deleteData = false) => {
    const broker = getBroker(brokerName);
    if (!broker) throw new ServiceError(404, "Unknown broker");

    const row = await getConnectionRow(userId, broker.name);
    if (row?.access_token_enc && isTokenValid(row) && isTokenKeyConfigured() && broker.isConfigured()) {
        const token = decryptToken(row.access_token_enc, tokenAad(userId, broker.name));
        if (token) {
            try {
                await broker.logout(token);
            } catch (error) {
                console.log(`${broker.label} logout failed:`, error.response?.status || error.message);
            }
        }
    }

    await db.query("DELETE FROM broker_connections WHERE user_id = ? AND broker = ?", [userId, broker.name]);
    let deletedSnapshots = 0;
    if (deleteData) {
        const [result] = await db.query("DELETE FROM portfolio_snapshots WHERE user_id = ? AND broker = ?", [userId, broker.name]);
        deletedSnapshots = result.affectedRows;
    }
    return { disconnected: Boolean(row), deleted_snapshots: deletedSnapshots };
};

// Account deletion: log out of every broker, then remove connections and snapshots
const deleteAllForUser = async (userId) => {
    await ensureTables();
    for (const name of BROKER_NAMES) {
        await disconnect(userId, name, true);
    }
};

// ---------------------------------------------------------------------------------------------
// GET /portfolio
// ---------------------------------------------------------------------------------------------

// Company + latest ranking for each holding, matched by ISIN first, then by symbol
const loadCompanyInfo = async (holdings) => {
    const isins = [...new Set(holdings.map((h) => h.isin).filter(Boolean))];
    const symbols = [...new Set(holdings.map((h) => h.symbol).filter(Boolean))];
    if (!isins.length && !symbols.length) return { byIsin: new Map(), bySymbol: new Map() };

    const conditions = [];
    const params = [];
    if (isins.length) { conditions.push("c.isin IN (?)"); params.push(isins); }
    if (symbols.length) { conditions.push("c.symbol IN (?)"); params.push(symbols); }

    const [rows] = await db.query(
        `SELECT c.id AS company_id, c.symbol AS company_symbol, c.isin, c.name, s.name AS sector, s.slug AS sector_slug,
                COALESCE(i.name, c.industry) AS industry,
                r.growth_score, r.growth_label, r.rank_overall, r.risks
         FROM companies c
         LEFT JOIN sectors s ON s.id = c.sector_id
         LEFT JOIN industries i ON i.id = c.industry_id
         LEFT JOIN company_rankings r
             ON r.company_id = c.id AND r.snapshot_date = (SELECT MAX(snapshot_date) FROM company_rankings)
         WHERE ${conditions.join(" OR ")}`,
        params
    );

    const byIsin = new Map();
    const bySymbol = new Map();
    for (const row of rows) {
        if (row.isin) byIsin.set(String(row.isin).toUpperCase(), row);
        bySymbol.set(String(row.company_symbol).toUpperCase(), row);
    }
    return { byIsin, bySymbol };
};

const enrichHolding = (holding, broker, info) => {
    const company = (holding.isin && info.byIsin.get(holding.isin)) || (holding.symbol && info.bySymbol.get(holding.symbol)) || null;
    const risks = parseJson(company?.risks, null);
    return {
        ...holding,
        broker,
        company_id: company ? Number(company.company_id) : null,
        name: company?.name ?? holding.company_name ?? holding.symbol,
        sector: company?.sector ?? null,
        sector_slug: company?.sector_slug ?? null,
        industry: company?.industry ?? null,
        growth_score: toNum(company?.growth_score),
        growth_label: company?.growth_label ?? null,
        rank_overall: company?.rank_overall ?? null,
        // Internal: used for insights.flagged, removed from the response
        _risks: Array.isArray(risks) ? risks.filter(Boolean) : [],
    };
};

const buildInsights = (holdings) => {
    const rated = holdings.filter((h) => h.growth_score !== null);
    const ratedWeight = rated.reduce((acc, h) => acc + (h.current_value ?? 0), 0);
    const weightedScore = ratedWeight > 0
        ? round(rated.reduce((acc, h) => acc + h.growth_score * (h.current_value ?? 0), 0) / ratedWeight)
        : null;

    const totalValue = holdings.reduce((acc, h) => acc + (h.current_value ?? 0), 0);
    const bySector = new Map();
    for (const h of holdings) {
        const sector = h.sector || "Unclassified";
        bySector.set(sector, (bySector.get(sector) || 0) + (h.current_value ?? 0));
    }
    const allocation = [...bySector.entries()]
        .map(([sector, value]) => ({ sector, value: round(value), pct: pct(value, totalValue) ?? 0 }))
        .sort((a, b) => b.value - a.value);

    return {
        weighted_score: weightedScore,
        strong_count: holdings.filter((h) => h.growth_label === "Strong").length,
        weak_count: holdings.filter((h) => h.growth_label === "Weak").length,
        unrated_count: holdings.length - rated.length,
        top_sector: allocation[0]?.sector ?? null,
        top_sector_pct: allocation[0]?.pct ?? null,
        sector_allocation: allocation,
        flagged: holdings
            .filter((h) => h._risks.length)
            .map((h) => ({ symbol: h.symbol, name: h.name, broker: h.broker, risks: h._risks })),
    };
};

// One point per day for the last 180 days: each broker's latest snapshot that day, carried
// forward on days a broker wasn't synced, summed across brokers
const buildHistory = async (userId) => {
    const [rows] = await db.query(
        `SELECT broker, day, totals FROM (
             SELECT broker, DATE_FORMAT(synced_at, '%Y-%m-%d') AS day, totals,
                    ROW_NUMBER() OVER (PARTITION BY broker, DATE(synced_at) ORDER BY synced_at DESC, id DESC) AS rn
             FROM portfolio_snapshots
             WHERE user_id = ? AND synced_at >= DATE_SUB(CURDATE(), INTERVAL 179 DAY)
         ) latest
         WHERE rn = 1
         ORDER BY day`,
        [userId]
    );

    const days = [...new Set(rows.map((r) => r.day))].sort();
    const lastByBroker = new Map();
    return days.map((day) => {
        for (const row of rows.filter((r) => r.day === day)) lastByBroker.set(row.broker, parseJson(row.totals, {}));
        let current = 0;
        let invested = 0;
        for (const totals of lastByBroker.values()) {
            current += num(totals?.current) ?? 0;
            invested += num(totals?.invested) ?? 0;
        }
        return { date: day, current: round(current), invested: round(invested) };
    });
};

const getPortfolio = async (userId) => {
    await ensureTables();
    const connections = await listConnections(userId);

    const [snapshots] = await db.query(
        `SELECT broker, synced_at, holdings, positions, funds FROM (
             SELECT broker, synced_at, holdings, positions, funds,
                    ROW_NUMBER() OVER (PARTITION BY broker ORDER BY synced_at DESC, id DESC) AS rn
             FROM portfolio_snapshots WHERE user_id = ?
         ) latest
         WHERE rn = 1`,
        [userId]
    );

    const rawHoldings = [];
    const positions = [];
    const funds = Object.fromEntries(BROKER_NAMES.map((name) => [name, null]));
    let lastSyncedAt = null;

    for (const snap of snapshots) {
        for (const h of parseJson(snap.holdings, []) || []) rawHoldings.push({ holding: h, broker: snap.broker });
        for (const p of parseJson(snap.positions, []) || []) positions.push({ ...p, broker: snap.broker });
        funds[snap.broker] = parseJson(snap.funds, null);
        if (!lastSyncedAt || new Date(snap.synced_at) > new Date(lastSyncedAt)) lastSyncedAt = snap.synced_at;
    }

    const info = await loadCompanyInfo(rawHoldings.map((r) => r.holding));
    const enriched = rawHoldings
        .map(({ holding, broker }) => enrichHolding(holding, broker, info))
        .sort((a, b) => (b.current_value ?? 0) - (a.current_value ?? 0));

    const totals = holdingTotals(enriched);
    const previousValue = totals.current - totals.day_change;
    const insights = buildInsights(enriched);
    const history = await buildHistory(userId);

    return {
        connections,
        summary: {
            invested: totals.invested,
            current: totals.current,
            pnl: totals.pnl,
            pnl_pct: pct(totals.pnl, totals.invested),
            day_change: totals.day_change,
            day_change_pct: pct(totals.day_change, previousValue),
            holdings_count: enriched.length,
            last_synced_at: lastSyncedAt,
        },
        holdings: enriched.map(({ _risks, ...holding }) => holding),
        positions,
        funds,
        insights,
        history,
    };
};

module.exports = {
    ServiceError,
    ensureTables,
    frontendUrl,
    isBrokerConfigured,
    listConnections,
    completeLink,
    syncBroker,
    disconnect,
    deleteAllForUser,
    getPortfolio,
};
