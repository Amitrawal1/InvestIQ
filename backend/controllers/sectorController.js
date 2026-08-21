const db = require("../config/db");

const getSectors = async (req, res) => {
    try {
        const [rows] = await db.query(
            "SELECT id, name, slug FROM sectors"
        );

        res.json(rows);
    } catch (error) {
        console.error(error);

        res.status(500).json({
            message: "Failed to fetch sectors"
        });
    }
};

module.exports = {
    getSectors
};