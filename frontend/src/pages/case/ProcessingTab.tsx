import clsx from "clsx";
import { motion } from "framer-motion";
import { Check, Loader2, Play, Swords, X } from "lucide-react";
import { useState } from "react";
import { Link } from "react-router-dom";
import { Badge, ErrorBox, Section, statusTone } from "../../components/ui";
import { api } from "../../lib/api";
import { fmtDate, titleCase, useApi, usePoll } from "../../lib/hooks";
import { useCase } from "./CaseWorkspace";
import { ConfidenceSummary } from "./ConfidenceTab";

export const PROCESSING_AGENTS = ["intake", "extraction", "entity_intelligence", "timeline", "relationship", "evidence_dna", "integrity_inspection", "message_classification", "message_authenticity", "contradiction", "evidence_gap", "confidence_report"];
export const ADVERSARIAL_AGENTS = ["investigation", "counter_investigation", "verification", "skeptical_review", "missing_evidence", "report"];
const LABEL: Record<string, string> = { intake: "Intake", extraction: "Extraction", entity_intelligence: "Entity Intelligence", timeline: "Timeline",
  relationship: "Relationship", evidence_dna: "Evidence DNA", integrity_inspection: "Integrity Inspection", contradiction: "Contradiction", evidence_gap: "Evidence Gap", message_classification: "Naive Bayes Labels", message_authenticity: "Message Check", confidence_report: "Confidence Report", investigation: "Investigation", missing_evidence: "Missing Evidence",
  counter_investigation: "Counter-Investigation", verification: "Verification", skeptical_review: "Skeptical Reviewer", report: "Report" };

export function AgentPipeline({ agents, run }: { agents: string[]; run: any }) {
  const done = new Map((run?.agents || []).map((a: any) => [a.agent, a]));
  return (
    <div className="flex flex-wrap items-center gap-y-3">
      {agents.map((a, i) => {
        const ex: any = done.get(a);
        const active = run?.status === "running" && run?.stage === a;
        const state = ex ? (ex.status === "failed" ? "failed" : "done") : active ? "active" : "idle";
        return (
          <div key={a} className="flex items-center">
            <motion.div layout className={clsx("flex items-center gap-2 rounded-lg border px-3 py-2 text-xs font-medium",
              state === "done" && "border-emerald-200 bg-emerald-50 text-emerald-800", state === "failed" && "border-rose-200 bg-rose-50 text-rose-700",
              state === "active" && "border-accent-500 bg-accent-50 text-accent-700 shadow-[0_0_0_3px_rgba(59,130,246,.15)]", state === "idle" && "border-slate-200 bg-surface text-slate-500")}>
              {state === "done" ? <Check className="h-3.5 w-3.5" /> : state === "failed" ? <X className="h-3.5 w-3.5" /> : state === "active" ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <span className="h-3.5 w-3.5 rounded-full border border-slate-300" />}
              <span>{LABEL[a]}</span>{ex && <span className="font-normal opacity-60">{ex.duration_ms} ms</span>}
            </motion.div>
            {i < agents.length - 1 && <div className={clsx("mx-1 h-px w-4", ex ? "bg-emerald-300" : "bg-slate-200")} />}
          </div>);
      })}
    </div>
  );
}

export default function ProcessingTab() {
  const { c, reload: reloadCase, canWrite } = useCase();
  const runs = useApi<any[]>(`/api/cases/${c.id}/runs`);
  const latest = runs.data?.find((r) => r.kind === "processing");
  const challenge = runs.data?.find((r) => r.kind === "adversarial");
  const hyprun = runs.data?.find((r) => r.kind === "hypotheses");
  const detail = useApi<any>(latest ? `/api/runs/${latest.id}` : null, [latest?.id]);
  const active = (runs.data || []).some((r) => r.status === "queued" || r.status === "running");
  // The chain (processing -> challenge -> hypotheses) starts each stage after the previous one ends; keep polling across the hand-over.
  const chainPending = latest?.status === "completed" && latest?.finished_at && (!hyprun || new Date(hyprun.started_at) < new Date(latest.started_at)) &&
    Date.now() - new Date(latest.finished_at).getTime() < 45000;
  usePoll(() => { runs.reload(true); detail.reload(true); }, active || !!chainPending, 1000);
  const [err, setErr] = useState<string | null>(null);
  const [wasActive, setWasActive] = useState(false);
  if (active !== wasActive) { setWasActive(active); if (!active) reloadCase(true); }

  const start = async () => {
    setErr(null);
    try { await api.post(`/api/cases/${c.id}/analyse`); runs.reload(true); } catch (e: any) { setErr(e.message); }
  };
  const r = detail.data;
  const extraction = r?.agents?.find((a: any) => a.agent === "extraction")?.output?.files || [];
  return (
    <div className="space-y-4">
      <Section title="Evidence processing pipeline" actions={canWrite && <button className="btn-primary" onClick={start} disabled={active || !c.counts.evidence}><Play className="h-4 w-4" />{latest ? "Re-run full analysis" : "Start full analysis"}</button>}>
        <StageStrip stages={[["Evidence processing", latest], ["Challenge engine", challenge], ["Hypothesis engine", hyprun]]} active={active} />
        <p className="mb-4 text-sm text-slate-500">Twelve agents run in sequence under LangGraph; the last one scores how reliable the output is.</p>
        <AgentPipeline agents={PROCESSING_AGENTS} run={r} />
        {!active && r?.status === "completed" && <FinalOutput caseId={c.id} key={(hyprun?.id || "") + (challenge?.id || "") + r.id} />}
        {r && (
          <div className="mt-4">
            <div className="mb-1 flex justify-between text-xs text-slate-500"><span>{r.status === "running" ? `Running: ${titleCase(r.stage)}` : `Last run ${fmtDate(r.finished_at || r.started_at)}`}</span><span>{Math.round(r.progress * 100)}%</span></div>
            <div className="h-1.5 overflow-hidden rounded-full bg-slate-100"><motion.div className="h-full bg-accent-500" animate={{ width: `${r.progress * 100}%` }} /></div>
            {r.error && <div className="mt-3"><ErrorBox error={r.error} /></div>}
          </div>)}
        {err && <div className="mt-3"><ErrorBox error={err} /></div>}
        {!active && r?.status === "completed" && (
          <div className="mt-4 flex flex-wrap gap-2"><Link to="../timeline" className="btn-outline">View timeline</Link><Link to="../graph" className="btn-outline">Relationships</Link>
            <Link to="../contradictions" className="btn-outline">Contradictions</Link><Link to="../challenge" className="btn-accent"><Swords className="h-4 w-4" />Run Challenge Engine</Link></div>)}
      </Section>
      {extraction.length > 0 && (
        <Section title="Extraction results by file">
          <div className="overflow-x-auto"><table className="w-full text-sm"><thead><tr className="label text-left"><th className="py-2">File</th><th>Status</th><th>Method</th><th>Segments</th><th>Notes</th></tr></thead>
            <tbody className="divide-y divide-slate-100">{extraction.map((f: any) => (
              <tr key={f.evidence_id}><td className="py-2 pr-3 font-medium">{f.file}</td><td><Badge tone={statusTone(f.status)}>{f.status}</Badge></td>
                <td className="mono text-slate-600">{f.method || "—"}</td><td className="tabular-nums">{f.segments ?? "—"}</td>
                <td className="max-w-md text-xs text-slate-500">{f.error || (f.warnings || []).join("; ")}</td></tr>))}</tbody></table></div>
        </Section>)}
      {r?.agents?.length > 0 && (
        <Section title="Agent outputs (structured JSON)">
          <div className="grid gap-3 md:grid-cols-2">{r.agents.filter((a: any) => a.agent !== "extraction").map((a: any) => (
            <details key={a.agent} className="rounded-lg border border-slate-200 p-3"><summary className="cursor-pointer text-sm font-medium">{LABEL[a.agent]} <span className="text-xs font-normal text-slate-500">· {a.mode} · {a.attempts} attempt(s)</span></summary>
              <pre className="mt-2 max-h-56 overflow-auto rounded bg-slate-50 p-2 mono text-[11px]">{JSON.stringify(a.output, null, 2)}</pre></details>))}</div>
        </Section>)}
      {r?.log?.length > 0 && (
        <Section title="Run log">
          <ol className="max-h-64 space-y-1 overflow-auto mono text-[11px] text-slate-600">{r.log.slice().reverse().map((l: any, i: number) => <li key={i}><span className="text-slate-400">{new Date(l.t).toLocaleTimeString()}</span> {l.msg}</li>)}</ol>
        </Section>)}
    </div>
  );
}

function StageStrip({ stages, active }: { stages: [string, any][]; active: boolean }) {
  return (
    <div className="mb-4 grid gap-2 sm:grid-cols-3">
      {stages.map(([name, run], i) => {
        const st = run?.status || (active ? "waiting" : "not run");
        return (
          <div key={name} className={clsx("border-2 border-ink-900 p-2.5", st === "completed" ? "bg-emerald-500 text-white" : st === "running" || st === "queued" ? "bg-acid" : st === "failed" ? "bg-rose-500 text-white" : "bg-surface")}>
            <div className="flex items-center gap-2 text-xs font-bold uppercase tracking-wide">
              <span className="flex h-5 w-5 items-center justify-center border-2 border-current text-[10px]">{i + 1}</span>{name}
              {(st === "running" || st === "queued") && <Loader2 className="ml-auto h-3.5 w-3.5 animate-spin" />}
              {st === "completed" && <Check className="ml-auto h-4 w-4" />}{st === "failed" && <X className="ml-auto h-4 w-4" />}
            </div>
            <div className="mt-1 text-[11px] opacity-90">{st === "running" ? `${titleCase(run.stage || "")} · ${Math.round((run.progress || 0) * 100)}%` : st}</div>
          </div>);
      })}
    </div>
  );
}

function FinalOutput({ caseId }: { caseId: string }) {
  const { c } = useCase();
  const hyp = useApi<any>(`/api/cases/${caseId}/hypothesis-lab`);
  const a = hyp.data?.analysis;
  const lead = a?.comparison?.[0];
  const tiles: [string, any, string][] = [["Timeline events", c.counts.events, "timeline"], ["Entities", c.counts.entities, "entities"],
    ["Contradictions", c.counts.contradictions, "contradictions"], ["Open gaps", c.counts.gaps_open, "gaps"]];
  return (
    <motion.div initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} className="mt-5 border-[3px] border-ink-900 bg-surface p-4 shadow-brutal">
      <div className="font-display text-xl uppercase">Final output</div>
      <div className="mt-3 grid gap-3 lg:grid-cols-[1fr_1fr]">
        <div className="grid grid-cols-2 gap-2">{tiles.map(([l, v, to]) => (
          <Link key={l} to={`../${to}`} className="border-2 border-ink-900 p-2 hover:bg-acid/40"><div className="font-display text-2xl">{v ?? 0}</div><div className="text-[11px] font-bold uppercase">{l}</div></Link>))}</div>
        <ConfidenceSummary caseId={caseId} />
      </div>
      {lead && (
        <Link to="../hypotheses" className="mt-3 block border-2 border-ink-900 bg-[#111827] p-3 text-slate-100 hover:bg-[#1e1b4b]">
          <div className="text-[11px] font-bold uppercase tracking-wider text-indigo-300">Hypothesis Lab · {a.hypotheses.length} explanations tested</div>
          <div className="mt-1 text-sm">Fits the evidence best: <b className="text-white">{lead.id} {lead.title}</b> ({lead.label_text})</div>
          <div className="text-xs text-slate-400">{a.review.statement}</div>
        </Link>)}
      <div className="mt-3 flex flex-wrap gap-2"><Link to="../timeline" className="btn-outline">Timeline</Link><Link to="../graph" className="btn-outline">Relationships</Link>
        <Link to="../authenticity" className="btn-outline">Message Check</Link><Link to="../challenge" className="btn-outline"><Swords className="h-4 w-4" />Challenge</Link>
        <Link to="../reports" className="btn-primary">Generate report</Link></div>
    </motion.div>
  );
}
