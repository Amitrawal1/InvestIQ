import React, { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { motion } from "motion/react";
import { Search } from "lucide-react";
import Navbar from "../components/Navbar";
import Footer from "../components/Footer";
import NewsItem, { formatWhen } from "../components/NewsItem";
import { PageHeading, MonoLabel, Pill, LiveDot } from "../components/ui";
import { getNews, getNewsStats } from "../services/api";
import { fmt } from "../data/sectorMeta";

const PAGE_SIZE = 25;

const SENTIMENTS = ["All", "POSITIVE", "NEGATIVE", "NEUTRAL"];
const IMPORTANCES = ["All", "HIGH", "MEDIUM", "LOW"];

const StatusLine = ({ children, tone = "muted" }) => (
  <div className={`px-6 md:px-16 py-20 text-center text-[10px] font-mono tracking-widest uppercase ${tone === "error" ? "text-red-400" : "text-gray-500"}`}>
    {children}
  </div>
);

export default function News() {
  const [sentiment, setSentiment] = useState("All");
  const [importance, setImportance] = useState("All");
  const [confidentOnly, setConfidentOnly] = useState(false);
  const [query, setQuery] = useState("");
  const [search, setSearch] = useState("");

  const [items, setItems] = useState(null);
  const [total, setTotal] = useState(0);
  const [error, setError] = useState(null);
  const [loadingMore, setLoadingMore] = useState(false);

  const [stats, setStats] = useState(null);
  const [statsError, setStatsError] = useState(false);

  // Guards against a slow first page overwriting a newer filter's result
  const requestId = useRef(0);

  // Debounce the search box so typing doesn't hammer the API
  useEffect(() => {
    const id = setTimeout(() => setSearch(query.trim()), 350);
    return () => clearTimeout(id);
  }, [query]);

  const params = useMemo(() => {
    const p = { limit: PAGE_SIZE };
    if (sentiment !== "All") p.sentiment = sentiment;
    if (importance !== "All") p.importance = importance;
    if (confidentOnly) p.confident = 1;
    if (search) p.search = search;
    return p;
  }, [sentiment, importance, confidentOnly, search]);

  // First page whenever the filters change
  useEffect(() => {
    const id = ++requestId.current;
    let cancelled = false;

    setItems(null);
    setError(null);

    getNews({ ...params, offset: 0 })
      .then((res) => {
        if (cancelled || id !== requestId.current) return;
        setItems(res.data || []);
        setTotal(res.total || 0);
      })
      .catch(() => {
        if (cancelled || id !== requestId.current) return;
        setItems([]);
        setTotal(0);
        setError("Couldn't reach the InvestIQ API. Start the backend with: cd backend && npm run dev");
      });

    return () => { cancelled = true; };
  }, [params]);

  useEffect(() => {
    let cancelled = false;

    getNewsStats()
      .then((data) => { if (!cancelled) setStats(data); })
      .catch(() => { if (!cancelled) setStatsError(true); });

    return () => { cancelled = true; };
  }, []);

  const loadMore = useCallback(() => {
    if (!items || loadingMore) return;

    const id = requestId.current;
    setLoadingMore(true);

    getNews({ ...params, offset: items.length })
      .then((res) => {
        if (id !== requestId.current) return;
        setItems((prev) => [...(prev || []), ...(res.data || [])]);
        setTotal(res.total || 0);
      })
      .catch(() => {
        if (id !== requestId.current) return;
        setError("Couldn't load more announcements.");
      })
      .finally(() => setLoadingMore(false));
  }, [items, loadingMore, params]);

  const statTiles = useMemo(() => {
    if (!stats) return [];
    return [
      { label: "Positive", value: fmt(stats.by_sentiment?.POSITIVE), tone: "text-green-500" },
      { label: "Negative", value: fmt(stats.by_sentiment?.NEGATIVE), tone: "text-red-400" },
      { label: "Neutral", value: fmt(stats.by_sentiment?.NEUTRAL), tone: "text-gray-300" },
      { label: "High confidence", value: fmt(stats.confident), tone: "text-white" },
      { label: "Latest filing", value: formatWhen(stats.newest_published_at), tone: "text-white", small: true },
    ];
  }, [stats]);

  const resetFilters = () => {
    setSentiment("All");
    setImportance("All");
    setConfidentOnly(false);
    setQuery("");
  };

  const hasFilters = sentiment !== "All" || importance !== "All" || confidentOnly || Boolean(search);

  return (
    <div className="min-h-screen w-full bg-page text-white font-sans overflow-x-clip">
      <Navbar />

      {/* HERO */}
      <section className="border-b border-gray-800 px-6 md:px-16 pt-12 pb-14">
        <PageHeading index="04" label="Announcements" title="MARKET NEWS">
          <div className="flex flex-col lg:items-end gap-4 lg:text-right">
            <p className="text-[10px] font-mono tracking-widest uppercase text-gray-400 leading-relaxed max-w-[320px]">
              NSE corporate filings scored by FinBERT. Labels below 95% confidence are marked uncertain.
            </p>
            <span className="inline-flex items-center gap-2 self-start lg:self-end">
              {statsError
                ? <span className="w-1.5 h-1.5 rounded-full bg-yellow-500" />
                : <LiveDot />}
              <MonoLabel className={statsError ? "text-yellow-500" : ""}>
                {statsError ? "Backend offline" : stats ? `${fmt(stats.total)} announcements` : "Loading…"}
              </MonoLabel>
            </span>
          </div>
        </PageHeading>
      </section>

      {/* STATS STRIP - hairline grid */}
      {statsError ? (
        <div className="border-b border-gray-800 px-6 md:px-16 py-5">
          <MonoLabel className="text-gray-500">Stats unavailable — backend offline</MonoLabel>
        </div>
      ) : (
        <section className="grid grid-cols-2 lg:grid-cols-5 gap-px bg-gray-800 border-b border-gray-800">
          {(stats ? statTiles : Array.from({ length: 5 }, (_, i) => ({ label: "—", value: "—", key: i }))).map((s, i) => (
            <motion.div
              key={s.label + i}
              initial={{ opacity: 0, y: 14 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.5, delay: 0.1 + i * 0.06 }}
              className="bg-surface px-6 md:px-8 py-6"
            >
              <div className="flex justify-between items-center mb-4">
                <MonoLabel>{s.label}</MonoLabel>
                <span className="text-[10px] font-mono text-gray-600">0{i + 1}</span>
              </div>
              <div className={`${s.small ? "text-[1.05rem]" : "text-[1.6rem] md:text-[1.9rem]"} font-normal tracking-tight leading-none ${s.tone || "text-gray-400"}`}>
                {s.value}
              </div>
            </motion.div>
          ))}
        </section>
      )}

      {/* FILTERS */}
      <section className="px-6 md:px-16 py-8 flex flex-col xl:flex-row xl:items-center justify-between gap-6 border-b border-gray-800">
        <div className="flex flex-col gap-3">
          <div className="flex items-start gap-4">
            <MonoLabel className="hidden md:block shrink-0 pt-3 w-[72px]">Sentiment</MonoLabel>
            <div className="flex flex-wrap gap-2">
              {SENTIMENTS.map((s) => (
                <Pill key={s} active={sentiment === s} onClick={() => setSentiment(s)} className="shrink-0">
                  {s === "All" ? "All" : s}
                </Pill>
              ))}
              <Pill
                active={confidentOnly}
                onClick={() => setConfidentOnly((v) => !v)}
                className="shrink-0"
                title="Only labels the model scored at 95% confidence or above"
              >
                Confident only
              </Pill>
            </div>
          </div>

          <div className="flex items-start gap-4">
            <MonoLabel className="hidden md:block shrink-0 pt-3 w-[72px]">Impact</MonoLabel>
            <div className="flex flex-wrap gap-2">
              {IMPORTANCES.map((s) => (
                <Pill key={s} active={importance === s} onClick={() => setImportance(s)} className="shrink-0">
                  {s}
                </Pill>
              ))}
            </div>
          </div>
        </div>

        <div className="relative w-full xl:w-[340px] shrink-0">
          <Search size={15} className="absolute left-4 top-1/2 -translate-y-1/2 text-gray-500" />
          <input
            type="text"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="Search company, symbol or event"
            className="w-full pl-10 pr-4 py-2.5 rounded-full bg-white/5 border border-gray-700 text-white text-sm outline-none placeholder:text-gray-500 focus:border-white transition-colors"
          />
        </div>
      </section>

      {/* LIST */}
      {error && !items?.length ? (
        <StatusLine tone="error">{error}</StatusLine>
      ) : items === null ? (
        <StatusLine>Loading announcements…</StatusLine>
      ) : items.length === 0 ? (
        <div className="px-6 md:px-16 py-20 flex flex-col items-center gap-5">
          <MonoLabel className="text-gray-500">No announcements match these filters.</MonoLabel>
          {hasFilters && <Pill onClick={resetFilters}>Clear filters</Pill>}
        </div>
      ) : (
        <div className="grid grid-cols-1 gap-px bg-gray-800 border-b border-gray-800">
          {items.map((item) => (
            <NewsItem key={item.id} item={item} />
          ))}
        </div>
      )}

      {/* FOOTER CONTROLS */}
      {items && items.length > 0 && (
        <div className="px-6 md:px-16 py-8 flex flex-col sm:flex-row items-center justify-between gap-4">
          <MonoLabel className="text-gray-500">
            Showing {fmt(items.length)} of {fmt(total)}
          </MonoLabel>
          {items.length < total && (
            <Pill onClick={loadMore} disabled={loadingMore}>
              {loadingMore ? "Loading…" : `Load more (${fmt(total - items.length)} left)`}
            </Pill>
          )}
        </div>
      )}

      {error && items?.length ? (
        <div className="px-6 md:px-16 pb-8">
          <MonoLabel className="text-red-400">{error}</MonoLabel>
        </div>
      ) : null}

      <Footer />
    </div>
  );
}
