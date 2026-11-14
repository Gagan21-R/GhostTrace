import { ChevronLeft, GitCompare } from "lucide-react";
import { useState } from "react";
import { Link } from "react-router-dom";
import { Bar, BarChart, CartesianGrid, Legend, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { Badge, Empty, ErrorBox, Loading, OutcomeBadge, PageHeader, Section, statusTone } from "../../components/ui";
import { fmtDate, titleCase, useApi } from "../../lib/hooks";

const CMP = ["contradiction_precision", "contradiction_recall", "entity_f1", "timeline_order_accuracy", "ocr_char_similarity", "source_reference_coverage", "hash_verification_accuracy"];
const COLORS = ["#0b0b0b", "#2b4bff", "#ff4f1f", "#a855f7", "#14b8a6", "#e4ff3a"];

export default function ScenarioHistory() {
  const { data, error, loading } = useApi<any[]>("/api/scenarios/runs");
  const [sel, setSel] = useState<string[]>([]);
  const cmp = useApi<any>(sel.length >= 2 ? `/api/scenarios/runs/compare?ids=${sel.join(",")}` : null, [sel.join(",")]);
  if (loading && !data) return <Loading />;
  if (error) return <ErrorBox error={error} />;
  const chart = cmp.data ? CMP.map((k) => ({ metric: titleCase(k).replace("Accuracy", "Acc."), ...Object.fromEntries(cmp.data.runs.map((r: any, i: number) => [r.test_code, cmp.data.metrics[k]?.[i] != null ? Math.round(cmp.data.metrics[k][i] * 1000) / 10 : null])) })) : [];
  return (
    <div>
      <Link to="/scenarios" className="mb-2 inline-flex items-center gap-1 text-xs font-medium text-slate-500 hover:text-ink-900"><ChevronLeft className="h-3.5 w-3.5" />Scenario Lab</Link>
      <PageHeader title="Scenario test results" subtitle="Every completed run is stored. Select two or more runs to compare their measured metrics." />
      {!data!.length ? <Empty title="No scenario runs yet" action={<Link to="/scenarios" className="btn-primary">Open Scenario Lab</Link>} /> : (
        <>
          {cmp.data && (
            <Section title={<span className="flex items-center gap-2"><GitCompare className="h-4 w-4" />Run comparison (%)</span>} className="mb-4">
              <div className="h-72"><ResponsiveContainer><BarChart data={chart} margin={{ left: -10 }}><CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#d6cfbd" />
                <XAxis dataKey="metric" tick={{ fontSize: 10 }} interval={0} /><YAxis domain={[0, 100]} tick={{ fontSize: 10 }} /><Tooltip /><Legend wrapperStyle={{ fontSize: 12 }} />
                {cmp.data.runs.map((r: any, i: number) => <Bar key={r.id} dataKey={r.test_code} fill={COLORS[i % COLORS.length]} radius={[3, 3, 0, 0]} />)}</BarChart></ResponsiveContainer></div>
              <div className="mt-2 flex flex-wrap gap-3 text-xs">{cmp.data.runs.map((r: any) => <span key={r.id}>{r.test_code}: <OutcomeBadge outcome={r.outcome} /> {(r.duration_ms / 1000).toFixed(1)} s</span>)}</div>
            </Section>)}
          <div className="card overflow-x-auto"><table className="w-full text-sm">
            <thead className="bg-slate-50"><tr className="label text-left"><th className="px-3 py-2.5"></th><th>Test</th><th>Scenario</th><th>Outcome</th><th>Expected</th><th>Critical</th><th>Contradiction P/R</th><th>Duration</th><th>Started</th></tr></thead>
            <tbody className="divide-y divide-slate-100">{data!.map((r) => (
              <tr key={r.id} className="hover:bg-slate-50">
                <td className="px-3"><input type="checkbox" checked={sel.includes(r.id)} disabled={r.status !== "completed"} onChange={(e) => setSel(e.target.checked ? [...sel, r.id].slice(-6) : sel.filter((x) => x !== r.id))} /></td>
                <td className="py-2"><Link to={`/scenarios/runs/${r.id}`} className="mono font-medium hover:text-accent-700">{r.test_code}</Link></td>
                <td>{r.scenario_title}</td><td>{r.status === "completed" ? <OutcomeBadge outcome={r.outcome} /> : <Badge tone={statusTone(r.status)}>{r.status}</Badge>}</td>
                <td>{r.expected_outcome || "—"} {r.outcome_matches_expected === false && <Badge tone="red">mismatch</Badge>}</td>
                <td className="tabular-nums">{r.metrics?.critical_findings ?? "—"}</td>
                <td className="tabular-nums text-xs">{r.metrics?.contradiction_precision != null ? `${Math.round(r.metrics.contradiction_precision * 100)}%` : "—"} / {r.metrics?.contradiction_recall != null ? `${Math.round(r.metrics.contradiction_recall * 100)}%` : "—"}</td>
                <td className="tabular-nums">{(r.duration_ms / 1000).toFixed(1)} s</td><td className="text-xs text-slate-500">{fmtDate(r.started_at)}</td></tr>))}</tbody></table></div>
        </>)}
    </div>
  );
}
