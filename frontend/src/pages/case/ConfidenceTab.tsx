import { motion } from "framer-motion";
import { AlertTriangle, FileDown, Gauge } from "lucide-react";
import { Link } from "react-router-dom";
import { Empty, ErrorBox, Loading, Section } from "../../components/ui";
import { t } from "../../lib/i18n";
import { useApi } from "../../lib/hooks";
import { useCase } from "./CaseWorkspace";

const bandColor = (s: number) => (s >= 80 ? "#16a34a" : s >= 60 ? "#f59e0b" : "#e11d48");

export function ConfidenceGauge({ score, size = 180 }: { score: number; size?: number }) {
  const r = size / 2 - 14, c = 2 * Math.PI * r, col = bandColor(score);
  return (
    <svg width={size} height={size} viewBox={`0 0 ${size} ${size}`} role="img" aria-label={`Confidence ${score} of 100`}>
      <circle cx={size / 2} cy={size / 2} r={r} fill="#fffdf6" stroke="#0b0b0b" strokeWidth={3} />
      <circle cx={size / 2} cy={size / 2} r={r} fill="none" stroke="#e5dfcf" strokeWidth={14} />
      <motion.circle cx={size / 2} cy={size / 2} r={r} fill="none" stroke={col} strokeWidth={14} strokeLinecap="butt"
        transform={`rotate(-90 ${size / 2} ${size / 2})`} strokeDasharray={c}
        initial={{ strokeDashoffset: c }} animate={{ strokeDashoffset: c * (1 - score / 100) }} transition={{ duration: 1.1, ease: "easeOut" }} />
      <text x="50%" y="50%" textAnchor="middle" dominantBaseline="central" className="font-display" fontSize={size / 3.6} fill="#0b0b0b">{score}</text>
      <text x="50%" y={size / 2 + size / 5.2} textAnchor="middle" fontSize={11} fontWeight={700} fill="#4a463e">/ 100</text>
    </svg>
  );
}

/** Compact version shown at the end of the Processing tab. */
export function ConfidenceSummary({ caseId }: { caseId: string }) {
  const { data } = useApi<any>(`/api/cases/${caseId}/confidence`);
  if (!data || data.score == null) return null;
  return (
    <Link to={`/cases/${caseId}/confidence`} className="card card-lift flex items-center gap-4 p-3">
      <ConfidenceGauge score={data.score} size={86} />
      <div>
        <div className="label">{t("Overall confidence")}</div>
        <div className="font-display text-xl uppercase" style={{ color: bandColor(data.score) }}>{t(data.band)}</div>
        {data.weakest?.length > 0 && <div className="text-xs text-slate-600">{t("Check these first")}: {data.weakest.map(t).join(", ")}</div>}
      </div>
    </Link>
  );
}

export default function ConfidenceTab() {
  const { c } = useCase();
  const { data, error, loading, reload } = useApi<any>(`/api/cases/${c.id}/confidence`);
  if (loading && !data) return <Loading />;
  if (error) return <ErrorBox error={error} onRetry={reload} />;
  if (!data || data.score == null) return <Empty icon={<Gauge className="h-5 w-5" />} title="No confidence report yet" hint="Process the evidence first." />;
  return (
    <div className="space-y-5">
      <div className="card grid items-center gap-6 p-5 md:grid-cols-[auto_1fr]">
        <ConfidenceGauge score={data.score} />
        <div>
          <div className="label">{t("Model confidence report")}</div>
          <div className="font-display text-4xl uppercase" style={{ color: bandColor(data.score) }}>{t(data.band)}</div>
          <p className="mt-1 text-sm text-slate-600">{t("How far the model's output for this case can be trusted.")}</p>
          {data.weakest?.length > 0 && (
            <div className="mt-3 flex items-start gap-2 border-2 border-ink-900 bg-acid/40 p-2 text-sm">
              <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0" /><span><b>{t("Check these first")}:</b> {data.weakest.map(t).join(", ")}</span></div>)}
          <Link to={`/cases/${c.id}/reports`} className="btn-outline mt-3"><FileDown className="h-4 w-4" />{t("Download report (PDF)")}</Link>
        </div>
      </div>
      <Section title="Confidence" topic="confidence">
        <div className="space-y-3">
          {data.components.map((k: any, i: number) => (
            <motion.div key={k.key} initial={{ opacity: 0, x: -10 }} animate={{ opacity: 1, x: 0 }} transition={{ delay: i * 0.06 }}>
              <div className="flex items-center justify-between text-sm"><b>{t(k.name)}</b>
                <span className="mono text-xs text-slate-500">{t("weight")} {Math.round(k.weight * 100)}% · <b className="text-ink-900">{k.score}/100</b></span></div>
              <div className="mt-1 h-3.5 border-2 border-ink-900 bg-surface">
                <motion.div className="h-full" style={{ background: bandColor(k.score) }} initial={{ width: 0 }} animate={{ width: `${k.score}%` }} transition={{ duration: 0.8, delay: i * 0.06 }} /></div>
              <div className="mt-0.5 text-xs text-slate-600">{k.detail}</div>
            </motion.div>))}
        </div>
        {data.missing?.length > 0 && <div className="mt-4 text-xs text-slate-500"><b>{t("Not measured in this case")}:</b> {data.missing.map(t).join(", ")}</div>}
        <ul className="mt-3 list-disc space-y-0.5 pl-5 text-xs text-slate-600">{data.notes.map((n: string) => <li key={n}>{n}</li>)}</ul>
      </Section>
    </div>
  );
}
