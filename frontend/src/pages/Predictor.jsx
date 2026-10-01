import React, { useEffect, useMemo, useRef, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { AnimatePresence, motion } from "motion/react";
import { ChevronDown, ChevronLeft, ChevronRight, Search, X } from "lucide-react";
import Navbar from "../components/Navbar";
import Footer from "../components/Footer";
import { PageHeading, MonoLabel, TouchPill, HScroll } from "../components/ui";
import { RankingTable, Disclaimer, StatusLine, LABELS, SORTS, selectClass, fmtDate } from "../components/rankings";
import { getRankings, getRankingsMeta, getSectors, getSectorIndustries } from "../services/api";
import { fmt } from "../data/sectorMeta";
import usePageTitle from "../hooks/usePageTitle";

const PAGE_SIZE = 50;

// Full growth ranking across every company. Filters live in the URL so a view is shareable.
export default function Predictor() {
  usePageTitle("Company Rankings");
  const [params, setParams] = useSearchParams();
  const sector = params.get("sector") || "";
  const industry = params.get("industry") || "";
  const label = params.get("label") || "";
  const sort = params.get("sort") || "rank";
  const page = Math.max(1, Number(params.get("page")) || 1);
  const q = params.get("q") || "";
  // "top" (default): the backtested Top list; "steady": the steadier breakout list; "all": every ranked company
  const view = ["all", "steady"].includes(params.get("view")) ? params.get("view") : "top";
  const listKey = view === "top" ? "top_list" : view === "steady" ? "steady_list" : null;
  const listMeta = listKey ? meta?.[listKey] : null;

  const [query, setQuery] = useState(q);
  const [meta, setMeta] = useState(null);
  const [metaError, setMetaError] = useState(false);
  const [showMethod, setShowMethod] = useState(false);
  const [sectors, setSectors] = useState([]);
  const [industries, setIndustries] = useState([]);

  const [res, setRes] = useState(null);
  const [error, setError] = useState(false);
  const requestId = useRef(0);

  // Update query params; any filter change resets to page 1
  const update = (changes, keepPage = false) => {
    const next = new URLSearchParams(params);
    Object.entries(changes).forEach(([k, v]) => (v ? next.set(k, v) : next.delete(k)));
    if (!keepPage) next.delete("page");
    setParams(next, { replace: !("page" in changes) });
  };

  // Debounced search box -> ?q=
  useEffect(() => {
    const id = setTimeout(() => {
      if (query.trim() !== q) update({ q: query.trim() });
    }, 350);
    return () => clearTimeout(id);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [query]);

  useEffect(() => {
    getRankingsMeta().then(setMeta).catch(() => setMetaError(true));
    getSectors().then(setSectors).catch(() => {});
  }, []);

  useEffect(() => {
    setIndustries([]);
    if (!sector) return;
    let cancelled = false;
    getSectorIndustries(sector)
      .then((rows) => { if (!cancelled && Array.isArray(rows)) setIndustries(rows); })
      .catch(() => {});
    return () => { cancelled = true; };
  }, [sector]);

  const request = useMemo(() => {
    const p = { page, limit: PAGE_SIZE };
    // No sort = the default order: rank, or Top list position
    if (sort !== "rank") p.sort = sort;
    if (view !== "all") p.list = view;
    if (sector) p.sector = sector;
    if (industry) p.industry = industry;
    if (label) p.label = label;
    if (q) p.search = q;
    return p;
  }, [sector, industry, label, sort, page, q, view]);

  useEffect(() => {
    const id = ++requestId.current;
    setError(false);
    setRes((prev) => (prev ? { ...prev, loading: true } : null));
    getRankings(request)
      .then((data) => { if (id === requestId.current) setRes(data); })
      .catch(() => { if (id === requestId.current) { setError(true); setRes(null); } });
  }, [request]);

  useEffect(() => { window.scrollTo({ top: 0 }); }, [page]);

  const rows = res?.data || [];
  const total = res?.total || 0;
  const pages = Math.max(1, Math.ceil(total / PAGE_SIZE));
  const snapshotDate = meta?.snapshot_date ?? res?.snapshot_date;
  const notReady = (meta && !meta.snapshot_date) || (res && !res.snapshot_date);
  const hasFilters = sector || industry || label || q;

  return (
    <div className="min-h-screen w-full bg-page text-white font-sans overflow-x-clip">
      <Navbar />

      {/* HERO */}
      <section className="border-b border-gray-800 px-6 md:px-16 pt-12 pb-12">
        <PageHeading index="05" label="Growth ranking" title="PREDICTOR">
          <div className="flex flex-col lg:items-end gap-3 lg:text-right">
            <p className="text-[10px] font-mono tracking-widest uppercase text-gray-400 leading-relaxed max-w-[360px]">
              Every listed company scored on price trend, financial health and news. Start with the Top list, or the Steady list for smaller swings.
            </p>
            {metaError ? (
              <MonoLabel className="text-red-400">Ranking status unavailable</MonoLabel>
            ) : meta ? (
              <div className="flex flex-col lg:items-end gap-1">
                <MonoLabel className="text-white">
                  {snapshotDate ? `Snapshot ${fmtDate(snapshotDate)} · ${meta.model_version || "—"}` : "Rankings are being prepared"}
                </MonoLabel>
                <MonoLabel className="text-gray-500">
                  Rankings refresh every 15 days{meta.next_update ? ` (next: ${fmtDate(meta.next_update)})` : ""}
                </MonoLabel>
                {snapshotDate && (
                  <MonoLabel className="text-gray-500">
                    {fmt(meta.ranked)} ranked · {fmt(meta.unranked)} with insufficient data
                  </MonoLabel>
                )}
              </div>
            ) : (
              <MonoLabel className="text-gray-600">Loading status…</MonoLabel>
            )}
          </div>
        </PageHeading>

        {meta?.method && (
          <div className="mt-10 border border-gray-800 rounded-xl bg-surface">
            <button
              type="button"
              onClick={() => setShowMethod((v) => !v)}
              className="w-full flex items-center justify-between px-5 py-4 cursor-pointer"
              aria-expanded={showMethod}
            >
              <MonoLabel className="text-gray-300">How the score works</MonoLabel>
              <ChevronDown size={16} strokeWidth={1.5} className={`text-gray-400 transition-transform ${showMethod ? "rotate-180" : ""}`} />
            </button>
            <AnimatePresence initial={false}>
              {showMethod && (
                <motion.div
                  initial={{ height: 0, opacity: 0 }}
                  animate={{ height: "auto", opacity: 1 }}
                  exit={{ height: 0, opacity: 0 }}
                  transition={{ duration: 0.35, ease: "easeOut" }}
                  className="overflow-hidden"
                >
                  <p className="px-5 pb-5 text-[14px] leading-relaxed text-gray-400 max-w-[900px]">{meta.method}</p>
                </motion.div>
              )}
            </AnimatePresence>
          </div>
        )}

        <Disclaimer className="mt-6" />
      </section>

      {/* VIEW: Top list or full ranking */}
      <section className="px-6 md:px-16 pt-8 flex flex-col gap-5">
        <div role="tablist" aria-label="Ranking view" className="inline-flex self-start rounded-full border border-gray-700 p-1 bg-surface">
          {[
            ["top", `Top list${meta?.top_list?.count ? ` · ${meta.top_list.count}` : ""}`],
            ["steady", `Steady list${meta?.steady_list?.count ? ` · ${meta.steady_list.count}` : ""}`],
            ["all", `Full ranking${meta?.ranked ? ` · ${fmt(meta.ranked)}` : ""}`],
          ].map(([v, text]) => (
            <button
              key={v}
              type="button"
              role="tab"
              aria-selected={view === v}
              onClick={() => update({ view: v === "top" ? "" : v, sort: "" })}
              className={`touch:min-h-11 px-5 py-2 rounded-full text-[12px] font-medium uppercase tracking-wider transition-colors cursor-pointer ${
                view === v ? "bg-white text-black" : "text-gray-300 hover:text-white"
              }`}
            >
              {text}
            </button>
          ))}
        </div>
        {listMeta?.rules?.length > 0 && (
          <div className="border border-gray-800 rounded-xl bg-surface px-5 py-4 max-w-[900px]">
            <MonoLabel className="block mb-3 text-gray-300">How the {view === "steady" ? "Steady" : "Top"} list is picked</MonoLabel>
            <ul className="space-y-2">
              {listMeta.rules.map((rule) => (
                <li key={rule} className="flex gap-3 text-[14px] leading-relaxed text-gray-400">
                  <span aria-hidden="true" className="mt-[0.7em] h-px w-3 shrink-0 bg-gray-500" />
                  <span>{rule}</span>
                </li>
              ))}
            </ul>
            <p className="mt-3 text-[12px] text-gray-500">
              {view === "steady"
                ? "Tested on 2019-2026 data with the list refreshed every 15 days. Pick it for smaller swings, not for the highest returns. A research shortlist, not a buy list."
                : "Tested on 2019-2026 data with the list refreshed every 15 days. It fell less than the index in most sell-offs, but it is a research shortlist, not a buy list."}
              {" "}<Link to="/track-record" className="text-gray-300 underline underline-offset-4 decoration-gray-700 hover:text-white">See how published lists have done</Link>
            </p>
          </div>
        )}
      </section>

      {/* FILTERS */}
      <section className="px-6 md:px-16 py-6 md:py-8 flex flex-col gap-4 md:gap-5 border-b border-gray-800">
        <div className="flex flex-col lg:flex-row gap-3">
          <div className="relative w-full lg:w-[340px] shrink-0">
            <Search size={15} className="absolute left-4 top-1/2 -translate-y-1/2 text-gray-500" />
            <input
              type="text"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              placeholder="Search company or symbol"
              className="w-full pl-10 pr-4 py-2.5 rounded-full bg-white/5 border border-gray-700 text-white text-sm outline-none placeholder:text-gray-500 focus:border-white transition-colors"
            />
          </div>
          <div className="relative min-w-0">
            <select value={sector} onChange={(e) => update({ sector: e.target.value, industry: "" })} className={`${selectClass} w-full lg:w-auto`}>
              <option value="">All sectors</option>
              {sectors.map((s) => <option key={s.id} value={s.slug}>{s.name}</option>)}
            </select>
            <ChevronDown size={14} className="absolute right-3 top-1/2 -translate-y-1/2 text-gray-500 pointer-events-none" />
          </div>
          <div className="relative min-w-0">
            <select
              value={industry}
              onChange={(e) => update({ industry: e.target.value })}
              disabled={!sector}
              className={`${selectClass} w-full lg:w-auto disabled:opacity-40 disabled:cursor-not-allowed`}
            >
              <option value="">{sector ? "All industries" : "Pick a sector first"}</option>
              {industries.map((i) => (
                <option key={i.industry} value={i.industry}>{i.industry} ({i.company_count})</option>
              ))}
            </select>
            <ChevronDown size={14} className="absolute right-3 top-1/2 -translate-y-1/2 text-gray-500 pointer-events-none" />
          </div>
          {hasFilters && (
            <button
              type="button"
              onClick={() => {
                setQuery("");
                const keep = {};
                if (sort !== "rank") keep.sort = sort;
                if (view !== "top") keep.view = view;
                setParams(new URLSearchParams(keep), { replace: true });
              }}
              className="inline-flex items-center gap-1.5 touch:min-h-11 text-[10px] font-mono tracking-widest uppercase text-gray-400 hover:text-white cursor-pointer lg:ml-auto self-start lg:self-center"
            >
              <X size={12} /> Clear filters
            </button>
          )}
        </div>

        <div className="flex flex-col xl:flex-row xl:items-center gap-4 xl:gap-8">
          <HScroll label="Filter by label" className="-mx-6 md:mx-0" innerClassName="flex items-center gap-2 px-6 md:px-0 pb-1">
            <MonoLabel className="shrink-0 mr-2 text-gray-500">Label</MonoLabel>
            <TouchPill active={!label} onClick={() => update({ label: "" })} className="shrink-0">All</TouchPill>
            {LABELS.map((l) => (
              <TouchPill key={l} active={label === l} onClick={() => update({ label: l })} className="shrink-0">{l}</TouchPill>
            ))}
          </HScroll>
          <HScroll label="Sort" className="-mx-6 md:mx-0" innerClassName="flex items-center gap-2 px-6 md:px-0 pb-1">
            <MonoLabel className="shrink-0 mr-2 text-gray-500">Sort</MonoLabel>
            {SORTS.map((s) => (
              <TouchPill key={s.value} active={sort === s.value} onClick={() => update({ sort: s.value === "rank" ? "" : s.value })} className="shrink-0">
                {s.label}
              </TouchPill>
            ))}
          </HScroll>
        </div>
      </section>

      {/* LIST */}
      <section className={res?.loading ? "opacity-50 transition-opacity" : "transition-opacity"}>
        {error ? (
          <StatusLine tone="error">Couldn't load rankings. Is the backend running? (cd backend &amp;&amp; npm run dev)</StatusLine>
        ) : !res ? (
          <StatusLine>Loading rankings…</StatusLine>
        ) : notReady ? (
          <StatusLine>Rankings are being prepared. The first snapshot will appear here once it's built.</StatusLine>
        ) : rows.length === 0 ? (
          <StatusLine>{listKey && !hasFilters ? "This list appears with the next snapshot." : "No companies match these filters."}</StatusLine>
        ) : (
          <>
            <div className="px-6 md:px-16 py-4">
              <MonoLabel className="text-gray-500">
                {listKey ? `${fmt(total)} companies on the ${view === "steady" ? "Steady" : "Top"} list` : `${fmt(total)} companies · page ${page} of ${fmt(pages)}`}
              </MonoLabel>
            </div>
            <RankingTable
              rows={rows}
              rankKey={listKey || (industry ? "rank_in_industry" : sector ? "rank_in_sector" : "rank_overall")}
              sort={sort}
              onSort={(s) => update({ sort: s === "rank" ? "" : s })}
              showSector={!sector}
              listKey={listKey}
            />
            <Pagination page={page} pages={pages} onPage={(p) => update({ page: p > 1 ? String(p) : "" }, true)} />
          </>
        )}
      </section>

      <Footer />
    </div>
  );
}

function Pagination({ page, pages, onPage }) {
  if (pages <= 1) return null;
  const nums = [...new Set([1, page - 1, page, page + 1, pages].filter((n) => n >= 1 && n <= pages))].sort((a, b) => a - b);
  const btn = "h-9 min-w-9 touch:h-11 touch:min-w-11 px-3 rounded-full border text-[11px] font-mono transition-colors cursor-pointer disabled:opacity-30 disabled:cursor-not-allowed";

  return (
    <div className="px-6 md:px-16 py-8 flex items-center justify-center gap-2 flex-wrap">
      <button type="button" className={`${btn} border-gray-700 text-gray-300 hover:border-white`} disabled={page <= 1} onClick={() => onPage(page - 1)} aria-label="Previous page">
        <ChevronLeft size={14} />
      </button>
      {nums.map((n, i) => (
        <React.Fragment key={n}>
          {i > 0 && n - nums[i - 1] > 1 && <span className="text-gray-600 font-mono text-[11px]">…</span>}
          <button
            type="button"
            onClick={() => onPage(n)}
            className={`${btn} ${n === page ? "bg-white text-black border-white" : "border-gray-700 text-gray-300 hover:border-white"}`}
          >
            {n}
          </button>
        </React.Fragment>
      ))}
      <button type="button" className={`${btn} border-gray-700 text-gray-300 hover:border-white`} disabled={page >= pages} onClick={() => onPage(page + 1)} aria-label="Next page">
        <ChevronRight size={14} />
      </button>
    </div>
  );
}
