import clsx from "clsx";
import { Copy, Dna, GitBranch, Layers, Link2, Split } from "lucide-react";
import { useState } from "react";
import { SourceRef } from "../../components/EvidenceViewer";
import { Badge, Empty, ErrorBox, Loading, Section, Stat } from "../../components/ui";
import { titleCase, useApi } from "../../lib/hooks";
import { useCase } from "./CaseWorkspace";

export const REL: Record<string, { label: string; tone: string; icon: any; note: string }> = {
  duplicate: { label: "Duplicated", tone: "red", icon: Copy, note: "Byte-identical copy. Counts once." },
  near_duplicate: { label: "Near-duplicate", tone: "red", icon: Layers, note: "Same content in another copy or format. Counts once." },
  derived: { label: "Derived", tone: "amber", icon: GitBranch, note: "One contains the other (forward, quote, embedded). Counts once." },
  shared_source: { label: "Shared source", tone: "violet", icon: Split, note: "Same issuer; corroborating but not independent of each other." },
  independent: { label: "Independent", tone: "green", icon: Link2, note: "Different issuers agree on a shared identifier." },
  uncertain: { label: "Uncertain", tone: "slate", icon: Link2, note: "Shared identifiers; source relationship unknown." },
};

export default function DnaTab() {
  const { c } = useCase();
  const { data, error, loading } = useApi<any>(`/api/cases/${c.id}/dna`);
  const [rel, setRel] = useState(""); const [sel, setSel] = useState<string | null>(null);
  if (loading && !data) return <Loading />;
  if (error) return <ErrorBox error={error} />;
  if (!data.dependencies.length && !data.shared_identifiers.length)
    return <Empty title="No cross-file relationships yet" hint="Run evidence processing; Evidence DNA compares every pair of files." icon={<Dna className="h-5 w-5" />} />;
  const deps = data.dependencies.filter((d: any) => !rel || d.relation === rel);
  const s = data.summary;
  return (
    <div className="space-y-4">
      <div className="grid grid-cols-2 gap-3 md:grid-cols-4">
        <Stat label="Evidence items" value={s.evidence} />
        <Stat label="Independent source groups" value={s.independent_source_groups} hint="copies and derivatives collapse into one" tone="ok" />
        <Stat label="Dependent pairs" value={(s.by_relation.duplicate || 0) + (s.by_relation.near_duplicate || 0) + (s.by_relation.derived || 0) + (s.by_relation.shared_source || 0)} tone="warn" />
        <Stat label="Shared identifiers" value={data.shared_identifiers.length} />
      </div>
      <div className="grid gap-4 xl:grid-cols-[1.25fr_1fr]">
        <Section title="Evidence dependencies" actions={
          <select className="input !w-auto !py-1 text-xs" value={rel} onChange={(e) => setRel(e.target.value)}>
            <option value="">All relations</option>{Object.entries(REL).map(([k, v]) => <option key={k} value={k}>{v.label} ({s.by_relation[k] || 0})</option>)}</select>}>
          <ul className="space-y-2">{deps.map((d: any) => { const R = REL[d.relation]; return (
            <li key={d.id} className={clsx("rounded-lg border p-3", sel === d.id ? "border-accent-500 bg-accent-50" : "border-slate-200")}>
              <button className="w-full text-left" onClick={() => setSel(sel === d.id ? null : d.id)}>
                <div className="flex flex-wrap items-center gap-2 text-sm">
                  <span className="mono font-semibold">{d.a.code}</span><R.icon className="h-4 w-4 text-slate-500" /><span className="mono font-semibold">{d.b.code}</span>
                  <Badge tone={R.tone}>{R.label}</Badge>{d.direction && <span className="text-xs text-slate-500">{d.direction}</span>}
                  <span className="ml-auto text-xs text-slate-500">confidence {Math.round(d.confidence * 100)}%</span></div>
                <div className="mt-1 truncate text-xs text-slate-500">{d.a.filename} · {d.b.filename}</div>
                <p className="mt-1.5 text-sm text-slate-700">{d.explanation}</p></button>
              {sel === d.id && d.matches.length > 0 && (
                <table className="mt-2 w-full text-xs"><thead><tr className="label text-left"><th className="py-1">Matched attribute</th><th>Value</th><th>Source A</th><th>Source B</th></tr></thead>
                  <tbody className="divide-y divide-slate-200">{d.matches.map((m: any, i: number) => (
                    <tr key={i}><td className="py-1.5">{m.attribute}</td><td className="mono">{m.value}</td><td><SourceRef src={{ ...m.a, evidence_code: d.a.code }} /></td>
                      <td><SourceRef src={{ ...m.b, evidence_code: d.b.code }} /></td></tr>))}</tbody></table>)}
            </li>); })}</ul>
          
        </Section>
        <div className="space-y-4">
          <Section title="Independent source groups">
            <p className="mb-2 text-xs text-slate-500">Files grouped with their copies and derivatives.</p>
            <ul className="space-y-1.5">{data.source_groups.map((g: any[], i: number) => (
              <li key={i} className="flex flex-wrap items-center gap-1.5 rounded-lg bg-slate-100 px-2.5 py-1.5 text-xs">
                <span className="mr-1 font-semibold text-slate-500">S{i + 1}</span>{g.map((e) => <span key={e.id} className="mono" title={e.filename}>{e.code}</span>)}
                {g.length > 1 && <Badge tone="amber" className="ml-auto">{g.length} copies → 1 source</Badge>}</li>))}</ul>
          </Section>
          <Section title="Shared identifiers (fingerprint)">
            <ul className="max-h-[520px] space-y-2 overflow-auto scrollbar-thin">{data.shared_identifiers.map((x: any, i: number) => (
              <li key={i} className="rounded-lg border border-slate-200 p-2.5">
                <div className="flex flex-wrap items-center gap-2 text-sm"><Badge tone={x.strength === "strong" ? "blue" : "slate"}>{titleCase(x.attribute)}</Badge>
                  <span className="mono break-all">{x.value}</span>
                  <span className="ml-auto text-xs text-slate-500">{x.files} files · <b className={x.independent_sources < x.files ? "text-amber-700" : "text-emerald-700"}>{x.independent_sources} independent</b></span></div>
                <div className="mt-1.5 flex flex-wrap gap-1">{x.occurrences.map((o: any, j: number) => <SourceRef key={j} src={o} />)}</div></li>))}</ul>
          </Section>
        </div>
      </div>
    </div>
  );
}
