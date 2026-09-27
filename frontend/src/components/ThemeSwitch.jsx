import React from 'react';
import { Sun, Moon, Monitor } from 'lucide-react';
import { useTheme } from '../context/ThemeContext';

export const THEME_OPTIONS = [
  { value: 'light', label: 'Light', icon: Sun },
  { value: 'dark', label: 'Dark', icon: Moon },
  { value: 'system', label: 'System', icon: Monitor },
];

// Compact Light / Dark / System segmented control (radio group semantics)
export default function ThemeSwitch({ className = '' }) {
  const { preference, setPreference } = useTheme();

  const onKeyDown = (e) => {
    const i = THEME_OPTIONS.findIndex((o) => o.value === preference);
    const step = e.key === 'ArrowRight' || e.key === 'ArrowDown' ? 1 : e.key === 'ArrowLeft' || e.key === 'ArrowUp' ? -1 : 0;
    if (!step) return;
    e.preventDefault();
    const next = THEME_OPTIONS[(i + step + THEME_OPTIONS.length) % THEME_OPTIONS.length];
    setPreference(next.value);
    e.currentTarget.querySelector(`[data-value="${next.value}"]`)?.focus();
  };

  return (
    <div
      role="radiogroup"
      aria-label="Theme"
      onKeyDown={onKeyDown}
      className={`grid grid-cols-3 gap-1 p-1 rounded-full border border-gray-800 bg-white/5 ${className}`}
    >
      {THEME_OPTIONS.map(({ value, label, icon: Icon }) => {
        const active = preference === value;
        return (
          <button
            key={value}
            type="button"
            role="radio"
            aria-checked={active}
            data-value={value}
            tabIndex={active ? 0 : -1}
            onClick={() => setPreference(value)}
            className={`flex items-center justify-center gap-1.5 rounded-full px-2 py-1.5 text-[10px] font-mono tracking-widest uppercase transition-colors cursor-pointer outline-none focus-visible:ring-1 focus-visible:ring-gray-400 ${
              active ? 'bg-white text-black' : 'text-gray-400 hover:text-white'
            }`}
          >
            <Icon size={12} strokeWidth={2} aria-hidden="true" />
            {label}
          </button>
        );
      })}
    </div>
  );
}
