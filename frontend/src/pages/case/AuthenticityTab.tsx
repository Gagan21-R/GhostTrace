import clsx from "clsx";
import { motion } from "framer-motion";
import { AlertTriangle, CheckCircle2, ChevronDown, Fingerprint, HelpCircle, Play, ShieldAlert, Terminal, Wrench } from "lucide-react";
import { t } from "../../lib/i18n";
import { useState } from "react";
import { Badge, Empty, ErrorBox, Loading, Section } from "../../components/ui";
import { api } from "../../lib/api";
import { titleCase, useApi } from "../../lib/hooks";
import { useCase } from "./CaseWorkspace";

const VERDICT_STYLE: Record<string, { bg: string; icon: any }> = {
  likely_fabricated: { bg: "bg-flame text-white", icon: AlertTriangle },
  possible_impersonation: { bg: "bg-volt text-white", icon: ShieldAlert },
  consistent_with_account_holder: { bg: "bg-acid text-ink-900", icon: CheckCircle2 },
  insufficient_evidence: { bg: "bg-slate-300 text-ink-900", icon: HelpCircle },
};
const KIND = {
  fabrication: { label: "Fake screenshot signs", color: "#ff4f1f" },
  compromise: { label: "Someone else used the account", color: "#2b4bff" },
  authentic: { label: "Account holder sent it", color: "#7a8f00" },
} as const;
export const LABEL_COLOR: Record<string, string> = {
  harassment: "#ff4f1f", extortion: "#b91c1c", financial_fraud: "#d97706", phishing: "#7c3aed", credential_request: "#2b4bff", benign: "#64748b",
};

export default function AuthenticityTab() {
  const { c } = useCase();
  const a = useApi<any>(`/api/cases/${c.id}/authenticity`);
  const cls = useApi<any>(`/api/cases/${c.id}/classifications`);
  if (a.loading && !a.data) return <Loading />;
  if (a.error) return <ErrorBox error={a.error} onRetry={a.reload} />;
  const items = a.data?.assessments || [];
  return (
    <div className="space-y-5">
      {items.length === 0 ? (
        <Empty icon={<Fingerprint className="h-5 w-5" />} title="No disputed chat screenshots"
          hint="When a case has a chat screenshot with a threatening or suspicious message, the authenticity agent checks it here." />
      ) : items.map((x: any, i: number) => <Assessment key={x.id} x={x} i={i} />)}
      <Labels data={cls.data} />
      <ToolConsole caseId={c.id} />
    </div>
  );
}

function Meter({ label, value, color }: { label: string; value: number; color: string }) {
  return (
    <div>
      <div className="flex justify-between text-[11px] font-bold uppercase tracking-wide"><span>{t(label)}</span><span>{Math.round(value * 100)}%</span></div>
      <div className="mt-1 h-3 border-2 border-ink-900 bg-surface">
        <motion.div className="h-full" style={{ background: color }} initial={{ width: 0 }} animate={{ width: `${value * 100}%` }} transition={{ duration: 0.8 }} />
      </div>
    </div>
  );
}

function Assessment({ x, i }: { x: any; i: number }) {
  const [trace, setTrace] = useState(false);
  const V = VERDICT_STYLE[x.verdict] || VERDICT_STYLE.insufficient_evidence;
  const Icon = V.icon;
  return (
    <motion.div className="card" initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: i * 0.08 }}>
      <div className={clsx("flex flex-wrap items-center gap-3 border-b-2 border-ink-900 px-4 py-3", V.bg)}>
        <Icon className="h-6 w-6" />
        <div className="font-display text-lg uppercase">{t(x.verdict_label)}</div>
        <span className="ml-auto text-xs font-bold uppercase opacity-80">{x.code} · {x.mode.replace(/-/g, " ")}</span>
      </div>
      <div className="grid gap-5 p-4 lg:grid-cols-[1.2fr_1fr]">
        <div>
          <blockquote className="border-l-4 border-ink-900 bg-paper px-3 py-2 text-base font-semibold">“{x.disputed_text}”</blockquote>
          <div className="mt-1 text-xs text-slate-600">{t("Shown as from")} <b>{x.claimed_sender || "unknown"}</b>{x.message_time && <> · {x.message_time}</>}</div>
          <ul className="mt-4 space-y-2">
            {x.indicators.map((ind: any, k: number) => {
              const K = KIND[ind.kind as keyof typeof KIND];
              return (
                <li key={k} className="flex gap-2 text-sm">
                  <span className="mt-1 h-3 w-3 shrink-0 border-2 border-ink-900" style={{ background: K?.color }} />
                  <span>{ind.text} {ind.refs?.length > 0 && <span className="mono text-slate-500">[{ind.refs.join(", ")}]</span>}</span>
                </li>);
            })}
          </ul>
        </div>
        <div className="space-y-3">
          <Meter label={KIND.fabrication.label} value={x.scores.fabrication} color={KIND.fabrication.color} />
          <Meter label={KIND.compromise.label} value={x.scores.compromise} color={KIND.compromise.color} />
          <Meter label={KIND.authentic.label} value={x.scores.authentic} color={KIND.authentic.color} />
          <div className="pt-2">
            <div className="label mb-1">{t("Next steps")}</div>
            <ul className="list-disc space-y-0.5 pl-5 text-xs text-slate-700">{x.recommendations.slice(0, 4).map((r: string, k: number) => <li key={k}>{r}</li>)}</ul>
          </div>
        </div>
      </div>
      <button onClick={() => setTrace(!trace)} className="flex w-full items-center gap-2 border-t-2 border-ink-900 px-4 py-2 text-left text-xs font-bold uppercase tracking-wide hover:bg-acid/40">
        <Wrench className="h-4 w-4" />{t("Agent called")} {x.tool_trace.length} {t("tools")}<ChevronDown className={clsx("ml-auto h-4 w-4 transition", trace && "rotate-180")} />
      </button>
      {trace && <Trace steps={x.tool_trace} />}
    </motion.div>
  );
}

function Trace({ steps }: { steps: any[] }) {
  const [open, setOpen] = useState<number | null>(null);
  return (
    <ol className="relative space-y-2 border-t border-slate-200 p-4 pl-8">
      <span className="absolute bottom-6 left-[19px] top-6 w-0.5 bg-ink-900" />
      {steps.map((s, k) => (
        <motion.li key={k} initial={{ opacity: 0, x: -8 }} animate={{ opacity: 1, x: 0 }} transition={{ delay: k * 0.05 }} className="relative">
          <span className={clsx("absolute -left-[18px] top-1.5 h-3 w-3 border-2 border-ink-900", s.status === "ok" ? "bg-acid" : "bg-flame")} />
          <button className="w-full text-left" onClick={() => setOpen(open === k ? null : k)}>
            <span className="mono font-bold">{s.tool}</span><span className="mono text-slate-500">({Object.keys(s.input || {}).join(", ")})</span>
            <span className="ml-2 text-xs text-slate-600">{s.why}</span><span className="ml-2 text-[11px] text-slate-400">{s.ms} ms</span>
          </button>
          {open === k && <pre className="mt-1 max-h-60 overflow-auto border-2 border-ink-900 bg-ink-900 p-2 text-[11px] text-acid">{JSON.stringify({ input: s.input, output: s.output }, null, 2)}</pre>}
        </motion.li>))}
    </ol>
  );
}

function Labels({ data }: { data: any }) {
  const [all, setAll] = useState(false);
  if (!data) return null;
  const rows = (data.items || []).filter((r: any) => all || (r.scope === "message" && r.label !== "benign"));
  return (
    <Section title="Message labels (Naive Bayes)" topic="naive_bayes"
      actions={<label className="flex items-center gap-1 text-xs"><input type="checkbox" checked={all} onChange={(e) => setAll(e.target.checked)} />{t("show whole files")}</label>}>
      {rows.length === 0 ? <div className="text-sm text-slate-500">{t("No message was flagged.")}</div> : (
        <div className="space-y-2">
          {rows.slice(0, 40).map((r: any) => (
            <div key={r.id} className="flex flex-wrap items-center gap-2 border-b border-slate-200 pb-2 text-sm last:border-0">
              <span className="border-2 border-ink-900 px-1.5 text-[11px] font-bold uppercase text-white" style={{ background: LABEL_COLOR[r.label] }}>{t(r.label_name)}</span>
              {r.language && r.language !== "en" && <span className="chip border border-ink-900 text-[10px] font-bold">{r.language_name}</span>}
              <span className="mono text-xs text-slate-500">{r.code} {r.locator}</span>
              <span className="min-w-0 flex-1 truncate">{r.author && <b>{r.author}: </b>}{r.text}</span>
              <span className="text-xs font-bold">{Math.round(r.confidence * 100)}%</span>
              {r.top_terms?.slice(0, 3).map((t: any) => <Badge key={t.term}>{t.term}</Badge>)}
            </div>))}
        </div>)}
    </Section>
  );
}

function ToolConsole({ caseId }: { caseId: string }) {
  const tools = useApi<any>("/api/tools");
  const [name, setName] = useState("search_message_exports");
  const [input, setInput] = useState('{"text": "", "sender": ""}');
  const [out, setOut] = useState<any>(null);
  const [busy, setBusy] = useState(false);
  const list = (tools.data?.tools || []).filter((x: any) => x.category === "case");
  const tool = list.find((x: any) => x.name === name);
  const pick = (n: string) => {
    setName(n);
    const props = list.find((x: any) => x.name === n)?.input_schema?.properties || {};
    setInput(JSON.stringify(Object.fromEntries(Object.keys(props).map((k) => [k, props[k].type === "integer" ? 60 : ""]))));
    setOut(null);
  };
  const run = async () => {
    setBusy(true);
    try {
      const body = JSON.parse(input || "{}");
      Object.keys(body).forEach((k) => (body[k] === "" ? delete body[k] : null));
      setOut(await api.post(`/api/cases/${caseId}/tools/${name}`, { input: body }));
    } catch (e: any) { setOut({ error: e.message }); } finally { setBusy(false); }
  };
  return (
    <Section title={<span className="inline-flex items-center gap-2"><Terminal className="h-4 w-4" />{t("Tool console")}</span>} topic="tool_calling">
      <div className="flex flex-wrap gap-1.5">{list.map((x: any) => (
        <button key={x.name} onClick={() => pick(x.name)} className={clsx("chip border-2 border-ink-900 mono", name === x.name ? "bg-acid" : "bg-surface")}>{x.name}</button>))}</div>
      {tool && <p className="mt-2 text-xs text-slate-600">{tool.description}</p>}
      <div className="mt-2 flex gap-2">
        <input className="input mono text-xs" value={input} onChange={(e) => setInput(e.target.value)} />
        <button className="btn-primary" disabled={busy} onClick={run}><Play className="h-4 w-4" />{t("Call")}</button>
      </div>
      {out && <pre className="mt-2 max-h-72 overflow-auto border-2 border-ink-900 bg-ink-900 p-2 text-[11px] text-acid">{JSON.stringify(out.output ?? out, null, 2)}</pre>}
      <p className="mt-2 text-[11px] text-slate-500">{titleCase("read-only")} · every call is written to the audit log.</p>
    </Section>
  );
}
