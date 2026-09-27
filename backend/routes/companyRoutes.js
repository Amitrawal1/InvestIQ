const express = require("express");

const {
    getCompanies,
    getCompanyBySymbol,
    getCompanyFinancials,
    getCompanyPrices
} = require("../controllers/companyController");

const router = express.Router();

router.get("/", getCompanies);
router.get("/:symbol", getCompanyBySymbol);
router.get("/:symbol/financials", getCompanyFinancials);
router.get("/:symbol/prices", getCompanyPrices);

module.exports = router;