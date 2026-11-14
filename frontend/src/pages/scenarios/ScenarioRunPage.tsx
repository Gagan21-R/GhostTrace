import clsx from "clsx";
import { motion } from "framer-motion";
import { CheckCircle2, ChevronLeft, CircleDashed, FileText, Loader2, XCircle } from "lucide-react";
import { Link, useParams } from "react-router-dom";
import { Badge, ErrorBox, Loading, OutcomeBadge, Section } from "../../components/ui";
import { api } from "../../lib/api";
import { fmtDate, titleCase, useApi, usePoll } from "../../lib/hooks";

const STAGES = ["creating case", "ingesting evidence", "intake", "extraction", "entity_intelligence", "timeline", "relationship", "contradiction",
  "evidence_gap", "investigation", "counter_investigation", "verification", "skeptical_review", "report", "testing alternative hypotheses", "question_analyzer", "hypothesis_generator", "evidence_mapper", "counterevidence",
  "hypothesis_evaluator", "next_evidence_planner", "independent_reviewer", "evaluating against ground truth", "generating report", "done"];

const METRIC_ORDER = ["critical_findings", "all_findings", "contradiction_precision", "contradiction_recall", "entity_precision", "entity_recall", "entity_f1", "timestamp_accuracy",
  "timeline_order_accuracy", "ocr_char_similarity", "asr_similarity", "hash_verification_accuracy", "source_reference_coverage", "unsupported_claim_rate",
  "false_positive_count", "processing_time", "human_reviews_pending"];

export default function ScenarioRunPage() {
  const { runId } = useParams();
  const { data: r, error, loading, reload } = useApi<any>(`/api/scenarios/runs/${runId}`);
  const running = !!r && ["queued", "running"].includes(r.status);
  const trace = useApi<any>(`/api/scenarios/runs/${runId}/status`);
  const execs = useApi<any[]>(r?.case_id && !running ? `/api/cases/${r.case_id}/agent-executions` : null, [r?.case_id, running]);
  usePoll(() => { reload(true); trace.reload(true); }, running, 1000);
  if (loading && !r) return <Loading />;
  if (error) return <ErrorBox error={error} />;
  const ev = r.evaluation || {};
  const stageIdx = Math.max(0, STAGES.indexOf(r.stage));
  return (
    <div>
      <Link to={r.scenario_id === "custom-dataset" ? "/scenarios" : `/scenarios/${r.scenario_id}`} className="mb-2 inline-flex items-center gap-1 text-xs font-medium text-slate-500 hover:text-ink-900"><ChevronLeft className="h-3.5 w-3.5" />Back to scenario</Link>
      <div className="mb-5 flex flex-wrap items-end justify-between gap-3">
        <div><div className="label">Scenario test · {r.test_code}</div><h1 className="mt-1 text-[22px] font-semibold tracking-tight">{titleCase(r.scenario_id.replace(/^s\d+h?-/, ""))}</h1>
          <div className="mt-1 text-xs text-slate-500">Started {fmtDate(r.started_at)}{r.finished_at && ` · finished ${fmtDate(r.finished_at)}`}</div></div>
        <div className="flex gap-2">
          {r.case_id && <Link to={`/cases/${r.case_id}/overview`} className="btn-outline">Open case workspace</Link>}
          {r.report_id && <button className="btn-primary" onClick={async () => { const { url } = await api.blobUrl(`/api/scenarios/runs/${r.id}/report.pdf`); window.open(url, "_blank"); }}><FileText className="h-4 w-4" />Scenario report (PDF)</button>}
        </div>
      </div>

      {running && (
        <Section title={<span className="flex items-center gap-2"><Loader2 className="h-4 w-4 animate-spin" />Running through the shared investigation pipeline</span>}>
          <div className="mb-2 flex justify-between text-sm"><span className="font-medium">{titleCase(r.stage)}</span><span className="tabular-nums">{Math.round(r.progress * 100)}%</span></div>
          <div className="h-2 overflow-hidden rounded-full bg-slate-100"><motion.div className="h-full bg-accent-600" animate={{ width: `${r.progress * 100}%` }} /></div>
          <div className="mt-4 flex flex-wrap gap-1.5">{STAGES.slice(0, -1).map((st, i) => (
            <span key={st} className={clsx("chip border", i < stageIdx ? "border-emerald-200 bg-emerald-50 text-emerald-700" : i === stageIdx ? "border-accent-500 bg-accent-50 text-accent-700" : "border-slate-200 text-slate-400")}>{titleCase(st)}</span>))}</div>
          <p className="mt-3 text-xs text-slate-500">OCR and speech-to-text run on CPU, so image- and audio-heavy scenarios take about a minute.</p>
        </Section>)}

      {(trace.data?.agents?.length > 0) && (
        <Section title="Execution trace (recorded agent executions)" className="mb-4">
          <div className="flex flex-wrap gap-2">{trace.data.agents.map((a: any, i: number) => (
            <div key={i} className={clsx("rounded-lg border px-3 py-1.5 text-xs", a.status === "failed" ? "border-rose-200 bg-rose-50 text-rose-700" : "border-emerald-200 bg-emerald-50 text-emerald-800")}>
              <b>{titleCase(a.agent)}</b> · {a.duration_ms} ms<div className="text-[10px] opacity-70">{a.mode}</div></div>))}</div>
          {execs.data && (
            <div className="mt-3 grid gap-2 md:grid-cols-2">{execs.data.slice().reverse().filter((a) => a.agent !== "extraction").map((a) => (
              <details key={a.id} className="rounded-lg border border-slate-200 p-2"><summary className="cursor-pointer text-xs font-medium">{titleCase(a.agent)} output (JSON)</summary>
                <pre className="mt-1 max-h-52 overflow-auto rounded bg-slate-50 p-2 mono text-[10px]">{JSON.stringify(a.output, null, 2)}</pre></details>))}</div>)}
        </Section>)}

      {r.status === "failed" && <ErrorBox error={`Run failed: ${r.error}`} />}

      {r.status === "completed" && (
        <div className="space-y-4">
          <motion.div initial={{ opacity: 0, scale: 0.98 }} animate={{ opacity: 1, scale: 1 }} className="card grid overflow-hidden md:grid-cols-[260px_1fr]">
            <div className={clsx("flex flex-col items-center justify-center gap-2 p-6", r.outcome === "PASS" ? "bg-emerald-50" : r.outcome === "FAIL" ? "bg-rose-50" : "bg-amber-50")}>
              <OutcomeBadge outcome={r.outcome} size="xl" />
              {ev.expected_outcome && <div className="text-xs text-slate-600">Expected: <b>{ev.expected_outcome}</b> · {ev.outcome_matches_expected ? <span className="text-emerald-700">matches</span> : <span className="text-rose-700">does not match</span>}</div>}
            </div>
            <div className="p-5">
              <div className="label mb-1">Result</div><p className="text-sm text-slate-800">{r.outcome_reason}</p>
              <div className="mt-3 grid grid-cols-2 gap-2 text-xs sm:grid-cols-4">
                {Object.entries(ev.actual || {}).map(([k, v]) => <div key={k} className="rounded-lg bg-slate-50 p-2"><div className="text-slate-500">{titleCase(k)}</div><div className="font-semibold">{v === null ? "—" : titleCase(String(v))}</div></div>)}
              </div>
              <p className="mt-3 text-[11px] text-slate-500">PASS/FAIL/HOLD is computed deterministically from the ground truth below — not from an LLM opinion.</p>
            </div>
          </motion.div>

          <div className="grid grid-cols-2 gap-3 md:grid-cols-4 xl:grid-cols-8">
            {METRIC_ORDER.filter((k) => ev.metrics?.[k]).map((k) => (
              <div key={k} className="card p-3" title={ev.metrics[k].basis}><div className="label !text-[10px]">{titleCase(k)}</div>
                <div className="mt-1 text-lg font-semibold tabular-nums">{ev.metrics[k].display}</div><div className="mt-0.5 line-clamp-2 text-[10px] text-slate-500">{ev.metrics[k].basis}</div></div>))}
          </div>

          {ev.findings?.length > 0 && (
            <Section title="Expected vs actual findings">
              <table className="w-full text-sm"><thead><tr className="label text-left"><th className="py-2">ID</th><th>Expected finding</th><th>Type</th><th>Result</th><th className="hidden lg:table-cell">Matched by (engine output)</th></tr></thead>
                <tbody className="divide-y divide-slate-100">{ev.findings.map((f: any) => (
                  <tr key={f.id} className={clsx(f.status !== "found" && f.critical && "bg-rose-50")}>
                    <td className="mono py-2">{f.id}</td><td>{f.description} {f.critical && <Badge tone="red" className="ml-1">critical</Badge>}</td><td><Badge>{f.type}</Badge></td>
                    <td>{f.status === "found" ? <span className="flex items-center gap-1 text-emerald-700"><CheckCircle2 className="h-4 w-4" />Found</span> :
                      f.status === "blocked" ? <span className="flex items-center gap-1 text-amber-700"><CircleDashed className="h-4 w-4" />Engine unavailable</span> :
                      <span className="flex items-center gap-1 text-rose-700"><XCircle className="h-4 w-4" />Missed</span>}</td>
                    <td className="hidden max-w-md truncate text-xs text-slate-500 lg:table-cell" title={f.matched_by}>{f.matched_by || "—"}</td></tr>))}</tbody></table>
            </Section>)}

          {(ev.timestamp_checks?.length > 0 || ev.ambiguous_records?.length > 0 || ev.irrelevant_records?.length > 0) && (
            <div className="grid gap-4 lg:grid-cols-3">
              <Section title="Expected event timestamps">
                <ul className="space-y-1.5 text-xs">{(ev.timestamp_checks || []).map((t: any, i: number) => (
                  <li key={i} className="flex items-start gap-2">{t.found ? <CheckCircle2 className="h-3.5 w-3.5 shrink-0 text-emerald-600" /> : <XCircle className="h-3.5 w-3.5 shrink-0 text-rose-600" />}
                    <span><b>{t.file}</b> expected {t.expected}{t.actual?.length ? ` · found ${t.actual.join(", ")}` : ""}</span></li>))}</ul>
              </Section>
              <Section title="Irrelevant control records">
                {ev.irrelevant_records?.length ? <><ul className="space-y-1 text-xs">{ev.irrelevant_records.map((f: string) => <li key={f}>• {f}</li>)}</ul>
                  <p className="mt-2 text-[11px] text-slate-500">These must not be cited as support or linked into contradictions; any breach appears under rule violations.</p></>
                  : <div className="text-xs text-slate-500">None in this dataset.</div>}
              </Section>
              <Section title="Ambiguous records">
                <ul className="space-y-1.5 text-xs">{(ev.ambiguous_records || []).map((a: any, i: number) => (
                  <li key={i}><b>{a.file}</b>: {a.note} · {a.flagged_by_engine ? <span className="text-emerald-700">flagged by engine</span> : <span className="text-amber-700">not flagged</span>}</li>))}</ul>
              </Section>
            </div>)}

          <div className="grid gap-4 lg:grid-cols-3">
            <Section title={`False positives (${ev.false_positives?.length || 0})`}>{ev.false_positives?.length ? <ul className="space-y-1 text-sm">{ev.false_positives.map((f: any) => <li key={f.code}><span className="mono">{f.code}</span> {f.description}</li>)}</ul> : <div className="text-sm text-slate-500">None — every reported contradiction was expected or in an allowed category.</div>}</Section>
            <Section title="Rule violations">{ev.violations?.length ? <ul className="space-y-1 text-sm text-rose-700">{ev.violations.map((v: string, i: number) => <li key={i}>{v}</li>)}</ul> : <div className="text-sm text-slate-500">No forbidden findings, guilt statements or unsupported identity claims.</div>}</Section>
            <Section title="Recommended improvements">{ev.recommendations?.length ? <ul className="space-y-1 text-sm">{ev.recommendations.map((v: string, i: number) => <li key={i}>• {v}</li>)}</ul> : <div className="text-sm text-slate-500">None from this run.</div>}
              {ev.errors?.length > 0 && <div className="mt-2 text-xs text-rose-700">{ev.errors.join("; ")}</div>}</Section>
          </div>
          {r.case_id && (
            <div className="flex flex-wrap gap-2">{[["timeline", "Timeline"], ["graph", "Relationship graph"], ["contradictions", "Contradictions"], ["gaps", "Evidence gaps"], ["adversarial", "Agent debate"], ["evidence", "Evidence & extraction"]].map(([t, l]) => (
              <Link key={t} to={`/cases/${r.case_id}/${t}`} className="btn-outline">{l}</Link>))}</div>)}
        </div>)}
    </div>
  );
}
