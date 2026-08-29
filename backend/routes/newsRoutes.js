const express = require("express");

const {
    getNews,
    getNewsById,
    getCompanyNews
} = require("../controllers/newsController");

const router = express.Router();

router.get("/", getNews);

router.get("/:id", getNewsById);

router.get("/company/:companyId", getCompanyNews);

module.exports = router;