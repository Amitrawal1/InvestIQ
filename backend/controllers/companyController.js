const companies = [
    {
        id: 1,
        name: "Tata Power",
        sector: "solar-energy",
        symbol: "TATAPOWER"
    },
    {
        id: 2,
        name: "Adani Green Energy",
        sector: "solar-energy",
        symbol: "ADANIGREEN"
    },
    {
        id: 3,
        name: "Waaree Energies",
        sector: "solar-energy",
        symbol: "WAAREEENER"
    },
    {
        id: 4,
        name: "Reliance Industries",
        sector: "artificial-intelligence",
        symbol: "RELIANCE"
    }
];

const getCompanies = (req, res) => {
    const { sector } = req.query;

    if (!sector) {
        return res.json(companies);
    }

    const filteredCompanies = companies.filter(
        company => company.sector === sector
    );

    res.json(filteredCompanies);
};

const getCompanyById = (req, res) => {
    const { id } = req.params;

    const company = companies.find(
        company => company.id === Number(id)
    );

    if (!company) {
        return res.status(404).json({
            message: "Company not found"
        });
    }

    res.json(company);
};

module.exports = {
    getCompanies,
    getCompanyById
};
