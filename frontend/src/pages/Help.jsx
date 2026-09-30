import React, { useMemo, useState } from "react";
import { AnimatePresence, motion } from "motion/react";
import { Mail, Plus, Search } from "lucide-react";
import DocPage, { A, P } from "../components/DocPage";
import { Panel, MonoLabel } from "../components/ui";
import { SITE, mailto } from "../data/site";

const FAQ = [
  {
    group: "Account",
    items: [
      ["How do I create an account?", <>Go to <A to="/login">Sign in</A> and choose Create account, or use Continue with Google. Accounts are free.</>],
      ["I forgot my password.", <>Password reset by email isn&rsquo;t available yet. If you signed up with Google, just use Continue with Google. Otherwise email <A href={mailto("Password reset")}>{SITE.contactEmail}</A> from your account email and we&rsquo;ll help you get back in.</>],
      ["How do I change my name, email or password?", <>In <A to="/settings#profile">Settings</A>. Google-only accounts can also set a password there to sign in with email.</>],
      ["How do I delete my account?", <><A to="/settings#delete-account">Settings → Delete account</A>. It immediately removes your profile, broker links and synced portfolio data.</>],
    ],
  },
  {
    group: "Linking a broker",
    items: [
      ["Is linking my broker safe? Can InvestIQ trade?", <>Access is read-only. You sign in on Upstox&rsquo;s or Zerodha&rsquo;s own page, so we never see your password, PIN or OTP. InvestIQ can read holdings, positions and funds, and it cannot place orders or move money. Tokens are encrypted and you can disconnect at any time.</>],
      ["Why do I have to reconnect every day?", <>Brokers expire API access daily (Upstox at 3:30 AM IST, Zerodha at 6:00 AM IST). This is a broker rule. Tap Reconnect on the Portfolio page.</>],
      ["The OTP isn't arriving or isn't accepted.", <>The OTP is sent and checked by your broker, not by InvestIQ. Wait a minute before resending, use only the latest code, and check that the broker&rsquo;s SMS isn&rsquo;t blocked. After several attempts brokers pause OTPs for a while, so try again in 30 to 60 minutes. If it also fails in the broker&rsquo;s own app, contact the broker.</>],
      ["I see “Couldn't finish linking”.", <>The link timed out or was cancelled. Start again from <A to="/portfolio">Portfolio</A> and finish within 10 minutes. If it keeps happening, email us the time it happened.</>],
    ],
  },
  {
    group: "Rankings and data",
    items: [
      ["What does the growth score mean?", <>It ranks companies from 0 to 100 on price trend, financial health and news, relative to each other. Labels: Strong (75+), Positive (60+), Neutral (40+), Weak. See <A to="/about#methodology">how the rankings work</A>. It is not a buy or sell recommendation.</>],
      ["Why is a company “Insufficient data”?", "It has no recent financial results we could read, a price history that is too short or broken (for example after a corporate action), or too little data overall. We would rather not rank it than guess."],
      ["How often is everything updated?", "Rankings on the 1st and 16th of each month, announcements every 15 minutes, prices every trading day, and financials as companies file results."],
      ["I found wrong data for a company.", <>Email <A href={mailto("Data correction")}>{SITE.contactEmail}</A> with the company symbol and what looks wrong. Filings are parsed automatically, so reports like this help us fix it.</>],
    ],
  },
];

function Question({ q, a, open, onToggle, id }) {
  return (
    <div className="border-b border-gray-800 last:border-b-0">
      <h3>
        <button
          type="button"
          onClick={onToggle}
          aria-expanded={open}
          aria-controls={`${id}-a`}
          className="w-full flex items-start justify-between gap-6 px-5 md:px-6 py-5 text-left text-[15px] text-white hover:bg-white/[0.02] transition-colors cursor-pointer"
        >
          <span>{q}</span>
          <Plus size={16} strokeWidth={1.5} aria-hidden="true" className={`mt-0.5 shrink-0 text-gray-400 transition-transform duration-300 ${open ? "rotate-45" : ""}`} />
        </button>
      </h3>
      <AnimatePresence initial={false}>
        {open && (
          <motion.div
            id={`${id}-a`}
            role="region"
            initial={{ height: 0, opacity: 0 }}
            animate={{ height: "auto", opacity: 1 }}
            exit={{ height: 0, opacity: 0 }}
            transition={{ duration: 0.3, ease: [0.16, 1, 0.3, 1] }}
            className="overflow-hidden"
          >
            <div className="px-5 md:px-6 pb-5 text-[14px] text-gray-400 leading-relaxed">{a}</div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}

const textOf = (node) => {
  if (node == null || typeof node === "boolean") return "";
  if (typeof node === "string" || typeof node === "number") return String(node);
  if (Array.isArray(node)) return node.map(textOf).join(" ");
  return textOf(node.props?.children);
};

function Faq() {
  const [query, setQuery] = useState("");
  const [open, setOpen] = useState(null);

  const groups = useMemo(() => {
    const q = query.trim().toLowerCase();
    return FAQ.map((g) => ({
      ...g,
      items: g.items.filter(([question, answer]) => !q || `${question} ${textOf(answer)}`.toLowerCase().includes(q)),
    })).filter((g) => g.items.length);
  }, [query]);

  return (
    <div className="space-y-8">
      <label className="flex items-center gap-3 border-b border-gray-700 focus-within:border-white pb-3 transition-colors max-w-[480px]">
        <Search size={16} strokeWidth={1.5} className="text-gray-500" aria-hidden="true" />
        <span className="sr-only">Search help</span>
        <input
          type="search"
          value={query}
          onChange={(e) => { setQuery(e.target.value); setOpen(null); }}
          placeholder="Search questions"
          className="w-full bg-transparent text-white text-[15px] outline-none placeholder:text-gray-600"
        />
      </label>

      {groups.length === 0 && (
        <p className="text-[11px] font-mono tracking-wider uppercase text-gray-500">No matching questions. Email us below.</p>
      )}

      {groups.map((g) => (
        <div key={g.group} className="space-y-3">
          <MonoLabel className="block text-gray-500">{g.group}</MonoLabel>
          <Panel>
            {g.items.map(([q, a]) => {
              const id = `faq-${g.group}-${q}`.replace(/[^a-z0-9]+/gi, "-").toLowerCase();
              return <Question key={q} id={id} q={q} a={a} open={open === id} onToggle={() => setOpen(open === id ? null : id)} />;
            })}
          </Panel>
        </div>
      ))}
    </div>
  );
}

const CONTACTS = [
  ["Support and account help", "Support request"],
  ["Data corrections", "Data correction"],
  ["Privacy requests and grievances", "Data request"],
];

function Contact() {
  return (
    <>
      <P>
        Email is the fastest way to reach us. We reply within a few working days, and within {SITE.responseDays} days for
        privacy requests.
      </P>
      <Panel className="divide-y divide-gray-800">
        {CONTACTS.map(([label, subject]) => (
          <a
            key={label}
            href={mailto(subject)}
            className="flex flex-col sm:flex-row sm:items-center justify-between gap-2 px-5 md:px-6 py-5 hover:bg-white/[0.02] transition-colors group"
          >
            <span className="text-[15px] text-white">{label}</span>
            <span className="inline-flex items-center gap-2 text-[11px] font-mono tracking-wider text-gray-400 group-hover:text-white transition-colors break-all">
              <Mail size={13} strokeWidth={1.5} aria-hidden="true" /> {SITE.contactEmail}
            </span>
          </a>
        ))}
      </Panel>
      <P>
        Please don&rsquo;t send passwords, OTPs or broker PINs. We will never ask for them. See also the{" "}
        <A to="/privacy">Privacy Policy</A>, <A to="/terms">Terms of Use</A> and <A to="/disclaimer">Investment Disclaimer</A>.
      </P>
    </>
  );
}

const sections = [
  { id: "faq", title: "Frequently asked questions", body: <Faq /> },
  { id: "contact", title: "Contact us", body: <Contact /> },
];

export default function Help() {
  return (
    <DocPage
      index="H1"
      label="Support"
      title="HELP & CONTACT"
      tabTitle="Help & Contact"
      intro="Answers to common questions, and how to reach a person."
      sections={sections}
    />
  );
}
