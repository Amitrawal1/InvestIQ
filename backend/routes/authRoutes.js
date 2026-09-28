const express = require("express");
const router = express.Router();

const requireAuth = require("../middleware/requireAuth");
const {
    register,
    login,
    me,
    updateMe,
    changePassword,
    deleteMe,
} = require("../controllers/authController");

router.post("/register", register);
router.post("/login", login);
router.get("/me", requireAuth, me);
router.patch("/me", requireAuth, updateMe);
router.post("/password", requireAuth, changePassword);
router.delete("/me", requireAuth, deleteMe);

module.exports = router;
