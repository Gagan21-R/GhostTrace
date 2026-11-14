import clsx from "clsx";
import { motion } from "framer-motion";
import { AlertTriangle, BadgeCheck, CircleSlash, Gavel, HelpCircle, Lightbulb, Scale, Search, ShieldAlert, Swords } from "lucide-react";
import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { SourceRef } from "../../components/EvidenceViewer";
import { Badge, Empty, ErrorBox, Loading, Section, VERDICT_LABEL, statusTone } from "../../components/ui";
import { api } from "../../lib/api";
import { useAuth } from "../../lib/auth";
import { titleCase, useApi, usePoll } from "../../lib/hooks";
import { useCase } from "./CaseWorkspace";
import { ADVERSARIAL_AGENTS, AgentPipeline } from "./ProcessingTab";

const V_ICON: Record<string, any> = { verified: BadgeCheck, partially_verified: HelpCircle, inference: Lightbulb, rejected: CircleSlash };
const V_TONE: Record<string, string> = { verified: "green", partially_verified: "amber", inference: "violet", rejected: "red" };

function VerifyChip({ v }: { v: any }) {
  if (!v) return null;
  const Icon = V_ICON[v.status] || HelpCircle;
  return <span title={v.checks?.join("\n")}><Badge tone={V_TONE[v.status]}><Icon className="h-3 w-3" />{titleCase(v.status)}</Badge></span>;
}

export default function AdversarialTab() {
  const { c, reload: reloadCase, canWrite } = useCase();
  const { can } = useAuth();
  const hyps = useApi<any[]>(`/api/cases/${c.id}/hypotheses`);
  const runs = useApi<any[]>(`/api/cases/${c.id}/runs`);
  const latestRun = runs.data?.find((r) => r.kind === "adversarial");
  const runDetail = useApi<any>(latestRun ? `/api/runs/${latestRun.id}` : null, [latestRun?.id]);
  const active = !!latestRun && ["queued", "running"].includes(latestRun.status);
  usePoll(() => { runs.reload(true); runDetail.reload(true); }, active, 900);
  const [was, setWas] = useState(false);
  if (active !== was) { setWas(active); if (!active) { hyps.reload(true); reloadCase(true); } }
  const [err, setErr] = useState<string | null>(null);
  const [note, setNote] = useState("");
  const nav = useNavigate();
  const start = async () => {
    setErr(null);
    try { await api.post(`/api/cases/${c.id}/adversarial`); nav(`/cases/${c.id}/processing?live=1`); } catch (e: any) { setErr(e.message); }
  };
  const [ci, setCi] = useState(0);
  const h = hyps.data?.[ci] ?? hyps.data?.[0];

  return (
    <div className="space-y-4">
      <Section title={<span className="flex items-center gap-2"><Swords className="h-4 w-4" />Challenge Centre · Evidence Challenge Engine</span>}
        actions={canWrite && <button className="btn-accent" onClick={start} disabled={active}><Swords className="h-4 w-4" />{h ? "Run again" : "Run adversarial review"}</button>}>
        <p className="mb-4 max-w-4xl text-sm text-slate-500">An Investigation agent proposes the best-supported hypothesis.</p>
        <AgentPipeline agents={ADVERSARIAL_AGENTS} run={runDetail.data} />
        {err && <div className="mt-3"><ErrorBox error={err} /></div>}
        {runDetail.data?.agents?.find((a: any) => a.agent === "counter_investigation")?.mode && (
          <div className="mt-3 text-xs text-slate-500">Counter-agent mode: <b>{runDetail.data.agents.find((a: any) => a.agent === "counter_investigation").mode}</b></div>)}
      </Section>

      {hyps.data && hyps.data.length > 1 && (
        <div className="flex flex-wrap items-center gap-2">
          <span className="label">Candidate hypotheses (each challenged separately)</span>
          {hyps.data.map((x: any, i: number) => (
            <button key={x.id} onClick={() => setCi(i)} className={clsx("chip border px-3 py-1", i === ci ? "border-accent-500 bg-accent-50 text-accent-700" : "border-slate-300 text-slate-600")}>
              #{i + 1} {x.pattern.replace(/_/g, " ")} · <b>{x.decision}</b></button>))}
        </div>)}
      {hyps.loading && !hyps.data ? <Loading /> : !h ? (
        <Empty title="No adversarial review yet" hint="Process the evidence first, then run the engine to generate and challenge a hypothesis." icon={<Scale className="h-5 w-5" />} />
      ) : (
        <>
          <motion.div initial={{ opacity: 0, y: 6 }} animate={{ opacity: 1, y: 0 }} className="card overflow-hidden">
            <div className="grid lg:grid-cols-[1fr_280px]">
              <div className="p-5">
                <div className="label mb-2">Balanced assessment · Skeptical Reviewer agent</div>
                <p className="text-[15px] leading-relaxed text-slate-800">{h.statement}</p>
                <p className="mt-3 text-sm text-slate-600">{h.assessment.reason}</p>
                <div className="mt-3 flex flex-wrap gap-2 text-xs text-slate-500"><Badge>{titleCase(h.pattern)}</Badge>
                  <span>{h.assessment.verified_support.length} verified supporting observations</span>·<span>{h.assessment.counter_considered.length} counter-points considered</span>·
                  <span>{h.verification.rejected} claim(s) rejected by verification</span></div>
              </div>
              <div className={clsx("flex flex-col items-center justify-center gap-2 p-5 text-center",
                h.decision === "CONTRADICTED" ? "bg-rose-50" : h.decision === "SUPPORTED" ? "bg-emerald-50" : h.decision === "HOLD" ? "bg-slate-100" : "bg-amber-50")}>
                <Gavel className="h-7 w-7 text-slate-700" />
                <div className="text-2xl font-bold tracking-wider">{h.decision}</div>
                <div className="text-sm text-slate-600">{VERDICT_LABEL[h.verdict] || h.verdict}</div>
                <div className="text-xs text-slate-500">{h.assessment.independent_sources ?? "—"} independent supporting source(s)</div>
                <Badge tone={statusTone(h.verdict)}>confidence: {h.assessment.confidence_band}</Badge>
                <div className="text-[11px] text-slate-500">Engine output · human review {h.human_review_status}</div>
              </div>
            </div>
          </motion.div>

          <div className="grid gap-4 xl:grid-cols-2">
            <Section title={<span className="flex items-center gap-2"><Search className="h-4 w-4 text-accent-600" />Investigation agent · hypothesis & supporting evidence</span>}>
              <ul className="space-y-3">
                {h.supporting.map((cl: any) => (
                  <li key={cl.id} className="rounded-lg border border-slate-200 p-3">
                    <div className="flex items-start justify-between gap-2"><div className="text-sm text-slate-800"><span className="mono mr-1.5 text-slate-400">{cl.id}</span>{cl.text}</div><VerifyChip v={cl.verification} /></div>
                    <div className="mt-2 flex flex-wrap gap-1.5">{cl.verification?.sources?.map((s: any, i: number) => <SourceRef key={i} src={s} />)}</div>
                  </li>))}
              </ul>
              <div className="label mb-2 mt-4">Unverified assumptions</div>
              <ul className="space-y-1.5">{h.assumptions.map((a: string, i: number) => <li key={i} className="flex gap-2 text-sm text-slate-700"><Lightbulb className="mt-0.5 h-4 w-4 shrink-0 text-violet-500" />{a}</li>)}</ul>
            </Section>

            <Section title={<span className="flex items-center gap-2"><ShieldAlert className="h-4 w-4 text-rose-600" />Counter-investigation agent · challenges</span>}>
              {[...h.counterevidence, ...h.alternatives.filter((a: any) => a.kind !== "other_pattern")].length === 0 && <div className="text-sm text-slate-500">The counter-agent found no material counter-evidence.</div>}
              <ul className="space-y-3">
                {[...h.alternatives.filter((a: any) => a.kind !== "other_pattern"), ...h.counterevidence].map((k: any) => (
                  <li key={k.id} className={clsx("rounded-lg border p-3", k.strength === "strong" ? "border-rose-200 bg-rose-50/50" : "border-slate-200")}>
                    <div className="flex flex-wrap items-center gap-1.5"><Badge tone={k.kind === "alternative_explanation" ? "violet" : k.kind === "contradiction" ? "red" : "amber"}>{titleCase(k.kind)}</Badge>
                      <Badge tone={k.strength === "strong" ? "red" : "slate"}>{k.strength}</Badge>{k.source === "llm" && <Badge tone="blue">LLM-suggested · verified</Badge>}
                      <span className="ml-auto"><VerifyChip v={k.verification} /></span></div>
                    <p className="mt-2 text-sm text-slate-800">{k.text}</p>
                    <div className="mt-2 flex flex-wrap gap-1.5">{k.verification?.sources?.map((s: any, i: number) => <SourceRef key={i} src={s} />)}</div>
                  </li>))}
              </ul>
              {h.alternatives.some((a: any) => a.kind === "other_pattern") && (<>
                <div className="label mb-2 mt-4">Other patterns the evidence partially fits</div>
                {h.alternatives.filter((a: any) => a.kind === "other_pattern").map((a: any, i: number) => <p key={i} className="mb-1 text-sm text-slate-600">• {a.text}</p>)}</>)}
            </Section>
          </div>

          <div className="grid gap-4 xl:grid-cols-3">
            <Section title="Missing information">
              {h.missing_information.length === 0 ? <div className="text-sm text-slate-500">None flagged as high severity.</div> :
                <ul className="space-y-2">{h.missing_information.map((m: any) => <li key={m.id} className="text-sm text-slate-700"><AlertTriangle className="mr-1 inline h-3.5 w-3.5 text-amber-500" />{m.text}</li>)}</ul>}
            </Section>
            <Section title="Recommended next steps">
              <ul className="space-y-1.5">{h.assessment.next_steps.map((n: string, i: number) => <li key={i} className="text-sm text-slate-700">☐ {n}</li>)}</ul>
            </Section>
            <Section title="Confidence limitations">
              <ul className="space-y-1.5">{h.assessment.limitations.map((n: string, i: number) => <li key={i} className="text-xs text-slate-600">• {n}</li>)}</ul>
            </Section>
          </div>

          <VerifyClaim caseId={c.id} />

          {h.verification.rejected_items?.length > 0 && (
            <Section title="Rejected by the Verification agent">
              <ul className="space-y-1 text-sm">{h.verification.rejected_items.map((r: any) => <li key={r.id}><span className="mono">{r.id}</span> — {r.checks.join("; ")}</li>)}</ul>
            </Section>)}

          {can("review:decide") && (
            <Section title="Human review checkpoint">
              <div className="flex flex-wrap items-center gap-2">
                <input className="input flex-1" placeholder="Reviewer note (recorded in audit log and report)" value={note} onChange={(e) => setNote(e.target.value)} />
                {[["accepted", "Accept assessment"], ["needs_more_evidence", "Needs more evidence"], ["rejected", "Reject"]].map(([s, l]) => (
                  <button key={s} className={clsx(s === "accepted" ? "btn-ok" : s === "rejected" ? "btn-no" : "btn-outline")} onClick={async () => { await api.patch(`/api/hypotheses/${h.id}`, { status: s, note }); hyps.reload(true); }}>{l}</button>))}
              </div>
              <div className="mt-2 text-xs text-slate-500">Current: <Badge tone={statusTone(h.human_review_status)}>{h.human_review_status}</Badge> {h.human_review_note && `— ${h.human_review_note}`}</div>
            </Section>)}
        </>
      )}
    </div>
  );
}


function VerifyClaim({ caseId }: { caseId: string }) {
  const { can } = useAuth();
  const ev = useApi<any[]>(`/api/cases/${caseId}/evidence`);
  const [evId, setEvId] = useState(""); const [segId, setSegId] = useState(""); const [text, setText] = useState(""); const [expect, setExpect] = useState("");
  const segs = useApi<any>(evId ? `/api/cases/${caseId}/extracted-data?evidence_id=${evId}&limit=300` : null, [evId]);
  const [res, setRes] = useState<any>(null); const [err, setErr] = useState<string | null>(null);
  if (!can("review:decide")) return null;
  return (
    <Section title="Verify a claim before citing it (Verification agent)">
      <p className="mb-3 text-xs text-slate-500">Check any claim - your own or an AI draft - against the original evidence.</p>
      <div className="grid gap-2 md:grid-cols-2">
        <input className="input md:col-span-2" placeholder="Claim, e.g. The bank debited Rs 24,999 under UTR 407215538921" value={text} onChange={(e) => setText(e.target.value)} />
        <select className="input" value={evId} onChange={(e) => { setEvId(e.target.value); setSegId(""); }}><option value="">Cite evidence…</option>
          {(ev.data || []).map((e) => <option key={e.id} value={e.id}>{e.code} · {e.filename}</option>)}</select>
        <select className="input" value={segId} onChange={(e) => setSegId(e.target.value)} disabled={!evId}><option value="">…at location</option>
          {(segs.data?.items || []).map((s: any) => <option key={s.segment_id} value={s.segment_id}>{s.locator} · {s.text.slice(0, 60)}</option>)}</select>
        <input className="input" placeholder="Value that must appear in the source (e.g. 407215538921)" value={expect} onChange={(e) => setExpect(e.target.value)} />
        <button className="btn-primary justify-center" disabled={!text || !segId} onClick={async () => {
          setErr(null); setRes(null);
          try { setRes(await api.post(`/api/cases/${caseId}/verify-claim`, { text, citations: [segId], expect: expect ? [expect] : [] })); } catch (e: any) { setErr(e.message); }
        }}>Verify claim</button>
      </div>
      {err && <div className="mt-2 text-sm text-rose-700">{err}</div>}
      {res && (
        <div className={clsx("mt-3 rounded-lg border p-3 text-sm", res.status === "verified" ? "border-emerald-200 bg-emerald-50" : res.status === "rejected" ? "border-rose-200 bg-rose-50" : "border-amber-200 bg-amber-50")}>
          <b className="uppercase tracking-wide">{res.status.replace("_", " ")}</b> - {res.checks.join("; ")}
          <div className="mt-1 flex flex-wrap gap-1">{res.sources.map((s: any, i: number) => <SourceRef key={i} src={s} />)}</div>
        </div>)}
    </Section>
  );
}
