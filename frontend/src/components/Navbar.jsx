import React from 'react';
import { NavLink } from 'react-router-dom';
import { Search, ArrowRight } from 'lucide-react';
import Logo from './Logo';
import ProfileMenu from './ProfileMenu';
import useMarketTicker, { formatPrice, formatChangePct } from '../hooks/useMarketTicker';

const INDEX_NAMES = ['NIFTY 50', 'SENSEX'];

const links = [
  { to: '/home', label: 'Home' },
  { to: '/news', label: 'News' },
  { to: '/dashboard', label: 'Dashboard' },
  { to: '/predictor', label: 'Predictor' },
];

const Navbar = ({ onSearch }) => {
  const { quotes } = useMarketTicker();
  const indices = quotes.filter((q) => INDEX_NAMES.includes(q.name));

  return (
    <>
    {/* Fixed (not sticky) so it stays pinned even inside overflow-hidden page wrappers */}
    <nav className="fixed top-0 inset-x-0 z-50 bg-page/85 backdrop-blur-md border-b border-gray-800">
      <div className="h-[72px] flex items-center justify-between gap-6 px-6 md:px-16">
        {/* Left - Brand + links */}
        <div className="flex items-center gap-8">
          <Logo />
          <div className="hidden md:flex items-center gap-6 text-[11px] font-mono tracking-[0.2em] uppercase">
            {links.map(({ to, label }) => (
              <NavLink
                key={to}
                to={to}
                className={({ isActive }) =>
                  `transition-colors ${isActive ? 'text-white underline underline-offset-8' : 'text-gray-400 hover:text-white'}`
                }
              >
                {label}
              </NavLink>
            ))}
          </div>
        </div>

        {/* Center - Search (only where a page handles it) */}
        {onSearch && (
          <div className="relative flex-1 max-w-[380px]">
            <Search size={15} className="absolute left-4 top-1/2 -translate-y-1/2 text-gray-500" />
            <input
              type="text"
              placeholder="Search NSE stocks (e.g. RELIANCE, TCS)"
              onChange={(e) => onSearch(e.target.value)}
              className="w-full pl-10 pr-4 py-2.5 rounded-full bg-white/5 border border-gray-700 text-white text-sm outline-none placeholder:text-gray-500 focus:border-white transition-colors"
            />
          </div>
        )}

        {/* Right - Indices + user */}
        <div className="flex items-center gap-6">
          <div className="hidden xl:flex items-center gap-5 text-[10px] font-mono tracking-widest uppercase">
            {indices.map((idx, i) => (
              <React.Fragment key={idx.name}>
                {i > 0 && <ArrowRight size={12} strokeWidth={1} className="text-gray-600" />}
                <div className="flex gap-2">
                  <span className="text-gray-500">{idx.name}</span>
                  <span className="text-gray-200">{formatPrice(idx.price)}</span>
                  <span className={idx.changePct == null ? 'text-gray-500' : idx.changePct < 0 ? 'text-red-400' : 'text-green-500'}>
                    {formatChangePct(idx.changePct)}
                  </span>
                </div>
              </React.Fragment>
            ))}
          </div>

          <ProfileMenu />
        </div>
      </div>
    </nav>
    {/* Spacer so page content starts below the fixed bar */}
    <div aria-hidden="true" className="h-[73px]" />
    </>
  );
};

export default Navbar;
