import React, { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { motion } from "motion/react";
import Navbar from "../components/Navbar";
import Footer from "../components/Footer";
import { PageHeading, Panel, MonoLabel, SectionLabel, fadeUp, stagger } from "../components/ui";
import { SignedPct, StatusLine, Disclaimer, fmtDate } from "../components/rankings";
import { getTrackRecord } from "../services/api";
import usePageTitle from "../hooks/usePageTitle";

const LISTS = [
  { key: "top", name: "Top list", blurb: "The 50 companies to research first, refreshed on the 1st and 16th." },
  { key: "steady", name: "Steady list", blurb: "Up to 30 breakout-from-a-base picks, for smaller swings." },
];

// Simulated results from the backtests (docs/model-report.md, ml/rankings/reports), kept apart from the live record
const BACKTEST = [
  { name: "Top list", cagr: 0.352, dd: -0.381, years: "7 of 8" },
  { name: "Steady list", cagr: 0.278, dd: -0.338, years: "6 of 8" },
  { name: "NIFTY Smallcap 250", cagr: 0.19, dd: -0.438, years: "—" },
];

// Growth of 1 rupee: the list as followed vs the index, drawn to one scale
function ValueChart({ points }) {
  if (!points || points.length < 3) return null;
  const W = 640, H = 180, P = 28;
  const vals = points.flatMap((p) => [p.value, p.benchmark]);
  const lo = Math.min(...vals, 1), hi = Math.max(...vals, 1);
  const pad = (hi - lo) * 0.1 || 0.02;
  const y = (v) => H - P - ((v - (lo - pad)) / (hi - lo + 2 * pad)) * (H - 2 * P);
  const x = (i) => P + (i / (points.length - 1)) * (W - 2 * P);
  const line = (k) => points.map((p, i) => `${i ? "L" : "M"}${x(i).toFixed(1)},${y(p[k]).toFixed(1)}`).join(" ");
  return (
    <svg viewBox={`0 0 ${W} ${H}`} className="w-full h-auto" role="img" aria-label="Value of the list as followed versus the index">
      <line x1={P} x2={W - P} y1={y(1)} y2={y(1)} className="stroke-gray-800" strokeDasharray="3 4" />
      <text x={P} y={y(1) - 6} className="fill-gray-500 font-mono" fontSize="10">start = 1.00</text>
      <path d={line("benchmark")} fill="none" className="stroke-gray-500" strokeWidth="1.5" />
      <path d={line("value")} fill="none" className="stroke-white" strokeWidth="2" />
    </svg>
  );
}

function ListRecord({ meta, data }) {
  if (!data) {
    return (
      <Panel className="p-6 md:p-8">
        <h3 className="text-xl text-white">{meta.name}</h3>
        <p className="mt-2 text-[14px] text-gray-400">{meta.blurb}</p>
        <MonoLabel className="block mt-6 text-gray-500">No published list yet</MonoLabel>
      </Panel>
    );
  }
  const s = data.since_start;
  const latest = data.snapshots[0];
  return (
    <Panel glow className="p-6 md:p-8 flex flex-col gap-6">
      <div className="flex flex-col md:flex-row md:items-end justify-between gap-4">
        <div>
          <h3 className="text-xl text-white">{meta.name}</h3>
          <p className="mt-2 text-[14px] text-gray-400 max-w-[440px]">{meta.blurb}</p>
        </div>
        <MonoLabel className="text-gray-500">Live since {fmtDate(data.first_snapshot)}</MonoLabel>
      </div>

      {s ? (
        <div className="grid grid-cols-2 sm:grid-cols-3 gap-px bg-gray-800 border border-gray-800 rounded-lg overflow-hidden">
          {[["List as followed", <SignedPct key="r" value={s.return} className="text-2xl" />],
            ["Smallcap 250", <SignedPct key="b" value={s.benchmark_return} className="text-2xl" />],
            ["Difference", <SignedPct key="d" value={s.return - s.benchmark_return} className="text-2xl" />]].map(([k, v]) => (
            <div key={k} className="bg-surface px-4 py-4 flex flex-col gap-2">
              <MonoLabel className="text-gray-500">{k}</MonoLabel>
              {v}
            </div>
          ))}
        </div>
      ) : (
        <p className="text-[14px] text-gray-400">
          First results appear after the first trading session following {fmtDate(latest?.snapshot_date)}.
          The list is bought at that session's close, the same rule as the backtests.
        </p>
      )}

      <ValueChart points={data.chained} />

      <div className="overflow-x-auto -mx-6 md:mx-0">
        <table className="w-full min-w-[620px] text-left text-[13px]">
          <thead>
            <tr className="border-b border-gray-800">
              {["Published", "Names", "Return since", "Smallcap 250", "Beat the index", "Best / worst"].map((h) => (
                <th key={h} scope="col" className="px-3 py-3 first:pl-6 md:first:pl-3 text-[10px] font-mono font-normal tracking-widest uppercase text-gray-500">{h}</th>
              ))}
            </tr>
          </thead>
          <tbody className="divide-y divide-gray-800">
            {data.snapshots.map((r) => (
              <tr key={r.snapshot_date} className="align-top">
                <td className="px-3 py-3 first:pl-6 md:first:pl-3 text-white">{fmtDate(r.snapshot_date)}</td>
                <td className="px-3 py-3 font-mono text-gray-300">{r.names}</td>
                {r.status ? (
                  <td colSpan={4} className="px-3 py-3 text-gray-500">Waiting for the first trading session after it was published</td>
                ) : (
                  <>
                    <td className="px-3 py-3"><SignedPct value={r.return} /></td>
                    <td className="px-3 py-3"><SignedPct value={r.benchmark_return} /></td>
                    <td className="px-3 py-3 font-mono text-gray-300">{r.beat_index_share == null ? "—" : `${Math.round(r.beat_index_share * 100)}%`}</td>
                    <td className="px-3 py-3 text-gray-400">
                      {[...r.best.slice(0, 1), ...r.worst.slice(0, 1)].map((b, i) => (
                        <Link key={b.symbol + i} to={`/company/${encodeURIComponent(b.symbol)}`} className="mr-3 hover:text-white">
                          {b.symbol} <SignedPct value={b.ret} />
                        </Link>
                      ))}
                    </td>
                  </>
                )}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </Panel>
  );
}

export default function TrackRecord() {
  usePageTitle("Track Record");
  const [data, setData] = useState(null);
  const [error, setError] = useState(false);

  useEffect(() => {
    getTrackRecord().then(setData).catch(() => setError(true));
  }, []);

  return (
    <div className="min-h-screen w-full bg-page text-white font-sans overflow-x-clip">
      <Navbar />

      <section className="px-6 md:px-16 pt-12 pb-12 border-b border-gray-800">
        <PageHeading index="07" label="Accountability" title="TRACK RECORD">
          <div className="max-w-[380px] lg:text-right space-y-3">
            <p className="text-[10px] font-mono tracking-widest uppercase text-gray-400 leading-relaxed">
              How every list we published has actually done since, against the NIFTY Smallcap 250.
            </p>
            {data?.as_of && <MonoLabel className="block text-gray-500">Prices up to {fmtDate(data.as_of)}</MonoLabel>}
          </div>
        </PageHeading>
        <p className="mt-8 max-w-[760px] text-[15px] text-gray-400 leading-relaxed">
          Each list is bought in equal amounts at the first close after it is published and measured to the latest
          close. "As followed" switches to every new list when it is published. No costs, taxes or dividends.
          Nothing here is edited after the fact: a bad period stays on the page.
        </p>
      </section>

      <motion.section initial="initial" animate="animate" variants={stagger(0.05, 0.1)} className="px-6 md:px-16 py-12 grid gap-6">
        <motion.div variants={fadeUp}><SectionLabel index="01" className="mb-2">Live</SectionLabel></motion.div>
        {error ? (
          <StatusLine tone="error">Couldn't load the track record. Try again in a minute.</StatusLine>
        ) : !data ? (
          <StatusLine>Loading the track record…</StatusLine>
        ) : (
          LISTS.map((l) => (
            <motion.div key={l.key} variants={fadeUp}><ListRecord meta={l} data={data.lists?.[l.key]} /></motion.div>
          ))
        )}
      </motion.section>

      <section className="px-6 md:px-16 py-12 border-t border-gray-800 grid gap-6">
        <SectionLabel index="02">Backtest, for comparison</SectionLabel>
        <p className="max-w-[760px] text-[15px] text-gray-400 leading-relaxed">
          Simulated on 2019-2026 data with the same rules, refreshed every 15 days, after 0.3% trading costs. A
          simulation, not real results: it uses today's company list, so companies that later delisted are missing,
          which makes these numbers look better than reality.
        </p>
        <Panel className="overflow-x-auto">
          <table className="w-full min-w-[520px] text-left text-[14px]">
            <thead>
              <tr className="border-b border-gray-800">
                {["", "Yearly return", "Worst fall", "Years beating the index"].map((h) => (
                  <th key={h} scope="col" className="px-5 py-4 text-[10px] font-mono font-normal tracking-widest uppercase text-gray-500">{h}</th>
                ))}
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-800">
              {BACKTEST.map((b) => (
                <tr key={b.name}>
                  <td className="px-5 py-4 text-white">{b.name}</td>
                  <td className="px-5 py-4"><SignedPct value={b.cagr} /></td>
                  <td className="px-5 py-4"><SignedPct value={b.dd} /></td>
                  <td className="px-5 py-4 font-mono text-gray-300">{b.years}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </Panel>
        <p className="text-[13px] text-gray-500">
          How the lists are built: <Link to="/predictor" className="text-gray-300 underline underline-offset-4 decoration-gray-700 hover:text-white">Predictor</Link> ·
          {" "}<Link to="/about#methodology" className="text-gray-300 underline underline-offset-4 decoration-gray-700 hover:text-white">How the rankings work</Link>
        </p>
        <Disclaimer />
      </section>

      <Footer />
    </div>
  );
}
