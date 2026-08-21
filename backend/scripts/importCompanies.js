const fs = require("fs");
const path = require("path");
const { parse } = require("csv-parse/sync");

const db = require("../config/db");

const importFile = async (fileName, marketSegment) => {
    const filePath = path.join(__dirname, "../data", fileName);

    const fileData = fs.readFileSync(filePath, "utf-8");

    const records = parse(fileData, {
        columns: true,
        skip_empty_lines: true,
        trim: true
    });

    console.log(`${fileName}: ${records.length} records found`);

    for (const company of records) {

        const symbol = company.SYMBOL?.trim();

        const name =
            company["NAME OF COMPANY"]?.trim() ||
            company.NAME_OF_COMPANY?.trim();

        const series = company.SERIES?.trim();

        const isin =
            company["ISIN NUMBER"]?.trim() ||
            company.ISIN_NUMBER?.trim();

        



        const rawListingDate =
            company["DATE OF LISTING"]?.trim() ||
            company.DATE_OF_LISTING?.trim();

        let listingDate = null;

        if (rawListingDate) {
            const [day, month, year] = rawListingDate.split("-");

            const months = {
                JAN: "01",
                FEB: "02",
                MAR: "03",
                APR: "04",
                MAY: "05",
                JUN: "06",
                JUL: "07",
                AUG: "08",
                SEP: "09",
                OCT: "10",
                NOV: "11",
                DEC: "12"
            };

            const monthNumber = months[month.toUpperCase()];

            if (monthNumber) {
                listingDate = `${year}-${monthNumber}-${day.padStart(2, "0")}`;
            }
        }

        if (!symbol || !name) {
            continue;
        }

        await db.query(
            `
            INSERT INTO companies
            (
                name,
                symbol,
                sector_id,
                exchange,
                market_segment,
                instrument_token,
                listing_status,
                isin,
                listing_date,
                series
            )
            VALUES (?, ?, NULL, 'NSE', ?, NULL, 'LISTED', ?, ?, ?)

            ON DUPLICATE KEY UPDATE
                name = VALUES(name),
                market_segment = VALUES(market_segment),
                listing_status = 'LISTED',
                isin = VALUES(isin),
                listing_date = VALUES(listing_date),
                series = VALUES(series)
            `,
            [
                name,
                symbol,
                marketSegment,
                isin || null,
                listingDate || null,
                series || null
            ]
        );
    }

    console.log(`${fileName} imported successfully`);
};


const importCompanies = async () => {

    try {

        console.log("================================");
        console.log("Starting NSE company import...");
        console.log("================================");

        await importFile(
            "equity.csv",
            "EQUITY"
        );

        await importFile(
            "sme_equity.csv",
            "SME"
        );

        console.log("================================");
        console.log("NSE import completed successfully");
        console.log("================================");

        process.exit(0);

    } catch (error) {

        console.error("Company import failed:");
        console.error(error.message);

        process.exit(1);
    }
};


importCompanies();