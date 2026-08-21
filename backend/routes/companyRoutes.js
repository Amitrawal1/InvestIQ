const express = require("express");

const {
    getCompanies
} = require("../controllers/companyController");

const router = express.Router();

router.get("/", getCompanies);

module.exports = router;