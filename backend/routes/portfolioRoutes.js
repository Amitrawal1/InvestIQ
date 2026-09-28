const express = require("express");
const router = express.Router();

const requireAuth = require("../middleware/requireAuth");
const { getPortfolio } = require("../controllers/portfolioController");

router.get("/", requireAuth, getPortfolio);

module.exports = router;
