const express = require("express");
const { list, types, playbook, classify, detail } = require("../controllers/eventsController");

const router = express.Router();

router.get("/", list);
router.get("/types", types);
router.get("/playbook", playbook);
router.post("/classify", classify);
router.get("/:id", detail);

module.exports = router;
