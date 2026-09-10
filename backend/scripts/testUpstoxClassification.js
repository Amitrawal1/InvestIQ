require("dotenv").config();

const fs = require("fs");
const path = require("path");
const axios = require("axios");
const db = require("../config/db");

const sleep = (ms) =>
    new Promise(resolve => setTimeout(resolve, ms));

const LIMIT = 10;
const DELAY = 500;


/*
=========================================================
ACCESS TOKEN
=========================================================
*/

const BASE_DIR = path.resolve(__dirname, "../..");

const TOKEN_FILE =
    path.join(
        BASE_DIR,
        "ml",
        "upstox_access_token.txt"
    );


if (!fs.existsSync(TOKEN_FILE)) {

    console.error(
        "\nERROR: Upstox access token file not found:"
    );

    console.error(TOKEN_FILE);

    process.exit(1);
}


const ACCESS_TOKEN =
    fs.readFileSync(
        TOKEN_FILE,
        "utf8"
    ).trim();


if (!ACCESS_TOKEN) {

    console.error(
        "\nERROR: Upstox access token file is empty."
    );

    process.exit(1);
}


console.log(
    "Upstox access token loaded:",
    true
);


/*
=========================================================
UPSTOX CLIENT
=========================================================
*/

const upstox = axios.create({

    baseURL:
        "https://api.upstox.com/v2",

    timeout:
        30000,

    headers: {

        "Accept":
            "application/json",

        "Authorization":
            `Bearer ${ACCESS_TOKEN}`
    }
});


/*
=========================================================
FETCH COMPANY PROFILE
=========================================================
*/

async function fetchCompanyProfile(isin) {

    try {

        const response =
            await upstox.get(
                `/fundamentals/${isin}/profile`
            );

        return response.data;

    } catch (error) {

        console.log(
            `Upstox request failed for ${isin}`
        );


        if (error.response) {

            console.log(
                "HTTP Status:",
                error.response.status
            );

            console.log(
                "Response:",
                JSON.stringify(
                    error.response.data,
                    null,
                    2
                )
            );

        } else {

            console.log(
                "Error:",
                error.message
            );
        }


        return null;
    }
}


/*
=========================================================
MAIN
=========================================================
*/

async function main() {

    console.log("\n========================================");
    console.log("InvestIQ Upstox Classification Test");
    console.log("========================================");


    /*
    =====================================================
    DATABASE
    =====================================================
    */

    const [companies] =
        await db.query(`
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
        `Companies to test: ${companies.length}`
    );


    const results = [];


    /*
    =====================================================
    PROCESS
    =====================================================
    */

    for (
        let i = 0;
        i < companies.length;
        i++
    ) {

        const company =
            companies[i];


        console.log(
            `\n[${i + 1}/${companies.length}] ` +
            `${company.symbol} - ${company.name}`
        );


        const data =
            await fetchCompanyProfile(
                company.isin
            );


        if (!data) {

            results.push({

                ...company,

                status:
                    "UPSTOX_FAILED",

                upstox_sector:
                    null,

                company_profile:
                    null
            });

            continue;
        }


        /*
        =================================================
        EXTRACT RESPONSE
        =================================================
        */

        const profile =
            data.data || {};


        const companyProfile =
            profile.company_profile ||
            profile.companyProfile ||
            null;


        const sector =
            profile.sector ||
            null;


        results.push({

            ...company,

            status:
                "SUCCESS",

            upstox_sector:
                sector,

            company_profile:
                companyProfile
        });


        await sleep(DELAY);
    }


    /*
    =====================================================
    RESULTS
    =====================================================
    */

    console.log("\n========================================");
    console.log("RESULTS");
    console.log("========================================");


    console.table(

        results.map(x => ({

            symbol:
                x.symbol,

            name:
                x.name,

            isin:
                x.isin,

            upstox_sector:
                x.upstox_sector,

            status:
                x.status
        }))
    );


    /*
    =====================================================
    DETAILED DATA
    =====================================================
    */

    console.log(
        "\n========== DETAILED DATA =========="
    );


    for (const result of results) {

        console.log(
            "\n----------------------------------------"
        );

        console.log(
            "Symbol:",
            result.symbol
        );

        console.log(
            "Name:",
            result.name
        );

        console.log(
            "ISIN:",
            result.isin
        );

        console.log(
            "Upstox Sector:",
            result.upstox_sector
        );

        console.log(
            "Company Profile:",
            result.company_profile
        );
    }


    /*
    =====================================================
    SAVE PREVIEW
    =====================================================
    */

    const outputFile =
        path.join(
            __dirname,
            "upstox_classification_preview.json"
        );


    fs.writeFileSync(
        outputFile,
        JSON.stringify(
            results,
            null,
            2
        )
    );


    console.log(
        "\nPreview saved:",
        outputFile
    );


    console.log("\n========================================");
    console.log("DATABASE WAS NOT MODIFIED");
    console.log("========================================");


    await db.end();
}


main()
    .catch(error => {

        console.error(
            "\nFATAL ERROR:"
        );

        console.error(error);

        process.exit(1);
    });
