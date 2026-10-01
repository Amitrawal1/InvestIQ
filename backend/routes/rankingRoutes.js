const express = require("express");

const {
    getRankings,
    getRankingsMeta,
    getRankingsTrackRecord,
} = require("../controllers/rankingController");

const router = express.Router();

router.get("/", getRankings);
router.get("/meta", getRankingsMeta);
router.get("/track-record", getRankingsTrackRecord);

module.exports = router;
