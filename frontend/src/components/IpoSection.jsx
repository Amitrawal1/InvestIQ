import React, { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { motion } from "motion/react";
import { ArrowRight, ArrowUpRight, CalendarDays, Landmark, Rocket, Scale } from "lucide-react";
import { PillTag } from "./ui";
import { SignedPct, fmtDate } from "./rankings";
import { getIpos } from "../services/api";

// Home page "New listings" section: a teaser for the IPO Check page (/ipo).
// Shows the open and upcoming IPOs that were analysed, topped up with recent listings,
// and always keeps the call to action even when the IPO data can't be loaded.

const STATUS = {
  open: { text: "Open now", tone: "border-green-500/60 text-green-400", live: true },
  upcoming: { text: "Upcoming", tone: "border-sky-500/60 text-sky-400" },
  closed: { text: "Closed, not listed yet", tone: "border-gray-600 text-gray-400" },
  listed: { text: "Listed", tone: "border-gray-600 text-gray-400" },
};

// Same verdict colours as the IPO Check page
const VERDICT_TONE = {
  below: "border-sky-500/60 text-sky-400",
  in_line: "border-gray-600 text-gray-300",
  above: "border-amber-500/60 text-amber-400",
  well_above: "border-orange-500/60 text-orange-400",
};
const verdictTone = (v) => VERDICT_TONE[(v || "").replace("_loss_making", "")] || "border-gray-700 text-gray-500";

const cardMotion = {
  initial: { opacity: 0, y: 24 },
  animate: { opacity: 1, y: 0, transition: { duration: 0.6, ease: [0.16, 1, 0.3, 1] } },
};

const cardClass =
  "group relative flex h-full flex-col justify-between gap-6 overflow-hidden rounded-xl border border-gray-800 bg-surface p-5 md:p-6 transform-gpu transition-[transform,border-color] duration-500 ease-[cubic-bezier(0.16,1,0.3,1)] hover:-translate-y-1 hover:border-gray-500 focus-visible:outline-none focus-visible:border-white";

const Badge = ({ tone, live, children }) => (
  <span className={`inline-flex items-center gap-1.5 px-2 py-0.5 rounded-full border text-[10px] font-mono tracking-wider uppercase whitespace-nowrap ${tone}`}>
    {live && (
      <span className="relative flex h-1.5 w-1.5">
        <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-green-400 opacity-75" />
        <span className="relative inline-flex h-1.5 w-1.5 rounded-full bg-green-400" />
      </span>
    )}
    {children}
  </span>
);

const Arrow = () => (
  <span
    aria-hidden="true"
    className="flex h-9 w-9 shrink-0 items-center justify-center rounded-full border border-gray-600 text-white transition-[transform,background-color,border-color,color] duration-500 group-hover:translate-x-0.5 group-hover:-translate-y-0.5 group-hover:bg-white group-hover:border-white group-hover:text-black"
  >
    <ArrowUpRight size={16} strokeWidth={1.75} />
  </span>
);

// An analysed IPO (open, upcoming, closed or recently listed)
function IssueCard({ a }) {
  const s = STATUS[a.status] || STATUS.closed;
  const [lo, hi] = a.price_band || [];
  const band = lo == null ? "—" : lo === hi ? `₹${lo}` : `₹${lo}–${hi}`;
  return (
    <Link to="/ipo" className={cardClass}>
      <div className="flex items-start justify-between gap-3">
        <div className="flex flex-wrap gap-2">
          <Badge tone={s.tone} live={s.live}>{s.text}</Badge>
          {a.verdict_label && <Badge tone={verdictTone(a.verdict)}>{a.verdict_label}</Badge>}
        </div>
        <Arrow />
      </div>
      <div>
        <h3 className="text-[20px] font-medium tracking-tight leading-[1.15] text-white">{a.company}</h3>
        {a.business && <p className="mt-2 text-[13px] leading-snug text-gray-400 line-clamp-2">{a.business}</p>}
        <div className="mt-5 grid grid-cols-2 gap-4 border-t border-gray-800 pt-4">
          <div>
            <span className="block text-[10px] font-mono tracking-wider uppercase text-gray-500">{a.status === "listed" ? "Issue price" : "Price band"}</span>
            <span className="text-[14px] text-white">{band}</span>
          </div>
          <div>
            <span className="block text-[10px] font-mono tracking-wider uppercase text-gray-500">
              {a.status === "listed" ? "Listing day" : "Bidding"}
            </span>
            <span className="text-[14px] text-white">
              {a.status === "listed"
                ? <SignedPct value={a.list_gain_close} />
                : `${fmtDate(a.issue_start, { day: "2-digit", month: "short" })} – ${fmtDate(a.issue_end, { day: "2-digit", month: "short" })}`}
            </span>
          </div>
        </div>
      </div>
    </Link>
  );
}

// A recent listing that wasn't analysed: just how it listed
function ListingCard({ l }) {
  return (
    <Link to="/ipo" className={cardClass}>
      <div className="flex items-start justify-between gap-3">
        <Badge tone={STATUS.listed.tone}>Listed {fmtDate(l.listing_date, { day: "2-digit", month: "short" })}</Badge>
        <Arrow />
      </div>
      <div>
        <h3 className="text-[20px] font-medium tracking-tight leading-[1.15] text-white">{l.company}</h3>
        <div className="mt-5 grid grid-cols-2 gap-4 border-t border-gray-800 pt-4">
          <div>
            <span className="block text-[10px] font-mono tracking-wider uppercase text-gray-500">Issue price</span>
            <span className="text-[14px] text-white">{l.issue_price != null ? `₹${l.issue_price}` : "—"}</span>
          </div>
          <div>
            <span className="block text-[10px] font-mono tracking-wider uppercase text-gray-500">Listing day</span>
            <span className="text-[14px]">{l.list_gain_close != null ? <SignedPct value={l.list_gain_close} /> : "—"}</span>
          </div>
        </div>
      </div>
    </Link>
  );
}

const IpoSection = () => {
  const [data, setData] = useState(null);

  useEffect(() => {
    getIpos({ limit: 12 }).then(setData).catch(() => setData(null));
  }, []);

  // Two cards next to the call to action: analysed IPOs first, then recent listings
  const issues = data ? [...data.current, ...data.analysed_listed].slice(0, 2) : [];
  const listings = data ? data.listings.filter((l) => l.list_gain_close != null).slice(0, 2 - issues.length) : [];
  const live = data ? data.current.filter((a) => a.status === "open" || a.status === "upcoming").length : 0;
  const market = data?.market;

  return (
    <section id="ipos" className="w-full scroll-mt-24">
      {/* Heading */}
      <div className="px-6 md:px-16 pt-24 md:pt-32 mb-10 md:mb-12 flex flex-col xl:flex-row justify-between items-start gap-8">
        <motion.h2
          initial={{ y: 40, opacity: 0 }}
          whileInView={{ y: 0, opacity: 1 }}
          viewport={{ once: true, margin: "-100px" }}
          transition={{ duration: 0.8 }}
          className="xl:flex-1 xl:max-w-[760px] text-[1.8rem] md:text-[3rem] lg:text-[3.6rem] leading-[1.1] font-medium tracking-tight text-white"
        >
          New on the market. Every IPO, checked against its peers.
        </motion.h2>

        <div className="xl:shrink-0 flex flex-col xl:items-end xl:text-right">
          <p className="text-[11px] font-mono tracking-widest text-gray-300 uppercase mb-6 leading-relaxed">
            {data
              ? <>{live ? `${live} open or upcoming` : "No open IPOs right now"} · {data.listings_total} recent listings<br />See if the price is fair before you look closer.</>
              : <>Open, upcoming and recent IPOs<br />compared with listed companies.</>}
          </p>
          <div className="flex flex-wrap gap-3 xl:justify-end">
            <PillTag icon={Landmark}>NSE</PillTag>
            <PillTag icon={Scale}>Peer check</PillTag>
            <PillTag icon={CalendarDays}>Bidding dates</PillTag>
          </div>
        </div>
      </div>

      <motion.div
        initial="initial"
        whileInView="animate"
        viewport={{ once: true, margin: "-80px" }}
        variants={{ animate: { transition: { staggerChildren: 0.08 } } }}
        className="mx-6 md:mx-16 grid gap-3 md:gap-4 md:grid-cols-2 lg:grid-cols-[1.3fr_1fr_1fr]"
      >
        {/* Call to action */}
        <motion.div variants={cardMotion} className="md:col-span-2 lg:col-span-1">
          <Link
            to="/ipo"
            className="group relative flex h-full min-h-[300px] flex-col justify-between gap-8 overflow-hidden rounded-xl border border-gray-700 bg-surface p-6 md:p-8 transform-gpu transition-[transform,border-color] duration-500 ease-[cubic-bezier(0.16,1,0.3,1)] hover:-translate-y-1 hover:border-gray-400 focus-visible:outline-none focus-visible:border-white"
          >
            {/* Soft glow and a faint grid behind the text */}
            <div aria-hidden="true" className="absolute -top-24 -right-24 h-64 w-64 rounded-full bg-sky-500/20 blur-3xl transition-opacity duration-700 group-hover:opacity-80" />
            <div aria-hidden="true" className="absolute -bottom-28 -left-20 h-64 w-64 rounded-full bg-green-500/10 blur-3xl" />
            <div
              aria-hidden="true"
              className="absolute inset-0 opacity-[0.07] [background-image:linear-gradient(to_right,currentColor_1px,transparent_1px),linear-gradient(to_bottom,currentColor_1px,transparent_1px)] [background-size:32px_32px] text-white"
            />

            <div className="relative flex items-start justify-between">
              <span className="inline-flex items-center gap-2 text-[11px] font-mono tracking-widest uppercase text-gray-300">
                <Rocket size={14} strokeWidth={1.75} /> IPO Check
              </span>
              <Arrow />
            </div>

            <div className="relative">
              <h3 className="text-[26px] md:text-[30px] font-medium tracking-tight leading-[1.1] text-white">
                Is the IPO priced fairly?
              </h3>
              <p className="mt-3 max-w-[420px] text-[14px] leading-relaxed text-gray-400">
                Each issue is compared with listed companies on P/E, P/B and P/S, with its bidding dates and
                how earlier IPOs like it did.
              </p>

              {market && (
                <div className="mt-6 grid grid-cols-2 gap-4 border-t border-gray-800 pt-4">
                  <div>
                    <span className="block text-[10px] font-mono tracking-wider uppercase text-gray-500">IPOs in last 90 days</span>
                    <span className="text-[20px] text-white">{market.ipos_prior_90d}</span>
                  </div>
                  <div>
                    <span className="block text-[10px] font-mono tracking-wider uppercase text-gray-500">Median listing day</span>
                    <span className="text-[20px]"><SignedPct value={market.prior_90d_median_list_gain} /></span>
                  </div>
                </div>
              )}

              <span className="mt-6 inline-flex items-center gap-2 rounded-md bg-white px-5 py-3 text-[14px] font-medium text-black transition-colors group-hover:bg-gray-200">
                Explore IPOs
                <ArrowRight size={16} strokeWidth={1.75} className="transition-transform duration-300 group-hover:translate-x-1" />
              </span>
            </div>
          </Link>
        </motion.div>

        {issues.map((a) => (
          <motion.div key={a.symbol} variants={cardMotion}><IssueCard a={a} /></motion.div>
        ))}
        {listings.map((l) => (
          <motion.div key={l.symbol} variants={cardMotion}><ListingCard l={l} /></motion.div>
        ))}
      </motion.div>

      <p className="mx-6 md:mx-16 mt-4 text-[12px] text-gray-500">
        A description of the price, not advice to apply.
        {data?.as_of && <> Data as of {fmtDate(data.as_of)}.</>}
      </p>
    </section>
  );
};

export default IpoSection;
