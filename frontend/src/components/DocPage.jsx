import React from "react";
import { Link } from "react-router-dom";
import { motion } from "motion/react";
import Navbar from "./Navbar";
import Footer from "./Footer";
import { PageHeading, Panel, MonoLabel, fadeUp, stagger } from "./ui";
import usePageTitle from "../hooks/usePageTitle";

// Long-form page (policies, About, Help): Intro-style heading, a sticky contents list on wide
// screens, and numbered sections. `sections`: [{ id, title, body }].

export const P = ({ children }) => <p className="text-[15px] text-gray-300 leading-relaxed">{children}</p>;

export const List = ({ items }) => (
  <ul className="space-y-3">
    {items.map((item, i) => (
      <li key={i} className="flex gap-3 text-[15px] text-gray-300 leading-relaxed">
        <span aria-hidden="true" className="mt-[0.7em] h-px w-3 shrink-0 bg-gray-500" />
        <span>{item}</span>
      </li>
    ))}
  </ul>
);

export const Strong = ({ children }) => <span className="text-white font-medium">{children}</span>;

export const A = ({ to, href, children }) => {
  const cls = "text-white underline decoration-gray-600 underline-offset-4 hover:decoration-white transition-colors";
  return to ? <Link to={to} className={cls}>{children}</Link> : <a href={href} className={cls}>{children}</a>;
};

// Two-column fact table (e.g. data we collect -> why)
export const Table = ({ head, rows }) => (
  <Panel className="overflow-x-auto">
    <table className="w-full min-w-[520px] text-left text-[14px]">
      <thead>
        <tr className="border-b border-gray-800">
          {head.map((h) => (
            <th key={h} scope="col" className="px-5 py-4 text-[10px] font-mono font-normal tracking-widest uppercase text-gray-500">{h}</th>
          ))}
        </tr>
      </thead>
      <tbody className="divide-y divide-gray-800">
        {rows.map((row, i) => (
          <tr key={i} className="align-top">
            {row.map((cell, j) => (
              <td key={j} className={`px-5 py-4 leading-relaxed ${j === 0 ? "text-white" : "text-gray-400"}`}>{cell}</td>
            ))}
          </tr>
        ))}
      </tbody>
    </table>
  </Panel>
);

export default function DocPage({ index, label, title, tabTitle, intro, updated, sections, children }) {
  usePageTitle(tabTitle || title);

  return (
    <div className="min-h-screen w-full bg-page text-white font-sans overflow-x-clip">
      <Navbar />

      <section className="px-6 md:px-16 pt-12 pb-10">
        <PageHeading index={index} label={label} title={title}>
          {(intro || updated) && (
            <div className="max-w-[380px] lg:text-right space-y-3">
              {intro && <p className="text-[10px] font-mono tracking-widest uppercase text-gray-400 leading-relaxed">{intro}</p>}
              {updated && <MonoLabel className="block text-gray-500">Last updated · {updated}</MonoLabel>}
            </div>
          )}
        </PageHeading>
      </section>

      <div className="border-t border-gray-800 px-6 md:px-16 py-12 md:py-16 lg:grid lg:grid-cols-[220px_minmax(0,1fr)] lg:gap-16">
        {sections?.length > 1 && (
          <nav aria-label="On this page" className="hidden lg:block">
            <div className="sticky top-[97px] space-y-4">
              <MonoLabel className="block text-gray-500">On this page</MonoLabel>
              <ol className="space-y-2.5">
                {sections.map((s, i) => (
                  <li key={s.id}>
                    <a href={`#${s.id}`} className="flex gap-3 text-[13px] text-gray-400 hover:text-white transition-colors">
                      <span className="font-mono text-gray-600">{String(i + 1).padStart(2, "0")}</span>
                      <span>{s.title}</span>
                    </a>
                  </li>
                ))}
              </ol>
            </div>
          </nav>
        )}

        <div className="max-w-[760px] space-y-14 md:space-y-16">
          {sections?.map((s, i) => (
            <motion.section
              key={s.id}
              id={s.id}
              initial="initial"
              whileInView="animate"
              viewport={{ once: true, margin: "-40px" }}
              variants={stagger(0, 0.06)}
              className="scroll-mt-[97px]"
            >
              <motion.h2 variants={fadeUp} className="flex items-baseline gap-4 text-[1.4rem] md:text-[1.7rem] font-normal tracking-tight leading-tight text-white mb-6">
                <span className="text-xs font-mono text-gray-500">{String(i + 1).padStart(2, "0")}</span>
                {s.title}
              </motion.h2>
              <motion.div variants={fadeUp} className="space-y-5">{s.body}</motion.div>
            </motion.section>
          ))}
          {children}
        </div>
      </div>

      <Footer />
    </div>
  );
}
