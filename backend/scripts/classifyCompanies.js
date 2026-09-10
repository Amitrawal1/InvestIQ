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

// Abhi sirf 10 companies test karenge
const LIMIT = 10;

const REQUEST_DELAY = 1000;
const MAX_RETRIES = 3;


/*
=========================================================
NSE CLIENT
=========================================================
*/

const nse = axios.create({
    baseURL: "https://www.nseindia.com",
    timeout: 30000,

    headers: {
        "User-Agent":
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) " +
            "AppleWebKit/537.36 (KHTML, like Gecko) " +
            "Chrome/139.0 Safari/537.36",

        "Accept":
            "application/json, text/plain, */*",

        "Accept-Language":
            "en-US,en;q=0.9",

        "Referer":
            "https://www.nseindia.com/",

        "Connection":
            "keep-alive"
    }
});


/*
=========================================================
COOKIE HANDLING
=========================================================
*/

let cookies = "";

function updateCookies(response) {

    const setCookie = response.headers["set-cookie"];

    if (!setCookie) {
        return;
    }

    const newCookies = setCookie
        .map(cookie => cookie.split(";")[0])
        .join("; ");

    cookies = newCookies;
}


/*
=========================================================
NSE REQUEST
=========================================================
*/

async function nseRequest(url, config = {}) {

    const headers = {
        ...config.headers
    };

    if (cookies) {
        headers.Cookie = cookies;
    }

    const response = await nse.get(url, {
        ...config,
        headers
    });

    updateCookies(response);

    return response;
}


/*
=========================================================
INITIALIZE NSE
=========================================================
*/

async function initializeNSE() {

    console.log("\n========================================");
    console.log("INITIALIZING NSE");
    console.log("========================================");

    try {

        const response = await nse.get("/", {
            headers: {
                "User-Agent":
                    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) " +
                    "AppleWebKit/537.36 (KHTML, like Gecko) " +
                    "Chrome/139.0 Safari/537.36",

                "Accept":
                    "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",

                "Accept-Language":
                    "en-US,en;q=0.9"
            }
        });

        updateCookies(response);

        console.log("NSE homepage status:", response.status);
        console.log(
            "NSE cookies:",
            cookies ? "received" : "NOT RECEIVED"
        );

        if (!cookies) {
            console.log(
                "WARNING: NSE did not provide cookies."
            );
        }

        // NSE ko thoda time
        await sleep(1500);

    } catch (error) {

        console.error(
            "\nNSE initialization failed."
        );

        console.error(
            "Message:",
            error.message
        );

        if (error.response) {

            console.error(
                "HTTP Status:",
                error.response.status
            );

            console.error(
                "Response:",
                typeof error.response.data === "string"
                    ? error.response.data.substring(0, 500)
                    : error.response.data
            );
        }

        throw error;
    }
}


/*
=========================================================
TEST NSE API
=========================================================
*/

async function testNSE() {

    console.log("\n========================================");
    console.log("TESTING NSE API");
    console.log("========================================");

    try {

        const response = await nseRequest(
            "/api/quote-equity",
            {
                params: {
                    symbol: "RELIANCE"
                },
                headers: {
                    "Referer":
                        "https://www.nseindia.com/get-quotes/equity?symbol=RELIANCE",

                    "Accept":
                        "application/json, text/plain, */*"
                }
            }
        );

        console.log(
            "RELIANCE API status:",
            response.status
        );

        if (!response.data) {
            throw new Error("Empty NSE response");
        }

        console.log(
            "RELIANCE API response received."
        );

        const info =
            response.data.industryInfo || {};

        console.log("\nNSE INDUSTRY INFO:");

        console.log(
            "Macro:",
            info.macro || null
        );

        console.log(
            "Sector:",
            info.sector || null
        );

        console.log(
            "Industry:",
            info.industry || null
        );

        console.log(
            "Basic Industry:",
            info.basicIndustry || null
        );

        return true;

    } catch (error) {

        console.error(
            "\nNSE API TEST FAILED"
        );

        console.error(
            "Message:",
            error.message
        );

        if (error.response) {

            console.error(
                "HTTP Status:",
                error.response.status
            );

            console.error(
                "URL:",
                error.config?.url
            );

            console.error(
                "Response:",
                typeof error.response.data === "string"
                    ? error.response.data.substring(0, 1000)
                    : JSON.stringify(
                        error.response.data,
                        null,
                        2
                    ).substring(0, 1000)
            );
        }

        return false;
    }
}


/*
=========================================================
FETCH COMPANY
=========================================================
*/

async function fetchNSECompany(symbol) {

    for (
        let attempt = 1;
        attempt <= MAX_RETRIES;
        attempt++
    ) {

        try {

            const response = await nseRequest(
                "/api/quote-equity",
                {
                    params: {
                        symbol
                    },

                    headers: {
                        "Referer":
                            `https://www.nseindia.com/get-quotes/equity?symbol=${encodeURIComponent(symbol)}`,

                        "Accept":
                            "application/json, text/plain, */*"
                    }
                }
            );

            return response.data;

        } catch (error) {

            console.log(
                `${symbol}: attempt ${attempt}/${MAX_RETRIES} failed`
            );

            if (error.response) {

                console.log(
                    `HTTP ${error.response.status}`
                );
            }

            if (attempt < MAX_RETRIES) {

                // Agar session expire/block ho gaya ho
                if (
                    error.response &&
                    (
                        error.response.status === 401 ||
                        error.response.status === 403 ||
                        error.response.status === 429
                    )
                ) {

                    console.log(
                        "Refreshing NSE session..."
                    );

                    try {
                        await initializeNSE();
                    } catch (_) {}
                }

                await sleep(attempt * 3000);
            }
        }
    }

    return null;
}


/*
=========================================================
NORMALIZATION
=========================================================
*/

function normalize(value) {

    if (!value) {
        return "";
    }

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
CLASSIFICATION
=========================================================
*/

function classifyFromNSE(nseData) {

    const info =
        nseData?.industryInfo || {};

    const macro =
        normalize(info.macro);

    const sector =
        normalize(info.sector);

    const industry =
        normalize(info.industry);

    const basic =
        normalize(info.basicIndustry);

    const text =
        `${macro} ${sector} ${industry} ${basic}`;


    // Technology

    if (
        basic.includes("semiconductor") ||
        industry.includes("semiconductor")
    ) {
        return {
            sector: "Technology",
            industry: "Semiconductor"
        };
    }

    if (
        basic.includes("software") ||
        industry.includes("software") ||
        basic.includes("it services") ||
        industry.includes("it services")
    ) {
        return {
            sector: "Technology",
            industry: "Software"
        };
    }

    if (
        basic.includes("computer hardware") ||
        basic.includes("hardware") ||
        industry.includes("hardware")
    ) {
        return {
            sector: "Technology",
            industry: "Hardware"
        };
    }

    if (
        text.includes("information technology") ||
        text.includes("information technology services")
    ) {
        return {
            sector: "Technology",
            industry: "IT Services"
        };
    }


    // Financial Services

    if (
        basic.includes("bank") ||
        industry.includes("bank") ||
        sector.includes("bank")
    ) {
        return {
            sector: "Financial Services",
            industry: "Banking"
        };
    }

    if (
        basic.includes("insurance") ||
        industry.includes("insurance")
    ) {
        return {
            sector: "Financial Services",
            industry: "Insurance"
        };
    }

    if (
        basic.includes("asset management") ||
        industry.includes("asset management") ||
        basic.includes("mutual fund")
    ) {
        return {
            sector: "Financial Services",
            industry: "Asset Management"
        };
    }

    if (
        basic.includes("finance") ||
        industry.includes("finance") ||
        basic.includes("nbfc") ||
        industry.includes("nbfc")
    ) {
        return {
            sector: "Financial Services",
            industry: "NBFC"
        };
    }


    // Healthcare

    if (
        basic.includes("pharma") ||
        basic.includes("pharmaceutical") ||
        industry.includes("pharma") ||
        industry.includes("pharmaceutical")
    ) {
        return {
            sector: "Healthcare & Pharmaceuticals",
            industry: "Pharmaceuticals"
        };
    }

    if (
        basic.includes("hospital") ||
        industry.includes("hospital")
    ) {
        return {
            sector: "Healthcare & Pharmaceuticals",
            industry: "Hospitals"
        };
    }

    if (
        basic.includes("diagnostic") ||
        industry.includes("diagnostic")
    ) {
        return {
            sector: "Healthcare & Pharmaceuticals",
            industry: "Diagnostics"
        };
    }

    if (
        basic.includes("medical device") ||
        basic.includes("medical equipment") ||
        industry.includes("medical device") ||
        industry.includes("medical equipment")
    ) {
        return {
            sector: "Healthcare & Pharmaceuticals",
            industry: "Medical Devices"
        };
    }


    // Automobile

    if (
        basic.includes("auto component") ||
        basic.includes("auto parts") ||
        industry.includes("auto component") ||
        industry.includes("auto parts")
    ) {
        return {
            sector: "Automobile & Mobility",
            industry: "Auto Components"
        };
    }

    if (
        basic.includes("electric vehicle") ||
        industry.includes("electric vehicle")
    ) {
        return {
            sector: "Automobile & Mobility",
            industry: "Electric Vehicles"
        };
    }

    if (
        basic.includes("passenger car") ||
        basic.includes("two wheeler") ||
        basic.includes("three wheeler") ||
        basic.includes("commercial vehicle") ||
        industry.includes("automobile")
    ) {
        return {
            sector: "Automobile & Mobility",
            industry: "Automobiles"
        };
    }


    // Energy

    if (
        basic.includes("oil") ||
        basic.includes("petroleum") ||
        basic.includes("refineries") ||
        industry.includes("oil") ||
        industry.includes("gas")
    ) {
        return {
            sector: "Energy",
            industry: "Oil & Gas"
        };
    }

    if (
        basic.includes("solar") ||
        industry.includes("solar")
    ) {
        return {
            sector: "Energy",
            industry: "Solar Energy"
        };
    }

    if (
        basic.includes("renewable") ||
        industry.includes("renewable")
    ) {
        return {
            sector: "Energy",
            industry: "Renewable Energy"
        };
    }

    if (
        basic.includes("power") ||
        industry.includes("power")
    ) {
        return {
            sector: "Energy",
            industry: "Power"
        };
    }


    // Metals / Mining

    if (
        basic.includes("cement") ||
        industry.includes("cement")
    ) {
        return {
            sector: "Metals, Mining & Chemicals",
            industry: "Cement"
        };
    }

    if (
        basic.includes("chemical") ||
        industry.includes("chemical")
    ) {
        return {
            sector: "Metals, Mining & Chemicals",
            industry: "Chemicals"
        };
    }

    if (
        basic.includes("steel") ||
        basic.includes("iron") ||
        basic.includes("aluminium") ||
        basic.includes("copper") ||
        basic.includes("zinc") ||
        basic.includes("mining") ||
        industry.includes("mining") ||
        industry.includes("metal")
    ) {
        return {
            sector: "Metals, Mining & Chemicals",
            industry: "Metals & Mining"
        };
    }


    // Real Estate

    if (
        basic.includes("real estate") ||
        basic.includes("realty") ||
        industry.includes("real estate") ||
        industry.includes("realty") ||
        sector.includes("realty")
    ) {
        return {
            sector: "Real Estate & Construction",
            industry: "Real Estate"
        };
    }

    if (
        basic.includes("building material") ||
        basic.includes("construction material")
    ) {
        return {
            sector: "Real Estate & Construction",
            industry: "Building Materials"
        };
    }


    // Industrials

    if (
        basic.includes("construction") ||
        industry.includes("construction")
    ) {
        return {
            sector: "Industrials & Infrastructure",
            industry: "Construction"
        };
    }

    if (
        basic.includes("engineering") ||
        industry.includes("engineering")
    ) {
        return {
            sector: "Industrials & Infrastructure",
            industry: "Engineering"
        };
    }

    if (
        basic.includes("capital goods") ||
        industry.includes("capital goods")
    ) {
        return {
            sector: "Industrials & Infrastructure",
            industry: "Capital Goods"
        };
    }

    if (
        basic.includes("infrastructure") ||
        industry.includes("infrastructure")
    ) {
        return {
            sector: "Industrials & Infrastructure",
            industry: "Infrastructure"
        };
    }


    // Consumer

    if (
        basic.includes("food") ||
        basic.includes("beverage") ||
        industry.includes("food") ||
        industry.includes("beverage")
    ) {
        return {
            sector: "Consumer & FMCG",
            industry: "Food & Beverages"
        };
    }

    if (
        basic.includes("retail") ||
        industry.includes("retail")
    ) {
        return {
            sector: "Consumer & FMCG",
            industry: "Retail"
        };
    }

    if (
        basic.includes("consumer durable") ||
        industry.includes("consumer durable")
    ) {
        return {
            sector: "Consumer & FMCG",
            industry: "Consumer Durables"
        };
    }

    if (
        basic.includes("fmcg") ||
        industry.includes("fmcg")
    ) {
        return {
            sector: "Consumer & FMCG",
            industry: "FMCG"
        };
    }


    // Services

    if (
        basic.includes("telecom") ||
        industry.includes("telecom")
    ) {
        return {
            sector: "Services & Others",
            industry: "Telecom"
        };
    }

    if (
        basic.includes("logistics") ||
        industry.includes("logistics") ||
        basic.includes("transportation")
    ) {
        return {
            sector: "Services & Others",
            industry: "Logistics"
        };
    }

    if (
        basic.includes("hotel") ||
        basic.includes("hospitality") ||
        industry.includes("hotel") ||
        industry.includes("hospitality")
    ) {
        return {
            sector: "Services & Others",
            industry: "Hotels & Hospitality"
        };
    }

    if (
        basic.includes("media") ||
        basic.includes("entertainment") ||
        industry.includes("media") ||
        industry.includes("entertainment")
    ) {
        return {
            sector: "Services & Others",
            industry: "Media & Entertainment"
        };
    }

    if (
        basic.includes("education") ||
        industry.includes("education")
    ) {
        return {
            sector: "Services & Others",
            industry: "Education"
        };
    }


    return null;
}


/*
=========================================================
MAIN
=========================================================
*/

async function main() {

    console.log("\n========================================");
    console.log("InvestIQ NSE Classification");
    console.log("========================================");

    await initializeNSE();


    // IMPORTANT:
    // Pehle NSE API test hoga.
    // Agar ye fail hua to companies process nahi hongi.

    const nseWorking =
        await testNSE();

    if (!nseWorking) {

        console.log("\n========================================");
        console.log("STOPPING");
        console.log("NSE API is not working.");
        console.log("No company classification attempted.");
        console.log("Database was NOT modified.");
        console.log("========================================");

        return;
    }


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
        LIMIT ?
    `, [LIMIT]);


    console.log(
        `\nCompanies to classify: ${companies.length}`
    );


    const results = [];


    for (let i = 0; i < companies.length; i++) {

        const company =
            companies[i];

        console.log(
            `\n[${i + 1}/${companies.length}] ` +
            `${company.symbol} - ${company.name}`
        );


        const nseData =
            await fetchNSECompany(
                company.symbol
            );


        if (!nseData) {

            results.push({
                ...company,

                status: "NSE_FAILED",

                nse_macro: null,
                nse_sector: null,
                nse_industry: null,
                nse_basic_industry: null,

                investiq_sector: null,
                investiq_industry: null
            });

            continue;
        }


        const info =
            nseData.industryInfo || {};


        const classification =
            classifyFromNSE(nseData);


        results.push({

            ...company,

            status:
                classification
                    ? "CLASSIFIED"
                    : "NSE_DATA_NO_MAPPING",

            nse_macro:
                info.macro || null,

            nse_sector:
                info.sector || null,

            nse_industry:
                info.industry || null,

            nse_basic_industry:
                info.basicIndustry || null,

            investiq_sector:
                classification?.sector || null,

            investiq_industry:
                classification?.industry || null
        });


        await sleep(
            REQUEST_DELAY
        );
    }


    console.log("\n========================================");
    console.log("RESULTS");
    console.log("========================================");


    console.table(
        results.map(x => ({
            symbol:
                x.symbol,

            name:
                x.name,

            nse_sector:
                x.nse_sector,

            nse_industry:
                x.nse_industry,

            basic_industry:
                x.nse_basic_industry,

            investiq_industry:
                x.investiq_industry,

            investiq_sector:
                x.investiq_sector,

            status:
                x.status
        }))
    );


    const fs =
        require("fs");


    fs.writeFileSync(
        "classification_preview.json",
        JSON.stringify(
            results,
            null,
            2
        )
    );


    console.log(
        "\nPreview saved:",
        "classification_preview.json"
    );


    console.log("\n========================================");
    console.log("DATABASE WAS NOT MODIFIED");
    console.log(`DRY_RUN = ${DRY_RUN}`);
    console.log("========================================");


    await db.end();
}


main()
    .catch(error => {

        console.error(
            "\nFATAL ERROR:"
        );

        console.error(
            error
        );

        process.exit(1);
    });
