const fs = require("fs");
const path = require("path");

const INPUT = path.join(
    __dirname,
    "upstox_classification_v3_preview.json"
);

const OUTPUT = path.join(
    __dirname,
    "v3_diagnostic_report.json"
);

const data = JSON.parse(
    fs.readFileSync(INPUT, "utf8")
);

const results = data.results || data;

function countBy(arr, keyFn) {
    const counter = {};

    for (const item of arr) {
        const key = keyFn(item) || "UNKNOWN";
        counter[key] = (counter[key] || 0) + 1;
    }

    return Object.entries(counter)
        .sort((a, b) => b[1] - a[1]);
}

const unmapped = results.filter(
    r => r.status === "UNMAPPED"
);

const low = results.filter(
    r => r.status === "LOW_CONFIDENCE"
);

const medium = results.filter(
    r => r.status === "MEDIUM_CONFIDENCE"
);

const high = results.filter(
    r => r.status === "HIGH_CONFIDENCE"
);

const failed = results.filter(
    r => r.status === "UPSTOX_FAILED"
);


/*
=========================================================
1. UNMAPPED UPSTOX SECTORS
=========================================================
*/

const unmappedSectors = countBy(
    unmapped,
    r => r.upstox_sector
);


/*
=========================================================
2. LOW CONFIDENCE SECTORS
=========================================================
*/

const lowConfidenceSectors = countBy(
    low,
    r => r.upstox_sector
);


/*
=========================================================
3. LOW CONFIDENCE CANDIDATE CONFLICTS
=========================================================
*/

const conflicts = {};

for (const r of low) {

    const candidates = r.candidates || [];

    if (candidates.length >= 2) {

        const first = candidates[0]?.industry || "";
        const second = candidates[1]?.industry || "";

        const key = `${first} VS ${second}`;

        conflicts[key] =
            (conflicts[key] || 0) + 1;
    }
}

const candidateConflicts =
    Object.entries(conflicts)
        .sort((a, b) => b[1] - a[1]);


/*
=========================================================
4. UNMAPPED COMPANY SAMPLE
=========================================================
*/

const unmappedSample =
    unmapped
        .slice(0, 300)
        .map(r => ({
            company_id: r.company_id,
            name: r.name,
            symbol: r.symbol,
            upstox_sector: r.upstox_sector,
            company_profile: r.company_profile
        }));


/*
=========================================================
5. LOW CONFIDENCE SAMPLE
=========================================================
*/

const lowSample =
    low
        .slice(0, 300)
        .map(r => ({
            company_id: r.company_id,
            name: r.name,
            symbol: r.symbol,
            upstox_sector: r.upstox_sector,
            investiq_industry: r.investiq_industry,
            confidence: r.confidence,
            candidates: r.candidates,
            matched_rules: r.matched_rules
        }));


/*
=========================================================
6. INDUSTRY DISTRIBUTION
=========================================================
*/

const industryDistribution =
    countBy(
        results.filter(r => r.investiq_industry),
        r => r.investiq_industry
    );


/*
=========================================================
7. FINAL REPORT
=========================================================
*/

const report = {

    summary: {
        total: results.length,
        high_confidence: high.length,
        medium_confidence: medium.length,
        low_confidence: low.length,
        unmapped: unmapped.length,
        upstox_failed: failed.length
    },

    unmapped_upstox_sectors:
        unmappedSectors,

    low_confidence_upstox_sectors:
        lowConfidenceSectors,

    candidate_conflicts:
        candidateConflicts,

    industry_distribution:
        industryDistribution,

    unmapped_sample:
        unmappedSample,

    low_confidence_sample:
        lowSample
};


fs.writeFileSync(
    OUTPUT,
    JSON.stringify(report, null, 2)
);


/*
=========================================================
CONSOLE
=========================================================
*/

console.log("\n========================================");
console.log("V3 DIAGNOSTIC REPORT");
console.log("========================================");

console.log(`Total:             ${results.length}`);
console.log(`High confidence:   ${high.length}`);
console.log(`Medium confidence: ${medium.length}`);
console.log(`Low confidence:    ${low.length}`);
console.log(`Unmapped:          ${unmapped.length}`);
console.log(`Upstox failed:     ${failed.length}`);


console.log(
    "\n========== TOP UNMAPPED UPSTOX SECTORS =========="
);

unmappedSectors
    .slice(0, 50)
    .forEach(([sector, count]) => {
        console.log(
            `${String(count).padStart(4)}  ${sector}`
        );
    });


console.log(
    "\n========== TOP LOW-CONFIDENCE SECTORS =========="
);

lowConfidenceSectors
    .slice(0, 30)
    .forEach(([sector, count]) => {
        console.log(
            `${String(count).padStart(4)}  ${sector}`
        );
    });


console.log(
    "\n========== TOP CANDIDATE CONFLICTS =========="
);

candidateConflicts
    .slice(0, 30)
    .forEach(([conflict, count]) => {
        console.log(
            `${String(count).padStart(4)}  ${conflict}`
        );
    });


console.log("\n========================================");
console.log("REPORT SAVED:");
console.log(OUTPUT);
console.log("========================================\n");