const express = require("express");

const {
    getNews,
    getNewsStats,
    getNewsById,
    getCompanyNews
} = require("../controllers/newsController");

const router = express.Router();

router.get("/", getNews);

// Declared before "/:id" so "stats" isn't swallowed by the id param
router.get("/stats", getNewsStats);

router.get("/company/:companyId", getCompanyNews);

router.get("/:id", getNewsById);

module.exports = router;
