import clsx from "clsx";
import { ShieldCheck } from "lucide-react";
import { useState } from "react";
import { Badge, ErrorBox, Hash, Loading, Section, statusTone } from "../../components/ui";
import { api } from "../../lib/api";
import { useAuth } from "../../lib/auth";
import { fmtDate, titleCase, useApi } from "../../lib/hooks";
import { SourceRef } from "../../components/EvidenceViewer";
import { useCase } from "./CaseWorkspace";

export default function AuditTab() {
  const { c } = useCase();
  const { can } = useAuth();
  const ev = useApi<any[]>(`/api/cases/${c.id}/evidence`);
  const log = useApi<any[]>(can("audit:view") ? `/api/cases/${c.id}/audit` : null);
  const [res, setRes] = useState<any>(null);
  return (
    <div className="space-y-4">
      <Section title="Evidence integrity" actions={<button className="btn-outline" onClick={async () => { setRes(await api.post(`/api/cases/${c.id}/verify-all`)); ev.reload(true); }}><ShieldCheck className="h-4 w-4" />Re-verify all</button>}>
        <p className="mb-3 text-xs text-slate-500">Each original is compared byte-for-byte (SHA-256) with the hash recorded at intake.</p>
        {res && <div className="mb-3 text-sm">{res.checked} checked · <b className="text-emerald-700">{res.results.filter((r: any) => r.result === "match").length} match</b> · <b className="text-rose-700">{res.results.filter((r: any) => r.result !== "match").length} mismatch/missing</b></div>}
        {ev.loading && !ev.data ? <Loading /> : (
          <div className="overflow-x-auto"><table className="w-full text-sm"><thead><tr className="label text-left"><th className="py-2">Code</th><th>File</th><th>SHA-256 at intake</th><th>Last check</th><th>Collected by / source</th></tr></thead>
            <tbody className="divide-y divide-slate-100">{ev.data?.map((e) => (
              <tr key={e.id} className={clsx(e.last_verification && e.last_verification !== "match" && "bg-rose-50")}>
                <td className="mono py-2">{e.code}</td><td className="max-w-[220px] truncate">{e.filename}</td><td><Hash value={e.sha256} /></td>
                <td><Badge tone={statusTone(e.last_verification)}>{e.last_verification || "—"}</Badge> <span className="text-xs text-slate-500">{fmtDate(e.last_verified_at)}</span></td>
                <td className="max-w-[260px] truncate text-xs text-slate-600">{e.collected_by || "—"} · {e.collection_source || <span className="text-amber-700">not recorded</span>}</td></tr>))}</tbody></table></div>)}
      </Section>
      <IntegrityFindings caseId={c.id} />
      {can("audit:view") && (
        <Section title="Case audit trail (append-only, hash-chained)">
          {log.error ? <ErrorBox error={log.error} /> : log.loading && !log.data ? <Loading /> : (
            <ol className="max-h-[520px] space-y-0 overflow-auto">{log.data?.map((a) => (
              <li key={a.id} className="grid grid-cols-[150px_1fr_auto] gap-3 border-b border-slate-100 py-2 text-sm">
                <span className="text-xs text-slate-500">{fmtDate(a.ts)}</span>
                <div className="min-w-0"><div className="font-medium">{titleCase(a.action.replace(/\./g, " "))} <span className="font-normal text-slate-500">· {a.user}</span></div>
                  <div className="truncate mono text-[11px] text-slate-500">{JSON.stringify(a.detail)}</div></div>
                <span title={`prev ${a.prev_hash}`}><Hash value={a.hash} /></span></li>))}</ol>)}
        </Section>)}
    </div>
  );
}


function IntegrityFindings({ caseId }: { caseId: string }) {
  const { data } = useApi<any[]>(`/api/cases/${caseId}/integrity-findings`);
  const [all, setAll] = useState(false);
  if (!data) return null;
  const shown = data.filter((f) => all || f.severity !== "info");
  return (
    <Section title={`Integrity inspection (${data.length} observations)`} actions={<label className="flex items-center gap-1 text-xs"><input type="checkbox" checked={all} onChange={(e) => setAll(e.target.checked)} />show informational</label>}>
      <div className="mb-3 grid gap-2 text-xs md:grid-cols-4">
        {[["File integrity since intake", "SHA-256 re-verification (above)"], ["Provenance at collection", "Who/when/how it was collected, as supplied"],
          ["Metadata observations", "What the file's own metadata says"], ["Potential anomalies", "Inconsistencies for a human to review"]].map(([t, d]) => (
          <div key={t} className="rounded-lg bg-slate-100 p-2"><div className="font-semibold text-slate-800">{t}</div><div className="text-slate-500">{d}</div></div>))}
      </div>
      {!shown.length ? <div className="text-sm text-slate-500">No anomalies flagged.</div> : (
        <table className="w-full text-sm"><thead><tr className="label text-left"><th className="py-1.5">Evidence</th><th>Check</th><th>Severity</th><th>Observation</th></tr></thead>
          <tbody className="divide-y divide-slate-200">{shown.map((f) => (
            <tr key={f.id}><td className="py-1.5"><SourceRef src={{ evidence_id: f.evidence_id, evidence_code: f.evidence_code, filename: f.filename }} /></td>
              <td className="text-xs">{titleCase(f.check)}</td>
              <td><Badge tone={f.severity === "high" ? "red" : f.severity === "medium" ? "amber" : "slate"}>{f.severity}</Badge></td>
              <td className="text-xs text-slate-700">{f.observation}</td></tr>))}</tbody></table>)}
      <p className="mt-2 text-[11px] text-slate-500">These are indicators for human review, not proof of tampering.</p>
    </Section>
  );
}
