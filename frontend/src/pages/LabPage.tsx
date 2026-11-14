import clsx from "clsx";
import { motion } from "framer-motion";
import { Brain, Wand2, Wrench } from "lucide-react";
import { t } from "../lib/i18n";
import { useState } from "react";
import { PageHeader, Section } from "../components/ui";
import { api } from "../lib/api";
import { useApi } from "../lib/hooks";
import { LABEL_COLOR } from "./case/AuthenticityTab";

const NAMES: Record<string, string> = {
  harassment: "Harassment / threat", extortion: "Extortion / blackmail", financial_fraud: "Financial fraud / payment scam",
  phishing: "Phishing / fake verification", credential_request: "OTP / password request", benign: "Ordinary conversation",
};
const SAMPLES = [
  "I know where you live. You will regret this.",
  "Send me the 6 digit code that came on your phone, sent by mistake",
  "Pay 20000 tonight or I share your photos with everyone",
  "Your KYC is pending, click the link or your account will be blocked",
  "Complete simple tasks and earn 5000 daily, deposit 1000 to unlock",
  "Are we still meeting for lunch tomorrow?",
  "मुझे पता है तुम कहाँ रहती हो, तुम पछताओगी",
  "ನಿಮಗೆ ಬಂದ ಓಟಿಪಿ ನನಗೆ ಕಳಿಸಿ, ತಪ್ಪಾಗಿ ಬಂತು",
  "paise bhej warna video viral kar dunga",
];

export default function LabPage() {
  const card = useApi<any>("/api/nb/model");
  const tools = useApi<any>("/api/tools");
  const [text, setText] = useState(SAMPLES[0]);
  const [res, setRes] = useState<any>(null);
  const [busy, setBusy] = useState(false);
  const run = async (t = text) => { setBusy(true); try { setRes(await api.post("/api/nb/classify", { text: t })); } finally { setBusy(false); } };
  const m = card.data;
  return (
    <div className="space-y-5">
      <PageHeader eyebrow="Models & tools" title="AI Lab" subtitle="OCR reads the words. Naive Bayes decides what they mean." topic="naive_bayes" />
      <div className="grid gap-5 lg:grid-cols-[1.3fr_1fr]">
        <Section title={<span className="inline-flex items-center gap-2"><Wand2 className="h-4 w-4" />{t("Try the classifier")}</span>} topic="naive_bayes">
          <textarea className="input h-24 text-base" value={text} onChange={(e) => setText(e.target.value)} />
          <div className="mt-2 flex flex-wrap gap-1.5">
            {SAMPLES.map((s) => <button key={s} onClick={() => { setText(s); run(s); }} className="chip border-2 border-ink-900 bg-surface text-[11px] hover:bg-acid">{s.slice(0, 28)}…</button>)}
          </div>
          <button className="btn-primary mt-3" disabled={busy || !text.trim()} onClick={() => run()}><Brain className="h-4 w-4" />{t("Classify")}</button>
          {res && (
            <motion.div initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} className="mt-4">
              <div className="flex items-center gap-3">
                <span className="border-2 border-ink-900 px-3 py-1 font-display text-lg uppercase text-white" style={{ background: LABEL_COLOR[res.label] }}>{t(res.label_name)}</span>
                <span className="font-display text-2xl">{Math.round(res.confidence * 100)}%</span>
                {res.uncertain && <span className="chip border-2 border-ink-900 bg-paper font-bold">{t("uncertain")}</span>}
                <span className="chip border-2 border-ink-900 bg-volt font-bold text-white">{t("Detected language")}: {res.language_name}</span>
              </div>
              <div className="mt-3 space-y-1.5">
                {Object.entries(res.probabilities).map(([k, v]: any) => (
                  <div key={k} className="grid grid-cols-[130px_1fr_44px] items-center gap-2 text-xs">
                    <span className="font-bold">{t(m?.classes?.[k] || NAMES[k] || k)}</span>
                    <div className="h-3 border-2 border-ink-900 bg-surface"><motion.div className="h-full" style={{ background: LABEL_COLOR[k] }} initial={{ width: 0 }} animate={{ width: `${v * 100}%` }} /></div>
                    <span className="text-right mono">{Math.round(v * 100)}%</span>
                  </div>))}
              </div>
              {res.top_terms.length > 0 && <div className="mt-3 flex flex-wrap items-center gap-1.5 text-xs"><span className="label">{t("Because of")}</span>
                {res.top_terms.map((t: any) => <span key={t.term} className="chip border-2 border-ink-900 bg-acid font-bold">{t.term}</span>)}</div>}
            </motion.div>)}
        </Section>
        <Section title="Model card" topic="naive_bayes">
          {m && (
            <div className="space-y-3 text-sm">
              <div className="grid grid-cols-2 gap-2 text-center">
                <div className="border-2 border-ink-900 p-2"><div className="font-display text-3xl">{Math.round(m.loo_accuracy * 100)}%</div><div className="text-[10px] font-bold uppercase">{t("leave-one-out accuracy")}</div></div>
                <div className="border-2 border-ink-900 p-2"><div className="font-display text-3xl">{m.training_examples}</div><div className="text-[10px] font-bold uppercase">{t("training messages")}</div></div>
              </div>
              <div className="space-y-1">{Object.entries(m.per_class_recall).map(([k, v]: any) => (
                <div key={k} className="flex items-center gap-2 text-xs"><span className="h-3 w-3 border-2 border-ink-900" style={{ background: LABEL_COLOR[k] }} />
                  <span className="flex-1">{t(m.classes[k])}</span><span className="mono">{Math.round(v * 100)}%</span></div>))}</div>
              {m.per_language && <div><div className="label mb-1">{t("Accuracy by language")}</div>
                <div className="grid grid-cols-2 gap-1.5">{Object.entries(m.per_language).map(([k, v]: any) => (
                  <div key={k} className="border-2 border-ink-900 px-2 py-1 text-xs"><b>{k}</b><div className="mono">{Math.round(v.accuracy * 100)}% · {v.examples}</div></div>))}</div></div>}
              <div className="text-xs text-slate-600">{m.features} · {m.smoothing}</div>
              <div className="border-l-4 border-flame pl-2 text-xs">{m.limits}</div>
            </div>)}
        </Section>
      </div>
      <Section title={<span className="inline-flex items-center gap-2"><Wrench className="h-4 w-4" />{t("Tools agents can call")}</span>} topic="tool_calling">
        <div className="grid gap-2 md:grid-cols-2 xl:grid-cols-3">
          {(tools.data?.tools || []).map((t: any, i: number) => (
            <motion.div key={t.name} initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: i * 0.03 }}
              className={clsx("border-2 border-ink-900 bg-surface p-3 shadow-brutal-sm")}>
              <div className="flex items-center justify-between"><span className="mono text-sm font-bold">{t.name}()</span>
                <span className={clsx("chip text-[10px] font-bold uppercase", t.category === "help" ? "bg-volt text-white" : "bg-ink-900 text-acid")}>{t.category === "help" ? "chatbot" : "case"}</span></div>
              <div className="mt-1 text-xs text-slate-600">{t.description}</div>
              <div className="mt-2 flex flex-wrap gap-1">{Object.keys(t.input_schema.properties || {}).map((p) => (
                <span key={p} className={clsx("chip border text-[10px] mono", (t.input_schema.required || []).includes(p) ? "border-ink-900 bg-acid" : "border-slate-300")}>{p}</span>))}</div>
            </motion.div>))}
        </div>
      </Section>
    </div>
  );
}
