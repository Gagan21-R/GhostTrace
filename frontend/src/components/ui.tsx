import clsx from "clsx";
import { AnimatePresence, motion } from "framer-motion";
import { AlertTriangle, Check, Copy, Inbox, Loader2, X } from "lucide-react";
import { useState, type ReactNode } from "react";
import { ExplainButton } from "./Assistant";

export function PageHeader({ title, subtitle, actions, eyebrow, explain = true, topic }: { title: ReactNode; subtitle?: ReactNode; actions?: ReactNode; eyebrow?: ReactNode; explain?: boolean; topic?: string }) {
  return (
    <motion.div className="mb-7 flex flex-wrap items-end justify-between gap-4 border-b-[3px] border-ink-900 pb-4"
      initial={{ opacity: 0, y: 14 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.35, ease: [0.2, 0.8, 0.2, 1] }}>
      <div className="min-w-0">
        {eyebrow && <div className="mb-2 inline-block bg-ink-900 px-2 py-0.5 text-[10px] font-bold uppercase tracking-[0.2em] text-acid">{eyebrow}</div>}
        <div className="flex flex-wrap items-center gap-3">
          <h1 className="font-display text-[30px] uppercase leading-[0.95] tracking-tight text-ink-900 sm:text-[38px]">{title}</h1>
          {explain && <ExplainButton title={title} topic={topic} context={typeof subtitle === "string" ? subtitle : undefined} />}
        </div>
        {subtitle && <p className="mt-2 max-w-3xl text-sm text-slate-600">{subtitle}</p>}
      </div>
      {actions && <div className="flex flex-wrap items-center gap-2">{actions}</div>}
    </motion.div>
  );
}

export function Stat({ label, value, hint, tone = "default", icon, topic }: { label: string; value: ReactNode; hint?: ReactNode; tone?: "default" | "warn" | "alert" | "ok"; icon?: ReactNode; topic?: string }) {
  const toneCls = { default: "text-ink-900", warn: "text-amber-600", alert: "text-rose-600", ok: "text-emerald-600" }[tone];
  const bar = { default: "bg-ink-900", warn: "bg-amber-400", alert: "bg-flame", ok: "bg-emerald-500" }[tone];
  return (
    <motion.div className="card card-lift relative overflow-hidden p-4" initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }}>
      <div className={clsx("absolute inset-x-0 top-0 h-1.5", bar)} />
      <div className="flex items-center justify-between gap-2"><span className="label">{label}</span>
        <span className="flex items-center gap-1.5 text-slate-500">{icon}<ExplainButton title={label} topic={topic} size="xs" /></span></div>
      <div className={clsx("mt-2 font-display text-[32px] tabular-nums leading-none", toneCls)}>{value}</div>
      {hint && <div className="mt-1.5 text-xs text-slate-600">{hint}</div>}
    </motion.div>
  );
}

const TONES: Record<string, string> = {
  slate: "bg-slate-100 text-slate-700", blue: "bg-accent-50 text-accent-700 ring-1 ring-inset ring-accent-100",
  green: "bg-emerald-50 text-emerald-700 ring-1 ring-inset ring-emerald-100", amber: "bg-amber-50 text-amber-700 ring-1 ring-inset ring-amber-100",
  red: "bg-rose-50 text-rose-700 ring-1 ring-inset ring-rose-100", violet: "bg-violet-50 text-violet-700 ring-1 ring-inset ring-violet-100",
  dark: "bg-accent-600 text-white",
};
export function Badge({ children, tone = "slate", className }: { children: ReactNode; tone?: keyof typeof TONES | string; className?: string }) {
  return <span className={clsx("chip", TONES[tone] || TONES.slate, className)}>{children}</span>;
}

export function statusTone(s?: string | null): string {
  if (!s) return "slate";
  if (["processed", "completed", "match", "confirmed", "resolved", "PASS", "supported", "accepted", "active"].includes(s)) return "green";
  if (["processing", "running", "queued", "pending", "open", "HOLD", "supported_with_reservations", "needs_more_evidence"].includes(s)) return "amber";
  if (["failed", "mismatch", "missing", "FAIL", "rejected", "contested", "high"].includes(s)) return "red";
  if (["unsupported", "insufficient_evidence", "dismissed", "archived"].includes(s)) return "slate";
  return "blue";
}

export function Loading({ label = "Loading" }: { label?: string }) {
  return <div className="flex items-center gap-2 py-10 justify-center text-sm text-slate-500"><Loader2 className="h-4 w-4 animate-spin" />{label}…</div>;
}

export function ErrorBox({ error, onRetry }: { error: string; onRetry?: () => void }) {
  return (
    <div className="card flex items-start gap-3 border-rose-200 bg-rose-50/60 p-4 text-sm text-rose-800">
      <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0" />
      <div className="flex-1">{error}</div>
      {onRetry && <button className="btn-ghost !py-1 text-rose-800" onClick={onRetry}>Retry</button>}
    </div>
  );
}

export function Empty({ title, hint, action, icon }: { title: string; hint?: ReactNode; action?: ReactNode; icon?: ReactNode }) {
  return (
    <div className="card flex flex-col items-center justify-center px-6 py-14 text-center">
      <div className="mb-3 rounded-full bg-slate-100 p-3 text-slate-400">{icon || <Inbox className="h-5 w-5" />}</div>
      <div className="font-medium text-slate-800">{title}</div>
      {hint && <div className="mt-1 max-w-md text-sm text-slate-500">{hint}</div>}
      {action && <div className="mt-4">{action}</div>}
    </div>
  );
}

export function Confidence({ value, label = true }: { value: number; label?: boolean }) {
  const pct = Math.round(value * 100);
  const color = value >= 0.8 ? "bg-accent-500" : value >= 0.6 ? "bg-accent-600" : "bg-slate-400";
  return (
    <div className="flex items-center gap-2" title="Rule confidence - how strongly the two records are linked and differ. Not a probability of wrongdoing.">
      <div className="h-1.5 w-20 overflow-hidden rounded-full bg-slate-200"><div className={clsx("h-full", color)} style={{ width: `${pct}%` }} /></div>
      {label && <span className="text-xs tabular-nums text-slate-500">{pct}%</span>}
    </div>
  );
}

export function Hash({ value, short = true }: { value: string; short?: boolean }) {
  const [copied, setCopied] = useState(false);
  return (
    <button className="group inline-flex items-center gap-1.5 mono text-slate-600 hover:text-ink-900" title={value}
      onClick={(e) => { e.stopPropagation(); navigator.clipboard?.writeText(value); setCopied(true); setTimeout(() => setCopied(false), 1200); }}>
      {short ? `${value.slice(0, 10)}…${value.slice(-6)}` : value}
      {copied ? <Check className="h-3 w-3 text-emerald-600" /> : <Copy className="h-3 w-3 opacity-0 group-hover:opacity-100" />}
    </button>
  );
}

export function Drawer({ open, onClose, title, children, width = "max-w-3xl" }: { open: boolean; onClose: () => void; title: ReactNode; children: ReactNode; width?: string }) {
  return (
    <AnimatePresence>
      {open && (
        <>
          <motion.div className="fixed inset-0 z-40 bg-ink-950/30 backdrop-blur-[1px]" initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }} onClick={onClose} />
          <motion.aside className={clsx("fixed right-0 top-0 z-50 flex h-full w-full flex-col bg-surface shadow-2xl", width)}
            initial={{ x: "100%" }} animate={{ x: 0 }} exit={{ x: "100%" }} transition={{ type: "spring", damping: 32, stiffness: 320 }}>
            <div className="flex items-center justify-between border-b border-slate-200 px-5 py-3.5">
              <div className="min-w-0 font-semibold text-ink-900">{title}</div>
              <button className="btn-ghost !p-1.5" onClick={onClose} aria-label="Close"><X className="h-4 w-4" /></button>
            </div>
            <div className="flex-1 overflow-y-auto scrollbar-thin">{children}</div>
          </motion.aside>
        </>
      )}
    </AnimatePresence>
  );
}

export function Modal({ open, onClose, title, children }: { open: boolean; onClose: () => void; title: string; children: ReactNode }) {
  return (
    <AnimatePresence>
      {open && (
        <motion.div className="fixed inset-0 z-50 flex items-center justify-center bg-ink-950/40 p-4" initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }} onClick={onClose}>
          <motion.div className="card w-full max-w-lg p-5" initial={{ y: 12, scale: 0.98 }} animate={{ y: 0, scale: 1 }} onClick={(e) => e.stopPropagation()}>
            <div className="mb-4 flex items-center justify-between"><h3 className="font-semibold">{title}</h3><button className="btn-ghost !p-1" onClick={onClose}><X className="h-4 w-4" /></button></div>
            {children}
          </motion.div>
        </motion.div>
      )}
    </AnimatePresence>
  );
}

export function OutcomeBadge({ outcome, size = "md" }: { outcome?: string | null; size?: "md" | "xl" }) {
  if (!outcome) return <Badge>—</Badge>;
  const cls = { PASS: "bg-emerald-600 text-white", FAIL: "bg-rose-600 text-white", HOLD: "bg-amber-500 text-white" }[outcome] || "bg-slate-500 text-white";
  return <span className={clsx("inline-flex items-center justify-center border-2 border-ink-900 font-bold tracking-wider", cls, size === "xl" ? "px-5 py-2 text-2xl" : "px-2 py-0.5 text-xs")}>{outcome}</span>;
}

export const VERDICT_LABEL: Record<string, string> = {
  supported: "Supported", supported_with_reservations: "Supported with reservations", contested: "Contested",
  insufficient_evidence: "Insufficient evidence", needs_review: "Needs review",
};

export function Section({ title, children, actions, className, explain = true, topic }: { title: ReactNode; children: ReactNode; actions?: ReactNode; className?: string; explain?: boolean; topic?: string }) {
  return (
    <motion.section className={clsx("card", className)} initial={{ opacity: 0, y: 16 }} whileInView={{ opacity: 1, y: 0 }}
      viewport={{ once: true, margin: "-40px" }} transition={{ duration: 0.35, ease: [0.2, 0.8, 0.2, 1] }}>
      <div className="flex flex-wrap items-center justify-between gap-2 border-b-2 border-ink-900 px-4 py-2.5">
        <div className="flex min-w-0 items-center gap-2">
          <h3 className="text-[13px] font-bold uppercase tracking-[0.08em] text-ink-900">{title}</h3>
          {explain && <ExplainButton title={title} topic={topic} />}
        </div>
        {actions}
      </div>
      <div className="p-4">{children}</div>
    </motion.section>
  );
}

export function Tabs({ tabs, value, onChange }: { tabs: { id: string; label: ReactNode }[]; value: string; onChange: (id: string) => void }) {
  return (
    <div className="flex gap-1 overflow-x-auto border-b-2 border-ink-900">
      {tabs.map((t) => <button key={t.id} className={clsx("tab", value === t.id && "tab-active")} onClick={() => onChange(t.id)}>{t.label}</button>)}
    </div>
  );
}
