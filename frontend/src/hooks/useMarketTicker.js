import { useEffect, useState } from "react";
import { getMarketTicker } from "../services/api";

// Near-live while NSE/BSE are open (Mon-Fri 09:00-15:40 IST), slow otherwise; paused in hidden tabs
const LIVE_MS = 2 * 1000;
const CLOSED_MS = 60 * 1000;
const ERROR_MS = 15 * 1000;

// Shown until the first response, or when Upstox is unreachable (e.g. expired token)
const PLACEHOLDER = [
  "NIFTY 50", "SENSEX", "BANK NIFTY", "RELIANCE", "TCS", "INFY", "HDFC BANK", "ICICI BANK", "ITC",
].map((name) => ({ name, price: null, change: null, changePct: null }));

// One poller shared by every mounted consumer (Navbar + MarketTicker)
// Each quote also carries `moved` ("up" / "down" / null) vs the previous poll, and `tick` changes
// on every poll, so components can flash a price when it moves.
let state = { quotes: PLACEHOLDER, live: false, tick: 0 };
const listeners = new Set();
let timer = null;

function marketOpen(now = new Date()) {
  const ist = new Date(now.getTime() + (now.getTimezoneOffset() + 330) * 60000);
  const day = ist.getDay();
  const mins = ist.getHours() * 60 + ist.getMinutes();
  return day >= 1 && day <= 5 && mins >= 9 * 60 && mins <= 15 * 60 + 40;
}

async function poll() {
  let delay;
  try {
    const fresh = await getMarketTicker();
    const prev = Object.fromEntries(state.quotes.map((q) => [q.name, q.price]));
    const quotes = fresh.map((q) => {
      const before = prev[q.name];
      const moved = before == null || q.price == null || q.price === before ? null : q.price > before ? "up" : "down";
      return { ...q, moved };
    });
    state = { quotes, live: true, tick: state.tick + 1 };
    delay = marketOpen() ? LIVE_MS : CLOSED_MS;
  } catch {
    state = { quotes: state.live ? state.quotes : PLACEHOLDER, live: false, tick: state.tick };
    delay = ERROR_MS;
  }
  listeners.forEach((fn) => fn(state));
  schedule(delay);
}

function schedule(delay) {
  clearTimeout(timer);
  timer = listeners.size && !document.hidden ? setTimeout(poll, delay) : null;
}

// Coming back to the tab refreshes at once; leaving it stops polling
document.addEventListener("visibilitychange", () => {
  if (document.hidden) {
    clearTimeout(timer);
    timer = null;
  } else if (listeners.size && !timer) {
    poll();
  }
});

export function formatPrice(price) {
  return price == null
    ? "—"
    : price.toLocaleString("en-IN", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
}

export function formatChangePct(pct) {
  return pct == null ? "—" : `${pct >= 0 ? "+" : ""}${pct.toFixed(2)}%`;
}

export default function useMarketTicker() {
  const [snapshot, setSnapshot] = useState(state);

  useEffect(() => {
    listeners.add(setSnapshot);
    if (!timer && !document.hidden) poll();
    return () => {
      listeners.delete(setSnapshot);
      if (listeners.size === 0) {
        clearTimeout(timer);
        timer = null;
      }
    };
  }, []);

  return snapshot;
}
