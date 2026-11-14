import clsx from "clsx";
import {
  Activity, BarChart3, Clock3, Dna, FlaskConical, FolderKanban, GitFork, LayoutDashboard, LogOut, Menu, Network, ScrollText,
  SearchCheck, Settings, ShieldCheck, Swords, Vault, X,
} from "lucide-react";
import { useEffect, useState } from "react";
import { AnimatePresence, motion } from "framer-motion";
import { NavLink, Outlet, useLocation } from "react-router-dom";
import { getActiveCase, type ActiveCase } from "../lib/activeCase";
import { useAuth } from "../lib/auth";

export function Logo({ dark = true }: { dark?: boolean }) {
  return (
    <div className="flex items-center gap-2.5">
      <div className="flex h-9 w-9 items-center justify-center border-[3px] border-current bg-acid text-ink-900 shadow-[3px_3px_0_0_#ff4f1f]">
        <svg viewBox="0 0 32 32" className="h-6 w-6"><path d="M7 7l18 18M25 7L7 25" stroke="#0b0b0b" strokeWidth="5" strokeLinecap="square" /></svg>
      </div>
      <div className="leading-none"><div className={clsx("font-display text-[17px] tracking-[0.06em]", dark ? "text-paper" : "text-ink-900")}>EVIDENCE-X</div>
        <div className={clsx("mt-1 text-[9px] font-bold uppercase tracking-[0.24em]", dark ? "text-acid" : "text-flame")}>Every clue connected</div></div>
    </div>
  );
}

type Item = { to: string; label: string; icon: any; end?: boolean; perm?: string; caseScoped?: boolean };
const GROUPS: { title: string; items: Item[] }[] = [
  { title: "Workspace", items: [
    { to: "/", label: "Overview", icon: LayoutDashboard, end: true },
    { to: "/cases", label: "Cases", icon: FolderKanban },
  ] },
  { title: "Active case", items: [
    { to: "/go/evidence", label: "Evidence Vault", icon: Vault, caseScoped: true },
    { to: "/go/dna", label: "Evidence DNA", icon: Dna, caseScoped: true },
    { to: "/go/timeline", label: "Timeline", icon: Clock3, caseScoped: true },
    { to: "/go/graph", label: "Entity Graph", icon: Network, caseScoped: true },
    { to: "/go/challenge", label: "Challenge Centre", icon: Swords, caseScoped: true },
    { to: "/go/missing", label: "Missing Evidence", icon: SearchCheck, caseScoped: true },
    { to: "/go/whatif", label: "What-If Lab", icon: GitFork, caseScoped: true },
    { to: "/go/replay", label: "Investigation Replay", icon: Activity, caseScoped: true },
  ] },
  { title: "Platform", items: [
    { to: "/scenarios", label: "Scenario Lab", icon: FlaskConical },
    { to: "/evaluation", label: "Evaluation", icon: BarChart3 },
    { to: "/reports", label: "Reports", icon: ScrollText },
    { to: "/audit", label: "Audit Log", icon: ShieldCheck, perm: "audit:view" },
    { to: "/settings", label: "Settings & Admin", icon: Settings },
  ] },
];

export default function Layout() {
  const { user, logout, can } = useAuth();
  const [open, setOpen] = useState(false);
  const loc = useLocation();
  const [active, setActive] = useState<ActiveCase | null>(getActiveCase());
  useEffect(() => {
    const h = () => setActive(getActiveCase());
    window.addEventListener("evx-active-case", h);
    return () => window.removeEventListener("evx-active-case", h);
  }, []);
  const nav = (
    <nav className="flex-1 space-y-4 overflow-y-auto px-3 pb-3 scrollbar-thin">
      {GROUPS.map((g) => (
        <div key={g.title}>
          <div className="mb-1.5 px-3 text-[10px] font-bold uppercase tracking-[0.24em] text-flame">{g.title}</div>
          {g.title === "Active case" && (
            <NavLink to={active ? `/cases/${active.id}/overview` : "/cases"} onClick={() => setOpen(false)}
              className="mx-1 mb-1.5 block border-2 border-dashed border-paper/30 px-2.5 py-1.5 text-[11px] text-paper/80 hover:border-acid hover:text-acid">
              {active ? <><span className="mono text-acid">{active.number}</span><div className="truncate font-semibold text-paper">{active.title}</div></>
                : <span className="text-slate-400">No case selected - choose one</span>}
            </NavLink>)}
          <div className="space-y-0.5">
            {g.items.filter((n) => !n.perm || can(n.perm)).map((n) => (
              <NavLink key={n.to} to={n.to} end={n.end} onClick={() => setOpen(false)}
                className={({ isActive }) => clsx("flex items-center gap-3 px-3 py-1.5 text-[13px] font-semibold uppercase tracking-wide transition",
                  isActive ? "translate-x-1 bg-acid text-ink-900 shadow-[3px_3px_0_0_#ff4f1f]" : "text-paper/60 hover:translate-x-1 hover:text-paper",
                  n.caseScoped && !active && "opacity-60")}>
                <n.icon className="h-4 w-4" />{n.label}
              </NavLink>))}
          </div>
        </div>))}
    </nav>
  );
  const footer = (
    <div className="border-t border-white/10 p-4">
      <div className="flex items-center gap-3">
        <div className="flex h-8 w-8 items-center justify-center border-2 border-paper bg-flame text-xs font-bold text-ink-900">{user?.full_name?.split(" ").map((s) => s[0]).slice(0, 2).join("")}</div>
        <NavLink to="/profile" onClick={() => setOpen(false)} className="min-w-0 flex-1 rounded-md hover:bg-white/5"><div className="truncate text-sm font-medium text-white">{user?.full_name}</div><div className="text-[11px] capitalize text-slate-400">{user?.role} · profile</div></NavLink>
        <button className="rounded-md p-1.5 text-slate-400 hover:bg-white/10 hover:text-white" title="Sign out" onClick={logout}><LogOut className="h-4 w-4" /></button>
      </div>
    </div>
  );
  return (
    <div className="flex min-h-full">
      <aside className="fixed inset-y-0 left-0 hidden w-64 flex-col border-r-[3px] border-ink-900 bg-ink-950 lg:flex">
        <div className="px-5 py-5"><Logo /></div>{nav}
        <div className="mx-4 mb-3 border-2 border-acid/60 p-3 text-[11px] leading-relaxed text-paper/70">
          Findings assist investigators. They are not determinations of guilt or identity.
        </div>{footer}
      </aside>
      <div className="fixed inset-x-0 top-0 z-30 flex items-center justify-between border-b-[3px] border-flame bg-ink-950 px-4 py-3 lg:hidden">
        <Logo /><button className="rounded-md p-2 text-slate-300 hover:bg-white/10" onClick={() => setOpen(true)} aria-label="Menu"><Menu className="h-5 w-5" /></button>
      </div>
      {open && (
        <div className="fixed inset-0 z-50 flex lg:hidden">
          <div className="flex w-72 flex-col bg-ink-950"><div className="flex items-center justify-between px-5 py-5"><Logo /><button onClick={() => setOpen(false)} className="text-slate-400" aria-label="Close menu"><X className="h-5 w-5" /></button></div>{nav}{footer}</div>
          <div className="flex-1 bg-black/60" onClick={() => setOpen(false)} />
        </div>
      )}
      <main className="min-w-0 flex-1 px-4 pb-24 pt-20 sm:px-6 lg:ml-64 lg:px-8 lg:pt-8">
        <AnimatePresence mode="wait">
          <motion.div key={loc.pathname.split("/").slice(0, 4).join("/")} initial={{ opacity: 0, y: 18, skewY: 0.6 }} animate={{ opacity: 1, y: 0, skewY: 0 }}
            exit={{ opacity: 0, y: -10 }} transition={{ duration: 0.28, ease: [0.2, 0.8, 0.2, 1] }}><Outlet /></motion.div>
        </AnimatePresence>
      </main>
    </div>
  );
}
