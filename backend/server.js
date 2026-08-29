const express = require("express");
const cors = require("cors");
require("dotenv").config();

const app = express();
const db = require("./config/db");
const sectorRoutes = require("./routes/sectorRoutes");
const companyRoutes = require("./routes/companyRoutes");
const stockPriceRoutes = require("./routes/stockPriceRoutes");
const newsRoutes = require("./routes/newsRoutes");

db.query("SELECT 1")
    .then(() => {
        console.log("MySQL connected");
    })
    .catch((error) => {
        console.log("MySQL connection failed:", error.message);
    });

app.use(cors());
app.use(express.json());
app.use("/sectors", sectorRoutes);
app.use("/companies", companyRoutes);
app.use("/stock-prices", stockPriceRoutes);
app.use("/news", newsRoutes);


app.get("/", (req, res) => {
    res.json({
        message: "InvestIQ Backend is running"
    });
});

const PORT = process.env.PORT || 5500;

app.listen(PORT, () => {
    console.log(`Server running on port ${PORT}`);
});