import clsx from "clsx";
import { FileAudio, FileImage, FileSpreadsheet, FileText, Mail, MessagesSquare, Play, Search, ShieldAlert, ShieldCheck, UploadCloud, Video } from "lucide-react";
import { useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import { useEvidenceViewer } from "../../components/EvidenceViewer";
import { Badge, Empty, ErrorBox, Hash, Loading, statusTone } from "../../components/ui";
import { api } from "../../lib/api";
import { fmtBytes, fmtDate, useApi } from "../../lib/hooks";
import { useCase } from "./CaseWorkspace";
import VoiceRecorder from "../../components/VoiceRecorder";

const ICONS: Record<string, any> = { image: FileImage, pdf: FileText, docx: FileText, text: FileText, spreadsheet: FileSpreadsheet, email: Mail, chat: MessagesSquare, audio: FileAudio, video: Video };
const JUNK = /^(\.|desktop\.ini$|thumbs\.db$|\.ds_store$)/i;

/** Files from a drop, including everything inside dropped folders (recursively). */
async function filesFromDrop(dt: DataTransfer): Promise<File[]> {
  const entries = Array.from(dt.items || []).map((it) => (it as any).webkitGetAsEntry?.()).filter(Boolean);
  if (!entries.length) return Array.from(dt.files);
  const out: File[] = [];
  const walk = async (entry: any): Promise<void> => {
    if (entry.isFile) {
      out.push(await new Promise<File>((res, rej) => entry.file(res, rej)));
    } else if (entry.isDirectory) {
      const reader = entry.createReader();
      for (;;) {  // readEntries returns results in batches
        const batch: any[] = await new Promise((res, rej) => reader.readEntries(res, rej));
        if (!batch.length) break;
        for (const e of batch) await walk(e);
      }
    }
  };
  for (const e of entries) await walk(e);
  return out;
}

const ACCEPT = ".jpg,.jpeg,.png,.webp,.pdf,.docx,.txt,.md,.log,.csv,.xlsx,.eml,.json,.mp3,.wav,.webm,.ogg,.mp4";

export default function EvidenceTab() {
  const { c, reload: reloadCase, canWrite } = useCase();
  const nav = useNavigate();
  const { open } = useEvidenceViewer();
  const [q, setQ] = useState(""); const [type, setType] = useState("");
  const qs = new URLSearchParams({ ...(q && { q }), ...(type && { type }) });
  const { data, error, loading, reload } = useApi<any[]>(`/api/cases/${c.id}/evidence?${qs}`, []);
  const [drag, setDrag] = useState(false);
  const [queue, setQueue] = useState<File[]>([]);
  const [meta, setMeta] = useState({ category: "uncategorised", tags: "", collection_source: "", collected_by: "", collected_at: "" });
  const [busy, setBusy] = useState(false);
  const [progress, setProgress] = useState(0);
  const [result, setResult] = useState<any>(null);
  const [verifyAll, setVerifyAll] = useState<any>(null);
  const input = useRef<HTMLInputElement>(null);
  const folderInput = useRef<HTMLInputElement>(null);
  const addFiles = (files: File[]) => setQueue((q) => [...q, ...files.filter((f) => f.size > 0 && !JUNK.test(f.name))]);

  const upload = async () => {
    setBusy(true); setResult(null);
    const fd = new FormData();
    queue.forEach((f) => fd.append("files", f, f.name));
    Object.entries(meta).forEach(([k, v]) => fd.append(k, v));
    setProgress(0);
    try {
      const r: any = await api.uploadWithProgress(`/api/cases/${c.id}/evidence`, fd, setProgress);
      setResult(r); setQueue([]); reload(true); reloadCase(true);
      if (r.accepted > 0) {  // analyse straight away and show the live pipeline
        try { await api.post(`/api/cases/${c.id}/analyse`); } catch { /* already running: just show it */ }
        nav(`/cases/${c.id}/processing?live=1`);
      }
    }
    catch (e: any) { setResult({ error: e.message }); } finally { setBusy(false); }
  };

  return (
    <div className="grid gap-4 xl:grid-cols-[380px_1fr]">
      {canWrite && (
        <div className="space-y-3">
          <VoiceRecorder caseId={c.id} onSaved={() => { reload(); reloadCase(true); setTimeout(() => nav(`/cases/${c.id}/processing?live=1`), 1800); }} />
          <div onDragOver={(e) => { e.preventDefault(); setDrag(true); }} onDragLeave={() => setDrag(false)}
            onDrop={async (e) => { e.preventDefault(); setDrag(false); addFiles(await filesFromDrop(e.dataTransfer)); }}
            onClick={() => input.current?.click()}
            className={clsx("card flex cursor-pointer flex-col items-center justify-center border-2 border-dashed px-4 py-8 text-center transition", drag ? "border-accent-500 bg-accent-50" : "border-slate-300 hover:border-slate-400")}>
            <UploadCloud className="mb-2 h-7 w-7 text-slate-400" />
            <div className="text-sm font-medium">Drop evidence files or a whole folder here, or click to browse</div>
            <div className="mt-1 text-xs text-slate-500">Images (JPG, PNG, WEBP), PDF, DOCX, TXT, CSV, XLSX, EML, chat JSON / WhatsApp TXT, MP3, WAV, MP4 · max 100 MB each</div>
            <input ref={input} type="file" multiple accept={ACCEPT} className="hidden" onChange={(e) => { addFiles(Array.from(e.target.files || [])); e.target.value = ""; }} />
            <input ref={folderInput} type="file" multiple className="hidden" {...({ webkitdirectory: "", directory: "" } as any)}
              onChange={(e) => { addFiles(Array.from(e.target.files || [])); e.target.value = ""; }} />
            <button type="button" className="btn-outline mt-3 !py-1 text-xs" onClick={(e) => { e.stopPropagation(); folderInput.current?.click(); }}>
              Choose a folder</button>
          </div>
          {queue.length > 0 && (
            <div className="card space-y-3 p-4">
              <div className="label">{queue.length} file(s) ready</div>
              <ul className="max-h-40 space-y-1 overflow-auto text-sm">{queue.map((f, i) => (
                <li key={i} className="flex justify-between gap-2"><span className="truncate">{f.name}</span><span className="text-xs text-slate-500">{fmtBytes(f.size)}
                  <button className="ml-2 text-rose-600" onClick={() => setQueue(queue.filter((_, j) => j !== i))}>×</button></span></li>))}</ul>
              <div className="grid grid-cols-2 gap-2">
                <div><label className="label">Category</label><input className="input mt-1" value={meta.category} onChange={(e) => setMeta({ ...meta, category: e.target.value })} /></div>
                <div><label className="label">Tags</label><input className="input mt-1" placeholder="comma separated" value={meta.tags} onChange={(e) => setMeta({ ...meta, tags: e.target.value })} /></div>
              </div>
              <div><label className="label">Collection source</label><input className="input mt-1" placeholder="e.g. Exported from victim's phone (WhatsApp)" value={meta.collection_source} onChange={(e) => setMeta({ ...meta, collection_source: e.target.value })} /></div>
              <div className="grid grid-cols-2 gap-2">
                <div><label className="label">Collected by</label><input className="input mt-1" value={meta.collected_by} onChange={(e) => setMeta({ ...meta, collected_by: e.target.value })} /></div>
                <div><label className="label">Collected at</label><input className="input mt-1" type="datetime-local" value={meta.collected_at} onChange={(e) => setMeta({ ...meta, collected_at: e.target.value })} /></div>
              </div>
              <button className="btn-primary w-full justify-center" disabled={busy} onClick={upload}>
                {busy ? (progress < 1 ? `Uploading ${Math.round(progress * 100)}%` : "Validating, hashing & storing…") : "Upload & hash"}</button>
              {busy && <div className="h-1.5 overflow-hidden rounded-full bg-slate-100"><div className="h-full bg-accent-600 transition-all" style={{ width: `${Math.max(4, progress * 100)}%` }} /></div>}
            </div>)}
          {result && (
            <div className="card p-4 text-sm">
              {result.error ? <div className="text-rose-700">{result.error}</div> : <>
                <div className="font-medium">{result.accepted} accepted · {result.rejected} rejected</div>
                <ul className="mt-2 space-y-1">{result.results.map((r: any, i: number) => (
                  <li key={i} className="flex gap-2 text-xs">{r.ok ? <ShieldCheck className="h-3.5 w-3.5 shrink-0 text-emerald-600" /> : <ShieldAlert className="h-3.5 w-3.5 shrink-0 text-rose-600" />}
                    <span className="min-w-0"><b>{r.filename}</b> {r.ok ? <>→ {r.evidence.code} <Hash value={r.evidence.sha256} /></> : <span className="text-rose-700">{r.reason}</span>}</span></li>))}</ul>
                {result.accepted > 0 && <button className="btn-accent mt-3 w-full justify-center" onClick={() => nav(`/cases/${c.id}/processing`)}><Play className="h-4 w-4" />Go to processing</button>}
              </>}
            </div>)}
        </div>)}
      <div className={clsx(!canWrite && "xl:col-span-2")}>
        <div className="mb-3 flex flex-wrap gap-2">
          <div className="relative min-w-[220px] flex-1"><Search className="absolute left-3 top-2.5 h-4 w-4 text-slate-400" />
            <input className="input pl-9" placeholder="Search names, tags, extracted text or SHA-256…" value={q} onChange={(e) => setQ(e.target.value)} /></div>
          <select className="input !w-auto" value={type} onChange={(e) => setType(e.target.value)}><option value="">All types</option>
            {["image", "pdf", "docx", "text", "spreadsheet", "email", "chat", "audio", "video"].map((t) => <option key={t}>{t}</option>)}</select>
          <button className="btn-outline" onClick={async () => setVerifyAll(await api.post(`/api/cases/${c.id}/verify-all`))}><ShieldCheck className="h-4 w-4" />Verify all hashes</button>
        </div>
        {verifyAll && <div className={clsx("mb-3 rounded-lg border p-3 text-sm", verifyAll.results.every((r: any) => r.result === "match") ? "border-emerald-200 bg-emerald-50 text-emerald-800" : "border-rose-200 bg-rose-50 text-rose-800")}>
          {verifyAll.checked} originals re-hashed: {verifyAll.results.filter((r: any) => r.result === "match").length} match, {verifyAll.results.filter((r: any) => r.result !== "match").length} mismatch/missing.
          {verifyAll.results.filter((r: any) => r.result !== "match").map((r: any) => <div key={r.evidence_id} className="font-medium">{r.code} {r.filename}: {r.result}</div>)}</div>}
        {loading && !data ? <Loading /> : error ? <ErrorBox error={error} /> : data!.length === 0 ? (
          <Empty title={q || type ? "No evidence matches" : "No evidence yet"} hint="Upload files on the left. Each original is hashed with SHA-256 at intake and stored write-once." />
        ) : (
          <div className="card divide-y divide-slate-100">
            {data!.map((e) => { const Icon = ICONS[e.type] || FileText; return (
              <button key={e.id} onClick={() => open(e.id)} className="flex w-full items-center gap-3 px-4 py-3 text-left hover:bg-slate-50">
                <div className="rounded-lg bg-slate-100 p-2 text-slate-600"><Icon className="h-4 w-4" /></div>
                <div className="min-w-0 flex-1">
                  <div className="flex items-center gap-2"><span className="mono text-slate-500">{e.code}</span><span className="truncate font-medium">{e.filename}</span>
                    {e.injection_indicators?.length > 0 && <Badge tone="amber">embedded instructions</Badge>}</div>
                  <div className="mt-0.5 flex flex-wrap items-center gap-x-3 gap-y-1 text-xs text-slate-500">
                    <span>{e.type}</span><span>{fmtBytes(e.size)}</span><span>{e.category}</span><Hash value={e.sha256} />
                    {e.segments ? <span>{e.segments} segments · {e.extraction?.method}</span> : null}<span>{fmtDate(e.intake_at)}</span>
                    {!e.collection_source && <span className="text-amber-700">no collection info</span>}
                  </div>
                  {e.processing_error && <div className="mt-0.5 truncate text-xs text-amber-700">{e.processing_error}</div>}
                </div>
                <div className="flex flex-col items-end gap-1"><Badge tone={statusTone(e.status)}>{e.status}</Badge>
                  {e.last_verification && <Badge tone={statusTone(e.last_verification)}>{e.last_verification === "match" ? "hash ✓" : e.last_verification}</Badge>}</div>
              </button>); })}
          </div>)}
      </div>
    </div>
  );
}
