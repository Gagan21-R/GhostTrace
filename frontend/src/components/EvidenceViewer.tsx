import clsx from "clsx";
import { Download, FileText, ShieldCheck, ShieldAlert } from "lucide-react";
import { createContext, useContext, useEffect, useRef, useState, type ReactNode } from "react";
import { api } from "../lib/api";
import { fmtBytes, fmtDate, titleCase } from "../lib/hooks";
import { Badge, Drawer, ErrorBox, Hash, Loading, Tabs, statusTone } from "./ui";

interface Ctx { open: (evidenceId: string, segmentId?: string | null) => void }
const ViewerCtx = createContext<Ctx>({ open: () => {} });
export const useEvidenceViewer = () => useContext(ViewerCtx);

export function EvidenceViewerProvider({ children }: { children: ReactNode }) {
  const [target, setTarget] = useState<{ id: string; seg?: string | null } | null>(null);
  return (
    <ViewerCtx.Provider value={{ open: (id, seg) => setTarget({ id, seg }) }}>
      {children}
      <Drawer open={!!target} onClose={() => setTarget(null)} title="Evidence item" width="max-w-4xl">
        {target && <Viewer id={target.id} segmentId={target.seg} />}
      </Drawer>
    </ViewerCtx.Provider>
  );
}

/** Clickable source reference used everywhere a finding cites evidence. */
export function SourceRef({ src, className }: { src: { evidence_id?: string; evidence_code?: string; locator?: string; segment_id?: string | null; filename?: string } | null | undefined; className?: string }) {
  const { open } = useEvidenceViewer();
  if (!src?.evidence_id) return null;
  return (
    <button onClick={() => open(src.evidence_id!, src.segment_id)} title={src.filename}
      className={clsx("inline-flex items-center gap-1 rounded border border-slate-200 bg-slate-50 px-1.5 py-0.5 mono text-[11px] text-slate-700 hover:border-accent-500 hover:bg-accent-50 hover:text-accent-700", className)}>
      <FileText className="h-3 w-3" />{src.evidence_code}{src.locator ? ` · ${src.locator}` : ""}
    </button>
  );
}

export function Viewer({ id, segmentId }: { id: string; segmentId?: string | null }) {
  const [ev, setEv] = useState<any>(null);
  const [err, setErr] = useState<string | null>(null);
  const [preview, setPreview] = useState<{ url: string; type: string } | null>(null);
  const [tab, setTab] = useState("content");
  const [verify, setVerify] = useState<any>(null);
  const segRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    setEv(null); setPreview(null); setVerify(null); setTab("content");
    api.get<any>(`/api/evidence/${id}`).then(setEv).catch((e) => setErr(e.message));
  }, [id]);
  useEffect(() => {
    if (!ev) return;
    if (["image", "pdf", "audio", "video"].includes(ev.type)) api.blobUrl(`/api/evidence/${id}/file`).then(setPreview).catch(() => {});
  }, [ev, id]);
  useEffect(() => { segRef.current?.scrollIntoView({ block: "center", behavior: "smooth" }); }, [ev, tab]);
  useEffect(() => () => { if (preview) URL.revokeObjectURL(preview.url); }, [preview]);

  if (err) return <div className="p-5"><ErrorBox error={err} /></div>;
  if (!ev) return <Loading />;
  const ext = ev.extraction || {};
  return (
    <div className="p-5">
      <div className="mb-4 flex flex-wrap items-start justify-between gap-3">
        <div>
          <div className="flex items-center gap-2"><Badge tone="dark">{ev.code}</Badge><span className="font-semibold">{ev.filename}</span></div>
          <div className="mt-1.5 flex flex-wrap gap-1.5 text-xs text-slate-500">
            <Badge tone="blue">{ev.type}</Badge><Badge>{ev.category}</Badge><Badge tone={statusTone(ev.status)}>{ev.status}</Badge>
            <span>{fmtBytes(ev.size)}</span><span>· intake {fmtDate(ev.intake_at)}</span>
          </div>
        </div>
        <div className="flex gap-2">
          <button className="btn-outline" onClick={async () => setVerify(await api.post(`/api/evidence/${id}/verify`))}><ShieldCheck className="h-4 w-4" />Verify hash</button>
          <button className="btn-outline" onClick={() => api.download(`/api/evidence/${id}/file`, ev.filename)}><Download className="h-4 w-4" />Original</button>
          {!location.pathname.startsWith("/evidence/") && <a className="btn-ghost" href={`/evidence/${id}${segmentId ? `?segment=${segmentId}` : ""}`}>Full page</a>}
        </div>
      </div>
      {verify && (
        <div className={clsx("mb-4 rounded-lg border p-3 text-sm", verify.result === "match" ? "border-emerald-200 bg-emerald-50 text-emerald-800" : "border-rose-200 bg-rose-50 text-rose-800")}>
          <div className="flex items-center gap-2 font-medium">{verify.result === "match" ? <ShieldCheck className="h-4 w-4" /> : <ShieldAlert className="h-4 w-4" />}
            {verify.result === "match" ? "Stored file matches the intake hash" : `Integrity check: ${verify.result.toUpperCase()}`}</div>
          <div className="mt-1 text-xs opacity-80">{verify.note}</div>
        </div>
      )}
      {ev.injection_indicators?.length > 0 && (
        <div className="mb-4 rounded-lg border border-amber-200 bg-amber-50 p-3 text-xs text-amber-900">
          <b>Embedded instructions detected:</b> {ev.injection_indicators.join(", ")}. Evidence content is treated as data only and never followed by the agents.
        </div>
      )}
      <Tabs value={tab} onChange={setTab} tabs={[{ id: "content", label: `Extracted content (${ev.segment_list.length})` }, { id: "preview", label: "Preview" },
        { id: "meta", label: "Metadata & integrity" }, { id: "history", label: `Processing history (${ev.history.length})` }]} />
      <div className="pt-4">
        {tab === "content" && (
          <div className="space-y-1.5">
            {ext.unavailable_engine && <ErrorBox error={`Extraction engine unavailable (${ext.unavailable_engine}). ${ev.processing_error || ""}`} />}
            {ev.segment_list.length === 0 && <div className="text-sm text-slate-500">No extracted content yet. Run processing on the case.</div>}
            {ev.segment_list.map((s: any) => (
              <div key={s.id} ref={s.id === segmentId ? segRef : undefined}
                className={clsx("rounded-lg border px-3 py-2 text-sm", s.id === segmentId ? "border-accent-500 bg-accent-50 ring-2 ring-accent-500/20" : "border-slate-200")}>
                <div className="mb-1 flex flex-wrap items-center gap-2 text-[11px] text-slate-500">
                  <span className="mono font-medium text-slate-700">{s.locator}</span><span>{s.kind}</span>
                  {s.author && <span>· {s.author}</span>}{s.timestamp_raw && <span>· {s.timestamp_raw}</span>}
                  <span className="ml-auto">{s.method} · conf {Math.round(s.confidence * 100)}%</span>
                </div>
                <div className="whitespace-pre-wrap break-words text-slate-800">{s.text || <i className="text-slate-400">(empty)</i>}</div>
                {s.data?.attachments?.length > 0 && <div className="mt-1 text-xs text-slate-500">Attachments: {s.data.attachments.map((a: any) => `${a.name || a.filename}${a.included === false ? " (not included)" : ""}`).join(", ")}</div>}
              </div>
            ))}
          </div>
        )}
        {tab === "preview" && (
          <div>
            {!preview && !["image", "pdf", "audio", "video"].includes(ev.type) && <div className="text-sm text-slate-500">Inline preview is available for images, PDFs, audio and video. Text-based evidence is shown under Extracted content.</div>}
            {preview && ev.type === "image" && <img src={preview.url} alt={ev.filename} className="max-h-[70vh] rounded-lg border" />}
            {preview && ev.type === "pdf" && <iframe src={preview.url} title="pdf" className="h-[70vh] w-full rounded-lg border" />}
            {preview && ev.type === "audio" && <audio controls src={preview.url} className="w-full" />}
            {preview && ev.type === "video" && <video controls src={preview.url} className="w-full rounded-lg" />}
          </div>
        )}
        {tab === "meta" && (
          <div className="grid gap-3 text-sm">
            <Meta k="SHA-256 (intake)"><Hash value={ev.sha256} short={false} /></Meta>
            <Meta k="Last verification">{ev.last_verification ? <Badge tone={statusTone(ev.last_verification)}>{ev.last_verification}</Badge> : "—"} {fmtDate(ev.last_verified_at)}</Meta>
            <Meta k="MIME type">{ev.mime_type}</Meta>
            <Meta k="Collection source">{ev.collection_source || <span className="text-amber-700">Not recorded</span>}</Meta>
            <Meta k="Collected by / at">{ev.collected_by || "—"} {ev.collected_at ? `· ${ev.collected_at}` : ""}</Meta>
            <Meta k="Extraction">{ext.method || "—"} {ext.segments != null && `· ${ext.segments} segments · ${ext.duration_ms} ms`}</Meta>
            {ext.warnings?.length > 0 && <Meta k="Warnings">{ext.warnings.join("; ")}</Meta>}
            <Meta k="Derivatives">{ev.derivatives.length === 0 ? "None" : ev.derivatives.map((d: any) => (
              <div key={d.id} className="flex items-center gap-2"><Badge tone="violet">{d.kind}</Badge><Hash value={d.sha256} />
                <button className="text-xs text-accent-700 hover:underline" onClick={() => api.download(`/api/evidence/${id}/file?derivative=${d.id}`, `${ev.code}_${d.kind}.txt`)}>download</button></div>))}
              <div className="mt-1 text-xs text-slate-500">Derivatives are stored separately; the original is never modified.</div></Meta>
            <Meta k="File metadata"><pre className="max-h-64 overflow-auto rounded bg-slate-50 p-2 mono text-[11px]">{JSON.stringify(Object.fromEntries(Object.entries(ev.metadata || {}).filter(([k]) => k !== "extraction")), null, 2)}</pre></Meta>
          </div>
        )}
        {tab === "history" && (
          <ol className="relative ml-2 border-l border-slate-200">
            {ev.history.map((h: any, i: number) => (
              <li key={i} className="mb-3 ml-4"><span className="absolute -left-1.5 mt-1.5 h-3 w-3 rounded-full border-2 border-white bg-slate-400" />
                <div className="text-sm font-medium">{titleCase(h.action.replace(".", " "))}</div>
                <div className="text-xs text-slate-500">{fmtDate(h.ts)} · {h.user}</div>
                {h.detail && Object.keys(h.detail).length > 0 && <div className="mono mt-0.5 text-[11px] text-slate-500">{JSON.stringify(h.detail).slice(0, 220)}</div>}</li>))}
          </ol>
        )}
      </div>
    </div>
  );
}

function Meta({ k, children }: { k: string; children: ReactNode }) {
  return <div className="grid grid-cols-[170px_1fr] gap-3 border-b border-slate-100 pb-2"><div className="label pt-0.5">{k}</div><div className="min-w-0 break-words">{children}</div></div>;
}
