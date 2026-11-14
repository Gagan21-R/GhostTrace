import { ChevronLeft, Download } from "lucide-react";
import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { SourceRef } from "../components/EvidenceViewer";
import { Badge, ErrorBox, Hash, Loading, Tabs } from "../components/ui";
import { api } from "../lib/api";
import { fmtDate, useApi } from "../lib/hooks";

function Cell({ v }: { v: any }) {
  if (v === null || v === undefined || v === "") return <>—</>;
  if (Array.isArray(v)) return <span className="inline-flex flex-wrap items-center gap-1">{v.length ? v.map((x, i) => <Cell key={i} v={x} />) : "—"}</span>;
  if (typeof v === "object") {
    if (v.evidence_id) {
      const m = /^\[(EV-[^|\]]+)\s*\|\s*([^\]]*)\]$/.exec(v.text || "");
      return <SourceRef src={{ evidence_id: v.evidence_id, segment_id: v.segment_id, evidence_code: m?.[1]?.trim() || "EV", locator: m?.[2] }} />;
    }
    return <span className="mono text-xs text-slate-500">{v.text}</span>;
  }
  return <>{String(v)}</>;
}

const LABEL_TONE: Record<string, string> = { ENGINE: "blue", HUMAN: "green", SYSTEM: "slate", "ENGINE + HUMAN": "violet" };

export default function ReportPreviewPage() {
  const { reportId } = useParams();
  const { data: r, error, loading } = useApi<any>(`/api/reports/${reportId}`);
  const [tab, setTab] = useState("html");
  const [pdf, setPdf] = useState<string | null>(null);
  const [pdfErr, setPdfErr] = useState<string | null>(null);
  useEffect(() => {
    if (tab !== "pdf" || pdf) return;
    api.blobUrl(`/api/reports/${reportId}/preview`).then((x) => setPdf(x.url)).catch((e) => setPdfErr(e.message));
  }, [tab, reportId, pdf]);
  useEffect(() => () => { if (pdf) URL.revokeObjectURL(pdf); }, [pdf]);
  if (loading && !r) return <Loading />;
  if (error) return <ErrorBox error={error} />;
  const c = r.content || {};
  const sections: any[] = c.sections || [];
  const dl = (fmt: string) => api.download(`/api/reports/${r.id}/${fmt === "pdf" ? "download" : fmt}`, `EVIDENCE-X_report_${r.id.slice(0, 8)}.${fmt}`);
  return (
    <div>
      <Link to="/reports" className="mb-2 inline-flex items-center gap-1 text-xs font-medium text-slate-500 hover:text-ink-900"><ChevronLeft className="h-3.5 w-3.5" />Reports</Link>
      <div className="mb-4 flex flex-wrap items-end justify-between gap-3">
        <div><div className="label">Report preview</div><h1 className="mt-1 text-[22px] font-semibold tracking-tight">{r.title}</h1>
          <div className="mt-1 flex flex-wrap items-center gap-2 text-xs text-slate-500"><span>{fmtDate(r.created_at)}</span><Badge tone={r.kind === "scenario" ? "violet" : "blue"}>{r.kind}</Badge>
            {r.redacted && <Badge tone="amber">redacted</Badge>}<span>PDF SHA-256 <Hash value={r.sha256} /></span></div></div>
        <div className="flex flex-wrap gap-2"><Link to={`/cases/${r.case_id}/overview`} className="btn-outline">Open case</Link>
          {["pdf", "docx", "html"].map((f) => <button key={f} className={f === "pdf" ? "btn-primary" : "btn-outline"} onClick={() => dl(f)}><Download className="h-4 w-4" />{f.toUpperCase()}</button>)}</div>
      </div>
      <Tabs value={tab} onChange={setTab} tabs={[{ id: "html", label: "Report view (linked citations)" }, { id: "pdf", label: "PDF" }]} />
      <div className="pt-4">
        {tab === "pdf" ? (
          <div className="card overflow-hidden">{pdfErr ? <div className="p-4"><ErrorBox error={pdfErr} /></div> : pdf ? <iframe title="report" src={pdf} className="h-[80vh] w-full" /> : <Loading label="Rendering PDF" />}</div>
        ) : !sections.length ? (
          <ErrorBox error="This report was generated before structured reports were introduced; open the PDF tab." />
        ) : (
          <div className="grid gap-4 xl:grid-cols-[220px_1fr]">
            <nav className="card sticky top-4 hidden max-h-[80vh] overflow-auto p-3 text-xs xl:block scrollbar-thin">
              {sections.map((s) => <a key={s.n} href={`#sec-${s.n}`} className="block rounded px-2 py-1 text-slate-600 hover:bg-slate-100 hover:text-slate-900">{s.n}. {s.title}</a>)}
            </nav>
            <div className="space-y-4">
              <div className="card p-4 text-xs text-slate-600">Citations <span className="mono">[EV-code | location]</span> open the exact evidence location. <Badge tone="blue">ENGINE</Badge> agent/rule output requiring review · <Badge tone="green">HUMAN</Badge> reviewer decision · <Badge>SYSTEM</Badge> platform record.</div>
              {sections.map((s) => (
                <section key={s.n} id={`sec-${s.n}`} className="card scroll-mt-4 p-5">
                  <div className="mb-3 flex items-center gap-2"><h2 className="text-base font-semibold">{s.n}. {s.title}</h2><Badge tone={LABEL_TONE[s.label] || "slate"}>{s.label}</Badge></div>
                  <div className="space-y-3 text-sm">{s.blocks.map((b: any, i: number) => (
                    b.type === "para" ? <p key={i} className="text-slate-700">{b.text}</p> :
                    b.type === "list" ? <ul key={i} className="list-disc space-y-0.5 pl-5 text-slate-700">{b.items.map((x: string, j: number) => <li key={j}>{x}</li>)}</ul> :
                    b.type === "table" ? (
                      <div key={i} className="overflow-x-auto"><table className="w-full text-xs"><thead><tr>{b.columns.map((h: string, j: number) => <th key={j} className="label border-b border-slate-200 py-1.5 pr-2 text-left">{h}</th>)}</tr></thead>
                        <tbody className="divide-y divide-slate-200">{b.rows.map((row: any[], j: number) => <tr key={j}>{row.map((v, k) => <td key={k} className="max-w-md break-words py-1.5 pr-2 align-top text-slate-700"><Cell v={v} /></td>)}</tr>)}</tbody></table></div>) :
                    b.type === "card" ? (
                      <div key={i} className="rounded-lg border border-slate-200"><div className="border-b border-slate-200 bg-slate-100 px-3 py-1.5 text-xs font-semibold">{b.title}</div>
                        <table className="w-full text-xs"><tbody className="divide-y divide-slate-200">{b.rows.map((row: any[], j: number) => (
                          <tr key={j}><th className="w-36 px-3 py-1.5 text-left align-top text-slate-500">{row[0]}</th><td className="px-3 py-1.5 text-slate-700"><Cell v={row[1]} /></td></tr>))}</tbody></table></div>) : null))}
                  </div>
                </section>))}
            </div>
          </div>)}
      </div>
    </div>
  );
}
