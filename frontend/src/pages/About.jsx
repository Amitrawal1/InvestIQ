import React, { useEffect, useState } from "react";
import DocPage, { A, List, P, Strong, Table } from "../components/DocPage";
import { Panel, MonoLabel, LiveDot } from "../components/ui";
import { getRankingsMeta } from "../services/api";
import { SITE, mailto } from "../data/site";

const fmtDate = (d) => (d ? new Date(`${d}T00:00:00`).toLocaleDateString("en-IN", { day: "numeric", month: "short", year: "numeric" }) : "—");

// Current snapshot numbers from /rankings/meta; the page reads fine without them
function LiveSnapshot() {
  const [meta, setMeta] = useState(null);
  useEffect(() => {
    getRankingsMeta().then(setMeta).catch(() => setMeta(null));
  }, []);

  const stats = [
    ["Companies ranked", meta?.ranked?.toLocaleString("en-IN")],
    ["Latest snapshot", meta && fmtDate(meta.snapshot_date)],
    ["Next update", meta && fmtDate(meta.next_update)],
    ["Model", meta?.model_version],
  ];

  return (
    <Panel glow className="grid grid-cols-2 md:grid-cols-4 divide-x divide-y md:divide-y-0 divide-gray-800">
      {stats.map(([label, value]) => (
        <div key={label} className="px-5 py-5">
          <MonoLabel className="flex items-center gap-2 text-gray-500">
            {label === "Latest snapshot" && meta && <LiveDot />} {label}
          </MonoLabel>
          <div className="mt-3 text-lg text-white font-mono">{value || "—"}</div>
        </div>
      ))}
    </Panel>
  );
}

const sections = [
  {
    id: "what",
    title: "What InvestIQ does",
    body: (
      <>
        <P>
          {SITE.name} helps investors in Indian markets find and research companies worth a closer look, especially
          small and mid-sized ones that get little coverage. It brings together price data, company financial statements
          and exchange announcements for about 3,100 NSE-listed companies, organised into 10 sectors and 45 industries.
        </P>
        <LiveSnapshot />
      </>
    ),
  },
  {
    id: "methodology",
    title: "How the rankings work",
    body: (
      <>
        <P>Every company gets a growth score from 0 to 100, built from three models:</P>
        <Table
          head={["Model", "What it asks", "Weight"]}
          rows={[
            ["Market model", "Is the market confirming the business? Distance from the 52-week high, position versus the 200- and 50-day averages, 3- and 6-month returns versus the NIFTY Smallcap 250, and how few down days the stock has had.", "70%"],
            ["Financial model", "Is the business healthy and improving? Revenue and profit growth, margins, ROE and ROCE, debt and liquidity, and how much profit turns into cash. It uses only results that were public on the scoring date.", "30%"],
            ["News model", "What is happening now? NSE announcements every 15 minutes, with sentiment scored by FinBERT, a finance-tuned language model.", "Small"],
          ]}
        />
        <List
          items={[
            <>Banks, NBFCs and insurers are compared with their own peer group on NPAs, capital, ROA/ROE and cost ratios, which are shown as strengths and risks.</>,
            <>Red flags that have historically come before under-performance, such as negative equity or worsening asset quality at lenders, cost points.</>,
            <>Companies without fresh financial data are shown as <Strong>Insufficient data</Strong> rather than guessed.</>,
            <>Each score lists its main reasons and risks, so you can see why a company ranks where it does.</>,
          ]}
        />
      </>
    ),
  },
  {
    id: "testing",
    title: "How it was tested",
    body: (
      <>
        <P>
          The method was chosen by walk-forward testing from 2019 to 2026: each year was scored using only data available
          before it, then compared with what actually happened over the next 6 and 12 months. In those tests, the combined
          score ranked future out-performers about twice as well as a financial-statement-only score.
        </P>
        <P>
          It is still a screen, not a forecast. Read the <A to="/disclaimer">Investment Disclaimer</A> for its limits.
        </P>
      </>
    ),
  },
  {
    id: "data",
    title: "Data sources and schedule",
    body: (
      <Table
        head={["Data", "Source", "Updated"]}
        rows={[
          ["Daily prices and indices", "Upstox market data", "Every trading day"],
          ["Live ticker", "Upstox market quotes", "Every few seconds in market hours"],
          ["Financial statements", "XBRL result filings on NSE", "As companies file results"],
          ["Company announcements", "NSE corporate filings", "Every 15 minutes"],
          ["Rankings", "InvestIQ models", "1st and 16th of each month"],
        ]}
      />
    ),
  },
  {
    id: "privacy",
    title: "Your data",
    body: (
      <P>
        Portfolio linking is optional and read-only: {SITE.name} never sees your broker password and can&rsquo;t place
        orders. We don&rsquo;t sell data or run ads. Read the <A to="/privacy">Privacy Policy</A>.
      </P>
    ),
  },
  {
    id: "who",
    title: "Who builds it",
    body: (
      <P>
        {SITE.name} is built and run by {SITE.operator} in {SITE.country}. Feedback, bug reports and data corrections are
        welcome at <A href={mailto("InvestIQ feedback")}>{SITE.contactEmail}</A>, or see <A to="/help">Help</A>.
      </P>
    ),
  },
];

export default function About() {
  return (
    <DocPage
      index="A1"
      label="Company"
      title="ABOUT INVESTIQ"
      tabTitle="About"
      intro="Research tools for Indian markets, built on data and tested before they ship."
      sections={sections}
    />
  );
}
