const fs = require("fs");
const path = require("path");

const INPUT_FILE = path.join(
    __dirname,
    "upstox_classification_v3_1_preview.json"
);

const OUTPUT_FILE = path.join(
    __dirname,
    "upstox_classification_v3_2_preview.json"
);


/*
=========================================================
INVESTIQ INDUSTRIES
=========================================================
*/

const INDUSTRIES = {
    "IT Services": 1,
    "Software": 2,
    "Artificial Intelligence": 3,
    "Semiconductor": 4,
    "Hardware": 5,

    "Solar Energy": 6,
    "Renewable Energy": 7,
    "Power": 8,
    "Oil & Gas": 9,

    "Banking": 10,
    "Insurance": 11,
    "NBFC": 12,
    "Asset Management": 13,

    "Pharmaceuticals": 14,
    "Hospitals": 15,
    "Diagnostics": 16,
    "Medical Devices": 17,

    "Automobiles": 18,
    "Auto Components": 19,
    "Electric Vehicles": 20,
    "Mobility Services": 21,

    "FMCG": 22,
    "Food & Beverages": 23,
    "Retail": 24,
    "Consumer Durables": 25,
    "Consumer Services": 26,

    "Capital Goods": 27,
    "Engineering": 28,
    "Construction": 29,
    "Infrastructure": 30,
    "Manufacturing": 31,

    "Metals & Mining": 32,
    "Cement": 33,
    "Chemicals": 34,
    "Specialty Chemicals": 35,

    "Real Estate": 36,
    "Real Estate Development": 37,
    "Building Materials": 38,

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
NORMALIZE
=========================================================
*/

function normalize(value) {
    return String(value || "")
        .toLowerCase()
        .replace(/&/g, " and ")
        .replace(/[^a-z0-9]+/g, " ")
        .replace(/\s+/g, " ")
        .trim();
}


/*
=========================================================
EXACT UPSTOX SECTOR MAPPING
=========================================================
*/

const SECTOR_MAP = {

    // Technology
    "it software": "Software",
    "it software ": "Software",
    "software": "Software",
    "bpo ites": "IT Services",
    "it hardware": "Hardware",
    "it networking": "IT Services",
    "it education": "Education",
    "electronics": "Hardware",
    "semiconductor": "Semiconductor",
    "semiconductors": "Semiconductor",

    // Financial
    "banking": "Banking",
    "insurance": "Insurance",
    "nbfc": "NBFC",
    "housing finance": "NBFC",
    "asset management": "Asset Management",
    "investment": "Asset Management",

    // Healthcare
    "pharmaceuticals": "Pharmaceuticals",
    "healthcare": "Hospitals",
    "healthcare services": "Hospitals",
    "diagnostics": "Diagnostics",
    "medical equipment": "Medical Devices",

    // Automobile
    "automobile": "Automobiles",
    "automobiles": "Automobiles",
    "auto ancillary": "Auto Components",
    "auto ancillaries": "Auto Components",
    "auto components": "Auto Components",
    "tyres allied": "Auto Components",
    "tyres": "Auto Components",
    "batteries": "Auto Components",
    "bearings": "Auto Components",
    "forgings": "Auto Components",
    "castings": "Auto Components",
    "castings forgings fastners": "Auto Components",

    // Energy
    "oil drill allied": "Oil & Gas",
    "oil exploration": "Oil & Gas",
    "petrochemicals": "Oil & Gas",
    "gases fuels": "Oil & Gas",
    "gas transmission": "Oil & Gas",
    "lubricants": "Oil & Gas",
    "power generation distribution": "Power",
    "power": "Power",

    // Consumer
    "fmcg": "FMCG",
    "household products": "FMCG",
    "tobacco": "FMCG",
    "tobacco products": "FMCG",

    "tea coffee": "Food & Beverages",
    "breweries": "Food & Beverages",
    "sugar": "Food & Beverages",
    "edible oil": "Food & Beverages",
    "aquaculture": "Food & Beverages",

    "consumer durables": "Consumer Durables",

    "e commerce": "Retail",
    "e commerce app based aggregator": "Retail",
    "retailing": "Retail",
    "retail": "Retail",

    "footwear": "Consumer Services",
    "diamond gems and jewellery": "Consumer Services",
    "jewellery": "Consumer Services",
    "watches accessories": "Consumer Services",

    "quick service restaurant": "Consumer Services",
    "recreation": "Consumer Services",
    "entertainment": "Consumer Services",

    // Industrial
    "capital goods electrical equipment": "Capital Goods",
    "capital goods non electrical equipment": "Capital Goods",
    "capital goods": "Capital Goods",
    "electric equipment": "Capital Goods",
    "welding equipment": "Capital Goods",
    "diesel engines": "Capital Goods",
    "compressors": "Capital Goods",
    "abrasives": "Capital Goods",
    "defence": "Capital Goods",
    "aerospace defence": "Capital Goods",
    "ship building": "Capital Goods",
    "railways wagons": "Capital Goods",

    "engineering": "Engineering",

    "construction": "Construction",

    "infrastructure developers operators": "Infrastructure",
    "transmission towers": "Infrastructure",
    "telecom equipment infra services": "Infrastructure",

    // Manufacturing
    "textile": "Manufacturing",
    "textiles": "Manufacturing",
    "plastic products": "Manufacturing",
    "paper": "Manufacturing",
    "packaging": "Manufacturing",
    "rubber products": "Manufacturing",
    "leather": "Manufacturing",
    "stationery": "Manufacturing",
    "wood products": "Manufacturing",
    "solvent extraction": "Manufacturing",
    "refractories": "Manufacturing",
    "photographic products": "Manufacturing",

    // Metals
    "steel iron products": "Metals & Mining",
    "metal": "Metals & Mining",
    "metals": "Metals & Mining",
    "steel": "Metals & Mining",
    "non ferrous metals": "Metals & Mining",
    "aluminium products": "Metals & Mining",
    "mining mineral products": "Metals & Mining",
    "minerals": "Metals & Mining",
    "carbon black": "Chemicals",

    // Chemicals
    "chemicals": "Chemicals",
    "agrochemicals": "Chemicals",
    "agro chemicals": "Chemicals",
    "dyes pigments": "Chemicals",
    "fertilizers": "Chemicals",
    "paints": "Chemicals",
    "specialty chemicals": "Specialty Chemicals",

    // Building Materials
    "ceramics": "Building Materials",
    "plywood boards laminates": "Building Materials",
    "cable": "Building Materials",
    "decoratives": "Building Materials",
    "glass": "Building Materials",
    "construction materials": "Building Materials",

    // Real Estate
    "realty": "Real Estate",
    "real estate": "Real Estate",
    "co working": "Real Estate",

    // Services
    "telecommunication": "Telecom",
    "telecom service": "Telecom",

    "logistics": "Logistics",
    "shipping": "Logistics",
    "port": "Logistics",
    "courier services": "Logistics",

    "airlines": "Aviation",

    "hotel": "Hotels & Hospitality",
    "hotels": "Hotels & Hospitality",

    "film production": "Media & Entertainment",
    "tv broadcasting": "Media & Entertainment",
    "printing and publishing": "Media & Entertainment",

    "educational institutions": "Education"
};


/*
=========================================================
PROFILE RULES
Used only to disambiguate broad sectors.
=========================================================
*/

const PROFILE_RULES = [

    {
        industry: "Diagnostics",
        keywords: [
            "diagnostic kits",
            "molecular diagnostics",
            "diagnostic laboratory",
            "diagnostic lab",
            "pathology",
            "pcr based"
        ]
    },

    {
        industry: "Medical Devices",
        keywords: [
            "medical devices",
            "medical equipment",
            "surgical devices",
            "surgical equipment"
        ]
    },

    {
        industry: "Hospitals",
        keywords: [
            "hospital chain",
            "operates hospitals",
            "hospital services",
            "healthcare provider"
        ]
    },

    {
        industry: "NBFC",
        keywords: [
            "lending company",
            "lending activities",
            "housing finance",
            "microfinance",
            "non banking financial"
        ]
    },

    {
        industry: "Asset Management",
        keywords: [
            "asset management",
            "mutual fund",
            "mutual funds",
            "wealth management",
            "portfolio management",
            "investment management"
        ]
    },

    {
        industry: "IT Services",
        keywords: [
            "application development",
            "application maintenance",
            "business process",
            "cloud services",
            "cybersecurity",
            "digital transformation"
        ]
    },

    {
        industry: "Software",
        keywords: [
            "software products",
            "software solutions",
            "software development",
            "computer programming",
            "saas"
        ]
    },

    {
        industry: "Electric Vehicles",
        keywords: [
            "electric vehicle",
            "electric vehicles",
            "electric mobility",
            "electric scooter",
            "electric bus"
        ]
    },

    {
        industry: "Auto Components",
        keywords: [
            "auto component",
            "automotive component",
            "automotive parts",
            "auto ancillary"
        ]
    },

    {
        industry: "Oil & Gas",
        keywords: [
            "oil exploration",
            "oil and gas",
            "oilfield",
            "oil drilling",
            "refinery",
            "petroleum"
        ]
    },

    {
        industry: "Real Estate Development",
        keywords: [
            "real estate development",
            "property developer",
            "realty developer",
            "residential developer",
            "commercial developer"
        ]
    },

    {
        industry: "Hotels & Hospitality",
        keywords: [
            "hotel",
            "hotels",
            "hospitality",
            "resort"
        ]
    },

    {
        industry: "Media & Entertainment",
        keywords: [
            "film production",
            "television",
            "broadcasting",
            "digital media",
            "content production"
        ]
    }
];


/*
=========================================================
BROAD SECTOR PROFILE RULES
=========================================================
*/

function profileIndustry(profile) {

    const p = normalize(profile);

    for (const rule of PROFILE_RULES) {

        for (const keyword of rule.keywords) {

            if (p.includes(normalize(keyword))) {
                return rule.industry;
            }
        }
    }

    return null;
}


/*
=========================================================
SPECIAL HANDLING FOR BROAD / AMBIGUOUS SECTORS
=========================================================
*/

function classifyBroadSector(company, sector) {

    const name = normalize(company.name);
    const profile = normalize(company.company_profile);

    const text = `${name} ${profile}`;


    /*
    Finance:
    Do NOT automatically call every finance company
    Asset Management.
    */

    if (sector === "finance" || sector === "financial services") {

        if (
            text.includes("wealth management") ||
            text.includes("asset management") ||
            text.includes("mutual fund") ||
            text.includes("portfolio management") ||
            text.includes("investment management")
        ) {
            return "Asset Management";
        }

        if (
            text.includes("lending") ||
            text.includes("loan") ||
            text.includes("financing") ||
            text.includes("finance company")
        ) {
            return "NBFC";
        }

        return "Other Services";
    }


    /*
    Trading:
    Trading is intentionally Other Services unless
    company profile clearly reveals a specific industry.
    */

    if (sector === "trading") {

        const p = profileIndustry(profile);

        if (p) return p;

        if (
            text.includes("pharmaceutical") ||
            text.includes("pharma")
        ) {
            return "Pharmaceuticals";
        }

        if (
            text.includes("chemical")
        ) {
            return "Chemicals";
        }

        if (
            text.includes("steel") ||
            text.includes("metal")
        ) {
            return "Metals & Mining";
        }

        return "Other Services";
    }


    /*
    Diversified / Miscellaneous / DVR:
    only classify if profile/name gives clear evidence.
    */

    if (
        sector === "diversified" ||
        sector === "miscellaneous" ||
        sector === "dvr"
    ) {

        const p = profileIndustry(profile);

        if (p) return p;

        if (text.includes("pharma")) {
            return "Pharmaceuticals";
        }

        if (text.includes("hospital")) {
            return "Hospitals";
        }

        if (text.includes("software")) {
            return "Software";
        }

        if (text.includes("technology")) {
            return "IT Services";
        }

        if (text.includes("real estate")) {
            return "Real Estate";
        }

        if (text.includes("construction")) {
            return "Construction";
        }

        if (text.includes("manufacturing")) {
            return "Manufacturing";
        }

        return null;
    }


    /*
    Agriculture
    */

    if (sector === "agriculture") {

        if (
            text.includes("seed") ||
            text.includes("seeds") ||
            text.includes("agro")
        ) {
            return "Other Services";
        }

        if (
            text.includes("food") ||
            text.includes("edible")
        ) {
            return "Food & Beverages";
        }

        return "Other Services";
    }


    return null;
}


/*
=========================================================
CLASSIFY
=========================================================
*/

function classify(company) {

    const sector = normalize(
        company.upstox_sector
    );

    const name = normalize(company.name);
    const profile = normalize(company.company_profile);

    /*
    -----------------------------------------------------
    1. Exact sector mapping
    -----------------------------------------------------
    */

    if (SECTOR_MAP[sector]) {

        const industry =
            SECTOR_MAP[sector];

        return {
            industry,
            confidence: 92,
            status: "HIGH_CONFIDENCE",
            source: "upstox_sector_exact",
            matched_rules: [
                `sector:${company.upstox_sector}`
            ]
        };
    }


    /*
    -----------------------------------------------------
    2. Broad sector handling
    -----------------------------------------------------
    */

    const broad =
        classifyBroadSector(
            company,
            sector
        );

    if (broad) {

        return {
            industry: broad,
            confidence:
                broad === "Other Services"
                    ? 65
                    : 85,
            status:
                broad === "Other Services"
                    ? "LOW_CONFIDENCE"
                    : "HIGH_CONFIDENCE",
            source: "sector+profile",
            matched_rules: [
                `sector:${company.upstox_sector}`
            ]
        };
    }


    /*
    -----------------------------------------------------
    3. Profile-specific
    -----------------------------------------------------
    */

    const pIndustry =
        profileIndustry(profile);

    if (pIndustry) {

        return {
            industry: pIndustry,
            confidence: 78,
            status: "MEDIUM_CONFIDENCE",
            source: "profile",
            matched_rules: [
                "profile_specific"
            ]
        };
    }


    /*
    -----------------------------------------------------
    4. Name fallback
    -----------------------------------------------------
    */

    const nameRules = [

        ["pharma", "Pharmaceuticals"],
        ["pharmaceutical", "Pharmaceuticals"],

        ["hospital", "Hospitals"],

        ["cement", "Cement"],

        ["steel", "Metals & Mining"],
        ["mining", "Metals & Mining"],
        ["minerals", "Metals & Mining"],

        ["chemical", "Chemicals"],

        ["textile", "Manufacturing"],
        ["textiles", "Manufacturing"],

        ["engineering", "Engineering"],

        ["construction", "Construction"],

        ["infra", "Infrastructure"],

        ["logistics", "Logistics"],

        ["telecom", "Telecom"],

        ["software", "Software"],

        ["technology", "IT Services"],

        ["hotel", "Hotels & Hospitality"],
        ["resort", "Hotels & Hospitality"],

        ["education", "Education"]
    ];


    for (const [keyword, industry] of nameRules) {

        if (name.includes(keyword)) {

            return {
                industry,
                confidence: 60,
                status: "LOW_CONFIDENCE",
                source: "name",
                matched_rules: [
                    `name:${keyword}`
                ]
            };
        }
    }


    /*
    -----------------------------------------------------
    5. Remain unmapped
    -----------------------------------------------------
    */

    return {
        industry: null,
        confidence: 0,
        status: "UNMAPPED",
        source: "none",
        matched_rules: []
    };
}


/*
=========================================================
MAIN
=========================================================
*/

function main() {

    console.log("\n========================================");
    console.log("InvestIQ V3.2 Classification");
    console.log("========================================");


    if (!fs.existsSync(INPUT_FILE)) {

        console.error(
            `Input file not found:\n${INPUT_FILE}`
        );

        process.exit(1);
    }


    const data =
        JSON.parse(
            fs.readFileSync(INPUT_FILE, "utf8")
        );

    const results =
        data.results || data;


    console.log(
        `Companies loaded: ${results.length}`
    );


    const output = [];


    for (const company of results) {

        /*
        NEVER classify failed API records here.
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

                v3_2_source: "none"
            });

            continue;
        }


        /*
        Keep already high-confidence V3.1
        classifications unless the company was
        originally unmapped/low-confidence.
        */

        let classification;


        if (
            company.status === "HIGH_CONFIDENCE" &&
            company.investiq_industry
        ) {

            classification = {
                industry:
                    company.investiq_industry,

                confidence:
                    company.confidence || 92,

                status:
                    "HIGH_CONFIDENCE",

                source:
                    company.v3_1_source ||
                    "v3.1_preserved",

                matched_rules:
                    company.matched_rules || []
            };

        } else {

            classification =
                classify(company);
        }


        output.push({

            ...company,

            investiq_industry:
                classification.industry,

            industry_id:
                classification.industry
                    ? INDUSTRIES[classification.industry]
                    : null,

            /*
            DO NOT set sector_id here.
            It will be derived from industries table
            during final DB update.
            */

            sector_id: null,

            confidence:
                classification.confidence,

            status:
                classification.status,

            v3_2_source:
                classification.source,

            matched_rules:
                classification.matched_rules
        });
    }


    /*
    =====================================================
    SUMMARY
    =====================================================
    */

    const statusCount = {};
    const industryCount = {};

    for (const r of output) {

        statusCount[r.status] =
            (statusCount[r.status] || 0) + 1;

        if (r.investiq_industry) {

            industryCount[r.investiq_industry] =
                (industryCount[r.investiq_industry] || 0) + 1;
        }
    }


    console.log("\n========== STATUS ==========");

    Object.entries(statusCount)
        .sort((a, b) => b[1] - a[1])
        .forEach(([key, value]) => {

            console.log(
                `${key.padEnd(22)} ${value}`
            );
        });


    console.log("\n========== INDUSTRIES ==========");

    Object.entries(industryCount)
        .sort((a, b) => b[1] - a[1])
        .forEach(([key, value]) => {

            console.log(
                `${key.padEnd(30)} ${value}`
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
                version: "V3.2",

                generated_at:
                    new Date().toISOString(),

                summary: {
                    total: output.length,
                    status: statusCount,
                    industries: industryCount
                },

                database_modified: false,

                results: output
            },
            null,
            2
        )
    );


    console.log("\n========================================");
    console.log("V3.2 CLASSIFICATION COMPLETE");
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