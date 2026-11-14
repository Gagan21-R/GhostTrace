import clsx from "clsx";
import { Activity, Pause, Play, SkipBack } from "lucide-react";
import { useEffect, useMemo, useRef, useState } from "react";
import { Link } from "react-router-dom";
import { useEvidenceViewer } from "../../components/EvidenceViewer";
import { Badge, Empty, ErrorBox, Loading } from "../../components/ui";
import { titleCase, useApi } from "../../lib/hooks";
import { useCase } from "./CaseWorkspace";

const STAGE: Record<string, string> = {
  evidence_vault: "Intake", intake: "Intake", integrity: "Integrity", extraction: "Extraction", entity_intelligence: "Entities", timeline: "Timeline",
  relationship: "Relationships", evidence_dna: "Evidence DNA", integrity_inspection: "Integrity", contradiction: "Contradictions", evidence_gap: "Gaps",
  investigation: "Challenge", counter_investigation: "Challenge", verification: "Verification", skeptical_review: "Review", missing_evidence: "Recommendations",
  report: "Report", human_review: "Human review", whatif_lab: "What-If",
};

function RefLink({ r, caseId }: { r: any; caseId: string }) {
  const { open } = useEvidenceViewer();
  if (!r?.id) return r?.label ? <span className="text-xs text-slate-500">{r.label}</span> : null;
  const cls = "chip border border-slate-300 bg-slate-100 text-slate-700 hover:border-accent-500 hover:text-accent-700";
  if (r.type === "evidence") return <button className={cls} onClick={() => open(r.id)}>{r.label || "evidence"}</button>;
  if (r.type === "segment") return r.evidence_id ? <button className={cls} onClick={() => open(r.evidence_id, r.id)}>{r.label || "source"}</button> : null;
  const to: Record<string, string> = { contradiction: "contradictions", gap: "gaps", hypothesis: "challenge", dependency: "dna", integrity_finding: "audit",
    recommendation: "missing", whatif: "whatif", agent_execution: "processing" };
  if (r.type === "report") return <Link className={cls} to={`/reports/${r.id}`}>{r.label || "report"}</Link>;
  if (to[r.type]) return <Link className={cls} to={`/cases/${caseId}/${to[r.type]}`}>{r.label || r.type}</Link>;
  return <span className={cls}>{r.label || r.type}</span>;
}

export default function ReplayTab() {
  const { c } = useCase();
  const [component, setComponent] = useState("");
  const { data, error, loading } = useApi<any>(`/api/cases/${c.id}/replay?limit=2000${component ? `&component=${component}` : ""}`, [component]);
  const [pos, setPos] = useState(-1); const [playing, setPlaying] = useState(false);
  const refs = useRef<Record<number, HTMLLIElement | null>>({});
  const items: any[] = useMemo(() => data?.items || [], [data]);
  useEffect(() => {
    if (!playing) return;
    const t = setInterval(() => setPos((p) => { if (p + 1 >= items.length) { setPlaying(false); return p; } return p + 1; }), 650);
    return () => clearInterval(t);
  }, [playing, items.length]);
  useEffect(() => { refs.current[pos]?.scrollIntoView({ block: "nearest", behavior: "smooth" }); }, [pos]);
  if (loading && !data) return <Loading />;
  if (error) return <ErrorBox error={error} />;
  if (!data.total && !component) return <Empty title="Nothing to replay yet" hint="Upload and process evidence; every step is recorded here as it happens." icon={<Activity className="h-5 w-5" />} />;
  const shown = pos < 0 ? items : items.slice(0, pos + 1);
  return (
    <div className="grid gap-4 xl:grid-cols-[260px_1fr]">
      <div className="space-y-3">
        <div className="card space-y-3 p-4">
          <div className="label">Replay controls</div>
          <div className="flex gap-2">
            <button className="btn-primary flex-1 justify-center" onClick={() => { if (pos >= items.length - 1) setPos(-1); if (pos < 0) setPos(0); setPlaying(!playing); }}>
              {playing ? <><Pause className="h-4 w-4" />Pause</> : <><Play className="h-4 w-4" />{pos < 0 ? "Play from start" : "Resume"}</>}</button>
            <button className="btn-outline" title="Show all" onClick={() => { setPlaying(false); setPos(-1); }}><SkipBack className="h-4 w-4" /></button>
          </div>
          {pos >= 0 && <div className="text-xs text-slate-500">Step {pos + 1} of {items.length}</div>}
          <select className="input" value={component} onChange={(e) => { setComponent(e.target.value); setPos(-1); setPlaying(false); }}>
            <option value="">All components ({Object.values(data.components || {}).reduce((a: number, b: any) => a + b, 0)})</option>
            {Object.entries(data.components || {}).map(([k, v]: any) => <option key={k} value={k}>{titleCase(k)} ({v})</option>)}</select>
        </div>
        <div className="card p-4 text-xs text-slate-600">Every entry is a persisted record written by the component at the moment it acted - not a generated narrative. Click references to open the evidence, finding or result.</div>
      </div>
      <ol className="relative border-l-2 border-slate-200 pl-5">
        {shown.map((e: any, i: number) => (
          <li key={e.id} ref={(el) => (refs.current[i] = el)} className={clsx("relative mb-2 rounded-lg border p-3 transition",
            i === pos ? "border-accent-500 bg-accent-50" : "border-slate-200 bg-surface", e.status === "failed" && "border-rose-300", e.status === "warning" && "border-amber-300/60")}>
            <span className={clsx("absolute -left-[27px] top-4 h-3 w-3 rounded-full ring-4 ring-slate-50",
              e.status === "failed" ? "bg-rose-500" : e.status === "warning" ? "bg-amber-500" : "bg-accent-500")} />
            <div className="flex flex-wrap items-center gap-2 text-xs">
              <span className="mono text-slate-500">{new Date(e.ts).toLocaleTimeString()}</span>
              <Badge tone="blue">{STAGE[e.component] || titleCase(e.component)}</Badge>
              <span className="font-semibold text-slate-800">{e.action}</span>
              <span className="text-slate-500">by {e.actor}</span>
              {e.status !== "ok" && <Badge tone={e.status === "failed" ? "red" : "amber"}>{e.status}</Badge>}
            </div>
            <p className="mt-1 text-sm text-slate-700">{e.summary}</p>
            {(e.inputs.length > 0 || e.outputs.length > 0) && (
              <div className="mt-1.5 flex flex-wrap items-center gap-1.5 text-[11px]">
                {e.inputs.slice(0, 6).map((r: any, j: number) => <RefLink key={j} r={r} caseId={c.id} />)}
                {e.outputs.length > 0 && <span className="text-slate-400">→</span>}
                {e.outputs.slice(0, 6).map((r: any, j: number) => <RefLink key={j} r={r} caseId={c.id} />)}
              </div>)}
            {e.details && Object.keys(e.details).length > 0 && (
              <details className="mt-1"><summary className="cursor-pointer text-[11px] text-slate-500">details</summary>
                <pre className="mt-1 max-h-40 overflow-auto rounded bg-slate-100 p-2 mono text-[10px]">{JSON.stringify(e.details, null, 2)}</pre></details>)}
          </li>))}
      </ol>
    </div>
  );
}
