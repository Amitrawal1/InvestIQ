const fs = require("fs");
const path = require("path");

const INPUT_FILE = path.join(
    __dirname,
    "upstox_classification_v3_preview.json"
);

const OUTPUT_FILE = path.join(
    __dirname,
    "upstox_classification_v3_1_preview.json"
);


/*
=========================================================
VALID INVESTIQ INDUSTRIES
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
UPSTOX SECTOR -> INVESTIQ INDUSTRY
PRIMARY SIGNAL
=========================================================
*/

const DIRECT_SECTOR_MAP = {

    // Technology
    "bpo/ites": "IT Services",
    "it - hardware": "Hardware",
    "electronics": "Hardware",
    "semiconductor": "Semiconductor",
    "semiconductors": "Semiconductor",
    "software": "Software",
    "it - software": "Software",

    // Financial
    "banking": "Banking",
    "insurance": "Insurance",
    "nbfc": "NBFC",
    "investment": "Asset Management",
    "asset management": "Asset Management",
    "stock broking": "Other Services",

    // Healthcare
    "pharmaceuticals": "Pharmaceuticals",
    "healthcare services": "Hospitals",
    "healthcare": "Hospitals",
    "diagnostics": "Diagnostics",
    "medical devices": "Medical Devices",

    // Automobile
    "automobile": "Automobiles",
    "automobiles": "Automobiles",
    "auto ancillary": "Auto Components",
    "auto components": "Auto Components",
    "forgings": "Auto Components",
    "bearings": "Auto Components",
    "castings": "Auto Components",
    "tyres & allied": "Auto Components",

    // Energy
    "oil exploration": "Oil & Gas",
    "oil & gas": "Oil & Gas",
    "refineries": "Oil & Gas",
    "power": "Power",
    "power generation & distribution": "Power",
    "solar": "Solar Energy",
    "solar energy": "Solar Energy",
    "renewable energy": "Renewable Energy",

    // Consumer
    "fmcg": "FMCG",
    "consumer durables": "Consumer Durables",
    "food": "Food & Beverages",
    "consumer food": "Food & Beverages",
    "tea/coffee": "Food & Beverages",
    "breweries": "Food & Beverages",
    "sugar": "Food & Beverages",
    "retailing": "Retail",
    "retail": "Retail",
    "e-commerce/app based aggregator": "Retail",
    "jewellery": "Consumer Services",

    // Industrial
    "engineering": "Engineering",
    "construction": "Construction",
    "infrastructure developers & operators": "Infrastructure",
    "infrastructure": "Infrastructure",
    "capital goods": "Capital Goods",
    "capital goods - electrical equipment": "Capital Goods",
    "capital goods-non electrical equipment": "Capital Goods",
    "electric equipment": "Capital Goods",
    "compressors": "Capital Goods",

    // Manufacturing
    "textile": "Manufacturing",
    "textiles": "Manufacturing",
    "plastic products": "Manufacturing",
    "paper": "Manufacturing",
    "packaging": "Manufacturing",
    "rubber products": "Manufacturing",
    "wood products": "Manufacturing",
    "wood products": "Manufacturing",

    // Metals / Chemicals
    "chemicals": "Chemicals",
    "agrochemicals": "Chemicals",
    "agro chemicals": "Chemicals",
    "dyes & pigments": "Chemicals",
    "fertilizers": "Chemicals",
    "paints": "Chemicals",
    "specialty chemicals": "Specialty Chemicals",

    "metal": "Metals & Mining",
    "metals": "Metals & Mining",
    "steel": "Metals & Mining",
    "steel & iron products": "Metals & Mining",
    "non ferrous metals": "Metals & Mining",
    "aluminium products": "Metals & Mining",
    "minerals": "Metals & Mining",

    "cement": "Cement",

    // Building Materials
    "construction materials": "Building Materials",
    "ceramics": "Building Materials",
    "cable": "Building Materials",
    "decoratives": "Building Materials",
    "glass": "Building Materials",

    // Real Estate
    "realty": "Real Estate",
    "real estate": "Real Estate",

    // Services
    "telecommunication": "Telecom",
    "telecom": "Telecom",
    "shipping": "Logistics",
    "logistics": "Logistics",
    "travel services": "Consumer Services",
    "hotel": "Hotels & Hospitality",
    "hotels": "Hotels & Hospitality",
    "film production": "Media & Entertainment",
    "tv broadcasting": "Media & Entertainment",
    "printing and publishing": "Media & Entertainment",
    "education": "Education",
    "educational institutions": "Education"
};


/*
=========================================================
NORMALIZATION
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
PROFILE SIGNALS
=========================================================
*/

const PROFILE_RULES = [

    // Healthcare
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

    // Finance
    {
        industry: "Asset Management",
        keywords: [
            "asset management",
            "mutual fund",
            "mutual funds",
            "wealth management",
            "portfolio management",
            "investment management",
            "alternative investment fund"
        ]
    },

    {
        industry: "NBFC",
        keywords: [
            "lending company",
            "lending activities",
            "non banking financial",
            "housing finance",
            "microfinance"
        ]
    },

    // Technology
    {
        industry: "IT Services",
        keywords: [
            "application development",
            "application maintenance",
            "cloud services",
            "cybersecurity",
            "digital transformation",
            "business process services"
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

    // Automobile
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
            "auto ancillary",
            "automotive parts"
        ]
    },

    // Energy
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
        industry: "Solar Energy",
        keywords: [
            "solar energy",
            "solar power",
            "solar module",
            "solar panels",
            "photovoltaic"
        ]
    },

    {
        industry: "Renewable Energy",
        keywords: [
            "renewable energy",
            "wind energy",
            "wind power",
            "green energy"
        ]
    },

    // Real estate
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

    // Hospitality
    {
        industry: "Hotels & Hospitality",
        keywords: [
            "hotel",
            "hotels",
            "hospitality",
            "resort",
            "resorts"
        ]
    },

    // Media
    {
        industry: "Media & Entertainment",
        keywords: [
            "film production",
            "television",
            "tv broadcasting",
            "broadcasting",
            "digital media",
            "content production"
        ]
    }
];


/*
=========================================================
CLASSIFICATION
=========================================================
*/

function classify(company) {

    const sectorRaw = String(
        company.upstox_sector || ""
    ).trim();

    const sector = normalize(sectorRaw);

    const name = normalize(company.name);
    const profile = normalize(company.company_profile);

    const fullText =
        `${name} ${profile}`;


    /*
    -----------------------------------------------------
    1. EXACT UPSTOX SECTOR
    -----------------------------------------------------
    */

    if (DIRECT_SECTOR_MAP[sector]) {

        const industry =
            DIRECT_SECTOR_MAP[sector];

        /*
        Profile can override only when there is
        strong evidence for a more specific industry.
        */

        let profileOverride = null;

        for (const rule of PROFILE_RULES) {

            for (const keyword of rule.keywords) {

                if (profile.includes(keyword)) {

                    profileOverride = rule.industry;
                    break;
                }
            }

            if (profileOverride) break;
        }


        /*
        Do not override strong exact sectors with
        generic profile matches.

        Examples:
        Cement sector -> Cement
        Sugar sector -> Food & Beverages
        Auto Ancillary -> Auto Components
        */

        if (
            profileOverride &&
            (
                industry === "Other Services" ||
                industry === "Hospitals" ||
                industry === "Manufacturing"
            )
        ) {

            return {
                investiq_industry: profileOverride,
                industry_id: INDUSTRIES[profileOverride],
                confidence: 90,
                status: "HIGH_CONFIDENCE",
                source: "upstox_sector+profile",
                matched_rules: [
                    `sector:${sectorRaw}`,
                    `profile:${profileOverride}`
                ]
            };
        }


        return {
            investiq_industry: industry,
            industry_id: INDUSTRIES[industry],
            confidence: 90,
            status: "HIGH_CONFIDENCE",
            source: "upstox_sector_direct",
            matched_rules: [
                `upstox_sector:${sectorRaw}`
            ]
        };
    }


    /*
    -----------------------------------------------------
    2. PROFILE SEMANTIC RULES
    -----------------------------------------------------
    */

    const profileMatches = [];

    for (const rule of PROFILE_RULES) {

        for (const keyword of rule.keywords) {

            if (fullText.includes(keyword)) {

                profileMatches.push({
                    industry: rule.industry,
                    keyword
                });
            }
        }
    }


    if (profileMatches.length > 0) {

        const counts = {};

        for (const match of profileMatches) {

            counts[match.industry] =
                (counts[match.industry] || 0) + 1;
        }

        const ranked =
            Object.entries(counts)
                .sort((a, b) => b[1] - a[1]);

        const best = ranked[0];

        const second = ranked[1];

        if (
            best &&
            (
                !second ||
                best[1] > second[1]
            )
        ) {

            const industry = best[0];

            return {
                investiq_industry: industry,
                industry_id: INDUSTRIES[industry],
                confidence: 75,
                status: "MEDIUM_CONFIDENCE",
                source: "profile",
                matched_rules:
                    profileMatches
                        .filter(x => x.industry === industry)
                        .map(x => `profile:${x.keyword}`),
                candidates: ranked.map(
                    ([industry, score]) => ({
                        industry,
                        score
                    })
                )
            };
        }
    }


    /*
    -----------------------------------------------------
    3. NAME-BASED FALLBACK
    -----------------------------------------------------
    -----------------------------------------------------
    */

    const NAME_RULES = {

        "hospital": "Hospitals",
        "pharma": "Pharmaceuticals",
        "pharmaceutical": "Pharmaceuticals",

        "cement": "Cement",

        "steel": "Metals & Mining",
        "mining": "Metals & Mining",
        "minerals": "Metals & Mining",

        "chem": "Chemicals",

        "textile": "Manufacturing",
        "textiles": "Manufacturing",

        "engineering": "Engineering",

        "construction": "Construction",

        "infra": "Infrastructure",

        "logistics": "Logistics",

        "hotel": "Hotels & Hospitality",
        "resort": "Hotels & Hospitality",

        "telecom": "Telecom",

        "education": "Education"
    };


    for (const [keyword, industry] of Object.entries(NAME_RULES)) {

        if (name.includes(keyword)) {

            return {
                investiq_industry: industry,
                industry_id: INDUSTRIES[industry],
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
    4. UNMAPPED
    -----------------------------------------------------
    */

    return {
        investiq_industry: null,
        industry_id: null,
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
    console.log("InvestIQ V3.1 Classification");
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
        Never classify API failures without data.
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

                v3_1_source: "none"
            });

            continue;
        }


        const classification =
            classify(company);


        output.push({

            ...company,

            investiq_industry:
                classification.investiq_industry,

            industry_id:
                classification.industry_id,

            /*
            Sector is intentionally left null here.
            Final sector will be derived from industries table.
            */

            sector_id: null,

            confidence:
                classification.confidence,

            status:
                classification.status,

            v3_1_source:
                classification.source,

            matched_rules:
                classification.matched_rules,

            candidates:
                classification.candidates || []
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
                version: "V3.1",
                generated_at: new Date().toISOString(),

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
    console.log("V3.1 CLASSIFICATION COMPLETE");
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