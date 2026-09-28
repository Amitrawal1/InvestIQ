import React, { useEffect, useMemo, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { motion } from "motion/react";
import { ArrowLeft, Check, TriangleAlert, ExternalLink } from "lucide-react";
import Navbar from "../components/Navbar";
import Footer from "../components/Footer";
import NewsItem from "../components/NewsItem";
import { SectionLabel, MonoLabel, TouchPill, HScroll, Panel, fadeUp, stagger } from "../components/ui";
import {
  GrowthBadge, ScoreBar, Disclaimer, StatusLine, SignedPct,
  fmtPct, fmtCr, fmtPrice, fmtRatio, fmtScore, fmtDate,
} from "../components/rankings";
import { CompareChart, QuarterlyChart, ScoreHistoryChart } from "../components/CompanyCharts";
import {
  getCompanyDetails, getCompanyFinancials, getCompanyPrices, getCompanyNews, getNews,
} from "../services/api";

const RANGES = [["6m", "6M"], ["1y", "1Y"], ["3y", "3Y"], ["5y", "5Y"], ["max", "MAX"]];

const COMPONENTS = [
  ["score_growth", "Growth"],
  ["score_profitability", "Profitability"],
  ["score_financial_health", "Financial health"],
  ["score_cash_flow", "Cash flow"],
  ["score_momentum", "Momentum"],
  ["score_news", "News"],
];

// Price series helpers (rows sorted oldest -> newest)
const closeOn = (rows, daysAgo) => {
  if (!rows?.length) return null;
  const target = new Date(rows[rows.length - 1].date).getTime() - daysAgo * 864e5;
  for (let i = rows.length - 1; i >= 0; i--) {
    if (new Date(rows[i].date).getTime() <= target) return Number(rows[i].close);
  }
  return null;
};
const retFrom = (rows, days) => {
  const past = closeOn(rows, days);
  const last = rows?.length ? Number(rows[rows.length - 1].close) : null;
  return past && last ? last / past - 1 : null;
};

// Charts are shorter on phones so a whole chart fits on screen with its controls
const PHONE_MQ = "(max-width: 767.98px)";
function useChartHeight(phone, desktop) {
  const [small, setSmall] = useState(() => typeof window !== "undefined" && window.matchMedia(PHONE_MQ).matches);
  useEffect(() => {
    const mq = window.matchMedia(PHONE_MQ);
    const onChange = (e) => setSmall(e.matches);
    mq.addEventListener("change", onChange);
    return () => mq.removeEventListener("change", onChange);
  }, []);
  return small ? phone : desktop;
}

const Section = ({ index, label, title, children, aside }) => (
  <motion.section
    initial="initial"
    whileInView="animate"
    viewport={{ once: true, margin: "-60px" }}
    variants={stagger(0, 0.08)}
    className="border-t border-gray-800 px-6 md:px-16 py-12 md:py-14"
  >
    <motion.div variants={fadeUp} className="flex flex-col md:flex-row md:items-end justify-between gap-4 mb-8 md:mb-10">
      <div>
        <SectionLabel index={index} className="mb-4">{label}</SectionLabel>
        <h2 className="text-[1.8rem] md:text-[2.4rem] font-normal tracking-tight leading-none">{title}</h2>
      </div>
      {aside}
    </motion.div>
    <motion.div variants={fadeUp}>{children}</motion.div>
  </motion.section>
);

const Empty = ({ children }) => (
  <Panel className="px-6 py-10 text-center">
    <MonoLabel className="text-gray-500">{children}</MonoLabel>
  </Panel>
);

const Stat = ({ label, children, sub }) => (
  <div className="bg-surface px-5 py-5 min-w-0">
    <MonoLabel className="block mb-3 text-gray-500">{label}</MonoLabel>
    <div className="text-[1.3rem] md:text-[1.5rem] font-normal tracking-tight leading-none truncate">{children}</div>
    {sub && <MonoLabel className="block mt-2 text-gray-600 normal-case tracking-wider">{sub}</MonoLabel>}
  </div>
);

export default function Company() {
  const { symbol } = useParams();
  const [detail, setDetail] = useState(null); // { profile, ranking, score_history }
  const [status, setStatus] = useState("loading"); // loading | ok | notfound | error

  useEffect(() => {
    let cancelled = false;
    window.scrollTo(0, 0);
    setStatus("loading");
    setDetail(null);
    getCompanyDetails(symbol)
      .then((d) => { if (!cancelled) { setDetail(d); setStatus(d?.profile ? "ok" : "notfound"); } })
      .catch((err) => { if (!cancelled) setStatus(err?.response?.status === 404 ? "notfound" : "error"); });
    return () => { cancelled = true; };
  }, [symbol]);

  // 1Y prices drive the header price, 1D change and 52-week stats regardless of chart range
  const [yearPrices, setYearPrices] = useState(null);
  useEffect(() => {
    let cancelled = false;
    setYearPrices(null);
    getCompanyPrices(symbol, "1y")
      .then((d) => { if (!cancelled) setYearPrices(d); })
      .catch(() => { if (!cancelled) setYearPrices({ data: [] }); });
    return () => { cancelled = true; };
  }, [symbol]);

  const profile = detail?.profile;
  const ranking = detail?.ranking;
  const km = ranking?.key_metrics || {};
  const rows = yearPrices?.data || [];

  const header = useMemo(() => {
    const km = ranking?.key_metrics || {};
    const rows = yearPrices?.data || [];
    const last = rows.length ? Number(rows[rows.length - 1].close) : null;
    const prev = rows.length > 1 ? Number(rows[rows.length - 2].close) : null;
    return {
      price: km.last_price ?? last,
      priceDate: km.price_date ?? rows[rows.length - 1]?.date,
      d1: last && prev ? last / prev - 1 : null,
      y1: km.return_1y ?? retFrom(rows, 365),
    };
  }, [ranking, yearPrices]);

  return (
    <div className="min-h-screen w-full bg-page text-white font-sans overflow-x-clip">
      <Navbar />

      <section className="px-6 md:px-16 pt-10 pb-12">
        <Link
          to={profile?.sector_slug ? `/sectors/${profile.sector_slug}` : "/predictor"}
          className="inline-flex items-center gap-2 touch:min-h-11 text-[10px] font-mono tracking-[0.2em] uppercase text-gray-400 hover:text-white transition-colors"
        >
          <ArrowLeft size={14} strokeWidth={1} /> {profile?.sector || "Rankings"}
        </Link>

        {status === "loading" && <StatusLine>Loading {symbol}…</StatusLine>}
        {status === "notfound" && (
          <StatusLine>
            No company found for “{symbol}”. <Link to="/predictor" className="underline hover:text-white">Browse the ranking</Link>
          </StatusLine>
        )}
        {status === "error" && <StatusLine tone="error">Couldn't load this company. Is the backend running?</StatusLine>}

        {status === "ok" && (
          <motion.div initial="initial" animate="animate" variants={stagger(0.1, 0.1)} className="mt-8 md:mt-12 flex flex-col lg:flex-row lg:items-end justify-between gap-8">
            <div className="min-w-0">
              <motion.div variants={fadeUp} className="flex flex-wrap items-center gap-3 mb-4">
                <SectionLabel index={profile.symbol} />
                <nav className="flex flex-wrap items-center gap-2 text-[10px] font-mono tracking-[0.2em] uppercase text-gray-400">
                  {profile.sector && (
                    <Link to={`/sectors/${profile.sector_slug}`} className="touch:py-3.5 touch:-my-3.5 hover:text-white transition-colors">{profile.sector}</Link>
                  )}
                  {profile.industry && (
                    <>
                      <span className="text-gray-600">›</span>
                      <Link to={`/sectors/${profile.sector_slug}?industry=${encodeURIComponent(profile.industry)}`} className="touch:py-3.5 touch:-my-3.5 hover:text-white transition-colors">
                        {profile.industry}
                      </Link>
                    </>
                  )}
                </nav>
              </motion.div>
              <motion.h1 variants={fadeUp} className="text-[2rem] md:text-[3.4rem] font-normal tracking-tight leading-[1.05] text-white break-words">
                {profile.name}
              </motion.h1>
              <motion.div variants={fadeUp} className="mt-6 flex flex-wrap items-baseline gap-x-5 gap-y-2">
                <span className="text-[1.8rem] md:text-[2.2rem] tracking-tight leading-none">{fmtPrice(header.price)}</span>
                <span className="text-[13px]"><SignedPct value={header.d1} /> <MonoLabel className="text-gray-600">1D</MonoLabel></span>
                <span className="text-[13px]"><SignedPct value={header.y1} /> <MonoLabel className="text-gray-600">1Y</MonoLabel></span>
                {header.priceDate && <MonoLabel className="text-gray-600">as of {fmtDate(header.priceDate)}</MonoLabel>}
              </motion.div>
            </div>

            <motion.div variants={fadeUp} className="shrink-0">
              <Panel glow className="px-6 py-5 sm:min-w-[260px]">
                <MonoLabel className="text-gray-500">Growth score</MonoLabel>
                <div className="mt-3 flex items-center gap-3">
                  <span className="text-[2.6rem] leading-none tracking-tight">{fmtScore(ranking?.growth_score)}</span>
                  <GrowthBadge label={ranking?.growth_label} />
                </div>
                <ScoreBar value={ranking?.growth_score} className="mt-4" />
                <div className="mt-4 flex flex-wrap gap-x-4 gap-y-1">
                  <MonoLabel className="text-gray-400">#{ranking?.rank_overall ?? "—"} overall</MonoLabel>
                  <MonoLabel className="text-gray-400">#{ranking?.rank_in_sector ?? "—"} in sector</MonoLabel>
                </div>
              </Panel>
            </motion.div>
          </motion.div>
        )}

        {status === "ok" && <Disclaimer className="mt-10" />}
      </section>

      {status === "ok" && (
        <>
          <Analysis ranking={ranking} history={detail.score_history || []} />
          <MarketData symbol={profile.symbol} name={profile.symbol} km={km} yearRows={rows} yearPrices={yearPrices} />
          <Financials symbol={profile.symbol} km={km} />
          <CompanyNews profile={profile} />
          {profile.description && (
            <section className="border-t border-gray-800 px-6 md:px-16 py-12 grid grid-cols-1 lg:grid-cols-3 gap-8">
              <MonoLabel className="text-gray-500">About</MonoLabel>
              <div className="lg:col-span-2 space-y-4">
                <p className="text-[14px] leading-relaxed text-gray-400">{profile.description}</p>
                <div className="flex flex-wrap gap-x-6 gap-y-2">
                  {profile.isin && <MonoLabel className="text-gray-600">ISIN {profile.isin}</MonoLabel>}
                  {profile.listing_date && <MonoLabel className="text-gray-600">Listed {fmtDate(profile.listing_date)}</MonoLabel>}
                  {profile.website && (
                    <a href={profile.website} target="_blank" rel="noreferrer noopener" className="inline-flex items-center gap-1.5 text-[10px] font-mono tracking-widest uppercase text-gray-400 hover:text-white">
                      Website <ExternalLink size={11} />
                    </a>
                  )}
                </div>
              </div>
            </section>
          )}
        </>
      )}

      <Footer />
    </div>
  );
}

function Analysis({ ranking, history }) {
  if (!ranking) {
    return (
      <Section index="01" label="InvestIQ analysis" title="Growth signal">
        <Empty>This company isn't in the current ranking snapshot yet.</Empty>
      </Section>
    );
  }

  const reasons = Array.isArray(ranking.reasons) ? ranking.reasons : [];
  const risks = Array.isArray(ranking.risks) ? ranking.risks : [];

  return (
    <Section
      index="01"
      label="InvestIQ analysis"
      title="Growth signal"
      aside={
        <MonoLabel className="text-gray-500">
          {ranking.model_version} · snapshot {fmtDate(ranking.snapshot_date)} · coverage {fmtPct(ranking.coverage, { digits: 0 })}
        </MonoLabel>
      }
    >
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        <Panel className="p-6">
          <MonoLabel className="text-gray-500">Component scores</MonoLabel>
          <div className="mt-6 space-y-5">
            {COMPONENTS.map(([key, label]) => (
              <div key={key}>
                <div className="flex justify-between mb-2">
                  <span className="text-[13px] text-gray-300">{label}</span>
                  <span className="font-mono text-[12px] text-gray-400">{ranking[key] == null ? "n/a" : fmtScore(ranking[key])}</span>
                </div>
                <ScoreBar value={ranking[key]} />
              </div>
            ))}
          </div>
          <div className="mt-6 pt-5 border-t border-gray-800 flex flex-wrap gap-x-4 gap-y-1">
            <MonoLabel className="text-gray-500">#{ranking.rank_overall ?? "—"} overall</MonoLabel>
            <MonoLabel className="text-gray-500">#{ranking.rank_in_sector ?? "—"} sector</MonoLabel>
            <MonoLabel className="text-gray-500">#{ranking.rank_in_industry ?? "—"} industry</MonoLabel>
          </div>
        </Panel>

        <Panel className="p-6">
          <MonoLabel className="text-gray-500">Strengths</MonoLabel>
          {reasons.length ? (
            <ul className="mt-6 space-y-4">
              {reasons.map((r, i) => (
                <li key={i} className="flex gap-3 text-[14px] leading-snug text-gray-300">
                  <Check size={15} className="shrink-0 mt-0.5 text-green-500" /> {r}
                </li>
              ))}
            </ul>
          ) : (
            <p className="mt-6 text-[13px] text-gray-600">No notable strengths flagged.</p>
          )}
        </Panel>

        <Panel className="p-6">
          <MonoLabel className="text-gray-500">Risks</MonoLabel>
          {risks.length ? (
            <ul className="mt-6 space-y-4">
              {risks.map((r, i) => (
                <li key={i} className="flex gap-3 text-[14px] leading-snug text-gray-300">
                  <TriangleAlert size={15} className="shrink-0 mt-0.5 text-red-400" /> {r}
                </li>
              ))}
            </ul>
          ) : (
            <p className="mt-6 text-[13px] text-gray-600">No red flags detected.</p>
          )}
        </Panel>
      </div>

      {history.length > 1 && (
        <Panel className="p-6 mt-6">
          <MonoLabel className="text-gray-500">Score history</MonoLabel>
          <div className="mt-4"><ScoreHistoryChart history={history} /></div>
        </Panel>
      )}
    </Section>
  );
}

function MarketData({ symbol, name, km, yearRows, yearPrices }) {
  const [range, setRange] = useState("1y");
  const [cache, setCache] = useState({});
  const chartH = useChartHeight(260, 340);

  useEffect(() => { setCache({}); setRange("1y"); }, [symbol]);

  // 1Y comes from the page-level fetch; other ranges load on demand and are cached
  const current = range === "1y" ? yearPrices : cache[range];
  const loading = !current;

  useEffect(() => {
    if (range === "1y" || cache[range]) return;
    let cancelled = false;
    getCompanyPrices(symbol, range)
      .then((d) => { if (!cancelled) setCache((c) => ({ ...c, [range]: d })); })
      .catch(() => { if (!cancelled) setCache((c) => ({ ...c, [range]: { data: [] } })); });
    return () => { cancelled = true; };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [symbol, range]);

  const closes = yearRows.map((r) => Number(r.close)).filter((v) => v > 0);
  const hi = closes.length ? Math.max(...closes) : null;
  const lo = closes.length ? Math.min(...closes) : null;
  const last = closes.length ? closes[closes.length - 1] : null;

  const returns = [
    ["1M", km.return_1m ?? retFrom(yearRows, 30)],
    ["3M", km.return_3m ?? retFrom(yearRows, 91)],
    ["6M", km.return_6m ?? retFrom(yearRows, 182)],
    ["1Y", km.return_1y ?? retFrom(yearRows, 365)],
  ];

  return (
    <Section
      index="02"
      label="Market data"
      title="Price vs Smallcap 250"
      aside={
        <div className="flex flex-wrap gap-2">
          {RANGES.map(([v, l]) => (
            <TouchPill key={v} active={range === v} onClick={() => setRange(v)} className="shrink-0">{l}</TouchPill>
          ))}
        </div>
      }
    >
      <Panel className="p-4 md:p-6">
        <div className="flex justify-between mb-2">
          <MonoLabel className="text-gray-500">Rebased to 100</MonoLabel>
          {loading && <MonoLabel className="text-gray-600">Loading…</MonoLabel>}
        </div>
        {!current ? (
          <div className="h-[260px] md:h-[340px] flex items-center justify-center"><MonoLabel className="text-gray-600">Loading prices…</MonoLabel></div>
        ) : current.data?.length > 1 ? (
          <CompareChart data={current.data} benchmark={current.benchmark} name={name} height={chartH} />
        ) : (
          <div className="h-[200px] flex items-center justify-center"><MonoLabel className="text-gray-600">No price history for this range.</MonoLabel></div>
        )}
      </Panel>

      <div className="mt-6 grid grid-cols-2 md:grid-cols-4 gap-px bg-gray-800 border border-gray-800 rounded-xl overflow-hidden">
        {returns.map(([l, v]) => (
          <Stat key={l} label={`${l} return`}><SignedPct value={v} /></Stat>
        ))}
        <Stat label="52W high" sub={hi && last ? `${fmtPct(last / hi - 1, { signed: true })} from high` : null}>{fmtPrice(hi)}</Stat>
        <Stat label="52W low" sub={lo && last ? `${fmtPct(last / lo - 1, { signed: true })} from low` : null}>{fmtPrice(lo)}</Stat>
        <Stat label="Avg traded value (3M)" sub="per day">{fmtCr(km.avg_traded_value_3m_cr, 1)}</Stat>
        <Stat label="Volatility (1Y)" sub={km.return_1y_vs_smallcap != null ? `1Y vs smallcap ${fmtPct(km.return_1y_vs_smallcap, { signed: true })}` : null}>
          {fmtPct(km.volatility_1y)}
        </Stat>
      </div>
    </Section>
  );
}

const RATIO_LABELS = {
  revenue_growth_yoy: "Revenue growth YoY",
  profit_growth_yoy: "Profit growth YoY",
  revenue_ttm_growth: "Revenue TTM growth",
  op_margin_ttm: "Operating margin (TTM)",
  net_margin_ttm: "Net margin (TTM)",
  roe: "ROE",
  roce: "ROCE",
  debt_to_equity: "Debt / equity",
  current_ratio: "Current ratio",
  interest_coverage: "Interest coverage",
  cash_conversion: "Cash conversion",
};

const fmtRatioValue = (key, v) => {
  if (v == null || typeof v === "object") return "—";
  if (typeof v === "string" && Number.isNaN(Number(v))) return v;
  if (/growth|margin|roe|roce|conversion|yield|return/.test(key)) return fmtPct(v);
  if (/_cr$|ttm$|revenue|profit|ocf|fcf|cap/.test(key)) return fmtCr(v);
  return fmtRatio(v);
};

const humanize = (k) => RATIO_LABELS[k] || k.replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase());

const cellTh = "px-4 py-3 font-normal text-left text-[10px] font-mono tracking-widest uppercase text-gray-500 whitespace-nowrap";
const cellTd = "px-4 py-3 font-mono text-[13px] text-gray-300 whitespace-nowrap";

const KM_RATIO_KEYS = ["revenue_growth_yoy", "profit_growth_yoy", "op_margin_ttm", "net_margin_ttm", "roe", "roce", "debt_to_equity", "current_ratio"];

function Financials({ symbol, km }) {
  const [fin, setFin] = useState(null);
  const [state, setState] = useState("loading");
  const quarterH = useChartHeight(240, 300);

  useEffect(() => {
    let cancelled = false;
    setState("loading");
    getCompanyFinancials(symbol)
      .then((d) => { if (!cancelled) { setFin(d); setState("ok"); } })
      .catch(() => { if (!cancelled) setState("error"); });
    return () => { cancelled = true; };
  }, [symbol]);

  const quarterly = fin?.quarterly || [];
  const half = (fin?.half_yearly || []).slice(-6); // last 3 years keeps the table readable
  // latest_ratios can be null before features are built; fall back to the ranking's key metrics
  const ratioSource = fin?.latest_ratios || Object.fromEntries(KM_RATIO_KEYS.map((k) => [k, km?.[k]]));
  const ratios = Object.entries(ratioSource).filter(([k, v]) => v != null && !/date|period|symbol|company|id$/.test(k));
  const empty = state === "ok" && !quarterly.length && !half.length && !ratios.length;

  return (
    <Section index="03" label="Financials" title="Results & balance sheet" aside={<MonoLabel className="text-gray-500">INR crore</MonoLabel>}>
      {state === "loading" && <Empty>Loading financials…</Empty>}
      {(state === "error" || empty) && <Empty>Financial filings aren't available for this company yet.</Empty>}

      {state === "ok" && !empty && (
        <div className="space-y-6">
          {quarterly.length > 0 && (
            <>
              <Panel className="p-4 md:p-6">
                <MonoLabel className="text-gray-500">Quarterly revenue & net profit</MonoLabel>
                <div className="mt-4"><QuarterlyChart quarterly={quarterly} height={quarterH} /></div>
              </Panel>

              <Panel>
                <HScroll label="Quarterly results" fade="from-surface">
                  <table className="w-full min-w-[640px] border-collapse">
                    <thead className="border-b border-gray-800">
                      <tr>
                        {["Quarter", "Revenue", "Net profit", "Op margin", "Net margin", "EPS"].map((h, i) => (
                          <th key={h} className={`${cellTh} ${i ? "text-right" : ""}`}>{h}</th>
                        ))}
                      </tr>
                    </thead>
                    <tbody>
                      {[...quarterly].reverse().map((q) => (
                        <tr key={q.period_end} className="border-b border-gray-800/60 last:border-b-0">
                          <td className={cellTd}>
                            {fmtDate(q.period_end, { month: "short", year: "numeric" })}
                            {q.statement_type && <span className="ml-2 text-[9px] text-gray-600 uppercase tracking-widest">{q.statement_type}</span>}
                          </td>
                          <td className={`${cellTd} text-right`}>{fmtCr(q.revenue, 1)}</td>
                          <td className={`${cellTd} text-right ${Number(q.net_profit) < 0 ? "text-red-400" : ""}`}>{fmtCr(q.net_profit, 1)}</td>
                          <td className={`${cellTd} text-right`}>{fmtPct(q.op_margin)}</td>
                          <td className={`${cellTd} text-right`}>{fmtPct(q.net_margin)}</td>
                          <td className={`${cellTd} text-right`}>{q.eps_basic == null ? "—" : Number(q.eps_basic).toFixed(2)}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </HScroll>
              </Panel>
            </>
          )}

          <div className="grid grid-cols-1 xl:grid-cols-3 gap-6">
            <Panel className="xl:col-span-2">
              <div className="px-4 pt-5 pb-2"><MonoLabel className="text-gray-500">Balance sheet & cash flow (half-yearly)</MonoLabel></div>
              {half.length ? (
                <HScroll label="Balance sheet and cash flow" fade="from-surface" fadeLeft={false}>
                  <table className="w-full border-collapse">
                    <thead className="border-b border-gray-800">
                      <tr>
                        <th className={`${cellTh} sticky left-0 z-[1] bg-surface`}>Item</th>
                        {[...half].reverse().map((h) => (
                          <th key={h.period_end} className={`${cellTh} text-right`}>
                            {fmtDate(h.period_end, { month: "short", year: "numeric" })}
                            {h.cf_months ? <span className="block text-gray-700">{h.cf_months}M CF</span> : null}
                          </th>
                        ))}
                      </tr>
                    </thead>
                    <tbody>
                      {[
                        ["Total assets", "total_assets"], ["Total equity", "total_equity"], ["Total debt", "total_debt"],
                        ["Current assets", "current_assets"], ["Current liabilities", "current_liabilities"],
                        ["Cash & equivalents", "cash_and_equivalents"], ["Operating cash flow", "operating_cf"],
                        ["Capex", "capex"], ["Free cash flow", "free_cash_flow"],
                      ].map(([label, key]) => (
                        <tr key={key} className="border-b border-gray-800/60 last:border-b-0">
                          <td className="px-4 py-3 text-[13px] text-gray-400 whitespace-nowrap sticky left-0 z-[1] bg-surface">{label}</td>
                          {[...half].reverse().map((h) => (
                            <td key={h.period_end} className={`${cellTd} text-right ${Number(h[key]) < 0 ? "text-red-400" : ""}`}>{fmtCr(h[key])}</td>
                          ))}
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </HScroll>
              ) : (
                <p className="px-4 pb-6 text-[13px] text-gray-600">No half-yearly balance sheet filed yet.</p>
              )}
            </Panel>

            <Panel>
              <div className="px-5 pt-5 pb-2"><MonoLabel className="text-gray-500">Key ratios</MonoLabel></div>
              {ratios.length ? (
                <dl className="px-5 pb-4">
                  {ratios.map(([k, v]) => (
                    <div key={k} className="flex justify-between gap-4 py-2.5 border-b border-gray-800/60 last:border-b-0">
                      <dt className="text-[13px] text-gray-400">{humanize(k)}</dt>
                      <dd className="font-mono text-[13px] text-gray-200 text-right">{fmtRatioValue(k, v)}</dd>
                    </div>
                  ))}
                </dl>
              ) : (
                <p className="px-5 pb-6 text-[13px] text-gray-600">Ratios not computed yet.</p>
              )}
            </Panel>
          </div>
        </div>
      )}
    </Section>
  );
}

const NEWS_STEP = 8;

function CompanyNews({ profile }) {
  const [items, setItems] = useState(null);
  const [error, setError] = useState(false);
  const [visible, setVisible] = useState(NEWS_STEP);

  useEffect(() => {
    let cancelled = false;
    setItems(null);
    setVisible(NEWS_STEP);
    const load = profile.id
      ? getCompanyNews(profile.id, 40)
      : getNews({ symbol: profile.symbol, limit: 40 });
    load
      .then((res) => { if (!cancelled) setItems(res.data || []); })
      .catch(() => { if (!cancelled) setError(true); });
    return () => { cancelled = true; };
  }, [profile.id, profile.symbol]);

  return (
    <Section index="04" label="News" title="Announcements" aside={<MonoLabel className="text-gray-500">FinBERT sentiment</MonoLabel>}>
      {error ? (
        <Empty>News unavailable right now.</Empty>
      ) : !items ? (
        <Empty>Loading news…</Empty>
      ) : !items.length ? (
        <Empty>No announcements for this company yet.</Empty>
      ) : (
        <>
          <div className="-mx-6 md:mx-0 md:border md:border-gray-800 md:rounded-xl overflow-hidden grid grid-cols-1 gap-px bg-gray-800 border-y border-gray-800">
            {items.slice(0, visible).map((item) => <NewsItem key={item.id} item={item} compact />)}
          </div>
          {visible < items.length && (
            <div className="mt-6 flex justify-center">
              <TouchPill onClick={() => setVisible((v) => v + NEWS_STEP)}>Show more ({items.length - visible} left)</TouchPill>
            </div>
          )}
        </>
      )}
    </Section>
  );
}
