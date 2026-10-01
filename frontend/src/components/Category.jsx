import React from "react";
import { Link } from "react-router-dom";
import { motion } from "motion/react";
import { ArrowUpRight, Landmark, Layers, LayoutGrid } from "lucide-react";
import { HScroll, PillTag } from "./ui";
import SourcePill from "./SourcePill";
import { useSectors } from "../hooks/useSectorData";
import { getSectorMeta, pad, fmt } from "../data/sectorMeta";

const StatusLine = ({ children, tone = "muted" }) => (
  <div className={`px-6 md:px-16 py-16 text-center text-[11px] font-mono tracking-widest uppercase ${tone === "error" ? "text-red-400" : "text-gray-400"}`}>
    {children}
  </div>
);

// Smaller Unsplash renditions: cards are at most ~300px wide, so 640px covers 2x screens
const cardImage = (url) => url?.replace(/([?&])w=\d+/, "$1w=640");

const cardMotion = {
  initial: { opacity: 0, y: 24 },
  animate: { opacity: 1, y: 0, transition: { duration: 0.6, ease: [0.16, 1, 0.3, 1] } },
};

// One sector card. Hover only animates transform and opacity (GPU-composited), never size or
// font-size, so the grid doesn't re-layout while the pointer moves across it.
function SectorCard({ sector, index }) {
  const meta = getSectorMeta(sector.slug);
  const industries = Number(sector.industry_count || 0);

  return (
    <motion.div variants={cardMotion} className="shrink-0 w-[78vw] max-w-[300px] snap-start md:w-auto md:max-w-none">
      <Link
        to={`/sectors/${sector.slug}`}
        className="group relative flex h-[300px] md:h-[240px] xl:h-[270px] flex-col justify-between overflow-hidden rounded-xl border border-gray-800 bg-surface p-5 transform-gpu transition-[transform,border-color] duration-500 ease-[cubic-bezier(0.16,1,0.3,1)] hover:-translate-y-1 hover:border-gray-500 focus-visible:outline-none focus-visible:border-white"
      >
        {meta.image && (
          <img
            src={cardImage(meta.image)}
            alt=""
            loading="lazy"
            decoding="async"
            onError={(e) => { e.currentTarget.style.display = "none"; }}
            className="absolute inset-0 h-full w-full object-cover grayscale opacity-45 transform-gpu will-change-transform transition-[transform,opacity] duration-700 ease-[cubic-bezier(0.16,1,0.3,1)] group-hover:scale-[1.06] group-hover:opacity-70"
          />
        )}
        <div aria-hidden="true" className="absolute inset-0 bg-gradient-to-t from-page via-page/75 to-page/10" />

        <div className="relative flex items-start justify-between">
          <span className="text-[12px] font-mono text-gray-300">{pad(index + 1)}</span>
          <span
            aria-hidden="true"
            className="flex h-9 w-9 items-center justify-center rounded-full border border-gray-600 text-white transition-[transform,background-color,border-color,color] duration-500 group-hover:translate-x-0.5 group-hover:-translate-y-0.5 group-hover:bg-white group-hover:border-white group-hover:text-black"
          >
            <ArrowUpRight size={16} strokeWidth={1.75} />
          </span>
        </div>

        <div className="relative">
          <span className="block mb-2 text-[11px] font-mono tracking-wider uppercase text-gray-300">
            {fmt(sector.company_count)} companies{industries ? ` · ${industries} industries` : ""}
          </span>
          <h3 className="text-[21px] md:text-[20px] xl:text-[22px] font-medium tracking-tight leading-[1.15] text-white">
            {sector.name}
          </h3>
          {meta.description && (
            <p className="mt-2 text-[13px] leading-snug text-gray-400 line-clamp-2">{meta.description}</p>
          )}
        </div>
      </Link>
    </motion.div>
  );
}

// Home page "Explore the market" section: one card per DB sector, each opening that sector's page.
// Phones: a swipeable row. Tablets: 2 columns. Desktop: 5 x 2 grid.
const Category = () => {
  const { sectors, source, loading, error } = useSectors();
  const totalCompanies = sectors.reduce((sum, s) => sum + Number(s.company_count || 0), 0);

  return (
    <section id="sectors" className="w-full scroll-mt-24">
      {/* Heading */}
      <div className="px-6 md:px-16 pt-24 md:pt-32 mb-10 md:mb-12 flex flex-col xl:flex-row justify-between items-start gap-8">
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
          <p className="text-[11px] font-mono tracking-widest text-gray-300 uppercase mb-6 leading-relaxed">
            {sectors.length
              ? <>{sectors.length} sectors · {fmt(totalCompanies)} listed companies<br />Pick a sector to see every company in it.</>
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
        <HScroll label="Sectors" className="md:mx-16" innerClassName="snap-x snap-mandatory scroll-px-6 md:snap-none md:overflow-visible">
          <motion.div
            initial="initial"
            whileInView="animate"
            viewport={{ once: true, margin: "-80px" }}
            variants={{ animate: { transition: { staggerChildren: 0.05 } } }}
            className="flex gap-3 px-6 pb-2 md:px-0 md:pb-0 md:grid md:grid-cols-2 lg:grid-cols-5 md:gap-4"
          >
            {sectors.map((sector, index) => (
              <SectorCard key={sector.id} sector={sector} index={index} />
            ))}
          </motion.div>
        </HScroll>
      )}
    </section>
  );
};

export default Category;
