import React, { useMemo, useState } from "react";
import { Search } from "lucide-react";
import { MonoLabel, Pill } from "./ui";
import { fmt } from "../data/sectorMeta";

const PAGE_SIZE = 48;

const StatusLine = ({ children, tone = "muted" }) => (
  <div className={`px-6 md:px-16 py-20 text-center text-[10px] font-mono tracking-widest uppercase ${tone === "error" ? "text-red-400" : "text-gray-500"}`}>
    {children}
  </div>
);

// Searchable, industry-filterable company grid for one sector.
// Render with key={sector.id} so filters reset when the sector changes.
export default function SectorCompanies({ sector, companies, error }) {
  const [industry, setIndustry] = useState("All");
  const [query, setQuery] = useState("");
  const [visible, setVisible] = useState(PAGE_SIZE);

  const industries = useMemo(() => {
    const counts = {};
    (companies || []).forEach((c) => {
      const key = c.industry || "Other";
      counts[key] = (counts[key] || 0) + 1;
    });
    return Object.entries(counts).sort((a, b) => b[1] - a[1]);
  }, [companies]);

  const filtered = useMemo(() => {
    const q = query.trim().toLowerCase();
    return (companies || []).filter((c) =>
      (industry === "All" || (c.industry || "Other") === industry) &&
      (!q || c.name.toLowerCase().includes(q) || c.symbol.toLowerCase().includes(q))
    );
  }, [companies, industry, query]);

  const shown = filtered.slice(0, visible);

  if (error) return <StatusLine tone="error">Couldn't load companies for this sector.</StatusLine>;
  if (!companies) return <StatusLine>Loading companies…</StatusLine>;

  return (
    <div>
      {/* Toolbar: industry filter + search */}
      <div className="px-6 md:px-16 py-8 flex flex-col xl:flex-row xl:items-center justify-between gap-6">
        <div className="flex gap-2 overflow-x-auto pb-1">
          {[["All", companies.length], ...industries].map(([name, count]) => (
            <Pill
              key={name}
              active={industry === name}
              onClick={() => {
                setIndustry(name);
                setVisible(PAGE_SIZE);
              }}
              className="shrink-0"
            >
              {name} <span className="text-gray-500">{count}</span>
            </Pill>
          ))}
        </div>

        <div className="relative w-full xl:w-[340px] shrink-0">
          <Search size={15} className="absolute left-4 top-1/2 -translate-y-1/2 text-gray-500" />
          <input
            type="text"
            value={query}
            onChange={(e) => {
              setQuery(e.target.value);
              setVisible(PAGE_SIZE);
            }}
            placeholder={`Search in ${sector.name}`}
            className="w-full pl-10 pr-4 py-2.5 rounded-full bg-white/5 border border-gray-700 text-white text-sm outline-none placeholder:text-gray-500 focus:border-white transition-colors"
          />
        </div>
      </div>

      {filtered.length === 0 ? (
        <StatusLine>No companies match your search.</StatusLine>
      ) : (
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-px bg-gray-800 border-y border-gray-800">
          {shown.map((c) => (
            <div key={c.id} className="group bg-page hover:bg-surface transition-colors px-6 py-5 flex flex-col gap-3 min-h-[128px]">
              <div className="flex justify-between items-center gap-2">
                <span className="font-mono text-[13px] text-white tracking-wide truncate">{c.symbol}</span>
                {c.market_segment === "SME" && (
                  <span className="shrink-0 px-2 py-0.5 rounded-full border border-gray-600 text-[9px] font-mono tracking-widest uppercase text-gray-400">
                    SME
                  </span>
                )}
              </div>
              <p className="text-[15px] leading-snug text-gray-300 group-hover:text-white transition-colors line-clamp-2">
                {c.name}
              </p>
              <MonoLabel className="mt-auto text-gray-500 truncate">{c.industry || "Other"}</MonoLabel>
            </div>
          ))}
        </div>
      )}

      <div className="px-6 md:px-16 py-8 flex flex-col sm:flex-row items-center justify-between gap-4">
        <MonoLabel className="text-gray-500">
          Showing {fmt(shown.length)} of {fmt(filtered.length)}
        </MonoLabel>
        {shown.length < filtered.length && (
          <Pill onClick={() => setVisible((v) => v + PAGE_SIZE)}>
            Show more ({fmt(filtered.length - shown.length)} left)
          </Pill>
        )}
      </div>
    </div>
  );
}
