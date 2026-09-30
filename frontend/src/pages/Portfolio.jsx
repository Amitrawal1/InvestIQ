import React, { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { Link, useNavigate, useSearchParams } from "react-router-dom";
import { AnimatePresence, motion } from "motion/react";
import {
  Chart as ChartJS, CategoryScale, LinearScale, PointElement, LineElement, Tooltip, Legend, Filler,
} from "chart.js";
import { Line } from "react-chartjs-2";
import { AlertTriangle, ArrowDown, ArrowUp, ArrowUpRight, Check, Info, Link2, Lock, Unplug, X } from "lucide-react";
import Navbar from "../components/Navbar";
import Footer from "../components/Footer";
import { PageHeading, Panel, MonoLabel, SectionLabel, PrimaryButton, TouchPill, HScroll, fadeUp, stagger } from "../components/ui";
import { GrowthBadge, ScoreBar, StatusLine, fmtScore, fmtPrice } from "../components/rankings";
import { ghostButton } from "../components/ConfirmDialog";
import {
  BROKERS, BROKER_ORDER, CONSENT_NOTE, BrokerStatus, DisconnectDialog, SpinIcon,
  brokerName, connectionState, finite, fmtINR, fmtPctPts, fmtQty, fmtSyncTime, gainTone, linkErrorText, useBrokerConnect,
} from "../components/brokers";
import useChartTheme from "../hooks/useChartTheme";
import { apiError, getPortfolio, syncBroker } from "../services/api";
import usePageTitle from "../hooks/usePageTitle";

ChartJS.register(CategoryScale, LinearScale, PointElement, LineElement, Tooltip, Legend, Filler);

const PORTFOLIO_DISCLAIMER =
  "Read-only view of your broker accounts. InvestIQ scores are model estimates, not investment advice.";

// --- layout pieces ---

// `flush` lets full-bleed tables run edge to edge while the heading keeps the page gutter
const Block = ({ index, label, title, aside, children, flush = false }) => (
  <motion.section
    initial="initial"
    whileInView="animate"
    viewport={{ once: true, margin: "-60px" }}
    variants={stagger(0, 0.08)}
    className={`border-t border-gray-800 py-12 md:py-14 ${flush ? "" : "px-6 md:px-16"}`}
  >
    {(label || title) && (
      <motion.div variants={fadeUp} className={`flex flex-col md:flex-row md:items-end justify-between gap-4 mb-8 md:mb-10 ${flush ? "px-6 md:px-16" : ""}`}>
        <div>
          <SectionLabel index={index} className="mb-4">{label}</SectionLabel>
          {title && <h2 className="text-[1.8rem] md:text-[2.4rem] font-normal tracking-tight leading-none text-white">{title}</h2>}
        </div>
        {aside}
      </motion.div>
    )}
    <motion.div variants={fadeUp}>{children}</motion.div>
  </motion.section>
);

// Dismissible banner for link results, sync problems, etc.
function Notice({ notice, onDismiss }) {
  return (
    <AnimatePresence>
      {notice && (
        <motion.div
          key={notice.id}
          initial={{ opacity: 0, y: -8 }}
          animate={{ opacity: 1, y: 0 }}
          exit={{ opacity: 0, y: -8 }}
          className="px-6 md:px-16 pb-6"
        >
          <div
            role={notice.tone === "error" ? "alert" : "status"}
            className={`flex items-start gap-3 rounded-xl border bg-surface px-5 py-4 ${
              notice.tone === "error" ? "border-red-900" : notice.tone === "success" ? "border-green-900" : "border-gray-800"
            }`}
          >
            <span className={`mt-0.5 shrink-0 ${notice.tone === "error" ? "text-red-400" : notice.tone === "success" ? "text-green-500" : "text-gray-400"}`}>
              {notice.tone === "error" ? <AlertTriangle size={16} strokeWidth={1.5} /> : notice.tone === "success" ? <Check size={16} strokeWidth={1.5} /> : <Info size={16} strokeWidth={1.5} />}
            </span>
            <p className="flex-1 text-sm text-gray-200 leading-relaxed">{notice.text}</p>
            {notice.action && (
              <button
                type="button"
                onClick={notice.action.onClick}
                className="shrink-0 touch:py-3.5 touch:-my-3.5 text-[11px] font-mono tracking-widest uppercase text-white underline underline-offset-4 hover:text-accent transition-colors cursor-pointer"
              >
                {notice.action.label}
              </button>
            )}
            <button type="button" onClick={onDismiss} aria-label="Dismiss" className="shrink-0 touch:p-3.5 touch:-m-3.5 text-gray-500 hover:text-white transition-colors cursor-pointer">
              <X size={16} strokeWidth={1.5} />
            </button>
          </div>
        </motion.div>
      )}
    </AnimatePresence>
  );
}

// --- empty state ---

function ConnectCards({ connections, onConnect, pending, error }) {
  return (
    <Block index="01" label="Link a broker" title="Connect your accounts">
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4 max-w-[980px]">
        {BROKER_ORDER.map((b) => {
          const c = connections.find((x) => x.broker === b);
          const configured = c?.configured !== false;
          return (
            <Panel key={b} glow className="p-7 md:p-8 flex flex-col">
              <div className="flex items-start justify-between gap-4">
                <div>
                  <MonoLabel className="text-gray-500">Broker</MonoLabel>
                  <h3 className="mt-2 text-2xl font-normal tracking-tight text-white">{BROKERS[b].name}</h3>
                </div>
                {!configured && (
                  <span className="px-3 py-1 rounded-full border border-gray-700 text-[10px] font-mono tracking-widest uppercase text-gray-500">
                    Coming soon
                  </span>
                )}
              </div>
              <p className="mt-4 text-sm text-gray-400 leading-relaxed flex-1">{BROKERS[b].note}</p>
              <div className="mt-8">
                <PrimaryButton
                  type="button"
                  icon={Link2}
                  disabled={!configured || Boolean(pending)}
                  onClick={() => onConnect(b)}
                  className="w-full sm:w-auto"
                >
                  {pending === b ? "Opening…" : configured ? `Connect ${BROKERS[b].name}` : "Not available yet"}
                </PrimaryButton>
              </div>
            </Panel>
          );
        })}
      </div>

      {error && <p role="alert" className="mt-6 text-[11px] font-mono tracking-wider uppercase text-red-400">{error}</p>}

      <div className="mt-8 max-w-[980px] flex items-start gap-3 rounded-xl border border-gray-800 px-5 py-4">
        <Lock size={15} strokeWidth={1.5} className="shrink-0 mt-0.5 text-gray-400" aria-hidden="true" />
        <p className="text-[13px] text-gray-400 leading-relaxed">{CONSENT_NOTE}</p>
      </div>
    </Block>
  );
}

// --- linked: accounts strip ---

function BrokerAccounts({ connections, onConnect, onDisconnect, pending, connectError }) {
  return (
    <div className="px-6 md:px-16 pb-10">
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-px bg-gray-800 border border-gray-800 rounded-xl overflow-hidden">
        {BROKER_ORDER.map((b) => {
          const c = connections.find((x) => x.broker === b) || { broker: b };
          const state = connectionState(c);
          const configured = c.configured !== false;
          return (
            <div key={b} className="bg-surface px-5 md:px-6 py-5 flex flex-col sm:flex-row sm:items-center gap-4 justify-between">
              <div className="min-w-0">
                <div className="flex items-center gap-3 flex-wrap">
                  <span className="text-[15px] text-white">{brokerName(b)}</span>
                  <BrokerStatus connection={c} />
                </div>
                <MonoLabel className="block mt-2 text-gray-500 normal-case tracking-wider truncate">
                  {state === "unlinked"
                    ? configured ? "Not linked" : "Coming soon"
                    : [c.broker_user_name, c.broker_user_id].filter(Boolean).join(" · ") || "Linked account"}
                </MonoLabel>
              </div>
              <div className="flex items-center gap-2 shrink-0">
                {state === "expired" && (
                  <button type="button" onClick={() => onConnect(b)} disabled={Boolean(pending)} className={ghostButton.replace("border-gray-600 text-gray-300", "border-white text-white")}>
                    {pending === b ? "Opening…" : "Reconnect"}
                  </button>
                )}
                {state === "unlinked" && configured && (
                  <button type="button" onClick={() => onConnect(b)} disabled={Boolean(pending)} className={ghostButton}>
                    <Link2 size={13} strokeWidth={1.5} /> {pending === b ? "Opening…" : "Connect"}
                  </button>
                )}
                {state !== "unlinked" && (
                  <button type="button" onClick={() => onDisconnect(b)} className={ghostButton}>
                    <Unplug size={13} strokeWidth={1.5} /> Disconnect
                  </button>
                )}
              </div>
            </div>
          );
        })}
      </div>
      {connectError && <p role="alert" className="mt-4 text-[11px] font-mono tracking-wider uppercase text-red-400">{connectError}</p>}
    </div>
  );
}

// --- summary ---

function Stat({ label, value, sub, tone = "text-white" }) {
  return (
    <div className="bg-page px-5 md:px-6 py-6 flex flex-col gap-3 min-w-0">
      <MonoLabel className="text-gray-500">{label}</MonoLabel>
      <span className={`text-[1.45rem] md:text-[1.7rem] font-normal tracking-tight leading-none truncate ${tone}`}>{value}</span>
      {sub && <span className="text-[11px] font-mono tracking-wider text-gray-500 truncate">{sub}</span>}
    </div>
  );
}

function Summary({ summary }) {
  const s = summary || {};
  const synced = fmtSyncTime(s.last_synced_at);
  return (
    <div className="grid grid-cols-2 lg:grid-cols-3 xl:grid-cols-6 gap-px bg-gray-800 border-y border-gray-800">
      <Stat label="Current value" value={fmtINR(s.current)} />
      <Stat label="Invested" value={fmtINR(s.invested)} />
      <Stat
        label="Total P&L"
        value={fmtINR(s.pnl, { signed: true })}
        sub={fmtPctPts(s.pnl_pct, { signed: true })}
        tone={gainTone(s.pnl)}
      />
      <Stat
        label="Today"
        value={fmtINR(s.day_change, { signed: true })}
        sub={fmtPctPts(s.day_change_pct, { signed: true })}
        tone={gainTone(s.day_change)}
      />
      <Stat label="Holdings" value={finite(s.holdings_count) ? Number(s.holdings_count) : "—"} />
      <Stat label="Last synced" value={synced || "Never"} tone={synced ? "text-white" : "text-gray-500"} />
    </div>
  );
}

// --- value history ---

const mono = { family: "ui-monospace, SFMono-Regular, Menlo, monospace", size: 10 };

const compactINR = (v) => {
  const n = Math.abs(v);
  const sign = v < 0 ? "−" : "";
  // Enough decimals that neighbouring ticks stay distinct (₹2.62L vs ₹2.64L)
  if (n >= 1e7) return `${sign}₹${+(n / 1e7).toFixed(n >= 1e8 ? 1 : 2)}Cr`;
  if (n >= 1e5) return `${sign}₹${+(n / 1e5).toFixed(n >= 1e6 ? 1 : 2)}L`;
  if (n >= 1e3) return `${sign}₹${(n / 1e3).toFixed(0)}K`;
  return `${sign}₹${n.toFixed(0)}`;
};

function ValueChart({ history }) {
  const c = useChartTheme();
  const rows = useMemo(() => (history || []).filter((h) => finite(h.current)), [history]);
  if (rows.length < 2) return null;

  const labels = rows.map((r) => new Date(r.date).toLocaleDateString("en-IN", { day: "2-digit", month: "short" }));
  const areaFill = (context) => {
    const { ctx, chartArea } = context.chart;
    if (!chartArea) return null;
    const g = ctx.createLinearGradient(0, chartArea.top, 0, chartArea.bottom);
    g.addColorStop(0, `rgba(${c.lineRgb}, 0.14)`);
    g.addColorStop(1, `rgba(${c.lineRgb}, 0)`);
    return g;
  };

  const data = {
    labels,
    datasets: [
      {
        label: "Current value",
        data: rows.map((r) => Number(r.current)),
        borderColor: c.line,
        borderWidth: 2,
        pointRadius: rows.length < 20 ? 2 : 0,
        pointHoverRadius: 4,
        pointBackgroundColor: c.line,
        tension: 0.2,
        fill: "start",
        backgroundColor: areaFill,
      },
      {
        label: "Invested",
        data: rows.map((r) => (finite(r.invested) ? Number(r.invested) : null)),
        borderColor: c.secondary,
        borderWidth: 1.5,
        borderDash: [5, 4],
        pointRadius: 0,
        pointHoverRadius: 4,
        tension: 0.2,
        spanGaps: true,
      },
    ],
  };

  const options = {
    responsive: true,
    maintainAspectRatio: false,
    interaction: { mode: "index", intersect: false },
    plugins: {
      legend: { position: "top", align: "end", labels: { color: c.muted, font: mono, usePointStyle: true, pointStyle: "line", boxWidth: 24 } },
      tooltip: {
        backgroundColor: c.tooltipBg,
        titleColor: c.tooltipTitle,
        bodyColor: c.tooltipBody,
        borderColor: c.tooltipBorder,
        borderWidth: 1,
        titleFont: { family: "Inter", weight: "500" },
        bodyFont: { family: "Inter" },
        padding: 12,
        callbacks: { label: (ctx) => ` ${ctx.dataset.label}: ${fmtINR(ctx.parsed.y)}` },
      },
    },
    scales: {
      x: { grid: { display: false }, border: { color: c.axis }, ticks: { color: c.muted, font: mono, maxRotation: 0, autoSkipPadding: 20 } },
      y: { grid: { color: c.grid }, border: { display: false }, ticks: { color: c.muted, font: mono, callback: (v) => compactINR(v) } },
    },
  };

  return (
    <Block index="02" label="History" title="Portfolio value">
      <div className="h-[300px] md:h-[340px]" role="img" aria-label={`Portfolio value over ${rows.length} days`}>
        <Line data={data} options={options} />
      </div>
    </Block>
  );
}

// --- holdings ---

const SORT_KEYS = {
  name: (h) => (h.name || h.company_name || h.symbol || "").toLowerCase(),
  broker: (h) => h.broker || "",
  quantity: (h) => Number(h.quantity) || 0,
  average_price: (h) => Number(h.average_price) || 0,
  last_price: (h) => Number(h.last_price) || 0,
  invested: (h) => Number(h.invested) || 0,
  current_value: (h) => Number(h.current_value) || 0,
  pnl: (h) => Number(h.pnl) || 0,
  day_change: (h) => Number(h.day_change) || 0,
  allocation: (h) => h.allocation || 0,
  growth_score: (h) => (finite(h.growth_score) ? Number(h.growth_score) : -1),
};

function SortTh({ children, k, sort, onSort, className = "" }) {
  const active = sort.key === k;
  const Arrow = sort.dir === "asc" ? ArrowUp : ArrowDown;
  return (
    <th className={`px-3 py-3 font-normal ${className}`} aria-sort={active ? (sort.dir === "asc" ? "ascending" : "descending") : "none"}>
      <button
        type="button"
        onClick={() => onSort(k)}
        className={`inline-flex items-center gap-1 touch:min-h-11 text-[10px] font-mono tracking-widest uppercase whitespace-nowrap cursor-pointer transition-colors ${active ? "text-white" : "text-gray-500 hover:text-white"}`}
      >
        {children}
        {active && <Arrow size={11} strokeWidth={1.5} />}
      </button>
    </th>
  );
}

const displayName = (h) => h.name || h.company_name || h.symbol;
const scoreLabel = (h) => h.growth_label || (h.company_id ? "Insufficient data" : "Not rated");

function ScoreCell({ h }) {
  return (
    <div className="flex items-center justify-end gap-2">
      <span className="font-mono text-[13px] text-white">{fmtScore(h.growth_score)}</span>
      <GrowthBadge label={scoreLabel(h)} />
    </div>
  );
}

function HoldingName({ h }) {
  const inner = (
    <>
      <span className="block text-[14px] text-gray-200 group-hover:text-white transition-colors truncate">{displayName(h)}</span>
      <span className="block font-mono text-[11px] text-gray-500 tracking-wide truncate">
        {h.symbol}{h.exchange ? ` · ${h.exchange}` : ""}{h.sector ? ` · ${h.sector}` : ""}
      </span>
    </>
  );
  return h.symbol ? (
    <Link to={`/company/${encodeURIComponent(h.symbol)}`} className="block min-w-0 touch:py-1.5 touch:-my-1.5">{inner}</Link>
  ) : (
    <div className="min-w-0">{inner}</div>
  );
}

function Holdings({ holdings, total }) {
  const [sort, setSort] = useState({ key: "current_value", dir: "desc" });
  const navigate = useNavigate();

  const rows = useMemo(() => {
    const withAlloc = holdings.map((h) => ({
      ...h,
      allocation: total > 0 && finite(h.current_value) ? (Number(h.current_value) / total) * 100 : null,
    }));
    const get = SORT_KEYS[sort.key] || SORT_KEYS.current_value;
    const dir = sort.dir === "asc" ? 1 : -1;
    return withAlloc.sort((a, b) => {
      const x = get(a);
      const y = get(b);
      return (x > y ? 1 : x < y ? -1 : 0) * dir;
    });
  }, [holdings, total, sort]);

  const onSort = (key) =>
    setSort((s) => (s.key === key ? { key, dir: s.dir === "asc" ? "desc" : "asc" } : { key, dir: key === "name" || key === "broker" ? "asc" : "desc" }));

  if (!holdings.length) {
    return <p className="px-6 md:px-16 py-10 text-[11px] font-mono tracking-widest uppercase text-gray-500">No holdings in the latest sync.</p>;
  }

  const th = { sort, onSort };
  return (
    <>
      <HScroll label="Holdings" className="hidden xl:block border-y border-gray-800">
        <table className="w-full min-w-[1180px] border-collapse">
          <thead className="bg-surface border-b border-gray-800">
            <tr className="text-right">
              <SortTh k="name" {...th} className="pl-6 lg:pl-16 text-left">Holding</SortTh>
              <SortTh k="broker" {...th} className="text-left">Broker</SortTh>
              <SortTh k="quantity" {...th}>Qty</SortTh>
              <SortTh k="average_price" {...th}>Avg</SortTh>
              <SortTh k="last_price" {...th}>LTP</SortTh>
              <SortTh k="invested" {...th}>Invested</SortTh>
              <SortTh k="current_value" {...th}>Current</SortTh>
              <SortTh k="pnl" {...th}>P&amp;L</SortTh>
              <SortTh k="day_change" {...th}>Day</SortTh>
              <SortTh k="allocation" {...th}>Alloc</SortTh>
              <SortTh k="growth_score" {...th} className="pr-6 lg:pr-16">InvestIQ score</SortTh>
            </tr>
          </thead>
          <tbody>
            {rows.map((h) => (
              <tr
                key={`${h.broker}-${h.symbol}-${h.isin || ""}`}
                onClick={(e) => { if (h.symbol && !e.target.closest("a")) navigate(`/company/${encodeURIComponent(h.symbol)}`); }}
                className="group border-b border-gray-800/70 last:border-b-0 hover:bg-surface transition-colors cursor-pointer text-right font-mono text-[13px] text-gray-300"
              >
                <td className="pl-6 lg:pl-16 px-3 py-4 text-left font-sans max-w-[280px]"><HoldingName h={h} /></td>
                <td className="px-3 py-4 text-left"><MonoLabel className="text-gray-500">{brokerName(h.broker)}</MonoLabel></td>
                <td className="px-3 py-4">{fmtQty(h.quantity)}</td>
                <td className="px-3 py-4">{fmtPrice(h.average_price)}</td>
                <td className="px-3 py-4 text-white">{fmtPrice(h.last_price)}</td>
                <td className="px-3 py-4">{fmtINR(h.invested)}</td>
                <td className="px-3 py-4 text-white">{fmtINR(h.current_value)}</td>
                <td className={`px-3 py-4 ${gainTone(h.pnl)}`}>
                  <span className="block">{fmtINR(h.pnl, { signed: true })}</span>
                  <span className="block text-[11px] opacity-80">{fmtPctPts(h.pnl_pct, { signed: true })}</span>
                </td>
                <td className={`px-3 py-4 ${gainTone(h.day_change)}`}>
                  <span className="block">{fmtINR(h.day_change, { signed: true })}</span>
                  <span className="block text-[11px] opacity-80">{fmtPctPts(h.day_change_pct, { signed: true })}</span>
                </td>
                <td className="px-3 py-4">{fmtPctPts(h.allocation, { digits: 1 })}</td>
                <td className="pr-6 lg:pr-16 px-3 py-4"><ScoreCell h={h} /></td>
              </tr>
            ))}
          </tbody>
        </table>
      </HScroll>

      {/* Phones / tablets: stacked cards */}
      <div className="xl:hidden">
        <HScroll label="Sort holdings" innerClassName="px-6 md:px-16 pb-4 flex items-center gap-2">
          <MonoLabel className="text-gray-500 shrink-0">Sort</MonoLabel>
          {[["current_value", "Value"], ["pnl", "P&L"], ["day_change", "Today"], ["growth_score", "Score"], ["name", "Name"]].map(([k, l]) => (
            <button
              key={k}
              type="button"
              onClick={() => onSort(k)}
              className={`shrink-0 min-h-11 px-4 rounded-full border text-[10px] font-mono tracking-widest uppercase cursor-pointer transition-colors ${sort.key === k ? "border-white text-white" : "border-gray-700 text-gray-500"}`}
            >
              {l}{sort.key === k ? (sort.dir === "asc" ? " ↑" : " ↓") : ""}
            </button>
          ))}
        </HScroll>
        <div className="grid grid-cols-1 md:grid-cols-2 md:[&>*:last-child:nth-child(odd)]:col-span-2 gap-px bg-gray-800 border-y border-gray-800">
          {rows.map((h) => (
            <Link
              key={`${h.broker}-${h.symbol}-${h.isin || ""}`}
              to={`/company/${encodeURIComponent(h.symbol)}`}
              className="bg-page active:bg-surface px-6 py-5 flex flex-col gap-4"
            >
              <div className="flex items-start justify-between gap-3">
                <div className="min-w-0">
                  <p className="text-[15px] text-white leading-snug line-clamp-2">{displayName(h)}</p>
                  <p className="font-mono text-[11px] text-gray-500 tracking-wide truncate">{h.symbol} · {brokerName(h.broker)}</p>
                </div>
                <div className="text-right shrink-0">
                  <p className="font-mono text-[14px] text-white">{fmtINR(h.current_value)}</p>
                  <p className={`font-mono text-[12px] ${gainTone(h.pnl)}`}>{fmtINR(h.pnl, { signed: true })} · {fmtPctPts(h.pnl_pct, { signed: true, digits: 1 })}</p>
                </div>
              </div>
              <div className="grid grid-cols-4 gap-2 text-[12px] font-mono">
                {[
                  ["Qty", fmtQty(h.quantity), "text-gray-300"],
                  ["Avg", fmtPrice(h.average_price), "text-gray-300"],
                  ["LTP", fmtPrice(h.last_price), "text-gray-300"],
                  ["Today", fmtPctPts(h.day_change_pct, { signed: true, digits: 1 }), gainTone(h.day_change)],
                ].map(([k, v, tone]) => (
                  <div key={k} className="flex flex-col gap-1 min-w-0">
                    <MonoLabel className="text-gray-600">{k}</MonoLabel>
                    <span className={`truncate ${tone}`}>{v}</span>
                  </div>
                ))}
              </div>
              <div className="flex items-center justify-between gap-3">
                <MonoLabel className="text-gray-500">{fmtPctPts(h.allocation, { digits: 1 })} of portfolio</MonoLabel>
                <ScoreCell h={h} />
              </div>
            </Link>
          ))}
        </div>
      </div>
    </>
  );
}

// --- positions + funds ---

function Positions({ positions }) {
  if (!positions.length) {
    return <p className="px-6 md:px-16 py-10 text-[11px] font-mono tracking-widest uppercase text-gray-500">No open positions today.</p>;
  }
  const hasBroker = positions.some((p) => p.broker);
  return (
    <>
    <HScroll label="Open positions" className="hidden lg:block border-y border-gray-800">
      <table className="w-full min-w-[820px] border-collapse">
        <thead className="bg-surface border-b border-gray-800">
          <tr className="text-right">
            {["Symbol", ...(hasBroker ? ["Broker"] : []), "Product", "Qty", "Avg", "LTP", "P&L", "Realised", "Unrealised"].map((t, i, all) => (
              <th key={t} className={`px-3 py-3 font-normal ${i === 0 ? "pl-6 lg:pl-16 text-left" : ""} ${t === "Broker" || t === "Product" ? "text-left" : ""} ${i === all.length - 1 ? "pr-6 lg:pr-16" : ""}`}>
                <MonoLabel className="text-gray-500">{t}</MonoLabel>
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {positions.map((p, i) => (
            <tr key={`${p.broker || ""}-${p.symbol}-${p.product}-${i}`} className="border-b border-gray-800/70 last:border-b-0 text-right font-mono text-[13px] text-gray-300">
              <td className="pl-6 lg:pl-16 px-3 py-4 text-left">
                <span className="block text-white">{p.symbol}</span>
                <span className="block text-[11px] text-gray-500">{p.exchange || ""}</span>
              </td>
              {hasBroker && <td className="px-3 py-4 text-left"><MonoLabel className="text-gray-500">{brokerName(p.broker)}</MonoLabel></td>}
              <td className="px-3 py-4 text-left"><MonoLabel className="text-gray-400">{p.product || "—"}</MonoLabel></td>
              <td className={`px-3 py-4 ${Number(p.quantity) < 0 ? "text-red-400" : ""}`}>{fmtQty(p.quantity)}</td>
              <td className="px-3 py-4">{fmtPrice(p.average_price)}</td>
              <td className="px-3 py-4 text-white">{fmtPrice(p.last_price)}</td>
              <td className={`px-3 py-4 ${gainTone(p.pnl)}`}>{fmtINR(p.pnl, { signed: true, digits: 2 })}</td>
              <td className={`px-3 py-4 ${gainTone(p.realised)}`}>{fmtINR(p.realised, { signed: true, digits: 2 })}</td>
              <td className={`pr-6 lg:pr-16 px-3 py-4 ${gainTone(p.unrealised)}`}>{fmtINR(p.unrealised, { signed: true, digits: 2 })}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </HScroll>

    {/* Phones / tablets: stacked cards */}
    <div className="lg:hidden grid grid-cols-1 md:grid-cols-2 md:[&>*:last-child:nth-child(odd)]:col-span-2 gap-px bg-gray-800 border-y border-gray-800">
      {positions.map((p, i) => (
        <div key={`${p.broker || ""}-${p.symbol}-${p.product}-${i}`} className="bg-page px-6 py-5 flex flex-col gap-4">
          <div className="flex items-start justify-between gap-3">
            <div className="min-w-0">
              <p className="font-mono text-[15px] text-white truncate">{p.symbol}</p>
              <MonoLabel className="text-gray-500">
                {[p.exchange, p.product, hasBroker ? brokerName(p.broker) : null].filter(Boolean).join(" · ") || "—"}
              </MonoLabel>
            </div>
            <div className="text-right shrink-0">
              <p className={`font-mono text-[14px] ${gainTone(p.pnl)}`}>{fmtINR(p.pnl, { signed: true, digits: 2 })}</p>
              <MonoLabel className="text-gray-600">P&amp;L</MonoLabel>
            </div>
          </div>
          <div className="grid grid-cols-3 gap-2 text-[12px] font-mono">
            {[
              ["Qty", fmtQty(p.quantity), Number(p.quantity) < 0 ? "text-red-400" : "text-gray-300"],
              ["Avg", fmtPrice(p.average_price), "text-gray-300"],
              ["LTP", fmtPrice(p.last_price), "text-white"],
              ["Realised", fmtINR(p.realised, { signed: true, digits: 2 }), gainTone(p.realised)],
              ["Unrealised", fmtINR(p.unrealised, { signed: true, digits: 2 }), gainTone(p.unrealised)],
            ].map(([k, v, tone]) => (
              <div key={k} className="flex flex-col gap-1 min-w-0">
                <MonoLabel className="text-gray-600">{k}</MonoLabel>
                <span className={`truncate ${tone}`}>{v}</span>
              </div>
            ))}
          </div>
        </div>
      ))}
    </div>
    </>
  );
}

function Funds({ funds, connections }) {
  const linked = BROKER_ORDER.filter((b) => connectionState(connections.find((c) => c.broker === b)) !== "unlinked");
  return (
    <div className="px-6 md:px-16">
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4 max-w-[980px]">
        {linked.map((b) => {
          const f = funds?.[b];
          return (
            <Panel key={b} className="p-6 md:p-7">
              <MonoLabel className="text-gray-500">{brokerName(b)} · equity funds</MonoLabel>
              {f ? (
                <dl className="mt-5 grid grid-cols-2 sm:grid-cols-3 gap-4">
                  {[["Available", f.available_cash], ["Used margin", f.used_margin], ["Total", f.total]].map(([k, v], i) => (
                    <div key={k} className={`min-w-0 ${i === 2 ? "col-span-2 sm:col-span-1" : ""}`}>
                      <dt><MonoLabel className="text-gray-600">{k}</MonoLabel></dt>
                      <dd className="mt-2 font-mono text-[15px] text-white truncate">{fmtINR(v, { digits: 2 })}</dd>
                    </div>
                  ))}
                </dl>
              ) : (
                <p className="mt-5 text-sm text-gray-500">Funds weren't available in the latest sync.</p>
              )}
            </Panel>
          );
        })}
      </div>
    </div>
  );
}

// --- insights ---

const risksOf = (f) => (Array.isArray(f.risks) ? f.risks : f.risks ? [f.risks] : []).map((r) => (typeof r === "string" ? r : r?.text || r?.label || JSON.stringify(r)));

function Insights({ insights, holdings }) {
  const ins = insights || {};
  const sectors = (ins.sector_allocation || []).filter((s) => finite(s.pct)).sort((a, b) => b.pct - a.pct);
  const shown = sectors.slice(0, 8);
  const rest = sectors.slice(8);
  if (rest.length) {
    shown.push({
      sector: `Other (${rest.length})`,
      pct: rest.reduce((t, s) => t + Number(s.pct), 0),
      value: rest.reduce((t, s) => t + (Number(s.value) || 0), 0),
    });
  }
  const maxPct = Math.max(...shown.map((s) => Number(s.pct)), 1);
  const flagged = ins.flagged || [];
  const nameOf = (sym) => {
    const h = holdings.find((x) => x.symbol === sym);
    return h ? displayName(h) : sym;
  };

  return (
    <Block index="04" label="Insights" title="What InvestIQ sees">
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
        <Panel glow className="p-6 md:p-7 flex flex-col">
          <MonoLabel className="text-gray-500">Weighted InvestIQ score</MonoLabel>
          <div className="mt-4 flex items-end gap-3">
            <span className="text-[3rem] font-normal tracking-tight leading-none text-white">{fmtScore(ins.weighted_score)}</span>
            <span className="pb-1.5 text-[11px] font-mono text-gray-500">/ 100</span>
          </div>
          <ScoreBar value={ins.weighted_score} className="mt-5" />
          <p className="mt-4 text-[12px] text-gray-500 leading-relaxed">Average growth score of rated holdings, weighted by current value.</p>
          <div className="mt-auto pt-6"><div className="grid grid-cols-3 gap-px bg-gray-800 border border-gray-800 rounded-lg overflow-hidden">
            {[["Strong", ins.strong_count, "text-green-500"], ["Weak", ins.weak_count, "text-red-400"], ["Unrated", ins.unrated_count, "text-gray-400"]].map(([k, v, tone]) => (
              <div key={k} className="bg-surface px-3 py-3">
                <MonoLabel className="text-gray-600">{k}</MonoLabel>
                <p className={`mt-1 font-mono text-[18px] ${tone}`}>{finite(v) ? Number(v) : "—"}</p>
              </div>
            ))}
          </div></div>
        </Panel>

        <Panel className="p-6 md:p-7">
          <div className="flex items-baseline justify-between gap-3">
            <MonoLabel className="text-gray-500">Sector allocation</MonoLabel>
            {ins.top_sector && <MonoLabel className="text-gray-600 normal-case tracking-wider truncate">Top: {ins.top_sector} {fmtPctPts(ins.top_sector_pct, { digits: 0 })}</MonoLabel>}
          </div>
          {shown.length ? (
            <ul className="mt-5 space-y-4">
              {shown.map((s) => (
                <li key={s.sector || "unknown"}>
                  <div className="flex items-baseline justify-between gap-3 text-[13px]">
                    <span className="text-gray-200 truncate">{s.sector || "Unclassified"}</span>
                    <span className="font-mono text-gray-400 shrink-0">{fmtPctPts(s.pct, { digits: 1 })}</span>
                  </div>
                  <div className="mt-1.5 h-[3px] w-full bg-gray-800 rounded-full overflow-hidden">
                    <div className="h-full bg-white rounded-full" style={{ width: `${(Number(s.pct) / maxPct) * 100}%` }} />
                  </div>
                </li>
              ))}
            </ul>
          ) : (
            <p className="mt-5 text-sm text-gray-500">No sector data yet.</p>
          )}
        </Panel>

        <Panel className="p-6 md:p-7">
          <MonoLabel className="text-gray-500">Flagged holdings</MonoLabel>
          {flagged.length ? (
            <ul className="mt-5 divide-y divide-gray-800">
              {flagged.map((f) => (
                <li key={`${f.broker || ""}-${f.symbol}`} className="py-3 first:pt-0 last:pb-0">
                  <Link to={`/company/${encodeURIComponent(f.symbol)}`} className="group flex items-center justify-between gap-3">
                    <span className="min-w-0">
                      <span className="block text-[14px] text-gray-200 group-hover:text-white truncate">{f.name || nameOf(f.symbol)}</span>
                      <span className="block font-mono text-[11px] text-gray-500">{f.symbol}{f.broker ? ` · ${brokerName(f.broker)}` : ""}</span>
                    </span>
                    <ArrowUpRight size={14} strokeWidth={1.5} className="shrink-0 text-gray-600 group-hover:text-white" />
                  </Link>
                  <ul className="mt-2 space-y-1">
                    {risksOf(f).map((r, i) => (
                      <li key={i} className="flex items-start gap-2 text-[12px] text-gray-400 leading-relaxed">
                        <AlertTriangle size={11} strokeWidth={1.5} className="shrink-0 mt-[3px] text-red-400" aria-hidden="true" />
                        {r}
                      </li>
                    ))}
                  </ul>
                </li>
              ))}
            </ul>
          ) : (
            <p className="mt-5 text-sm text-gray-500">Nothing flagged. No holding has a Weak label or notable model risk.</p>
          )}
        </Panel>
      </div>
    </Block>
  );
}

// --- page ---

let noticeSeq = 0;

export default function Portfolio() {
  usePageTitle("Portfolio");
  const [params, setParams] = useSearchParams();
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState("");
  const [notice, setNotice] = useState(null);
  const [syncing, setSyncing] = useState(false);
  const [tab, setTab] = useState("holdings");
  const [disconnecting, setDisconnecting] = useState(null);
  const [expiredDismissed, setExpiredDismissed] = useState(false);
  const { connect, pending, error: connectError } = useBrokerConnect();
  const requestId = useRef(0);

  const show = (tone, text, action) => setNotice({ id: ++noticeSeq, tone, text, action });

  const load = useCallback(async ({ quiet = false } = {}) => {
    const id = ++requestId.current;
    if (!quiet) setLoading(true);
    setLoadError("");
    try {
      const res = await getPortfolio();
      if (id === requestId.current) setData(res);
    } catch (err) {
      if (id === requestId.current) setLoadError(apiError(err, "Couldn't load your portfolio."));
    } finally {
      if (id === requestId.current) setLoading(false);
    }
  }, []);

  useEffect(() => { load(); }, [load]);

  // ?linked=upstox / ?error=code from the broker callback -> notice, then tidy the URL
  useEffect(() => {
    const linked = params.get("linked");
    const error = params.get("error");
    if (!linked && !error) return;
    if (linked) show("success", `${brokerName(linked)} linked. Your holdings are synced read-only.`);
    else show("error", linkErrorText(error));
    const next = new URLSearchParams(params);
    next.delete("linked");
    next.delete("error");
    next.delete("broker");
    setParams(next, { replace: true });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const connections = data?.connections || [];
  const linkedConnections = connections.filter((c) => c.connected);
  const isLinked = linkedConnections.length > 0;
  const expired = linkedConnections.filter((c) => c.token_valid === false);

  const syncNow = async () => {
    const targets = linkedConnections.filter((c) => c.token_valid !== false).map((c) => c.broker);
    if (!targets.length) {
      const b = expired[0]?.broker;
      show("error", "Broker sessions expire daily. Reconnect to sync fresh data.", b && { label: `Reconnect ${brokerName(b)}`, onClick: () => connect(b) });
      return;
    }
    setSyncing(true);
    setNotice(null);
    const results = await Promise.allSettled(targets.map((b) => syncBroker(b)));
    setSyncing(false);

    const expiredNow = [];
    const failed = [];
    results.forEach((r, i) => {
      if (r.status === "fulfilled") return;
      const err = r.reason;
      if (err.response?.status === 409 && err.response?.data?.code === "TOKEN_EXPIRED") expiredNow.push(targets[i]);
      else failed.push([targets[i], apiError(err, "Sync failed.")]);
    });

    if (expiredNow.length) {
      const b = expiredNow[0];
      show("error", `${expiredNow.map(brokerName).join(" and ")} session expired. Reconnect to sync.`, { label: "Reconnect", onClick: () => connect(b) });
    } else if (failed.length) {
      show("error", failed.map(([b, m]) => `${brokerName(b)}: ${m}`).join(" "));
    } else {
      show("success", `Synced ${targets.map(brokerName).join(" and ")}.`);
    }
    load({ quiet: true });
  };

  const onDisconnected = (broker, deleted) => {
    setDisconnecting(null);
    show("info", `${brokerName(broker)} disconnected${deleted ? " and its synced data deleted" : ""}.`);
    load({ quiet: true });
  };

  const syncIcon = useMemo(
    () => function SyncIcon(props) {
      return <SpinIcon {...props} spinning={syncing} />;
    },
    [syncing]
  );

  const summary = data?.summary || {};
  const holdings = data?.holdings || [];
  const positions = data?.positions || [];

  return (
    <div className="min-h-screen w-full bg-page text-white font-sans overflow-x-clip">
      <Navbar />

      <section className="px-6 md:px-16 pt-12 pb-10">
        <PageHeading index="07" label="Your money" title="PORTFOLIO">
          {isLinked ? (
            <div className="flex flex-col items-start lg:items-end gap-3">
              <PrimaryButton type="button" onClick={syncNow} disabled={syncing} icon={syncIcon}>
                {syncing ? "Syncing…" : "Sync now"}
              </PrimaryButton>
              <MonoLabel className="text-gray-500">
                {fmtSyncTime(summary.last_synced_at) ? `Last synced ${fmtSyncTime(summary.last_synced_at)}` : "Not synced yet"}
              </MonoLabel>
            </div>
          ) : (
            <p className="text-[10px] font-mono tracking-widest uppercase text-gray-400 leading-relaxed max-w-[360px] lg:text-right">
              Link Upstox or Zerodha read-only and see your holdings scored by InvestIQ.
            </p>
          )}
        </PageHeading>
      </section>

      <Notice notice={notice} onDismiss={() => setNotice(null)} />

      {loading && !data ? (
        <StatusLine className="border-t border-gray-800">Loading your portfolio…</StatusLine>
      ) : loadError && !data ? (
        <div className="border-t border-gray-800 px-6 md:px-16 py-16 flex flex-col items-center gap-5 text-center">
          <p role="alert" className="text-[11px] font-mono tracking-widest uppercase text-red-400">{loadError}</p>
          <button type="button" onClick={() => load()} className={ghostButton}>Try again</button>
        </div>
      ) : !isLinked ? (
        <ConnectCards connections={connections} onConnect={connect} pending={pending} error={connectError} />
      ) : (
        <>
          {expired.length > 0 && !notice && !expiredDismissed && (
            <Notice
              notice={{
                id: "expired",
                tone: "error",
                text: `${expired.map((c) => brokerName(c.broker)).join(" and ")} session expired. Showing your last synced data; reconnect to refresh.`,
                action: { label: "Reconnect", onClick: () => connect(expired[0].broker) },
              }}
              onDismiss={() => setExpiredDismissed(true)}
            />
          )}

          <BrokerAccounts
            connections={connections}
            onConnect={connect}
            onDisconnect={setDisconnecting}
            pending={pending}
            connectError={connectError}
          />

          <Summary summary={summary} />

          <ValueChart history={data?.history} />

          <Block
            index="03"
            label="Holdings"
            title="What you own"
            flush
            aside={
              <HScroll className="-mx-6 md:mx-0" innerClassName="px-6 md:px-0">
              <div role="tablist" aria-label="Portfolio views" className="flex gap-2 w-max">
                {[["holdings", `Holdings · ${holdings.length}`], ["positions", `Positions · ${positions.length}`], ["funds", "Funds"]].map(([k, l]) => (
                  <TouchPill key={k} role="tab" className="shrink-0" aria-selected={tab === k} active={tab === k} onClick={() => setTab(k)}>
                    {l}
                  </TouchPill>
                ))}
              </div>
              </HScroll>
            }
          >
            <div role="tabpanel">
              {tab === "holdings" && <Holdings holdings={holdings} total={Number(summary.current) || 0} />}
              {tab === "positions" && <Positions positions={positions} />}
              {tab === "funds" && <Funds funds={data?.funds} connections={connections} />}
            </div>
          </Block>

          <Insights insights={data?.insights} holdings={holdings} />
        </>
      )}

      <div className="border-t border-gray-800 px-6 md:px-16 py-8">
        <p className="flex items-start gap-2 text-[10px] font-mono tracking-widest uppercase text-gray-500 leading-relaxed">
          <Info size={12} strokeWidth={1.5} className="shrink-0 mt-[1px]" />
          {PORTFOLIO_DISCLAIMER}
        </p>
      </div>

      <DisconnectDialog broker={disconnecting} onClose={() => setDisconnecting(null)} onDone={onDisconnected} />

      <Footer />
    </div>
  );
}
