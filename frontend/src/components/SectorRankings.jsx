import React, { useEffect, useMemo, useRef, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { Search } from "lucide-react";
import { MonoLabel, Pill, SectionLabel } from "./ui";
import { RankingTable, SORTS, StatusLine, Disclaimer, fmtDate } from "./rankings";
import { getRankings, getSectorIndustries } from "../services/api";
import { fmt } from "../data/sectorMeta";

const PAGE_SIZE = 25;

// Industry chips (?industry=<name>) + companies of one sector ranked by growth score.
// Falls back to a plain company grid while rankings are unavailable.
// Render with key={sector.id} so state resets when the sector changes.
export default function SectorRankings({ sector, companies, companiesError }) {
  const [params, setParams] = useSearchParams();
  const industry = params.get("industry") || "";

  const [industries, setIndustries] = useState(null);
  const [sort, setSort] = useState("rank");
  const [query, setQuery] = useState("");
  const [search, setSearch] = useState("");

  const [rows, setRows] = useState(null);
  const [info, setInfo] = useState(null); // { snapshot_date, model_version, total }
  const [error, setError] = useState(false);
  const [loadingMore, setLoadingMore] = useState(false);
  const requestId = useRef(0);

  useEffect(() => {
    const id = setTimeout(() => setSearch(query.trim()), 350);
    return () => clearTimeout(id);
  }, [query]);

  // Industry chips: API first, else derived from the sector's company list
  useEffect(() => {
    let cancelled = false;
    getSectorIndustries(sector.slug)
      .then((data) => { if (!cancelled && Array.isArray(data)) setIndustries(data); else if (!cancelled) setIndustries(false); })
      .catch(() => { if (!cancelled) setIndustries(false); });
    return () => { cancelled = true; };
  }, [sector.slug]);

  const chips = useMemo(() => {
    if (industries) {
      return [...industries].sort((a, b) => b.company_count - a.company_count)
        .map((i) => ({ name: i.industry, count: i.company_count }));
    }
    const counts = {};
    (companies || []).forEach((c) => { const k = c.industry || "Other"; counts[k] = (counts[k] || 0) + 1; });
    return Object.entries(counts).sort((a, b) => b[1] - a[1]).map(([name, count]) => ({ name, count }));
  }, [industries, companies]);

  const total = chips.reduce((s, c) => s + c.count, 0) || sector.company_count;

  const query_ = useMemo(() => {
    const p = { sector: sector.slug, sort, limit: PAGE_SIZE };
    if (industry) p.industry = industry;
    if (search) p.search = search;
    return p;
  }, [sector.slug, industry, sort, search]);

  useEffect(() => {
    const id = ++requestId.current;
    setRows(null);
    setError(false);
    getRankings({ ...query_, page: 1 })
      .then((res) => {
        if (id !== requestId.current) return;
        setInfo({ snapshot_date: res.snapshot_date, model_version: res.model_version, total: res.total || 0, page: 1 });
        setRows(res.data || []);
      })
      .catch(() => {
        if (id !== requestId.current) return;
        setError(true);
        setRows([]);
      });
  }, [query_]);

  const loadMore = () => {
    if (!info || loadingMore) return;
    const id = requestId.current;
    const next = info.page + 1;
    setLoadingMore(true);
    getRankings({ ...query_, page: next })
      .then((res) => {
        if (id !== requestId.current) return;
        setRows((prev) => [...(prev || []), ...(res.data || [])]);
        setInfo((prev) => ({ ...prev, total: res.total || prev.total, page: next }));
      })
      .catch(() => {})
      .finally(() => setLoadingMore(false));
  };

  const selectIndustry = (name) => {
    const next = new URLSearchParams(params);
    if (name) next.set("industry", name); else next.delete("industry");
    setParams(next, { replace: true });
  };

  const unavailable = error || (info && !info.snapshot_date);

  return (
    <section>
      {/* Heading */}
      <div className="px-6 md:px-16 pt-12 pb-2 flex flex-col md:flex-row md:items-end justify-between gap-4">
        <div>
          <SectionLabel index="01" className="mb-4">Growth ranking</SectionLabel>
          <h2 className="text-[1.8rem] md:text-[2.4rem] font-normal tracking-tight leading-none">
            {industry || "All industries"}
          </h2>
        </div>
        <div className="flex flex-col md:items-end gap-2">
          {info?.snapshot_date && (
            <MonoLabel className="text-gray-500">
              Snapshot {fmtDate(info.snapshot_date)} · {info.model_version}
            </MonoLabel>
          )}
          <Link to="/predictor" className="text-[10px] font-mono tracking-widest uppercase text-gray-400 hover:text-white transition-colors">
            Full ranking across sectors →
          </Link>
        </div>
      </div>

      {/* Industry chips + search + sort */}
      <div className="px-6 md:px-16 py-8 flex flex-col gap-5">
        <div className="flex gap-2 overflow-x-auto pb-1">
          <Pill active={!industry} onClick={() => selectIndustry("")} className="shrink-0">
            All <span className="text-gray-500">{fmt(total)}</span>
          </Pill>
          {chips.map((c) => (
            <Pill key={c.name} active={industry === c.name} onClick={() => selectIndustry(c.name)} className="shrink-0">
              {c.name} <span className="text-gray-500">{fmt(c.count)}</span>
            </Pill>
          ))}
        </div>

        {!unavailable && (
          <div className="flex flex-col lg:flex-row lg:items-center justify-between gap-4">
            <div className="flex items-center gap-2 overflow-x-auto pb-1">
              <MonoLabel className="shrink-0 mr-2 text-gray-500">Sort</MonoLabel>
              {SORTS.map((s) => (
                <Pill key={s.value} active={sort === s.value} onClick={() => setSort(s.value)} className="shrink-0">
                  {s.label}
                </Pill>
              ))}
            </div>
            <div className="relative w-full lg:w-[320px] shrink-0">
              <Search size={15} className="absolute left-4 top-1/2 -translate-y-1/2 text-gray-500" />
              <input
                type="text"
                value={query}
                onChange={(e) => setQuery(e.target.value)}
                placeholder={`Search in ${sector.name}`}
                className="w-full pl-10 pr-4 py-2.5 rounded-full bg-white/5 border border-gray-700 text-white text-sm outline-none placeholder:text-gray-500 focus:border-white transition-colors"
              />
            </div>
          </div>
        )}
      </div>

      {rows === null ? (
        <StatusLine>Loading rankings…</StatusLine>
      ) : unavailable ? (
        <FallbackList companies={companies} error={companiesError} industry={industry} rankingError={error} />
      ) : rows.length === 0 ? (
        <StatusLine>No companies match.</StatusLine>
      ) : (
        <>
          <RankingTable
            rows={rows}
            rankKey={industry ? "rank_in_industry" : "rank_in_sector"}
            sort={sort}
            onSort={setSort}
          />
          <div className="px-6 md:px-16 py-8 flex flex-col sm:flex-row items-center justify-between gap-4">
            <MonoLabel className="text-gray-500">Showing {fmt(rows.length)} of {fmt(info.total)}</MonoLabel>
            {rows.length < info.total && (
              <Pill onClick={loadMore}>{loadingMore ? "Loading…" : `Show more (${fmt(info.total - rows.length)} left)`}</Pill>
            )}
          </div>
        </>
      )}

      <div className="px-6 md:px-16 pb-10">
        <Disclaimer />
      </div>
    </section>
  );
}

// Unranked company grid shown while no snapshot exists (or the rankings API is down)
function FallbackList({ companies, error, industry, rankingError }) {
  const [visible, setVisible] = useState(48);
  const list = useMemo(
    () => (companies || []).filter((c) => !industry || (c.industry || "Other") === industry),
    [companies, industry]
  );

  return (
    <div>
      <div className="mx-6 md:mx-16 mb-6 border border-gray-800 rounded-xl bg-[#0a0a0a] px-5 py-4">
        <MonoLabel className="text-gray-300">
          {rankingError ? "Rankings unavailable right now" : "Rankings are being prepared"}
        </MonoLabel>
        <p className="mt-1 text-[13px] text-gray-500">
          Growth scores appear here once the next snapshot is built. Companies are listed alphabetically meanwhile.
        </p>
      </div>
      {error ? (
        <StatusLine tone="error">Couldn't load companies for this sector.</StatusLine>
      ) : !companies ? (
        <StatusLine>Loading companies…</StatusLine>
      ) : (
        <>
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-px bg-gray-800 border-y border-gray-800">
            {list.slice(0, visible).map((c) => (
              <Link
                key={c.id}
                to={`/company/${encodeURIComponent(c.symbol)}`}
                className="group bg-[#050011] hover:bg-[#0a0a0a] transition-colors px-6 py-5 flex flex-col gap-3 min-h-[120px]"
              >
                <span className="font-mono text-[13px] text-white tracking-wide truncate">{c.symbol}</span>
                <p className="text-[15px] leading-snug text-gray-300 group-hover:text-white transition-colors line-clamp-2">{c.name}</p>
                <MonoLabel className="mt-auto text-gray-500 truncate">{c.industry || "Other"}</MonoLabel>
              </Link>
            ))}
          </div>
          <div className="px-6 md:px-16 py-8 flex flex-col sm:flex-row items-center justify-between gap-4">
            <MonoLabel className="text-gray-500">Showing {fmt(Math.min(visible, list.length))} of {fmt(list.length)}</MonoLabel>
            {visible < list.length && <Pill onClick={() => setVisible((v) => v + 48)}>Show more</Pill>}
          </div>
        </>
      )}
    </div>
  );
}
