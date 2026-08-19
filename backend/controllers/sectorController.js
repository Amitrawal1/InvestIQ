const getSectors = (req, res) => {
    const sectors = [
        {
            id: 1,
            name: "Artificial Intelligence",
            slug: "artificial-intelligence"
        },
        {
            id: 2,
            name: "Solar Energy",
            slug: "solar-energy"
        },
        {
            id: 3,
            name: "Banking",
            slug: "banking"
        },
        {
            id: 4,
            name: "Pharmaceuticals",
            slug: "pharmaceuticals"
        }
    ];

    res.json(sectors);
};

module.exports = {
    getSectors
};