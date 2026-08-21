require("dotenv").config();

const db = require("../config/db");

const rules = [
    // Technology
    {
        industry: "Artificial Intelligence",
        keywords: ["artificial intelligence", "ai ", "machine learning"]
    },
    {
        industry: "Semiconductor",
        keywords: ["semiconductor", "microchip", "integrated circuit"]
    },
    {
        industry: "Software",
        keywords: ["software", "software solutions", "software services"]
    },
    {
        industry: "IT Services",
        keywords: ["technologies", "technology services", "infotech", "tech services"]
    },

    // Energy
    {
        industry: "Solar Energy",
        keywords: ["solar", "photovoltaic"]
    },
    {
        industry: "Renewable Energy",
        keywords: ["renewable", "green energy"]
    },
    {
        industry: "Oil & Gas",
        keywords: ["oil", "petroleum", "natural gas", "gas"]
    },
    {
        industry: "Power",
        keywords: ["power", "electricity", "power generation"]
    },

    // Financial Services
    {
        industry: "Banking",
        keywords: ["bank", "banking"]
    },
    {
        industry: "Insurance",
        keywords: ["insurance", "insurer"]
    },
    {
        industry: "NBFC",
        keywords: ["finance", "finserv", "financial services"]
    },

    // Healthcare
    {
        industry: "Pharmaceuticals",
        keywords: ["pharma", "pharmaceutical", "drugs", "medicines"]
    },
    {
        industry: "Hospitals",
        keywords: ["hospital", "healthcare"]
    },
    {
        industry: "Diagnostics",
        keywords: ["diagnostic", "diagnostics"]
    },
    {
        industry: "Medical Devices",
        keywords: ["medical device", "medical equipment"]
    },

    // Automobile
    {
        industry: "Automobiles",
        keywords: ["automobile", "motors", "motor", "vehicles"]
    },
    {
        industry: "Auto Components",
        keywords: ["auto component", "automotive component"]
    },

    // Materials
    {
        industry: "Cement",
        keywords: ["cement"]
    },
    {
        industry: "Metals & Mining",
        keywords: ["steel", "metal", "mining", "minerals"]
    },

    // Chemicals
    {
        industry: "Specialty Chemicals",
        keywords: ["chemical", "chemicals"]
    },

    // Construction
    {
        industry: "Construction",
        keywords: ["construction", "builders", "building"]
    },

    // Real Estate
    {
        industry: "Real Estate Development",
        keywords: ["realty", "real estate", "properties"]
    },

    // Telecom
    {
        industry: "Telecom Services",
        keywords: ["telecom", "telecommunications"]
    },

    // Media
    {
        industry: "Media",
        keywords: ["media", "entertainment", "films", "television"]
    },

    // Agriculture
    {
        industry: "Agricultural Products",
        keywords: ["agriculture", "agro", "seeds", "fertilizer"]
    },

    // Consumer
    {
        industry: "FMCG",
        keywords: ["foods", "food", "consumer products", "consumer goods"]
    },

    // Retail
    {
        industry: "Retail",
        keywords: ["retail", "stores", "mart"]
    }
];


const classifyCompanies = async () => {

    try {

        console.log("================================");
        console.log("Starting company classification...");
        console.log("================================");

        const [companies] = await db.query(`
            SELECT id, name
            FROM companies
            WHERE industry_id IS NULL
        `);

        console.log(`${companies.length} companies need classification`);

        let classified = 0;
        let unclassified = 0;

        for (const company of companies) {

            const companyName = company.name.toLowerCase();

            let matchedIndustry = null;

            for (const rule of rules) {

                const matched = rule.keywords.some(keyword =>
                    companyName.includes(keyword)
                );

                if (matched) {
                    matchedIndustry = rule.industry;
                    break;
                }
            }

            if (!matchedIndustry) {
                unclassified++;
                continue;
            }

            const [industryRows] = await db.query(
                `
                SELECT id, sector_id
                FROM industries
                WHERE name = ?
                LIMIT 1
                `,
                [matchedIndustry]
            );

            if (industryRows.length === 0) {
                console.log(
                    `Industry not found: ${matchedIndustry}`
                );

                unclassified++;
                continue;
            }

            const industry = industryRows[0];

            await db.query(
                `
                UPDATE companies
                SET
                    industry_id = ?,
                    sector_id = ?
                WHERE id = ?
                `,
                [
                    industry.id,
                    industry.sector_id,
                    company.id
                ]
            );

            classified++;
        }

        console.log("--------------------------------");
        console.log(`Classified: ${classified}`);
        console.log(`Unclassified: ${unclassified}`);
        console.log("--------------------------------");

        console.log("Classification completed.");

        process.exit(0);

    } catch (error) {

        console.error("Classification failed:");
        console.error(error.message);

        process.exit(1);
    }
};


classifyCompanies();