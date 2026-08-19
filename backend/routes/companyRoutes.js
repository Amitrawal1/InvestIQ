const express = require("express");
const router = express.Router();

const { getCompanies, getCompanyById } = require("../controllers/companyController");

router.get("/", getCompanies);
router.get("/:id", getCompanyById);

module.exports = router;