import React, { useState, useEffect, useRef, useId } from "react";
import { motion, AnimatePresence, usePresence } from "motion/react";
import {
  ArrowRight,
  ArrowUpRight,
  Newspaper,
  LineChart,
  TrendingUp,
  Cpu,
  MonitorPlay,
  X
} from "lucide-react";

// GLOBE COMPONENT KO YAHAN IMPORT KIYA HAI
import IntroGlobe from "../components/IntroGlobe";

// --- DATA ---
const chaptersData = [
  { name: "Information Technology", image: "/InformationTechnology.jpg" },
  { name: "Financials", image: "/Financials.jpg" },
  { name: "Health Care", image: "/healthCare.jpg" },
  { name: "Consumer Discretionary", image: "/ConsumerDiscretionary.jpg" },
  { name: "Industrials", image: "/Industrials.jpg" }
];

// --- FEATURE DESCRIPTIONS DATA ---
const featureDescriptions = {
  "NEWS ALERTS": "Get instant notifications on breaking financial news that moves the market. Our system scans thousands of sources globally to bring you only the news that matters to your portfolio.",
  "STOCK SIGNALS": "Translate complex news into actionable insights. We provide clear Buy/Sell signals based on sentiment analysis of recent announcements, earnings reports, and geopolitical events.",
  "MARKET TRENDS": "Stay ahead of the curve by understanding the broader macroeconomic shifts. We analyze aggregate news sentiment to identify sector rotations and emerging bull or bear market phases.",
  "AI PREDICTOR": "Leverage advanced Natural Language Processing. Our proprietary AI doesn't just read the news; it historical compares it to past events to calculate the probability of a stock's upward movement."
};

// --- ANIMATION VARIANTS ---
const fadeUp = {
  initial: { opacity: 0, y: 20 },
  animate: { opacity: 1, y: 0, transition: { duration: 0.8, ease: "easeOut" } },
};

const letterBlock = {
  initial: { y: 120, opacity: 0 },
  animate: { 
    y: 0, 
    opacity: 1, 
    transition: { duration: 1.2, ease: [0.16, 1, 0.3, 1] } 
  }
};

// --- HELPER COMPONENT: SandTransitionImage ---
function SandTransitionImage({ src, alt }) {
  const [isPresent, safeToRemove] = usePresence();
  const filterId = useId();
  const feDisplacementMapRef = useRef(null);
  const feOffsetRef = useRef(null);
  const feGaussianBlurRef = useRef(null);
  const feColorMatrixRef = useRef(null);
  
  useEffect(() => {
    let animationFrameId;
    const startTime = performance.now();
    const duration = 900;

    const animate = (currentTime) => {
      const elapsed = currentTime - startTime;
      const t = Math.min(elapsed / duration, 1);
      
      const progress = isPresent 
        ? 1 - Math.pow(1 - t, 4) 
        : Math.pow(t, 3);        

      const visualProgress = isPresent ? 1 - progress : progress;

      if (feDisplacementMapRef.current) {
        feDisplacementMapRef.current.setAttribute("scale", (visualProgress * 150).toString());
      }
      if (feOffsetRef.current) {
        const dy = isPresent ? visualProgress * -80 : visualProgress * 120;
        const dx = (Math.random() - 0.5) * 60 * visualProgress;
        feOffsetRef.current.setAttribute("dx", dx.toString());
        feOffsetRef.current.setAttribute("dy", dy.toString());
      }
      if (feGaussianBlurRef.current) {
        feGaussianBlurRef.current.setAttribute("stdDeviation", (visualProgress * 6).toString());
      }
      if (feColorMatrixRef.current) {
        const opacity = Math.max(0, 1 - visualProgress * 1.2);
        feColorMatrixRef.current.setAttribute("values", `1 0 0 0 0  0 1 0 0 0  0 0 1 0 0  0 0 0 ${opacity} 0`);
      }

      if (t < 1) {
        animationFrameId = requestAnimationFrame(animate);
      } else if (!isPresent && safeToRemove) {
        safeToRemove();
      }
    };

    animationFrameId = requestAnimationFrame(animate);
    return () => cancelAnimationFrame(animationFrameId);
  }, [isPresent, safeToRemove]);

  return (
    <div className="absolute inset-0 w-full h-full">
      <svg className="hidden">
        <defs>
          <filter id={filterId} colorInterpolationFilters="sRGB">
            <feTurbulence type="fractalNoise" baseFrequency="1.8" numOctaves="4" result="noise" />
            <feDisplacementMap ref={feDisplacementMapRef} in="SourceGraphic" in2="noise" scale="0" xChannelSelector="R" yChannelSelector="G" result="displaced" />
            <feOffset ref={feOffsetRef} in="displaced" dx="0" dy="0" result="offset" />
            <feGaussianBlur ref={feGaussianBlurRef} in="offset" stdDeviation="0" result="blurred" />
            <feColorMatrix ref={feColorMatrixRef} in="blurred" type="matrix" values="1 0 0 0 0  0 1 0 0 0  0 0 1 0 0  0 0 0 1 0" />
          </filter>
        </defs>
      </svg>
      <img
        src={src}
        alt={alt}
        crossOrigin="anonymous"
        referrerPolicy="no-referrer"
        style={{ filter: `url(#${filterId})` }}
        className="absolute inset-0 w-[80%] h-[80%] m-auto object-cover mix-blend-lighten"
      />
    </div>
  );
}

// --- MAIN APP COMPONENT ---
export default function Intro() {
  const [activeChapter, setActiveChapter] = useState(2); 
  const [isMobileMenuOpen, setIsMobileMenuOpen] = useState(false);
  const [activeFeature, setActiveFeature] = useState(null); // New state for feature description

  useEffect(() => {
    const cycleTimer = setInterval(() => {
      setActiveChapter((prev) => (prev + 1) % 5);
    }, 3500);
    return () => clearInterval(cycleTimer);
  }, []);

  const handleFeatureClick = (label) => {
    if (label === "GO TO DASHBOARD") {
      // Add your navigation logic here, e.g., window.location.href = '/dashboard';
      console.log("Navigating to dashboard...");
      return;
    }
    setActiveFeature(activeFeature === label ? null : label);
  };

  return (
    <div className="font-sans text-[#111] bg-[#fcfcfc] overflow-x-hidden selection:bg-black selection:text-white">
      
      {/* SECTION 1: HERO - Bg set to #050011 immediately to prevent white flash */}
      <section className="relative w-full h-screen min-h-[800px] flex flex-col bg-[url('/bg.png')] bg-cover bg-center bg-no-repeat overflow-hidden ">
        {/* 1A. HEADER */}
        <motion.header
          initial="initial"
          animate="animate"
          variants={{ animate: { transition: { staggerChildren: 0.1, delayChildren: 0.1 } } }}
          className="pt-6 px-6 md:px-16 z-20 pointer-events-none" 
        >
          <motion.h1
            variants={{
              initial: { scale: 1.03 },
              animate: { scale: 1, transition: { staggerChildren: 0.06, delayChildren: 0.1 } }
            }}
            className="w-full"
          >
            <svg viewBox="0 0 850 100" className="w-full fill-white pointer-events-auto font-sans font-black">
              {"BULLSTACK".split("").map((letter, index) => (
                <motion.text
                  key={index}
                  x={index * 90} 
                  y="85"         
                  fontSize="90"  
                  variants={letterBlock}
                >
                  {letter}
                </motion.text>
              ))}
            </svg>
          </motion.h1>

          <motion.div variants={fadeUp} className="flex justify-between items-start mt-8 text-[10px] md:text-[11px] font-mono tracking-[0.2em] uppercase pointer-events-auto">
            <div className="w-[15%] space-y-1 text-gray-300">
              <p>STOCK</p>
              <p>NEWS</p>
              <p>TRENDS</p>
            </div>
            
            <ArrowRight className="hidden md:block w-[5%] text-gray-400" size={14} strokeWidth={1} />
            
            <div className="flex-1 md:w-[30%] text-gray-300 leading-relaxed font-mono">
              <p className="hidden md:block">AI POWERED ANALYSIS OF DAILY</p>
              <p className="hidden md:block">FINANCE NEWS TO QUANTIFY MARKET</p>
              <p className="hidden md:block">IMPACT AND PREDICT TRENDS.</p>
              
            </div>

            <ArrowRight className="hidden md:block w-[5%] text-gray-400" size={14} strokeWidth={1} />

            <div className="hidden md:flex w-[15%] flex-col space-y-1 text-gray-300">
              {["Visit", "Dashboard", "Discover", "Learn", "About"].map(link => (
                <a key={link} href={`#${link.toLowerCase()}`} className="hover:text-white hover:underline">{link}</a>
              ))}
            </div>

          </motion.div>
        </motion.header>

        <AnimatePresence>
          {isMobileMenuOpen && (
            <motion.div
              initial={{ y: -20, opacity: 0 }}
              animate={{ y: 0, opacity: 1 }}
              exit={{ y: -20, opacity: 0 }}
              className="absolute top-24 left-0 w-full bg-[#fcfcfc] border-b border-gray-200 shadow-xl z-50 md:hidden p-6 pt-10"
            >
              <div className="flex flex-col space-y-6 text-sm font-mono tracking-[0.2em] uppercase text-gray-800">
                {["GET STARTED", "ALGORITHM", "PERFORMANCE", "About"].map(link => (
                  <a key={link} href={`#${link.toLowerCase()}`} className="hover:text-black">{link}</a>
                ))}
              </div>
            </motion.div>
          )}
        </AnimatePresence>

        {/* 1D. FRONT BACKGROUND GLOBE */}
        <motion.div
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          transition={{ duration: 1.2 }}
          className="absolute top-0 left-0 w-full h-full z-0 scale-[1.28] origin-top"
        >
          <IntroGlobe />
        </motion.div>

        {/* 1E. LEFT SIDEBAR CONTENT */}
        <motion.div
          initial="initial"
          animate="animate"
          variants={{ animate: { transition: { staggerChildren: 0.15, delayChildren: 0.6 } } }}
          className="px-10 md:px-16 mt-20 sm:mt-28 md:mt-32 w-[320px] z-10 pointer-events-none"
        >
          <motion.div variants={fadeUp} className="flex items-center gap-4 mb-4 text-xs font-mono pointer-events-auto w-fit">
            <span className="text-white mix-blend-difference">01</span>
            <div className="w-16 h-[1.5px] bg-white mix-blend-difference" />
          </motion.div>
          
          <motion.h2 variants={fadeUp} className="text-[3.5rem] md:text-[5rem] font-normal tracking-tight leading-[1] mb-6 text-white mix-blend-difference pointer-events-auto">
            MARKET<br/>INTELLIGENCE
          </motion.h2>

          <motion.p variants={fadeUp} className="text-[13px] md:text-[14px] text-gray-300 w-[240px] leading-[1.6] mb-10 mix-blend-difference pointer-events-auto">
            Utilize the power of modern natural<br/>language processing to decode <br/>financial news signals.
          </motion.p>

          <motion.button 
            variants={fadeUp}
            className="pointer-events-auto group relative overflow-hidden bg-[#1a1a1a] px-6 py-3.5 border border-[#1a1a1a] rounded-md shadow-sm transition-transform hover:-translate-y-[0.5px] hover:shadow-[3px_3px_0px_rgba(17,17,17,0.5)] active:translate-y-0 active:shadow-sm flex items-center gap-3"
          >
            <div className="absolute inset-0 bg-[#fcfcfc] -translate-x-[101%] group-hover:translate-x-0 transition-transform duration-700 ease-[cubic-bezier(0.16,1,0.3,1)] z-0" />
            
            <div className="relative z-10 flex items-center gap-2">
              <svg viewBox="0 0 24 24" className="w-4 h-4 fill-white group-hover:fill-[#111] transition-all duration-300 group-hover:scale-110 group-hover:-rotate-12 group-hover:-translate-y-1">
                <path d="M12 2L15 10H22L16 15L18 22L12 18L6 22L8 15L2 10H9L12 2Z" />
              </svg>
              <span className="text-[15px] font-medium text-white group-hover:text-[#111] transition-colors duration-300">
                Explore Now
              </span>
            </div>
          </motion.button>
        </motion.div>
      </section>

      {/* SECTION 2: "WE READ THE NEWS" */}
      <section className="relative w-full min-h-[75vh] md:min-h-screen bg-[#050011] flex flex-col items-center pt-10 md:pt-16 pb-12 z-20">

        <motion.h2 
            initial={{ y: 40, opacity: 0 }}
            whileInView={{ y: 0, opacity: 1 }}
            viewport={{ once: true, margin: "-100px" }}
            transition={{ duration: 0.8 }}
            className="text-[2.2rem] md:text-[3.5rem] lg:text-[4.2rem] leading-[1.1] font-medium tracking-tight text-[#fcfcfc] max-w-[1000px] text-center px-6 mb-12">
            WE READ THE NEWS.<br/>YOU GET THE <br className="hidden md:block"/> TICKER.
        </motion.h2>

        <div className="flex flex-col items-center w-full max-w-4xl px-4">
          <motion.div 
              initial="initial"
              whileInView="animate"
              viewport={{ once: true }}
              variants={{ animate: { transition: { staggerChildren: 0.1, delayChildren: 0.3 } } }}
              className="flex flex-wrap justify-center gap-3 md:gap-4 mb-8"
          >
            {[
                { icon: Newspaper, label: "NEWS ALERTS" },
                { icon: LineChart, label: "STOCK SIGNALS" },
                { icon: TrendingUp, label: "MARKET TRENDS" },
                { icon: Cpu, label: "AI PREDICTOR" },
                { icon: MonitorPlay, label: "GO TO DASHBOARD" },
            ].map((pill, i) => {
              const isActive = activeFeature === pill.label;
              return (
                <motion.button 
                  key={i}
                  variants={fadeUp}
                  onClick={() => handleFeatureClick(pill.label)}
                  className={`flex items-center gap-2 px-4 py-2 rounded-full border text-[11px] font-medium uppercase tracking-wider transition-all duration-300 
                    ${isActive 
                      ? "bg-white text-black border-white" 
                      : "border-gray-300 bg-white/10 backdrop-blur-sm text-gray-300 hover:border-white hover:bg-white/20 hover:text-white"
                    }`}
                >
                  <pill.icon size={14} strokeWidth={2} />
                  {pill.label}
                </motion.button>
              )
            })}
          </motion.div>

          {/* FEATURE DESCRIPTION PANEL */}
          <div className="w-full h-[120px] flex justify-center mt-4">
            <AnimatePresence mode="wait">
              {activeFeature && (
                <motion.div
                  key={activeFeature}
                  initial={{ opacity: 0, y: 10, scale: 0.98 }}
                  animate={{ opacity: 1, y: 0, scale: 1 }}
                  exit={{ opacity: 0, y: -10, scale: 0.98 }}
                  transition={{ duration: 0.3, ease: "easeOut" }}
                  className="w-full max-w-2xl bg-[#0a0a0a] border border-gray-800 rounded-xl p-6 md:p-8 relative overflow-hidden shadow-2xl"
                >
                  {/* Subtle Background Glow */}
                  <div className="absolute -top-10 -right-10 w-32 h-32 bg-white/5 rounded-full blur-3xl pointer-events-none" />
                  
                  <div className="flex justify-between items-start mb-3">
                    <h3 className="text-white text-lg md:text-xl font-medium tracking-wide flex items-center gap-2">
                      <span className="w-1.5 h-1.5 bg-green-500 rounded-full animate-pulse" />
                      {activeFeature}
                    </h3>
                    <button 
                      onClick={() => setActiveFeature(null)}
                      className="text-gray-500 hover:text-white transition-colors"
                    >
                      <X size={18} />
                    </button>
                  </div>
                  
                  <p className="text-gray-400 text-sm md:text-base leading-relaxed font-light">
                    {featureDescriptions[activeFeature]}
                  </p>
                </motion.div>
              )}
            </AnimatePresence>
          </div>
        </div>

      </section>
        
        {/* SECTION 3: "MARKET COLLECTION" */}
        <section className="relative w-full bg-[#0a0a0a] text-white flex flex-col z-30">
        {/* 3B. HEADING AREA */}
        <div className="px-8 md:px-16 pt-32 md:pt-48 mb-16 z-10 flex flex-col xl:flex-row justify-between items-start gap-12">
          
          <div className="xl:w-[60%]">
            <h2 className="text-[1.8rem] md:text-[3rem] lg:text-[3.8rem] xl:text-[4rem] leading-[1.15] font-medium tracking-tight text-white">
              Curated from thousands of global data points
              <span className="inline-flex gap-2 md:gap-3 align-middle mx-2 md:mx-4 translate-y-[-4px]">
                {[Newspaper, TrendingUp, Cpu].map((Icon, i) => (
                  <span key={i} className="flex items-center justify-center w-10 h-10 md:w-14 md:h-14 rounded-full border border-gray-600 bg-black text-gray-400 hover:bg-white hover:text-black hover:border-white transition-colors duration-300">
                    <Icon size={22} />
                  </span>
                ))}
              </span>
              & AI predictions.
            </h2>
          </div>

          <div className="xl:w-[35%] flex flex-col xl:items-end xl:text-right">
            <p className="text-[9px] md:text-[10px] font-mono tracking-widest text-gray-400 uppercase mb-6 leading-relaxed">
              We don't just read the news<br/>we predict the impact.
            </p>
            <div className="flex flex-wrap gap-3 xl:justify-end">
              {["Real-Time", "Data-Driven", "Actionable"].map(pill => (
                <span key={pill} className="px-5 py-2 rounded-full border border-gray-600 text-[9px] font-mono tracking-widest uppercase text-gray-300 hover:bg-white hover:text-black hover:border-white transition-colors duration-300 cursor-default">
                  {pill}
                </span>
              ))}
            </div>
          </div>
        </div>

        {/* 3C. TWO-COLUMN PANEL */}
        <div className="w-full border-t border-gray-800 flex flex-col lg:flex-row z-10 bg-[#0a0a0a]">
          
          <div className="w-full lg:w-[35%] border-b lg:border-b-0 lg:border-r border-gray-800 min-h-[400px] md:min-h-[500px] flex flex-col justify-between relative overflow-hidden">
            <div className="p-8 text-gray-500 text-xl tracking-[0.3em] z-10">***</div>
            
            <div className="absolute inset-0 z-0">
              <AnimatePresence mode="wait">
                <SandTransitionImage 
                  key={activeChapter} 
                  src={chaptersData[activeChapter].image} 
                  alt={chaptersData[activeChapter].name} 
                />
              </AnimatePresence>
            </div>

            <div className="p-8 text-[10px] font-mono tracking-widest text-[#888] uppercase z-10 flex items-center gap-2">
              <div className="overflow-hidden h-[15px] relative w-4">
                <AnimatePresence mode="popLayout">
                  <motion.span 
                    key={activeChapter}
                    initial={{ y: 15, opacity: 0 }}
                    animate={{ y: 0, opacity: 1 }}
                    exit={{ y: -15, opacity: 0 }}
                    transition={{ duration: 0.4 }}
                    className="absolute"
                  >
                    0{activeChapter + 1}
                  </motion.span>
                </AnimatePresence>
              </div>
              <span className="text-[#333]">/</span> 05
            </div>
          </div>

          <div className="w-full lg:w-[65%] flex flex-col">
            <div className="border-b border-gray-800 p-8 flex justify-between items-center text-[10px] font-mono text-gray-400 tracking-widest uppercase">
              <span>Analyze the news. Predict the market.</span>
              <div className="flex gap-2">
                <span>Sector</span>
                <div className="overflow-hidden relative w-4 h-[15px]">
                  <AnimatePresence mode="popLayout">
                    <motion.span 
                      key={activeChapter}
                      initial={{ y: 15, opacity: 0 }}
                      animate={{ y: 0, opacity: 1 }}
                      exit={{ y: -15, opacity: 0 }}
                      transition={{ duration: 0.4 }}
                      className="absolute"
                    >
                      0{activeChapter + 1}
                    </motion.span>
                  </AnimatePresence>
                </div>
              </div>
            </div>
            
            <div className="flex flex-col">
              {chaptersData.map((chapter, idx) => {
                const isActive = activeChapter === idx;
                return (
                  <div 
                    key={idx}
                    onClick={() => setActiveChapter(idx)}
                    className={`border-b border-gray-800/80 px-8 py-8 flex justify-between items-center cursor-pointer transition-colors duration-300 ${isActive ? 'text-white' : 'text-[#444] hover:text-[#999]'}`}
                  >
                    <h3 className="text-2xl md:text-[2rem] font-medium tracking-tight">
                      {chapter.name}
                    </h3>
                    <AnimatePresence>
                      {isActive && (
                        <motion.div
                          initial={{ opacity: 0, x: -10, y: 10 }}
                          animate={{ opacity: 1, x: 0, y: 0 }}
                          exit={{ opacity: 0, x: 10, y: -10 }}
                          transition={{ duration: 0.3 }}
                        >
                          <ArrowUpRight size={22} strokeWidth={1} className="text-gray-400" />
                        </motion.div>
                      )}
                    </AnimatePresence>
                  </div>
                );
              })}
            </div>
          </div>
        </div>

        {/* 3D. BOTTOM FOOTER */}
        <div className="w-full border-t border-gray-800 bg-[#0a0a0a] px-8 py-8 text-[10px] font-mono tracking-widest text-gray-500 uppercase z-10 text-center md:text-left">
          Quantifying the impact of global financial news
        </div>

      </section>
    </div>
  );
}