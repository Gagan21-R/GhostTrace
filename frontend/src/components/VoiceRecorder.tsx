import clsx from "clsx";
import { motion } from "framer-motion";
import { Loader2, Mic, RotateCcw, Square, Upload } from "lucide-react";
import { useEffect, useRef, useState } from "react";
import { api } from "../lib/api";
import { t } from "../lib/i18n";

const LANG_LABEL: Record<string, string> = { en: "English", hi: "हिन्दी (Hindi)", kn: "ಕನ್ನಡ (Kannada)" };
const LANG_COLOR: Record<string, string> = { en: "#2b4bff", hi: "#ff4f1f", kn: "#16a34a" };

/** Record a voice statement, store it as evidence, show the detected language, and re-run the analysis. */
export default function VoiceRecorder({ caseId, onSaved }: { caseId: string; onSaved?: (r: any) => void }) {
  const [state, setState] = useState<"idle" | "recording" | "recorded" | "saving" | "done">("idle");
  const [secs, setSecs] = useState(0);
  const [level, setLevel] = useState(0);
  const [blob, setBlob] = useState<Blob | null>(null);
  const [url, setUrl] = useState<string | null>(null);
  const [speaker, setSpeaker] = useState("");
  const [consent, setConsent] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  const [res, setRes] = useState<any>(null);
  const rec = useRef<MediaRecorder | null>(null);
  const stream = useRef<MediaStream | null>(null);
  const timer = useRef<number | null>(null);
  const raf = useRef<number | null>(null);

  const cleanup = () => {
    if (timer.current) window.clearInterval(timer.current);
    if (raf.current) cancelAnimationFrame(raf.current);
    stream.current?.getTracks().forEach((tr) => tr.stop());
    stream.current = null;
  };
  useEffect(() => () => { cleanup(); if (url) URL.revokeObjectURL(url); }, []); // eslint-disable-line react-hooks/exhaustive-deps

  const start = async () => {
    setErr(null); setRes(null);
    try {
      const s = await navigator.mediaDevices.getUserMedia({ audio: { echoCancellation: true, noiseSuppression: true } });
      stream.current = s;
      const mime = ["audio/webm;codecs=opus", "audio/webm", "audio/ogg;codecs=opus"].find((m) => MediaRecorder.isTypeSupported?.(m)) || "";
      const r = new MediaRecorder(s, mime ? { mimeType: mime } : undefined);
      const chunks: BlobPart[] = [];
      r.ondataavailable = (e) => e.data.size && chunks.push(e.data);
      r.onstop = () => {
        const b = new Blob(chunks, { type: r.mimeType || "audio/webm" });
        setBlob(b); setUrl(URL.createObjectURL(b)); setState("recorded"); cleanup();
      };
      r.start(250);
      rec.current = r;
      setSecs(0); setState("recording");
      timer.current = window.setInterval(() => setSecs((x) => { if (x + 1 >= 300) r.stop(); return x + 1; }), 1000);
      const ctx = new AudioContext();
      const an = ctx.createAnalyser(); an.fftSize = 512;
      ctx.createMediaStreamSource(s).connect(an);
      const buf = new Uint8Array(an.frequencyBinCount);
      const tick = () => { an.getByteTimeDomainData(buf); let m = 0; for (const v of buf) m = Math.max(m, Math.abs(v - 128)); setLevel(m / 128); raf.current = requestAnimationFrame(tick); };
      tick();
    } catch (e: any) {
      setErr(e?.name === "NotAllowedError" ? "Microphone permission was denied." : `Microphone unavailable: ${e?.message || e}`);
    }
  };
  const stop = () => rec.current?.state === "recording" && rec.current.stop();
  const reset = () => { if (url) URL.revokeObjectURL(url); setBlob(null); setUrl(null); setRes(null); setState("idle"); setSecs(0); };

  const save = async () => {
    if (!blob) return;
    setState("saving"); setErr(null);
    const f = new FormData();
    f.append("audio", blob, blob.type.includes("ogg") ? "voice.ogg" : "voice.webm");
    f.append("speaker", speaker);
    f.append("consent", String(consent));
    f.append("reanalyse", "true");
    try { const r = await api.upload<any>(`/api/cases/${caseId}/voice`, f); setRes(r); setState("done"); onSaved?.(r); }
    catch (e: any) { setErr(e.message); setState("recorded"); }
  };

  const mmss = `${String(Math.floor(secs / 60)).padStart(2, "0")}:${String(secs % 60).padStart(2, "0")}`;
  return (
    <div className="card p-4">
      <div className="flex items-center gap-2">
        <Mic className="h-4 w-4" /><span className="text-[13px] font-bold uppercase tracking-wide">{t("Record a voice statement")}</span>
      </div>
      {state !== "done" && (
        <div className="mt-3 space-y-3">
          <input className="input" placeholder={t("Speaker name (optional)")} value={speaker} onChange={(e) => setSpeaker(e.target.value)} maxLength={120} />
          <div className="flex items-center gap-3">
            {state === "recording" ? (
              <button className="btn-no" onClick={stop}><Square className="h-4 w-4" />{t("Stop")}</button>
            ) : state === "idle" ? (
              <button className="btn-primary" onClick={start}><Mic className="h-4 w-4" />{t("Start recording")}</button>
            ) : (
              <button className="btn-outline" onClick={reset} disabled={state === "saving"}><RotateCcw className="h-4 w-4" />{t("Record again")}</button>
            )}
            <span className="mono text-lg font-bold">{mmss}</span>
            {state === "recording" && <span className="flex items-center gap-1 text-xs font-bold text-flame"><span className="h-2.5 w-2.5 animate-blink rounded-full bg-flame" />REC</span>}
          </div>
          {state === "recording" && (
            <div className="flex h-8 items-end gap-0.5">{Array.from({ length: 28 }).map((_, i) => (
              <motion.span key={i} className="w-full bg-ink-900" animate={{ height: `${Math.max(8, Math.min(100, level * 100 * (0.5 + Math.abs(Math.sin(i + secs)))))}%` }} transition={{ duration: 0.1 }} />))}</div>)}
          {url && state !== "recording" && <audio controls src={url} className="w-full" />}
          {blob && (
            <>
              <label className="flex items-start gap-2 text-xs"><input type="checkbox" className="mt-0.5" checked={consent} onChange={(e) => setConsent(e.target.checked)} />
                {t("The person agreed to be recorded and to the recording being stored as evidence.")}</label>
              <button className="btn-ok w-full justify-center" disabled={!consent || state === "saving"} onClick={save}>
                {state === "saving" ? <><Loader2 className="h-4 w-4 animate-spin" />{t("Saving and detecting language…")}</> : <><Upload className="h-4 w-4" />{t("Save as evidence and re-analyse")}</>}
              </button>
            </>)}
          {err && <div className="border-2 border-flame bg-flame/10 p-2 text-xs">{err}</div>}
        </div>)}
      {state === "done" && res && (
        <motion.div initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} className="mt-3 space-y-3">
          <div className="flex flex-wrap items-center gap-2">
            <span className="mono font-bold">{res.code}</span>
            <span className="border-2 border-ink-900 px-2 py-0.5 font-display text-sm uppercase text-white" style={{ background: LANG_COLOR[res.language] || "#64748b" }}>
              {LANG_LABEL[res.language] || res.language_name}</span>
            {res.language_probability != null && <span className="text-sm font-bold">{Math.round(res.language_probability * 100)}%</span>}
          </div>
          {res.language_candidates && (
            <div className="space-y-1">{Object.entries(res.language_candidates).map(([k, v]: any) => (
              <div key={k} className="grid grid-cols-[110px_1fr_40px] items-center gap-2 text-xs">
                <span className="font-semibold">{LANG_LABEL[k]}</span>
                <div className="h-2.5 border-2 border-ink-900"><motion.div className="h-full" style={{ background: LANG_COLOR[k] }} initial={{ width: 0 }} animate={{ width: `${v * 100}%` }} /></div>
                <span className="mono text-right">{Math.round(v * 100)}%</span></div>))}</div>)}
          {res.transcript && <blockquote className="border-l-4 border-ink-900 bg-paper px-3 py-2 text-sm">{res.transcript}</blockquote>}
          <div className="text-[11px] text-slate-600 mono">SHA-256 {res.sha256?.slice(0, 16)}…</div>
          <div className={clsx("border-2 border-ink-900 p-2 text-xs font-bold", res.reanalysis?.status === "queued" ? "bg-acid" : "bg-paper")}>
            {res.reanalysis?.status === "queued" ? t("Stored. The full analysis is running again with this recording.") : res.reanalysis?.reason || t("Stored as evidence.")}
          </div>
          <button className="btn-outline w-full justify-center" onClick={reset}><Mic className="h-4 w-4" />{t("Record another")}</button>
        </motion.div>)}
    </div>
  );
}
