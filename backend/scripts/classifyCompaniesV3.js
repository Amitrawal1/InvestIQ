const fs = require("fs");
const path = require("path");

/*
=========================================================
CONFIG
=========================================================
*/

const INPUT_FILE = path.join(
    __dirname,
    "upstox_bulk_classification_v2_preview.json"
);

const OUTPUT_FILE = path.join(
    __dirname,
    "upstox_classification_v3_preview.json"
);


/*
=========================================================
VALID INVESTIQ INDUSTRIES
=========================================================
*/

const INDUSTRIES = {

    // Technology
    "IT Services": 1,
    "Software": 2,
    "Artificial Intelligence": 3,
    "Semiconductor": 4,
    "Hardware": 5,

    // Energy
    "Solar Energy": 6,
    "Renewable Energy": 7,
    "Power": 8,
    "Oil & Gas": 9,

    // Financial
    "Banking": 10,
    "Insurance": 11,
    "NBFC": 12,
    "Asset Management": 13,

    // Healthcare
    "Pharmaceuticals": 14,
    "Hospitals": 15,
    "Diagnostics": 16,
    "Medical Devices": 17,

    // Automobile
    "Automobiles": 18,
    "Auto Components": 19,
    "Electric Vehicles": 20,
    "Mobility Services": 21,

    // Consumer
    "FMCG": 22,
    "Food & Beverages": 23,
    "Retail": 24,
    "Consumer Durables": 25,
    "Consumer Services": 26,

    // Industrials
    "Capital Goods": 27,
    "Engineering": 28,
    "Construction": 29,
    "Infrastructure": 30,
    "Manufacturing": 31,

    // Metals / Chemicals
    "Metals & Mining": 32,
    "Cement": 33,
    "Chemicals": 34,
    "Specialty Chemicals": 35,

    // Real Estate
    "Real Estate": 36,
    "Real Estate Development": 37,
    "Building Materials": 38,

    // Services
    "Telecom": 39,
    "Logistics": 40,
    "Aviation": 41,
    "Hotels & Hospitality": 42,
    "Media & Entertainment": 43,
    "Education": 44,
    "Other Services": 45
};


/*
=========================================================
SECTOR MAPPING
=========================================================
*/

const SECTOR_IDS = {
    technology: 1,
    energy: 2,
    financial: 3,
    healthcare: 4,
    automobile: 5,
    consumer: 21,
    industrial: 22,
    metals: 23,
    realestate: 24,
    services: 25
};


/*
=========================================================
TEXT NORMALIZATION
=========================================================
*/

function normalize(text) {

    return String(text || "")
        .toLowerCase()
        .replace(/&/g, " and ")
        .replace(/[^a-z0-9]+/g, " ")
        .replace(/\s+/g, " ")
        .trim();
}


/*
=========================================================
RULE DEFINITIONS
=========================================================
*/

const RULES = [

    // =====================================================
    // FINANCIAL
    // =====================================================

    {
        industry: "Banking",
        sector: "financial",
        strong: [
            "bank",
            "commercial banking",
            "retail banking",
            "private banking"
        ]
    },

    {
        industry: "Insurance",
        sector: "financial",
        strong: [
            "insurance",
            "insurer",
            "life insurance",
            "general insurance",
            "health insurance"
        ]
    },

    {
        industry: "NBFC",
        sector: "financial",
        strong: [
            "nbfc",
            "non banking financial",
            "housing finance",
            "vehicle finance",
            "microfinance",
            "lending company",
            "lending activities"
        ]
    },

    {
        industry: "Asset Management",
        sector: "financial",
        strong: [
            "asset management",
            "mutual fund",
            "alternative investment fund",
            "portfolio management",
            "wealth management",
            "investment management",
            "pooled funds"
        ]
    },


    // =====================================================
    // TECHNOLOGY
    // =====================================================

    {
        industry: "Artificial Intelligence",
        sector: "technology",
        strong: [
            "artificial intelligence",
            "machine learning",
            "deep learning",
            "generative ai",
            "ai platform"
        ]
    },

    {
        industry: "Semiconductor",
        sector: "technology",
        strong: [
            "semiconductor",
            "semiconductors",
            "integrated circuit",
            "chip design",
            "microprocessor",
            "microcontroller"
        ]
    },

    {
        industry: "IT Services",
        sector: "technology",
        strong: [
            "information technology services",
            "it services",
            "application development",
            "application maintenance",
            "cloud services",
            "cybersecurity",
            "data center",
            "infrastructure services",
            "business process services",
            "digital transformation"
        ]
    },

    {
        industry: "Software",
        sector: "technology",
        strong: [
            "software products",
            "software solutions",
            "software development",
            "computer programming",
            "software as a service",
            "saas",
            "technology software"
        ]
    },

    {
        industry: "Hardware",
        sector: "technology",
        strong: [
            "computer hardware",
            "electronic hardware",
            "electronic products",
            "computer peripherals",
            "network equipment"
        ]
    },


    // =====================================================
    // HEALTHCARE
    // =====================================================

    {
        industry: "Diagnostics",
        sector: "healthcare",
        strong: [
            "diagnostic kits",
            "diagnostics",
            "diagnostic services",
            "pathology",
            "molecular diagnostics",
            "pcr based",
            "diagnostic laboratory",
            "diagnostic lab"
        ]
    },

    {
        industry: "Medical Devices",
        sector: "healthcare",
        strong: [
            "medical devices",
            "medical equipment",
            "medical supplies",
            "surgical devices",
            "surgical equipment"
        ]
    },

    {
        industry: "Hospitals",
        sector: "healthcare",
        strong: [
            "hospital",
            "hospitals",
            "hospital chain",
            "healthcare provider",
            "health care provider"
        ]
    },

    {
        industry: "Pharmaceuticals",
        sector: "healthcare",
        strong: [
            "pharmaceutical",
            "pharmaceuticals",
            "pharma",
            "drug manufacturing",
            "formulations",
            "active pharmaceutical ingredient",
            "api manufacturing"
        ]
    },


    // =====================================================
    // AUTOMOBILE
    // =====================================================

    {
        industry: "Electric Vehicles",
        sector: "automobile",
        strong: [
            "electric vehicle",
            "electric vehicles",
            "ev manufacturer",
            "electric mobility",
            "electric scooter",
            "electric bus"
        ]
    },

    {
        industry: "Auto Components",
        sector: "automobile",
        strong: [
            "auto ancillary",
            "auto component",
            "automotive component",
            "automobile component",
            "forgings",
            "automotive gears",
            "automotive parts"
        ]
    },

    {
        industry: "Mobility Services",
        sector: "automobile",
        strong: [
            "mobility services",
            "ride hailing",
            "ride sharing",
            "cab services",
            "vehicle rental"
        ]
    },

    {
        industry: "Automobiles",
        sector: "automobile",
        strong: [
            "automobiles",
            "automobile manufacturer",
            "vehicle manufacturer",
            "passenger vehicles",
            "commercial vehicles",
            "two wheelers",
            "three wheelers"
        ]
    },


    // =====================================================
    // ENERGY
    // =====================================================

    {
        industry: "Oil & Gas",
        sector: "energy",
        strong: [
            "oil exploration",
            "oil and gas",
            "oil & gas",
            "refinery",
            "refineries",
            "petroleum",
            "natural gas",
            "oil drilling",
            "oilfield"
        ]
    },

    {
        industry: "Power",
        sector: "energy",
        strong: [
            "power generation",
            "power transmission",
            "power distribution",
            "electricity generation",
            "thermal power",
            "power company"
        ]
    },

    {
        industry: "Solar Energy",
        sector: "energy",
        strong: [
            "solar energy",
            "solar power",
            "solar module",
            "solar panels",
            "photovoltaic"
        ]
    },

    {
        industry: "Renewable Energy",
        sector: "energy",
        strong: [
            "renewable energy",
            "wind energy",
            "wind power",
            "green energy",
            "clean energy"
        ]
    },


    // =====================================================
    // CONSUMER
    // =====================================================

    {
        industry: "Food & Beverages",
        sector: "consumer",
        strong: [
            "food products",
            "food processing",
            "beverages",
            "consumer food",
            "food manufacturing",
            "dairy products",
            "tea coffee"
        ]
    },

    {
        industry: "FMCG",
        sector: "consumer",
        strong: [
            "fast moving consumer goods",
            "fmcg",
            "personal care products",
            "household products"
        ]
    },

    {
        industry: "Retail",
        sector: "consumer",
        strong: [
            "retail",
            "retailer",
            "retailing",
            "e commerce",
            "ecommerce",
            "online marketplace"
        ]
    },

    {
        industry: "Consumer Durables",
        sector: "consumer",
        strong: [
            "consumer durables",
            "home appliances",
            "household appliances",
            "electrical appliances",
            "air conditioner",
            "refrigerator"
        ]
    },

    {
        industry: "Consumer Services",
        sector: "consumer",
        strong: [
            "consumer services",
            "restaurant",
            "restaurants",
            "food service",
            "travel services"
        ]
    },


    // =====================================================
    // INDUSTRIAL
    // =====================================================

    {
        industry: "Construction",
        sector: "industrial",
        strong: [
            "construction",
            "construction company",
            "building construction",
            "construction services",
            "epc contractor"
        ]
    },

    {
        industry: "Infrastructure",
        sector: "industrial",
        strong: [
            "infrastructure",
            "infrastructure development",
            "road infrastructure",
            "port infrastructure",
            "urban infrastructure"
        ]
    },

    {
        industry: "Engineering",
        sector: "industrial",
        strong: [
            "engineering services",
            "engineering company",
            "engineering solutions",
            "engineering products"
        ]
    },

    {
        industry: "Capital Goods",
        sector: "industrial",
        strong: [
            "capital goods",
            "industrial equipment",
            "industrial machinery",
            "heavy engineering",
            "electrical equipment",
            "industrial equipment manufacturing"
        ]
    },

    {
        industry: "Manufacturing",
        sector: "industrial",
        strong: [
            "manufacturing",
            "manufactures",
            "manufacturing company",
            "industrial products"
        ]
    },


    // =====================================================
    // METALS / CHEMICALS
    // =====================================================

    {
        industry: "Metals & Mining",
        sector: "metals",
        strong: [
            "mining",
            "minerals",
            "metal",
            "metals",
            "steel",
            "iron",
            "aluminium",
            "copper",
            "zinc",
            "ferro alloys",
            "steel products"
        ]
    },

    {
        industry: "Cement",
        sector: "metals",
        strong: [
            "cement",
            "cement products"
        ]
    },

    {
        industry: "Specialty Chemicals",
        sector: "metals",
        strong: [
            "specialty chemical",
            "specialty chemicals",
            "performance chemicals",
            "speciality chemicals"
        ]
    },

    {
        industry: "Chemicals",
        sector: "metals",
        strong: [
            "chemical",
            "chemicals",
            "fertilizer",
            "fertilizers",
            "agrochemicals",
            "petrochemicals",
            "industrial chemicals"
        ]
    },


    // =====================================================
    // REAL ESTATE / BUILDING
    // =====================================================

    {
        industry: "Real Estate Development",
        sector: "realestate",
        strong: [
            "real estate development",
            "property development",
            "property developer",
            "realty developer",
            "residential developer",
            "commercial developer"
        ]
    },

    {
        industry: "Real Estate",
        sector: "realestate",
        strong: [
            "real estate",
            "realty",
            "property leasing",
            "real estate leasing"
        ]
    },

    {
        industry: "Building Materials",
        sector: "realestate",
        strong: [
            "building materials",
            "ceramic products",
            "tiles",
            "sanitaryware",
            "pipes",
            "cables",
            "glass products",
            "decoratives"
        ]
    },


    // =====================================================
    // SERVICES
    // =====================================================

    {
        industry: "Telecom",
        sector: "services",
        strong: [
            "telecom",
            "telecommunication",
            "telecommunications",
            "wireless communication"
        ]
    },

    {
        industry: "Logistics",
        sector: "services",
        strong: [
            "logistics",
            "shipping",
            "freight",
            "transportation",
            "supply chain",
            "warehousing",
            "cargo"
        ]
    },

    {
        industry: "Aviation",
        sector: "services",
        strong: [
            "aviation",
            "airline",
            "airlines",
            "airport",
            "air transportation"
        ]
    },

    {
        industry: "Hotels & Hospitality",
        sector: "services",
        strong: [
            "hotel",
            "hotels",
            "hospitality",
            "resort",
            "resorts"
        ]
    },

    {
        industry: "Media & Entertainment",
        sector: "services",
        strong: [
            "media",
            "entertainment",
            "film production",
            "television",
            "broadcasting",
            "digital media",
            "content production"
        ]
    },

    {
        industry: "Education",
        sector: "services",
        strong: [
            "education",
            "educational services",
            "school",
            "schools",
            "university",
            "edtech",
            "e learning"
        ]
    }
];


/*
=========================================================
SPECIAL UPSTOX SECTOR MAPPINGS
=========================================================
*/

const SECTOR_HINTS = {

    "banking": "Banking",
    "private bank": "Banking",

    "insurance": "Insurance",

    "nbfc": "NBFC",
    "housing finance": "NBFC",
    "microfinance": "NBFC",
    "finance": "NBFC",

    "investment": "Asset Management",
    "asset management": "Asset Management",
    "mutual fund": "Asset Management",
    "wealth management": "Asset Management",

    "stock broking": "Other Services",

    "it software": "Software",
    "software": "Software",
    "it services": "IT Services",

    "semiconductors": "Semiconductor",
    "semiconductor": "Semiconductor",

    "pharmaceuticals": "Pharmaceuticals",
    "diagnostics": "Diagnostics",
    "medical devices": "Medical Devices",
    "hospitals": "Hospitals",

    "auto ancillary": "Auto Components",
    "automobiles": "Automobiles",
    "electric vehicles": "Electric Vehicles",

    "oil and gas": "Oil & Gas",
    "oil exploration": "Oil & Gas",
    "refineries": "Oil & Gas",
    "power": "Power",
    "solar": "Solar Energy",
    "renewable energy": "Renewable Energy",

    "cement": "Cement",
    "metals": "Metals & Mining",
    "steel": "Metals & Mining",
    "minerals": "Metals & Mining",

    "real estate": "Real Estate",
    "realty": "Real Estate",
    "construction": "Construction",

    "logistics": "Logistics",
    "shipping": "Logistics",
    "aviation": "Aviation",
    "hotel": "Hotels & Hospitality",
    "hotels": "Hotels & Hospitality",
    "media": "Media & Entertainment",
    "film production": "Media & Entertainment",
    "education": "Education",

    "consumer food": "Food & Beverages",
    "food": "Food & Beverages",
    "beverages": "Food & Beverages",

    "retail": "Retail",

    "engineering": "Engineering",
    "capital goods": "Capital Goods"
};


/*
=========================================================
PROFILE OVERRIDES
=========================================================
*/

function profileSpecificIndustry(text) {

    // Diagnostics must beat generic healthcare/agrochemical
    if (
        text.includes("molecular diagnostic") ||
        text.includes("diagnostic kits") ||
        text.includes("pcr-based") ||
        text.includes("diagnostic laboratory")
    ) {
        return "Diagnostics";
    }

    // Medical devices
    if (
        text.includes("medical devices") ||
        text.includes("medical equipment") ||
        text.includes("surgical devices")
    ) {
        return "Medical Devices";
    }

    // Hospitals
    if (
        text.includes("hospital chain") ||
        text.includes("operates hospitals") ||
        text.includes("hospital services")
    ) {
        return "Hospitals";
    }

    // Asset management
    if (
        text.includes("asset management") ||
        text.includes("mutual funds") ||
        text.includes("pooled funds") ||
        text.includes("alternative investment fund") ||
        text.includes("portfolio management")
    ) {
        return "Asset Management";
    }

    // Lending
    if (
        text.includes("lending company") ||
        text.includes("lending activities") ||
        text.includes("non banking financial") ||
        text.includes("housing finance")
    ) {
        return "NBFC";
    }

    // Software / IT
    if (
        text.includes("application development") ||
        text.includes("application maintenance") ||
        text.includes("cloud") &&
        text.includes("cybersecurity")
    ) {
        return "IT Services";
    }

    if (
        text.includes("software services") ||
        text.includes("software solutions") ||
        text.includes("computer programming")
    ) {
        return "Software";
    }

    // EV
    if (
        text.includes("electric vehicle") ||
        text.includes("electric vehicles") ||
        text.includes("electric mobility")
    ) {
        return "Electric Vehicles";
    }

    // Auto components
    if (
        text.includes("auto component") ||
        text.includes("automotive component") ||
        text.includes("auto ancillary") ||
        text.includes("automotive parts")
    ) {
        return "Auto Components";
    }

    // Oil
    if (
        text.includes("oil exploration") ||
        text.includes("oil and gas") ||
        text.includes("refinery") ||
        text.includes("petroleum")
    ) {
        return "Oil & Gas";
    }

    // Real estate development
    if (
        text.includes("real estate development") ||
        text.includes("property developer") ||
        text.includes("realty developer")
    ) {
        return "Real Estate Development";
    }

    // Hotels
    if (
        text.includes("hotel") ||
        text.includes("hospitality") ||
        text.includes("resort")
    ) {
        return "Hotels & Hospitality";
    }

    // Media
    if (
        text.includes("film production") ||
        text.includes("digital media") ||
        text.includes("television") ||
        text.includes("broadcasting")
    ) {
        return "Media & Entertainment";
    }

    return null;
}


/*
=========================================================
CLASSIFY
=========================================================
*/

function classify(company) {

    const name = normalize(company.name);
    const symbol = normalize(company.symbol);
    const upstoxSector = normalize(company.upstox_sector);
    const profile = normalize(company.company_profile);

    const fullText =
        `${name} ${symbol} ${upstoxSector} ${profile}`;

    const scores = {};
    const matchedRules = {};

    function addScore(industry, score, reason) {

        if (!INDUSTRIES[industry]) return;

        scores[industry] =
            (scores[industry] || 0) + score;

        if (!matchedRules[industry]) {
            matchedRules[industry] = [];
        }

        matchedRules[industry].push({
            score,
            reason
        });
    }


    /*
    =====================================================
    1. PROFILE-SPECIFIC HIGH PRIORITY
    =====================================================
    */

    const profileIndustry =
        profileSpecificIndustry(profile);

    if (profileIndustry) {
        addScore(
            profileIndustry,
            100,
            "profile_specific"
        );
    }


    /*
    =====================================================
    2. UPSTOX SECTOR
    =====================================================
    */

    for (const [hint, industry] of Object.entries(SECTOR_HINTS)) {

        if (upstoxSector.includes(hint)) {

            addScore(
                industry,
                55,
                `upstox_sector:${hint}`
            );
        }
    }


    /*
    =====================================================
    3. PROFILE RULES
    =====================================================
    */

    for (const rule of RULES) {

        for (const keyword of rule.strong) {

            if (profile.includes(keyword)) {

                addScore(
                    rule.industry,
                    30,
                    `profile:${keyword}`
                );
            }
        }
    }


    /*
    =====================================================
    4. NAME RULES
    =====================================================
    */

    for (const rule of RULES) {

        for (const keyword of rule.strong) {

            if (name.includes(keyword)) {

                addScore(
                    rule.industry,
                    15,
                    `name:${keyword}`
                );
            }
        }
    }


    /*
    =====================================================
    5. SELECT WINNER
    =====================================================
    */

    const ranked =
        Object.entries(scores)
            .sort((a, b) => b[1] - a[1]);


    if (ranked.length === 0) {

        return {
            investiq_industry: null,
            industry_id: null,
            sector_id: null,
            confidence: 0,
            status: "UNMAPPED",
            matched_rules: []
        };
    }


    const [bestIndustry, bestScore] = ranked[0];

    const secondScore =
        ranked.length > 1
            ? ranked[1][1]
            : 0;

    const margin =
        bestScore - secondScore;


    /*
    =====================================================
    CONFIDENCE
    =====================================================
    */

    let confidence = 0;
    let status = "UNMAPPED";

    if (bestScore >= 100 && margin >= 25) {

        confidence = 95;
        status = "HIGH_CONFIDENCE";

    } else if (bestScore >= 80 && margin >= 20) {

        confidence = 90;
        status = "HIGH_CONFIDENCE";

    } else if (bestScore >= 60 && margin >= 15) {

        confidence = 75;
        status = "MEDIUM_CONFIDENCE";

    } else if (bestScore >= 45 && margin >= 10) {

        confidence = 65;
        status = "LOW_CONFIDENCE";

    } else {

        confidence = 0;
        status = "UNMAPPED";
    }


    /*
    =====================================================
    VALIDATE INDUSTRY
    =====================================================
    */

    const industryId =
        INDUSTRIES[bestIndustry] || null;


    /*
    Sector is temporarily derived from rule.
    Final DB sector will come from industries table.
    */

    let sectorId = null;

    for (const rule of RULES) {

        if (rule.industry === bestIndustry) {

            sectorId =
                SECTOR_IDS[rule.sector];

            break;
        }
    }


    return {

        investiq_industry:
            status === "UNMAPPED"
                ? null
                : bestIndustry,

        industry_id:
            status === "UNMAPPED"
                ? null
                : industryId,

        sector_id:
            status === "UNMAPPED"
                ? null
                : sectorId,

        confidence,

        status,

        matched_rules:
            matchedRules[bestIndustry] || [],

        candidates:
            ranked.slice(0, 3).map(([industry, score]) => ({
                industry,
                score
            }))
    };
}


/*
=========================================================
MAIN
=========================================================
*/

function main() {

    console.log("\n========================================");
    console.log("InvestIQ V3 Classification");
    console.log("========================================");

    if (!fs.existsSync(INPUT_FILE)) {

        console.error("\nERROR:");
        console.error(
            `Input file not found:\n${INPUT_FILE}`
        );

        process.exit(1);
    }


    const raw =
        fs.readFileSync(INPUT_FILE, "utf8");

    const data =
        JSON.parse(raw);


    const results =
        data.results || data;


    console.log(
        `Companies loaded: ${results.length}`
    );


    const output = [];

    for (const company of results) {

        /*
        API failure remains API failure.
        We DO NOT guess.
        */

        if (
            company.status === "UPSTOX_FAILED"
        ) {

            output.push({
                ...company,
                investiq_industry: null,
                industry_id: null,
                sector_id: null,
                confidence: 0,
                status: "UPSTOX_FAILED",
                v3_source: "none"
            });

            continue;
        }


        const classification =
            classify(company);


        output.push({

            ...company,

            ...classification,

            v3_source:
                "upstox_sector+company_profile+name"
        });
    }


    /*
    =====================================================
    SUMMARY
    =====================================================
    */

    const statusCount = {};

    const industryCount = {};

    for (const result of output) {

        statusCount[result.status] =
            (statusCount[result.status] || 0) + 1;

        const industry =
            result.investiq_industry;

        if (industry) {

            industryCount[industry] =
                (industryCount[industry] || 0) + 1;
        }
    }


    console.log("\n========== STATUS ==========");

    Object.entries(statusCount)
        .sort((a, b) => b[1] - a[1])
        .forEach(([status, count]) => {

            console.log(
                `${status.padEnd(22)} ${count}`
            );
        });


    console.log("\n========== INDUSTRIES ==========");

    Object.entries(industryCount)
        .sort((a, b) => b[1] - a[1])
        .forEach(([industry, count]) => {

            console.log(
                `${industry.padEnd(30)} ${count}`
            );
        });


    /*
    =====================================================
    SAVE
    =====================================================
    */

    fs.writeFileSync(
        OUTPUT_FILE,
        JSON.stringify(
            {
                version: "V3",
                total: output.length,
                results: output
            },
            null,
            2
        )
    );


    console.log("\n========================================");
    console.log("V3 CLASSIFICATION COMPLETE");
    console.log("========================================");

    console.log(
        `Preview saved:\n${OUTPUT_FILE}`
    );

    console.log(
        "\nDATABASE WAS NOT MODIFIED"
    );

    console.log("========================================\n");
}


main();