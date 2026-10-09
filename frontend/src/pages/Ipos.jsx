import React, { useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { ExternalLink, TriangleAlert } from "lucide-react";
import Navbar from "../components/Navbar";
import Footer from "../components/Footer";
import { PageHeading, Panel, MonoLabel, SectionLabel, TouchPill } from "../components/ui";
import { SignedPct, StatusLine, fmtDate, fmtCr, fmtPct, fmtPrice, fmtRatio } from "../components/rankings";
import { getIpoBaseRates, getIpos } from "../services/api";
import usePageTitle from "../hooks/usePageTitle";

// IPO check: is the issue priced above or below listed peers, and what did earlier IPOs priced like it do?
// A description with base rates, not a forecast (ml/ipo: neither valuation nor subscription predicted returns).

const VERDICT_TONE = {
  below: "border-sky-500/60 text-sky-400",
  in_line: "border-gray-600 text-gray-300",
  above: "border-amber-500/60 text-amber-400",
  well_above: "border-orange-500/60 text-orange-400",
};
const toneFor = (v) => VERDICT_TONE[(v || "").replace("_loss_making", "")] || "border-gray-700 text-gray-500";

const STATUS = {
  open: { text: "Open now", tone: "border-green-500/60 text-green-500" },
  upcoming: { text: "Upcoming", tone: "border-sky-500/60 text-sky-400" },
  closed: { text: "Closed, not listed yet", tone: "border-gray-600 text-gray-400" },
  listed: { text: "Listed", tone: "border-gray-600 text-gray-400" },
};

const Badge = ({ tone, children }) => (
  <span className={`inline-flex px-2 py-0.5 rounded-full border text-[10px] font-mono tracking-wider uppercase whitespace-nowrap ${tone}`}>{children}</span>
);

const fmtX = (v) => (v == null ? "—" : `${v >= 100 ? Math.round(v) : v.toFixed(1)}x`);
const median = (b) => b?.median;

function Fact({ label, children }) {
  return (
    <div className="space-y-1">
      <MonoLabel className="block text-gray-500">{label}</MonoLabel>
      <div className="text-[14px] text-white">{children}</div>
    </div>
  );
}

function IpoCard({ a }) {
  const s = STATUS[a.status] || STATUS.closed;
  const h = a.history;
  const band = a.price_band?.[0] === a.price_band?.[1] ? fmtPrice(a.price_band[0]) : `₹${a.price_band?.[0]}–${a.price_band?.[1]}`;
  return (
    <Panel className="p-5 md:p-7 space-y-6">
      <div className="flex flex-col md:flex-row md:items-start md:justify-between gap-3">
        <div className="space-y-1.5 min-w-0">
          <div className="flex flex-wrap items-center gap-2">
            <Badge tone={s.tone}>{s.text}</Badge>
            <Badge tone={toneFor(a.verdict)}>{a.verdict_label}</Badge>
          </div>
          <h3 className="text-[20px] md:text-[22px] font-semibold text-white">{a.company}</h3>
          {a.business && <p className="text-[14px] text-gray-400">{a.business}</p>}
        </div>
        {a.rhp_url && (
          <a href={a.rhp_url} target="_blank" rel="noreferrer" className="inline-flex items-center gap-1.5 text-[13px] text-gray-300 hover:text-white shrink-0">
            Prospectus (RHP) <ExternalLink size={12} />
          </a>
        )}
      </div>

      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <Fact label={a.status === "listed" ? "Issue price" : "Price band"}>{band}</Fact>
        <Fact label="Bidding">{fmtDate(a.issue_start, { day: "2-digit", month: "short" })} – {fmtDate(a.issue_end)}</Fact>
        <Fact label="Market cap at issue">{fmtCr(a.mcap_cr)}</Fact>
        <Fact label="Issue size">{a.issue_size_cr ? fmtCr(a.issue_size_cr) : "—"}{a.ofs_share > 0 ? <span className="text-gray-500 text-[12px]"> · {Math.round(a.ofs_share * 100)}% sale by owners</span> : null}</Fact>
        {a.status === "listed" && <Fact label="Listing day">{a.list_gain_close != null ? <SignedPct value={a.list_gain_close} /> : "—"}</Fact>}
        {a.sub_qib != null && <Fact label="QIB subscription">{fmtX(a.sub_qib)}</Fact>}
      </div>

      <div className="space-y-3">
        <p className="text-[15px] text-gray-200">{a.wording}</p>
        <div className="overflow-x-auto">
          <table className="w-full text-left text-[13px]">
            <thead>
              <tr className="border-b border-gray-800">
                {["Measure", "This IPO", `${a.industry} median`, "Peers", "Vs peers"].map((t) => (
                  <th key={t} scope="col" className={`px-3 py-2.5 text-[10px] font-mono font-normal tracking-widest uppercase text-gray-500 ${t === "Peers" ? "hidden md:table-cell" : ""}`}>{t}</th>
                ))}
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-800">
              {a.table.map((t) => (
                <tr key={t.metric}>
                  <td className="px-3 py-2.5 text-white">{t.metric}</td>
                  <td className="px-3 py-2.5 font-mono text-gray-200">{fmtRatio(t.ipo, 1)}</td>
                  <td className="px-3 py-2.5 font-mono text-gray-400">{fmtRatio(t.peer_median, 1)}</td>
                  <td className="hidden md:table-cell px-3 py-2.5 font-mono text-gray-500">{t.peers ?? "—"}</td>
                  <td className="px-3 py-2.5 font-mono text-gray-200">{t.premium_pct == null ? "—" : `${t.premium_pct > 0 ? "+" : ""}${Math.round(t.premium_pct)}%`}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        <p className="text-[12px] text-gray-500">
          At the {a.status === "listed" ? "issue price" : "top of the price band"}, on {a.fin_source === "rhp" ? `${a.fiscal} figures from the prospectus` : "the company's first published results, annualised"}.
          Peers priced at their close on {fmtDate(a.peer_date)}.
          {a.rhp_peers?.length > 0 && <> The prospectus compares itself with {a.rhp_peers.map((p, i) => (
            <span key={p.symbol}>{i ? ", " : ""}<Link to={`/company/${p.symbol}`} className="text-gray-300 underline underline-offset-4 decoration-gray-700 hover:text-white">{p.symbol}</Link>{p.investiq_pe ? ` (P/E ${p.investiq_pe.toFixed(1)}x)` : ""}</span>
          ))}.</>}
        </p>
      </div>

      <div className="grid gap-5 md:grid-cols-2">
        {h?.n > 0 && (
          <div className="space-y-2">
            <MonoLabel className="block text-gray-500">Earlier IPOs priced like this · not a forecast</MonoLabel>
            <p className="text-[14px] text-gray-300 leading-relaxed">
              {h.n} earlier IPOs with the same verdict: median listing-day gain <SignedPct value={median(h.list_gain_close)} />;
              {" "}after a year, median <SignedPct value={median(h.exc_12m)} /> against the Smallcap 250
              {h.exc_12m?.share_positive != null && <>, and {Math.round(h.exc_12m.share_positive * 100)}% beat it</>}.
            </p>
          </div>
        )}
        <div className="space-y-2">
          <MonoLabel className="block text-gray-500">Things to check</MonoLabel>
          {a.risks.length ? (
            <ul className="space-y-1.5 text-[14px] text-gray-300 list-disc pl-5">
              {a.risks.map((r) => <li key={r}>{r.replace(/Rs /g, "₹")}</li>)}
            </ul>
          ) : <p className="text-[14px] text-gray-400">No rule-based flags.</p>}
        </div>
      </div>
    </Panel>
  );
}

function ListingsTable({ rows }) {
  return (
    <Panel className="overflow-x-auto">
      <table className="w-full min-w-[760px] text-left text-[13px]">
        <thead>
          <tr className="border-b border-gray-800">
            {["Company", "Listed", "Issue price", "QIB subscription", "Listing day", "Now vs issue price", "Priced at issue"].map((t) => (
              <th key={t} scope="col" className="px-4 py-3 text-[10px] font-mono font-normal tracking-widest uppercase text-gray-500">{t}</th>
            ))}
          </tr>
        </thead>
        <tbody className="divide-y divide-gray-800">
          {rows.map((r) => (
            <tr key={r.symbol + r.listing_date}>
              <td className="px-4 py-3 max-w-[260px]">
                {r.site_symbol
                  ? <Link to={`/company/${r.site_symbol}`} className="text-white hover:underline underline-offset-4 decoration-gray-600 block truncate">{r.company}</Link>
                  : <span className="text-white block truncate">{r.company}</span>}
                <span className="font-mono text-[11px] text-gray-500">{r.symbol}{r.industry ? ` · ${r.industry}` : ""}</span>
              </td>
              <td className="px-4 py-3 font-mono text-gray-400 whitespace-nowrap">{fmtDate(r.listing_date)}</td>
              <td className="px-4 py-3 font-mono text-gray-300">{fmtPrice(r.issue_price)}</td>
              <td className="px-4 py-3 font-mono text-gray-300">{fmtX(r.sub_qib)}</td>
              <td className="px-4 py-3"><SignedPct value={r.list_gain_close} /></td>
              <td className="px-4 py-3"><SignedPct value={r.now?.vs_issue} /></td>
              <td className="px-4 py-3">{r.verdict ? <Badge tone={toneFor(r.verdict)}>{r.verdict_label}</Badge> : <span className="text-gray-600 text-[12px]">No data</span>}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </Panel>
  );
}

function RatesTable({ title, rows, labels }) {
  return (
    <div className="space-y-3">
      <MonoLabel className="block text-gray-400">{title}</MonoLabel>
      <Panel className="overflow-x-auto">
        <table className="w-full min-w-[560px] text-left text-[13px]">
          <thead>
            <tr className="border-b border-gray-800">
              {["Group", "IPOs", "Median listing day", "Median 1 year vs Smallcap 250", "Beat Smallcap 250 in 1 year"].map((t) => (
                <th key={t} scope="col" className="px-4 py-3 text-[10px] font-mono font-normal tracking-widest uppercase text-gray-500">{t}</th>
              ))}
            </tr>
          </thead>
          <tbody className="divide-y divide-gray-800">
            {rows.map((r) => {
              const few = (r.exc_12m?.n || 0) < 15;
              return (
                <tr key={r.bucket} className={few ? "opacity-60" : ""}>
                  <td className="px-4 py-3 text-white">{labels?.[r.bucket] || r.bucket}</td>
                  <td className="px-4 py-3 font-mono text-gray-300">{r.n}</td>
                  <td className="px-4 py-3"><SignedPct value={r.list_gain_close?.median} /></td>
                  <td className="px-4 py-3"><SignedPct value={r.exc_12m?.median} /> <span className="text-gray-600 font-mono text-[11px]">n={r.exc_12m?.n || 0}</span></td>
                  <td className="px-4 py-3 font-mono text-gray-300">{r.exc_12m?.hit != null ? fmtPct(r.exc_12m.hit, { digits: 0 }) : "—"}</td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </Panel>
    </div>
  );
}

const QIB_LABELS = { "<1x": "QIB under 1x", "1-10x": "QIB 1–10x", "10-50x": "QIB 10–50x", "50-100x": "QIB 50–100x", ">100x": "QIB over 100x" };
const MARKET_LABELS = { "SC250 >=20% off high": "Small caps 20%+ below their high", "10-20% off": "Small caps 10–20% below", "within 10%": "Small caps near their high" };
const VERDICT_ORDER = ["below", "in_line", "above", "well_above", "below_loss_making", "in_line_loss_making"];

export default function Ipos() {
  usePageTitle("IPO Check");
  const [data, setData] = useState(null);
  const [error, setError] = useState(false);
  const [rates, setRates] = useState(null);
  const [filter, setFilter] = useState("all");
  const [showAll, setShowAll] = useState(false);

  useEffect(() => {
    getIpos({ limit: 300 }).then(setData).catch(() => setError(true));
    getIpoBaseRates().then(setRates).catch(() => setRates(null));
  }, []);

  const listings = useMemo(() => {
    const rows = data?.listings || [];
    if (filter === "below") return rows.filter((r) => r.verdict?.startsWith("below"));
    if (filter === "above") return rows.filter((r) => /above/.test(r.verdict || ""));
    return rows;
  }, [data, filter]);

  const o = rates?.overall;

  return (
    <div className="min-h-screen w-full bg-page text-white font-sans overflow-x-clip">
      <Navbar />

      <section className="px-6 md:px-16 pt-12 pb-10 border-b border-gray-800">
        <PageHeading index="09" label="New listings" title="IPO CHECK">
          <p className="text-[10px] font-mono tracking-widest uppercase text-gray-400 leading-relaxed max-w-[380px] lg:text-right">
            Is a new issue priced above or below similar listed companies, and what happened to earlier IPOs like it?
          </p>
        </PageHeading>
        <Panel className="mt-8 p-5 md:p-6 max-w-[900px] flex gap-4">
          <TriangleAlert size={18} className="shrink-0 mt-0.5 text-amber-400" aria-hidden="true" />
          <div className="space-y-2 text-[14px] text-gray-300 leading-relaxed">
            <p className="text-white">A description of the price, not a forecast.</p>
            <p>
              We tested this on {rates?.sample?.test_sample || 280} IPOs from 2018 to 2026. IPOs priced cheaply against their peers did
              not do better than dearly priced ones over the next 6 or 12 months. Heavy demand from big institutions (QIB subscription)
              usually meant a bigger first-day gain, but not better returns after that.
              {o && <> The typical IPO gained <SignedPct value={o.list_gain_close.median} /> on listing day, then trailed the Smallcap 250 by
              {" "}{fmtPct(Math.abs(o.exc_12m.median), { digits: 0 })} over its first year.</>}
            </p>
          </div>
        </Panel>
      </section>

      <section className="px-6 md:px-16 py-10 grid gap-6 border-b border-gray-800">
        <SectionLabel index="01">Open and upcoming</SectionLabel>
        {error ? <StatusLine tone="error">Couldn't load IPO data.</StatusLine> : !data ? <StatusLine>Loading…</StatusLine> : (
          <>
            {!data.current.length && <p className="text-[14px] text-gray-400">No open or upcoming IPOs have been analysed yet. Recently listed ones are below.</p>}
            <div className="grid gap-6 xl:grid-cols-2">
              {data.current.map((a) => <IpoCard key={a.symbol} a={a} />)}
            </div>
            {data.analysed_listed.length > 0 && (
              <>
                <MonoLabel className="block text-gray-400 pt-2">Recently listed, checked against its prospectus peers</MonoLabel>
                <div className="grid gap-6 xl:grid-cols-2">
                  {data.analysed_listed.map((a) => <IpoCard key={a.symbol} a={a} />)}
                </div>
              </>
            )}
            <p className="text-[12px] text-gray-500 max-w-[900px]">
              Main-board IPOs only. Prospectus figures are checked by hand, so an issue appears here once its prospectus has been read.
              Data as of {fmtDate(data.as_of)}.
            </p>
          </>
        )}
      </section>

      <section className="px-6 md:px-16 py-10 grid gap-6 border-b border-gray-800">
        <SectionLabel index="02">Recently listed</SectionLabel>
        {data && (
          <>
            <div className="flex flex-wrap items-center gap-2">
              <MonoLabel className="mr-1 text-gray-500">Priced</MonoLabel>
              <TouchPill active={filter === "all"} onClick={() => setFilter("all")}>All · {data.listings.length}</TouchPill>
              <TouchPill active={filter === "below"} onClick={() => setFilter("below")}>Below peers</TouchPill>
              <TouchPill active={filter === "above"} onClick={() => setFilter("above")}>Above peers</TouchPill>
            </div>
            <ListingsTable rows={showAll ? listings : listings.slice(0, 25)} />
            {listings.length > 25 && (
              <button type="button" onClick={() => setShowAll(!showAll)} className="justify-self-start text-[12px] font-mono tracking-widest uppercase text-gray-300 hover:text-white underline underline-offset-4 decoration-gray-700 cursor-pointer">
                {showAll ? "Show fewer" : `Show all ${listings.length}`}
              </button>
            )}
            <p className="text-[12px] text-gray-500 max-w-[900px]">
              Listing day: closing price on the first day vs the issue price. "Priced at issue" compares the issue price with listed
              peers using the company's first published results, so it is filled in a few weeks after listing; banks and other
              financial companies are not compared.
            </p>
          </>
        )}
      </section>

      <section className="px-6 md:px-16 py-10 grid gap-8">
        <SectionLabel index="03">What earlier IPOs did</SectionLabel>
        {rates && (
          <>
            <RatesTable title="By price vs peers at issue" labels={rates.verdict_labels}
              rows={[...rates.verdict].sort((a, b) => VERDICT_ORDER.indexOf(a.bucket) - VERDICT_ORDER.indexOf(b.bucket))} />
            <RatesTable title="By QIB subscription" rows={rates.qib} labels={QIB_LABELS} />
            <RatesTable title="By market mood when the IPO opened" rows={rates.market} labels={MARKET_LABELS} />
            <p className="text-[12px] text-gray-500 max-w-[900px]">
              Returns are measured from the listing-day close against the NIFTY Smallcap 250. Greyed rows have fewer than 15 IPOs
              with a full year of history. The market-mood rows rest on a few episodes, so treat them as anecdotes.
            </p>
          </>
        )}
        <p className="text-[12px] text-gray-500 max-w-[900px]">{data?.source_note}</p>
        <p className="flex items-start gap-2 text-[10px] font-mono tracking-widest uppercase text-gray-500 leading-relaxed">
          {data?.disclaimer || "InvestIQ is not a SEBI-registered investment adviser. This is not a recommendation to apply, buy or sell."}
        </p>
      </section>

      <Footer />
    </div>
  );
}
