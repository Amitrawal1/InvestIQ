import React, { useEffect, useId, useRef } from "react";
import { createPortal } from "react-dom";
import { AnimatePresence, motion } from "motion/react";
import { X } from "lucide-react";
import { MonoLabel } from "./ui";

export const ghostButton =
  "inline-flex items-center justify-center gap-2 px-5 py-2.5 rounded-full border border-gray-600 text-[11px] font-medium uppercase tracking-wider text-gray-300 hover:bg-white hover:text-black hover:border-white disabled:opacity-40 disabled:pointer-events-none transition-colors cursor-pointer";

export const dangerButton =
  "inline-flex items-center justify-center gap-2 px-5 py-2.5 rounded-full border border-red-400 text-[11px] font-medium uppercase tracking-wider text-red-400 hover:bg-red-400 hover:text-black disabled:opacity-40 disabled:pointer-events-none transition-colors cursor-pointer";

// Modal confirm: surface panel over a blurred page, Escape / backdrop cancel,
// focus moves in on open and back to the trigger on close.
export default function ConfirmDialog({
  open,
  title,
  label = "Confirm",
  children,
  confirmLabel = "Confirm",
  cancelLabel = "Cancel",
  danger = false,
  busy = false,
  error = "",
  confirmDisabled = false,
  onConfirm,
  onCancel,
}) {
  const titleId = useId();
  const panelRef = useRef(null);
  const returnFocus = useRef(null);
  // Latest handlers without re-running the open/close effect (which moves focus)
  const latest = useRef({ busy, onCancel });
  latest.current = { busy, onCancel };

  useEffect(() => {
    if (!open) return undefined;
    returnFocus.current = document.activeElement;
    const onKey = (e) => {
      if (e.key === "Escape" && !latest.current.busy) latest.current.onCancel?.();
      // Keep Tab inside the dialog
      if (e.key === "Tab" && panelRef.current) {
        const items = panelRef.current.querySelectorAll("button:not([disabled]), input:not([disabled]), a[href]");
        if (!items.length) return;
        const first = items[0];
        const last = items[items.length - 1];
        if (e.shiftKey && document.activeElement === first) { e.preventDefault(); last.focus(); }
        else if (!e.shiftKey && document.activeElement === last) { e.preventDefault(); first.focus(); }
      }
    };
    document.addEventListener("keydown", onKey);
    const t = requestAnimationFrame(() => {
      const target = panelRef.current?.querySelector("input, [data-autofocus]") || panelRef.current?.querySelector("button");
      target?.focus();
    });
    return () => {
      document.removeEventListener("keydown", onKey);
      cancelAnimationFrame(t);
      returnFocus.current?.focus?.();
    };
  }, [open]);

  const submit = (e) => {
    e.preventDefault();
    if (!busy && !confirmDisabled) onConfirm?.();
  };

  return createPortal(
    <AnimatePresence>
      {open && (
        <motion.div
          className="fixed inset-0 z-[100] flex items-end sm:items-center justify-center p-4 bg-page/80 backdrop-blur-sm"
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          exit={{ opacity: 0 }}
          onMouseDown={(e) => { if (e.target === e.currentTarget && !busy) onCancel?.(); }}
        >
          <motion.form
            ref={panelRef}
            role="dialog"
            aria-modal="true"
            aria-labelledby={titleId}
            onSubmit={submit}
            initial={{ opacity: 0, y: 16 }}
            animate={{ opacity: 1, y: 0, transition: { duration: 0.3, ease: "easeOut" } }}
            exit={{ opacity: 0, y: 16, transition: { duration: 0.15 } }}
            className="relative w-full max-w-[480px] bg-surface border border-gray-800 rounded-xl shadow-2xl p-6 md:p-8"
          >
            <button
              type="button"
              onClick={onCancel}
              disabled={busy}
              aria-label="Close"
              className="absolute top-4 right-4 p-1.5 rounded-full text-gray-500 hover:text-white transition-colors cursor-pointer"
            >
              <X size={16} strokeWidth={1.5} />
            </button>
            <MonoLabel className={danger ? "text-red-400" : "text-gray-500"}>{label}</MonoLabel>
            <h2 id={titleId} className="mt-3 pr-8 text-xl md:text-2xl font-normal tracking-tight text-white">{title}</h2>
            <div className="mt-4 text-sm text-gray-400 leading-relaxed">{children}</div>
            {error && (
              <p role="alert" className="mt-5 text-[11px] font-mono tracking-wider uppercase text-red-400">{error}</p>
            )}
            <div className="mt-8 flex flex-col-reverse sm:flex-row sm:justify-end gap-3">
              <button type="button" onClick={onCancel} disabled={busy} className={ghostButton}>
                {cancelLabel}
              </button>
              <button
                type="submit"
                disabled={busy || confirmDisabled}
                className={danger ? dangerButton : ghostButton.replace("border-gray-600 text-gray-300", "border-white text-white")}
              >
                {busy ? "Please wait…" : confirmLabel}
              </button>
            </div>
          </motion.form>
        </motion.div>
      )}
    </AnimatePresence>,
    document.body
  );
}
