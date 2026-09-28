import React, { useEffect, useId, useRef, useState } from 'react';
import { NavLink, useLocation } from 'react-router-dom';
import { AnimatePresence, motion } from 'motion/react';
import { Search, ArrowRight, ArrowUpRight, LogIn } from 'lucide-react';
import Logo from './Logo';
import ProfileMenu from './ProfileMenu';
import { MonoLabel } from './ui';
import { useAuth } from '../context/AuthContext';
import useMarketTicker, { formatPrice, formatChangePct } from '../hooks/useMarketTicker';

const INDEX_NAMES = ['NIFTY 50', 'SENSEX'];

const links = [
  { to: '/home', label: 'Home' },
  { to: '/news', label: 'News' },
  { to: '/predictor', label: 'Predictor' },
];

const signedInLinks = [...links, { to: '/portfolio', label: 'Portfolio' }];

const changeTone = (pct) => (pct == null ? 'text-gray-500' : pct < 0 ? 'text-red-400' : 'text-green-500');

// Two hairlines that fold into an X
function MenuIcon({ open }) {
  const bar = 'absolute left-1/2 h-[1.5px] w-4 -translate-x-1/2 rounded-full bg-white transition-transform duration-300 ease-[cubic-bezier(0.16,1,0.3,1)]';
  return (
    <span aria-hidden="true" className="relative block h-4 w-4">
      <span className={`${bar} top-1/2 ${open ? '-translate-y-1/2 rotate-45' : '-translate-y-[4px]'}`} />
      <span className={`${bar} top-1/2 ${open ? '-translate-y-1/2 -rotate-45' : 'translate-y-[3px]'}`} />
    </span>
  );
}

const panelMotion = {
  initial: { opacity: 0, y: -8 },
  animate: { opacity: 1, y: 0, transition: { duration: 0.3, ease: [0.16, 1, 0.3, 1], staggerChildren: 0.04, delayChildren: 0.05 } },
  exit: { opacity: 0, y: -8, transition: { duration: 0.18, ease: 'easeIn' } },
};

const rowMotion = {
  initial: { opacity: 0, y: 8 },
  animate: { opacity: 1, y: 0, transition: { duration: 0.35, ease: 'easeOut' } },
};

const Navbar = ({ onSearch }) => {
  const { quotes, tick } = useMarketTicker();
  const { user } = useAuth();
  const indices = quotes.filter((q) => INDEX_NAMES.includes(q.name));
  const navLinks = user ? signedInLinks : links;

  const [menuOpen, setMenuOpen] = useState(false);
  const location = useLocation();
  const buttonRef = useRef(null);
  const panelRef = useRef(null);
  const panelId = useId();

  // Close on navigation
  useEffect(() => setMenuOpen(false), [location.pathname, location.search, location.hash]);

  // Close if the viewport grows past the phone layout (rotate / resize)
  useEffect(() => {
    const mq = window.matchMedia('(min-width: 768px)');
    const onChange = (e) => { if (e.matches) setMenuOpen(false); };
    mq.addEventListener('change', onChange);
    return () => mq.removeEventListener('change', onChange);
  }, []);

  // While open: Escape / outside tap close it, focus moves in, the page behind doesn't scroll
  useEffect(() => {
    if (!menuOpen) return undefined;
    const onKey = (e) => {
      if (e.key === 'Escape') {
        setMenuOpen(false);
        buttonRef.current?.focus();
      }
    };
    const onPointer = (e) => {
      if (!panelRef.current?.contains(e.target) && !buttonRef.current?.contains(e.target)) setMenuOpen(false);
    };
    document.addEventListener('keydown', onKey);
    document.addEventListener('pointerdown', onPointer);
    const prevOverflow = document.body.style.overflow;
    document.body.style.overflow = 'hidden';
    const t = requestAnimationFrame(() => panelRef.current?.querySelector('a, button')?.focus());
    return () => {
      document.removeEventListener('keydown', onKey);
      document.removeEventListener('pointerdown', onPointer);
      document.body.style.overflow = prevOverflow;
      cancelAnimationFrame(t);
    };
  }, [menuOpen]);

  // Tabbing out of the menu (past its last link or back before the button) closes it
  const onPanelBlur = (e) => {
    const next = e.relatedTarget;
    if (next && !panelRef.current?.contains(next) && !buttonRef.current?.contains(next)) setMenuOpen(false);
  };

  return (
    <>
    {/* Fixed (not sticky) so it stays pinned even inside overflow-hidden page wrappers */}
    <nav aria-label="Main" className="fixed top-0 inset-x-0 z-50 bg-page/85 backdrop-blur-md border-b border-gray-800">
      <div className="h-[72px] flex items-center justify-between gap-4 md:gap-6 px-6 md:px-16">
        {/* Left - Brand + links */}
        <div className="flex items-center gap-8 min-w-0">
          <Logo />
          <div className="hidden md:flex items-center gap-6 text-[11px] font-mono tracking-[0.2em] uppercase">
            {navLinks.map(({ to, label }) => (
              <NavLink
                key={to}
                to={to}
                className={({ isActive }) =>
                  `touch:py-4 transition-colors ${isActive ? 'text-white underline underline-offset-8' : 'text-gray-400 hover:text-white'}`
                }
              >
                {label}
              </NavLink>
            ))}
          </div>
        </div>

        {/* Center - Search (only where a page handles it) */}
        {onSearch && (
          <div className="relative flex-1 max-w-[380px] hidden sm:block">
            <Search size={15} className="absolute left-4 top-1/2 -translate-y-1/2 text-gray-500" />
            <input
              type="text"
              placeholder="Search NSE stocks (e.g. RELIANCE, TCS)"
              onChange={(e) => onSearch(e.target.value)}
              className="w-full pl-10 pr-4 py-2.5 rounded-full bg-white/5 border border-gray-700 text-white text-sm outline-none placeholder:text-gray-500 focus:border-white transition-colors"
            />
          </div>
        )}

        {/* Right - Indices + user + phone menu */}
        <div className="flex items-center gap-2 md:gap-6">
          <div className="hidden xl:flex items-center gap-5 text-[10px] font-mono tracking-widest uppercase">
            {indices.map((idx, i) => (
              <React.Fragment key={idx.name}>
                {i > 0 && <ArrowRight size={12} strokeWidth={1} className="text-gray-600" />}
                <div className="flex gap-2">
                  <span className="text-gray-500">{idx.name}</span>
                  <span
                    key={idx.moved ? `${tick}` : 'still'}
                    className={`text-gray-200 ${idx.moved ? `price-flash-${idx.moved}` : ''}`}
                  >
                    {formatPrice(idx.price)}
                  </span>
                  <span className={changeTone(idx.changePct)}>
                    {formatChangePct(idx.changePct)}
                  </span>
                </div>
              </React.Fragment>
            ))}
          </div>

          <ProfileMenu />

          <button
            ref={buttonRef}
            type="button"
            aria-label={menuOpen ? 'Close menu' : 'Open menu'}
            aria-expanded={menuOpen}
            aria-controls={panelId}
            onClick={() => setMenuOpen((v) => !v)}
            className="md:hidden group -mr-1.5 flex h-11 w-11 items-center justify-center rounded-full outline-none focus-visible:ring-1 focus-visible:ring-gray-400 cursor-pointer"
          >
            <span className={`flex h-8 w-8 items-center justify-center rounded-full border transition-colors ${menuOpen ? 'border-white' : 'border-gray-600 group-hover:border-gray-400'}`}>
              <MenuIcon open={menuOpen} />
            </span>
          </button>
        </div>
      </div>

      {/* Phone menu: drops down under the bar over a dimmed page */}
      <AnimatePresence>
        {menuOpen && (
            <motion.div
              key="panel"
              id={panelId}
              ref={panelRef}
              onBlur={onPanelBlur}
              variants={panelMotion}
              initial="initial"
              animate="animate"
              exit="exit"
              className="md:hidden absolute inset-x-0 top-full max-h-[calc(100dvh-73px)] overflow-y-auto overscroll-contain bg-surface border-b border-gray-800 shadow-2xl pb-[env(safe-area-inset-bottom)]"
            >
              <nav aria-label="Pages" className="px-6">
                {navLinks.map(({ to, label }, i) => (
                  <motion.div key={to} variants={rowMotion} className="border-b border-gray-800">
                    <NavLink
                      to={to}
                      onClick={() => setMenuOpen(false)}
                      className={({ isActive }) =>
                        `group flex min-h-14 items-center gap-5 text-[13px] font-mono tracking-[0.2em] uppercase outline-none transition-colors focus-visible:text-white ${
                          isActive ? 'text-white' : 'text-gray-400 hover:text-white'
                        }`
                      }
                    >
                      {({ isActive }) => (
                        <>
                          <span className="w-5 text-[10px] text-gray-600">0{i + 1}</span>
                          <span className="flex-1">{label}</span>
                          {isActive
                            ? <span aria-hidden="true" className="w-1.5 h-1.5 rounded-full bg-white" />
                            : <ArrowUpRight size={16} strokeWidth={1} className="text-gray-600 group-hover:text-white transition-colors" />}
                        </>
                      )}
                    </NavLink>
                  </motion.div>
                ))}
                {!user && (
                  <motion.div variants={rowMotion} className="border-b border-gray-800">
                    <NavLink
                      to="/login"
                      onClick={() => setMenuOpen(false)}
                      className="flex min-h-14 items-center gap-5 text-[13px] font-mono tracking-[0.2em] uppercase text-gray-400 hover:text-white focus-visible:text-white outline-none transition-colors"
                    >
                      <LogIn size={14} strokeWidth={1.5} className="w-5 text-gray-600" aria-hidden="true" />
                      <span className="flex-1">Sign in</span>
                    </NavLink>
                  </motion.div>
                )}
              </nav>

              {/* Indices (hidden in the bar below xl) */}
              <motion.div variants={rowMotion} className="px-6 pt-6 pb-7">
                <MonoLabel className="block mb-3 text-gray-500">Indices</MonoLabel>
                <dl className="grid grid-cols-2 gap-px overflow-hidden rounded-xl border border-gray-800 bg-gray-800">
                  {indices.map((idx) => (
                    <div key={idx.name} className="bg-page px-4 py-3.5 min-w-0">
                      <dt><MonoLabel className="text-gray-500">{idx.name}</MonoLabel></dt>
                      <dd className="mt-2 flex flex-wrap items-baseline gap-x-2 gap-y-0.5 font-mono tabular-nums">
                        <span
                          key={idx.moved ? `${tick}` : 'still'}
                          className={`text-[15px] text-white ${idx.moved ? `price-flash-${idx.moved}` : ''}`}
                        >
                          {formatPrice(idx.price)}
                        </span>
                        <span className={`text-[11px] ${changeTone(idx.changePct)}`}>{formatChangePct(idx.changePct)}</span>
                      </dd>
                    </div>
                  ))}
                </dl>
              </motion.div>
            </motion.div>
        )}
      </AnimatePresence>
    </nav>
    {/* Dimmed page behind the phone menu. Outside <nav>: its backdrop-filter would trap a fixed child */}
    <AnimatePresence>
      {menuOpen && (
        <motion.div
          key="menu-backdrop"
          aria-hidden="true"
          className="md:hidden fixed inset-x-0 top-[73px] bottom-0 z-40 bg-page/70 backdrop-blur-sm"
          initial={{ opacity: 0 }}
          animate={{ opacity: 1, transition: { duration: 0.25 } }}
          exit={{ opacity: 0, transition: { duration: 0.2 } }}
        />
      )}
    </AnimatePresence>
    {/* Spacer so page content starts below the fixed bar */}
    <div aria-hidden="true" className="h-[73px]" />
    </>
  );
};

export default Navbar;
