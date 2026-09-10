const fs = require("fs");

/*
=========================================================
InvestIQ V3.4
Targeted cleanup of V3.3 classification
=========================================================
*/

const INPUT =
    "./scripts/upstox_classification_v3_3_preview.json";

const OUTPUT =
    "./scripts/upstox_classification_v3_4_preview.json";


/*
=========================================================
VALID INVESTIQ INDUSTRIES
=========================================================
*/

const VALID_INDUSTRIES = new Set([
    "IT Services",
    "Software",
    "Artificial Intelligence",
    "Semiconductor",
    "Hardware",

    "Solar Energy",
    "Renewable Energy",
    "Power",
    "Oil & Gas",

    "Banking",
    "Insurance",
    "NBFC",
    "Asset Management",

    "Pharmaceuticals",
    "Hospitals",
    "Diagnostics",
    "Medical Devices",

    "Automobiles",
    "Auto Components",
    "Electric Vehicles",
    "Mobility Services",

    "FMCG",
    "Food & Beverages",
    "Retail",
    "Consumer Durables",
    "Consumer Services",

    "Capital Goods",
    "Engineering",
    "Construction",
    "Infrastructure",
    "Manufacturing",

    "Metals & Mining",
    "Cement",
    "Chemicals",
    "Specialty Chemicals",

    "Real Estate",
    "Real Estate Development",
    "Building Materials",

    "Telecom",
    "Logistics",
    "Aviation",
    "Hotels & Hospitality",
    "Media & Entertainment",
    "Education",
    "Other Services"
]);


/*
=========================================================
SECTOR → INVESTIQ INDUSTRY
=========================================================
*/

const SECTOR_MAP = {

    // TECHNOLOGY
    "it software": "Software",
    "software": "Software",

    "it hardware": "Hardware",
    "it-hardware": "Hardware",

    "it networking": "IT Services",
    "bpo ites": "IT Services",
    "bpo/ites": "IT Services",

    "it education": "Education",

    // FINANCIAL
    "stock commodity brokers": "Other Services",
    "stock/ commodity brokers": "Other Services",
    "stock brokers": "Other Services",
    "ratings": "Other Services",

    "housing finance": "NBFC",

    // HEALTHCARE
    "healthcare services": "Hospitals",
    "healthcare": "Hospitals",
    "medical equipment": "Medical Devices",

    // AUTOMOBILE
    "auto ancillary": "Auto Components",
    "auto ancillaries": "Auto Components",
    "tyres allied": "Auto Components",
    "tyres": "Auto Components",
    "castings": "Auto Components",
    "forgings": "Auto Components",
    "bearings": "Auto Components",
    "fasteners": "Auto Components",
    "batteries": "Auto Components",

    "cycles": "Automobiles",

    // CONSUMER
    "air conditioners": "Consumer Durables",
    "consumer durables": "Consumer Durables",

    "household products": "FMCG",
    "tobacco": "FMCG",

    "tea coffee": "Food & Beverages",
    "tea/coffee": "Food & Beverages",
    "breweries": "Food & Beverages",
    "alcoholic beverages": "Food & Beverages",
    "edible oil": "Food & Beverages",
    "aquaculture": "Food & Beverages",

    "footwear": "Consumer Services",
    "watches accessories": "Consumer Services",
    "watches & accessories": "Consumer Services",

    "diamond gems jewellery": "Consumer Services",
    "diamond/gems/jewellery": "Consumer Services",

    "e-commerce": "Retail",
    "ecommerce": "Retail",

    // ENERGY
    "power generation distribution": "Power",
    "power generation & distribution": "Power",

    "oil drill allied": "Oil & Gas",
    "oil exploration": "Oil & Gas",
    "gases fuels": "Oil & Gas",
    "gas transmission": "Oil & Gas",
    "lubricants": "Oil & Gas",

    // INDUSTRIALS
    "aerospace defence": "Capital Goods",
    "aerospace & defence": "Capital Goods",
    "defence": "Capital Goods",

    "capital goods electrical equipment": "Capital Goods",
    "capital goods non electrical equipment": "Capital Goods",

    "capital goods - electrical equipment": "Capital Goods",
    "capital goods- electrical equipment": "Capital Goods",
    "capital goods-non electrical equipment": "Capital Goods",

    "diesel engines": "Capital Goods",
    "ship building": "Capital Goods",
    "railways wagons": "Capital Goods",
    "welding equipment": "Capital Goods",

    // INFRASTRUCTURE
    "infrastructure developers operators": "Infrastructure",
    "infrastructure developers & operators": "Infrastructure",

    "telecom equipment infra": "Infrastructure",
    "telecom equipment & infra": "Infrastructure",

    "transmission towers": "Infrastructure",

    // METALS
    "steel": "Metals & Mining",
    "steel iron products": "Metals & Mining",
    "steel & iron products": "Metals & Mining",

    "non ferrous metals": "Metals & Mining",
    "minerals": "Metals & Mining",
    "mining": "Metals & Mining",
    "mining mineral products": "Metals & Mining",
    "mining & mineral products": "Metals & Mining",

    "aluminium products": "Metals & Mining",
    "metal": "Metals & Mining",

    // CHEMICALS
    "dyes pigments": "Chemicals",
    "dyes & pigments": "Chemicals",

    "agrochemicals": "Chemicals",
    "agro chemicals": "Chemicals",

    "solvent extraction": "Chemicals",
    "carbon black": "Chemicals",

    "fertilizers": "Chemicals",

    // BUILDING MATERIALS
    "refractories": "Building Materials",
    "plywood boards laminates": "Building Materials",
    "ceramics": "Building Materials",
    "ceramic products": "Building Materials",
    "glass": "Building Materials",
    "decoratives": "Building Materials",
    "cable": "Building Materials",

    // MANUFACTURING
    "paper": "Manufacturing",
    "printing publishing": "Manufacturing",
    "printing and publishing": "Manufacturing",
    "stationery": "Manufacturing",
    "leather": "Manufacturing",
    "photographic products": "Manufacturing",

    // REAL ESTATE
    "co-working": "Real Estate",
    "co working": "Real Estate",

    // SERVICES
    "port": "Logistics",
    "courier services": "Logistics",
    "shipping": "Logistics",

    "airlines": "Aviation",

    "telecom service": "Telecom",

    "film production": "Media & Entertainment",
    "tv broadcasting": "Media & Entertainment",
    "entertainment": "Media & Entertainment"
};


/*
=========================================================
NORMALIZATION
=========================================================
*/

function normalize(value) {

    return String(value || "")
        .toLowerCase()
        .replace(/[&/(),.-]/g, " ")
        .replace(/\s+/g, " ")
        .trim();
}


/*
=========================================================
NAME RULES
=========================================================
*/

function classifyFromName(name, symbol) {

    const text =
        `${name || ""} ${symbol || ""}`.toLowerCase();


    // Healthcare
    if (
        /\b(hospital|healthcare|medical|diagnostic|diagnostics)\b/.test(text)
    ) {
        return {
            industry: "Hospitals",
            confidence: 80,
            reason: "company-name healthcare signal"
        };
    }


    // Pharmaceuticals
    if (
        /\b(pharma|pharmaceutical|laboratories|lifesciences|life sciences)\b/.test(text)
    ) {
        return {
            industry: "Pharmaceuticals",
            confidence: 85,
            reason: "company-name pharmaceutical signal"
        };
    }


    // Hotels
    if (
        /\b(hotel|hotels|hospitality|resort)\b/.test(text)
    ) {
        return {
            industry: "Hotels & Hospitality",
            confidence: 85,
            reason: "company-name hospitality signal"
        };
    }


    // Logistics
    if (
        /\b(logistics|courier|cargo|shipping|transport)\b/.test(text)
    ) {
        return {
            industry: "Logistics",
            confidence: 80,
            reason: "company-name logistics signal"
        };
    }


    // Education
    if (
        /\b(education|educational|institute|school|learning|academy)\b/.test(text)
    ) {
        return {
            industry: "Education",
            confidence: 80,
            reason: "company-name education signal"
        };
    }


    // Software / IT
    if (
        /\b(software|technolog|tech solutions|infotech|cyber|systems)\b/.test(text)
    ) {
        return {
            industry: "Software",
            confidence: 75,
            reason: "company-name technology signal"
        };
    }


    // Tyres
    if (
        /\b(tyre|tyres)\b/.test(text)
    ) {
        return {
            industry: "Auto Components",
            confidence: 90,
            reason: "company-name tyre signal"
        };
    }


    // Steel
    if (
        /\b(steel|tubes|pipes|metals|metal)\b/.test(text)
    ) {
        return {
            industry: "Metals & Mining",
            confidence: 75,
            reason: "company-name metals signal"
        };
    }


    // Cement
    if (
        /\b(cement)\b/.test(text)
    ) {
        return {
            industry: "Cement",
            confidence: 90,
            reason: "company-name cement signal"
        };
    }


    // Chemicals
    if (
        /\b(chemical|chemicals|pigment|dyes|fertilizer|fertilizers)\b/.test(text)
    ) {
        return {
            industry: "Chemicals",
            confidence: 75,
            reason: "company-name chemicals signal"
        };
    }


    // Real Estate
    if (
        /\b(realty|real estate|properties|property|developers|development)\b/.test(text)
    ) {
        return {
            industry: "Real Estate",
            confidence: 75,
            reason: "company-name real-estate signal"
        };
    }


    // Construction
    if (
        /\b(construction|infra|infrastructure|engineering)\b/.test(text)
    ) {
        return {
            industry: "Engineering",
            confidence: 70,
            reason: "company-name engineering/infrastructure signal"
        };
    }


    // Food
    if (
        /\b(food|foods|beverages|beverage|sugar|tea|coffee|brewery|breweries)\b/.test(text)
    ) {
        return {
            industry: "Food & Beverages",
            confidence: 75,
            reason: "company-name food signal"
        };
    }


    return null;
}


/*
=========================================================
PROFILE RULES
=========================================================
*/

function classifyFromProfile(profile) {

    if (!profile) {
        return null;
    }


    const text =
        String(profile).toLowerCase();


    // Asset Management
    if (
        /\b(asset management|mutual fund|mutual funds|wealth management|portfolio management)\b/.test(text)
    ) {
        return {
            industry: "Asset Management",
            confidence: 90,
            reason: "company profile asset-management signal"
        };
    }


    // NBFC
    if (
        /\b(nbfc|lending|microfinance|housing finance|vehicle finance|consumer finance)\b/.test(text)
    ) {
        return {
            industry: "NBFC",
            confidence: 90,
            reason: "company profile lending signal"
        };
    }


    // Banking
    if (
        /\bbank\b/.test(text)
    ) {
        return {
            industry: "Banking",
            confidence: 90,
            reason: "company profile banking signal"
        };
    }


    // Insurance
    if (
        /\b(insurance|insurer)\b/.test(text)
    ) {
        return {
            industry: "Insurance",
            confidence: 90,
            reason: "company profile insurance signal"
        };
    }


    // Software
    if (
        /\b(software|saas|software services|technology services|it services)\b/.test(text)
    ) {
        return {
            industry: "Software",
            confidence: 85,
            reason: "company profile software signal"
        };
    }


    // AI
    if (
        /\b(artificial intelligence|machine learning|generative ai|ai platform)\b/.test(text)
    ) {
        return {
            industry: "Artificial Intelligence",
            confidence: 90,
            reason: "company profile AI signal"
        };
    }


    // Pharmaceuticals
    if (
        /\b(pharmaceutical|pharmaceuticals|drug|drugs|formulation|api|biotech)\b/.test(text)
    ) {
        return {
            industry: "Pharmaceuticals",
            confidence: 85,
            reason: "company profile pharmaceutical signal"
        };
    }


    // Manufacturing
    if (
        /\b(manufactur|production|factory|industrial products)\b/.test(text)
    ) {
        return {
            industry: "Manufacturing",
            confidence: 70,
            reason: "company profile manufacturing signal"
        };
    }


    return null;
}


/*
=========================================================
SECTOR MAPPING
=========================================================
*/

function classifyFromSector(upstoxSector) {

    const normalized =
        normalize(upstoxSector);

    if (!normalized) {
        return null;
    }


    const industry =
        SECTOR_MAP[normalized];


    if (!industry) {
        return null;
    }


    return {
        industry,
        confidence: 90,
        reason: `Upstox sector mapped: ${upstoxSector}`
    };
}


/*
=========================================================
MAIN CLASSIFICATION
=========================================================
*/

function classifyCompany(company) {

    /*
    -----------------------------------------------------
    Already high confidence
    -----------------------------------------------------
    */

    if (company.status === "HIGH_CONFIDENCE") {
        return company;
    }


    /*
    -----------------------------------------------------
    API failed
    -----------------------------------------------------
    */

    if (company.status === "UPSTOX_FAILED") {
        return company;
    }


    let candidates = [];


    /*
    -----------------------------------------------------
    PROFILE FIRST
    -----------------------------------------------------
    */

    const profileResult =
        classifyFromProfile(company.company_profile);

    if (profileResult) {
        candidates.push(profileResult);
    }


    /*
    -----------------------------------------------------
    SECTOR
    -----------------------------------------------------
    */

    const sectorResult =
        classifyFromSector(company.upstox_sector);

    if (sectorResult) {
        candidates.push(sectorResult);
    }


    /*
    -----------------------------------------------------
    NAME
    -----------------------------------------------------
    */

    const nameResult =
        classifyFromName(
            company.name,
            company.symbol
        );

    if (nameResult) {
        candidates.push(nameResult);
    }


    /*
    -----------------------------------------------------
    NO RESULT
    -----------------------------------------------------
    */

    if (!candidates.length) {

        return {
            ...company,
            investiq_industry: null,
            industry_id: null,
            sector_id: null,
            confidence: 0,
            status: "UNMAPPED",
            matched_rules: []
        };
    }


    /*
    -----------------------------------------------------
    GROUP CANDIDATES
    -----------------------------------------------------
    */

    const grouped = {};


    for (const candidate of candidates) {

        if (!VALID_INDUSTRIES.has(candidate.industry)) {
            continue;
        }


        if (!grouped[candidate.industry]) {

            grouped[candidate.industry] = {
                industry: candidate.industry,
                confidence: candidate.confidence,
                reasons: [candidate.reason],
                matches: 1
            };

        } else {

            grouped[candidate.industry].matches++;

            grouped[candidate.industry].confidence +=
                candidate.confidence * 0.35;

            grouped[candidate.industry].reasons.push(
                candidate.reason
            );
        }
    }


    const ranked =
        Object.values(grouped)
            .sort((a, b) => {

                if (b.matches !== a.matches) {
                    return b.matches - a.matches;
                }

                return b.confidence - a.confidence;
            });


    if (!ranked.length) {

        return {
            ...company,
            investiq_industry: null,
            industry_id: null,
            sector_id: null,
            confidence: 0,
            status: "UNMAPPED",
            matched_rules: []
        };
    }


    const best = ranked[0];


    /*
    -----------------------------------------------------
    CONFIDENCE
    -----------------------------------------------------
    */

    let confidence =
        Math.min(100, Math.round(best.confidence));


    let status;


    if (best.matches >= 2 && confidence >= 85) {

        status = "HIGH_CONFIDENCE";

    } else if (confidence >= 80) {

        status = "HIGH_CONFIDENCE";

    } else if (confidence >= 65) {

        status = "MEDIUM_CONFIDENCE";

    } else {

        status = "LOW_CONFIDENCE";
    }


    return {
        ...company,

        investiq_industry: best.industry,

        industry_id: null,
        sector_id: null,

        confidence,

        status,

        matched_rules: ranked.slice(0, 3).map(x => ({
            industry: x.industry,
            confidence: Math.round(x.confidence),
            matches: x.matches,
            reasons: x.reasons
        }))
    };
}


/*
=========================================================
LOAD
=========================================================
*/

console.log("\n========================================");
console.log("InvestIQ V3.4 Classification");
console.log("========================================");


const data =
    JSON.parse(
        fs.readFileSync(INPUT, "utf8")
    );


const results =
    data.results.map(classifyCompany);


/*
=========================================================
SUMMARY
=========================================================
*/

const statusCount = {};

const industryCount = {};


for (const r of results) {

    statusCount[r.status] =
        (statusCount[r.status] || 0) + 1;


    const industry =
        r.investiq_industry || "UNMAPPED";


    industryCount[industry] =
        (industryCount[industry] || 0) + 1;
}


console.log("\n========== STATUS ==========");

for (
    const [status, count]
    of Object.entries(statusCount)
) {
    console.log(
        `${status.padEnd(22)} ${count}`
    );
}


console.log("\n========== INDUSTRIES ==========");

Object.entries(industryCount)
    .sort((a, b) => b[1] - a[1])
    .forEach(([industry, count]) => {

        console.log(
            `${industry.padEnd(30)} ${count}`
        );

    });


/*
=========================================================
SAVE
=========================================================
*/

const output = {
    generated_at: new Date().toISOString(),

    source:
        "upstox_classification_v3_3_preview.json",

    version: "V3.4",

    total:
        results.length,

    status_summary:
        statusCount,

    industry_summary:
        industryCount,

    results
};


fs.writeFileSync(
    OUTPUT,
    JSON.stringify(output, null, 2)
);


console.log("\n========================================");
console.log("V3.4 CLASSIFICATION COMPLETE");
console.log("========================================");

console.log("\nPreview saved:");
console.log(OUTPUT);

console.log("\nDATABASE WAS NOT MODIFIED");

console.log("========================================\n");