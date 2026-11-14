import { ChevronLeft } from "lucide-react";
import { Link, useParams, useSearchParams } from "react-router-dom";
import { SourceRef, Viewer } from "../components/EvidenceViewer";
import { Badge, ErrorBox, Loading, Section } from "../components/ui";
import { titleCase, useApi } from "../lib/hooks";
import { REL } from "./case/DnaTab";

/** Evidence detail page: the original, its extracted content and everything the case links to it. */
export default function EvidencePage() {
  const { evidenceId } = useParams();
  const [sp] = useSearchParams();
  const { data, error, loading } = useApi<any>(`/api/evidence/${evidenceId}`);
  const rel = useApi<any>(`/api/evidence/${evidenceId}/related`);
  if (loading && !data) return <Loading />;
  if (error) return <ErrorBox error={error} />;
  const r = rel.data;
  return (
    <div>
      <Link to={`/cases/${data.case_id}/evidence`} className="mb-2 inline-flex items-center gap-1 text-xs font-medium text-slate-500 hover:text-ink-900"><ChevronLeft className="h-3.5 w-3.5" />Evidence Vault</Link>
      <div className="grid gap-4 xl:grid-cols-[1fr_380px]">
        <div className="card"><Viewer id={evidenceId!} segmentId={sp.get("segment")} /></div>
        <div className="space-y-4">
          {!r ? <Loading /> : <>
            <Section title={`Integrity checks (${r.integrity_findings.length})`}>
              {!r.integrity_findings.length ? <div className="text-sm text-slate-500">No integrity observations.</div> :
                <ul className="space-y-1.5">{r.integrity_findings.map((f: any, i: number) => (
                  <li key={i} className="text-xs"><Badge tone={f.severity === "high" ? "red" : f.severity === "medium" ? "amber" : "slate"}>{f.severity}</Badge> <b>{titleCase(f.check)}</b> - {f.observation}</li>))}</ul>}
              <p className="mt-2 text-[11px] text-slate-500">Indicators for human review, not proof of tampering. Hash verification shows integrity since intake only.</p>
            </Section>
            <Section title={`Related evidence (${r.related_evidence.length})`}>
              {!r.related_evidence.length ? <div className="text-sm text-slate-500">No cross-file relationships.</div> :
                <ul className="space-y-2">{r.related_evidence.map((d: any) => { const other = d.a.id === evidenceId ? d.b : d.a; const R = REL[d.relation]; return (
                  <li key={d.id} className="text-xs"><div className="flex items-center gap-2"><Link to={`/evidence/${other.id}`} className="mono font-semibold hover:text-accent-700">{other.code}</Link>
                    <Badge tone={R.tone}>{R.label}</Badge><span className="truncate text-slate-500">{other.filename}</span></div>
                    <div className="mt-0.5 text-slate-600">{d.explanation}</div></li>); })}</ul>}
            </Section>
            <Section title={`Contradictions involving this item (${r.contradictions.length})`}>
              {!r.contradictions.length ? <div className="text-sm text-slate-500">None.</div> :
                <ul className="space-y-1">{r.contradictions.map((c: any) => <li key={c.id} className="text-xs"><Link to={`/cases/${data.case_id}/contradictions`} className="mono font-semibold hover:text-accent-700">{c.code}</Link> <Badge>{c.classification}</Badge> {c.description}</li>)}</ul>}
            </Section>
            <Section title={`Timeline events (${r.events.length})`}>
              <ul className="max-h-64 space-y-1 overflow-auto scrollbar-thin">{r.events.map((e: any) => (
                <li key={e.id} className="text-xs"><span className="mono text-slate-500">{e.display_time || "time unknown"}</span> <Badge>{e.kind.replace(/_/g, " ")}</Badge> {e.title}</li>))}</ul>
            </Section>
            <Section title={`Extracted entities (${r.entities.length})`}>
              <div className="flex flex-wrap gap-1.5">{r.entities.map((e: any) => <Badge key={e.id}>{e.type}: {e.value}</Badge>)}</div>
            </Section>
          </>}
          <div className="text-[11px] text-slate-500">Source references elsewhere open this page at the cited location: <SourceRef src={{ evidence_id: data.id, evidence_code: data.code, filename: data.filename }} /></div>
        </div>
      </div>
    </div>
  );
}
