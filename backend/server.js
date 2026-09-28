const express = require("express");
const cors = require("cors");
require("dotenv").config();

const app = express();
const db = require("./config/db");
const sectorRoutes = require("./routes/sectorRoutes");
const companyRoutes = require("./routes/companyRoutes");
const stockPriceRoutes = require("./routes/stockPriceRoutes");
const newsRoutes = require("./routes/newsRoutes");
const marketRoutes = require("./routes/marketRoutes");
const upstoxRoutes = require("./routes/upstoxRoutes");
const rankingRoutes = require("./routes/rankingRoutes");
const authRoutes = require("./routes/authRoutes");
const brokerRoutes = require("./routes/brokerRoutes");
const portfolioRoutes = require("./routes/portfolioRoutes");

db.query("SELECT 1")
    .then(() => {
        console.log("MySQL connected");
    })
    .catch((error) => {
        console.log("MySQL connection failed:", error.message);
    });

// Vercel (and local dev tools) sit one proxy hop in front: use X-Forwarded-For for req.ip
app.set("trust proxy", 1);
app.use(cors());
// strict: false accepts a bare `null` body (older frontends sent one on POST /brokers/:b/connect);
// anything that isn't an object becomes {} so handlers can always read req.body.x
app.use(express.json({ strict: false }));
app.use((req, res, next) => {
    if (req.body === null || typeof req.body !== "object") req.body = {};
    next();
});
app.use("/sectors", sectorRoutes);
app.use("/companies", companyRoutes);
app.use("/stock-prices", stockPriceRoutes);
app.use("/news", newsRoutes);
app.use("/market", marketRoutes);
app.use("/upstox", upstoxRoutes);
app.use("/rankings", rankingRoutes);
app.use("/auth", authRoutes);
app.use("/brokers", brokerRoutes);
app.use("/portfolio", portfolioRoutes);


app.get("/", (req, res) => {
    res.json({
        message: "InvestIQ Backend is running"
    });
});

// Last-resort JSON error handler (bad JSON bodies, unexpected throws): no stack traces to clients
app.use((err, req, res, next) => {
    const status = Number(err.status || err.statusCode) || 500;
    if (status >= 500) console.error("Unhandled error:", err.message);
    res.status(status).json({
        success: false,
        message: status < 500 && err.expose ? err.message : status < 500 ? "Bad request" : "Something went wrong. Try again.",
    });
});

// On Vercel the exported app is served directly (Express is auto-detected);
// locally (`npm run dev` / `npm start`) it listens on a port as usual
if (require.main === module) {
    const PORT = process.env.PORT || 5500;

    app.listen(PORT, () => {
        console.log(`Server running on port ${PORT}`);
    });
}

module.exports = app;