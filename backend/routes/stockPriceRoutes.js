const express = require("express");
const router = express.Router();

const {
    getStockPrices
} = require("../controllers/stockPriceController");

router.get("/:companyId", getStockPrices);

module.exports = router;