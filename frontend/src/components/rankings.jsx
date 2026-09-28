import React from "react";
import { Link } from "react-router-dom";
import { ArrowDown, Info } from "lucide-react";
import { HScroll, MonoLabel } from "./ui";

// Building blocks for the growth rankings (Sector, Predictor, Company pages).
// Scores are 0-100; key_metrics returns/ratios arrive as fractions (0.34 = 34%).

export const DISCLAIMER =
  "InvestIQ is a research and screening tool. Scores are model estimates, not investment advice.";

export const LABELS = ["Strong", "Positive", "Neutral", "Weak", "Insufficient data"];

export const SORTS = [
  { value: "rank", label: "Rank" },
  { value: "score", label: "Score" },
  { value: "name", label: "Name" },
  { value: "return_1y", label: "1Y return" },
];

const num = (v) => (v === null || v === undefined || v === "" ? null : Number(v));
const finite = (v) => Number.isFinite(num(v));

// 0.3412 -> "34.1%"; signed adds a leading +
export const fmtPct = (v, { signed = false, digits = 1 } = {}) => {
  if (!finite(v)) return "—";
  const n = num(v) * 100;
  return `${signed && n > 0 ? "+" : ""}${n.toFixed(digits)}%`;
};

// INR crore
export const fmtCr = (v, digits = 0) => {
  if (!finite(v)) return "—";
  return `₹${num(v).toLocaleString("en-IN", { maximumFractionDigits: digits, minimumFractionDigits: digits })} Cr`;
};

export const fmtPrice = (v) => {
  if (!finite(v)) return "—";
  return `₹${num(v).toLocaleString("en-IN", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
};

export const fmtRatio = (v, digits = 2) => (finite(v) ? `${num(v).toFixed(digits)}x` : "—");

export const fmtScore = (v) => (finite(v) ? num(v).toFixed(1) : "—");

export const fmtDate = (v, opts = { day: "2-digit", month: "short", year: "numeric" }) => {
  if (!v) return "—";
  const d = new Date(v);
  return Number.isNaN(d.getTime()) ? "—" : d.toLocaleDateString("en-IN", opts);
};

// Green/red only for up/down values
export const toneOf = (v) => (!finite(v) ? "text-gray-500" : num(v) >= 0 ? "text-green-500" : "text-red-400");

export function SignedPct({ value, className = "" }) {
  return <span className={`font-mono ${toneOf(value)} ${className}`}>{fmtPct(value, { signed: true })}</span>;
}

const LABEL_TONE = {
  Strong: "border-green-600 text-green-400",
  Positive: "border-green-900 text-green-600",
  Neutral: "border-gray-600 text-gray-300",
  Weak: "border-red-900 text-red-400",
  "Insufficient data": "border-gray-800 text-gray-600",
};

export function GrowthBadge({ label, className = "" }) {
  const text = label || "Insufficient data";
  return (
    <span
      className={`inline-block shrink-0 px-2.5 py-0.5 rounded-full border text-[9px] font-mono tracking-widest uppercase whitespace-nowrap ${LABEL_TONE[text] || LABEL_TONE.Neutral} ${className}`}
    >
      {text}
    </span>
  );
}

// Thin hairline bar, white fill on a gray-800 track
export function ScoreBar({ value, className = "", height = "h-[3px]" }) {
  const w = finite(value) ? Math.max(0, Math.min(100, num(value))) : 0;
  return (
    <div className={`w-full ${height} bg-gray-800 rounded-full overflow-hidden ${className}`}>
      <div className="h-full bg-white rounded-full transition-[width] duration-700" style={{ width: `${w}%` }} />
    </div>
  );
}

export function Disclaimer({ className = "" }) {
  return (
    <p className={`flex items-start gap-2 text-[10px] font-mono tracking-widest uppercase text-gray-500 leading-relaxed ${className}`}>
      <Info size={12} strokeWidth={1.5} className="shrink-0 mt-[1px]" />
      {DISCLAIMER}
    </p>
  );
}

export const StatusLine = ({ children, tone = "muted", className = "" }) => (
  <div className={`px-6 md:px-16 py-16 text-center text-[10px] font-mono tracking-widest uppercase ${tone === "error" ? "text-red-400" : "text-gray-500"} ${className}`}>
    {children}
  </div>
);

export const selectClass =
  "appearance-none touch:min-h-11 bg-white/5 border border-gray-700 rounded-full pl-4 pr-9 py-2.5 text-white text-[12px] font-mono tracking-wider uppercase outline-none focus:border-white transition-colors cursor-pointer [&>option]:bg-surface [&>option]:normal-case max-w-full";

// Header cell that doubles as a sort toggle when `sortKey` is given
function Th({ children, sortKey, sort, onSort, className = "" }) {
  const active = sortKey && sort === sortKey;
  return (
    <th className={`px-4 py-3 font-normal text-left ${className}`}>
      {sortKey && onSort ? (
        <button
          type="button"
          onClick={() => onSort(sortKey)}
          className={`inline-flex items-center gap-1 touch:min-h-11 touch:min-w-8 text-[10px] font-mono tracking-widest uppercase cursor-pointer transition-colors ${active ? "text-white" : "text-gray-500 hover:text-white"}`}
        >
          {children}
          {active && <ArrowDown size={11} strokeWidth={1.5} />}
        </button>
      ) : (
        <MonoLabel className="text-gray-500">{children}</MonoLabel>
      )}
    </th>
  );
}

const rankOf = (row, rankKey) => row[rankKey] ?? null;

// Ranked list: table on lg+, stacked cards on phones (one column) and tablets (two). `rankKey` picks which rank to show.
export function RankingTable({ rows, rankKey = "rank_overall", sort, onSort, showSector = false }) {
  return (
    <>
      {/* Desktop / tablet: table scrolls inside its own container, never the page */}
      <HScroll label="Ranked companies" className="hidden lg:block border-y border-gray-800">
        <table className="w-full min-w-[860px] border-collapse">
          <thead className="bg-surface border-b border-gray-800">
            <tr>
              <Th sortKey="rank" sort={sort} onSort={onSort} className="pl-6 lg:pl-16 w-[72px]">#</Th>
              <Th sortKey="name" sort={sort} onSort={onSort}>Company</Th>
              <Th>{showSector ? "Sector · Industry" : "Industry"}</Th>
              <Th sortKey="score" sort={sort} onSort={onSort} className="w-[220px]">Growth score</Th>
              <Th sortKey="return_1y" sort={sort} onSort={onSort} className="text-right">1Y return</Th>
              <Th className="text-right">Rev growth</Th>
              <Th className="pr-6 lg:pr-16 text-right">ROE</Th>
            </tr>
          </thead>
          <tbody>
            {rows.map((r) => {
              const km = r.key_metrics || {};
              const rank = rankOf(r, rankKey);
              return (
                <tr key={r.company_id ?? r.symbol} className="group border-b border-gray-800/70 last:border-b-0 hover:bg-surface transition-colors">
                  <td className="pl-6 lg:pl-16 px-4 py-4 font-mono text-[13px] text-gray-400">{rank ?? "—"}</td>
                  <td className="px-4 py-4 max-w-[320px]">
                    <Link to={`/company/${encodeURIComponent(r.symbol)}`} className="block touch:py-1.5 touch:-my-1.5">
                      <span className="block text-[15px] text-gray-200 group-hover:text-white transition-colors truncate">{r.name}</span>
                      <span className="block font-mono text-[11px] text-gray-500 tracking-wide">{r.symbol}</span>
                    </Link>
                  </td>
                  <td className="px-4 py-4 max-w-[240px]">
                    {showSector && r.sector && (
                      <Link to={`/sectors/${r.sector_slug}`} className="block touch:py-3.5 touch:-my-3.5 text-[12px] text-gray-400 hover:text-white truncate">{r.sector}</Link>
                    )}
                    <MonoLabel className="block text-gray-500 truncate">{r.industry || "—"}</MonoLabel>
                  </td>
                  <td className="px-4 py-4">
                    <div className="flex items-center gap-3">
                      <span className="font-mono text-[14px] text-white w-10">{fmtScore(r.growth_score)}</span>
                      <div className="flex-1 min-w-[56px]"><ScoreBar value={r.growth_score} /></div>
                      <GrowthBadge label={r.growth_label} />
                    </div>
                  </td>
                  <td className="px-4 py-4 text-right text-[13px]"><SignedPct value={km.return_1y} /></td>
                  <td className="px-4 py-4 text-right text-[13px]"><SignedPct value={km.revenue_growth_yoy} /></td>
                  <td className="pr-6 lg:pr-16 px-4 py-4 text-right font-mono text-[13px] text-gray-300">{fmtPct(km.roe)}</td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </HScroll>

      {/* Phones / tablets: stacked cards */}
      <div className="lg:hidden grid grid-cols-1 md:grid-cols-2 md:[&>*:last-child:nth-child(odd)]:col-span-2 gap-px bg-gray-800 border-y border-gray-800">
        {rows.map((r) => {
          const km = r.key_metrics || {};
          const rank = rankOf(r, rankKey);
          return (
            <Link
              key={r.company_id ?? r.symbol}
              to={`/company/${encodeURIComponent(r.symbol)}`}
              className="bg-page active:bg-surface px-6 py-5 flex flex-col gap-3"
            >
              <div className="flex items-start gap-4">
                <span className="font-mono text-[13px] text-gray-500 w-8 shrink-0 pt-0.5">{rank ?? "—"}</span>
                <div className="min-w-0 flex-1">
                  <p className="text-[15px] text-white leading-snug line-clamp-2">{r.name}</p>
                  <p className="font-mono text-[11px] text-gray-500 tracking-wide truncate">
                    {r.symbol} · {showSector && r.sector ? `${r.sector} · ` : ""}{r.industry || "—"}
                  </p>
                </div>
                <GrowthBadge label={r.growth_label} />
              </div>
              <div className="flex items-center gap-3 pl-12">
                <span className="font-mono text-[13px] text-white w-10">{fmtScore(r.growth_score)}</span>
                <ScoreBar value={r.growth_score} />
              </div>
              <div className="grid grid-cols-3 gap-2 pl-12">
                {[["1Y", <SignedPct key="1y" value={km.return_1y} />], ["Rev", <SignedPct key="rev" value={km.revenue_growth_yoy} />], ["ROE", <span key="roe" className="font-mono text-gray-300">{fmtPct(km.roe)}</span>]].map(([k, v]) => (
                  <div key={k} className="flex flex-col gap-1 text-[12px]">
                    <MonoLabel className="text-gray-600">{k}</MonoLabel>
                    {v}
                  </div>
                ))}
              </div>
            </Link>
          );
        })}
      </div>
    </>
  );
}
