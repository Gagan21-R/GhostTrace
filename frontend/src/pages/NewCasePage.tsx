import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { PageHeader } from "../components/ui";
import { api } from "../lib/api";
import CaseTranslations from "../components/CaseTranslations";
import { t } from "../lib/i18n";

const TYPES = [["fraud", "Fraud / phishing"], ["account_compromise", "Account compromise"], ["harassment", "Harassment / preservation"],
  ["corporate", "Corporate misconduct"], ["commercial_dispute", "Commercial / delivery dispute"], ["general", "General"]];

export default function NewCasePage() {
  const nav = useNavigate();
  const [f, setF] = useState({ title: "", description: "", objective: "", case_type: "fraud", priority: "medium", default_timezone: "+05:30", translations: {} as Record<string, Record<string, string>> });
  const [err, setErr] = useState<string | null>(null); const [busy, setBusy] = useState(false);
  const set = (k: string) => (e: any) => setF({ ...f, [k]: e.target.value });
  const submit = async (e: React.FormEvent) => {
    e.preventDefault(); setBusy(true); setErr(null);
    try { const c = await api.post<any>("/api/cases", f); nav(`/cases/${c.id}/evidence`); }
    catch (e: any) { setErr(e.message); setBusy(false); }
  };
  return (
    <div className="max-w-3xl">
      <PageHeader eyebrow="Investigations" title="Open a new case" subtitle="You become the case owner." />
      <form onSubmit={submit} className="card space-y-4 p-6">
        <div><label className="label">{t("Case title")}</label><input className="input mt-1" value={f.title} onChange={set("title")} required minLength={3} placeholder="e.g. KYC phishing payment – complainant A. Rao" /></div>
        <div className="grid gap-4 sm:grid-cols-3">
          <div><label className="label">{t("Case type")}</label><select className="input mt-1" value={f.case_type} onChange={set("case_type")}>{TYPES.map(([v, l]) => <option key={v} value={v}>{t(l)}</option>)}</select></div>
          <div><label className="label">{t("Priority")}</label><select className="input mt-1" value={f.priority} onChange={set("priority")}>{["low", "medium", "high", "critical"].map((p) => <option key={p} value={p}>{t(p)}</option>)}</select></div>
          <div><label className="label">Default timezone</label><select className="input mt-1" value={f.default_timezone} onChange={set("default_timezone")}>
            {["UTC", "+05:30", "+00:00", "+01:00", "+04:00", "+08:00", "-05:00", "-08:00", "unknown"].map((t) => <option key={t}>{t}</option>)}</select>
            <div className="mt-1 text-[11px] text-slate-500">Applied only to timestamps that state no timezone, labelled as an assumption. Choose 'unknown' to keep the uncertainty.</div></div>
        </div>
        <div><label className="label">{t("Incident description")}</label><textarea className="input mt-1 min-h-[96px]" value={f.description} onChange={set("description")} /></div>
        <div><label className="label">{t("Investigation objective")}</label><textarea className="input mt-1 min-h-[72px]" value={f.objective} onChange={set("objective")} placeholder="What must the investigation establish?" /></div>
        <CaseTranslations value={f.translations} onChange={(translations) => setF({ ...f, translations })} />
        {err && <div className="rounded-lg bg-rose-50 px-3 py-2 text-sm text-rose-700">{err}</div>}
        <div className="flex justify-end gap-2"><button type="button" className="btn-ghost" onClick={() => nav(-1)}>Cancel</button><button className="btn-primary" disabled={busy}>Create case</button></div>
      </form>
    </div>
  );
}
