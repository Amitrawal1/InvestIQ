const express = require("express");
const cors = require("cors");
require("dotenv").config();

const app = express();
const sectorRoutes = require("./routes/sectorRoutes");
const companyRoutes = require("./routes/companyRoutes");

app.use(cors());
app.use(express.json());
app.use("/sectors", sectorRoutes);
app.use("/companies", companyRoutes);

app.get("/", (req, res) => {
    res.json({
        message: "InvestIQ Backend is running"
    });
});

const PORT = process.env.PORT || 5500;

app.listen(PORT, () => {
    console.log(`Server running on port ${PORT}`);
});