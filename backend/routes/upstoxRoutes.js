const express = require("express");
const router = express.Router();

const { login, callback, requestToken, requestTokenPage, notifier } = require("../controllers/upstoxController");

router.get("/login", login);
router.get("/callback", callback);
router.post("/request-token", requestToken);
router.get("/request", requestTokenPage);
// Upstox may post JSON or a form
router.post("/notifier", express.urlencoded({ extended: false }), notifier);

module.exports = router;
