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

// Rounded pill, same states as the Intro feature pills
export function Pill({ active = false, icon: Icon, children, className = "", ...props }) {
  return (
    <button
      type="button"
      className={`flex items-center gap-2 px-4 py-2 rounded-full border text-[11px] font-medium uppercase tracking-wider transition-all duration-300 cursor-pointer
        ${active
          ? "bg-white text-black border-white"
          : "border-gray-600 bg-white/5 backdrop-blur-sm text-gray-300 hover:border-white hover:bg-white/20 hover:text-white"}
        ${className}`}
      {...props}
    >
      {Icon && <Icon size={14} strokeWidth={2} />}
      {children}
    </button>
  );
}

// Dark button with the white slide-in fill from the Intro "Explore Now" CTA
export function PrimaryButton({ children, icon: Icon, className = "", ...props }) {
  return (
    <button
      className={`group relative overflow-hidden bg-[#1a1a1a] px-6 py-3.5 border border-gray-700 rounded-md shadow-sm transition-transform hover:-translate-y-[0.5px] hover:shadow-[3px_3px_0px_rgba(255,255,255,0.15)] active:translate-y-0 disabled:opacity-60 disabled:pointer-events-none flex items-center justify-center gap-3 cursor-pointer ${className}`}
      {...props}
    >
      <div className="absolute inset-0 bg-[#fcfcfc] -translate-x-[101%] group-hover:translate-x-0 transition-transform duration-700 ease-[cubic-bezier(0.16,1,0.3,1)] z-0" />
      <span className="relative z-10 flex items-center gap-2 text-[15px] font-medium text-white group-hover:text-[#111] transition-colors duration-300">
        {Icon && (
          <Icon size={16} className="transition-transform duration-300 group-hover:scale-110 group-hover:-rotate-12" />
        )}
        {children}
      </span>
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
