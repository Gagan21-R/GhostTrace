import { Download, FileText, Loader2 } from "lucide-react";
import { useState } from "react";
import { Link } from "react-router-dom";
import { Badge, Empty, ErrorBox, Hash, Loading, Section, VERDICT_LABEL } from "../../components/ui";
import { api } from "../../lib/api";
import { useAuth } from "../../lib/auth";
import { fmtDate, useApi } from "../../lib/hooks";
import { useCase } from "./CaseWorkspace";

export function ReportList({ reports }: { reports: any[] }) {
  const [opening, setOpening] = useState<string | null>(null);
  return (
    <div className="card divide-y divide-slate-100">
      {reports.map((r) => (
        <div key={r.id} className="flex flex-wrap items-center gap-3 px-4 py-3">
          <FileText className="h-5 w-5 text-slate-400" />
          <div className="min-w-0 flex-1"><div className="font-medium">{r.title}</div>
            <div className="mt-0.5 flex flex-wrap gap-2 text-xs text-slate-500"><span>{fmtDate(r.created_at)}</span><Badge tone={r.kind === "scenario" ? "violet" : "blue"}>{r.kind}</Badge>
              {r.redacted && <Badge tone="amber">redacted</Badge>}{r.verdict && <Badge>{VERDICT_LABEL[r.verdict]}</Badge>}<span>SHA-256 <Hash value={r.sha256} /></span></div></div>
          <Link to={`/reports/${r.id}`} className="btn-outline">Preview</Link>
          <button className="btn-ghost" disabled={opening === r.id} onClick={async () => {
            setOpening(r.id); try { const { url } = await api.blobUrl(`/api/reports/${r.id}/pdf`); window.open(url, "_blank"); } finally { setOpening(null); } }}>
            {opening === r.id ? <Loader2 className="h-4 w-4 animate-spin" /> : <FileText className="h-4 w-4" />}Open</button>
          <button className="btn-ghost !px-2 text-xs" title="Download PDF" onClick={() => api.download(`/api/reports/${r.id}/pdf`, `EVIDENCE-X_report_${r.id.slice(0, 8)}.pdf`)}><Download className="h-4 w-4" />PDF</button>
          <button className="btn-ghost !px-2 text-xs" title="Download DOCX" onClick={() => api.download(`/api/reports/${r.id}/docx`, `EVIDENCE-X_report_${r.id.slice(0, 8)}.docx`)}>DOCX</button>
          <button className="btn-ghost !px-2 text-xs" title="Download HTML" onClick={() => api.download(`/api/reports/${r.id}/html`, `EVIDENCE-X_report_${r.id.slice(0, 8)}.html`)}>HTML</button>
        </div>))}
    </div>
  );
}

export default function ReportsTab() {
  const { c } = useCase();
  const { can } = useAuth();
  const { data, error, loading, reload } = useApi<any[]>(`/api/reports?case_id=${c.id}`);
  const [redact, setRedact] = useState(false); const [busy, setBusy] = useState(false); const [err, setErr] = useState<string | null>(null);
  return (
    <div className="space-y-4">
      {can("report:generate") && (
        <Section title="Generate evidence-linked report">
          <p className="mb-3 text-sm text-slate-600">The PDF covers case information, evidence inventory with SHA-256 hashes, entities, chronology, relationships, contradictions, gaps, the adversarial assessment, reviewer findings, unresolved questions, next actions and source references. Engine interpretations and human decisions are labelled separately.</p>
          <div className="flex flex-wrap items-center gap-3">
            <label className="flex items-center gap-2 text-sm"><input type="checkbox" checked={redact} onChange={(e) => setRedact(e.target.checked)} />Redact personal identifiers (emails, phone and account digits) for sharing</label>
            <button className="btn-primary ml-auto" disabled={busy} onClick={async () => { setBusy(true); setErr(null); try { await api.post(`/api/cases/${c.id}/reports`, { redact }); reload(true); } catch (e: any) { setErr(e.message); } finally { setBusy(false); } }}>
              {busy ? <Loader2 className="h-4 w-4 animate-spin" /> : <FileText className="h-4 w-4" />}Generate PDF</button>
          </div>
          {err && <div className="mt-2"><ErrorBox error={err} /></div>}
        </Section>)}
      {loading && !data ? <Loading /> : error ? <ErrorBox error={error} /> : !data!.length ? <Empty title="No reports yet" /> : <ReportList reports={data!} />}
    </div>
  );
}
