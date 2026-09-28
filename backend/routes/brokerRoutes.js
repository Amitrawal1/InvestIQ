const express = require("express");
const router = express.Router();

const requireAuth = require("../middleware/requireAuth");
const {
    list,
    connect,
    sync,
    remove,
    zerodhaCallback,
} = require("../controllers/brokerController");

// Callback first and without auth: the browser comes back from Kite, the signed state identifies the user
router.get("/zerodha/callback", zerodhaCallback);

router.get("/", requireAuth, list);
router.post("/:broker/connect", requireAuth, connect);
router.post("/:broker/sync", requireAuth, sync);
router.delete("/:broker", requireAuth, remove);

module.exports = router;
