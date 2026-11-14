import { ArrowRight, Bot, CheckCircle2, Circle, Pencil, UserPlus } from "lucide-react";
import { ct, t } from "../../lib/i18n";
import { useState } from "react";
import { Link } from "react-router-dom";
import { Badge, Modal, Section, Stat, VERDICT_LABEL, statusTone } from "../../components/ui";
import { api } from "../../lib/api";
import { fmtDate, titleCase, useApi } from "../../lib/hooks";
import { useCase } from "./CaseWorkspace";
import CaseTranslations from "../../components/CaseTranslations";

function EditCase({ c, onDone }: { c: any; onDone: () => void }) {
  const [f, setF] = useState({ title: c.title, description: c.description, objective: c.objective, priority: c.priority, status: c.status, default_timezone: c.default_timezone,
    translations: (c.translations || {}) as Record<string, Record<string, string>> });
  const [err, setErr] = useState<string | null>(null);
  const set = (k: string) => (e: any) => setF({ ...f, [k]: e.target.value });
  return (
    <form className="space-y-3" onSubmit={async (e) => { e.preventDefault(); try { await api.patch(`/api/cases/${c.id}`, f); onDone(); } catch (x: any) { setErr(x.message); } }}>
      <div><label className="label">Title</label><input className="input mt-1" value={f.title} onChange={set("title")} required minLength={3} /></div>
      <div><label className="label">Description</label><textarea className="input mt-1 min-h-[80px]" value={f.description} onChange={set("description")} /></div>
      <div><label className="label">Objective</label><textarea className="input mt-1 min-h-[60px]" value={f.objective} onChange={set("objective")} /></div>
      <CaseTranslations value={f.translations} onChange={(translations) => setF({ ...f, translations })} />
      <div className="grid grid-cols-3 gap-2">
        <div><label className="label">Priority</label><select className="input mt-1" value={f.priority} onChange={set("priority")}>{["low", "medium", "high", "critical"].map((p) => <option key={p}>{p}</option>)}</select></div>
        <div><label className="label">Status</label><select className="input mt-1" value={f.status} onChange={set("status")}>{["active", "completed", "archived"].map((p) => <option key={p}>{p}</option>)}</select></div>
        <div><label className="label">Timezone</label><select className="input mt-1" value={f.default_timezone} onChange={set("default_timezone")}>{["UTC", "+05:30", "+00:00", "+01:00", "+04:00", "+08:00", "-05:00", "-08:00", "unknown"].map((t) => <option key={t}>{t}</option>)}</select></div>
      </div>
      {err && <div className="text-sm text-rose-700">{err}</div>}
      <div className="flex justify-end"><button className="btn-primary">Save changes</button></div>
    </form>
  );
}

export default function OverviewTab() {
  const { c, reload, canWrite } = useCase();
  const history = useApi<any[]>(`/api/cases/${c.id}/history?limit=40`);
  const n = c.counts;
  const steps = [
    { done: n.evidence > 0, label: "Upload evidence", to: "evidence" },
    { done: n.entities > 0, label: "Run evidence processing", to: "processing" },
    { done: n.events > 0, label: "Review timeline & relationships", to: "timeline" },
    { done: n.contradictions_pending === 0 && n.contradictions > 0, label: "Review contradictions", to: "contradictions" },
    { done: !!c.verdict, label: "Run Challenge Engine", to: "challenge" },
    { done: false, label: "Generate evidence-linked report", to: "reports" },
  ];
  const [email, setEmail] = useState(""); const [access, setAccess] = useState("viewer"); const [msg, setMsg] = useState<string | null>(null);
  const [editing, setEditing] = useState(false); const [aiErr, setAiErr] = useState<string | null>(null);
  const isOwner = c.access === "owner";
  return (
    <div className="grid gap-4 xl:grid-cols-3">
      <div className="space-y-4 xl:col-span-2">
        <div className="grid grid-cols-2 gap-3 md:grid-cols-4">
          <Stat label="Evidence" value={n.evidence} /><Stat label="Entities" value={n.entities} /><Stat label="Timeline events" value={n.events} />
          <Stat label="Contradictions" value={n.contradictions} tone={n.contradictions ? "alert" : "default"} hint={`${n.contradictions_pending} awaiting review`} />
        </div>
        <Section title="Incident & objective" actions={canWrite && <button className="btn-ghost !py-1 text-xs" onClick={() => setEditing(true)}><Pencil className="h-3.5 w-3.5" />Edit case</button>}>
          <div className="space-y-3 text-sm"><div><div className="label mb-1">Description</div><p className="whitespace-pre-wrap text-slate-700">{ct(c, "description") || "—"}</p></div>
            <div><div className="label mb-1">Objective</div><p className="whitespace-pre-wrap text-slate-700">{ct(c, "objective") || "—"}</p></div>
            <div className="flex gap-6 text-xs text-slate-500"><span>Opened {fmtDate(c.created_at)}</span><span>Updated {fmtDate(c.updated_at)}</span></div></div>
        </Section>
        <Section title="Investigation workflow">
          <ol className="space-y-1">{steps.map((s, i) => (
            <li key={i}><Link to={`../${s.to}`} className="flex items-center gap-3 rounded-lg px-2 py-2 text-sm hover:bg-slate-50">
              {s.done ? <CheckCircle2 className="h-4 w-4 text-emerald-600" /> : <Circle className="h-4 w-4 text-slate-300" />}
              <span className={s.done ? "text-slate-500" : "font-medium"}>{s.label}</span><ArrowRight className="ml-auto h-3.5 w-3.5 text-slate-300" /></Link></li>))}</ol>
        </Section>
        <Section title="Case history">
          {!history.data?.length ? <div className="text-sm text-slate-500">No activity yet.</div> : (
            <ol className="max-h-72 space-y-1.5 overflow-auto">{history.data.map((h, i) => (
              <li key={i} className="flex gap-3 text-sm"><span className="w-36 shrink-0 text-xs text-slate-500">{fmtDate(h.ts)}</span>
                <span className="font-medium">{titleCase(h.action.replace(/\./g, " "))}</span><span className="text-xs text-slate-500">{h.user}</span></li>))}</ol>)}
        </Section>
      </div>
      <div className="space-y-4">
        <Section title="Current assessment">
          {c.verdict ? <><Badge tone={statusTone(c.verdict)} className="!text-sm">{VERDICT_LABEL[c.verdict]}</Badge>
            <p className="mt-2 text-xs text-slate-500">Engine verdict from the skeptical reviewer agent.</p>
            <Link to="../challenge" className="mt-3 inline-flex text-sm font-medium text-accent-700">Open Challenge Centre →</Link></>
            : <p className="text-sm text-slate-500">No adversarial review yet.</p>}
        </Section>
        <Section title={<span className="flex items-center gap-2"><Bot className="h-4 w-4" />External AI provider</span>}>
          
          <label className="mt-3 flex items-center gap-2 text-sm">
            <input type="checkbox" checked={c.allow_external_ai} disabled={!isOwner} onChange={async (e) => {
              setAiErr(null);
              try { await api.patch(`/api/cases/${c.id}`, { allow_external_ai: e.target.checked }); reload(true); } catch (x: any) { setAiErr(x.message); }
            }} />Authorise external AI for this case</label>
          {!isOwner && <div className="mt-1 text-[11px] text-slate-500">Only the case owner can change this.</div>}
          {aiErr && <div className="mt-1 text-xs text-rose-700">{aiErr}</div>}
        </Section>
        <Section title="Access & assignments">
          <ul className="space-y-2 text-sm">{c.members?.map((m: any) => (
            <li key={m.user_id} className="flex items-center justify-between"><div><div className="font-medium">{m.name}</div><div className="text-xs text-slate-500">{m.email}</div></div><Badge>{m.access}</Badge></li>))}</ul>
          {isOwner && (
            <form className="mt-4 space-y-2 border-t border-slate-100 pt-3" onSubmit={async (e) => {
              e.preventDefault(); setMsg(null);
              try { await api.post(`/api/cases/${c.id}/members`, { email, access }); setEmail(""); setMsg("Shared."); reload(true); } catch (e: any) { setMsg(e.message); }
            }}>
              <div className="label">Assign an investigator or reviewer</div>
              <div className="flex gap-2"><input className="input" placeholder="email" value={email} onChange={(e) => setEmail(e.target.value)} required />
                <select className="input !w-28" value={access} onChange={(e) => setAccess(e.target.value)}><option>viewer</option><option>editor</option><option>owner</option></select></div>
              <button className="btn-outline w-full justify-center"><UserPlus className="h-4 w-4" />Grant access</button>
              {msg && <div className="text-xs text-slate-600">{msg}</div>}
            </form>)}
        </Section>
      </div>
      <Modal open={editing} onClose={() => setEditing(false)} title="Edit case">
        <EditCase c={c} onDone={() => { setEditing(false); reload(true); history.reload(true); }} />
      </Modal>
    </div>
  );
}
