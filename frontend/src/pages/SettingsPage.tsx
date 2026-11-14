import { Bot, Cpu, Database, HardDrive, Workflow } from "lucide-react";
import { useState } from "react";
import { Badge, ErrorBox, Loading, PageHeader, Section } from "../components/ui";
import { api } from "../lib/api";
import { useAuth } from "../lib/auth";
import { useApi } from "../lib/hooks";

function Row({ k, v }: { k: string; v: React.ReactNode }) {
  return <div className="flex items-center justify-between gap-3 border-b border-slate-100 py-2 text-sm"><span className="text-slate-600">{k}</span><span className="text-right">{v}</span></div>;
}
const yes = (b: boolean, on = "available", off = "not available") => <Badge tone={b ? "green" : "slate"}>{b ? on : off}</Badge>;

export default function SettingsPage() {
  const { data: s, error, loading } = useApi<any>("/api/system/status");
  const { can, user } = useAuth();
  const [ret, setRet] = useState<string | null>(null);
  if (loading && !s) return <Loading />;
  if (error) return <ErrorBox error={error} />;
  const e = s.engines;
  return (
    <div>
      <PageHeader eyebrow="Settings" title="System configuration" subtitle="Engines and infrastructure in use." />
      <div className={`mb-4 rounded-xl border p-4 text-sm ${e.llm.configured ? "border-emerald-200 bg-emerald-50 text-emerald-900" : "border-amber-200 bg-amber-50 text-amber-900"}`}>
        <b>Analysis mode:</b> {s.llm_mode}. {!e.llm.configured && "Set ANTHROPIC_API_KEY to let the Counter-Investigation agent add LLM-suggested challenges (each one is still verified against the evidence)."}
      </div>
      <div className="grid gap-4 lg:grid-cols-2">
        <Section title={<span className="flex items-center gap-2"><Cpu className="h-4 w-4" />Extraction engines</span>}>
          <Row k="OCR (configured)" v={e.ocr.configured} /><Row k="RapidOCR (PP-OCR models, ONNX)" v={yes(e.ocr.rapidocr_installed, "installed", "missing")} />
          <Row k="PaddleOCR" v={yes(e.ocr.paddleocr_installed, "installed", "missing")} />
          <Row k="Speech-to-text (faster-whisper)" v={<>{yes(e.asr.faster_whisper_installed, "installed", "missing")} <span className="mono ml-1 text-xs">{e.asr.model}</span></>} />
          <Row k="spaCy NER" v={yes(e.nlp.spacy_installed && !e.errors?.spacy, "installed", "unavailable — rule-based extraction used")} />
          {Object.keys(e.errors || {}).length > 0 && <div className="mt-2 rounded bg-slate-50 p-2 mono text-[11px] text-slate-600">{Object.entries(e.errors).map(([k, v]) => <div key={k}>{k}: {String(v)}</div>)}</div>}
        </Section>
        <Section title={<span className="flex items-center gap-2"><Bot className="h-4 w-4" />LLM provider</span>}>
          <Row k="Provider" v={e.llm.provider} /><Row k="Model" v={<span className="mono text-xs">{e.llm.model}</span>} />
          <Row k="SDK" v={yes(e.llm.sdk_installed, "installed", "missing")} /><Row k="API key" v={yes(e.llm.configured, "configured", "not configured")} />
          <p className="mt-2 text-xs text-slate-500">The LLM never controls hashing, permissions, timestamps or PASS/FAIL.</p>
        </Section>
        <Section title={<span className="flex items-center gap-2"><Workflow className="h-4 w-4" />Orchestration</span>}>
          <Row k="Agent orchestrator" v={<Badge tone="blue">{s.orchestration.orchestrator}</Badge>} />
          <Row k="xxhash compatibility shim" v={s.orchestration.xxhash_shim_active ? <Badge tone="amber">active (native DLL blocked)</Badge> : <Badge tone="green">not needed</Badge>} />
        </Section>
        <Section title={<span className="flex items-center gap-2"><Database className="h-4 w-4" />Storage & data</span>}>
          <Row k="Database" v={s.database} /><Row k="Evidence storage" v={s.storage} /><Row k="Graph backend" v={s.graph} />
          <Row k="Max upload size" v={`${s.max_upload_mb} MB`} /><Row k="Retention" v={s.retention_days ? `${s.retention_days} days (archived cases)` : "keep indefinitely"} />
          {can("user:manage") && <div className="mt-3 flex items-center gap-2"><button className="btn-outline" onClick={async () => { const r = await api.post<any>("/api/system/retention/apply"); setRet(r.note || `${r.purged} item(s) purged`); }}><HardDrive className="h-4 w-4" />Apply retention policy</button>{ret && <span className="text-xs text-slate-600">{ret}</span>}</div>}
        </Section>
      </div>
      <div className="mt-4 text-xs text-slate-500">Signed in as {user?.email} ({user?.role}).</div>
    </div>
  );
}
