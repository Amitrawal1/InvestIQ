// Export sectors + their companies to a JSON snapshot used by the frontend
// when the API is unreachable. Re-run after the companies table changes:
//   cd backend && node scripts/exportSectorSnapshot.js

const fs = require("fs");
const path = require("path");
const db = require("../config/db");

const OUTPUT = path.join(__dirname, "..", "..", "frontend", "src", "data", "sectorsSnapshot.json");

async function main() {
    const [sectors] = await db.query(`
        SELECT
            s.id,
            s.name,
            s.slug,
            (SELECT COUNT(*) FROM companies c WHERE c.sector_id = s.id) AS company_count,
            (SELECT COUNT(*) FROM industries i WHERE i.sector_id = s.id) AS industry_count
        FROM sectors s
        ORDER BY s.id
    `);

    const [companies] = await db.query(`
        SELECT
            c.id,
            c.name,
            c.symbol,
            c.market_segment,
            c.sector_id,
            i.name AS industry
        FROM companies c
        LEFT JOIN industries i ON c.industry_id = i.id
        WHERE c.sector_id IS NOT NULL
        ORDER BY c.name ASC
    `);

    // Same shape as GET /companies?sector=..., grouped by sector id
    const companiesBySector = {};
    for (const { sector_id, ...company } of companies) {
        (companiesBySector[sector_id] ||= []).push(company);
    }

    const snapshot = {
        exported_at: new Date().toISOString(),
        sectors,
        companiesBySector,
    };

    fs.mkdirSync(path.dirname(OUTPUT), { recursive: true });
    fs.writeFileSync(OUTPUT, JSON.stringify(snapshot));

    console.log(`Exported ${sectors.length} sectors and ${companies.length} companies to ${OUTPUT}`);
}

main()
    .catch((error) => {
        console.error("Snapshot export failed:", error.message);
        process.exitCode = 1;
    })
    .finally(() => db.end());
