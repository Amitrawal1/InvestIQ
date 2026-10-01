import React, { useEffect, useId, useRef, useState } from 'react';
import { Link, NavLink, useLocation } from 'react-router-dom';
import { AnimatePresence, motion } from 'motion/react';
import { ChevronDown, LogIn, LogOut, Settings, Pencil, User, Briefcase } from 'lucide-react';
import { useAuth } from '../context/AuthContext';
import ThemeSwitch from './ThemeSwitch';
import { MonoLabel } from './ui';

const itemClass =
  'flex w-full items-center gap-3 px-4 py-3 md:py-2.5 text-sm text-gray-300 hover:text-white hover:bg-white/5 focus-visible:bg-white/5 focus-visible:text-white outline-none transition-colors cursor-pointer';

// Avatar + dropdown in the Navbar: account header, settings links, theme control, sign out.
export default function ProfileMenu() {
  const { user, logout } = useAuth();
  const [open, setOpen] = useState(false);
  const rootRef = useRef(null);
  const buttonRef = useRef(null);
  const panelId = useId();
  const location = useLocation();

  // Close on route change
  useEffect(() => setOpen(false), [location.pathname, location.hash]);

  // Close on outside click / Escape; move focus into the panel when it opens
  useEffect(() => {
    if (!open) return undefined;
    const onPointer = (e) => {
      if (!rootRef.current?.contains(e.target)) setOpen(false);
    };
    const onKey = (e) => {
      if (e.key === 'Escape') {
        setOpen(false);
        buttonRef.current?.focus();
      }
    };
    document.addEventListener('pointerdown', onPointer);
    document.addEventListener('keydown', onKey);
    const t = requestAnimationFrame(() => rootRef.current?.querySelector('[data-menu-panel] a, [data-menu-panel] button')?.focus());
    return () => {
      document.removeEventListener('pointerdown', onPointer);
      document.removeEventListener('keydown', onKey);
      cancelAnimationFrame(t);
    };
  }, [open]);

  const name = user?.username || 'Account';
  const initial = name[0]?.toUpperCase() || 'U';

  const signOut = () => {
    setOpen(false);
    logout();
  };

  return (
    <div ref={rootRef} className="relative flex items-center gap-3">
      {!user && (
        <NavLink
          to="/login"
          className="hidden sm:inline-flex items-center touch:min-h-11 px-4 py-2 rounded-full border border-gray-500 text-[12px] font-medium uppercase tracking-wider text-gray-100 hover:bg-white hover:text-black hover:border-white transition-colors"
        >
          Sign in
        </NavLink>
      )}

      <button
        ref={buttonRef}
        type="button"
        aria-haspopup="true"
        aria-expanded={open}
        aria-controls={panelId}
        aria-label={user ? `Account menu for ${name}` : 'Theme and sign in'}
        onClick={() => setOpen((v) => !v)}
        className="group flex min-h-11 min-w-11 justify-center sm:justify-start items-center gap-3 rounded-full outline-none focus-visible:ring-1 focus-visible:ring-gray-400 cursor-pointer"
      >
        <span className="w-8 h-8 rounded-full border border-gray-600 group-hover:border-gray-400 flex items-center justify-center text-xs font-medium text-white transition-colors">
          {user ? initial : <User size={14} strokeWidth={1.5} />}
        </span>
        {user && <span className="hidden sm:block text-sm text-gray-300 group-hover:text-white transition-colors max-w-[140px] truncate">{name}</span>}
        <ChevronDown
          size={14}
          strokeWidth={1.5}
          className={`hidden sm:block text-gray-500 transition-transform duration-300 ${open ? 'rotate-180' : ''}`}
        />
      </button>

      <AnimatePresence>
        {open && (
          <motion.div
            id={panelId}
            data-menu-panel
            initial={{ opacity: 0, y: -6 }}
            animate={{ opacity: 1, y: 0, transition: { duration: 0.25, ease: 'easeOut' } }}
            exit={{ opacity: 0, y: -6, transition: { duration: 0.15 } }}
            className="absolute right-0 top-[calc(100%+14px)] w-[min(18rem,calc(100vw-2rem))] overflow-hidden rounded-xl border border-gray-800 bg-surface shadow-2xl"
          >
            {user ? (
              <>
                <div className="flex items-center gap-3 px-4 py-4 border-b border-gray-800">
                  <span className="w-10 h-10 shrink-0 rounded-full border border-gray-600 flex items-center justify-center text-sm font-medium text-white">
                    {initial}
                  </span>
                  <div className="min-w-0">
                    <div className="text-sm text-white truncate">{name}</div>
                    <div className="text-xs text-gray-500 truncate">{user.email}</div>
                  </div>
                </div>

                <nav aria-label="Account" className="py-2">
                  <Link to="/portfolio" className={itemClass}>
                    <Briefcase size={15} strokeWidth={1.5} aria-hidden="true" /> Portfolio
                  </Link>
                  <Link to="/settings" className={itemClass}>
                    <Settings size={15} strokeWidth={1.5} aria-hidden="true" /> Profile &amp; settings
                  </Link>
                  <Link to="/settings#profile" className={itemClass}>
                    <Pencil size={15} strokeWidth={1.5} aria-hidden="true" /> Edit profile
                  </Link>
                </nav>
              </>
            ) : null}

            <div className={`px-4 py-4 ${user ? 'border-t border-gray-800' : ''}`}>
              <MonoLabel className="block mb-3">Theme</MonoLabel>
              <ThemeSwitch />
            </div>

            <div className="border-t border-gray-800 py-2">
              {user ? (
                <button type="button" onClick={signOut} className={itemClass}>
                  <LogOut size={15} strokeWidth={1.5} aria-hidden="true" /> Sign out
                </button>
              ) : (
                <Link to="/login" className={itemClass}>
                  <LogIn size={15} strokeWidth={1.5} aria-hidden="true" /> Sign in
                </Link>
              )}
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}
