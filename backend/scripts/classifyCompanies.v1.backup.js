require("dotenv").config();

const axios = require("axios");
const db = require("../config/db");

const sleep = (ms) => new Promise(resolve => setTimeout(resolve, ms));

/*
=========================================================
CONFIG
=========================================================
*/

const DRY_RUN = true;

// NSE API ko unnecessarily fast hit nahi karna
const REQUEST_DELAY = 350;

// Retry configuration
const MAX_RETRIES = 3;


/*
=========================================================
INVESTIQ 10 SECTORS
=========================================================
*/

const SECTORS = {
    TECHNOLOGY: "Technology",
    ENERGY: "Energy",
    FINANCIAL: "Financial Services",
    HEALTHCARE: "Healthcare & Pharmaceuticals",
    AUTOMOBILE: "Automobile & Mobility",
    CONSUMER: "Consumer & FMCG",
    INDUSTRIALS: "Industrials & Infrastructure",
    METALS: "Metals, Mining & Chemicals",
    REAL_ESTATE: "Real Estate & Construction",
    SERVICES: "Services & Others"
};


/*
=========================================================
INVESTIQ 45 INDUSTRIES
=========================================================
*/

const INDUSTRIES = {

    // Technology
    "IT Services": SECTORS.TECHNOLOGY,
    "Software": SECTORS.TECHNOLOGY,
    "Artificial Intelligence": SECTORS.TECHNOLOGY,
    "Semiconductor": SECTORS.TECHNOLOGY,
    "Hardware": SECTORS.TECHNOLOGY,

    // Energy
    "Solar Energy": SECTORS.ENERGY,
    "Renewable Energy": SECTORS.ENERGY,
    "Power": SECTORS.ENERGY,
    "Oil & Gas": SECTORS.ENERGY,

    // Financial
    "Banking": SECTORS.FINANCIAL,
    "Insurance": SECTORS.FINANCIAL,
    "NBFC": SECTORS.FINANCIAL,
    "Asset Management": SECTORS.FINANCIAL,

    // Healthcare
    "Pharmaceuticals": SECTORS.HEALTHCARE,
    "Hospitals": SECTORS.HEALTHCARE,
    "Diagnostics": SECTORS.HEALTHCARE,
    "Medical Devices": SECTORS.HEALTHCARE,

    // Automobile
    "Automobiles": SECTORS.AUTOMOBILE,
    "Auto Components": SECTORS.AUTOMOBILE,
    "Electric Vehicles": SECTORS.AUTOMOBILE,
    "Mobility Services": SECTORS.AUTOMOBILE,

    // Consumer
    "FMCG": SECTORS.CONSUMER,
    "Food & Beverages": SECTORS.CONSUMER,
    "Retail": SECTORS.CONSUMER,
    "Consumer Durables": SECTORS.CONSUMER,
    "Consumer Services": SECTORS.CONSUMER,

    // Industrials
    "Capital Goods": SECTORS.INDUSTRIALS,
    "Engineering": SECTORS.INDUSTRIALS,
    "Construction": SECTORS.INDUSTRIALS,
    "Infrastructure": SECTORS.INDUSTRIALS,
    "Manufacturing": SECTORS.INDUSTRIALS,

    // Metals / Mining / Chemicals
    "Metals & Mining": SECTORS.METALS,
    "Cement": SECTORS.METALS,
    "Chemicals": SECTORS.METALS,
    "Specialty Chemicals": SECTORS.METALS,

    // Real Estate
    "Real Estate": SECTORS.REAL_ESTATE,
    "Real Estate Development": SECTORS.REAL_ESTATE,
    "Building Materials": SECTORS.REAL_ESTATE,

    // Services
    "Telecom": SECTORS.SERVICES,
    "Logistics": SECTORS.SERVICES,
    "Aviation": SECTORS.SERVICES,
    "Hotels & Hospitality": SECTORS.SERVICES,
    "Media & Entertainment": SECTORS.SERVICES,
    "Education": SECTORS.SERVICES,
    "Other Services": SECTORS.SERVICES
};


/*
=========================================================
NORMALIZATION
=========================================================
*/

function normalize(value) {

    if (!value) return "";

    return value
        .toString()
        .toLowerCase()
        .replace(/&/g, "and")
        .replace(/[^a-z0-9\s]/g, " ")
        .replace(/\s+/g, " ")
        .trim();
}


/*
=========================================================
NSE SESSION
=========================================================
*/

const nse = axios.create({
    baseURL: "https://www.nseindia.com",
    timeout: 20000,

    headers: {
        "User-Agent":
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) " +
            "AppleWebKit/537.36 " +
            "(KHTML, like Gecko) Chrome/139.0 Safari/537.36",

        "Accept":
            "application/json,text/plain,*/*",

        "Accept-Language":
            "en-US,en;q=0.9",

        "Referer":
            "https://www.nseindia.com/"
    }
});


/*
=========================================================
NSE SESSION INITIALIZATION
=========================================================
*/

async function initializeNSE() {

    console.log("\nInitializing NSE session...");

    try {

        await nse.get("/");

        console.log("NSE session initialized.");

    } catch (error) {

        console.error(
            "NSE session initialization failed:",
            error.message
        );

        throw error;
    }
}


/*
=========================================================
FETCH NSE COMPANY INFORMATION
=========================================================
*/

async function fetchNSECompany(symbol) {

    for (let attempt = 1; attempt <= MAX_RETRIES; attempt++) {

        try {

            const response = await nse.get(
                "/api/quote-equity",
                {
                    params: {
                        symbol
                    }
                }
            );

            return response.data;

        } catch (error) {

            console.log(
                `NSE request failed for ${symbol} ` +
                `(attempt ${attempt}/${MAX_RETRIES})`
            );

            if (attempt < MAX_RETRIES) {

                await sleep(attempt * 2000);

            } else {

                console.log(
                    `Giving up on ${symbol}`
                );
            }
        }
    }

    return null;
}


/*
=========================================================
NSE → INVESTIQ MAPPING
=========================================================
*/

function classifyFromNSE(nseData) {

    if (!nseData) {
        return null;
    }

    const industryInfo =
        nseData.industryInfo || {};

    const macro =
        normalize(industryInfo.macro);

    const sector =
        normalize(industryInfo.sector);

    const industry =
        normalize(industryInfo.industry);

    const basicIndustry =
        normalize(industryInfo.basicIndustry);


    /*
    =====================================================
    TECHNOLOGY
    =====================================================
    */

    if (
        industry.includes("it") ||
        industry.includes("information technology") ||
        industry.includes("software") ||
        basicIndustry.includes("software") ||
        basicIndustry.includes("it services")
    ) {

        return {
            industry: "IT Services",
            sector: SECTORS.TECHNOLOGY
        };
    }


    if (
        industry.includes("semiconductor") ||
        basicIndustry.includes("semiconductor")
    ) {

        return {
            industry: "Semiconductor",
            sector: SECTORS.TECHNOLOGY
        };
    }


    if (
        industry.includes("computer") ||
        industry.includes("technology hardware") ||
        basicIndustry.includes("computer") ||
        basicIndustry.includes("hardware")
    ) {

        return {
            industry: "Hardware",
            sector: SECTORS.TECHNOLOGY
        };
    }


    /*
    =====================================================
    FINANCIAL SERVICES
    =====================================================
    */

    if (
        industry.includes("bank")
        || sector.includes("bank")
        || basicIndustry.includes("bank")
    ) {

        return {
            industry: "Banking",
            sector: SECTORS.FINANCIAL
        };
    }


    if (
        industry.includes("insurance")
        || basicIndustry.includes("insurance")
    ) {

        return {
            industry: "Insurance",
            sector: SECTORS.FINANCIAL
        };
    }


    if (
        industry.includes("financial services")
        || industry.includes("finance")
        || industry.includes("nbfc")
        || basicIndustry.includes("housing finance")
        || basicIndustry.includes("non banking")
    ) {

        return {
            industry: "NBFC",
            sector: SECTORS.FINANCIAL
        };
    }


    if (
        industry.includes("capital markets")
        || industry.includes("asset management")
        || basicIndustry.includes("asset management")
        || basicIndustry.includes("mutual fund")
    ) {

        return {
            industry: "Asset Management",
            sector: SECTORS.FINANCIAL
        };
    }


    /*
    =====================================================
    HEALTHCARE
    =====================================================
    */

    if (
        industry.includes("pharma")
        || industry.includes("pharmaceutical")
        || basicIndustry.includes("pharmaceutical")
        || basicIndustry.includes("pharma")
    ) {

        return {
            industry: "Pharmaceuticals",
            sector: SECTORS.HEALTHCARE
        };
    }


    if (
        industry.includes("hospital")
        || basicIndustry.includes("hospital")
        || basicIndustry.includes("healthcare service")
    ) {

        return {
            industry: "Hospitals",
            sector: SECTORS.HEALTHCARE
        };
    }


    if (
        industry.includes("diagnostic")
        || basicIndustry.includes("diagnostic")
    ) {

        return {
            industry: "Diagnostics",
            sector: SECTORS.HEALTHCARE
        };
    }


    if (
        industry.includes("medical equipment")
        || industry.includes("medical devices")
        || basicIndustry.includes("medical equipment")
        || basicIndustry.includes("medical device")
    ) {

        return {
            industry: "Medical Devices",
            sector: SECTORS.HEALTHCARE
        };
    }


    /*
    =====================================================
    AUTOMOBILE
    =====================================================
    */

    if (
        industry.includes("automobile")
        || industry.includes("auto and auto components")
        || basicIndustry.includes("passenger cars")
        || basicIndustry.includes("two wheelers")
        || basicIndustry.includes("three wheelers")
        || basicIndustry.includes("commercial vehicles")
    ) {

        return {
            industry: "Automobiles",
            sector: SECTORS.AUTOMOBILE
        };
    }


    if (
        industry.includes("auto components")
        || industry.includes("auto parts")
        || basicIndustry.includes("auto components")
        || basicIndustry.includes("auto parts")
    ) {

        return {
            industry: "Auto Components",
            sector: SECTORS.AUTOMOBILE
        };
    }


    /*
    =====================================================
    ENERGY
    =====================================================
    */

    if (
        industry.includes("oil")
        || industry.includes("gas")
        || industry.includes("petroleum")
        || basicIndustry.includes("oil")
        || basicIndustry.includes("refineries")
        || basicIndustry.includes("oil exploration")
    ) {

        return {
            industry: "Oil & Gas",
            sector: SECTORS.ENERGY
        };
    }


    if (
        industry.includes("power")
        || basicIndustry.includes("power generation")
        || basicIndustry.includes("power transmission")
        || basicIndustry.includes("power distribution")
    ) {

        return {
            industry: "Power",
            sector: SECTORS.ENERGY
        };
    }


    if (
        industry.includes("renewable")
        || basicIndustry.includes("renewable")
    ) {

        return {
            industry: "Renewable Energy",
            sector: SECTORS.ENERGY
        };
    }


    if (
        industry.includes("solar")
        || basicIndustry.includes("solar")
    ) {

        return {
            industry: "Solar Energy",
            sector: SECTORS.ENERGY
        };
    }


    /*
    =====================================================
    METALS / MINING
    =====================================================
    */

    if (
        industry.includes("metals")
        || industry.includes("mining")
        || industry.includes("ferrous")
        || industry.includes("non ferrous")
        || basicIndustry.includes("iron")
        || basicIndustry.includes("steel")
        || basicIndustry.includes("aluminium")
        || basicIndustry.includes("copper")
        || basicIndustry.includes("zinc")
        || basicIndustry.includes("mining")
    ) {

        return {
            industry: "Metals & Mining",
            sector: SECTORS.METALS
        };
    }


    if (
        industry.includes("cement")
        || basicIndustry.includes("cement")
    ) {

        return {
            industry: "Cement",
            sector: SECTORS.METALS
        };
    }


    if (
        industry.includes("chemical")
        || industry.includes("chemicals")
        || basicIndustry.includes("chemical")
        || basicIndustry.includes("chemicals")
    ) {

        return {
            industry: "Chemicals",
            sector: SECTORS.METALS
        };
    }


    /*
    =====================================================
    REAL ESTATE
    =====================================================
    */

    if (
        industry.includes("realty")
        || industry.includes("real estate")
        || sector.includes("realty")
        || basicIndustry.includes("real estate")
        || basicIndustry.includes("residential")
        || basicIndustry.includes("commercial projects")
    ) {

        return {
            industry: "Real Estate",
            sector: SECTORS.REAL_ESTATE
        };
    }


    if (
        industry.includes("construction materials")
        || basicIndustry.includes("building materials")
        || basicIndustry.includes("construction materials")
    ) {

        return {
            industry: "Building Materials",
            sector: SECTORS.REAL_ESTATE
        };
    }


    /*
    =====================================================
    INDUSTRIALS
    =====================================================
    */

    if (
        industry.includes("construction")
        || basicIndustry.includes("construction")
    ) {

        return {
            industry: "Construction",
            sector: SECTORS.INDUSTRIALS
        };
    }


    if (
        industry.includes("engineering")
        || basicIndustry.includes("engineering")
    ) {

        return {
            industry: "Engineering",
            sector: SECTORS.INDUSTRIALS
        };
    }


    if (
        industry.includes("capital goods")
        || basicIndustry.includes("capital goods")
    ) {

        return {
            industry: "Capital Goods",
            sector: SECTORS.INDUSTRIALS
        };
    }


    if (
        industry.includes("infrastructure")
        || basicIndustry.includes("infrastructure")
    ) {

        return {
            industry: "Infrastructure",
            sector: SECTORS.INDUSTRIALS
        };
    }


    /*
    =====================================================
    CONSUMER
    =====================================================
    */

    if (
        industry.includes("fmcg")
        || industry.includes("consumer")
        || basicIndustry.includes("consumer")
        || basicIndustry.includes("personal care")
    ) {

        return {
            industry: "FMCG",
            sector: SECTORS.CONSUMER
        };
    }


    if (
        industry.includes("food")
        || industry.includes("beverage")
        || basicIndustry.includes("food")
        || basicIndustry.includes("beverage")
    ) {

        return {
            industry: "Food & Beverages",
            sector: SECTORS.CONSUMER
        };
    }


    if (
        industry.includes("retail")
        || basicIndustry.includes("retail")
    ) {

        return {
            industry: "Retail",
            sector: SECTORS.CONSUMER
        };
    }


    if (
        industry.includes("consumer durables")
        || basicIndustry.includes("consumer durables")
    ) {

        return {
            industry: "Consumer Durables",
            sector: SECTORS.CONSUMER
        };
    }


    /*
    =====================================================
    SERVICES
    =====================================================
    */

    if (
        industry.includes("telecom")
        || basicIndustry.includes("telecom")
    ) {

        return {
            industry: "Telecom",
            sector: SECTORS.SERVICES
        };
    }


    if (
        industry.includes("logistics")
        || basicIndustry.includes("logistics")
        || basicIndustry.includes("transportation")
    ) {

        return {
            industry: "Logistics",
            sector: SECTORS.SERVICES
        };
    }


    if (
        industry.includes("hotel")
        || industry.includes("hospitality")
        || basicIndustry.includes("hotel")
        || basicIndustry.includes("hospitality")
    ) {

        return {
            industry: "Hotels & Hospitality",
            sector: SECTORS.SERVICES
        };
    }


    if (
        industry.includes("media")
        || industry.includes("entertainment")
        || basicIndustry.includes("media")
        || basicIndustry.includes("entertainment")
    ) {

        return {
            industry: "Media & Entertainment",
            sector: SECTORS.SERVICES
        };
    }


    if (
        industry.includes("education")
        || basicIndustry.includes("education")
    ) {

        return {
            industry: "Education",
            sector: SECTORS.SERVICES
        };
    }


    /*
    =====================================================
    FALLBACK
    =====================================================
    */

    return {
        industry: "Other Services",
        sector: SECTORS.SERVICES
    };
}


/*
=========================================================
MAIN
=========================================================
*/

async function classifyCompanies() {

    console.log("\n========================================");
    console.log("InvestIQ NSE Classification");
    console.log("========================================");

    await initializeNSE();

    const [companies] = await db.query(`
        SELECT
            id,
            name,
            symbol,
            isin
        FROM companies
        WHERE isin IS NOT NULL
          AND isin != ''
        ORDER BY id
    `);

    console.log(
        `Companies to classify: ${companies.length}`
    );

    const results = [];

    let processed = 0;
    let failed = 0;


    /*
    =====================================================
    PROCESS COMPANIES
    =====================================================
    */

    for (const company of companies) {

        processed++;

        console.log(
            `[${processed}/${companies.length}] ` +
            `${company.symbol} - ${company.name}`
        );


        const nseData =
            await fetchNSECompany(company.symbol);


        if (!nseData) {

            failed++;

            results.push({
                ...company,
                nse_macro: null,
                nse_sector: null,
                nse_industry: null,
                nse_basic_industry: null,
                investiq_industry: "Other Services",
                investiq_sector: SECTORS.SERVICES,
                source: "fallback"
            });

            continue;
        }


        const industryInfo =
            nseData.industryInfo || {};


        const classification =
            classifyFromNSE(nseData);


        results.push({

            ...company,

            nse_macro:
                industryInfo.macro || null,

            nse_sector:
                industryInfo.sector || null,

            nse_industry:
                industryInfo.industry || null,

            nse_basic_industry:
                industryInfo.basicIndustry || null,

            investiq_industry:
                classification.industry,

            investiq_sector:
                classification.sector,

            source: "NSE"
        });


        await sleep(REQUEST_DELAY);
    }


    /*
    =====================================================
    SUMMARY
    =====================================================
    */

    console.log("\n========================================");
    console.log("CLASSIFICATION COMPLETE");
    console.log("========================================");

    console.log(
        "Total companies :", results.length
    );

    console.log(
        "NSE API failures :", failed
    );


    /*
    =====================================================
    INDUSTRY DISTRIBUTION
    =====================================================
    */

    const industryCount = {};

    const sectorCount = {};


    for (const result of results) {

        const industry =
            result.investiq_industry;

        const sector =
            result.investiq_sector;


        industryCount[industry] =
            (industryCount[industry] || 0) + 1;

        sectorCount[sector] =
            (sectorCount[sector] || 0) + 1;
    }


    console.log("\n========== INDUSTRY DISTRIBUTION ==========");

    Object.entries(industryCount)
        .sort((a, b) => b[1] - a[1])
        .forEach(([industry, count]) => {

            console.log(
                `${industry.padEnd(30)} ${count}`
            );

        });


    console.log("\n========== SECTOR DISTRIBUTION ==========");

    Object.entries(sectorCount)
        .sort((a, b) => b[1] - a[1])
        .forEach(([sector, count]) => {

            console.log(
                `${sector.padEnd(35)} ${count}`
            );

        });


    /*
    =====================================================
    SAVE DRY RUN
    =====================================================
    */

    const fs = require("fs");

    fs.writeFileSync(
        "classification_preview.json",
        JSON.stringify(results, null, 2)
    );


    console.log(
        "\nSaved:",
        "classification_preview.json"
    );


    /*
    =====================================================
    DATABASE UPDATE
    =====================================================
    */

    if (DRY_RUN) {

        console.log("\n========================================");
        console.log("DATABASE WAS NOT MODIFIED");
        console.log("DRY_RUN = true");
        console.log("========================================");

        return;
    }


    /*
    =====================================================
    UPDATE COMPANIES
    =====================================================
    */

    let updated = 0;

    for (const result of results) {

        if (!result.investiq_industry) {
            continue;
        }


        const [industryRows] = await db.query(
            `
            SELECT
                id,
                sector_id
            FROM industries
            WHERE name = ?
            LIMIT 1
            `,
            [result.investiq_industry]
        );


        if (!industryRows.length) {

            console.log(
                "Industry not found:",
                result.investiq_industry
            );

            continue;
        }


        const industry =
            industryRows[0];


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
                result.id
            ]
        );


        updated++;
    }


    console.log("\n========================================");
    console.log("DATABASE UPDATED");
    console.log("Companies updated:", updated);
    console.log("========================================");
}


classifyCompanies()
    .catch(error => {

        console.error(
            "\nFATAL ERROR:"
        );

        console.error(error);

        process.exit(1);
    });