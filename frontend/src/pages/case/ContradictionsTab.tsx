import clsx from "clsx";
import { ArrowLeftRight, Check, GitCompareArrows, X } from "lucide-react";
import { useState } from "react";
import { SourceRef } from "../../components/EvidenceViewer";
import { Badge, Confidence, Empty, ErrorBox, Loading, statusTone } from "../../components/ui";
import { api } from "../../lib/api";
import { useAuth } from "../../lib/auth";
import { titleCase, useApi } from "../../lib/hooks";
import { useCase } from "./CaseWorkspace";

export default function ContradictionsTab() {
  const { c, reload: reloadCase } = useCase();
  const { can } = useAuth();
  const { data, error, loading, reload, setData } = useApi<any[]>(`/api/cases/${c.id}/contradictions`);
  const [filter, setFilter] = useState("all");
  const [notes, setNotes] = useState<Record<string, string>>({});
  const [prio, setPrio] = useState("all");
  if (loading && !data) return <Loading />;
  if (error) return <ErrorBox error={error} onRetry={reload} />;
  if (!data!.length) return <Empty title="No contradictions detected" hint="Contradictions are only reported between records linked by a shared order, transaction, amount, person or event. Run processing first if you have not." icon={<GitCompareArrows className="h-5 w-5" />} />;
  const review = async (id: string, status: string) => {
    const r = await api.patch<any>(`/api/contradictions/${id}`, { status, note: notes[id] || null });
    setData(data!.map((x) => (x.id === id ? r : x))); reloadCase(true);
  };
  const shown = data!.filter((x) => (filter === "all" || x.review_status === filter) && (prio === "all" || x.priority === prio));
  return (
    <div>
      <div className="mb-4 flex flex-wrap items-center gap-2">
        {["all", "pending", "confirmed", "dismissed"].map((f) => (
          <button key={f} onClick={() => setFilter(f)} className={clsx("chip border px-3 py-1", filter === f ? "border-ink-900 bg-accent-600 text-white" : "border-slate-200 bg-surface text-slate-600")}>
            {titleCase(f)} · {f === "all" ? data!.length : data!.filter((x) => x.review_status === f).length}</button>))}
        <select className="input !w-auto !py-1 text-xs" value={prio} onChange={(e) => setPrio(e.target.value)}>
          <option value="all">All priorities</option><option value="high">High</option><option value="medium">Medium</option><option value="low">Low</option></select>
        <span className="ml-auto text-xs text-slate-500">Engine findings. Confirm or dismiss each after checking both sources.</span>
      </div>
      <div className="space-y-4">
        {shown.map((x) => (
          <div key={x.id} className={clsx("card overflow-hidden", x.review_status === "dismissed" && "opacity-60")}>
            <div className="flex flex-wrap items-center gap-2 border-b border-slate-100 px-4 py-3">
              <span className="mono font-semibold text-ink-900">{x.code}</span>
              <Badge tone={x.priority === "high" ? "dark" : x.priority === "medium" ? "amber" : "slate"}>{x.priority} priority</Badge>
              <Badge tone={x.classification === "direct" ? "red" : x.classification === "contextual" ? "violet" : "amber"}>{x.classification} contradiction</Badge>
              <Badge>{titleCase(x.category)}</Badge>
              <span className="text-sm font-medium">{x.description}</span>
              <div className="ml-auto flex items-center gap-3"><Confidence value={x.confidence} /><Badge tone={statusTone(x.review_status)}>{x.review_status}</Badge></div>
            </div>
            <div className="grid md:grid-cols-[1fr_auto_1fr]">
              {[x.source_a, x.source_b].map((s: any, i: number) => (
                <div key={i} className={clsx("p-4", i === 0 ? "bg-slate-50/60" : "bg-surface")}>
                  <div className="mb-2 flex items-center justify-between"><span className="label">Source {i ? "B" : "A"}</span><SourceRef src={s} /></div>
                  <div className="text-xs text-slate-500">{s.filename}</div>
                  <div className="mt-2 rounded-md border-l-4 border-rose-400 bg-surface px-3 py-2 text-sm text-slate-800 shadow-sm">{s.excerpt}</div>
                  <div className="mt-2 text-xs"><span className="label">Value</span> <span className="mono ml-1 rounded bg-rose-50 px-1.5 py-0.5 text-rose-800">{String(s.value)}</span></div>
                </div>))}
              <div className="hidden items-center justify-center border-x border-slate-100 px-2 md:flex"><ArrowLeftRight className="h-4 w-4 text-rose-500" /></div>
            </div>
            <div className="grid gap-4 border-t border-slate-100 p-4 text-sm md:grid-cols-3">
              <div><div className="label mb-1">Why they conflict</div><p className="text-slate-700">{x.reason}</p></div>
              <div><div className="label mb-1">Why they are linked</div><p className="text-slate-700">{x.same_event_basis}</p></div>
              <div><div className="label mb-1">Verify by</div><p className="text-slate-700">{x.suggested_action}</p></div>
            </div>
            {can("review:decide") && (
              <div className="flex flex-wrap items-center gap-2 border-t border-slate-100 bg-slate-50/60 px-4 py-3">
                <input className="input !py-1.5 flex-1" placeholder="Reviewer note (recorded in the audit log)" value={notes[x.id] ?? x.reviewer_note ?? ""} onChange={(e) => setNotes({ ...notes, [x.id]: e.target.value })} />
                <button className="btn-ok !py-1.5" onClick={() => review(x.id, "confirmed")}><Check className="h-4 w-4" />Confirm</button>
                <button className="btn-no !py-1.5" onClick={() => review(x.id, "dismissed")}><X className="h-4 w-4" />Reject</button>
                {x.review_status !== "pending" && <button className="btn-ghost !py-1.5 text-xs" onClick={() => review(x.id, "pending")}>Reset</button>}
              </div>)}
          </div>))}
      </div>
    </div>
  );
}
