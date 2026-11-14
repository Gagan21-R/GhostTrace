import clsx from "clsx";
import { AnimatePresence, motion } from "framer-motion";
import { ArrowRight, Check, CircleSlash, FileDown, FlaskConical, GitCompare, History, Plus, RotateCcw, Scale, ShieldQuestion, Sparkles, Swords, X } from "lucide-react";
import { useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import { useEvidenceViewer } from "../../components/EvidenceViewer";
import { Badge, Empty, Loading, Section } from "../../components/ui";
import { api, getToken } from "../../lib/api";
import { useAuth } from "../../lib/auth";
import { fmtDate, useApi } from "../../lib/hooks";
import { t } from "../../lib/i18n";
import { useCase } from "./CaseWorkspace";

/* Same visual language as the rest of GhostTrace: paper cards, ink borders, hard shadows, acid / flame / volt accents. */
const LABEL_STYLE: Record<string, { card: string; chip: string; bar: string; width: number }> = {
  strongly_supported: { card: "bg-emerald-50", chip: "bg-emerald-500 text-white", bar: "bg-emerald-500", width: 100 },
  partially_supported: { card: "bg-surface", chip: "bg-acid text-ink-900", bar: "bg-volt", width: 70 },
  inconclusive: { card: "bg-surface", chip: "bg-slate-200 text-ink-900", bar: "bg-slate-400", width: 45 },
  weakened: { card: "bg-amber-50", chip: "bg-amber-400 text-ink-900", bar: "bg-amber-400", width: 25 },
  contradicted: { card: "bg-rose-50", chip: "bg-rose-500 text-white", bar: "bg-rose-500", width: 8 },
  rejected: { card: "bg-paper opacity-70", chip: "bg-slate-300 text-slate-600 line-through", bar: "bg-slate-300", width: 0 },
};
const CELL: Record<string, { cls: string; sym: string; label: string }> = {
  supports: { cls: "bg-emerald-500 text-white", sym: "✓", label: "Supports" },
  contradicts: { cls: "bg-rose-500 text-white", sym: "✕", label: "Contradicts" },
  inconclusive: { cls: "bg-paper text-slate-500", sym: "~", label: "Inconclusive" },
  not_evaluated: { cls: "bg-surface text-slate-300 border-dashed", sym: "·", label: "Not evaluated" },
};
const KIND_TS: Record<string, string> = { source_reported: "confirmed in record", metadata_derived: "file metadata", estimated: "estimated", unknown: "no time" };

/** "New evidence EV-007: Payment failed, pending or reversed" -> translated, keeping the evidence codes as they are. */
const because = (b: string) => {
  const m = /^New evidence ([^:]+): (.*)$/.exec(b || "");
  return m ? `${t("New evidence")} ${m[1]}: ${t(m[2])}` : t(b || "");
};
const lab = (k: string) => t((k || "").replace(/_/g, " "));

export default function HypothesisTab() {
  const { c, canWrite } = useCase();
  const { can } = useAuth();
  const { open } = useEvidenceViewer();
  const nav = useNavigate();
  const [ver, setVer] = useState<number | null>(null);
  const latest = useApi<any>(`/api/cases/${c.id}/hypothesis-lab`);
  const old = useApi<any>(ver ? `/api/cases/${c.id}/hypothesis-lab/versions/${ver}` : null, [ver]);
  const tl = useApi<any[]>(`/api/cases/${c.id}/timeline`);
  const [busy, setBusy] = useState(false);
  const [cell, setCell] = useState<{ row: any; hid: string } | null>(null);
  const [adding, setAdding] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  const a = ver ? old.data : latest.data?.analysis;
  const versions = latest.data?.versions || [];
  const decide = can("review:decide") && canWrite;

  const act = async (fn: () => Promise<any>) => {
    setBusy(true); setErr(null);
    try { await fn(); setVer(null); await latest.reload(true); } catch (e: any) { setErr(e.message); } finally { setBusy(false); }
  };
  // Re-evaluation runs in the background; follow it on the live processing page like every other run.
  const reevaluate = async () => {
    setErr(null);
    try { await api.post(`/api/cases/${c.id}/hypothesis-lab/run?background=true`); nav(`/cases/${c.id}/processing?live=1`); } catch (e: any) { setErr(e.message); }
  };
  const exportReport = async () => {
    const r = await fetch(`/api/cases/${c.id}/hypothesis-lab/report`, { headers: { Authorization: `Bearer ${getToken()}` } });
    window.open(URL.createObjectURL(new Blob([await r.text()], { type: "text/html" })), "_blank");
  };
  const hyps = useMemo(() => (a?.hypotheses || []) as any[], [a]);
  const cmp = useMemo(() => Object.fromEntries((a?.comparison || []).map((x: any) => [x.id, x])), [a]);

  if (latest.loading && !latest.data) return <Loading />;
  if (!a) return (
    <Empty icon={<FlaskConical className="h-5 w-5" />} title="No hypothesis analysis yet"
      hint="The engine runs automatically after processing. You can also start it now."
      action={canWrite && <button className="btn-primary" onClick={reevaluate}><Sparkles className="h-4 w-4" />Generate hypotheses</button>} />
  );

  return (
    <div className="space-y-5">
      {/* A. Investigation question */}
      <Section title="Investigation question" topic="hypothesis_lab"
        actions={<div className="flex flex-wrap gap-2">
          {canWrite && !ver && <button className="btn-outline !py-1.5" onClick={reevaluate}><RotateCcw className="h-4 w-4" />{t("Re-evaluate")}</button>}
          <button className="btn-primary !py-1.5" onClick={exportReport}><FileDown className="h-4 w-4" />{t("Export report")}</button></div>}>
        <div className="font-display text-2xl uppercase leading-tight">{a.question.question}</div>
        <div className="mt-2 flex flex-wrap gap-1.5">
          <Badge>{c.case_number}</Badge><Badge tone="blue">{a.question.dispute_type.replace(/_/g, " ")}</Badge>
          <Badge>{a.question.evidence_count} evidence items</Badge><Badge>version {a.version} · {fmtDate(a.created_at)}</Badge>
          <Badge tone={a.approval.status === "approved" ? "green" : a.approval.status === "rejected" ? "red" : "amber"}>human review: {a.approval.status}</Badge>
        </div>
        <div className="mt-4 grid gap-4 md:grid-cols-2">
          <div><div className="label">Allegations (claims, not evidence)</div>
            <ul className="mt-1 space-y-1 text-sm">{a.question.allegations.slice(0, 3).map((x: any, i: number) => (
              <li key={i}><button className="text-left hover:underline" onClick={() => open(x.evidence_id, x.segment_id)}><span className="mono font-bold text-flame">{x.code}</span> {x.excerpt}</button></li>))}
              {!a.question.allegations.length && <li className="text-slate-500">None recorded</li>}</ul></div>
          <div><div className="label">Documented facts</div>
            <div className="mt-1 flex flex-wrap gap-1.5">{a.question.documented_facts.slice(0, 10).map((f: any, i: number) => (
              <button key={i} onClick={() => open(f.evidence_id, f.segment_id)} className="chip border-2 border-ink-900 bg-surface mono text-[11px] hover:bg-acid">{f.type}: {f.value}</button>))}</div></div>
        </div>
      </Section>

      {(() => {
        // The latest version may be a re-check with no changes; always surface the most recent real revision.
        const rv = ver ? (a.changes && !a.changes.first_version && (a.changes.changed.length || a.changes.leading_changed) ? { ...a.changes, version: a.version } : null)
                       : latest.data?.last_revision;
        if (!rv) return null;
        return (
        <motion.div initial={{ scale: 0.98, opacity: 0 }} animate={{ scale: 1, opacity: 1 }} className="border-[3px] border-ink-900 bg-acid p-4 shadow-brutal">
          <div className="flex items-center gap-2 font-display text-lg uppercase"><GitCompare className="h-5 w-5" />
            {t("Assessment revised in version")} {rv.version}{rv.new_evidence.length > 0 && ` · ${t("after new evidence")} ${rv.new_evidence.join(", ")}`}</div>
          {rv.version !== a.version && <div className="text-xs">{t("Later versions re-checked the evidence without changing these results.")}</div>}
          {rv.leading_changed && <div className="mt-1 text-sm">{t("Leading explanation")}: <b>{rv.leading_before}</b> <ArrowRight className="inline h-3.5 w-3.5" /> <b>{rv.leading_after}</b></div>}
          <ul className="mt-2 space-y-1 text-sm">{rv.changed.map((x: any) => (
            <li key={x.id}><b>{x.id} {t(x.title)}</b>: {lab(x.from)} → <b>{lab(x.to)}</b>. {because(x.because)}</li>))}</ul>
        </motion.div>);
      })()}

      {/* B. Hypothesis cards */}
      <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
        {hyps.map((h: any, i: number) => {
          const k = cmp[h.id]; const st = LABEL_STYLE[k?.label || "inconclusive"]; const ctr = a.counter[h.id] || {};
          const best = k?.rank === 1 && k.label !== "rejected";
          return (
            <motion.div key={h.id} initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: i * 0.05 }}
              className={clsx("card card-lift relative p-4", st.card, best && "shadow-brutal-lg ring-4 ring-acid")}>
              {best && <span className="absolute -top-3 right-3 border-2 border-ink-900 bg-acid px-2 py-0.5 text-[10px] font-bold uppercase">{t("Fits best")}</span>}
              <div className="mono text-xs text-slate-500">{h.id}{h.source === "investigator" && " · investigator"}</div>
              <div className="font-display text-lg uppercase leading-tight">{t(h.title)}</div>
              <p className="mt-1 text-sm text-slate-600">{t(h.description)}</p>
              <span className={clsx("mt-3 inline-block border-2 border-ink-900 px-2 py-0.5 text-xs font-bold uppercase", st.chip)}>{t(k?.label_text || "")}</span>
              <div className="mt-2 h-2.5 border-2 border-ink-900 bg-surface"><motion.div className={clsx("h-full", st.bar)} initial={{ width: 0 }} animate={{ width: `${st.width}%` }} /></div>
              <div className="mt-2 flex flex-wrap gap-3 text-xs font-semibold"><span className="text-emerald-700">✓ {k?.independent_support ?? 0} independent</span>
                <span className="text-rose-700">✕ {k?.contradicting ?? 0} against</span><span>? {(ctr.unverified_assumptions || []).length} unverified</span></div>
              {(ctr.unverified_assumptions || []).length > 0 && <div className="mt-2 text-xs text-slate-600">Unresolved: {ctr.unverified_assumptions.join("; ")}</div>}
              {h.challenges?.length > 0 && <div className="mt-2 border-l-4 border-volt pl-2 text-xs">Investigator challenge: {h.challenges[h.challenges.length - 1]}</div>}
              {decide && !ver && (
                <div className="mt-3 flex flex-wrap gap-1.5">
                  {h.status === "rejected"
                    ? <button disabled={busy} className="btn-outline !px-2 !py-0.5 text-[11px]" onClick={() => act(() => api.post(`/api/cases/${c.id}/hypothesis-lab/${h.id}/restore`, { note: "" }))}>Restore</button>
                    : <button disabled={busy} className="btn-no !px-2 !py-0.5 text-[11px]" onClick={() => { const note = prompt(`Why reject ${h.id}?`) ?? ""; act(() => api.post(`/api/cases/${c.id}/hypothesis-lab/${h.id}/reject`, { note })); }}>
                        <CircleSlash className="h-3 w-3" />Reject</button>}
                  <button disabled={busy} className="btn-outline !px-2 !py-0.5 text-[11px]" onClick={() => { const note = prompt(`Challenge ${h.id}: what does the engine miss?`); if (note) act(() => api.post(`/api/cases/${c.id}/hypothesis-lab/${h.id}/challenge`, { note })); }}>
                    <Swords className="h-3 w-3" />Challenge</button>
                </div>)}
            </motion.div>);
        })}
        {decide && !ver && (
          <button onClick={() => setAdding(true)} className="flex min-h-[180px] flex-col items-center justify-center gap-2 border-[3px] border-dashed border-ink-900 bg-paper text-sm font-bold uppercase hover:bg-acid/40">
            <Plus className="h-6 w-6" />Add your own hypothesis</button>)}
      </div>
      {err && <div className="border-2 border-flame bg-flame/10 p-2 text-sm">{err}</div>}

      {/* C. Evidence comparison matrix */}
      <Section title={<span className="inline-flex items-center gap-2"><Scale className="h-4 w-4" />Evidence comparison matrix</span>}>
        <div className="mb-3 flex flex-wrap items-center gap-3 text-xs">{Object.entries(CELL).map(([k, v]) => (
          <span key={k} className="inline-flex items-center gap-1"><span className={clsx("inline-flex h-5 w-5 items-center justify-center border-2 border-ink-900 text-[11px] font-bold", v.cls)}>{v.sym}</span>{v.label}</span>))}
          <span className="text-slate-500">Click a cell to see the exact source.</span></div>
        <div className="overflow-x-auto">
          <table className="w-full border-separate border-spacing-1 text-xs">
            <thead><tr><th className="label text-left">Evidence</th>{hyps.map((h: any) => (
              <th key={h.id} className="min-w-[64px] border-2 border-ink-900 bg-ink-900 py-1 text-center mono text-acid" title={h.title}>{h.id}</th>))}</tr></thead>
            <tbody>{a.matrix.map((row: any) => (
              <tr key={row.evidence_id}>
                <td className="max-w-[280px] truncate pr-2"><span className="mono font-bold">{row.code}</span> {row.file}
                  <Badge className="ml-1" tone={row.allegation ? "amber" : row.reliability === "high" ? "green" : "slate"}>{row.allegation ? "allegation" : row.reliability}</Badge></td>
                {hyps.map((h: any) => { const v = row.cells[h.id] || { state: "not_evaluated" }; const s = CELL[v.state];
                  const on = cell?.row.evidence_id === row.evidence_id && cell?.hid === h.id;
                  return <td key={h.id}><button onClick={() => setCell({ row, hid: h.id })}
                    className={clsx("h-8 w-full border-2 border-ink-900 text-sm font-bold transition hover:-translate-y-px hover:shadow-brutal-sm", s.cls, on && "shadow-brutal ring-2 ring-volt")}>{s.sym}</button></td>; })}
              </tr>))}</tbody>
          </table>
        </div>
        <AnimatePresence>{cell && (
          <motion.div initial={{ opacity: 0, height: 0 }} animate={{ opacity: 1, height: "auto" }} exit={{ opacity: 0, height: 0 }} className="mt-3 overflow-hidden border-2 border-ink-900 bg-paper p-3">
            <div className="flex items-start justify-between gap-2"><div className="text-sm"><b>{cell.row.code} × {cell.hid}</b>
              <span className="ml-2 text-slate-600">{CELL[cell.row.cells[cell.hid].state].label} · {cell.row.cells[cell.hid].reason}</span></div>
              <button onClick={() => setCell(null)} aria-label="Close"><X className="h-4 w-4" /></button></div>
            <ul className="mt-2 space-y-1.5">{cell.row.cells[cell.hid].refs.map((r: any, i: number) => (
              <li key={i} className="text-xs"><button onClick={() => open(r.evidence_id, r.segment_id)} className="chip mr-2 border-2 border-ink-900 bg-surface mono hover:bg-acid">{r.code} · {r.locator}</button>
                <b className={r.relation === "supports" ? "text-emerald-700" : "text-rose-700"}>{r.relation}</b> “{r.excerpt}”
                {r.derived && <span className="ml-1 text-[10px] text-slate-500">(from {r.derived})</span>}</li>))}
              {!cell.row.cells[cell.hid].refs.length && <li className="text-xs text-slate-500">No passage in this file bears on this hypothesis.</li>}</ul>
          </motion.div>)}</AnimatePresence>
      </Section>

      <div className="grid gap-5 xl:grid-cols-2">
        {/* D. Adversarial reasoning */}
        <Section title={<span className="inline-flex items-center gap-2"><Swords className="h-4 w-4" />Adversarial reasoning</span>}>
          {(() => {
            const first = hyps[0]; const ctr = a.counter[first?.id] || {}; const lead = a.comparison[0];
            const steps = [
              { t: "Initial explanation", c: "border-slate-400", body: <>{first?.title}: {first?.description}<div className="mt-1 text-slate-600">A single-agent baseline would conclude: <b>{a.baseline.conclusion}</b> ({a.baseline.considered_alternatives} alternatives considered).</div></> },
              { t: "Counterevidence challenge", c: "border-flame", body: <>{ctr.contradicting?.length || 0} contradicting record(s); {ctr.alternative_readings?.length || 0} alternative reading(s) of its support.
                <ul className="mt-1 list-disc pl-4 text-slate-600">{(ctr.alternative_readings || []).slice(0, 2).map((r: any) => <li key={r.signal}>{r.text}</li>)}
                  {(ctr.contradicting || []).slice(0, 2).map((r: any, i: number) => <li key={i}>{r.code}: {r.what}</li>)}</ul></> },
              { t: "Revised assessment", c: "border-volt", body: <>{a.hypotheses.length} explanations compared. Fits best: <b>{lead?.id} {lead?.title}</b> ({lead?.label_text}).
                {first && cmp[first.id] && <div className="mt-1 text-slate-600">{first.id} is now: <b>{cmp[first.id].label_text}</b>.</div>}</> },
              { t: "Reviewer findings", c: a.review.status === "passed" ? "border-emerald-500" : "border-amber-400", body: <>{a.review.statement} {a.review.citations_checked} citations checked;
                {" "}{a.review.issues.length ? `${a.review.issues.length} issue(s): ${a.review.issues.slice(0, 2).map((x: any) => x.text).join("; ")}` : "no issues."}</> },
            ];
            return <ol className="space-y-2">{steps.map((s, i) => (
              <motion.li key={s.t} initial={{ opacity: 0, x: -10 }} animate={{ opacity: 1, x: 0 }} transition={{ delay: i * 0.1 }}
                className={clsx("border-2 border-l-[6px] border-ink-900 bg-paper p-2.5 text-sm", s.c)}>
                <div className="label mb-0.5">{i + 1}. {s.t}</div>{s.body}</motion.li>))}</ol>;
          })()}
        </Section>

        {/* E. Evidence that would settle it */}
        <Section title={<span className="inline-flex items-center gap-2"><ShieldQuestion className="h-4 w-4" />Evidence that would settle it</span>} topic="missing_evidence">
          <ol className="space-y-2">{a.next_evidence.map((n: any) => (
            <li key={n.id} className="border-2 border-ink-900 bg-surface p-2.5 text-sm shadow-brutal-sm">
              <div className="flex items-center gap-2"><span className="flex h-6 w-6 shrink-0 items-center justify-center border-2 border-ink-900 bg-acid text-xs font-bold">{n.rank}</span>
                <b>{n.evidence}</b><Badge className="ml-auto" tone={n.urgency === "high" ? "red" : "slate"}>{n.urgency}</Badge></div>
              <div className="mt-1 text-slate-700">{n.how}</div>
              <div className="mt-1 text-xs text-slate-500">From: {n.source} · separates {n.separates.join(" / ")} · {n.privacy}</div></li>))}
            {!a.next_evidence.length && <li className="border-2 border-ink-900 bg-emerald-50 p-2.5 text-sm"><Check className="mr-1 inline h-4 w-4 text-emerald-600" />The available records already separate the standing explanations.</li>}</ol>
        </Section>
      </div>

      {/* F. Timeline */}
      <Section title={<span className="inline-flex items-center gap-2"><History className="h-4 w-4" />Source-linked timeline</span>} topic="timeline">
        <ol className="relative max-h-80 space-y-2 overflow-y-auto border-l-[3px] border-ink-900 pl-4 scrollbar-thin">
          {(tl.data || []).filter((e: any) => e.timestamp_kind !== "system_recorded").slice(0, 40).map((e: any) => (
            <li key={e.id} className="relative text-sm">
              <span className={clsx("absolute -left-[23px] top-1.5 h-3 w-3 border-2 border-ink-900", e.timestamp_kind === "source_reported" ? "bg-volt" : e.timestamp_kind === "estimated" ? "bg-amber-400" : "bg-slate-300")} />
              <span className="mono text-xs text-slate-500">{e.display_time || "time unknown"}</span>
              <Badge className="ml-2" tone={e.timestamp_kind === "source_reported" ? "blue" : "amber"}>{KIND_TS[e.timestamp_kind] || e.timestamp_kind}</Badge>
              <button className="ml-2 text-left hover:underline" onClick={() => open(e.evidence_id, e.segment_id)}>{e.title}</button>
              <span className="ml-1 mono text-xs font-bold">{e.evidence_code}</span>{e.conflict && <Badge className="ml-1" tone="red">conflict</Badge>}</li>))}
          {!(tl.data || []).some((e: any) => e.timestamp_kind !== "system_recorded") && <li className="text-sm text-slate-500">No dated events.</li>}
        </ol>
      </Section>

      {/* G. Human approval and versions */}
      <Section title={<span className="inline-flex items-center gap-2"><Check className="h-4 w-4" />Human approval and versions</span>} topic="human_review">
        <div className="flex flex-wrap items-center gap-2">
          {decide && !ver && <>
            <button disabled={busy} className="btn-ok" onClick={() => { const note = prompt("Approval note (recorded in the audit log)") ?? ""; act(() => api.post(`/api/cases/${c.id}/hypothesis-lab/approve`, { decision: "approved", note })); }}>Approve assessment</button>
            <button disabled={busy} className="btn-no" onClick={() => { const note = prompt("Why is the assessment rejected?") ?? ""; act(() => api.post(`/api/cases/${c.id}/hypothesis-lab/approve`, { decision: "rejected", note })); }}>Reject assessment</button></>}
          {a.approval.note && <span className="text-sm text-slate-600">“{a.approval.note}”</span>}
          <div className="ml-auto flex flex-wrap items-center gap-1.5 text-xs">
            <span className="label">Versions</span>
            {versions.map((v: any) => {
              const isLatest = v.version === versions[versions.length - 1]?.version; const on = ver ? ver === v.version : isLatest;
              return <button key={v.version} onClick={() => setVer(isLatest ? null : v.version)} title={`${v.trigger} · leading ${v.leading} · ${v.evidence} files`}
                className={clsx("border-2 border-ink-900 px-2 py-0.5 mono font-bold", on ? "bg-ink-900 text-acid" : "bg-surface hover:bg-acid")}>v{v.version}</button>;
            })}
          </div>
        </div>
        <p className="mt-2 text-xs text-slate-500">Labels describe the state of the evidence, not guilt or liability. No probabilities are shown because no calibrated model exists for them.</p>
      </Section>

      <AnimatePresence>{adding && <AddHypothesis caseId={c.id} onClose={() => setAdding(false)} onDone={() => { setAdding(false); latest.reload(true); }} />}</AnimatePresence>
    </div>
  );
}

function AddHypothesis({ caseId, onClose, onDone }: { caseId: string; onClose: () => void; onDone: () => void }) {
  const [f, setF] = useState({ title: "", description: "", keywords: "" });
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  const save = async () => {
    setBusy(true); setErr(null);
    try { await api.post(`/api/cases/${caseId}/hypothesis-lab/custom`, { title: f.title, description: f.description, keywords: f.keywords.split(",").map((k) => k.trim()).filter(Boolean) }); onDone(); }
    catch (e: any) { setErr(e.message); } finally { setBusy(false); }
  };
  return (
    <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }} className="fixed inset-0 z-50 flex items-center justify-center bg-ink-900/50 p-4" onClick={onClose}>
      <motion.div initial={{ scale: 0.95 }} animate={{ scale: 1 }} className="w-full max-w-md border-[3px] border-ink-900 bg-surface p-5 shadow-brutal-lg" onClick={(e) => e.stopPropagation()}>
        <div className="font-display text-xl uppercase">Add a hypothesis</div>
        <p className="mt-1 text-xs text-slate-600">It is tested against the same evidence. Keywords decide which passages count as relevant.</p>
        <input className="input mt-3" placeholder="Title, e.g. Buyer cancelled and the seller kept the advance" value={f.title} onChange={(e) => setF({ ...f, title: e.target.value })} />
        <textarea className="input mt-2 h-20" placeholder="Description" value={f.description} onChange={(e) => setF({ ...f, description: e.target.value })} />
        <input className="input mt-2" placeholder="Keywords, comma separated (e.g. cancel, advance)" value={f.keywords} onChange={(e) => setF({ ...f, keywords: e.target.value })} />
        {err && <div className="mt-2 text-xs text-rose-700">{err}</div>}
        <div className="mt-4 flex justify-end gap-2"><button onClick={onClose} className="btn-outline">Cancel</button>
          <button disabled={busy || f.title.trim().length < 3} onClick={save} className="btn-primary">{busy ? "Testing…" : "Add and test"}</button></div>
      </motion.div>
    </motion.div>
  );
}
