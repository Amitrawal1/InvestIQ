const fs = require("fs");
const path = require("path");

const INPUT = path.join(
  __dirname,
  "upstox_classification_v3_5_preview.json"
);

const OUTPUT = path.join(
  __dirname,
  "company_classification_final_preview.json"
);

/*
|--------------------------------------------------------------------------
| FINAL MANUAL CLASSIFICATION
|--------------------------------------------------------------------------
| Only manually reviewed companies are listed here.
| Symbol -> [InvestIQ Industry, Confidence]
|--------------------------------------------------------------------------
*/

const MANUAL = {

  // =========================
  // FINANCIAL SERVICES
  // =========================

  "360ONE": ["Asset Management", 95],
  "ABANSENT": ["Other Services", 90],
  "ALGOQUANT": ["Other Services", 90],
  "ANANDRATHI": ["Asset Management", 95],
  "BSE": ["Other Services", 95],
  "IFCI": ["Other Services", 90],
  "NORTHARC": ["NBFC", 95],
  "PRUDENT": ["Asset Management", 95],
  "SATIN": ["NBFC", 95],
  "SBIFUNDS": ["Asset Management", 95],
  "TATACAP": ["NBFC", 95],
  "TATAINVEST": ["Asset Management", 95],

  // =========================
  // TECHNOLOGY
  // =========================

  "COFORGE": ["Software", 95],
  "DRCSYSTEMS": ["Software", 90],
  "E2E": ["IT Services", 90],
  "KELLTONTEC": ["Software", 90],
  "LATENTVIEW": ["Software", 95],
  "SIGMA": ["Software", 95],
  "DUGLOBAL": ["IT Services", 85],
  "IKS": ["IT Services", 90],

  // =========================
  // CONSUMER / RETAIL
  // =========================

  "AARNAV": ["Consumer Services", 85],
  "ABLBL": ["Consumer Services", 90],
  "BCONCEPTS": ["Consumer Services", 90],
  "CRAVATEX": ["Consumer Services", 90],
  "FIRSTCRY": ["Retail", 95],
  "HONASA": ["FMCG", 95],
  "MUFTI": ["Consumer Services", 90],
  "MVGJL": ["Retail", 90],
  "SSDL": ["Retail", 90],
  "V2RETAIL": ["Retail", 95],
  "CELLPOINT": ["Retail", 90],
  "LLOYDS": ["Consumer Services", 85],
  "FOCE": ["Consumer Durables", 85],
  "JUSTDIAL": ["Consumer Services", 95],

  // =========================
  // FOOD & BEVERAGES
  // =========================

  "ASIANTNE": ["Food & Beverages", 90],
  "BBTC": ["Food & Beverages", 85],
  "HARRMALAYA": ["Food & Beverages", 90],
  "MGEL": ["Food & Beverages", 85],
  "SAKUMA": ["Food & Beverages", 90],
  "SHEETAL": ["Food & Beverages", 85],
  "UMAEXPORTS": ["Food & Beverages", 90],
  "VENKEYS": ["Food & Beverages", 95],
  "VINCOFE": ["Food & Beverages", 90],

  // =========================
  // AGRICULTURE / SEEDS
  // =========================
  // Our taxonomy has no Agriculture industry.
  // Therefore these are mapped to Other Services
  // rather than inventing a new industry.

  "AGRITECH": ["Other Services", 75],
  "BSHSL": ["Other Services", 75],
  "INDOUS": ["Other Services", 75],
  "KSCL": ["Other Services", 75],
  "MSL": ["Other Services", 75],
  "NATHBIOGEN": ["Other Services", 75],
  "NIRMAN": ["Other Services", 75],
  "OSWALSEEDS": ["Other Services", 75],
  "USASEEDS": ["Other Services", 75],
  "CONTI": ["Other Services", 75],

  // =========================
  // PHARMACEUTICALS
  // =========================

  "AJOONI": ["Pharmaceuticals", 85],
  "NOVARTIND": ["Pharmaceuticals", 95],
  "SUNREST": ["Pharmaceuticals", 85],
  "SYNGENE": ["Pharmaceuticals", 95],

  // =========================
  // CHEMICALS
  // =========================

  "DCMSHRIRAM": ["Chemicals", 90],
  "GRASIM": ["Chemicals", 90],
  "JUBLCPL": ["Chemicals", 90],
  "KAMOPAINTS": ["Chemicals", 90],
  "OSWALAGRO": ["Chemicals", 85],
  "RCDL": ["Chemicals", 90],
  "SIRCA": ["Chemicals", 95],
  "SRD": ["Chemicals", 95],
  "SIDDHIKA": ["Chemicals", 95],
  "UNIENTER": ["Chemicals", 85],

  // =========================
  // INDUSTRIAL / MANUFACTURING
  // =========================

  "3MINDIA": ["Manufacturing", 95],
  "ALLTIME": ["Manufacturing", 95],
  "AVROIND": ["Manufacturing", 90],
  "GKWLIMITED": ["Manufacturing", 85],
  "MALLCOM": ["Manufacturing", 95],
  "MANAKSIA": ["Manufacturing", 85],
  "MODIRUBBER": ["Manufacturing", 85],
  "NRL": ["Manufacturing", 85],
  "COOLCAPS": ["Manufacturing", 95],

  "BUILDPRO": ["Building Materials", 90],
  "CROWN": ["Capital Goods", 85],
  "GALAPREC": ["Engineering", 90],
  "RMDRIP": ["Manufacturing", 90],
  "JISLDVREQS": ["Manufacturing", 90],
  "AILIMITED": ["Engineering", 85],

  // =========================
  // METALS / AUTOMOBILE
  // =========================

  "NIRAJISPAT": ["Metals & Mining", 90],
  "IMPAL": ["Auto Components", 90],
  "OMAXAUTO": ["Auto Components", 95],
  "RKFORGE": ["Auto Components", 95],
  "STEELCAS": ["Auto Components", 90],
  "STUDDS": ["Auto Components", 90],
  "MAJESAUT": ["Automobiles", 90],

  // =========================
  // REAL ESTATE / INFRA
  // =========================

  "AWFIS": ["Real Estate", 95],
  "EFCIL": ["Real Estate", 90],
  "FMNL": ["Real Estate", 85],
  "KONTOR": ["Real Estate", 95],
  "PACEDIGITK": ["Infrastructure", 90],
  "LEAPIND": ["Logistics", 95],

  // =========================
  // MEDIA / ENTERTAINMENT
  // =========================

  "AMAGI": ["Media & Entertainment", 95],
  "QUINT": ["Media & Entertainment", 95],
  "SIGNPOST": ["Media & Entertainment", 95],
  "TOUCHWOOD": ["Media & Entertainment", 90],
  "MAXPOSURE": ["Media & Entertainment", 95],
  "GRAPHISAD": ["Media & Entertainment", 95],
  "CRAYONS": ["Media & Entertainment", 95],
  "VERTOZ": ["Media & Entertainment", 90],

  // =========================
  // SERVICES
  // =========================

  "AARVI": ["Other Services", 90],
  "BLS": ["Other Services", 95],
  "BLSE": ["Other Services", 95],
  "GCSL": ["Other Services", 85],
  "KAPSTON": ["Other Services", 95],
  "KRYSTAL": ["Other Services", 95],
  "MMTC": ["Other Services", 85],
  "MSTCLTD": ["Other Services", 90],
  "PROPEQUITY": ["Other Services", 90],
  "QUESS": ["Other Services", 95],
  "RTNINDIA": ["Other Services", 80],
  "SHRENIK": ["Other Services", 80],
  "SICAGEN": ["Other Services", 80],
  "SIS": ["Other Services", 95],
  "STCINDIA": ["Other Services", 90],
  "TEAMLEASE": ["Other Services", 95],
  "THACKER": ["Other Services", 80],
  "UDS": ["Other Services", 95],
  "IPSL": ["Other Services", 95],
  "SPECTSTM": ["Other Services", 95],
  "INFOLLION": ["Other Services", 95],
  "SERVICE": ["Other Services", 95],
  "KCK": ["Other Services", 75],
    // =========================
  // FINAL 27 UNMAPPED
  // =========================

  "ABMINTLLTD": ["Other Services", 90],

  "AEROENTER": ["Manufacturing", 95],

  "AKG": ["Other Services", 80],

  "ANMOL": ["Metals & Mining", 90],

  "ARIS": ["Infrastructure", 95],

  "ASHOKAMET": ["Real Estate", 85],

  "AURUS": ["Consumer Services", 80],

  "AUSOMENT": ["Other Services", 90],

  "BLACKROSE": ["Chemicals", 95],

  "BLUSPRING": ["Other Services", 95],

  "BMWVENTLTD": ["Manufacturing", 95],

  "CNL": ["Hardware", 95],

  "EBGNG": ["Hardware", 95],

  "EKI": ["Other Services", 80],

  "FELDVR": ["Retail", 90],

  "HEXATRADEX": ["Other Services", 80],

  "INNOVISION": ["Other Services", 95],

  "JKIPL": ["Capital Goods", 90],

  "JMA": ["Auto Components", 95],

  "LANDSMILL": ["Manufacturing", 95],

  "LLOYDSENT": ["Metals & Mining", 90],

  "NEUEON": ["Manufacturing", 95],

  "ODIGMA": ["IT Services", 95],

  "PTL": ["Auto Components", 90],

  "RKSWAMY": ["Media & Entertainment", 95],

  "SIL": ["Chemicals", 90],

  "TCC": ["Real Estate", 95],

  // =========================
  // HOSPITALITY / AVIATION
  // =========================

  "PRAVEG": ["Hotels & Hospitality", 90],
  "DRONE": ["Aviation", 85],

  // =========================
  // TELECOM / MOBILITY
  // =========================

  "OPTIEMUS": ["Telecom", 85],
  "SHREEOSFM": ["Mobility Services", 90],

  // =========================
  // INSURANCE
  // =========================

  "TURTLEMINT": ["Insurance", 95],

  // =========================
  // CEMENT
  // =========================

  "PRSMJOHNSN": ["Cement", 95]
};


/*
|--------------------------------------------------------------------------
| Load V3.5
|--------------------------------------------------------------------------
*/

const data = JSON.parse(
  fs.readFileSync(INPUT, "utf8")
);

const results = data.results.map(row => {

  const symbol = String(row.symbol || "")
    .trim()
    .toUpperCase();

  const manual = MANUAL[symbol];

  if (!manual) {
    return row;
  }

  const [industry, confidence] = manual;

  return {
    ...row,

    investiq_industry: industry,

    confidence,

    status: "MANUAL_REVIEWED",

    matched_rules: [
      ...(row.matched_rules || []),
      `MANUAL_FINAL_${symbol}`
    ]
  };
});


/*
|--------------------------------------------------------------------------
| Summary
|--------------------------------------------------------------------------
*/

const summary = {
  total: results.length,

  high_confidence: results.filter(
    x => x.status === "HIGH_CONFIDENCE"
  ).length,

  medium_confidence: results.filter(
    x => x.status === "MEDIUM_CONFIDENCE"
  ).length,

  manual_reviewed: results.filter(
    x => x.status === "MANUAL_REVIEWED"
  ).length,

  unmapped: results.filter(
    x => x.status === "UNMAPPED"
  ).length,

  upstox_failed: results.filter(
    x => x.status === "UPSTOX_FAILED"
  ).length
};


/*
|--------------------------------------------------------------------------
| Industry distribution
|--------------------------------------------------------------------------
*/

const industryCounts = {};

for (const row of results) {

  if (!row.investiq_industry) continue;

  industryCounts[row.investiq_industry] =
    (industryCounts[row.investiq_industry] || 0) + 1;
}


/*
|--------------------------------------------------------------------------
| Output
|--------------------------------------------------------------------------
*/

const output = {
  generated_at: new Date().toISOString(),

  version: "FINAL_MANUAL_REVIEW",

  summary,

  industry_counts: industryCounts,

  results
};


fs.writeFileSync(
  OUTPUT,
  JSON.stringify(output, null, 2)
);


console.log("\n=================================");
console.log("InvestIQ FINAL MANUAL REVIEW");
console.log("=================================");

console.log("Total:", summary.total);
console.log("HIGH_CONFIDENCE:", summary.high_confidence);
console.log("MEDIUM_CONFIDENCE:", summary.medium_confidence);
console.log("MANUAL_REVIEWED:", summary.manual_reviewed);
console.log("UNMAPPED:", summary.unmapped);
console.log("UPSTOX_FAILED:", summary.upstox_failed);

console.log("\nIndustry Distribution:");

Object.entries(industryCounts)
  .sort((a, b) => b[1] - a[1])
  .forEach(([industry, count]) => {
    console.log(
      `${industry.padEnd(25)} ${count}`
    );
  });

console.log("\nOutput:");
console.log(OUTPUT);