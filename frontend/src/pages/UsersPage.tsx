import { Badge, ErrorBox, Loading, PageHeader, Section } from "../components/ui";
import { api } from "../lib/api";
import { useAuth } from "../lib/auth";
import { fmtDate, useApi } from "../lib/hooks";

const ROLE_INFO: Record<string, string> = {
  admin: "Everything, across all cases, including user management and retention.",
  investigator: "Create cases, upload evidence, run analysis, review findings and generate reports on cases shared with them.",
  reviewer: "Review contradictions, gaps and hypotheses and generate reports on shared cases.",
  viewer: "Read-only access to cases shared with them.",
};

export default function UsersPage() {
  const { user, can } = useAuth();
  const { data, error, loading, reload } = useApi<any[]>(can("user:manage") ? "/api/users" : null);
  if (!can("user:manage")) return <ErrorBox error="You need the admin role to manage users." />;
  return (
    <div>
      <PageHeader eyebrow="Administration" title="Users & access" subtitle="Roles grant capabilities; access to each case is granted separately by its owner. Users never see cases they are not members of." />
      <div className="grid gap-4 xl:grid-cols-[1fr_340px]">
        {loading && !data ? <Loading /> : error ? <ErrorBox error={error} /> : (
          <div className="card overflow-x-auto"><table className="w-full text-sm">
            <thead className="bg-slate-50"><tr className="label text-left"><th className="px-4 py-2.5">User</th><th>Role</th><th>Status</th><th>Last login</th><th></th></tr></thead>
            <tbody className="divide-y divide-slate-100">{data!.map((u) => (
              <tr key={u.id}><td className="px-4 py-2.5"><div className="font-medium">{u.full_name}</div><div className="text-xs text-slate-500">{u.email}</div></td>
                <td><select className="input !w-36 !py-1" value={u.role} disabled={u.id === user?.id} onChange={async (e) => { await api.patch(`/api/users/${u.id}`, { role: e.target.value }); reload(true); }}>
                  {Object.keys(ROLE_INFO).map((r) => <option key={r}>{r}</option>)}</select></td>
                <td><Badge tone={u.is_active ? "green" : "slate"}>{u.is_active ? "active" : "disabled"}</Badge></td>
                <td className="text-xs text-slate-500">{fmtDate(u.last_login_at)}</td>
                <td className="pr-4 text-right">{u.id !== user?.id && <button className="btn-ghost !py-1 text-xs" onClick={async () => { await api.patch(`/api/users/${u.id}`, { is_active: !u.is_active }); reload(true); }}>{u.is_active ? "Disable" : "Enable"}</button>}</td></tr>))}</tbody></table></div>)}
        <Section title="Roles">
          <ul className="space-y-3 text-sm">{Object.entries(ROLE_INFO).map(([r, d]) => <li key={r}><Badge tone="dark">{r}</Badge><p className="mt-1 text-slate-600">{d}</p></li>)}</ul>
        </Section>
      </div>
    </div>
  );
}
