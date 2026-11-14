import clsx from "clsx";
import { ChevronLeft, Eye, EyeOff, FileText, Loader2, Play } from "lucide-react";
import { useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { Badge, Drawer, ErrorBox, Hash, Loading, OutcomeBadge, Section, statusTone } from "../../components/ui";
import { api } from "../../lib/api";
import { useAuth } from "../../lib/auth";
import { fmtBytes, fmtDate, titleCase, useApi } from "../../lib/hooks";

function FilePreview({ sid, file }: { sid: string; file: any }) {
  const [state, setState] = useState<{ url?: string; text?: string; type?: string; err?: string } | null>(null);
  const ext = file.file.split(".").pop().toLowerCase();
  if (!state) {
    api.blobUrl(`/api/scenarios/${sid}/files/${encodeURIComponent(file.file)}`).then(async ({ url, type }) => {
      if (["png", "jpg", "pdf", "wav"].includes(ext)) setState({ url, type });
      else if (["docx", "xlsx"].includes(ext)) setState({ text: "Binary Office document. Run the scenario to see its extracted content in the case workspace." });
      else setState({ text: await (await fetch(url)).text() });
    }).catch((e) => setState({ err: e.message }));
    return <Loading />;
  }
  if (state.err) return <ErrorBox error={state.err} />;
  return (
    <div className="p-5">
      <div className="mb-3 flex flex-wrap gap-2 text-xs"><Badge>{file.category}</Badge><span>{fmtBytes(file.size)}</span><Hash value={file.sha256} />
        <span className="text-slate-500">Collection: {file.collection_source || <b className="text-amber-700">none recorded</b>}</span></div>
      {ext === "png" || ext === "jpg" ? <img src={state.url} className="rounded-lg border" /> : ext === "pdf" ? <iframe src={state.url} className="h-[70vh] w-full rounded border" /> :
        ext === "wav" ? <audio controls src={state.url} className="w-full" /> : <pre className="whitespace-pre-wrap rounded-lg bg-slate-50 p-3 mono text-[12px]">{state.text}</pre>}
    </div>
  );
}

export default function ScenarioDetail() {
  const { scenarioId } = useParams();
  const { data: s, error, loading } = useApi<any>(`/api/scenarios/${scenarioId}`);
  const { can } = useAuth();
  const nav = useNavigate();
  const [file, setFile] = useState<any>(null); const [reveal, setReveal] = useState(false); const [busy, setBusy] = useState(false); const [err, setErr] = useState<string | null>(null);
  if (loading && !s) return <Loading />;
  if (error) return <ErrorBox error={error} />;
  const start = async () => { setBusy(true); setErr(null); try { const r = await api.post<any>(`/api/scenarios/${s.id}/run`); nav(`/scenarios/runs/${r.id}`); } catch (e: any) { setErr(e.message); setBusy(false); } };
  return (
    <div>
      <Link to="/scenarios" className="mb-2 inline-flex items-center gap-1 text-xs font-medium text-slate-500 hover:text-ink-900"><ChevronLeft className="h-3.5 w-3.5" />Scenario Lab</Link>
      <div className="mb-5 flex flex-wrap items-end justify-between gap-3">
        <div><div className="label">{s.variant_of ? "Negative control" : `Scenario ${s.number}`} · {s.difficulty}</div><h1 className="mt-1 text-[22px] font-semibold tracking-tight">{s.title}</h1></div>
        {can("scenario:run") && <button className="btn-accent !px-5 !py-2.5" onClick={start} disabled={busy}>{busy ? <Loader2 className="h-4 w-4 animate-spin" /> : <Play className="h-4 w-4" />}Start investigation</button>}
      </div>
      {err && <div className="mb-3"><ErrorBox error={err} /></div>}
      <div className="grid gap-4 xl:grid-cols-[1.3fr_1fr]">
        <div className="space-y-4">
          <div className="card overflow-hidden"><div className="bg-ink-950 px-5 py-3 text-xs font-semibold tracking-[0.2em] text-slate-300">INCIDENT BRIEFING</div>
            <div className="p-5"><p className="text-[15px] leading-relaxed text-slate-800">{s.briefing}</p>
              <div className="label mb-2 mt-5">Investigation questions</div>
              <ol className="list-decimal space-y-1 pl-5 text-sm text-slate-700">{s.questions.map((q: string, i: number) => <li key={i}>{q}</li>)}</ol></div></div>
          <Section title={`Evidence dataset · ${s.files.length} files`} actions={<span className="text-[11px] text-slate-500">Dataset SHA-256 <Hash value={s.dataset_sha256} /></span>}>
            <div className="grid gap-2 sm:grid-cols-2">{s.files.map((f: any) => (
              <button key={f.file} onClick={() => setFile(f)} className="flex items-center gap-3 rounded-lg border border-slate-200 p-3 text-left hover:border-accent-500 hover:bg-accent-50/40">
                <FileText className="h-4 w-4 shrink-0 text-slate-400" /><div className="min-w-0"><div className="truncate text-sm font-medium">{f.file}</div>
                  <div className="text-xs text-slate-500">{f.category} · {fmtBytes(f.size)}</div></div></button>))}</div>
          </Section>
        </div>
        <div className="space-y-4">
          <Section title="Ground truth" actions={<button className="btn-ghost !py-1 text-xs" onClick={() => setReveal(!reveal)}>{reveal ? <EyeOff className="h-3.5 w-3.5" /> : <Eye className="h-3.5 w-3.5" />}{reveal ? "Hide" : "Reveal"} planted items</button>}>
            <div className="mb-3 text-sm">Expected outcome: <Badge tone="blue">{s.expected_outcome}</Badge></div>
            <ul className="space-y-1.5">{s.expected_findings.map((f: any) => (
              <li key={f.id} className="flex items-start gap-2 text-sm"><span className="mono text-slate-400">{f.id}</span><span className="flex-1">{f.description}</span>
                {f.critical && <Badge tone="red">critical</Badge>}<Badge>{f.type}</Badge></li>))}</ul>
            <div className={clsx("mt-4 space-y-3 transition", !reveal && "select-none blur-sm")}>
              <div><div className="label mb-1">Planted facts</div><ul className="list-disc space-y-0.5 pl-5 text-xs text-slate-700">{s.planted_facts.map((x: string, i: number) => <li key={i}>{x}</li>)}</ul></div>
              <div><div className="label mb-1">Planted inconsistencies</div><ul className="list-disc space-y-0.5 pl-5 text-xs text-slate-700">{s.planted_inconsistencies.length ? s.planted_inconsistencies.map((x: string, i: number) => <li key={i}>{x}</li>) : <li>None — this is a control case</li>}</ul></div>
            </div>
          </Section>
          <Section title="Previous runs">
            {s.runs.length === 0 ? <div className="text-sm text-slate-500">No runs yet.</div> : (
              <ul className="divide-y divide-slate-100">{s.runs.map((r: any) => (
                <li key={r.id}><Link to={`/scenarios/runs/${r.id}`} className="flex items-center gap-3 py-2 text-sm hover:text-accent-700">
                  <span className="mono">{r.test_code}</span><OutcomeBadge outcome={r.outcome} /><Badge tone={statusTone(r.status)}>{titleCase(r.status)}</Badge>
                  <span className="ml-auto text-xs text-slate-500">{fmtDate(r.started_at)} · {(r.duration_ms / 1000).toFixed(1)} s</span></Link></li>))}</ul>)}
          </Section>
        </div>
      </div>
      <Drawer open={!!file} onClose={() => setFile(null)} title={file?.file}>{file && <FilePreview key={file.file} sid={s.id} file={file} />}</Drawer>
    </div>
  );
}
