const fs = require("fs");
const path = require("path");
const axios = require("axios");

require("dotenv").config({
  path: path.join(__dirname, "../.env")
});

const db = require("../config/db");

const TOKEN_PATH = path.join(
  __dirname,
  "../../ml/upstox_access_token.txt"
);

const OUTPUT_PATH = path.join(
  __dirname,
  "upstox_bulk_classification_v2_preview.json"
);

const REQUEST_DELAY = 300;
const MAX_RETRIES = 3;

// ============================================================
// INVESTIQ INDUSTRIES
// ============================================================

const INDUSTRIES = {
  "IT Services": 1,
  "Software": 2,
  "Artificial Intelligence": 3,
  "Semiconductor": 4,
  "Hardware": 5,

  "Solar Energy": 6,
  "Renewable Energy": 7,
  "Power": 8,
  "Oil & Gas": 9,

  "Banking": 10,
  "Insurance": 11,
  "NBFC": 12,
  "Asset Management": 13,

  "Pharmaceuticals": 14,
  "Hospitals": 15,
  "Diagnostics": 16,
  "Medical Devices": 17,

  "Automobiles": 18,
  "Auto Components": 19,
  "Electric Vehicles": 20,
  "Mobility Services": 21,

  "FMCG": 22,
  "Food & Beverages": 23,
  "Retail": 24,
  "Consumer Durables": 25,
  "Consumer Services": 26,

  "Capital Goods": 27,
  "Engineering": 28,
  "Construction": 29,
  "Infrastructure": 30,
  "Manufacturing": 31,

  "Metals & Mining": 32,
  "Cement": 33,
  "Chemicals": 34,
  "Specialty Chemicals": 35,

  "Real Estate": 36,
  "Real Estate Development": 37,
  "Building Materials": 38,

  "Telecom": 39,
  "Logistics": 40,
  "Aviation": 41,
  "Hotels & Hospitality": 42,
  "Media & Entertainment": 43,
  "Education": 44,
  "Other Services": 45
};

// ============================================================
// INDUSTRY → SECTOR
// ============================================================

const INDUSTRY_TO_SECTOR = {

  "IT Services": 1,
  "Software": 1,
  "Artificial Intelligence": 1,
  "Semiconductor": 1,
  "Hardware": 1,

  "Solar Energy": 2,
  "Renewable Energy": 2,
  "Power": 2,
  "Oil & Gas": 2,

  "Banking": 3,
  "Insurance": 3,
  "NBFC": 3,
  "Asset Management": 3,

  "Pharmaceuticals": 4,
  "Hospitals": 4,
  "Diagnostics": 4,
  "Medical Devices": 4,

  "Automobiles": 5,
  "Auto Components": 5,
  "Electric Vehicles": 5,
  "Mobility Services": 5,

  "FMCG": 21,
  "Food & Beverages": 21,
  "Retail": 21,
  "Consumer Durables": 21,
  "Consumer Services": 21,

  "Capital Goods": 22,
  "Engineering": 22,
  "Construction": 22,
  "Infrastructure": 22,
  "Manufacturing": 22,

  "Metals & Mining": 23,
  "Cement": 23,
  "Chemicals": 23,
  "Specialty Chemicals": 23,

  "Real Estate": 24,
  "Real Estate Development": 24,
  "Building Materials": 24,

  "Telecom": 25,
  "Logistics": 25,
  "Aviation": 25,
  "Hotels & Hospitality": 25,
  "Media & Entertainment": 25,
  "Education": 25,
  "Other Services": 25
};

// ============================================================
// NORMALIZATION
// ============================================================

function normalize(text) {
  return String(text || "")
    .toLowerCase()
    .replace(/&/g, " and ")
    .replace(/[^a-z0-9]+/g, " ")
    .replace(/\s+/g, " ")
    .trim();
}

function sleep(ms) {
  return new Promise(resolve => setTimeout(resolve, ms));
}

// ============================================================
// UPSTOX SECTOR → CANDIDATE INDUSTRIES
// ============================================================

const SECTOR_MAP = {

  "engineering": ["Engineering"],

  "textile": ["Manufacturing"],
  "textiles": ["Manufacturing"],

  "trading": ["Other Services"],

  "steel iron products": ["Metals & Mining"],
  "steel": ["Metals & Mining"],
  "metal": ["Metals & Mining"],
  "metals": ["Metals & Mining"],
  "non ferrous metals": ["Metals & Mining"],

  "construction": ["Construction"],

  "auto ancillary": ["Auto Components"],
  "auto ancillaries": ["Auto Components"],

  "plastic products": ["Manufacturing"],
  "plastics": ["Manufacturing"],

  "consumer food": ["Food & Beverages"],
  "food products": ["Food & Beverages"],
  "food beverages": ["Food & Beverages"],

  "investment": ["Asset Management"],
  "finance": ["NBFC"],
  "nbfc": ["NBFC"],
  "housing finance": ["NBFC"],
  "financial services": ["Other Services"],

  "stock broking": ["Other Services"],
  "stock commodity brokers": ["Other Services"],

  "electric equipment": ["Capital Goods"],
  "electrical equipment": ["Capital Goods"],

  "bpo ites": ["IT Services"],

  "electronics": ["Hardware"],
  "it hardware": ["Hardware"],
  "it networking": ["IT Services"],

  "automobile": ["Automobiles"],
  "automobiles": ["Automobiles"],

  "power": ["Power"],

  "packaging": ["Manufacturing"],

  "printing and publishing": ["Media & Entertainment"],

  "agriculture": ["Other Services"],
  "fertilizers": ["Chemicals"],

  "healthcare services": ["Healthcare Services"],
  "healthcare": ["Healthcare Services"],

  "shipping": ["Logistics"],
  "courier services": ["Logistics"],
  "port": ["Logistics"],

  "breweries": ["Food & Beverages"],
  "tea coffee": ["Food & Beverages"],

  "forgings": ["Capital Goods"],
  "castings": ["Capital Goods"],
  "castings forgings fastners": ["Capital Goods"],
  "fasteners": ["Capital Goods"],
  "bearings": ["Capital Goods"],
  "compressors": ["Capital Goods"],
  "diesel engines": ["Capital Goods"],
  "welding equipment": ["Capital Goods"],
  "railways wagons": ["Capital Goods"],

  "dyes pigments": ["Chemicals"],
  "rubber products": ["Manufacturing"],
  "tyres allied": ["Auto Components"],
  "tyres": ["Auto Components"],
  "solvent extraction": ["Chemicals"],

  "travel services": ["Consumer Services"],

  "wood products": ["Building Materials"],
  "plywood boards laminates": ["Building Materials"],
  "ceramics": ["Building Materials"],
  "ceramic products": ["Building Materials"],
  "glass": ["Building Materials"],
  "refractories": ["Building Materials"],

  "aerospace defence": ["Capital Goods"],
  "defence": ["Capital Goods"],
  "ship building": ["Capital Goods"],

  "oil exploration": ["Oil & Gas"],
  "oil drill allied": ["Oil & Gas"],
  "gases fuels": ["Oil & Gas"],
  "gas transmission": ["Oil & Gas"],

  "batteries": ["Manufacturing"],
  "dry cells": ["Manufacturing"],

  "decoratives": ["Building Materials"],
  "paints": ["Chemicals"],

  "footwear": ["Manufacturing"],
  "stationery": ["Manufacturing"],
  "tobacco": ["FMCG"],
  "tobacco products": ["FMCG"],

  "jewellery": ["Consumer Services"],
  "diamond gems jewellery": ["Consumer Services"],
  "watches accessories": ["Consumer Durables"],

  "air conditioners": ["Consumer Durables"],

  "co working": ["Real Estate"],
  "real estate": ["Real Estate"],
  "housing": ["Real Estate"],

  "telecom service": ["Telecom"],
  "telecom equipment infra services": ["Telecom"],

  "insurance": ["Insurance"],

  "quick service restaurant": ["Consumer Services"],

  "recreation": ["Consumer Services"],

  "photographic products": ["Consumer Durables"]
};

// ============================================================
// DESCRIPTION RULES
//
// High-specificity business phrases get much higher scores
// than generic words.
// ============================================================

const RULES = [

  // HEALTHCARE
  {
    industry: "Diagnostics",
    weight: 100,
    words: [
      "molecular diagnostic",
      "diagnostic kit",
      "diagnostic kits",
      "diagnostic laboratory",
      "diagnostic laboratories",
      "pathology laboratory",
      "pathology laboratories",
      "pathology services",
      "diagnostic tests",
      "diagnostic testing",
      "pcr based diagnostic",
      "medical diagnostic"
    ]
  },

  {
    industry: "Hospitals",
    weight: 100,
    words: [
      "hospital",
      "hospitals",
      "hospital chain",
      "hospital services",
      "multispecialty hospital"
    ]
  },

  {
    industry: "Medical Devices",
    weight: 100,
    words: [
      "medical device",
      "medical devices",
      "surgical instrument",
      "surgical instruments",
      "medical equipment",
      "medical implants",
      "orthopedic implant"
    ]
  },

  {
    industry: "Pharmaceuticals",
    weight: 95,
    words: [
      "pharmaceutical",
      "pharmaceuticals",
      "drug manufacturer",
      "drug manufacturing",
      "pharmaceutical formulations",
      "active pharmaceutical ingredient",
      "api manufacturing",
      "generic medicines"
    ]
  },

  // FINANCE
  {
    industry: "Banking",
    weight: 100,
    words: [
      "commercial bank",
      "private sector bank",
      "public sector bank",
      "banking company",
      "banking services"
    ]
  },

  {
    industry: "Insurance",
    weight: 100,
    words: [
      "insurance company",
      "life insurance",
      "general insurance",
      "health insurance"
    ]
  },

  {
    industry: "Asset Management",
    weight: 95,
    words: [
      "asset management",
      "mutual fund",
      "portfolio management",
      "alternative investment fund",
      "investment management",
      "wealth management"
    ]
  },

  {
    industry: "NBFC",
    weight: 90,
    words: [
      "non banking financial",
      "non banking finance",
      "nbfc",
      "lending company",
      "financing company"
    ]
  },

  // TECHNOLOGY
  {
    industry: "Artificial Intelligence",
    weight: 100,
    words: [
      "artificial intelligence",
      "machine learning",
      "generative ai",
      "ai platform",
      "ai solutions"
    ]
  },

  {
    industry: "Semiconductor",
    weight: 100,
    words: [
      "semiconductor",
      "semiconductors",
      "integrated circuit",
      "microchip",
      "chip manufacturing"
    ]
  },

  {
    industry: "Software",
    weight: 90,
    words: [
      "software products",
      "software solutions",
      "software development",
      "software services",
      "saas",
      "application development"
    ]
  },

  {
    industry: "IT Services",
    weight: 85,
    words: [
      "information technology services",
      "information technology company",
      "it services",
      "technology services",
      "cloud services",
      "digital transformation",
      "it consulting"
    ]
  },

  {
    industry: "Hardware",
    weight: 90,
    words: [
      "computer hardware",
      "electronic hardware",
      "electronic equipment",
      "computer systems",
      "electronics manufacturing"
    ]
  },

  // ENERGY
  {
    industry: "Solar Energy",
    weight: 100,
    words: [
      "solar power",
      "solar energy",
      "solar module",
      "solar modules",
      "solar panel",
      "solar panels",
      "photovoltaic",
      "pv module"
    ]
  },

  {
    industry: "Renewable Energy",
    weight: 95,
    words: [
      "renewable energy",
      "wind energy",
      "wind power",
      "green energy",
      "clean energy"
    ]
  },

  {
    industry: "Power",
    weight: 95,
    words: [
      "power generation",
      "power transmission",
      "power distribution",
      "electricity generation",
      "electric utility",
      "power utility"
    ]
  },

  {
    industry: "Oil & Gas",
    weight: 100,
    words: [
      "oil and gas",
      "oil gas",
      "oil exploration",
      "oil drilling",
      "petroleum",
      "natural gas",
      "crude oil",
      "refinery",
      "refineries"
    ]
  },

  // AUTOMOBILE
  {
    industry: "Electric Vehicles",
    weight: 100,
    words: [
      "electric vehicle",
      "electric vehicles",
      "electric mobility",
      "electric scooter",
      "electric scooters",
      "electric two wheeler",
      "electric three wheeler"
    ]
  },

  {
    industry: "Auto Components",
    weight: 95,
    words: [
      "auto component",
      "auto components",
      "automotive components",
      "automotive parts",
      "vehicle components",
      "auto parts",
      "automotive ancillary"
    ]
  },

  {
    industry: "Automobiles",
    weight: 95,
    words: [
      "automobile manufacturer",
      "automobile manufacturing",
      "automotive manufacturer",
      "passenger vehicles",
      "commercial vehicles",
      "two wheeler manufacturer",
      "three wheeler manufacturer"
    ]
  },

  // CONSUMER
  {
    industry: "Food & Beverages",
    weight: 90,
    words: [
      "food products",
      "food processing",
      "food manufacturer",
      "food manufacturing",
      "beverages",
      "food and beverage",
      "dairy products",
      "edible oils",
      "sugar manufacturing",
      "sugar mill"
    ]
  },

  {
    industry: "FMCG",
    weight: 90,
    words: [
      "fast moving consumer goods",
      "fmcg",
      "consumer packaged goods",
      "personal care products"
    ]
  },

  {
    industry: "Retail",
    weight: 90,
    words: [
      "retail company",
      "retail business",
      "retail stores",
      "retailing",
      "e commerce",
      "ecommerce"
    ]
  },

  {
    industry: "Consumer Durables",
    weight: 90,
    words: [
      "consumer durable",
      "consumer durables",
      "home appliances",
      "electrical appliances",
      "consumer electronics"
    ]
  },

  // INDUSTRIAL
  {
    industry: "Engineering",
    weight: 90,
    words: [
      "engineering services",
      "engineering solutions",
      "engineering company",
      "engineering projects",
      "engineering procurement construction"
    ]
  },

  {
    industry: "Construction",
    weight: 95,
    words: [
      "construction company",
      "construction services",
      "construction projects",
      "construction contractor",
      "construction and engineering"
    ]
  },

  {
    industry: "Infrastructure",
    weight: 90,
    words: [
      "infrastructure development",
      "infrastructure projects",
      "infrastructure company",
      "infrastructure services"
    ]
  },

  {
    industry: "Capital Goods",
    weight: 90,
    words: [
      "capital goods",
      "industrial equipment",
      "industrial machinery",
      "heavy equipment",
      "machinery manufacturing",
      "industrial equipment manufacturer"
    ]
  },

  {
    industry: "Manufacturing",
    weight: 75,
    words: [
      "manufacturing company",
      "manufacturing facility",
      "manufactures and sells",
      "manufacturing and sale",
      "industrial manufacturing"
    ]
  },

  // METALS / CHEMICALS
  {
    industry: "Cement",
    weight: 100,
    words: [
      "cement manufacturing",
      "cement manufacturer",
      "cement products",
      "cement plant",
      "clinker"
    ]
  },

  {
    industry: "Specialty Chemicals",
    weight: 100,
    words: [
      "specialty chemical",
      "specialty chemicals",
      "speciality chemicals",
      "performance chemicals",
      "specialty chemical products"
    ]
  },

  {
    industry: "Chemicals",
    weight: 85,
    words: [
      "chemical manufacturing",
      "chemical manufacturer",
      "chemical products",
      "industrial chemicals",
      "chemicals manufacturer"
    ]
  },

  {
    industry: "Metals & Mining",
    weight: 95,
    words: [
      "mining company",
      "mining operations",
      "mineral mining",
      "mineral products",
      "metal manufacturing",
      "steel manufacturing",
      "iron and steel",
      "non ferrous metals",
      "aluminium manufacturing",
      "copper manufacturing",
      "zinc manufacturing"
    ]
  },

  // REAL ESTATE
  {
    industry: "Real Estate Development",
    weight: 100,
    words: [
      "real estate development",
      "property development",
      "realty development",
      "real estate developer",
      "property developer",
      "real estate projects"
    ]
  },

  {
    industry: "Real Estate",
    weight: 90,
    words: [
      "real estate",
      "realty",
      "property leasing",
      "real estate leasing",
      "property management"
    ]
  },

  {
    industry: "Building Materials",
    weight: 90,
    words: [
      "building materials",
      "construction materials",
      "building products",
      "sanitaryware",
      "ceramic tiles",
      "plywood",
      "laminates"
    ]
  },

  // SERVICES
  {
    industry: "Telecom",
    weight: 100,
    words: [
      "telecommunication",
      "telecommunications",
      "telecom services",
      "mobile network",
      "wireless communication"
    ]
  },

  {
    industry: "Logistics",
    weight: 95,
    words: [
      "logistics company",
      "logistics services",
      "freight services",
      "warehousing",
      "supply chain",
      "cargo transportation",
      "shipping services"
    ]
  },

  {
    industry: "Aviation",
    weight: 100,
    words: [
      "airline",
      "airlines",
      "aviation company",
      "airport operator",
      "air transport"
    ]
  },

  {
    industry: "Hotels & Hospitality",
    weight: 100,
    words: [
      "hotel",
      "hotels",
      "hospitality",
      "resort",
      "resorts"
    ]
  },

  {
    industry: "Media & Entertainment",
    weight: 95,
    words: [
      "media company",
      "entertainment company",
      "television broadcasting",
      "broadcasting company",
      "film production",
      "digital media",
      "publishing company"
    ]
  },

  {
    industry: "Education",
    weight: 95,
    words: [
      "education services",
      "educational services",
      "school",
      "schools",
      "university",
      "online learning",
      "edtech"
    ]
  }
];

// ============================================================
// UPSTOX API
// ============================================================

async function getCompanyProfile(isin, token) {

  const url =
    `https://api.upstox.com/v2/fundamentals/${encodeURIComponent(isin)}/profile`;

  for (let attempt = 1; attempt <= MAX_RETRIES; attempt++) {

    try {

      const response = await axios.get(url, {
        headers: {
          Authorization: `Bearer ${token}`,
          Accept: "application/json"
        },
        timeout: 15000
      });

      return {
        success: true,
        data: response.data?.data || null
      };

    } catch (error) {

      const status = error.response?.status;

      if (status === 401) {
        return {
          success: false,
          error: "INVALID_TOKEN",
          status
        };
      }

      if (attempt === MAX_RETRIES) {
        return {
          success: false,
          error:
            error.response?.data?.errors?.[0]?.message ||
            error.message ||
            "API_ERROR",
          status
        };
      }

      await sleep(1000 * attempt);
    }
  }
}

// ============================================================
// CLASSIFICATION
// ============================================================

function classifyCompany(company, data) {

  const profile =
    data?.company_profile ||
    data?.companyProfile ||
    {};

  const upstoxSector =
    data?.sector ||
    profile?.sector ||
    "";

  const description =
    profile?.description ||
    profile?.business_description ||
    profile?.businessDescription ||
    "";

  const sectorText = normalize(upstoxSector);

  const fullText = normalize(
    `${company.name} ${company.symbol} ${description}`
  );

  const candidates = new Map();

  // ----------------------------------------------------------
  // 1. HIGH-QUALITY DESCRIPTION MATCH
  // ----------------------------------------------------------

  for (const rule of RULES) {

    for (const phrase of rule.words) {

      if (fullText.includes(normalize(phrase))) {

        const current = candidates.get(rule.industry) || 0;

        candidates.set(
          rule.industry,
          Math.max(current, rule.weight)
        );
      }
    }
  }

  // ----------------------------------------------------------
  // 2. UPSTOX SECTOR MATCH
  // ----------------------------------------------------------

  const sectorCandidates = SECTOR_MAP[sectorText] || [];

  for (const industry of sectorCandidates) {

    const current = candidates.get(industry) || 0;

    // Sector signal is strong, but description can beat it.
    candidates.set(
      industry,
      Math.max(current, 70)
    );
  }

  // ----------------------------------------------------------
  // 3. SPECIAL CASES
  // ----------------------------------------------------------

  // Healthcare should beat generic "Agrochemicals" etc.
  if (
    fullText.includes("diagnostic") ||
    fullText.includes("pcr") ||
    fullText.includes("pathology")
  ) {
    candidates.set(
      "Diagnostics",
      Math.max(candidates.get("Diagnostics") || 0, 110)
    );
  }

  // Mining/minerals should beat generic services.
  if (
    fullText.includes("mining") ||
    fullText.includes("mineral products") ||
    sectorText.includes("mineral")
  ) {
    candidates.set(
      "Metals & Mining",
      Math.max(candidates.get("Metals & Mining") || 0, 105)
    );
  }

  // Rubber products are manufacturing unless clearly auto-related.
  if (
    sectorText.includes("rubber products") &&
    !fullText.includes("automotive") &&
    !fullText.includes("auto component")
  ) {
    candidates.set(
      "Manufacturing",
      Math.max(candidates.get("Manufacturing") || 0, 80)
    );
  }

  // Textile companies → Manufacturing.
  if (sectorText === "textile" || sectorText === "textiles") {
    candidates.set(
      "Manufacturing",
      Math.max(candidates.get("Manufacturing") || 0, 80)
    );
  }

  // ----------------------------------------------------------
  // NO MATCH
  // ----------------------------------------------------------

  if (candidates.size === 0) {

    return {
      industry: null,
      industry_id: null,
      sector_id: null,
      confidence: 0,
      status: "UNMAPPED",
      candidates: []
    };
  }

  const sorted = [...candidates.entries()]
    .sort((a, b) => b[1] - a[1]);

  const [bestIndustry, bestScore] = sorted[0];
  const secondScore = sorted[1]?.[1] || 0;

  const gap = bestScore - secondScore;

  // ----------------------------------------------------------
  // CONFIDENCE
  // ----------------------------------------------------------

  let confidence = Math.min(100, bestScore);

  let status = "CLASSIFIED";

  if (
    bestScore < 80 ||
    (secondScore >= 85 && gap < 10)
  ) {
    status = "LOW_CONFIDENCE";
  }

  return {
    industry: bestIndustry,
    industry_id: INDUSTRIES[bestIndustry],
    sector_id: INDUSTRY_TO_SECTOR[bestIndustry],
    confidence,
    status,

    candidates: sorted
      .slice(0, 5)
      .map(([industry, score]) => ({
        industry,
        score
      }))
  };
}

// ============================================================
// MAIN
// ============================================================

async function main() {

  console.log("\n========================================");
  console.log("InvestIQ Upstox Classification V2");
  console.log("========================================\n");

  if (!fs.existsSync(TOKEN_PATH)) {
    throw new Error(`Token file not found: ${TOKEN_PATH}`);
  }

  const token = fs.readFileSync(TOKEN_PATH, "utf8").trim();

  if (!token) {
    throw new Error("Upstox access token is empty.");
  }

  console.log("Upstox token loaded: true\n");

  const [companies] = await db.query(`
    SELECT
      id,
      name,
      symbol,
      isin
    FROM companies
    WHERE industry_id IS NULL
       OR sector_id IS NULL
    ORDER BY id
  `);

  console.log(`Companies to classify: ${companies.length}\n`);

  const results = [];

  let apiSuccess = 0;
  let apiFailed = 0;
  let classified = 0;
  let lowConfidence = 0;
  let unmapped = 0;

  for (let i = 0; i < companies.length; i++) {

    const company = companies[i];

    process.stdout.write(
      `[${i + 1}/${companies.length}] ` +
      `${company.symbol} - ${company.name}`
    );

    if (!company.isin) {

      console.log(" → NO ISIN");

      results.push({
        company_id: company.id,
        name: company.name,
        symbol: company.symbol,
        isin: null,
        status: "UPSTOX_FAILED",
        error: "NO_ISIN"
      });

      apiFailed++;
      continue;
    }

    const response =
      await getCompanyProfile(company.isin, token);

    if (!response.success) {

      console.log(` → ${response.error}`);

      results.push({
        company_id: company.id,
        name: company.name,
        symbol: company.symbol,
        isin: company.isin,
        status: "UPSTOX_FAILED",
        error: response.error,
        http_status: response.status || null
      });

      apiFailed++;

      if (response.error === "INVALID_TOKEN") {
        console.log("\n❌ INVALID TOKEN — STOPPING\n");
        break;
      }

      await sleep(REQUEST_DELAY);
      continue;
    }

    apiSuccess++;

    const profile =
      response.data?.company_profile ||
      response.data?.companyProfile ||
      {};

    const upstoxSector =
      response.data?.sector ||
      profile?.sector ||
      null;

    const description =
      profile?.description ||
      profile?.business_description ||
      profile?.businessDescription ||
      null;

    const classification =
      classifyCompany(company, response.data);

    if (classification.status === "CLASSIFIED") {
      classified++;
    }

    if (classification.status === "LOW_CONFIDENCE") {
      lowConfidence++;
    }

    if (classification.status === "UNMAPPED") {
      unmapped++;
    }

    console.log(
      ` → ${classification.industry || "UNMAPPED"} ` +
      `[${classification.status}]`
    );

    results.push({

      company_id: company.id,
      name: company.name,
      symbol: company.symbol,
      isin: company.isin,

      upstox_sector: upstoxSector,
      company_profile: description,

      investiq_industry:
        classification.industry,

      industry_id:
        classification.industry_id,

      sector_id:
        classification.sector_id,

      confidence:
        classification.confidence,

      status:
        classification.status,

      candidates:
        classification.candidates
    });

    await sleep(REQUEST_DELAY);
  }

  const output = {

    generated_at:
      new Date().toISOString(),

    version: "V2",

    database_modified: false,

    summary: {

      total_companies:
        companies.length,

      processed:
        results.length,

      api_success:
        apiSuccess,

      api_failed:
        apiFailed,

      classified:
        classified,

      low_confidence:
        lowConfidence,

      unmapped:
        unmapped
    },

    results
  };

  fs.writeFileSync(
    OUTPUT_PATH,
    JSON.stringify(output, null, 2)
  );

  console.log("\n========================================");
  console.log("V2 CLASSIFICATION COMPLETE");
  console.log("========================================\n");

  console.log(`Total:          ${companies.length}`);
  console.log(`Processed:      ${results.length}`);
  console.log(`API Success:    ${apiSuccess}`);
  console.log(`API Failed:     ${apiFailed}`);
  console.log(`Classified:     ${classified}`);
  console.log(`Low Confidence: ${lowConfidence}`);
  console.log(`Unmapped:       ${unmapped}`);

  console.log("\nPreview saved:");
  console.log(OUTPUT_PATH);

  console.log("\n⚠ DATABASE WAS NOT MODIFIED ⚠\n");

  await db.end();
}

main().catch(async error => {

  console.error("\n❌ ERROR:");
  console.error(error.message);

  try {
    await db.end();
  } catch (_) {}

  process.exit(1);
});