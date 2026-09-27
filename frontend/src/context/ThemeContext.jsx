import React, { createContext, useCallback, useContext, useEffect, useMemo, useState } from 'react';

// Theme preference: 'light' | 'dark' | 'system', resolved to 'light' | 'dark'
// and applied as <html data-theme="..."> (index.html applies it before React loads).

export const THEME_STORAGE_KEY = 'investiq-theme';
const PREFERENCES = ['light', 'dark', 'system'];
// Dark is the design default, so only an explicit light OS preference resolves to light
const QUERY = '(prefers-color-scheme: light)';

const readPreference = () => {
  try {
    const v = localStorage.getItem(THEME_STORAGE_KEY);
    return PREFERENCES.includes(v) ? v : 'system';
  } catch {
    return 'system';
  }
};

const systemTheme = () =>
  typeof window !== 'undefined' && window.matchMedia?.(QUERY).matches ? 'light' : 'dark';

const ThemeContext = createContext({ preference: 'system', theme: 'dark', setPreference: () => {} });

export const useTheme = () => useContext(ThemeContext);

export function ThemeProvider({ children }) {
  const [preference, setPreferenceState] = useState(readPreference);
  const [system, setSystem] = useState(systemTheme);

  // Follow OS changes (only matters while preference is 'system')
  useEffect(() => {
    const mq = window.matchMedia?.(QUERY);
    if (!mq) return undefined;
    const onChange = () => setSystem(mq.matches ? 'light' : 'dark');
    mq.addEventListener?.('change', onChange);
    return () => mq.removeEventListener?.('change', onChange);
  }, []);

  const theme = preference === 'system' ? system : preference;

  useEffect(() => {
    const root = document.documentElement;
    root.dataset.theme = theme;
    root.style.colorScheme = theme;
  }, [theme]);

  const setPreference = useCallback((next) => {
    if (!PREFERENCES.includes(next)) return;
    setPreferenceState(next);
    try {
      localStorage.setItem(THEME_STORAGE_KEY, next);
    } catch {
      /* storage unavailable: preference lasts for this session only */
    }
  }, []);

  const value = useMemo(() => ({ preference, theme, setPreference }), [preference, theme, setPreference]);
  return <ThemeContext.Provider value={value}>{children}</ThemeContext.Provider>;
}
