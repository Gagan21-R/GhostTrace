import clsx from "clsx";
import { CheckSquare, ShieldQuestion, Square } from "lucide-react";
import { useState } from "react";
import { SourceRef } from "../../components/EvidenceViewer";
import { Badge, Empty, ErrorBox, Loading, statusTone } from "../../components/ui";
import { api } from "../../lib/api";
import { useAuth } from "../../lib/auth";
import { titleCase, useApi } from "../../lib/hooks";
import { useCase } from "./CaseWorkspace";

const SEV = { high: "border-l-rose-500", medium: "border-l-amber-500", low: "border-l-slate-300" } as Record<string, string>;

export default function GapsTab() {
  const { c, reload: reloadCase } = useCase();
  const { can } = useAuth();
  const { data, error, loading, setData } = useApi<any[]>(`/api/cases/${c.id}/gaps`);
  const [ticked, setTicked] = useState<Record<string, boolean>>(() => { try { return JSON.parse(localStorage.getItem(`evx_gap_${c.id}`) || "{}"); } catch { return {}; } });
  const tick = (k: string) => { const t = { ...ticked, [k]: !ticked[k] }; setTicked(t); try { localStorage.setItem(`evx_gap_${c.id}`, JSON.stringify(t)); } catch { /* ignore */ } };
  if (loading && !data) return <Loading />;
  if (error) return <ErrorBox error={error} />;
  if (!data!.length) return <Empty title="No evidence gaps identified" hint="Run processing to check for missing confirmations, incomplete exports, missing attachments and unverified senders." icon={<ShieldQuestion className="h-5 w-5" />} />;
  const review = async (id: string, status: string) => { await api.patch(`/api/gaps/${id}`, { status }); setData(data!.map((g) => (g.id === id ? { ...g, review_status: status } : g))); reloadCase(true); };
  const total = data!.reduce((n, g) => n + g.checklist.length, 0);
  const done = data!.reduce((n, g) => n + g.checklist.filter((_: any, i: number) => ticked[`${g.id}:${i}`]).length, 0);
  return (
    <div>
      <div className="card mb-4 flex flex-wrap items-center gap-6 p-4">
        <div><div className="label">Evidence completeness</div><div className="mt-1 text-sm text-slate-600">{data!.filter((g) => g.review_status === "open").length} open gaps · {done}/{total} collection actions ticked</div></div>
        <div className="h-2 min-w-[200px] flex-1 overflow-hidden rounded-full bg-slate-100"><div className="h-full bg-emerald-600 transition-all" style={{ width: `${total ? (done / total) * 100 : 0}%` }} /></div>
        <div className="flex gap-2 text-xs">{["high", "medium", "low"].map((s) => <Badge key={s} tone={s === "high" ? "red" : s === "medium" ? "amber" : "slate"}>{data!.filter((g) => g.severity === s).length} {s}</Badge>)}</div>
      </div>
      <p className="mb-4 text-xs text-slate-500">A gap marks information that is missing or unverified. It never implies wrongdoing. Checklist ticks are saved in this browser; resolve/dismiss decisions are recorded in the audit log.</p>
      <div className="grid gap-3 lg:grid-cols-2">
        {data!.map((g) => (
          <div key={g.id} className={clsx("card border-l-4 p-4", SEV[g.severity], g.review_status !== "open" && "opacity-60")}>
            <div className="flex flex-wrap items-center gap-2"><span className="mono font-semibold">{g.code}</span><Badge>{titleCase(g.category)}</Badge>
              <Badge tone={g.severity === "high" ? "red" : g.severity === "medium" ? "amber" : "slate"}>{g.severity}</Badge>
              <Badge tone={statusTone(g.review_status)} className="ml-auto">{g.review_status}</Badge></div>
            <p className="mt-2 text-sm text-slate-800">{g.description}</p>
            {g.why_it_matters && <p className="mt-2 rounded-md bg-slate-50 px-3 py-2 text-xs text-slate-600"><b className="text-slate-700">Why it matters:</b> {g.why_it_matters}</p>}
            {g.related.length > 0 && <div className="mt-2 flex flex-wrap gap-1.5">{g.related.map((r: any, i: number) => <SourceRef key={i} src={r} />)}</div>}
            <div className="label mb-1.5 mt-3">To resolve</div>
            <ul className="space-y-1">{g.checklist.map((item: string, i: number) => {
              const k = `${g.id}:${i}`;
              return <li key={i}><button className="flex items-start gap-2 text-left text-sm text-slate-700" onClick={() => tick(k)}>
                {ticked[k] ? <CheckSquare className="mt-0.5 h-4 w-4 shrink-0 text-emerald-600" /> : <Square className="mt-0.5 h-4 w-4 shrink-0 text-slate-400" />}
                <span className={ticked[k] ? "line-through text-slate-400" : ""}>{item}</span></button></li>; })}</ul>
            {can("review:decide") && (
              <div className="mt-3 flex gap-2 border-t border-slate-100 pt-3">
                {g.review_status === "open" ? <>
                  <button className="btn-outline !py-1 text-xs" onClick={() => review(g.id, "resolved")}>Mark resolved</button>
                  <button className="btn-ghost !py-1 text-xs" onClick={() => review(g.id, "dismissed")}>Dismiss</button></> :
                  <button className="btn-ghost !py-1 text-xs" onClick={() => review(g.id, "open")}>Reopen</button>}
              </div>)}
          </div>))}
      </div>
    </div>
  );
}
