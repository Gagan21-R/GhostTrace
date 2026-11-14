import clsx from "clsx";
import { ArrowRight, FlaskRound, GitFork, Loader2, Trash2 } from "lucide-react";
import { useState } from "react";
import { SourceRef } from "../../components/EvidenceViewer";
import { Badge, Empty, ErrorBox, Loading, Section } from "../../components/ui";
import { api } from "../../lib/api";
import { useAuth } from "../../lib/auth";
import { useApi, usePoll } from "../../lib/hooks";
import { useCase } from "./CaseWorkspace";

const TYPES: Record<string, string> = {
  exclude_evidence: "This evidence item is unrelated / unreliable",
  timestamp_override: "A timestamp is wrong or unknown",
  unlink_identifier: "A record does not refer to an order / transaction",
  different_sender: "The email was forwarded; the original sender differs",
  same_source: "Two records come from one source",
  narrative: "Other assumption (recorded, not computable)",
};

function Hypo() {
  return <span className="rounded bg-violet-600 px-1.5 py-0.5 text-[10px] font-bold tracking-wider text-white">HYPOTHETICAL</span>;
}

function NewScenario({ cid, parent, onCreated }: { cid: string; parent: any | null; onCreated: (id: string) => void }) {
  const ev = useApi<any[]>(`/api/cases/${cid}/evidence`);
  const [type, setType] = useState("exclude_evidence");
  const [f, setF] = useState<Record<string, string>>({});
  const [title, setTitle] = useState("");
  const [err, setErr] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const segs = useApi<any>(type === "timestamp_override" && f.evidence_id ? `/api/cases/${cid}/extracted-data?evidence_id=${f.evidence_id}&limit=200` : null, [type, f.evidence_id]);
  const evSel = (k: string, label: string) => (
    <div><label className="label">{label}</label><select className="input mt-1" value={f[k] || ""} onChange={(e) => setF({ ...f, [k]: e.target.value })}>
      <option value="">Select evidence…</option>{(ev.data || []).map((e) => <option key={e.id} value={e.id}>{e.code} · {e.filename}</option>)}</select></div>);
  const submit = async () => {
    setErr(null); setBusy(true);
    const a: any = { type };
    if (type === "exclude_evidence") a.evidence_id = f.evidence_id;
    if (type === "timestamp_override") { a.segment_id = f.segment_id; a.value = f.value || null; a.label = f.label; }
    if (type === "unlink_identifier") { a.evidence_id = f.evidence_id; a.value = f.value; }
    if (type === "different_sender") { a.evidence_id = f.evidence_id; a.sender = f.sender; }
    if (type === "same_source") { a.evidence_a = f.evidence_a; a.evidence_b = f.evidence_b; }
    if (type === "narrative") a.note = f.note;
    try {
      const r = await api.post<any>(`/api/cases/${cid}/whatif`, { title: title || TYPES[type], parent_id: parent?.id || null, assumption: a });
      setF({}); setTitle(""); onCreated(r.id);
    } catch (e: any) { setErr(e.message); } finally { setBusy(false); }
  };
  return (
    <div className="space-y-3">
      {parent && <div className="rounded-lg bg-violet-50 px-3 py-2 text-xs text-violet-800">Branching from “{parent.title}” - its assumptions are kept and this one is added.</div>}
      <div><label className="label">Assumption</label><select className="input mt-1" value={type} onChange={(e) => { setType(e.target.value); setF({}); }}>
        {Object.entries(TYPES).map(([k, v]) => <option key={k} value={k}>{v}</option>)}</select></div>
      {["exclude_evidence", "unlink_identifier", "different_sender", "timestamp_override"].includes(type) && evSel("evidence_id", "Evidence")}
      {type === "timestamp_override" && f.evidence_id && (
        <div><label className="label">Segment</label><select className="input mt-1" value={f.segment_id || ""} onChange={(e) => {
          const s = segs.data?.items.find((x: any) => x.segment_id === e.target.value); setF({ ...f, segment_id: e.target.value, label: s ? `${s.evidence_code} ${s.locator}` : "" }); }}>
          <option value="">Select segment…</option>{(segs.data?.items || []).map((s: any) => <option key={s.segment_id} value={s.segment_id}>{s.locator} · {s.text.slice(0, 70)}</option>)}</select>
          <input className="input mt-2" placeholder="Correct time (e.g. 2026-03-12 09:47) - leave empty for 'unknown'" value={f.value || ""} onChange={(e) => setF({ ...f, value: e.target.value })} /></div>)}
      {type === "unlink_identifier" && <input className="input" placeholder="Identifier the record does NOT refer to, e.g. OD-48213" value={f.value || ""} onChange={(e) => setF({ ...f, value: e.target.value })} />}
      {type === "different_sender" && <input className="input" placeholder="Original sender address" value={f.sender || ""} onChange={(e) => setF({ ...f, sender: e.target.value })} />}
      {type === "same_source" && <>{evSel("evidence_a", "Record A")}{evSel("evidence_b", "Record B")}</>}
      {type === "narrative" && <textarea className="input min-h-[70px]" placeholder="e.g. The account was used by a family member" value={f.note || ""} onChange={(e) => setF({ ...f, note: e.target.value })} />}
      <input className="input" placeholder="Scenario title (optional)" value={title} onChange={(e) => setTitle(e.target.value)} />
      {err && <div className="text-sm text-rose-700">{err}</div>}
      <button className="btn-accent w-full justify-center" disabled={busy} onClick={submit}>{busy ? <Loader2 className="h-4 w-4 animate-spin" /> : <FlaskRound className="h-4 w-4" />}Simulate in sandbox</button>
      <p className="text-[11px] text-slate-500">The case is copied into an isolated sandbox, the assumption is applied there, and the analysis is re-run. Nothing is written to the real case.</p>
    </div>
  );
}

function Result({ id, onBranch, onDiscard }: { id: string; onBranch: (w: any) => void; onDiscard: () => void }) {
  const { can } = useAuth();
  const { data: w, reload } = useApi<any>(`/api/whatif/${id}`, [id]);
  usePoll(() => reload(true), !!w && ["queued", "running"].includes(w.status), 1000);
  if (!w) return <Loading />;
  if (w.status === "failed") return <ErrorBox error={`Simulation failed: ${w.error}`} />;
  if (w.status !== "completed") return <Loading label="Re-running the analysis in the sandbox" />;
  const r = w.result, ch = r.changes;
  return (
    <div className="space-y-4">
      <div className="card border-violet-300 p-4" style={{ backgroundImage: "repeating-linear-gradient(135deg, rgba(139,92,246,.06) 0 12px, transparent 12px 24px)" }}>
        <div className="flex flex-wrap items-center gap-2"><Hypo /><h3 className="font-semibold">{w.title}</h3>
          <div className="ml-auto flex gap-2">{can("analysis:run") && <><button className="btn-outline !py-1 text-xs" onClick={() => onBranch(w)}><GitFork className="h-3.5 w-3.5" />Branch</button>
            <button className="btn-ghost !py-1 text-xs" onClick={async () => { await api.post(`/api/whatif/${w.id}/discard`); onDiscard(); }}><Trash2 className="h-3.5 w-3.5" />Discard</button></>}</div></div>
        <ul className="mt-2 space-y-0.5 text-sm text-slate-700">{r.assumptions_described.map((a: string, i: number) => <li key={i}>• What if {a}?</li>)}</ul>
        {r.not_computable.length > 0 && <p className="mt-2 text-xs text-amber-700">Recorded but not computable (no records change): {r.not_computable.join("; ")}</p>}
      </div>
      <div className="grid gap-3 md:grid-cols-3">
        <div className="card p-4"><div className="label">Reviewer decision</div>
          <div className="mt-2 flex items-center gap-2 text-sm"><Badge>{ch.decision.from || "—"}</Badge><ArrowRight className="h-4 w-4 text-slate-400" />
            <Badge tone={ch.decision.changed ? "violet" : "slate"}>{ch.decision.to}</Badge></div>
          <div className="mt-1 text-xs text-slate-500">{ch.decision.changed ? "Changes under this assumption" : "Unchanged under this assumption"}</div></div>
        <div className="card p-4"><div className="label">Leading hypothesis</div><div className="mt-2 text-sm">{ch.pattern.to?.replace(/_/g, " ") || "none"}</div>
          {ch.pattern.changed && <div className="text-xs text-violet-700">was {ch.pattern.from?.replace(/_/g, " ")}</div>}</div>
        <div className="card p-4"><div className="label">Independent supporting sources</div><div className="mt-2 text-sm">{ch.independent_sources.from ?? "—"} → {ch.independent_sources.to ?? "—"}</div></div>
      </div>
      <div className="grid gap-4 lg:grid-cols-2">
        <Section title={<span className="flex items-center gap-2">Contradictions <Hypo /></span>}>
          {!ch.contradictions_added.length && !ch.contradictions_removed.length && <div className="text-sm text-slate-500">No change.</div>}
          {ch.contradictions_removed.map((x: string, i: number) => <div key={i} className="text-sm text-emerald-700">− {x}</div>)}
          {ch.contradictions_added.map((x: string, i: number) => <div key={i} className="text-sm text-rose-700">+ {x}</div>)}
        </Section>
        <Section title={<span className="flex items-center gap-2">Evidence gaps <Hypo /></span>}>
          {!ch.gaps_added.length && !ch.gaps_removed.length && <div className="text-sm text-slate-500">No change.</div>}
          {ch.gaps_removed.map((x: string, i: number) => <div key={i} className="text-sm text-emerald-700">− {x}</div>)}
          {ch.gaps_added.map((x: string, i: number) => <div key={i} className="text-sm text-rose-700">+ {x}</div>)}
        </Section>
      </div>
      <div className="grid gap-4 lg:grid-cols-2">
        <Section title="Evidence supporting the hypothesis under this assumption">
          <ul className="space-y-2">{r.supporting_under_assumption.map((s: any, i: number) => (
            <li key={i} className="text-sm"><Badge tone={s.status === "verified" ? "green" : "amber"}>{s.status}</Badge> {s.text}
              <div className="mt-1 flex flex-wrap gap-1">{s.sources.filter(Boolean).map((x: any, j: number) => <SourceRef key={j} src={x} />)}</div></li>))}</ul>
        </Section>
        <Section title="Evidence challenging it">
          <ul className="space-y-2">{r.challenging_under_assumption.map((s: any, i: number) => (
            <li key={i} className="text-sm"><Badge>{s.kind.replace(/_/g, " ")}</Badge> {s.text}
              <div className="mt-1 flex flex-wrap gap-1">{s.sources.filter(Boolean).map((x: any, j: number) => <SourceRef key={j} src={x} />)}</div></li>))}</ul>
        </Section>
      </div>
      <Section title="What would resolve this scenario">
        <ol className="space-y-1">{r.would_resolve.map((x: any) => <li key={x.rank} className="text-sm text-slate-700">{x.rank}. {x.question} <span className="text-xs text-slate-500">(score {x.score})</span></li>)}</ol>
      </Section>
    </div>
  );
}

export default function WhatIfTab() {
  const { c } = useCase();
  const { can } = useAuth();
  const list = useApi<any[]>(`/api/cases/${c.id}/whatif`);
  const [sel, setSel] = useState<string | null>(null);
  const [parent, setParent] = useState<any>(null);
  const [cmp, setCmp] = useState<string[]>([]);
  const compare = useApi<any>(cmp.length >= 2 ? `/api/cases/${c.id}/whatif-compare?ids=${cmp.join(",")}` : null, [cmp.join(",")]);
  usePoll(() => list.reload(true), (list.data || []).some((w) => ["queued", "running"].includes(w.status)), 1500);
  if (list.loading && !list.data) return <Loading />;
  const items = list.data || [];
  const depth = (w: any): number => (w.parent_id ? 1 + depth(items.find((x) => x.id === w.parent_id) || {}) : 0);
  return (
    <div className="grid gap-4 xl:grid-cols-[340px_1fr]">
      <div className="space-y-4">
        {can("analysis:run") && <Section title={parent ? "Branch scenario" : "New hypothetical scenario"} actions={parent && <button className="text-xs text-accent-700" onClick={() => setParent(null)}>cancel branch</button>}>
          <NewScenario cid={c.id} parent={parent} onCreated={(id) => { setParent(null); setSel(id); list.reload(true); }} /></Section>}
        <Section title="Scenario branches">
          {!items.length ? <div className="text-sm text-slate-500">No scenarios yet.</div> : (
            <ul className="space-y-1">{items.map((w) => (
              <li key={w.id} className={clsx("flex items-center gap-2 rounded-lg px-2 py-1.5 text-sm", sel === w.id ? "bg-accent-50" : "hover:bg-slate-100")} style={{ paddingLeft: 8 + depth(w) * 16 }}>
                <input type="checkbox" title="Compare" checked={cmp.includes(w.id)} disabled={w.status !== "completed"} onChange={(e) => setCmp(e.target.checked ? [...cmp, w.id] : cmp.filter((x) => x !== w.id))} />
                <button className="min-w-0 flex-1 truncate text-left" onClick={() => setSel(w.id)}>{depth(w) > 0 && "↳ "}{w.title}</button>
                {w.status !== "completed" ? <Badge tone={w.status === "failed" ? "red" : "amber"}>{w.status}</Badge> :
                  w.decision_change && <Badge tone={w.decision_change.changed ? "violet" : "slate"}>{w.decision_change.to}</Badge>}</li>))}</ul>)}
        </Section>
      </div>
      <div>
        {cmp.length >= 2 && compare.data && (
          <Section title={<span className="flex items-center gap-2">Scenario comparison <Hypo /></span>} className="mb-4">
            <table className="w-full text-sm"><thead><tr className="label text-left"><th className="py-1">Scenario</th><th>Decision</th><th>Hypothesis</th><th>Contradictions</th><th>Gaps</th><th>Independent sources</th></tr></thead>
              <tbody className="divide-y divide-slate-200">{compare.data.scenarios.map((s: any) => (
                <tr key={s.id}><td className="py-1.5">{s.title}</td><td><Badge>{s.decision}</Badge></td><td>{s.pattern?.replace(/_/g, " ")}</td>
                  <td className="tabular-nums">{s.contradictions}</td><td className="tabular-nums">{s.gaps}</td><td className="tabular-nums">{s.independent_sources}</td></tr>))}</tbody></table>
          </Section>)}
        {sel ? <Result key={sel} id={sel} onBranch={(w) => setParent(w)} onDiscard={() => { setSel(null); list.reload(true); }} /> :
          <Empty title="Test an alternative explanation" icon={<GitFork className="h-5 w-5" />}
            hint="Pick an assumption on the left. The simulation runs on an isolated copy of the case and every result is labelled HYPOTHETICAL." />}
      </div>
    </div>
  );
}
