import React from 'react';
import { Link } from 'react-router-dom';
import { motion } from 'motion/react';

const columns = [
  {
    title: 'Product',
    links: [
      { label: 'Home', to: '/home' },
      { label: 'Portfolio', to: '/portfolio' },
      { label: 'AI Predictor', to: '/predictor' },
    ],
  },
  {
    title: 'Data',
    links: [
      { label: 'Market News', to: '/news' },
      { label: 'Company Rankings', to: '/predictor' },
      { label: 'Sector Trends', to: '/home#sectors' },
      { label: 'Track Record', to: '/track-record' },
      { label: 'Market Events', to: '/events' },
    ],
  },
  {
    title: 'Company',
    links: [
      { label: 'About', to: '/about' },
      { label: 'How It Works', to: '/about#methodology' },
      { label: 'Help & Contact', to: '/help' },
      { label: 'Settings', to: '/settings' },
    ],
  },
  {
    title: 'Legal',
    links: [
      { label: 'Privacy Policy', to: '/privacy' },
      { label: 'Terms of Use', to: '/terms' },
      { label: 'Disclaimer', to: '/disclaimer' },
    ],
  },
];

export default function Footer() {
  return (
    <footer className="w-full bg-surface text-white border-t border-gray-800 mt-24 overflow-hidden">
      <div className="px-6 md:px-16 py-16 grid grid-cols-2 md:grid-cols-4 lg:grid-cols-6 gap-x-6 gap-y-10 md:gap-12">
        <div className="col-span-2 space-y-6">
          <span className="font-black text-2xl tracking-tight">INVEST IQ</span>
          <p className="text-[10px] font-mono tracking-widest uppercase leading-relaxed text-gray-400 max-w-[320px]">
            AI rankings for 3,100+ NSE-listed companies,<br />built from prices, results filings and daily news.
          </p>
        </div>

        {columns.map((col) => (
          <div key={col.title} className="space-y-3 md:space-y-5">
            <h4 className="text-[10px] font-mono tracking-widest uppercase text-gray-500">{col.title}</h4>
            <ul className="md:space-y-3">
              {col.links.map((link) => (
                <li key={link.label}>
                  <Link to={link.to} className="inline-flex touch:min-h-11 items-center text-sm text-gray-300 hover:text-white hover:underline transition-colors">
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
          <text x="0" y="88" fontSize="90" fill="none" strokeWidth="1" className="stroke-wordmark" textLength="850">
            INVEST IQ
          </text>
        </svg>
      </motion.div>

      <div className="border-t border-gray-800 px-6 md:px-16 pt-8 pb-[max(2rem,env(safe-area-inset-bottom))] flex flex-col md:flex-row justify-between gap-4 text-[10px] font-mono tracking-widest uppercase text-gray-500">
        <span>© {new Date().getFullYear()} InvestIQ · Made in India</span>
        <span className="md:text-right">
          Not SEBI registered. Not investment advice.{' '}
          <Link to="/disclaimer" className="text-gray-400 hover:text-white underline underline-offset-4 decoration-gray-700 transition-colors">Read the disclaimer</Link>
        </span>
      </div>
    </footer>
  );
}
