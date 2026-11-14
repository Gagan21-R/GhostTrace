import { FlaskConical, Plus, Search } from "lucide-react";
import { useState } from "react";
import { Link } from "react-router-dom";
import { Badge, Empty, ErrorBox, Loading, PageHeader, VERDICT_LABEL, statusTone } from "../components/ui";
import { fmtDate, titleCase, useApi } from "../lib/hooks";

export default function CasesPage() {
  const [q, setQ] = useState(""); const [status, setStatus] = useState(""); const [scen, setScen] = useState(false);
  const qs = new URLSearchParams({ ...(q && { q }), ...(status && { status }), include_scenarios: String(scen) });
  const { data, error, loading, reload } = useApi<any[]>(`/api/cases?${qs}`, []);
  return (
    <div>
      <PageHeader eyebrow="Investigations" title="Cases" subtitle="Each case keeps its own evidence, findings and access list."
        actions={<Link to="/cases/new" className="btn-primary"><Plus className="h-4 w-4" />New case</Link>} />
      <div className="mb-4 flex flex-wrap gap-2">
        <div className="relative min-w-[240px] flex-1"><Search className="absolute left-3 top-2.5 h-4 w-4 text-slate-400" />
          <input className="input pl-9" placeholder="Search title, number, description…" value={q} onChange={(e) => setQ(e.target.value)} /></div>
        <select className="input !w-auto" value={status} onChange={(e) => setStatus(e.target.value)}>
          <option value="">All statuses</option><option value="active">Active</option><option value="completed">Completed</option><option value="archived">Archived</option></select>
        <label className="btn-outline cursor-pointer"><input type="checkbox" checked={scen} onChange={(e) => setScen(e.target.checked)} /><FlaskConical className="h-4 w-4" />Include Scenario Lab cases</label>
      </div>
      {loading && !data ? <Loading /> : error ? <ErrorBox error={error} onRetry={reload} /> : data!.length === 0 ? (
        <Empty title="No cases match" hint="Create a case to start collecting evidence." action={<Link to="/cases/new" className="btn-primary">Create case</Link>} />
      ) : (
        <div className="card overflow-hidden">
          <table className="w-full text-sm">
            <thead className="bg-slate-50 text-left"><tr className="label">
              <th className="px-4 py-2.5">Case</th><th className="hidden px-4 md:table-cell">Type</th><th className="px-4">Evidence</th>
              <th className="hidden px-4 lg:table-cell">Findings</th><th className="hidden px-4 lg:table-cell">Reviewer verdict</th><th className="px-4">Status</th><th className="hidden px-4 md:table-cell">Updated</th></tr></thead>
            <tbody className="divide-y divide-slate-100">
              {data!.map((c) => (
                <tr key={c.id} className="hover:bg-slate-50/70">
                  <td className="px-4 py-3"><Link to={`/cases/${c.id}`} className="font-medium text-ink-900 hover:text-accent-700">{c.title}</Link>
                    <div className="mono text-slate-500">{c.case_number}{c.is_scenario && <Badge tone="violet" className="ml-2">scenario</Badge>}</div></td>
                  <td className="hidden px-4 text-slate-600 md:table-cell">{titleCase(c.case_type)}</td>
                  <td className="px-4 tabular-nums">{c.counts.evidence}</td>
                  <td className="hidden px-4 lg:table-cell"><div className="flex gap-1.5">
                    <Badge tone={c.counts.contradictions ? "red" : "slate"}>{c.counts.contradictions} conflicts</Badge>
                    <Badge tone={c.counts.gaps_open ? "amber" : "slate"}>{c.counts.gaps_open} gaps</Badge></div></td>
                  <td className="hidden px-4 lg:table-cell">{c.verdict ? <Badge tone={statusTone(c.verdict)}>{VERDICT_LABEL[c.verdict] || c.verdict}</Badge> : <span className="text-slate-400">—</span>}</td>
                  <td className="px-4"><Badge tone={statusTone(c.status)}>{c.status}</Badge></td>
                  <td className="hidden px-4 text-slate-500 md:table-cell">{fmtDate(c.updated_at)}</td>
                </tr>))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
