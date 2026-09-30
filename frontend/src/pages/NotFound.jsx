import React from "react";
import { Link, useLocation, useNavigate } from "react-router-dom";
import { motion } from "motion/react";
import { ArrowLeft, Home } from "lucide-react";
import Navbar from "../components/Navbar";
import Footer from "../components/Footer";
import { SectionLabel, PrimaryButton, fadeUp, stagger } from "../components/ui";
import usePageTitle from "../hooks/usePageTitle";

const SUGGESTIONS = [
  { to: "/predictor", label: "Company rankings" },
  { to: "/news", label: "Market news" },
  { to: "/home#sectors", label: "Sectors" },
  { to: "/help", label: "Help & contact" },
];

export default function NotFound() {
  usePageTitle("Page not found");
  const { pathname } = useLocation();
  const navigate = useNavigate();

  return (
    <div className="min-h-screen w-full bg-page text-white font-sans overflow-x-clip flex flex-col">
      <Navbar />
      <motion.section
        initial="initial"
        animate="animate"
        variants={stagger(0.1, 0.12)}
        className="flex-1 px-6 md:px-16 pt-16 md:pt-24 pb-12"
      >
        <motion.div variants={fadeUp}><SectionLabel index="404" className="mb-6">Not found</SectionLabel></motion.div>
        <motion.h1 variants={fadeUp} className="text-[2.6rem] md:text-[5rem] font-normal tracking-tight leading-[0.95] text-white">
          THIS PAGE<br />ISN&rsquo;T LISTED
        </motion.h1>
        <motion.p variants={fadeUp} className="mt-6 max-w-[480px] text-[15px] text-gray-400 leading-relaxed">
          Nothing lives at <span className="font-mono text-gray-300 break-all">{pathname}</span>. The link may be old, or
          the address mistyped.
        </motion.p>
        <motion.div variants={fadeUp} className="mt-10 flex flex-col sm:flex-row gap-4">
          <PrimaryButton icon={Home} onClick={() => navigate("/home")} className="self-start">Go to Home</PrimaryButton>
          <button
            type="button"
            onClick={() => navigate(-1)}
            className="self-start flex items-center gap-2 touch:min-h-11 px-5 py-3 rounded-full border border-gray-600 text-[11px] font-medium uppercase tracking-wider text-gray-300 hover:bg-white hover:text-black hover:border-white transition-colors cursor-pointer"
          >
            <ArrowLeft size={14} strokeWidth={1.5} /> Go back
          </button>
        </motion.div>
        <motion.div variants={fadeUp} className="mt-14 border-t border-gray-800 pt-8">
          <span className="block mb-4 text-[10px] font-mono tracking-widest uppercase text-gray-500">Or try</span>
          <ul className="flex flex-wrap gap-3">
            {SUGGESTIONS.map((s) => (
              <li key={s.to}>
                <Link to={s.to} className="inline-flex items-center touch:min-h-11 px-4 py-2 rounded-full border border-gray-800 text-[11px] font-medium uppercase tracking-wider text-gray-300 hover:border-white hover:text-white transition-colors">
                  {s.label}
                </Link>
              </li>
            ))}
          </ul>
        </motion.div>
      </motion.section>
      <Footer />
    </div>
  );
}
