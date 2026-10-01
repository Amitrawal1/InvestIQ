import React, { useEffect, useRef, useState } from "react";
import { motion } from "motion/react";
import { Link } from "react-router-dom";
import { ArrowLeft, ChevronRight } from "lucide-react";

// Shared building blocks that mirror the Intro page's visual language:
// deep page canvas (--page), surface panels (--surface), gray-800 hairlines, mono micro-labels.

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

// Pill for the app pages (filters, tabs, ranges): same look, but at least 44px tall on
// touch-size screens. Intro keeps the plain Pill so its design never changes.
export function TouchPill({ className = "", ...props }) {
  return <Pill className={`touch:min-h-11 justify-center ${className}`} {...props} />;
}

// Horizontal scroller for wide tables and pill rows: scrolls inside itself (never the page)
// and fades the edge that has more content, with a chevron hint on the right.
// `fade` is the colour class the fades blend into (match the background behind the content).
// `fadeLeft={false}` when the first column is sticky (it already marks the left edge).
export function HScroll({ children, className = "", innerClassName = "", fade = "from-page", label, hint = true, fadeLeft = true }) {
  const ref = useRef(null);
  const [edges, setEdges] = useState({ left: false, right: false });

  useEffect(() => {
    const el = ref.current;
    if (!el) return undefined;
    const update = () => {
      const left = el.scrollLeft > 2;
      const right = el.scrollLeft + el.clientWidth < el.scrollWidth - 2;
      setEdges((e) => (e.left === left && e.right === right ? e : { left, right }));
    };
    update();
    el.addEventListener("scroll", update, { passive: true });
    const ro = new ResizeObserver(update);
    ro.observe(el);
    if (el.firstElementChild) ro.observe(el.firstElementChild);
    return () => {
      el.removeEventListener("scroll", update);
      ro.disconnect();
    };
  }, []);

  const scrollable = edges.left || edges.right;
  const fadeBase = "pointer-events-none absolute inset-y-0 w-10 z-10 transition-opacity duration-300";

  return (
    <div className={`relative min-w-0 ${className}`}>
      <div
        ref={ref}
        className={`overflow-x-auto overscroll-x-contain [scrollbar-width:thin] ${innerClassName}`}
        {...(scrollable && label ? { role: "region", "aria-label": label, tabIndex: 0 } : {})}
      >
        {children}
      </div>
      <div aria-hidden="true" className={`${fadeBase} left-0 bg-gradient-to-r ${fade} to-transparent ${edges.left && fadeLeft ? "opacity-100" : "opacity-0"}`} />
      <div aria-hidden="true" className={`${fadeBase} right-0 bg-gradient-to-l ${fade} to-transparent flex items-start justify-end pt-3.5 ${edges.right ? "opacity-100" : "opacity-0"}`}>
        {hint && <ChevronRight size={16} strokeWidth={1.5} className="text-gray-400 mr-0.5" />}
      </div>
    </div>
  );
}

// Outlined pill for navigation actions (back, "all news", "explore first"): readable 12px text,
// near-white label and a visible border, so it reads as a button rather than a caption.
export const navButtonClass =
  "group inline-flex items-center gap-2 touch:min-h-11 px-4 py-2 rounded-full border border-gray-600 text-[12px] font-medium uppercase tracking-wider text-gray-100 hover:bg-white hover:text-black hover:border-white focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-gray-300 transition-colors cursor-pointer";

// Back link: arrow nudges left on hover
export function BackLink({ to, onClick, children, className = "" }) {
  const Icon = ArrowLeft;
  const content = (
    <>
      <Icon size={15} strokeWidth={1.75} aria-hidden="true" className="transition-transform duration-300 group-hover:-translate-x-0.5" />
      {children}
    </>
  );
  return to
    ? <Link to={to} className={`${navButtonClass} ${className}`}>{content}</Link>
    : <button type="button" onClick={onClick} className={`${navButtonClass} ${className}`}>{content}</button>;
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
  <svg viewBox="0 0 24 24" className={`w-4 h-4 fill-btn-fg group-hover:fill-btn-ink ${className}`}>
    <path d="M12 2L15 10H22L16 15L18 22L12 18L6 22L8 15L2 10H9L12 2Z" />
  </svg>
);

// Exact copy of the Intro "Explore Now" button: dark block, white slide-in fill,
// star icon that tilts on hover. Pass `icon` to swap the star for a lucide icon.
export function PrimaryButton({ children, icon: Icon, className = "", ...props }) {
  const iconMotion = "transition-all duration-300 group-hover:scale-110 group-hover:-rotate-12 group-hover:-translate-y-1";

  return (
    <button
      className={`group relative overflow-hidden bg-btn px-6 py-3.5 border border-btn rounded-md shadow-sm transition-transform hover:-translate-y-[0.5px] hover:shadow-[3px_3px_0px_rgba(17,17,17,0.5)] active:translate-y-0 active:shadow-sm disabled:opacity-60 disabled:pointer-events-none flex items-center justify-center gap-3 cursor-pointer ${className}`}
      {...props}
    >
      <div className="absolute inset-0 bg-btn-fill -translate-x-[101%] group-hover:translate-x-0 transition-transform duration-700 ease-[cubic-bezier(0.16,1,0.3,1)] z-0" />

      <div className="relative z-10 flex items-center gap-2">
        {Icon
          ? <Icon size={16} className={`text-btn-fg group-hover:text-btn-ink ${iconMotion}`} />
          : <StarIcon className={iconMotion} />}
        <span className="text-[15px] font-medium text-btn-fg group-hover:text-btn-ink transition-colors duration-300">
          {children}
        </span>
      </div>
    </button>
  );
}

export function Panel({ children, className = "", glow = false }) {
  return (
    <div className={`relative overflow-hidden bg-surface border border-gray-800 rounded-xl ${className}`}>
      {glow && (
        <div className="absolute -top-10 -right-10 w-32 h-32 bg-white/5 rounded-full blur-3xl pointer-events-none" />
      )}
      {children}
    </div>
  );
}

// Longest word, in ems of the heading font: long single words ("PHARMACEUTICALS")
// shrink the heading on narrow screens instead of breaking mid-word.
const titleEms = (title) => {
  if (typeof title !== "string") return 1;
  const longest = Math.max(...title.split(/\s+/).map((w) => w.length));
  return Math.max(1, longest * 0.72);
};

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
          style={{ "--title-em": titleEms(title) }}
          className="text-[min(2.6rem,calc((100vw-3rem)/var(--title-em)))] md:text-[min(4rem,calc((100vw-8rem)/var(--title-em)))] font-normal tracking-tight leading-[1] text-white break-words"
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
