const fs = require("fs");
const path = require("path");

const INPUT = path.join(
    __dirname,
    "upstox_classification_v3_2_preview.json"
);

const OUTPUT = path.join(
    __dirname,
    "upstox_classification_v3_3_preview.json"
);

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

function norm(v) {
    return String(v || "")
        .toLowerCase()
        .replace(/&/g, " and ")
        .replace(/[^a-z0-9]+/g, " ")
        .replace(/\s+/g, " ")
        .trim();
}


/*
=========================================================
EXACT REMAINING UPSTOX SECTORS
=========================================================
*/

const MAP = {

    // Technology
    "it software": "Software",
    "it hardware": "Hardware",
    "it networking": "IT Services",
    "bpo ites": "IT Services",
    "it education": "Education",

    // Finance
    "finance": "Other Services",
    "financial services": "Other Services",
    "stock commodity brokers": "Other Services",
    "ratings": "Other Services",
    "housing finance": "NBFC",

    // Healthcare
    "medical equipment": "Medical Devices",
    "healthcare": "Hospitals",
    "healthcare services": "Hospitals",

    // Automobile
    "tyres allied": "Auto Components",
    "tyres": "Auto Components",
    "auto ancillaries": "Auto Components",
    "castings forgings fastners": "Auto Components",
    "fasteners": "Auto Components",
    "bearings": "Auto Components",
    "batteries": "Auto Components",
    "cycles": "Automobiles",

    // Energy
    "oil drill allied": "Oil & Gas",
    "gases fuels": "Oil & Gas",
    "gas transmission": "Oil & Gas",
    "petrochemicals": "Oil & Gas",
    "lubricants": "Oil & Gas",
    "power generation distribution": "Power",

    // Consumer
    "air conditioners": "Consumer Durables",
    "consumer durables": "Consumer Durables",
    "household products": "FMCG",
    "tobacco": "FMCG",
    "tobacco products": "FMCG",
    "tea coffee": "Food & Beverages",
    "alcoholic beverages": "Food & Beverages",
    "edible oil": "Food & Beverages",
    "aquaculture": "Food & Beverages",
    "quick service restaurant": "Consumer Services",
    "footwear": "Consumer Services",
    "watches accessories": "Consumer Services",
    "diamond gems and jewellery": "Consumer Services",
    "jewellery": "Consumer Services",

    "e commerce": "Retail",
    "e commerce app based aggregator": "Retail",

    // Industrial
    "aerospace defence": "Capital Goods",
    "defence": "Capital Goods",
    "welding equipment": "Capital Goods",
    "capital goods electrical equipment": "Capital Goods",
    "capital goods non electrical equipment": "Capital Goods",
    "diesel engines": "Capital Goods",
    "ship building": "Capital Goods",
    "railways wagons": "Capital Goods",
    "telecom equipment infra services": "Infrastructure",
    "transmission towers": "Infrastructure",

    // Materials / manufacturing
    "steel iron products": "Metals & Mining",
    "castings": "Metals & Mining",
    "steel": "Metals & Mining",
    "metal": "Metals & Mining",
    "mining mineral products": "Metals & Mining",
    "non ferrous metals": "Metals & Mining",
    "aluminium products": "Metals & Mining",

    "dyes pigments": "Chemicals",
    "solvent extraction": "Chemicals",
    "carbon black": "Chemicals",

    "refractories": "Manufacturing",
    "photographic products": "Manufacturing",
    "stationery": "Manufacturing",
    "leather": "Manufacturing",

    // Building materials
    "plywood boards laminates": "Building Materials",
    "ceramics": "Building Materials",
    "glass": "Building Materials",
    "cable": "Building Materials",
    "decoratives": "Building Materials",

    // Real estate
    "co working": "Real Estate",

    // Services
    "port": "Logistics",
    "courier services": "Logistics",
    "shipping": "Logistics",
    "airlines": "Aviation",
    "telecom service": "Telecom",
    "entertainment": "Media & Entertainment",
    "printing publishing": "Media & Entertainment"
};


/*
=========================================================
PROFILE-BASED DISAMBIGUATION
=========================================================
*/

function profileMap(profile) {

    const p = norm(profile);

    const rules = [

        ["mutual fund", "Asset Management"],
        ["asset management", "Asset Management"],
        ["wealth management", "Asset Management"],
        ["portfolio management", "Asset Management"],

        ["lending", "NBFC"],
        ["housing finance", "NBFC"],
        ["microfinance", "NBFC"],

        ["diagnostic", "Diagnostics"],
        ["pathology", "Diagnostics"],

        ["medical device", "Medical Devices"],
        ["medical equipment", "Medical Devices"],

        ["hospital", "Hospitals"],

        ["electric vehicle", "Electric Vehicles"],

        ["auto component", "Auto Components"],
        ["automotive component", "Auto Components"],

        ["oil exploration", "Oil & Gas"],
        ["oil and gas", "Oil & Gas"],
        ["refinery", "Oil & Gas"],

        ["solar", "Solar Energy"],
        ["renewable energy", "Renewable Energy"],

        ["power generation", "Power"],

        ["real estate development", "Real Estate Development"],
        ["property developer", "Real Estate Development"],

        ["software development", "Software"],
        ["software products", "Software"],

        ["application development", "IT Services"],
        ["cloud services", "IT Services"],
        ["cybersecurity", "IT Services"],

        ["hotel", "Hotels & Hospitality"],
        ["hospitality", "Hotels & Hospitality"],

        ["film production", "Media & Entertainment"],
        ["broadcasting", "Media & Entertainment"]
    ];

    for (const [keyword, industry] of rules) {

        if (p.includes(keyword)) {
            return industry;
        }
    }

    return null;
}


/*
=========================================================
BROAD SECTORS
=========================================================
*/

function broadSector(company) {

    const sector = norm(company.upstox_sector);
    const name = norm(company.name);
    const profile = norm(company.company_profile);

    /*
    Diversified / Miscellaneous / DVR
    */

    if (
        sector === "diversified" ||
        sector === "miscellaneous" ||
        sector === "dvr"
    ) {

        const p = profileMap(profile);

        if (p) return p;

        if (name.includes("hotel"))
            return "Hotels & Hospitality";

        if (
            name.includes("pharma") ||
            name.includes("pharmaceutical")
        )
            return "Pharmaceuticals";

        if (name.includes("software"))
            return "Software";

        if (
            name.includes("infra") ||
            name.includes("infrastructure")
        )
            return "Infrastructure";

        if (name.includes("steel"))
            return "Metals & Mining";

        if (
            name.includes("chemical") ||
            name.includes("chem")
        )
            return "Chemicals";

        return null;
    }

    /*
    Agriculture:
    only obvious food/agri-product cases.
    */

    if (sector === "agriculture") {

        if (
            name.includes("seed") ||
            name.includes("seeds")
        ) {
            return "Other Services";
        }

        if (
            name.includes("food") ||
            name.includes("beverage") ||
            name.includes("oil")
        ) {
            return "Food & Beverages";
        }

        return "Other Services";
    }

    return null;
}


/*
=========================================================
CLASSIFY REMAINING RECORD
=========================================================
*/

function classify(company) {

    const sector = norm(company.upstox_sector);

    /*
    1. Exact sector
    */

    if (MAP[sector]) {

        return {
            industry: MAP[sector],
            confidence:
                MAP[sector] === "Other Services"
                    ? 65
                    : 92,
            status:
                MAP[sector] === "Other Services"
                    ? "LOW_CONFIDENCE"
                    : "HIGH_CONFIDENCE",
            source: "v3.3_exact_sector"
        };
    }


    /*
    2. Broad sector
    */

    const broad = broadSector(company);

    if (broad) {

        return {
            industry: broad,
            confidence:
                broad === "Other Services"
                    ? 65
                    : 80,
            status:
                broad === "Other Services"
                    ? "LOW_CONFIDENCE"
                    : "MEDIUM_CONFIDENCE",
            source: "v3.3_broad_sector"
        };
    }


    /*
    3. Profile
    */

    const profile = profileMap(
        company.company_profile
    );

    if (profile) {

        return {
            industry: profile,
            confidence: 78,
            status: "MEDIUM_CONFIDENCE",
            source: "v3.3_profile"
        };
    }


    return {
        industry: null,
        confidence: 0,
        status: "UNMAPPED",
        source: "none"
    };
}


/*
=========================================================
MAIN
=========================================================
*/

function main() {

    const data = JSON.parse(
        fs.readFileSync(INPUT, "utf8")
    );

    const results = data.results || data;

    const output = [];

    for (const company of results) {

        /*
        Preserve API failures.
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
                v3_3_source: "none"
            });

            continue;
        }


        /*
        Preserve HIGH confidence.
        */

        if (
            company.status === "HIGH_CONFIDENCE" &&
            company.investiq_industry
        ) {

            output.push({
                ...company,
                sector_id: null,
                v3_3_source:
                    company.v3_2_source ||
                    "v3.2_preserved"
            });

            continue;
        }


        const c = classify(company);

        output.push({

            ...company,

            investiq_industry:
                c.industry,

            industry_id:
                c.industry
                    ? INDUSTRIES[c.industry]
                    : null,

            sector_id: null,

            confidence:
                c.confidence,

            status:
                c.status,

            v3_3_source:
                c.source
        });
    }


    /*
    Summary
    */

    const status = {};
    const industries = {};

    for (const r of output) {

        status[r.status] =
            (status[r.status] || 0) + 1;

        if (r.investiq_industry) {

            industries[r.investiq_industry] =
                (industries[r.investiq_industry] || 0) + 1;
        }
    }


    console.log("\n========================================");
    console.log("InvestIQ V3.3 Classification");
    console.log("========================================");

    console.log(
        `Companies loaded: ${output.length}`
    );

    console.log("\n========== STATUS ==========");

    Object.entries(status)
        .sort((a,b)=>b[1]-a[1])
        .forEach(([k,v])=>{
            console.log(
                `${k.padEnd(22)} ${v}`
            );
        });

    console.log("\n========== INDUSTRIES ==========");

    Object.entries(industries)
        .sort((a,b)=>b[1]-a[1])
        .forEach(([k,v])=>{
            console.log(
                `${k.padEnd(30)} ${v}`
            );
        });


    fs.writeFileSync(
        OUTPUT,
        JSON.stringify(
            {
                version: "V3.3",
                generated_at:
                    new Date().toISOString(),

                summary: {
                    total: output.length,
                    status,
                    industries
                },

                database_modified: false,

                results: output
            },
            null,
            2
        )
    );


    console.log("\n========================================");
    console.log("V3.3 CLASSIFICATION COMPLETE");
    console.log("========================================");

    console.log(
        `Preview saved:\n${OUTPUT}`
    );

    console.log(
        "\nDATABASE WAS NOT MODIFIED"
    );

    console.log("========================================\n");
}

main();