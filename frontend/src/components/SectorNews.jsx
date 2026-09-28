import React, { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { ArrowRight } from "lucide-react";
import NewsItem from "./NewsItem";
import { MonoLabel, SectionLabel } from "./ui";
import { getNews } from "../services/api";

const LIMIT = 6;

// Compact "latest news in this sector" strip. Renders nothing structural if the
// API is down beyond a single muted status line, so the sector page never breaks.
export default function SectorNews({ sector }) {
  const [items, setItems] = useState(null);
  const [error, setError] = useState(false);

  useEffect(() => {
    if (!sector) return;
    let cancelled = false;

    setItems(null);
    setError(false);

    getNews({ sector: sector.name, limit: LIMIT })
      .then((res) => { if (!cancelled) setItems(res.data || []); })
      .catch(() => { if (!cancelled) setError(true); });

    return () => { cancelled = true; };
  }, [sector]);

  if (error) {
    return (
      <section className="border-t border-gray-800 px-6 md:px-16 py-10">
        <MonoLabel className="text-gray-500">Latest news unavailable — backend offline</MonoLabel>
      </section>
    );
  }

  return (
    <section className="border-t border-gray-800">
      <div className="px-6 md:px-16 pt-10 pb-6 flex flex-col sm:flex-row sm:items-end justify-between gap-4">
        <div>
          <SectionLabel index="03" className="mb-4">Latest news in this sector</SectionLabel>
          <h2 className="text-[1.6rem] md:text-[2rem] font-normal tracking-tight leading-none text-white">
            Recent filings
          </h2>
        </div>
        <Link
          to="/news"
          className="inline-flex items-center gap-2 touch:min-h-11 text-[10px] font-mono tracking-[0.2em] uppercase text-gray-400 hover:text-white transition-colors"
        >
          All news <ArrowRight size={14} strokeWidth={1} />
        </Link>
      </div>

      {items === null ? (
        <div className="px-6 md:px-16 pb-12">
          <MonoLabel className="text-gray-500">Loading news…</MonoLabel>
        </div>
      ) : items.length === 0 ? (
        <div className="px-6 md:px-16 pb-12">
          <MonoLabel className="text-gray-500">No announcements for this sector yet.</MonoLabel>
        </div>
      ) : (
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-px bg-gray-800 border-y border-gray-800">
          {items.map((item) => (
            <NewsItem key={item.id} item={item} compact />
          ))}
        </div>
      )}
    </section>
  );
}
