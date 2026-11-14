import { SearchCheck } from "lucide-react";
import { useState } from "react";
import { Link } from "react-router-dom";
import { Badge, Empty, ErrorBox, Loading } from "../../components/ui";
import { api } from "../../lib/api";
import { useAuth } from "../../lib/auth";
import { titleCase, useApi } from "../../lib/hooks";
import { useCase } from "./CaseWorkspace";

const WEIGHTS: Record<string, number> = { importance: 0.3, discrimination: 0.25, relevance: 0.2, information_value: 0.15, availability: 0.1 };

export default function MissingEvidenceTab() {
  const { c } = useCase();
  const { can } = useAuth();
  const { data, error, loading, setData } = useApi<any[]>(`/api/cases/${c.id}/recommendations`);
  const [open, setOpen] = useState<string | null>(null);
  if (loading && !data) return <Loading />;
  if (error) return <ErrorBox error={error} />;
  if (!data!.length) return <Empty title="No recommendations yet" icon={<SearchCheck className="h-5 w-5" />}
    hint={<>The Missing Evidence Predictor runs as part of the Challenge Engine. <Link to="../challenge" className="text-accent-700">Open Challenge Centre</Link>.</>} />;
  const setStatus = async (id: string, status: string) => {
    await api.patch(`/api/recommendations/${id}`, { status });
    setData(data!.map((r) => (r.id === id ? { ...r, status } : r)));
  };
  return (
    <div>
      <div className="card mb-4 p-4 text-sm text-slate-600">
        <b className="text-slate-800">What should be collected next?</b> Each recommendation answers an unresolved question. The ranking is explainable:
        score = {Object.entries(WEIGHTS).map(([k, w], i) => <span key={k}>{i ? " + " : " "}{w}×{titleCase(k)}</span>)}.
        Recommendations name lawful, authorised sources only and never assume the record exists.
      </div>
      <ol className="space-y-3">{data!.map((r) => (
        <li key={r.id} className="card overflow-hidden">
          <button className="flex w-full items-start gap-4 p-4 text-left" onClick={() => setOpen(open === r.id ? null : r.id)}>
            <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg bg-accent-50 text-sm font-bold text-accent-700">#{r.rank}</div>
            <div className="min-w-0 flex-1">
              <div className="font-medium text-slate-900">{r.question}</div>
              <div className="mt-1 text-sm text-slate-600"><b className="text-slate-700">Collect:</b> {r.recommended_evidence}</div>
            </div>
            <div className="w-28 shrink-0 text-right"><div className="text-lg font-semibold tabular-nums">{r.score.toFixed(2)}</div>
              <div className="mt-1 h-1.5 overflow-hidden rounded-full bg-slate-200"><div className="h-full bg-accent-500" style={{ width: `${r.score * 100}%` }} /></div>
              <Badge tone={r.status === "collected" ? "green" : r.status === "requested" ? "amber" : "slate"} className="mt-2">{r.status.replace("_", " ")}</Badge></div>
          </button>
          {open === r.id && (
            <div className="grid gap-4 border-t border-slate-200 p-4 text-sm md:grid-cols-2">
              <div className="space-y-2">
                <div><div className="label">Why it matters</div><p className="text-slate-700">{r.why_it_matters}</p></div>
                <div><div className="label">Could confirm</div><p className="text-slate-700">{r.could_confirm}</p></div>
                <div><div className="label">Could disprove</div><p className="text-slate-700">{r.could_disprove}</p></div>
                <div><div className="label">Authorised source</div><p className="text-slate-700">{r.authorised_source}</p></div>
                <div><div className="label">Limitations</div><p className="text-slate-600">{r.limitations}</p></div>
              </div>
              <div className="space-y-3">
                <div><div className="label mb-1">Competing explanations it distinguishes</div>
                  <ul className="space-y-1">{r.distinguishes.map((d: string, i: number) => <li key={i} className="text-xs text-slate-700">• {d}</li>)}</ul></div>
                <div><div className="label mb-1">Score breakdown</div>
                  {Object.entries(r.score_breakdown).map(([k, v]: any) => (
                    <div key={k} className="flex items-center gap-2 text-xs"><span className="w-32 text-slate-500">{titleCase(k)} ×{WEIGHTS[k]}</span>
                      <div className="h-1.5 flex-1 overflow-hidden rounded-full bg-slate-200"><div className="h-full bg-accent-500" style={{ width: `${v * 100}%` }} /></div>
                      <span className="w-8 text-right tabular-nums">{v}</span></div>))}</div>
                <div className="text-xs text-slate-500">Linked: {Object.entries(r.linked).map(([k, v]) => `${k} ${v}`).join(", ")}</div>
                {can("review:decide") && (
                  <div className="flex flex-wrap gap-2 pt-1">{["requested", "collected", "not_available", "open"].map((s) => (
                    <button key={s} className="btn-outline !py-1 text-xs" disabled={r.status === s} onClick={() => setStatus(r.id, s)}>Mark {s.replace("_", " ")}</button>))}</div>)}
              </div>
            </div>)}
        </li>))}</ol>
    </div>
  );
}
