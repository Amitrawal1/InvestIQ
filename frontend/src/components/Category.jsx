import React from "react";
import { motion } from "motion/react";
import { ArrowUpRight } from "lucide-react";
import { MonoLabel } from "./ui";

const categories = [
  {
    title: "Financial Services",
    description: "Banks, NBFC, Insurance, FinTech",
    image: "https://images.unsplash.com/photo-1559526324-593bc073d938?auto=format&fit=crop&w=900&q=80",
  },
  {
    title: "Technology",
    description: "IT Services, Software, AI, Cybersecurity",
    image: "https://images.unsplash.com/photo-1518770660439-4636190af475?auto=format&fit=crop&w=900&q=80",
  },
  {
    title: "Healthcare & Pharmaceuticals",
    description: "Pharma, Hospitals, Diagnostics",
    image: "https://images.unsplash.com/photo-1576091160399-112ba8d25d1d?auto=format&fit=crop&w=900&q=80",
  },
  {
    title: "Energy & Utilities",
    description: "Oil & Gas, Power, Renewable, Solar, Coal",
    image: "https://images.unsplash.com/photo-1473341304170-971dccb5ac1e?auto=format&fit=crop&w=900&q=80",
  },
  {
    title: "Automobile & Mobility",
    description: "Automobiles, EV, Auto Components",
    image: "https://images.unsplash.com/photo-1492144534655-ae79c964c9d7?auto=format&fit=crop&w=900&q=80",
  },
  {
    title: "Consumer & FMCG",
    description: "Food, Beverages, Retail, Consumer Durables",
    image: "https://images.unsplash.com/photo-1601598851547-4302969d9a2c?auto=format&fit=crop&w=900&q=80",
  },
  {
    title: "Industrials & Infrastructure",
    description: "Manufacturing, Construction, Capital Goods",
    image: "https://images.unsplash.com/photo-1504917595217-d4dc5ebe6122?auto=format&fit=crop&w=900&q=80",
  },
  {
    title: "Metals, Mining & Chemicals",
    description: "Steel, Mining, Chemicals, Cement",
    image: "https://images.unsplash.com/photo-1513828583688-c52646db42da?auto=format&fit=crop&w=900&q=80",
  },
  {
    title: "Real Estate & Construction",
    description: "Real Estate, Housing, Building Materials",
    image: "https://images.unsplash.com/photo-1560518883-ce09059eeffa?auto=format&fit=crop&w=900&q=80",
  },
  {
    title: "Services & Others",
    description: "Telecom, Logistics, Aviation, Hotels, Media",
    image: "https://images.unsplash.com/photo-1436491865332-7a61a109cc05?auto=format&fit=crop&w=900&q=80",
  },
];

const Category = () => {
  return (
    <>
      <style>{`
        .category-card {
          flex: 1 1 0%;
          min-width: 0;
          transition: flex-grow 600ms cubic-bezier(0.16, 1, 0.3, 1);
        }
        .category-card:hover { flex-grow: 3; }
      `}</style>

      <section className="w-full">
        {/* Heading */}
        <div className="px-6 md:px-16 pt-24 md:pt-32 mb-12 flex flex-col xl:flex-row justify-between items-start gap-8">
          <motion.h2
            initial={{ y: 40, opacity: 0 }}
            whileInView={{ y: 0, opacity: 1 }}
            viewport={{ once: true, margin: "-100px" }}
            transition={{ duration: 0.8 }}
            className="xl:w-[60%] text-[1.8rem] md:text-[3rem] lg:text-[3.6rem] leading-[1.1] font-medium tracking-tight text-white"
          >
            Explore the market, one sector at a time.
          </motion.h2>

          <div className="xl:w-[35%] flex flex-col xl:items-end xl:text-right">
            <p className="text-[10px] font-mono tracking-widest text-gray-400 uppercase mb-6 leading-relaxed">
              Ten sectors. Thousands of listed companies.<br />One view of the news that moves them.
            </p>
            <div className="flex flex-wrap gap-3 xl:justify-end">
              {["NSE", "BSE", "Sector-wise"].map((pill) => (
                <span
                  key={pill}
                  className="px-5 py-2 rounded-full border border-gray-600 text-[9px] font-mono tracking-widest uppercase text-gray-300 hover:bg-white hover:text-black hover:border-white transition-colors duration-300 cursor-default"
                >
                  {pill}
                </span>
              ))}
            </div>
          </div>
        </div>

        {/* Cards - desktop accordion, mobile scroll */}
        <div className="px-6 md:px-16">
          <div className="flex h-[420px] w-full gap-2 overflow-x-auto md:overflow-hidden">
            {categories.map((category, index) => (
              <div
                key={category.title}
                className="category-card group relative cursor-pointer overflow-hidden rounded-xl border border-gray-800 bg-[#0a0a0a] min-w-[200px] md:min-w-0"
              >
                <img
                  src={category.image}
                  alt=""
                  onError={(e) => { e.currentTarget.style.display = "none"; }}
                  className="absolute inset-0 h-full w-full object-cover grayscale opacity-60 transition-all duration-700 group-hover:grayscale-0 group-hover:opacity-90 group-hover:scale-105"
                />
                <div className="absolute inset-0 bg-gradient-to-t from-[#050011] via-[#050011]/40 to-transparent" />

                <div className="absolute top-0 left-0 w-full p-4 flex justify-between items-start">
                  <MonoLabel className="text-gray-300">{String(index + 1).padStart(2, "0")}</MonoLabel>
                  <ArrowUpRight size={18} strokeWidth={1} className="text-white opacity-0 transition-opacity duration-300 group-hover:opacity-100" />
                </div>

                <div className="absolute bottom-0 left-0 w-full p-4">
                  <h3 className="text-[14px] font-medium tracking-tight leading-tight text-white line-clamp-2 break-words transition-[font-size] duration-500 group-hover:text-lg">
                    {category.title}
                  </h3>
                  <p className="max-w-[240px] max-h-0 overflow-hidden text-[10px] font-mono tracking-widest uppercase leading-relaxed text-gray-400 opacity-0 transition-all duration-500 group-hover:mt-2 group-hover:max-h-16 group-hover:opacity-100">
                    {category.description}
                  </p>
                </div>
              </div>
            ))}
          </div>
        </div>
      </section>
    </>
  );
};

export default Category;
