const express = require("express");

const {
    getRankings,
    getRankingsMeta
} = require("../controllers/rankingController");

const router = express.Router();

router.get("/", getRankings);
router.get("/meta", getRankingsMeta);

module.exports = router;
