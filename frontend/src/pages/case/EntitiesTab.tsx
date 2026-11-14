import { Search, Users } from "lucide-react";
import { useMemo, useState } from "react";
import { SourceRef } from "../../components/EvidenceViewer";
import { Badge, Empty, ErrorBox, Loading } from "../../components/ui";
import { titleCase, useApi } from "../../lib/hooks";
import { useCase } from "./CaseWorkspace";
import { ENTITY_COLORS } from "./GraphTab";

export default function EntitiesTab() {
  const { c } = useCase();
  const { data, error, loading } = useApi<any[]>(`/api/cases/${c.id}/entities`);
  const [q, setQ] = useState(""); const [type, setType] = useState(""); const [open, setOpen] = useState<string | null>(null);
  const rows = useMemo(() => (data || []).filter((e) => (!type || e.type === type) && (!q || `${e.value} ${e.normalized}`.toLowerCase().includes(q.toLowerCase()))), [data, q, type]);
  if (loading && !data) return <Loading />;
  if (error) return <ErrorBox error={error} />;
  if (!data!.length) return <Empty title="No entities yet" hint="Run evidence processing to extract entities." icon={<Users className="h-5 w-5" />} />;
  const counts: Record<string, number> = data!.reduce((m: Record<string, number>, e) => ({ ...m, [e.type]: (m[e.type] || 0) + 1 }), {});
  return (
    <div>
      <div className="mb-3 flex flex-wrap gap-2">
        <div className="relative min-w-[240px] flex-1"><Search className="absolute left-3 top-2.5 h-4 w-4 text-slate-400" />
          <input className="input pl-9" placeholder="Search entities…" value={q} onChange={(e) => setQ(e.target.value)} /></div>
        <select className="input !w-auto" value={type} onChange={(e) => setType(e.target.value)}><option value="">All types ({data!.length})</option>
          {Object.entries(counts).sort().map(([t, n]) => <option key={t} value={t}>{titleCase(t)} ({n})</option>)}</select>
      </div>
      <div className="card overflow-x-auto"><table className="w-full text-sm">
        <thead className="bg-slate-100"><tr className="label text-left"><th className="px-4 py-2.5">Type</th><th>Value</th><th>Files</th><th>Mentions</th><th>Notes</th></tr></thead>
        <tbody className="divide-y divide-slate-200">{rows.map((e) => (
          <>
            <tr key={e.id} className="cursor-pointer hover:bg-slate-100" onClick={() => setOpen(open === e.id ? null : e.id)}>
              <td className="px-4 py-2"><span className="inline-flex items-center gap-2"><span className="h-2 w-2 rounded-full" style={{ background: ENTITY_COLORS[e.type] || "#64748b" }} />{titleCase(e.type)}</span></td>
              <td className="max-w-md break-all font-medium">{e.value}</td>
              <td className="tabular-nums">{(e.attributes?.sources || []).length}</td><td className="tabular-nums">{e.mentions.length}</td>
              <td className="space-x-1">{e.risk?.indicators?.length > 0 && <Badge tone="red">risk indicators</Badge>}
                {e.attributes?.chat_display_name && <Badge tone="amber">display name</Badge>}{e.attributes?.ner && <Badge>NER</Badge>}</td>
            </tr>
            {open === e.id && (
              <tr key={e.id + "-m"}><td colSpan={5} className="bg-slate-50 px-4 py-3">
                {e.risk?.indicators?.length > 0 && <div className="mb-2 text-xs text-rose-700">Indicators (signals, not proof): {e.risk.indicators.join("; ")}</div>}
                <ul className="space-y-1.5">{e.mentions.slice(0, 20).map((m: any, i: number) => (
                  <li key={i} className="flex gap-2 text-xs"><SourceRef src={m} /><span className="text-slate-600">{m.snippet}</span></li>))}</ul></td></tr>)}
          </>))}</tbody></table></div>
      <p className="mt-2 text-xs text-slate-500">Entities are normalised identifiers found in the evidence.</p>
    </div>
  );
}
