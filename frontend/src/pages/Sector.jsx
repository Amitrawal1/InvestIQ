import React, { useEffect, useMemo } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { motion } from "motion/react";
import { ArrowLeft } from "lucide-react";
import Navbar from "../components/Navbar";
import Footer from "../components/Footer";
import SectorRankings from "../components/SectorRankings";
import SectorNews from "../components/SectorNews";
import SourcePill from "../components/SourcePill";
import { PageHeading, MonoLabel, Pill } from "../components/ui";
import { useSectors, useSectorCompanies } from "../hooks/useSectorData";
import { getSectorMeta, pad, fmt } from "../data/sectorMeta";

const BackLink = () => (
  <Link
    to="/home#sectors"
    className="inline-flex items-center gap-2 text-[10px] font-mono tracking-[0.2em] uppercase text-gray-400 hover:text-white transition-colors"
  >
    <ArrowLeft size={14} strokeWidth={1} /> All sectors
  </Link>
);

export default function Sector() {
  const { slug } = useParams();
  const navigate = useNavigate();

  const { sectors, source, loading, error } = useSectors();
  const index = sectors.findIndex((s) => s.slug === slug);
  const sector = index >= 0 ? sectors[index] : null;
  const meta = getSectorMeta(slug);

  const { companies, error: companiesError } = useSectorCompanies(sector, source?.live);

  // New sector -> start at the top of the page
  useEffect(() => { window.scrollTo(0, 0); }, [slug]);

  const stats = useMemo(() => {
    const sme = companies ? companies.filter((c) => c.market_segment === "SME").length : null;
    return [
      { label: "Companies", value: sector ? fmt(sector.company_count) : "—" },
      { label: "Industries", value: sector ? fmt(sector.industry_count) : "—" },
      { label: "Equity listings", value: companies ? fmt(companies.length - sme) : "—" },
      { label: "SME listings", value: companies ? fmt(sme) : "—" },
    ];
  }, [sector, companies]);

  return (
    <div className="min-h-screen w-full bg-[#050011] text-white font-sans overflow-x-clip">
      <Navbar />

      {/* HERO */}
      <section className="relative overflow-hidden border-b border-gray-800">
        {meta.image && (
          <img
            src={meta.image}
            alt=""
            onError={(e) => { e.currentTarget.style.display = "none"; }}
            className="absolute inset-0 w-full h-full object-cover grayscale opacity-25 pointer-events-none"
          />
        )}
        <div className="absolute inset-0 bg-gradient-to-b from-[#050011]/60 via-[#050011]/80 to-[#050011] pointer-events-none" />

        <div className="relative z-10 px-6 md:px-16 pt-10 pb-14 md:pb-20">
          <BackLink />

          <div className="mt-12 md:mt-16" key={slug}>
            {sector ? (
              <PageHeading index={pad(index + 1)} label="Sector" title={sector.name.toUpperCase()}>
                <div className="flex flex-col lg:items-end gap-5 lg:text-right">
                  {meta.description && (
                    <p className="text-[10px] font-mono tracking-widest uppercase text-gray-400 leading-relaxed max-w-[320px]">
                      {meta.description}
                    </p>
                  )}
                  <SourcePill source={source} />
                </div>
              </PageHeading>
            ) : (
              <div className="py-10 text-[10px] font-mono tracking-widest uppercase text-gray-500">
                {loading && "Loading sector…"}
                {error && <span className="text-red-400">Couldn't load sectors. Start the backend with: cd backend &amp;&amp; npm run dev</span>}
                {!loading && !error && "Sector not found."}
              </div>
            )}
          </div>
        </div>
      </section>

      {sector && (
        <>
          {/* STATS - hairline grid */}
          <section className="grid grid-cols-2 lg:grid-cols-4 gap-px bg-gray-800 border-b border-gray-800">
            {stats.map((s, i) => (
              <motion.div
                key={s.label}
                initial={{ opacity: 0, y: 16 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ duration: 0.6, delay: 0.2 + i * 0.08 }}
                className="bg-[#0a0a0a] px-6 md:px-8 py-7"
              >
                <div className="flex justify-between items-center mb-5">
                  <MonoLabel>{s.label}</MonoLabel>
                  <span className="text-[10px] font-mono text-gray-600">0{i + 1}</span>
                </div>
                <div className="text-[1.8rem] md:text-[2.2rem] font-normal tracking-tight leading-none">{s.value}</div>
              </motion.div>
            ))}
          </section>

          {/* SECTOR SWITCHER */}
          <section className="border-b border-gray-800 px-6 md:px-16 py-6 flex items-start gap-6">
            <MonoLabel className="shrink-0 hidden md:block pt-3">Sectors</MonoLabel>
            <div className="flex flex-wrap gap-2">
              {sectors.map((s) => (
                <Pill
                  key={s.id}
                  active={s.id === sector.id}
                  onClick={() => navigate(`/sectors/${s.slug}`)}
                  className="shrink-0"
                >
                  {s.name}
                </Pill>
              ))}
            </div>
          </section>

          {/* INDUSTRIES + GROWTH RANKING (?industry=<name>) */}
          <SectorRankings key={sector.id} sector={sector} companies={companies} companiesError={companiesError} />

          {/* LATEST NEWS */}
          <SectorNews key={`news-${sector.id}`} sector={sector} />
        </>
      )}

      <Footer />
    </div>
  );
}
