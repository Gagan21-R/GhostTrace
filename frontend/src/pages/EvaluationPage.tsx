import { BarChart3, Info } from "lucide-react";
import { useState } from "react";
import { Link } from "react-router-dom";
import { Badge, ErrorBox, Loading, OutcomeBadge, PageHeader, Section } from "../components/ui";
import { fmtDate, titleCase, useApi } from "../lib/hooks";

const SHOW = ["critical_findings", "contradiction_precision", "contradiction_recall", "entity_f1", "dependency_precision", "dependency_recall",
  "timestamp_accuracy", "timeline_order_accuracy", "ocr_char_similarity", "asr_similarity", "source_reference_coverage", "unsupported_claim_rate",
  "hash_verification_accuracy", "processing_time"];

export default function EvaluationPage() {
  const { data, error, loading } = useApi<any>("/api/evaluation/summary");
  const [def, setDef] = useState<string | null>(null);
  if (loading && !data) return <Loading />;
  if (error) return <ErrorBox error={error} />;
  const cellTone = (m: any, k: string) => {
    if (m.value === null || m.value === undefined) return "text-slate-500";
    if (k === "unsupported_claim_rate") return m.value === 0 ? "text-emerald-700" : "text-rose-700";
    if (typeof m.value === "number" && m.value <= 1 && !["processing_time"].includes(k)) return m.value >= 0.9 ? "text-emerald-700" : m.value >= 0.7 ? "text-amber-700" : "text-rose-700";
    return "text-slate-800";
  };
  return (
    <div>
      <PageHeader eyebrow="Evaluation & benchmarking" title="Ground-truth evaluation" subtitle="Latest completed Scenario Lab run per scenario, scored deterministically against its ground truth."
        actions={<Link to="/scenarios" className="btn-outline"><BarChart3 className="h-4 w-4" />Scenario Lab</Link>} />
      <div className="card overflow-x-auto">
        <table className="w-full text-sm">
          <thead className="bg-slate-100"><tr className="text-left">
            <th className="label px-3 py-2.5">Scenario</th><th className="label px-2">Result</th>
            {SHOW.map((k) => <th key={k} className="label cursor-help whitespace-nowrap px-2" title={data.definitions[k]} onClick={() => setDef(k)}>{titleCase(k).replace("Accuracy", "acc.").replace("Precision", "P").replace("Recall", "R")}</th>)}
          </tr></thead>
          <tbody className="divide-y divide-slate-200">{data.scenarios.map((s: any) => (
            <tr key={s.scenario_id}>
              <td className="px-3 py-2.5"><div className="font-medium">{s.title}</div><div className="text-xs text-slate-500">{s.test_code ? <Link className="hover:text-accent-700" to={`/scenarios/runs/${s.run_id}`}>{s.test_code} · {fmtDate(s.finished_at)}</Link> : "never run"}</div></td>
              <td className="px-2">{s.outcome === "NOT EVALUATED" ? <Badge>NOT EVALUATED</Badge> : <><OutcomeBadge outcome={s.outcome} /><div className="mt-0.5 text-[10px] text-slate-500">expected {s.expected_outcome}</div></>}</td>
              {SHOW.map((k) => { const m = s.metrics[k]; return <td key={k} className={`px-2 tabular-nums text-xs ${cellTone(m, k)}`} title={m.basis}>{m.display === "n/a" ? "NOT EVALUATED" : m.display}</td>; })}
            </tr>))}</tbody>
        </table>
      </div>
      <div className="mt-4 grid gap-4 lg:grid-cols-2">
        <Section title="Ground truth vs model confidence vs human review">
          <p className="mb-2 text-xs text-slate-500">Ground truth decides correctness.</p>
          <table className="w-full text-sm"><thead><tr className="label text-left"><th className="py-1">Scenario</th><th>Mean confidence (correct)</th><th>Mean confidence (false positive)</th><th>Human reviews agreeing</th></tr></thead>
            <tbody className="divide-y divide-slate-200">{data.scenarios.map((s: any) => (
              <tr key={s.scenario_id}><td className="py-1.5">{s.title}</td>
                <td className="tabular-nums">{s.model_confidence?.mean_confidence_correct ?? "NOT EVALUATED"}</td>
                <td className="tabular-nums">{s.model_confidence?.mean_confidence_false_positive ?? "none"}</td>
                <td className="tabular-nums">{s.human_review ? `${s.human_review.agree_with_ground_truth}/${s.human_review.reviewed}` : "NOT EVALUATED (no reviews)"}</td></tr>))}</tbody></table>
        </Section>
        <Section title={<span className="flex items-center gap-2"><Info className="h-4 w-4" />Metric definitions</span>}>
          <dl className="max-h-80 space-y-2 overflow-auto text-xs scrollbar-thin">{Object.entries(data.definitions).map(([k, v]: any) => (
            <div key={k} className={def === k ? "rounded bg-accent-50 p-1.5" : ""}><dt className="font-semibold text-slate-800">{titleCase(k)}</dt><dd className="text-slate-600">{v}</dd></div>))}</dl>
          
        </Section>
      </div>
    </div>
  );
}
