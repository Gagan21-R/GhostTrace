import { AnimatePresence, motion } from "framer-motion";
import { ArrowRight, Loader2 } from "lucide-react";
import { useEffect, useRef, useState } from "react";
import { Link, useLocation } from "react-router-dom";
import { api } from "../lib/api";
import { t } from "../lib/i18n";

/** Shown on every page while anything is processing: what is running, how far it is, and a link to watch it live. */
export default function LiveRuns() {
  const [runs, setRuns] = useState<any[]>([]);
  const loc = useLocation();
  const timer = useRef<number | null>(null);
  useEffect(() => {
    let alive = true;
    const tick = async () => {
      try { const r = await api.get<any[]>("/api/runs/active"); if (alive) setRuns(r || []); } catch { /* signed out or offline */ }
      if (alive) timer.current = window.setTimeout(tick, document.hidden ? 8000 : 2500);
    };
    tick();
    return () => { alive = false; if (timer.current) window.clearTimeout(timer.current); };
  }, []);
  const here = (link: string) => loc.pathname + loc.search === link || loc.pathname === link.split("?")[0];
  const visible = runs.filter((r) => !here(r.link)).slice(0, 3);
  return (
    <div className="pointer-events-none fixed bottom-20 left-4 z-[55] flex flex-col gap-2 lg:left-[272px]">
      <AnimatePresence>
        {visible.map((r) => (
          <motion.div key={r.link + r.kind} initial={{ x: -30, opacity: 0 }} animate={{ x: 0, opacity: 1 }} exit={{ x: -30, opacity: 0 }}
            className="pointer-events-auto w-72 border-[3px] border-ink-900 bg-acid shadow-brutal">
            <Link to={r.link} className="block p-2.5">
              <div className="flex items-center gap-2 text-[11px] font-bold uppercase tracking-wide">
                <Loader2 className="h-3.5 w-3.5 animate-spin" />{t(r.label)}<span className="ml-auto mono">{Math.round((r.progress || 0) * 100)}%</span></div>
              <div className="mt-0.5 truncate text-sm font-semibold">{r.title}</div>
              <div className="mt-1 h-1.5 border border-ink-900 bg-surface"><div className="h-full bg-ink-900 transition-all" style={{ width: `${(r.progress || 0) * 100}%` }} /></div>
              <div className="mt-1 flex items-center justify-between text-[11px]"><span className="truncate">{(r.stage || "").replace(/_/g, " ")}</span>
                <span className="inline-flex items-center gap-0.5 font-bold">{t("Watch live")}<ArrowRight className="h-3 w-3" /></span></div>
            </Link>
          </motion.div>))}
      </AnimatePresence>
    </div>
  );
}
