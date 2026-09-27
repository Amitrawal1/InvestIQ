import React from "react";
import { Link } from "react-router-dom";
import { motion } from "motion/react";
import { ArrowUpRight, Landmark, Layers, LayoutGrid } from "lucide-react";
import { MonoLabel, PillTag } from "./ui";
import SourcePill from "./SourcePill";
import { useSectors } from "../hooks/useSectorData";
import { getSectorMeta, pad, fmt } from "../data/sectorMeta";

const StatusLine = ({ children, tone = "muted" }) => (
  <div className={`px-6 md:px-16 py-16 text-center text-[10px] font-mono tracking-widest uppercase ${tone === "error" ? "text-red-400" : "text-gray-500"}`}>
    {children}
  </div>
);

// Home page "Explore the market" section: one card per DB sector.
// Each card opens that sector's page with its full company list.
const Category = () => {
  const { sectors, source, loading, error } = useSectors();
  const totalCompanies = sectors.reduce((sum, s) => sum + Number(s.company_count || 0), 0);

  return (
    <>
      <style>{`
        .category-card {
          flex: 1 1 0%;
          min-width: 0;
          transition: flex-grow 600ms cubic-bezier(0.16, 1, 0.3, 1), border-color 300ms;
        }
        .category-card:hover { flex-grow: 3; }
      `}</style>

      <section id="sectors" className="w-full scroll-mt-24">
        {/* Heading */}
        <div className="px-6 md:px-16 pt-24 md:pt-32 mb-12 flex flex-col xl:flex-row justify-between items-start gap-8">
          <motion.h2
            initial={{ y: 40, opacity: 0 }}
            whileInView={{ y: 0, opacity: 1 }}
            viewport={{ once: true, margin: "-100px" }}
            transition={{ duration: 0.8 }}
            className="xl:flex-1 xl:max-w-[760px] text-[1.8rem] md:text-[3rem] lg:text-[3.6rem] leading-[1.1] font-medium tracking-tight text-white"
          >
            Explore the market, one sector at a time.
          </motion.h2>

          <div className="xl:shrink-0 flex flex-col xl:items-end xl:text-right">
            <p className="text-[10px] font-mono tracking-widest text-gray-400 uppercase mb-6 leading-relaxed">
              {sectors.length
                ? <>{sectors.length} sectors. {fmt(totalCompanies)} listed companies.<br />Pick a sector to see every company in it.</>
                : <>Sectors and listed companies<br />from the InvestIQ database.</>}
            </p>
            <div className="flex flex-wrap gap-3 xl:justify-end">
              <SourcePill source={source} />
              <PillTag icon={Landmark}>NSE</PillTag>
              <PillTag icon={Layers}>Equity + SME</PillTag>
              <PillTag icon={LayoutGrid}>Sector-wise</PillTag>
            </div>
          </div>
        </div>

        {error && (
          <StatusLine tone="error">
            Couldn't load sectors. Start the backend with: cd backend &amp;&amp; npm run dev
          </StatusLine>
        )}
        {loading && <StatusLine>Loading sectors…</StatusLine>}

        {sectors.length > 0 && (
          <div className="px-6 md:px-16">
            <div className="flex h-[420px] w-full gap-2 overflow-x-auto md:overflow-hidden">
              {sectors.map((sector, index) => {
                const meta = getSectorMeta(sector.slug);

                return (
                  <Link
                    key={sector.id}
                    to={`/sectors/${sector.slug}`}
                    className="category-card group relative overflow-hidden rounded-xl border border-gray-800 hover:border-gray-500 bg-surface min-w-[200px] md:min-w-0"
                  >
                    {meta.image && (
                      <img
                        src={meta.image}
                        alt=""
                        onError={(e) => { e.currentTarget.style.display = "none"; }}
                        className="absolute inset-0 h-full w-full object-cover grayscale opacity-60 transition-all duration-700 group-hover:grayscale-0 group-hover:opacity-90 group-hover:scale-105"
                      />
                    )}
                    <div className="absolute inset-0 bg-gradient-to-t from-page via-page/40 to-transparent" />

                    <div className="absolute top-0 left-0 w-full p-4 flex justify-between items-start">
                      <MonoLabel className="text-gray-300">{pad(index + 1)}</MonoLabel>
                      <ArrowUpRight size={18} strokeWidth={1} className="text-white opacity-0 transition-opacity duration-300 group-hover:opacity-100" />
                    </div>

                    <div className="absolute bottom-0 left-0 w-full p-4">
                      <MonoLabel className="block mb-2 text-gray-300">{fmt(sector.company_count)} cos</MonoLabel>
                      <h3 className="text-[14px] font-medium tracking-tight leading-tight text-white line-clamp-2 break-words transition-[font-size] duration-500 group-hover:text-lg">
                        {sector.name}
                      </h3>
                      <div className="max-h-0 overflow-hidden opacity-0 transition-all duration-500 group-hover:mt-2 group-hover:max-h-24 group-hover:opacity-100">
                        {meta.description && (
                          <p className="max-w-[240px] text-[10px] font-mono tracking-widest uppercase leading-relaxed text-gray-400">
                            {meta.description}
                          </p>
                        )}
                        <span className="mt-3 inline-flex items-center gap-1 text-[10px] font-mono tracking-widest uppercase text-white">
                          View companies <ArrowUpRight size={12} strokeWidth={1.5} />
                        </span>
                      </div>
                    </div>
                  </Link>
                );
              })}
            </div>
          </div>
        )}
      </section>
    </>
  );
};

export default Category;
