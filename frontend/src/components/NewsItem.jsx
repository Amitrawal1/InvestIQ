import React from "react";
import { ExternalLink } from "lucide-react";
import { MonoLabel } from "./ui";

// Sentiment is a FinBERT prediction, not a fact. Rows the model wasn't confident
// about (sentiment_confident = 0, i.e. confidence < 0.95) are dimmed and tagged
// so an unreliable label is never presented as certain.

const SENTIMENT_TONE = {
  POSITIVE: { confident: "border-green-600 text-green-400", weak: "border-green-900 text-green-700" },
  NEGATIVE: { confident: "border-red-500 text-red-400", weak: "border-red-900 text-red-800" },
  NEUTRAL: { confident: "border-gray-600 text-gray-300", weak: "border-gray-800 text-gray-600" },
};

const IMPORTANCE_TONE = {
  HIGH: "border-accent text-accent",
  MEDIUM: "border-gray-600 text-gray-300",
  LOW: "border-gray-800 text-gray-500",
};

const tagClass = "shrink-0 px-2.5 py-0.5 rounded-full border text-[9px] font-mono tracking-widest uppercase whitespace-nowrap";

// NSE filing text arrives with HTML entities (e.g. &#8377; for the rupee sign).
// Decoded with a regex rather than innerHTML so no markup is ever parsed.
const NAMED_ENTITIES = { amp: "&", lt: "<", gt: ">", quot: '"', apos: "'", nbsp: " " };

export const decodeEntities = (value) => {
  if (!value) return "";
  return String(value)
    .replace(/&#x([0-9a-fA-F]+);/g, (_, hex) => String.fromCodePoint(parseInt(hex, 16)))
    .replace(/&#(\d+);/g, (_, dec) => String.fromCodePoint(parseInt(dec, 10)))
    .replace(/&([a-zA-Z]+);/g, (match, name) => NAMED_ENTITIES[name.toLowerCase()] ?? match);
};

export const pct = (value) => {
  const n = Number(value);
  return Number.isFinite(n) ? `${Math.round(n * 100)}%` : "—";
};

export function SentimentTag({ item }) {
  if (!item.sentiment) {
    return <span className={`${tagClass} border-gray-800 text-gray-600`}>Unscored</span>;
  }

  const confident = item.sentiment_confident === 1;
  const tone = SENTIMENT_TONE[item.sentiment] || SENTIMENT_TONE.NEUTRAL;

  return (
    <span
      className={`${tagClass} ${confident ? tone.confident : tone.weak}`}
      title={
        confident
          ? `FinBERT: ${item.sentiment} at ${pct(item.sentiment_confidence)} confidence`
          : `Low confidence (${pct(item.sentiment_confidence)}) — treat this label as uncertain`
      }
    >
      {item.sentiment} · {pct(item.sentiment_confidence)}
    </span>
  );
}

export function ImportanceTag({ importance }) {
  if (!importance) return null;

  return (
    <span className={`${tagClass} ${IMPORTANCE_TONE[importance] || IMPORTANCE_TONE.LOW}`}>
      {importance}
    </span>
  );
}

// "23 Sep, 18:30" — published_at comes back as an ISO string
export const formatWhen = (value) => {
  if (!value) return "—";
  const d = new Date(value);
  if (Number.isNaN(d.getTime())) return "—";
  return d.toLocaleString("en-IN", {
    day: "2-digit",
    month: "short",
    hour: "2-digit",
    minute: "2-digit",
  });
};

export default function NewsItem({ item, compact = false }) {
  const uncertain = item.sentiment && item.sentiment_confident !== 1;
  const text = decodeEntities(item.content || item.headline || "");

  return (
    <article className={`group bg-page hover:bg-surface transition-colors px-6 ${compact ? "py-4 md:px-6" : "py-5 md:px-16"}`}>
      <div className="flex flex-wrap items-center gap-x-3 gap-y-2 mb-2">
        <span className="font-mono text-[13px] text-white tracking-wide">{item.symbol || "—"}</span>
        <span className="text-[13px] text-gray-500 truncate max-w-[220px] md:max-w-[360px]">
          {decodeEntities(item.company_name)}
        </span>
        <span className="w-full sm:w-auto sm:ml-auto flex flex-wrap items-center gap-2">
          <ImportanceTag importance={item.importance} />
          <SentimentTag item={item} />
          {uncertain && (
            <span
              className="shrink-0 text-[9px] font-mono tracking-widest uppercase text-gray-600 whitespace-nowrap"
              title="Model confidence below 95% — treat this label as uncertain"
            >
              Low confidence
            </span>
          )}
        </span>
      </div>

      <p className={`text-gray-300 group-hover:text-white transition-colors leading-snug ${compact ? "text-[13px] line-clamp-2" : "text-[15px] line-clamp-3"}`}>
        {text}
      </p>

      <div className="mt-3 flex flex-wrap items-center gap-x-4 gap-y-1">
        <MonoLabel className="text-gray-500">{formatWhen(item.published_at)}</MonoLabel>
        {item.event_type && item.event_type !== item.headline && (
          <MonoLabel className="text-gray-600 truncate max-w-[280px]">{decodeEntities(item.event_type)}</MonoLabel>
        )}
        {(item.url || item.attachment_url) && (
          <a
            href={item.url || item.attachment_url}
            target="_blank"
            rel="noreferrer noopener"
            className="inline-flex items-center gap-1.5 touch:py-3.5 touch:-my-3.5 text-[10px] font-mono tracking-widest uppercase text-gray-500 hover:text-white transition-colors"
          >
            Filing <ExternalLink size={11} strokeWidth={1.5} />
          </a>
        )}
      </div>
    </article>
  );
}
