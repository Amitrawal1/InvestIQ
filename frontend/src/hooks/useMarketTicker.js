import { useEffect, useState } from "react";
import { getMarketTicker } from "../services/api";

const POLL_MS = 30 * 1000;

// Shown until the first response, or when Upstox is unreachable (e.g. expired token)
const PLACEHOLDER = [
  "NIFTY 50", "SENSEX", "BANK NIFTY", "RELIANCE", "TCS", "INFY", "HDFC BANK", "ICICI BANK", "ITC",
].map((name) => ({ name, price: null, change: null, changePct: null }));

// One poller shared by every mounted consumer (Navbar + MarketTicker)
let state = { quotes: PLACEHOLDER, live: false };
const listeners = new Set();
let timer = null;

async function poll() {
  try {
    const quotes = await getMarketTicker();
    state = { quotes, live: true };
  } catch {
    state = { quotes: state.live ? state.quotes : PLACEHOLDER, live: false };
  }
  listeners.forEach((fn) => fn(state));
}

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
    if (!timer) {
      poll();
      timer = setInterval(poll, POLL_MS);
    }
    return () => {
      listeners.delete(setSnapshot);
      if (listeners.size === 0) {
        clearInterval(timer);
        timer = null;
      }
    };
  }, []);

  return snapshot;
}
