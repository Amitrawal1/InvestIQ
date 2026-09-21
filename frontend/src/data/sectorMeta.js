// Presentation-only details per sector slug (names, ids and counts come from the DB)
const sectorMeta = {
  "financial-services": {
    description: "Banks, NBFC, Insurance, FinTech",
    image: "https://images.unsplash.com/photo-1559526324-593bc073d938?auto=format&fit=crop&w=900&q=80",
  },
  technology: {
    description: "IT Services, Software, AI, Cybersecurity",
    image: "https://images.unsplash.com/photo-1518770660439-4636190af475?auto=format&fit=crop&w=900&q=80",
  },
  "healthcare-pharmaceuticals": {
    description: "Pharma, Hospitals, Diagnostics",
    image: "https://images.unsplash.com/photo-1576091160399-112ba8d25d1d?auto=format&fit=crop&w=900&q=80",
  },
  "energy-utilities": {
    description: "Oil & Gas, Power, Renewable, Solar, Coal",
    image: "https://images.unsplash.com/photo-1473341304170-971dccb5ac1e?auto=format&fit=crop&w=900&q=80",
  },
  "automobile-mobility": {
    description: "Automobiles, EV, Auto Components",
    image: "https://images.unsplash.com/photo-1492144534655-ae79c964c9d7?auto=format&fit=crop&w=900&q=80",
  },
  "consumer-fmcg": {
    description: "Food, Beverages, Retail, Consumer Durables",
    image: "https://images.unsplash.com/photo-1542838132-92c53300491e?auto=format&fit=crop&w=900&q=80",
  },
  "industrials-infrastructure": {
    description: "Manufacturing, Construction, Capital Goods",
    image: "https://images.unsplash.com/photo-1504917595217-d4dc5ebe6122?auto=format&fit=crop&w=900&q=80",
  },
  "metals-mining-chemicals": {
    description: "Steel, Mining, Chemicals, Cement",
    image: "https://images.unsplash.com/photo-1513828583688-c52646db42da?auto=format&fit=crop&w=900&q=80",
  },
  "real-estate-construction": {
    description: "Real Estate, Housing, Building Materials",
    image: "https://images.unsplash.com/photo-1560518883-ce09059eeffa?auto=format&fit=crop&w=900&q=80",
  },
  "services-others": {
    description: "Telecom, Logistics, Aviation, Hotels, Media",
    image: "https://images.unsplash.com/photo-1436491865332-7a61a109cc05?auto=format&fit=crop&w=900&q=80",
  },
};

export const getSectorMeta = (slug) => sectorMeta[slug] || {};

export const pad = (n) => String(n).padStart(2, "0");
export const fmt = (n) => Number(n || 0).toLocaleString("en-IN");
