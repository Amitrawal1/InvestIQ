const fs = require("fs");
const path = require("path");
const db = require("../config/db");

const INPUT = path.join(
  __dirname,
  "company_classification_final_preview.json"
);

async function main() {
  const data = JSON.parse(
    fs.readFileSync(INPUT, "utf8")
  );

  const results = data.results.filter(
    row =>
      row.investiq_industry &&
      row.status !== "UPSTOX_FAILED"
  );

  console.log("\n=================================");
  console.log("InvestIQ FINAL DB UPDATE");
  console.log("=================================");

  console.log("Preview records:", data.results.length);
  console.log("Records to update:", results.length);

  // Get a dedicated DB connection for transaction
  const conn = await db.getConnection();

  try {
    // --------------------------------
    // LOAD INDUSTRIES
    // --------------------------------

    const [industries] = await conn.query(`
      SELECT
        id,
        name,
        sector_id
      FROM industries
    `);

    const industryMap = new Map();

    for (const industry of industries) {
      industryMap.set(
        industry.name.trim().toLowerCase(),
        industry
      );
    }

    // --------------------------------
    // VALIDATE ALL INDUSTRIES
    // --------------------------------

    const invalid = [];

    for (const row of results) {
      const key = row.investiq_industry
        .trim()
        .toLowerCase();

      if (!industryMap.has(key)) {
        invalid.push({
          company_id: row.company_id,
          symbol: row.symbol,
          name: row.name,
          industry: row.investiq_industry
        });
      }
    }

    if (invalid.length > 0) {
      console.error("\nINVALID INDUSTRIES FOUND:");
      console.error(
        JSON.stringify(invalid, null, 2)
      );

      console.error("\nDB UPDATE ABORTED.");

      conn.release();
      process.exit(1);
    }

    console.log(
      "\nAll industry names validated successfully."
    );

    // --------------------------------
    // START TRANSACTION
    // --------------------------------

    await conn.beginTransaction();

    console.log("\nTransaction started.");

    let updated = 0;

    // --------------------------------
    // UPDATE COMPANIES
    // --------------------------------

    for (const row of results) {
      const industry = industryMap.get(
        row.investiq_industry
          .trim()
          .toLowerCase()
      );

      const [result] = await conn.query(
        `
        UPDATE companies
        SET
          industry_id = ?,
          sector_id = ?,
          industry = ?
        WHERE id = ?
        `,
        [
          industry.id,
          industry.sector_id,
          industry.name,
          row.company_id
        ]
      );

      updated += result.affectedRows;
    }

    console.log(
      `Updated ${updated} database rows.`
    );

    // --------------------------------
    // COMMIT
    // --------------------------------

    await conn.commit();

    console.log("\n=================================");
    console.log("DB UPDATE SUCCESSFUL");
    console.log("=================================");

    console.log(
      "Companies processed:",
      results.length
    );

    console.log(
      "Rows affected:",
      updated
    );

    // --------------------------------
    // VERIFY
    // --------------------------------

    const [[stats]] = await conn.query(`
      SELECT
        COUNT(*) AS total,
        SUM(industry_id IS NOT NULL) AS classified,
        SUM(industry_id IS NULL) AS unclassified,
        SUM(sector_id IS NOT NULL) AS sector_assigned
      FROM companies
    `);

    console.log("\n=================================");
    console.log("DATABASE VERIFICATION");
    console.log("=================================");

    console.log("Total companies:", stats.total);
    console.log("Classified:", stats.classified);
    console.log("Unclassified:", stats.unclassified);
    console.log("Sector assigned:", stats.sector_assigned);

    // --------------------------------
    // VERIFY INDUSTRY ↔ SECTOR
    // --------------------------------

    const [[mismatch]] = await conn.query(`
      SELECT COUNT(*) AS count
      FROM companies c
      JOIN industries i
        ON c.industry_id = i.id
      WHERE c.sector_id <> i.sector_id
    `);

    console.log(
      "Industry/Sector mismatches:",
      mismatch.count
    );

    // --------------------------------
    // SHOW REMAINING UNCLASSIFIED
    // --------------------------------

    const [remaining] = await conn.query(`
      SELECT
        id,
        symbol,
        name
      FROM companies
      WHERE industry_id IS NULL
      ORDER BY id
    `);

    console.log(
      "\nRemaining unclassified:",
      remaining.length
    );

    if (remaining.length > 0) {
      console.log(
        remaining.slice(0, 20)
      );

      if (remaining.length > 20) {
        console.log(
          `... and ${remaining.length - 20} more`
        );
      }
    }

  } catch (error) {

    // --------------------------------
    // ROLLBACK
    // --------------------------------

    try {
      await conn.rollback();
      console.error(
        "\nTransaction rolled back."
      );
    } catch (rollbackError) {
      console.error(
        "\nRollback failed:",
        rollbackError
      );
    }

    console.error("\nDB UPDATE FAILED:");
    console.error(error);

    process.exitCode = 1;

  } finally {

    // --------------------------------
    // RELEASE CONNECTION
    // --------------------------------

    conn.release();
  }
}

main().catch(error => {
  console.error("\nUnexpected error:");
  console.error(error);

  process.exit(1);
});