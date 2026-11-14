import { Link2, ShieldAlert, ShieldCheck } from "lucide-react";
import { ct, t } from "../lib/i18n";
import { useState } from "react";
import { Link } from "react-router-dom";
import { Badge, Hash, PageHeader, Section } from "../components/ui";
import { api } from "../lib/api";
import { useApi } from "../lib/hooks";

export default function AuditPage() {
  const [chain, setChain] = useState<any>(null); const [busy, setBusy] = useState(false);
  const cases = useApi<any[]>("/api/cases?include_scenarios=true");
  return (
    <div>
      <PageHeader eyebrow="Audit & Integrity" title="Audit trail and evidence integrity"
        subtitle="Every intake, access, processing step, review decision and export is written to an append-only log." />
      <div className="grid gap-4 lg:grid-cols-2">
        <Section title="Audit chain verification">
          <div className="flex items-center gap-4">
            <div className="rounded-xl bg-slate-100 p-3"><Link2 className="h-6 w-6 text-slate-600" /></div>
            <div className="flex-1 text-sm text-slate-600">Recompute every entry's SHA-256 from its content and its predecessor's hash.</div>
            <button className="btn-primary" disabled={busy} onClick={async () => { setBusy(true); try { setChain(await api.get("/api/audit/verify")); } finally { setBusy(false); } }}>Verify chain</button>
          </div>
          {chain && (
            <div className={`mt-4 rounded-lg border p-3 text-sm ${chain.valid ? "border-emerald-200 bg-emerald-50 text-emerald-800" : "border-rose-200 bg-rose-50 text-rose-800"}`}>
              <div className="flex items-center gap-2 font-medium">{chain.valid ? <ShieldCheck className="h-4 w-4" /> : <ShieldAlert className="h-4 w-4" />}
                {chain.valid ? `Chain intact: ${chain.checked} entries verified` : `Chain broken at entry #${chain.broken_at} after ${chain.checked} valid entries`}</div>
              {chain.head && <div className="mt-1 text-xs">Head hash <Hash value={chain.head} /></div>}
            </div>)}
        </Section>
        <Section title="What integrity verification shows">
          <ul className="space-y-2 text-sm text-slate-700">
            <li>• <b>SHA-256 match:</b> the stored file is byte-identical to the one received at intake.</li>
            <li>• It does <b>not</b> prove the file was genuine or unaltered before it reached GhostTrace.</li>
            <li>• It does <b>not</b> by itself establish legal admissibility or chain-of-custody compliance.</li>
            <li>• Hashing, verification and access checks are deterministic code; no LLM is involved.</li>
          </ul>
        </Section>
      </div>
      <Section title="Per-case integrity & audit" className="mt-4">
        <ul className="divide-y divide-slate-100">{(cases.data || []).map((c) => (
          <li key={c.id}><Link to={`/cases/${c.id}/audit`} className="flex items-center gap-3 py-2.5 text-sm hover:text-accent-700">
            <span className="mono text-slate-500">{c.case_number}</span><span className="flex-1 truncate font-medium">{ct(c, "title")}</span>
            {c.is_scenario && <Badge tone="violet">scenario</Badge>}<Badge>{c.counts.evidence} items</Badge></Link></li>))}</ul>
      </Section>
    </div>
  );
}
