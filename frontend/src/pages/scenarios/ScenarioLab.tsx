import { motion } from "framer-motion";
import { ArrowRight, FileUp, FlaskConical, History, Loader2 } from "lucide-react";
import { useRef, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { Badge, ErrorBox, Loading, OutcomeBadge, PageHeader, Section } from "../../components/ui";
import { api } from "../../lib/api";
import { useAuth } from "../../lib/auth";
import { titleCase, useApi } from "../../lib/hooks";

const ART: Record<number, string> = { 1: "M4 8l8 5 8-5M4 8v9h16V8M4 8l8-4 8 4", 2: "M12 3l7 3v6c0 4-3 7-7 9-4-2-7-5-7-9V6z M9 12l2 2 4-4",
  3: "M5 4h14v16H5z M8 8h8 M8 12h8 M8 16h5", 4: "M4 20h16 M6 20V10 M12 20V4 M18 20v-7", 5: "M3 7h13v10H3z M16 10h3l2 3v4h-5 M7 19a2 2 0 100-4 2 2 0 000 4z M17 19a2 2 0 100-4 2 2 0 000 4z", 6: "M12 3v18 M3 12h18" };

export default function ScenarioLab() {
  const { data, error, loading } = useApi<any[]>("/api/scenarios");
  const { can } = useAuth();
  const nav = useNavigate();
  const [files, setFiles] = useState<File[]>([]); const [gt, setGt] = useState(""); const [busy, setBusy] = useState(false); const [err, setErr] = useState<string | null>(null);
  const input = useRef<HTMLInputElement>(null);
  if (loading && !data) return <Loading />;
  if (error) return <ErrorBox error={error} />;
  return (
    <div>
      <PageHeader eyebrow="Scenario Lab" title="Investigation simulations"
        subtitle="Each scenario feeds a prepared synthetic evidence set through the same pipeline as a real case, then scores the result against a deterministic ground truth."
        actions={<Link to="/scenarios/history" className="btn-outline"><History className="h-4 w-4" />Run history & comparison</Link>} />
      <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
        {data!.map((s, i) => (
          <motion.div key={s.id} initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: i * 0.04 }}
            className="card group flex flex-col overflow-hidden">
            <div className="relative h-24 bg-ink-950 p-4 text-white">
              <svg viewBox="0 0 24 24" className="absolute right-4 top-4 h-14 w-14 text-accent-500 opacity-80" fill="none" stroke="currentColor" strokeWidth="1.3" strokeLinecap="round" strokeLinejoin="round"><path d={ART[s.number] || ART[6]} /></svg>
              <div className="text-[11px] font-semibold tracking-[0.2em] text-slate-400">{s.variant_of ? "NEGATIVE CONTROL" : `SCENARIO ${s.number}`}</div>
              <div className="mt-1 max-w-[75%] font-semibold leading-snug">{s.title}</div>
            </div>
            <div className="flex flex-1 flex-col p-4">
              <p className="text-sm text-slate-600">{s.summary}</p>
              <div className="mt-3 flex flex-wrap gap-1.5 text-xs"><Badge tone={s.difficulty === "Hard" ? "red" : s.difficulty === "Control" ? "violet" : "amber"}>{s.difficulty}</Badge>
                <Badge>{s.files} files</Badge><Badge>{s.critical_findings}/{s.expected_findings} critical findings</Badge><Badge tone="blue">expects {s.expected_outcome}</Badge></div>
              <div className="mt-2 text-[11px] text-slate-500">Formats: {s.file_types.join(", ")}</div>
              <div className="mt-auto flex items-center justify-between pt-4">
                <div className="text-xs text-slate-500">{s.last_run ? <span className="flex items-center gap-1.5">Last: <OutcomeBadge outcome={s.last_run.outcome} /> {s.last_run.status !== "completed" && titleCase(s.last_run.status)}</span> : "Not run yet"}</div>
                <div className="flex gap-1.5">
                  <Link to={`/scenarios/${s.id}`} className="btn-outline !py-1.5">Open</Link>
                  {can("scenario:run") && <button className="btn-primary !py-1.5" disabled={busy}
                    onClick={async () => { setBusy(true); setErr(null); try { const r = await api.post<any>(`/api/scenarios/${s.id}/run`); nav(`/scenarios/runs/${r.id}`); } catch (e: any) { setErr(e.message); setBusy(false); } }}>
                    Run<ArrowRight className="h-4 w-4" /></button>}
                </div>
              </div>
            </div>
          </motion.div>))}
      </div>
      {can("scenario:run") && (
        <Section title={<span className="flex items-center gap-2"><FileUp className="h-4 w-4" />Test with a custom evidence dataset</span>} className="mt-6">
          <p className="mb-3 text-sm text-slate-600">Upload your own (consented or synthetic) files.</p>
          <div className="grid gap-3 lg:grid-cols-2">
            <div className="card flex cursor-pointer flex-col items-center justify-center border-dashed p-6 text-center" onClick={() => input.current?.click()}>
              <FlaskConical className="mb-2 h-6 w-6 text-slate-400" /><div className="text-sm font-medium">{files.length ? `${files.length} file(s) selected` : "Choose files"}</div>
              <div className="mt-1 max-h-20 overflow-auto text-xs text-slate-500">{files.map((f) => f.name).join(", ")}</div>
              <input ref={input} type="file" multiple className="hidden" onChange={(e) => setFiles(Array.from(e.target.files || []))} />
            </div>
            <textarea className="input min-h-[120px] mono" placeholder='Optional ground truth, e.g. {"expected_outcome":"PASS","findings":[{"id":"F1","critical":true,"type":"entity","description":"Sender extracted","match":{"type":"email","value":"x@y.z"}}]}' value={gt} onChange={(e) => setGt(e.target.value)} />
          </div>
          {err && <div className="mt-2"><ErrorBox error={err} /></div>}
          <div className="mt-3 flex justify-end"><button className="btn-accent" disabled={!files.length || busy} onClick={async () => {
            setBusy(true); setErr(null);
            const fd = new FormData(); files.forEach((f) => fd.append("files", f, f.name)); fd.append("ground_truth", gt);
            try { const r = await api.upload<any>("/api/scenarios/custom/run", fd); nav(`/scenarios/runs/${r.id}`); } catch (e: any) { setErr(e.message); setBusy(false); }
          }}>{busy ? <Loader2 className="h-4 w-4 animate-spin" /> : <FlaskConical className="h-4 w-4" />}Run custom test</button></div>
        </Section>)}
    </div>
  );
}
