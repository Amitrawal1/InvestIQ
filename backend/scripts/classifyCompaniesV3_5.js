const fs = require("fs");
const path = require("path");

const INPUT = path.join(
  __dirname,
  "upstox_classification_v3_4_preview.json"
);

const OUTPUT = path.join(
  __dirname,
  "upstox_classification_v3_5_preview.json"
);

/*
|--------------------------------------------------------------------------
| Exact company overrides
|--------------------------------------------------------------------------
| Only companies that were UNMAPPED in V3.4 are handled here.
| Symbol is used instead of name because it is stable.
|
| confidence:
| 95 = strong/direct business match
| 85 = reasonable taxonomy fit
| 75 = weaker taxonomy fit
|--------------------------------------------------------------------------
*/

const OVERRIDES = {

  // ---------------- FINANCIAL SERVICES ----------------

  "360ONE": ["Asset Management", 95],
  "ANANDRATHI": ["Asset Management", 95],
  "CAMS": ["Asset Management", 95],
  "PRUDENT": ["Asset Management", 95],
  "SBIFUNDS": ["Asset Management", 95],
  "TATAINVEST": ["Asset Management", 95],

  "NORTHARC": ["NBFC", 95],
  "SATIN": ["NBFC", 95],
  "TATACAP": ["NBFC", 95],

  "BSE": ["Other Services", 95],
  "IFCI": ["Other Services", 90],
  "MCX": ["Other Services", 95],
  "RECLTD": ["Other Services", 90],
  "DELPHIFX": ["Other Services", 90],
  "ALGOQUANT": ["Other Services", 85],

  // ---------------- TECHNOLOGY ----------------

  "COFORGE": ["Software", 95],
  "FRACTAL": ["Artificial Intelligence", 95],
  "LATENTVIEW": ["Software", 95],
  "SIGMA": ["Software", 95],
  "E2E": ["IT Services", 90],
  "DIGITIDE": ["IT Services", 90],
  "ONEPOINT": ["IT Services", 90],
  "SAGILITY": ["IT Services", 90],
  "DUGLOBAL": ["IT Services", 85],
  "SPCENET": ["IT Services", 85],

  "HCL-INSYS": ["Hardware", 95],
  "COMPINFO": ["Hardware", 95],
  "REDINGTON": ["Hardware", 95],
  "RPTECH": ["Hardware", 95],
  "TVSELECT": ["Hardware", 90],

  // ---------------- HEALTHCARE ----------------

  "AJOONI": ["Pharmaceuticals", 85],
  "NOVARTIND": ["Pharmaceuticals", 95],
  "SYNGENE": ["Pharmaceuticals", 95],
  "SUNREST": ["Pharmaceuticals", 85],

  "DENTALKART": ["Medical Devices", 95],

  // ---------------- AUTOMOBILE ----------------

  "IMPAL": ["Auto Components", 90],
  "OMAXAUTO": ["Auto Components", 95],
  "RKFORGE": ["Auto Components", 95],
  "STEELCAS": ["Auto Components", 90],
  "STUDDS": ["Auto Components", 90],
  "MAJESAUT": ["Automobiles", 90],

  // ---------------- CONSUMER / FMCG ----------------

  "HONASA": ["FMCG", 95],
  "SHANTHALA": ["FMCG", 95],
  "FIRSTCRY": ["Retail", 95],
  "V2RETAIL": ["Retail", 95],
  "PATELRMART": ["Retail", 95],
  "CELLPOINT": ["Retail", 85],

  "MVGJL": ["Consumer Services", 90],
  "MUFTI": ["Consumer Services", 90],
  "SREEL": ["Consumer Services", 90],
  "LLOYDS": ["Consumer Services", 85],

  "CELLECOR": ["Consumer Durables", 95],
  "FOCE": ["Consumer Durables", 85],

  "SSDL": ["Retail", 90],
  "CRAVATEX": ["Consumer Services", 85],

  // ---------------- FOOD & BEVERAGES ----------------

  "SAKUMA": ["Food & Beverages", 90],
  "UMAEXPORTS": ["Food & Beverages", 85],
  "VENKEYS": ["Food & Beverages", 95],
  "SHEETAL": ["Food & Beverages", 85],

  // ---------------- ENERGY ----------------

  "PRABHA": ["Oil & Gas", 90],
  "PREMIERENE": ["Solar Energy", 95],
  "KOTYARK": ["Renewable Energy", 95],
  "TRUALT": ["Renewable Energy", 95],

  // ---------------- CHEMICALS ----------------

  "JUBLCPL": ["Chemicals", 90],
  "KAMOPAINTS": ["Chemicals", 90],
  "SIRCA": ["Chemicals", 95],
  "SRD": ["Chemicals", 95],
  "RCDL": ["Chemicals", 90],
  "SIDDHIKA": ["Chemicals", 95],
  "UNIENTER": ["Chemicals", 85],

  // ---------------- METALS / MINING ----------------

  "REGAAL": ["Metals & Mining", 90],
  "NRL": ["Manufacturing", 85],

  // ---------------- INDUSTRIALS ----------------

  "3MINDIA": ["Manufacturing", 95],
  "MALLCOM": ["Manufacturing", 95],
  "MANAKSIA": ["Manufacturing", 85],
  "SIGIND": ["Manufacturing", 90],
  "COOLCAPS": ["Manufacturing", 95],

  "WHBRADY": ["Capital Goods", 90],
  "TEMBO": ["Engineering", 90],
  "AILIMITED": ["Engineering", 85],

  // ---------------- INFRASTRUCTURE / REAL ESTATE ----------------

  "AWFIS": ["Real Estate", 95],
  "KONTOR": ["Real Estate", 95],
  "PACEDIGITK": ["Infrastructure", 90],

  // ---------------- LOGISTICS ----------------

  "LEAPIND": ["Logistics", 95],

  // ---------------- SERVICES ----------------

  "AARVI": ["Other Services", 90],
  "ABANSENT": ["Other Services", 85],
  "BLS": ["Other Services", 95],
  "BLSE": ["Other Services", 95],
  "KAPSTON": ["Other Services", 95],
  "KRYSTAL": ["Other Services", 95],
  "QUESS": ["Other Services", 95],
  "TEAMLEASE": ["Other Services", 95],
  "UDS": ["Other Services", 95],
  "IPSL": ["Other Services", 95],
  "SPECTSTM": ["Other Services", 95],
  "INFOLLION": ["Other Services", 95],
  "PROPEQUITY": ["Other Services", 90],
  "SERVICE": ["Other Services", 95],
  "DYNAMIC": ["Other Services", 90],
  "GCSL": ["Other Services", 85],
  "STCINDIA": ["Other Services", 85],
  "MMTC": ["Other Services", 85],
  "MSTCLTD": ["Other Services", 90],
  "SICAGEN": ["Other Services", 80],
  "SHRENIK": ["Other Services", 80],
  "KCK": ["Other Services", 80],
  "THACKER": ["Other Services", 80],

  // ---------------- MEDIA / ENTERTAINMENT ----------------

  "AMAGI": ["Media & Entertainment", 95],
  "QUINT": ["Media & Entertainment", 95],
  "SIGNPOST": ["Media & Entertainment", 95],
  "TOUCHWOOD": ["Media & Entertainment", 90],
  "MAXPOSURE": ["Media & Entertainment", 95],
  "GRAPHISAD": ["Media & Entertainment", 95],
  "CRAYONS": ["Media & Entertainment", 95],
  "VERTOZ": ["Media & Entertainment", 90],

  // ---------------- HOSPITALITY / TOURISM ----------------

  "PRAVEG": ["Hotels & Hospitality", 90],

  // ---------------- TELECOM ----------------

  "OPTIEMUS": ["Telecom", 85],

  // ---------------- AVIATION ----------------

  "DRONE": ["Aviation", 85],

  // ---------------- MOBILITY ----------------

  "SHREEOSFM": ["Mobility Services", 90],

  // ---------------- INSURANCE ----------------

  "TURTLEMINT": ["Insurance", 95],

  // ---------------- CEMENT ----------------

  "PRSMJOHNSN": ["Cement", 95],

  // ---------------- SPECIAL CASES ----------------

  "ADANIENT": ["Other Services", 75],
  "DCMSHRIRAM": ["Chemicals", 90],
  "GRASIM": ["Chemicals", 90],
  "JUSTDIAL": ["Consumer Services", 95],
  "ABLBL": ["Consumer Services", 90],
  "AARNAV": ["Consumer Services", 75],
  "DELTACORP": ["Consumer Services", 90],
  "FMNL": ["Real Estate", 85],
  "RTNINDIA": ["Other Services", 75],
  "NIRAJISPAT": ["Metals & Mining", 85],
  "ASPINWALL": ["Other Services", 75],
  "BALMLAWRIE": ["Other Services", 75],
  "GILLANDERS": ["Other Services", 75],
  "JAYKAY": ["Other Services", 75],
  "BILVYAPAR": ["Other Services", 75],
  "CROWN": ["Capital Goods", 80],
  "AEROFLEX": ["Other Services", 75],
  "AGRITECH": ["Other Services", 75],
  "BSHSL": ["Other Services", 75],
  "INDOUS": ["Other Services", 75],
  "KSCL": ["Other Services", 75],
  "NATHBIOGEN": ["Other Services", 75],
  "NIRMAN": ["Other Services", 75],
  "USASEEDS": ["Other Services", 75],
  "MGEL": ["Other Services", 75],
  "MSL": ["Other Services", 75],
  "BBTC": ["Other Services", 75],
  "OSWALAGRO": ["Chemicals", 80],
  "ESSENTIA": ["Other Services", 75],
  "HALDER": ["Other Services", 75],
  "KOTHARIPRO": ["Other Services", 75],
  "LAHOTIOV": ["Other Services", 75],
  "MANBRO": ["Other Services", 75],
  "MITTAL": ["Other Services", 75],
  "METROGLOBL": ["Other Services", 75],
  "GOYALALUM": ["Other Services", 75],
  "REDINGTON": ["Hardware", 95],
  "AGARWALFT": ["Building Materials", 90],
  "AGUL": ["Other Services", 75],
  "SHUBHLAXMI": ["Other Services", 75],
  "PARTYCRUS": ["Consumer Services", 90],
  "DUGLOBAL": ["IT Services", 85]
};


/*
|--------------------------------------------------------------------------
| Load V3.4
|--------------------------------------------------------------------------
*/

const data = JSON.parse(
  fs.readFileSync(INPUT, "utf8")
);

const results = data.results.map(row => {

  // Never modify already classified records
  if (row.status !== "UNMAPPED") {
    return row;
  }

  const symbol = String(row.symbol || "")
    .trim()
    .toUpperCase();

  const override = OVERRIDES[symbol];

  if (!override) {
    return {
      ...row,
      status: "UNMAPPED",
      confidence: null,
      matched_rules: [
        ...(row.matched_rules || []),
        "V3.5_NO_EXACT_OVERRIDE"
      ]
    };
  }

  const [industry, confidence] = override;

  return {
    ...row,
    investiq_industry: industry,
    confidence,
    status: confidence >= 90
      ? "HIGH_CONFIDENCE"
      : "MEDIUM_CONFIDENCE",
    matched_rules: [
      ...(row.matched_rules || []),
      `V3.5_EXACT_SYMBOL_${symbol}`
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

  low_confidence: results.filter(
    x => x.status === "LOW_CONFIDENCE"
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

const output = {
  generated_at: new Date().toISOString(),
  version: "V3.5",
  summary,
  industry_counts: industryCounts,
  results
};

fs.writeFileSync(
  OUTPUT,
  JSON.stringify(output, null, 2)
);

console.log("\n=================================");
console.log("InvestIQ Classification V3.5");
console.log("=================================");
console.log("Total:", summary.total);
console.log("HIGH_CONFIDENCE:", summary.high_confidence);
console.log("MEDIUM_CONFIDENCE:", summary.medium_confidence);
console.log("LOW_CONFIDENCE:", summary.low_confidence);
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