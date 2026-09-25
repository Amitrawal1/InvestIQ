import React from 'react';
import { Link } from 'react-router-dom';
import { motion } from 'motion/react';

const columns = [
  {
    title: 'Product',
    links: [
      { label: 'Home', to: '/home' },
      { label: 'Dashboard', to: '/dashboard' },
      { label: 'AI Predictor', to: '/predictor' },
    ],
  },
  {
    title: 'Data',
    links: [
      { label: 'Market News', to: '/news' },
      { label: 'Stock Signals', to: '/dashboard' },
      { label: 'Sector Trends', to: '/home' },
    ],
  },
  {
    title: 'Account',
    links: [
      { label: 'Sign In', to: '/login' },
      { label: 'Intro', to: '/' },
    ],
  },
];

export default function Footer() {
  return (
    <footer className="w-full bg-[#0a0a0a] text-white border-t border-gray-800 mt-24 overflow-hidden">
      <div className="px-6 md:px-16 py-16 grid grid-cols-1 md:grid-cols-2 lg:grid-cols-5 gap-12">
        <div className="lg:col-span-2 space-y-6">
          <span className="font-black text-2xl tracking-tight">INVEST IQ</span>
          <p className="text-[10px] font-mono tracking-widest uppercase leading-relaxed text-gray-400 max-w-[320px]">
            AI powered analysis of daily finance news<br />to quantify market impact and predict trends.
          </p>
        </div>

        {columns.map((col) => (
          <div key={col.title} className="space-y-5">
            <h4 className="text-[10px] font-mono tracking-widest uppercase text-gray-500">{col.title}</h4>
            <ul className="space-y-3">
              {col.links.map((link) => (
                <li key={link.label}>
                  <Link to={link.to} className="text-sm text-gray-300 hover:text-white hover:underline transition-colors">
                    {link.label}
                  </Link>
                </li>
              ))}
            </ul>
          </div>
        ))}
      </div>

      {/* Oversized wordmark */}
      <motion.div
        initial={{ opacity: 0, y: 40 }}
        whileInView={{ opacity: 1, y: 0 }}
        viewport={{ once: true }}
        transition={{ duration: 1.2, ease: [0.16, 1, 0.3, 1] }}
        className="px-6 md:px-16 select-none pointer-events-none"
      >
        <svg viewBox="0 0 850 100" className="w-full font-sans font-black" aria-hidden="true">
          <text x="0" y="88" fontSize="90" fill="none" stroke="rgba(255,255,255,0.18)" strokeWidth="1" textLength="850">
            INVEST IQ
          </text>
        </svg>
      </motion.div>

      <div className="border-t border-gray-800 px-6 md:px-16 py-8 flex flex-col md:flex-row justify-between gap-4 text-[10px] font-mono tracking-widest uppercase text-gray-500">
        <span>Quantifying the impact of global financial news</span>
        <span>© {new Date().getFullYear()} InvestIQ. Not investment advice.</span>
      </div>
    </footer>
  );
}
