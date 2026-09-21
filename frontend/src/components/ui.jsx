import React from "react";
import { motion } from "motion/react";

// Shared building blocks that mirror the Intro page's visual language:
// deep #050011 canvas, #0a0a0a panels, gray-800 hairlines, mono micro-labels.

export const fadeUp = {
  initial: { opacity: 0, y: 20 },
  animate: { opacity: 1, y: 0, transition: { duration: 0.8, ease: "easeOut" } },
};

export const stagger = (delay = 0.1, step = 0.1) => ({
  animate: { transition: { staggerChildren: step, delayChildren: delay } },
});

// "01 ——— LABEL" marker used above section headings
export function SectionLabel({ index, children, className = "" }) {
  return (
    <div className={`flex items-center gap-4 text-xs font-mono ${className}`}>
      <span className="text-white">{index}</span>
      <div className="w-16 h-[1.5px] bg-white" />
      {children && (
        <span className="text-[10px] tracking-[0.2em] uppercase text-gray-400">{children}</span>
      )}
    </div>
  );
}

export function MonoLabel({ children, className = "" }) {
  return (
    <span className={`text-[10px] font-mono tracking-widest uppercase text-gray-400 ${className}`}>
      {children}
    </span>
  );
}

// Exact copy of the Intro feature pills (NEWS ALERTS, STOCK SIGNALS, ...)
const pillClass = (active, className) =>
  `flex items-center gap-2 px-4 py-2 rounded-full border text-[11px] font-medium uppercase tracking-wider transition-all duration-300
  ${active
    ? "bg-white text-black border-white"
    : "border-gray-300 bg-white/10 backdrop-blur-sm text-gray-300 hover:border-white hover:bg-white/20 hover:text-white"}
  ${className}`;

export function Pill({ active = false, icon: Icon, children, className = "", ...props }) {
  return (
    <button type="button" className={`${pillClass(active, className)} cursor-pointer`} {...props}>
      {Icon && <Icon size={14} strokeWidth={2} />}
      {children}
    </button>
  );
}

// Same look as Pill, for non-interactive tags
export function PillTag({ icon: Icon, children, className = "", ...props }) {
  return (
    <span className={`${pillClass(false, className)} cursor-default`} {...props}>
      {Icon && <Icon size={14} strokeWidth={2} />}
      {children}
    </span>
  );
}

// The star from the Intro "Explore Now" button
export const StarIcon = ({ className = "" }) => (
  <svg viewBox="0 0 24 24" className={`w-4 h-4 fill-white group-hover:fill-[#111] ${className}`}>
    <path d="M12 2L15 10H22L16 15L18 22L12 18L6 22L8 15L2 10H9L12 2Z" />
  </svg>
);

// Exact copy of the Intro "Explore Now" button: dark block, white slide-in fill,
// star icon that tilts on hover. Pass `icon` to swap the star for a lucide icon.
export function PrimaryButton({ children, icon: Icon, className = "", ...props }) {
  const iconMotion = "transition-all duration-300 group-hover:scale-110 group-hover:-rotate-12 group-hover:-translate-y-1";

  return (
    <button
      className={`group relative overflow-hidden bg-[#1a1a1a] px-6 py-3.5 border border-[#1a1a1a] rounded-md shadow-sm transition-transform hover:-translate-y-[0.5px] hover:shadow-[3px_3px_0px_rgba(17,17,17,0.5)] active:translate-y-0 active:shadow-sm disabled:opacity-60 disabled:pointer-events-none flex items-center justify-center gap-3 cursor-pointer ${className}`}
      {...props}
    >
      <div className="absolute inset-0 bg-[#fcfcfc] -translate-x-[101%] group-hover:translate-x-0 transition-transform duration-700 ease-[cubic-bezier(0.16,1,0.3,1)] z-0" />

      <div className="relative z-10 flex items-center gap-2">
        {Icon
          ? <Icon size={16} className={`text-white group-hover:text-[#111] ${iconMotion}`} />
          : <StarIcon className={iconMotion} />}
        <span className="text-[15px] font-medium text-white group-hover:text-[#111] transition-colors duration-300">
          {children}
        </span>
      </div>
    </button>
  );
}

export function Panel({ children, className = "", glow = false }) {
  return (
    <div className={`relative overflow-hidden bg-[#0a0a0a] border border-gray-800 rounded-xl ${className}`}>
      {glow && (
        <div className="absolute -top-10 -right-10 w-32 h-32 bg-white/5 rounded-full blur-3xl pointer-events-none" />
      )}
      {children}
    </div>
  );
}

export function PageHeading({ index, label, title, children }) {
  return (
    <motion.div
      initial="initial"
      animate="animate"
      variants={stagger(0.1, 0.12)}
      className="flex flex-col lg:flex-row lg:items-end justify-between gap-6"
    >
      <div>
        <motion.div variants={fadeUp}>
          <SectionLabel index={index} className="mb-4">{label}</SectionLabel>
        </motion.div>
        <motion.h1
          variants={fadeUp}
          className="text-[2.6rem] md:text-[4rem] font-normal tracking-tight leading-[1] text-white"
        >
          {title}
        </motion.h1>
      </div>
      {children && <motion.div variants={fadeUp}>{children}</motion.div>}
    </motion.div>
  );
}

export function LiveDot({ className = "" }) {
  return <span className={`w-1.5 h-1.5 bg-green-500 rounded-full animate-pulse ${className}`} />;
}

export function Change({ value, className = "" }) {
  const up = value >= 0;
  return (
    <span className={`font-mono ${up ? "text-green-500" : "text-red-400"} ${className}`}>
      {up ? "+" : ""}{value}%
    </span>
  );
}
