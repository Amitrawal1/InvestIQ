import React, { useState } from "react";
import { RefreshCw } from "lucide-react";
import ConfirmDialog from "./ConfirmDialog";
import { apiError, connectBroker, disconnectBroker } from "../services/api";

// Shared bits for broker linking (Portfolio + Settings) and ₹ formatting.

export const BROKERS = {
  upstox: { name: "Upstox", note: "Log in on upstox.com. Links holdings, positions and funds." },
  zerodha: { name: "Zerodha", note: "Log in on kite.zerodha.com (Kite Connect). Links holdings, positions and funds." },
};
export const BROKER_ORDER = ["upstox", "zerodha"];
export const brokerName = (b) => BROKERS[b]?.name || (b ? b[0].toUpperCase() + b.slice(1) : "Broker");

export const CONSENT_NOTE =
  "Read-only: InvestIQ can't place orders or move money. You log in on the broker's own site, so InvestIQ never sees your broker password. Broker sessions expire daily; reconnect to refresh.";

// Friendly text for ?error=<code> from the OAuth callback
const ERROR_TEXT = {
  denied: "Linking was cancelled on the broker's page.",
  cancelled: "Linking was cancelled on the broker's page.",
  access_denied: "Linking was cancelled on the broker's page.",
  state: "That link request expired or was invalid. Start again from here.",
  invalid_state: "That link request expired or was invalid. Start again from here.",
  expired_state: "That link request expired. Start again from here.",
  exchange: "The broker didn't accept the login. Try again.",
  token: "The broker didn't accept the login. Try again.",
  not_configured: "Linking for that broker isn't configured yet.",
  sync: "Linked, but the first sync failed. Try Sync now.",
  link_failed: "The broker didn't accept the login, or the first sync failed. Try again.",
  account_not_found: "Your InvestIQ account wasn't found. Sign in again and retry.",
};
export const linkErrorText = (code) =>
  ERROR_TEXT[code] || `Linking didn't complete (${String(code).replace(/[_-]+/g, " ")}). Try again.`;

// --- numbers ---

const num = (v) => (v === null || v === undefined || v === "" ? null : Number(v));
export const finite = (v) => Number.isFinite(num(v));

// ₹ with Indian grouping: 123456.7 -> "₹1,23,457"; signed adds +/− (U+2212)
export const fmtINR = (v, { digits = 0, signed = false } = {}) => {
  if (!finite(v)) return "—";
  const n = num(v);
  const body = Math.abs(n).toLocaleString("en-IN", { minimumFractionDigits: digits, maximumFractionDigits: digits });
  const sign = n < 0 ? "−" : signed && n > 0 ? "+" : "";
  return `${sign}₹${body}`;
};

// Percent values from the portfolio API are already in percent points (12.5 = 12.5%)
export const fmtPctPts = (v, { digits = 2, signed = false } = {}) => {
  if (!finite(v)) return "—";
  const n = num(v);
  const sign = n < 0 ? "−" : signed && n > 0 ? "+" : "";
  return `${sign}${Math.abs(n).toFixed(digits)}%`;
};

export const fmtQty = (v) => (finite(v) ? num(v).toLocaleString("en-IN", { maximumFractionDigits: 4 }) : "—");

export const gainTone = (v) => (!finite(v) || num(v) === 0 ? "text-gray-400" : num(v) > 0 ? "text-green-500" : "text-red-400");

// "09:14" today, "27 Sep, 09:14" otherwise
export const fmtSyncTime = (v) => {
  if (!v) return null;
  const d = new Date(v);
  if (Number.isNaN(d.getTime())) return null;
  const time = d.toLocaleTimeString("en-IN", { hour: "2-digit", minute: "2-digit", hour12: false });
  const today = new Date().toDateString() === d.toDateString();
  return today ? time : `${d.toLocaleDateString("en-IN", { day: "2-digit", month: "short" })}, ${time}`;
};

// --- connection state ---

// "linked" | "expired" | "unlinked"
export const connectionState = (c) => {
  if (!c?.connected) return "unlinked";
  if (c.token_valid === false) return "expired";
  return "linked";
};

// Status chip: Synced 09:14 / Session expired / Not linked
export function BrokerStatus({ connection, className = "" }) {
  const state = connectionState(connection);
  let dot = "bg-gray-600";
  let text = "Not linked";
  if (state === "expired") {
    dot = "bg-red-400";
    text = "Session expired";
  } else if (state === "linked") {
    const t = fmtSyncTime(connection.last_synced_at);
    dot = connection.last_error ? "bg-yellow-500" : "bg-green-500";
    text = t ? `Synced ${t}` : "Linked · not synced yet";
  }
  return (
    <span
      title={connection?.last_error || undefined}
      className={`inline-flex items-center gap-2 px-3 py-1 rounded-full border border-gray-800 text-[10px] font-mono tracking-widest uppercase whitespace-nowrap ${
        state === "expired" ? "text-red-400" : "text-gray-400"
      } ${className}`}
    >
      <span aria-hidden="true" className={`w-1.5 h-1.5 rounded-full ${dot}`} />
      {text}
    </span>
  );
}

// Starts the OAuth-style link: ask the backend for the broker login URL, then leave the app.
export function useBrokerConnect() {
  const [pending, setPending] = useState(null);
  const [error, setError] = useState("");

  const connect = async (broker) => {
    setError("");
    setPending(broker);
    try {
      const { url } = await connectBroker(broker);
      if (!url) throw new Error("no url");
      window.location.assign(url);
      // Keep `pending` set while the browser navigates away
    } catch (err) {
      setPending(null);
      setError(err.response ? apiError(err, `Couldn't start linking ${brokerName(broker)}.`) : `Couldn't start linking ${brokerName(broker)}. Try again.`);
    }
  };

  return { connect, pending, error, clearError: () => setError("") };
}

// Disconnect confirm with the "also delete synced data" option
export function DisconnectDialog({ broker, onClose, onDone }) {
  const [deleteData, setDeleteData] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  const close = () => {
    if (busy) return;
    setDeleteData(false);
    setError("");
    onClose();
  };

  const confirm = async () => {
    setBusy(true);
    setError("");
    try {
      await disconnectBroker(broker, deleteData);
      setBusy(false);
      setDeleteData(false);
      onDone?.(broker, deleteData);
    } catch (err) {
      setBusy(false);
      setError(apiError(err, `Couldn't disconnect ${brokerName(broker)}.`));
    }
  };

  return (
    <ConfirmDialog
      open={Boolean(broker)}
      label="Disconnect broker"
      title={`Disconnect ${brokerName(broker)}?`}
      confirmLabel="Disconnect"
      danger
      busy={busy}
      error={error}
      onConfirm={confirm}
      onCancel={close}
    >
      <p>
        InvestIQ ends its {brokerName(broker)} session and forgets the link. Your broker account itself isn't affected.
      </p>
      <label className="mt-5 flex items-start gap-3 cursor-pointer select-none">
        <input
          type="checkbox"
          checked={deleteData}
          onChange={(e) => setDeleteData(e.target.checked)}
          className="mt-0.5 w-4 h-4 accent-accent cursor-pointer"
        />
        <span>
          <span className="block text-white">Also delete synced data</span>
          <span className="block mt-1 text-[12px] text-gray-500">
            Removes this broker's saved holdings snapshots and value history. Otherwise they stay until you delete them.
          </span>
        </span>
      </label>
    </ConfirmDialog>
  );
}

export function SpinIcon({ spinning, size = 14, className = "" }) {
  // While spinning, drop the hover transforms (they fight animate-spin)
  const cls = spinning ? className.split(" ").filter((c) => !c.startsWith("group-hover:") || c.includes("text-")).join(" ") + " animate-spin" : className;
  return <RefreshCw size={size} strokeWidth={1.5} aria-hidden="true" className={cls} />;
}
