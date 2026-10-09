const express = require("express");
const { list, baseRates, detail } = require("../controllers/ipoController");

const router = express.Router();

router.get("/", list);
router.get("/base-rates", baseRates);
router.get("/:symbol", detail);

module.exports = router;
