import { Activity, AlertOctagon, FileStack, FolderOpen, Gavel, HelpCircle, Plus, ShieldQuestion } from "lucide-react";
import { ct, t } from "../lib/i18n";
import { Link } from "react-router-dom";
import { Area, AreaChart, Bar, BarChart, Cell, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { Badge, Empty, ErrorBox, Loading, OutcomeBadge, PageHeader, Section, Stat, statusTone } from "../components/ui";
import { fmtDate, titleCase, useApi, usePoll } from "../lib/hooks";

const TYPE_COLORS = ["#0b0b0b", "#2b4bff", "#ff4f1f", "#e4ff3a", "#8f887a", "#14b8a6", "#a855f7", "#f59e0b", "#d6cfbd"];

export default function Dashboard() {
  const { data, error, loading, reload } = useApi<any>("/api/dashboard");
  usePoll(() => reload(true), !!data && data.stats.running_jobs > 0, 2500);
  if (loading && !data) return <Loading />;
  if (error) return <ErrorBox error={error} onRetry={reload} />;
  const s = data.stats;
  const intake = data.intake_14d.map((v: number, i: number) => ({ d: i === 13 ? "today" : `-${13 - i}d`, v }));
  const types = Object.entries(data.evidence_by_type).map(([k, v]) => ({ k, v: v as number }));
  const contra = Object.entries(data.contradictions_by_category).map(([k, v]) => ({ k: titleCase(k), v: v as number }));
  return (
    <div>
      <PageHeader eyebrow="Overview" title="Investigation workspace" subtitle="Live figures from your cases."
        actions={<Link to="/cases/new" className="btn-primary"><Plus className="h-4 w-4" />New investigation</Link>} />
      <div className="grid grid-cols-2 gap-3 md:grid-cols-4 xl:grid-cols-8">
        <Stat label="Cases" value={s.total_cases} icon={<FolderOpen className="h-4 w-4" />} />
        <Stat label="Active" value={s.active_cases} />
        <Stat label="Completed" value={s.completed_cases} tone="ok" />
        <Stat label="Evidence files" value={s.evidence_files} hint={`${s.evidence_processed} processed · ${s.pending_processing} pending`} icon={<FileStack className="h-4 w-4" />} />
        <Stat label="Contradictions" value={s.contradictions} tone={s.contradictions ? "alert" : "default"} icon={<AlertOctagon className="h-4 w-4" />} />
        <Stat label="Pending reviews" value={s.pending_reviews} tone={s.pending_reviews ? "warn" : "default"} icon={<Gavel className="h-4 w-4" />} />
        <Stat label="Open gaps" value={s.open_gaps} tone={s.open_gaps ? "warn" : "default"} icon={<ShieldQuestion className="h-4 w-4" />} />
        <Stat label="Running jobs" value={s.running_jobs} icon={<Activity className="h-4 w-4" />} />
      </div>
      {s.total_cases === 0 ? (
        <div className="mt-6"><Empty title="No investigations yet" hint="Create a case and upload evidence, or run a Scenario Lab simulation to see the full pipeline."
          action={<div className="flex gap-2"><Link to="/cases/new" className="btn-primary">Create case</Link><Link to="/scenarios" className="btn-outline">Open Scenario Lab</Link></div>} /></div>
      ) : (
        <div className="mt-6 grid gap-4 xl:grid-cols-3">
          <Section title="Evidence intake · last 14 days" className="xl:col-span-2">
            <div className="h-48"><ResponsiveContainer><AreaChart data={intake} margin={{ left: -20, right: 8, top: 6 }}>
              <defs><linearGradient id="g" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stopColor="#2b4bff" stopOpacity={0.35} /><stop offset="1" stopColor="#2b4bff" stopOpacity={0} /></linearGradient></defs>
              <XAxis dataKey="d" tick={{ fontSize: 10, fill: "#36332d" }} interval={1} axisLine={false} tickLine={false} />
              <YAxis allowDecimals={false} tick={{ fontSize: 10, fill: "#36332d" }} axisLine={false} tickLine={false} />
              <Tooltip /><Area type="monotone" dataKey="v" name="Files" stroke="#0b0b0b" strokeWidth={3} fill="url(#g)" /></AreaChart></ResponsiveContainer></div>
          </Section>
          <Section title="Evidence by type">
            {types.length === 0 ? <div className="text-sm text-slate-500">No evidence yet.</div> : (
              <div className="space-y-2">{types.sort((a, b) => b.v - a.v).map((t, i) => (
                <div key={t.k} className="flex items-center gap-3 text-sm"><span className="w-20 capitalize text-slate-600">{t.k}</span>
                  <div className="h-2 flex-1 overflow-hidden rounded-full bg-slate-100"><div className="h-full rounded-full" style={{ width: `${(t.v / Math.max(...types.map((x) => x.v))) * 100}%`, background: TYPE_COLORS[i % 9] }} /></div>
                  <span className="w-6 text-right tabular-nums text-slate-700">{t.v}</span></div>))}</div>)}
          </Section>
          <Section title="Contradictions by category" className="xl:col-span-2">
            {contra.length === 0 ? <div className="text-sm text-slate-500">No contradictions detected yet.</div> : (
              <div className="h-52"><ResponsiveContainer><BarChart data={contra} layout="vertical" margin={{ left: 30 }}>
                <XAxis type="number" allowDecimals={false} tick={{ fontSize: 10 }} /><YAxis type="category" dataKey="k" width={170} tick={{ fontSize: 11, fill: "#0b0b0b" }} />
                <Tooltip /><Bar dataKey="v" name="Count" radius={[0, 4, 4, 0]}>{contra.map((_, i) => <Cell key={i} fill={i % 2 ? "#2b4bff" : "#ff4f1f"} stroke="#0b0b0b" strokeWidth={2} />)}</Bar></BarChart></ResponsiveContainer></div>)}
          </Section>
          <Section title="Reviewer verdicts">
            {Object.keys(data.verdicts).length === 0 ? <div className="text-sm text-slate-500">No adversarial reviews run yet.</div> :
              <div className="space-y-2">{Object.entries(data.verdicts).map(([k, v]) => <div key={k} className="flex items-center justify-between text-sm"><Badge tone={statusTone(k)}>{titleCase(k)}</Badge><span className="tabular-nums">{v as number}</span></div>)}</div>}
            <div className="mt-4 border-t border-slate-100 pt-3"><div className="label mb-2">Scenario Lab outcomes</div>
              <div className="flex gap-2">{["PASS", "HOLD", "FAIL"].map((o) => <div key={o} className="flex-1 rounded-lg bg-slate-50 p-2 text-center"><div className="text-lg font-semibold tabular-nums">{data.scenario_outcomes[o] || 0}</div><div className="text-[11px] text-slate-500">{o}</div></div>)}</div></div>
          </Section>
        </div>
      )}
      <div className="mt-4 grid gap-4 xl:grid-cols-3">
        <Section title="Integrity verification">
          <div className="grid grid-cols-3 gap-2 text-center">{[["match", "Verified", "text-emerald-700"], ["mismatch", "Mismatch", "text-rose-700"], ["missing", "Missing", "text-rose-700"]].map(([k, l, cls]) => (
            <div key={k} className="rounded-lg bg-slate-100 p-2"><div className={`text-xl font-semibold tabular-nums ${(data.integrity?.[k] || 0) && k !== "match" ? cls : k === "match" ? cls : "text-slate-700"}`}>{data.integrity?.[k] || 0}</div><div className="text-[11px] text-slate-500">{l}</div></div>))}</div>
          <p className="mt-2 text-[11px] text-slate-500">Originals re-hashed against their intake SHA-256.</p>
        </Section>
        <Section title="Needs attention">
          <div className="space-y-2 text-sm">
            <div className="flex justify-between"><span>Unresolved contradictions</span><Badge tone={data.unresolved_contradictions ? "red" : "slate"}>{data.unresolved_contradictions}</Badge></div>
            <div className="flex justify-between"><span>High-priority evidence gaps</span><Badge tone={data.high_priority_gaps ? "amber" : "slate"}>{data.high_priority_gaps}</Badge></div>
            <div className="flex justify-between"><span>Pending human reviews</span><Badge tone={s.pending_reviews ? "amber" : "slate"}>{s.pending_reviews}</Badge></div>
          </div>
        </Section>
        <Section title="Recent reviewer decisions">
          {!data.recent_decisions?.length ? <div className="text-sm text-slate-500">No challenge runs yet.</div> : (
            <ul className="divide-y divide-slate-200">{data.recent_decisions.map((d: any, i: number) => (
              <li key={i}><Link to={`/cases/${d.case_id}/challenge`} className="flex items-center gap-2 py-2 text-sm hover:text-accent-700">
                <Badge tone={d.decision === "SUPPORTED" ? "green" : d.decision === "CONTRADICTED" ? "red" : "amber"}>{d.decision}</Badge>
                <span className="min-w-0 flex-1 truncate">{d.case}</span><span className="text-xs text-slate-500">human: {d.human_review}</span></Link></li>))}</ul>)}
        </Section>
      </div>
      <div className="mt-4 grid gap-4 xl:grid-cols-3">
        <Section title="Recent cases">
          {data.recent_cases.length === 0 ? <div className="text-sm text-slate-500">No cases yet.</div> : (
            <ul className="divide-y divide-slate-100">{data.recent_cases.map((c: any) => (
              <li key={c.id}><Link to={`/cases/${c.id}`} className="flex items-center gap-2 py-2 text-sm hover:text-accent-700">
                <span className="min-w-0 flex-1 truncate font-medium">{ct(c, "title")}</span><Badge tone={statusTone(c.status)}>{t(c.status)}</Badge></Link></li>))}</ul>)}
        </Section>
        <Section title="Recent reports">
          {data.recent_reports.length === 0 ? <div className="text-sm text-slate-500">No reports yet.</div> : (
            <ul className="divide-y divide-slate-100">{data.recent_reports.map((r: any) => (
              <li key={r.id}><Link to={`/reports/${r.id}`} className="block py-2 text-sm hover:text-accent-700"><div className="truncate font-medium">{r.title}</div>
                <div className="text-xs text-slate-500">{fmtDate(r.created_at)}</div></Link></li>))}</ul>)}
        </Section>
        <Section title="Scenario Lab activity" actions={<Link to="/scenarios/history" className="text-xs font-medium text-accent-700">History</Link>}>
          {data.scenario_activity.length === 0 ? <div className="text-sm text-slate-500">No scenario runs yet.</div> : (
            <ul className="divide-y divide-slate-100">{data.scenario_activity.map((r: any) => (
              <li key={r.id}><Link to={`/scenarios/runs/${r.id}`} className="flex items-center gap-2 py-2 text-sm hover:text-accent-700">
                <span className="mono">{r.test_code}</span><span className="min-w-0 flex-1 truncate text-slate-600">{titleCase(r.scenario_id.replace(/^s\d+h?-/, ""))}</span>
                <OutcomeBadge outcome={r.outcome} /></Link></li>))}</ul>)}
        </Section>
      </div>
      <div className="mt-4 grid gap-4 xl:grid-cols-2">
        <Section title="Processing status">
          {data.recent_runs.length === 0 ? <div className="text-sm text-slate-500">No analysis runs yet.</div> : (
            <ul className="divide-y divide-slate-100">{data.recent_runs.map((r: any) => (
              <li key={r.id} className="flex items-center gap-3 py-2.5 text-sm">
                <Badge tone={statusTone(r.status)}>{r.status}</Badge>
                <Link to={`/cases/${r.case_id}/processing`} className="min-w-0 flex-1 truncate font-medium hover:text-accent-700">{r.case}</Link>
                <span className="text-xs capitalize text-slate-500">{r.kind}</span>
                <div className="h-1.5 w-20 overflow-hidden rounded-full bg-slate-100"><div className="h-full bg-accent-500" style={{ width: `${r.progress * 100}%` }} /></div>
              </li>))}</ul>)}
        </Section>
        <Section title="Recent activity">
          {data.recent_activity.length === 0 ? <div className="text-sm text-slate-500">No activity yet.</div> : (
            <ul className="space-y-2.5">{data.recent_activity.slice(0, 10).map((a: any, i: number) => (
              <li key={i} className="flex gap-3 text-sm"><span className="mt-1.5 h-1.5 w-1.5 shrink-0 rounded-full bg-accent-600" />
                <div className="min-w-0"><span className="font-medium">{titleCase(a.action.replace(/\./g, " "))}</span>{a.case && <span className="text-slate-500"> · {a.case}</span>}
                  <div className="text-xs text-slate-500">{a.user} · {fmtDate(a.ts)}</div></div></li>))}</ul>)}
          <div className="mt-3 flex items-center gap-1 text-[11px] text-slate-400"><HelpCircle className="h-3 w-3" />All activity is recorded in a hash-chained audit log.</div>
        </Section>
      </div>
    </div>
  );
}
