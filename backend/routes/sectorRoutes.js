const express = require("express");
const router = express.Router();

const { getSectors, getSectorIndustries } = require("../controllers/sectorController");

router.get("/", getSectors);
router.get("/:slug/industries", getSectorIndustries);

module.exports = router;