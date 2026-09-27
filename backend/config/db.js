const mysql = require("mysql2/promise");
require("dotenv").config();

// Cloud MySQL (TiDB Cloud) needs TLS: set DB_SSL=true. Local MySQL leaves it unset.
const db = mysql.createPool({
    host: process.env.DB_HOST,
    port: Number(process.env.DB_PORT) || 3306,
    user: process.env.DB_USER,
    password: process.env.DB_PASSWORD,
    database: process.env.DB_NAME,
    ssl: process.env.DB_SSL === "true" ? { minVersion: "TLSv1.2", rejectUnauthorized: true } : undefined,
    connectionLimit: 10,
    enableKeepAlive: true,
    // Stored DATETIMEs are IST wall-clock times. Pin both sides to IST so results don't
    // depend on the host (Vercel runs in UTC) or the server default (TiDB Cloud is UTC).
    timezone: "+05:30",
});

db.pool.on("connection", (connection) => {
    connection.query("SET time_zone = '+05:30'");
});

module.exports = db;
