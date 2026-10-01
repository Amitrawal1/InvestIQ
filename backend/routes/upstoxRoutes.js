const express = require("express");
const router = express.Router();

const { login, callback, requestToken, requestTokenPage, cronRequestToken, notifier } = require("../controllers/upstoxController");

router.get("/login", login);
router.get("/callback", callback);
router.post("/request-token", requestToken);
router.get("/request", requestTokenPage);
router.get("/cron", cronRequestToken);         // Vercel Cron (vercel.json), Bearer CRON_SECRET
// Upstox may post JSON or a form
router.post("/notifier", express.urlencoded({ extended: false }), notifier);

module.exports = router;
