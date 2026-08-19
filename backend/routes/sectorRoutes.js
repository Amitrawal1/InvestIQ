const express = require("express");
const router = express.Router();

const { getSectors } = require("../controllers/sectorController");

router.get("/", getSectors);

module.exports = router;