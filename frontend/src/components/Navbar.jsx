import React from 'react';
import { NavLink } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import { Search, LogOut, ArrowRight } from 'lucide-react';
import Logo from './Logo';

const links = [
  { to: '/home', label: 'Home' },
  { to: '/dashboard', label: 'Dashboard' },
  { to: '/predictor', label: 'Predictor' },
];

const indices = [
  { name: 'NIFTY 50', value: '22,957.10', change: '+0.82%' },
  { name: 'SENSEX', value: '75,410.35', change: '+0.78%' },
];

const Navbar = ({ onSearch }) => {
  const { user, logout } = useAuth();

  return (
    <nav className="w-full sticky top-0 z-40 bg-[#050011]/85 backdrop-blur-md border-b border-gray-800">
      <div className="flex items-center justify-between gap-6 px-6 md:px-16 py-4">
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
                  <span className="text-gray-200">{idx.value}</span>
                  <span className="text-green-500">{idx.change}</span>
                </div>
              </React.Fragment>
            ))}
          </div>

          {user ? (
            <div className="flex items-center gap-3">
              <div className="w-8 h-8 rounded-full border border-gray-600 flex items-center justify-center text-xs font-medium text-white">
                {user.username ? user.username[0].toUpperCase() : 'U'}
              </div>
              <span className="hidden sm:block text-sm text-gray-300">{user.username}</span>
              <button
                onClick={logout}
                title="Log out"
                className="text-gray-500 hover:text-white transition-colors cursor-pointer"
              >
                <LogOut size={16} />
              </button>
            </div>
          ) : (
            <NavLink
              to="/login"
              className="px-4 py-2 rounded-full border border-gray-600 text-[11px] font-medium uppercase tracking-wider text-gray-300 hover:bg-white hover:text-black hover:border-white transition-colors"
            >
              Sign in
            </NavLink>
          )}
        </div>
      </div>
    </nav>
  );
};

export default Navbar;
