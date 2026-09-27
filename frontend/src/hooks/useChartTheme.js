import { useEffect, useState } from 'react';

// Resolved chart.js colours for the active theme, read from the CSS variables
// declared in index.css. Watches <html data-theme> so charts re-render when the
// theme changes (the attribute is set by ThemeContext / the index.html boot script).
const VARS = {
  line: '--chart-line',
  lineRgb: '--chart-line-rgb',
  secondary: '--chart-secondary',
  muted: '--chart-muted',
  axis: '--chart-axis',
  grid: '--chart-grid',
  bar: '--chart-bar',
  bar2: '--chart-bar-2',
  negative: '--chart-neg',
  accent: '--accent',
  accentRgb: '--chart-accent-rgb',
  tooltipBg: '--tooltip-bg',
  tooltipTitle: '--tooltip-title',
  tooltipBody: '--tooltip-body',
  tooltipBorder: '--tooltip-border',
};

const read = () => {
  const root = document.documentElement;
  const css = getComputedStyle(root);
  const out = { theme: root.dataset.theme || 'dark' };
  for (const [key, name] of Object.entries(VARS)) out[key] = css.getPropertyValue(name).trim();
  return out;
};

export default function useChartTheme() {
  const [colors, setColors] = useState(read);

  useEffect(() => {
    const observer = new MutationObserver(() => {
      const next = read();
      setColors((prev) => (prev.theme === next.theme && prev.line === next.line ? prev : next));
    });
    observer.observe(document.documentElement, { attributes: true, attributeFilter: ['data-theme'] });
    return () => observer.disconnect();
  }, []);

  return colors;
}
