import { useState } from "react";
import { Badge, PageHeader, Section } from "../components/ui";
import { api } from "../lib/api";
import { useAuth } from "../lib/auth";
import { fmtDate } from "../lib/hooks";

export default function ProfilePage() {
  const { user, permissions } = useAuth();
  const [name, setName] = useState(user?.full_name || ""); const [nameMsg, setNameMsg] = useState<string | null>(null);
  const [cur, setCur] = useState(""); const [nw, setNw] = useState(""); const [pwMsg, setPwMsg] = useState<{ ok: boolean; t: string } | null>(null);
  return (
    <div className="max-w-3xl">
      <PageHeader eyebrow="Account" title="Your profile" />
      <div className="space-y-4">
        <Section title="Profile">
          <div className="mb-3 grid gap-1 text-sm"><div><span className="text-slate-500">Email</span> · {user?.email}</div>
            <div><span className="text-slate-500">Role</span> · <Badge tone="dark">{user?.role}</Badge></div>
            <div><span className="text-slate-500">Member since</span> · {fmtDate(user?.created_at)}</div></div>
          <form className="flex gap-2" onSubmit={async (e) => { e.preventDefault(); try { await api.patch("/api/auth/me", { full_name: name }); setNameMsg("Saved. Reload to update the sidebar."); } catch (x: any) { setNameMsg(x.message); } }}>
            <input className="input" value={name} onChange={(e) => setName(e.target.value)} minLength={2} required /><button className="btn-primary">Save name</button></form>
          {nameMsg && <div className="mt-2 text-xs text-slate-600">{nameMsg}</div>}
        </Section>
        <Section title="Change password">
          <form className="grid gap-2 sm:grid-cols-[1fr_1fr_auto]" onSubmit={async (e) => {
            e.preventDefault(); setPwMsg(null);
            try { await api.post("/api/auth/me/password", { current_password: cur, new_password: nw }); setCur(""); setNw(""); setPwMsg({ ok: true, t: "Password changed." }); }
            catch (x: any) { setPwMsg({ ok: false, t: x.message }); }
          }}>
            <input className="input" type="password" placeholder="Current password" value={cur} onChange={(e) => setCur(e.target.value)} required autoComplete="current-password" />
            <input className="input" type="password" placeholder="New password" value={nw} onChange={(e) => setNw(e.target.value)} required minLength={10} autoComplete="new-password" />
            <button className="btn-primary">Change</button>
          </form>
          <div className="mt-1 text-[11px] text-slate-500">At least 10 characters with an uppercase letter and a digit.</div>
          {pwMsg && <div className={`mt-2 text-sm ${pwMsg.ok ? "text-emerald-700" : "text-rose-700"}`}>{pwMsg.t}</div>}
        </Section>
        <Section title="Your permissions">
          <div className="flex flex-wrap gap-1.5">{permissions.length ? permissions.map((p) => <Badge key={p}>{p}</Badge>) : <span className="text-sm text-slate-500">Read-only access to cases shared with you.</span>}</div>
        </Section>
      </div>
    </div>
  );
}
