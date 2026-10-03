import React, { useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { AnimatePresence, motion } from "motion/react";
import { ChevronDown, ExternalLink, Search, TriangleAlert } from "lucide-react";
import Navbar from "../components/Navbar";
import Footer from "../components/Footer";
import { PageHeading, Panel, MonoLabel, SectionLabel, TouchPill, HScroll, PrimaryButton } from "../components/ui";
import { SignedPct, StatusLine, Disclaimer, fmtDate } from "../components/rankings";
import { apiError, classifyEvent, getEventPlaybook, getEventTypes, getEvents } from "../services/api";
import usePageTitle from "../hooks/usePageTitle";

// Market events: what sectors did after past events of a type. History, not a forecast (ml/events).

const HORIZONS = [["21d", "1 month"], ["63d", "3 months"], ["126d", "6 months"]];
const STANCE_LABELS = {
  escalation: "Escalation", de_escalation: "De-escalation", easing: "Easing / cuts", tightening: "Tightening / hikes",
  hold: "Hold", support: "Support", restrict: "Restriction", reform: "Reform", tax_down: "Tax cut", tax_up: "Tax rise",
  spend_up: "Stimulus", neutral: "Routine", shock: "Shock", pro_incumbent: "Incumbent wins", supply_cut: "Supply cut",
  price_war: "Price war", risk_off: "Risk-off", uncertain: "Uncertain", tighten: "Tightening",
};
const stanceLabel = (s) => STANCE_LABELS[s] || (s ? s.replace(/_/g, " ") : "");

const RELIABILITY = {
  "event-specific": { tone: "border-green-500/60 text-green-500", text: "Event-specific" },
  "event-specific (weak)": { tone: "border-amber-500/60 text-amber-400", text: "Weak pattern" },
  "trend, not event": { tone: "border-gray-600 text-gray-400", text: "Trend, not event" },
  "no reliable pattern": { tone: "border-gray-700 text-gray-500", text: "No reliable pattern" },
  anecdotal: { tone: "border-gray-700 text-gray-500", text: "Too few events" },
};
const muted = (rel) => rel !== "event-specific" && rel !== "event-specific (weak)";

function ReliabilityBadge({ value }) {
  const r = RELIABILITY[value] || { tone: "border-gray-700 text-gray-500", text: value || "—" };
  return <span className={`inline-flex px-2 py-0.5 rounded-full border text-[10px] font-mono tracking-wider uppercase whitespace-nowrap ${r.tone}`}>{r.text}</span>;
}

function HitBar({ value }) {
  if (value == null) return <span className="text-gray-600">—</span>;
  return (
    <div className="flex items-center gap-2">
      <div className="h-1.5 w-16 rounded-full bg-gray-800 overflow-hidden">
        <div className={`h-full ${value >= 0.5 ? "bg-green-500" : "bg-red-400"}`} style={{ width: `${Math.round(value * 100)}%` }} />
      </div>
      <span className="font-mono text-[12px] text-gray-300">{Math.round(value * 100)}%</span>
    </div>
  );
}

function PlaybookTable({ data }) {
  if (!data) return null;
  if (!data.rows.length) return <StatusLine>Too few past events of this kind to show a table.</StatusLine>;
  return (
    <Panel className="overflow-x-auto">
      <table className="w-full min-w-[640px] text-left text-[13px]">
        <thead>
          <tr className="border-b border-gray-800">
            {["Sector / theme", "Vs average stock", "Beat the average", "Past events", "How reliable"].map((h) => (
              <th key={h} scope="col" className="px-4 py-3 text-[10px] font-mono font-normal tracking-widest uppercase text-gray-500">{h}</th>
            ))}
          </tr>
        </thead>
        <tbody className="divide-y divide-gray-800">
          {data.rows.map((r) => (
            <tr key={r.group} className={muted(r.reliability) ? "opacity-60" : ""}>
              <td className="px-4 py-3 text-white">{r.group}</td>
              <td className="px-4 py-3"><SignedPct value={r.mean} /></td>
              <td className="px-4 py-3"><HitBar value={r.hit_rate} /></td>
              <td className="px-4 py-3 font-mono text-gray-300">{r.n_events}</td>
              <td className="px-4 py-3"><ReliabilityBadge value={r.reliability} /></td>
            </tr>
          ))}
        </tbody>
      </table>
    </Panel>
  );
}

// Paste a headline -> type + what sectors did after similar events
function HeadlineCheck({ horizon }) {
  const [text, setText] = useState("");
  const [busy, setBusy] = useState(false);
  const [res, setRes] = useState(null);
  const [error, setError] = useState("");

  const run = async (e) => {
    e.preventDefault();
    if (text.trim().length < 8) { setError("Paste a headline of at least a few words."); return; }
    setBusy(true); setError("");
    try { setRes(await classifyEvent(text.trim(), horizon)); }
    catch (err) { setError(apiError(err, "Couldn't check that headline. Try again.")); setRes(null); }
    finally { setBusy(false); }
  };

  return (
    <div className="space-y-5">
      <form onSubmit={run} className="flex flex-col md:flex-row gap-3 max-w-[900px]">
        <label className="relative flex-1">
          <span className="sr-only">News headline</span>
          <Search size={15} className="absolute left-4 top-1/2 -translate-y-1/2 text-gray-500" aria-hidden="true" />
          <input
            value={text}
            onChange={(e) => setText(e.target.value)}
            placeholder="e.g. RBI cuts repo rate by 25 basis points"
            className="w-full pl-10 pr-4 py-3 rounded-full bg-white/5 border border-gray-700 text-white text-sm outline-none placeholder:text-gray-500 focus:border-white transition-colors"
          />
        </label>
        <PrimaryButton type="submit" icon={Search} disabled={busy}>{busy ? "Checking…" : "Check headline"}</PrimaryButton>
      </form>
      {error && <p role="alert" className="text-[11px] font-mono tracking-wider uppercase text-red-400">{error}</p>}
      {res && !res.event_type && <p className="text-[14px] text-gray-400">{res.note}</p>}
      {res?.event_type && (
        <div className="space-y-4">
          <p className="text-[15px] text-gray-300">
            Looks like <span className="text-white font-medium">{res.playbook?.type_label}</span>
            {res.stance && <> · <span className="text-white">{stanceLabel(res.stance)}</span></>}
            <span className="text-gray-500"> · based on {res.playbook?.n_events} past events</span>
            {res.mentioned_groups?.length > 0 && <span className="text-gray-500"> · mentions {res.mentioned_groups.join(", ")}</span>}
          </p>
          <PlaybookTable data={res.playbook} />
          <p className="text-[12px] text-gray-500">{res.note}</p>
        </div>
      )}
    </div>
  );
}

function EventRow({ e }) {
  const [open, setOpen] = useState(false);
  const day0 = e.day0_market;
  return (
    <div className="border-b border-gray-800 last:border-b-0">
      <button type="button" onClick={() => setOpen(!open)} aria-expanded={open}
        className="w-full grid grid-cols-[90px_minmax(0,1fr)_auto] md:grid-cols-[110px_180px_minmax(0,1fr)_120px_auto] gap-3 items-center px-4 md:px-5 py-4 text-left hover:bg-white/[0.02] transition-colors cursor-pointer">
        <span className="font-mono text-[12px] text-gray-400">{fmtDate(e.date)}</span>
        <span className="hidden md:block text-[12px] text-gray-400 truncate">{e.type_label}{e.stance ? ` · ${stanceLabel(e.stance)}` : ""}</span>
        <span className="text-[14px] text-white truncate">{e.title}</span>
        <span className="hidden md:block text-right text-[12px]">{day0 ? <><span className="text-gray-500">day 0 </span><SignedPct value={day0.index_sc} /></> : null}</span>
        <ChevronDown size={15} className={`text-gray-500 transition-transform ${open ? "rotate-180" : ""}`} aria-hidden="true" />
      </button>
      <AnimatePresence initial={false}>
        {open && (
          <motion.div initial={{ height: 0, opacity: 0 }} animate={{ height: "auto", opacity: 1 }} exit={{ height: 0, opacity: 0 }} transition={{ duration: 0.25 }} className="overflow-hidden">
            <div className="px-4 md:px-5 pb-5 grid gap-4 md:grid-cols-2 text-[13px]">
              <div className="space-y-2">
                <MonoLabel className="block text-gray-500">{e.horizon ? `Next ${HORIZONS.find((h) => h[0] === e.horizon)?.[1] || e.horizon}, vs the average stock` : "Not enough time has passed yet"}</MonoLabel>
                {[...e.best.map((b) => ["Best", b]), ...e.worst.map((w) => ["Worst", w])].map(([k, g]) => (
                  <div key={k + g.group} className="flex justify-between gap-3"><span className="text-gray-300">{k}: {g.group}</span><SignedPct value={g.rel} /></div>
                ))}
              </div>
              <div className="space-y-2 text-gray-400">
                <MonoLabel className="block text-gray-500">Source</MonoLabel>
                <a href={e.source_url} target="_blank" rel="noreferrer" className="inline-flex items-center gap-1.5 text-gray-300 hover:text-white break-all">
                  {e.source_kind === "encyclopedia" ? "Encyclopedia entry" : "Official / news source"} <ExternalLink size={12} />
                </a>
                {day0 && <p>Smallcap 250 on the first trading day: <SignedPct value={day0.index_sc} /></p>}
              </div>
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}

export default function Events() {
  usePageTitle("Market Events");
  const [meta, setMeta] = useState(null);
  const [type, setType] = useState("war_geopolitics");
  const [stance, setStance] = useState("");
  const [horizon, setHorizon] = useState("63d");
  const [level, setLevel] = useState("sector");
  const [table, setTable] = useState(null);
  const [tableError, setTableError] = useState("");
  const [events, setEvents] = useState(null);
  const [eventsError, setEventsError] = useState(false);

  useEffect(() => { getEventTypes().then(setMeta).catch(() => setMeta(null)); }, []);
  useEffect(() => {
    setEvents(null); setEventsError(false);
    getEvents({ type, limit: 50 }).then(setEvents).catch(() => setEventsError(true));
  }, [type]);
  useEffect(() => {
    setTableError("");
    getEventPlaybook({ type, stance: stance || undefined, horizon, level })
      .then(setTable).catch((err) => { setTable(null); setTableError(apiError(err, "Couldn't load this table.")); });
  }, [type, stance, horizon, level]);

  const current = meta?.types.find((t) => t.id === type);
  const stances = useMemo(() => Object.entries(current?.stances || {}).filter(([, n]) => n >= 3), [current]);
  const day0 = meta?.validation?.targets?.find((t) => t.horizon === "day0");
  const later = meta?.validation?.targets?.find((t) => t.horizon === "63d");

  return (
    <div className="min-h-screen w-full bg-page text-white font-sans overflow-x-clip">
      <Navbar />

      <section className="px-6 md:px-16 pt-12 pb-10 border-b border-gray-800">
        <PageHeading index="08" label="History" title="MARKET EVENTS">
          <p className="text-[10px] font-mono tracking-widest uppercase text-gray-400 leading-relaxed max-w-[380px] lg:text-right">
            Wars, RBI decisions, budgets and policies since 2016, and how each sector moved afterwards.
          </p>
        </PageHeading>
        <Panel className="mt-8 p-5 md:p-6 max-w-[900px] flex gap-4">
          <TriangleAlert size={18} className="shrink-0 mt-0.5 text-amber-400" aria-hidden="true" />
          <div className="space-y-2 text-[14px] text-gray-300 leading-relaxed">
            <p className="text-white">History, not a forecast.</p>
            <p>
              The market prices most news on the first trading day: the sector a policy names moved the expected way
              {day0 ? ` ${Math.round(day0.hit_rate * 100)}% ` : " about 72% "}of the time that day, but only
              {later ? ` ${Math.round(later.hit_rate * 100)}% ` : " about 52% "}of the time over the next 3 months, which is close to a coin flip.
              In testing, these tables did not pick the next event's winners better than chance. Use them to understand
              past reactions, not to trade the next headline.
            </p>
          </div>
        </Panel>
      </section>

      <section className="px-6 md:px-16 py-10 grid gap-6 border-b border-gray-800">
        <SectionLabel index="01">Check a headline</SectionLabel>
        <HeadlineCheck horizon={horizon} />
      </section>

      <section className="px-6 md:px-16 py-10 grid gap-6 border-b border-gray-800">
        <SectionLabel index="02">After similar events</SectionLabel>
        <HScroll label="Event type" className="-mx-6 md:mx-0" innerClassName="flex items-center gap-2 px-6 md:px-0 pb-1">
          {(meta?.types || []).map((t) => (
            <TouchPill key={t.id} active={type === t.id} onClick={() => { setType(t.id); setStance(""); }} className="shrink-0">
              {t.label} · {t.count}
            </TouchPill>
          ))}
        </HScroll>
        <div className="flex flex-col lg:flex-row gap-4 lg:items-center">
          {stances.length > 0 && (
            <HScroll label="Kind" className="-mx-6 md:mx-0" innerClassName="flex items-center gap-2 px-6 md:px-0 pb-1">
              <MonoLabel className="shrink-0 mr-1 text-gray-500">Kind</MonoLabel>
              <TouchPill active={!stance} onClick={() => setStance("")} className="shrink-0">All</TouchPill>
              {stances.map(([s, n]) => <TouchPill key={s} active={stance === s} onClick={() => setStance(s)} className="shrink-0">{stanceLabel(s)} · {n}</TouchPill>)}
            </HScroll>
          )}
          <div className="flex flex-wrap items-center gap-2">
            <MonoLabel className="mr-1 text-gray-500">After</MonoLabel>
            {HORIZONS.map(([h, l]) => <TouchPill key={h} active={horizon === h} onClick={() => setHorizon(h)}>{l}</TouchPill>)}
          </div>
          <div className="flex flex-wrap items-center gap-2">
            <MonoLabel className="mr-1 text-gray-500">By</MonoLabel>
            <TouchPill active={level === "sector"} onClick={() => setLevel("sector")}>Sector</TouchPill>
            <TouchPill active={level === "theme"} onClick={() => setLevel("theme")}>Theme</TouchPill>
          </div>
        </div>
        {tableError ? <StatusLine tone="error">{tableError}</StatusLine> : !table ? <StatusLine>Loading…</StatusLine> : (
          <>
            <p className="text-[13px] text-gray-400">
              Average return against the average stock in the {HORIZONS.find((h) => h[0] === horizon)?.[1]} after
              {" "}{table.n_events} past {table.type_label.toLowerCase()} events{table.stance ? ` (${stanceLabel(table.stance).toLowerCase()})` : ""}.
              Greyed rows moved just as much on random dates, or have too few events to mean anything.
            </p>
            <PlaybookTable data={table} />
          </>
        )}
      </section>

      <section className="px-6 md:px-16 py-10 grid gap-6">
        <SectionLabel index="03">{current ? `${current.label} events` : "Events"}</SectionLabel>
        {eventsError ? <StatusLine tone="error">Couldn't load events.</StatusLine> : !events ? <StatusLine>Loading events…</StatusLine> : (
          <Panel>{events.data.map((e) => <EventRow key={e.id} e={e} />)}</Panel>
        )}
        <p className="text-[12px] text-gray-500 max-w-[900px]">
          Returns are equal-weighted across liquid NSE stocks in each group, measured from the first close after the news
          became public. Sources link to official releases where possible. Built from companies listed today, so companies
          that later delisted are missing. See <Link to="/about#methodology" className="underline underline-offset-4 decoration-gray-700 hover:text-white">how InvestIQ works</Link>.
        </p>
        <Disclaimer />
      </section>

      <Footer />
    </div>
  );
}
