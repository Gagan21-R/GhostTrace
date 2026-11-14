import clsx from "clsx";
import { AlertTriangle, Clock, Download, HelpCircle } from "lucide-react";
import { api } from "../../lib/api";
import { useMemo, useState } from "react";
import { SourceRef } from "../../components/EvidenceViewer";
import { Badge, Empty, ErrorBox, Loading } from "../../components/ui";
import { titleCase, useApi } from "../../lib/hooks";
import { useCase } from "./CaseWorkspace";

const KIND: Record<string, { label: string; cls: string; tip: string }> = {
  source_reported: { label: "Source-reported", cls: "bg-accent-600 text-white", tip: "Time stated inside the record (header, message time, log row, text)." },
  metadata_derived: { label: "Metadata", cls: "bg-violet-600 text-white", tip: "From file metadata (EXIF, PDF/DOCX properties). Can be altered." },
  estimated: { label: "Estimated", cls: "bg-amber-500 text-white", tip: "Resolved from a relative phrase such as 'yesterday'." },
  unknown: { label: "Unknown", cls: "bg-slate-300 text-slate-700", tip: "Event described without any time information." },
  system_recorded: { label: "System", cls: "bg-slate-200 text-slate-700", tip: "Recorded by the platform (e.g. upload time). Not an event time." },
};
const TYPE_DOT: Record<string, string> = { payment: "bg-emerald-600", refund: "bg-emerald-400", login: "bg-accent-600", security_alert: "bg-rose-500",
  password_reset: "bg-rose-600", recovery_change: "bg-rose-700", complaint: "bg-violet-600", access_change: "bg-orange-500", delivery: "bg-teal-600",
  shipment: "bg-teal-400", threat: "bg-rose-600", email: "bg-slate-500", message: "bg-slate-400" };

export default function TimelineTab() {
  const { c } = useCase();
  const { data, error, loading } = useApi<any[]>(`/api/cases/${c.id}/timeline`);
  const ents = useApi<any[]>(`/api/cases/${c.id}/entities`);
  const [src, setSrc] = useState(""); const [kind, setKind] = useState(""); const [ent, setEnt] = useState(""); const [type, setType] = useState("");
  const [onlyConflict, setOnlyConflict] = useState(false); const [expanded, setExpanded] = useState<string | null>(null);
  const [q, setQ] = useState("");
  const [showSys, setShowSys] = useState(false);
  const insights = useApi<any>(`/api/cases/${c.id}/timeline/analysis`);
  const simIds = useMemo(() => new Set<string>((insights.data?.simultaneous_groups || []).flat()), [insights.data]);
  const silentAfter = useMemo(() => new Map<string, any>((insights.data?.silent_periods || []).map((p: any) => [p.after_event, p])), [insights.data]);
  const events = useMemo(() => (data || []).filter((e) => (!src || e.evidence_id === src) && (!kind || e.timestamp_kind === kind) &&
    (!type || e.event_type === type) && (!ent || e.entity_ids.includes(ent)) && (!onlyConflict || e.conflict) &&
    (!q || `${e.title} ${e.description} ${e.filename}`.toLowerCase().includes(q.toLowerCase())) &&
    (showSys || (e.timestamp_kind !== "system_recorded" && !["file_created", "file_modified"].includes(e.event_type)))), [data, src, kind, ent, type, onlyConflict, q, showSys]);
  if (loading && !data) return <Loading />;
  if (error) return <ErrorBox error={error} />;
  if (!data!.length) return <Empty title="No timeline yet" hint="Run evidence processing to reconstruct the chronology." icon={<Clock className="h-5 w-5" />} />;
  const sources = Array.from(new Map(data!.map((e) => [e.evidence_id, `${e.evidence_code} ${e.filename}`])).entries());
  const types = Array.from(new Set(data!.map((e) => e.event_type))).sort();
  const dated = events.filter((e) => e.occurred_at); const undated = events.filter((e) => !e.occurred_at);
  const byDay = new Map<string, any[]>();
  dated.forEach((e) => { const d = (e.display_time || "").slice(0, 11); byDay.set(d, [...(byDay.get(d) || []), e]); });
  const counts = Object.fromEntries(Object.keys(KIND).map((k) => [k, data!.filter((e) => e.timestamp_kind === k).length]));
  return (
    <div className="grid gap-4 xl:grid-cols-[260px_1fr]">
      <div className="space-y-3">
        <div className="card space-y-3 p-4">
          <div className="label">Filters</div>
          <input className="input" placeholder="Search events…" value={q} onChange={(e) => setQ(e.target.value)} />
          <select className="input" value={src} onChange={(e) => setSrc(e.target.value)}><option value="">All sources</option>{sources.map(([id, l]) => <option key={id} value={id}>{l}</option>)}</select>
          <select className="input" value={type} onChange={(e) => setType(e.target.value)}><option value="">All event types</option>{types.map((t) => <option key={t} value={t}>{titleCase(t)}</option>)}</select>
          <select className="input" value={ent} onChange={(e) => setEnt(e.target.value)}><option value="">All entities</option>
            {(ents.data || []).filter((x) => x.mentions.length > 1).slice(0, 80).map((x) => <option key={x.id} value={x.id}>{x.type}: {x.value}</option>)}</select>
          <select className="input" value={kind} onChange={(e) => setKind(e.target.value)}><option value="">All timestamp kinds</option>{Object.entries(KIND).map(([k, v]) => <option key={k} value={k}>{v.label}</option>)}</select>
          <label className="flex items-center gap-2 text-sm"><input type="checkbox" checked={onlyConflict} onChange={(e) => setOnlyConflict(e.target.checked)} />Only conflicting timestamps</label>
          <label className="flex items-center gap-2 text-sm"><input type="checkbox" checked={showSys} onChange={(e) => setShowSys(e.target.checked)} />Show file &amp; upload times (not event times)</label>
          <div className="flex gap-2 border-t border-slate-100 pt-3">
            <button className="btn-outline flex-1 justify-center !py-1.5 text-xs" onClick={() => api.download(`/api/cases/${c.id}/timeline/export?format=csv`, `${c.case_number}_timeline.csv`)}><Download className="h-3.5 w-3.5" />CSV</button>
            <button className="btn-outline flex-1 justify-center !py-1.5 text-xs" onClick={() => api.download(`/api/cases/${c.id}/timeline/export?format=json`, `${c.case_number}_timeline.json`)}><Download className="h-3.5 w-3.5" />JSON</button>
          </div>
        </div>
        <div className="card space-y-2 p-4 text-xs">
          <div className="label">Timestamp provenance</div>
          {Object.entries(KIND).map(([k, v]) => <div key={k} className="flex items-start gap-2" title={v.tip}><span className={clsx("chip shrink-0", v.cls)}>{v.label}</span><span className="text-slate-500">{counts[k]} · {v.tip}</span></div>)}
          <div className="flex items-center gap-2 pt-1 text-rose-700"><AlertTriangle className="h-3.5 w-3.5" />Conflicting dates for the same event</div>
        </div>
      </div>
      <div>
        {insights.data && (insights.data.silent_periods.length > 0 || insights.data.reported_vs_header.length > 0 || insights.data.simultaneous_groups.length > 0) && (
          <div className="mb-3 grid gap-2 md:grid-cols-3">
            <div className="card p-3 text-xs"><div className="label mb-1">Silent periods</div>
              {insights.data.silent_periods.length ? insights.data.silent_periods.map((p: any, i: number) => <div key={i}>{p.from} → {p.to} <b>({p.hours} h)</b></div>) : <span className="text-slate-500">None unusually long.</span>}</div>
            <div className="card p-3 text-xs"><div className="label mb-1">Simultaneous across sources</div>
              {insights.data.simultaneous_groups.length} group(s) of events from different files within 2 minutes.</div>
            <div className="card p-3 text-xs"><div className="label mb-1">Reported vs header time</div>
              {insights.data.reported_vs_header.length ? insights.data.reported_vs_header.slice(0, 3).map((x: any, i: number) => <div key={i}>{x.evidence_code}: sent {x.header_time}, reports {x.reported_in_body} ({x.minutes_apart} min)</div>) : <span className="text-slate-500">No differences.</span>}</div>
          </div>)}
        <div className="mb-2 text-xs text-slate-500">{events.length} of {data!.length} events. Times are shown in the timezone each source reported; ⓘ marks an assumed case-default timezone.</div>
        <div className="relative">
          {Array.from(byDay.entries()).map(([day, evs]) => (
            <div key={day} className="mb-4">
              <div className="sticky top-0 z-10 mb-2 inline-block rounded-md bg-accent-500 px-2.5 py-1 text-xs font-semibold text-white">{day}</div>
              <ol className="relative ml-3 border-l-2 border-slate-200">
                {evs.map((e) => (
                  <li key={e.id} className="relative ml-5 pb-3">
                    <span className={clsx("absolute -left-[27px] top-3 h-3 w-3 rounded-full ring-4 ring-slate-50", TYPE_DOT[e.event_type] || "bg-accent-500", e.conflict && "!bg-rose-600 animate-pulse")} />
                    <div className={clsx("card cursor-pointer p-3 transition hover:border-slate-300", e.conflict && "border-rose-300 bg-rose-50/40")} onClick={() => setExpanded(expanded === e.id ? null : e.id)}>
                      <div className="flex flex-wrap items-center gap-2 text-xs">
                        <span className="mono font-medium text-ink-900">{e.display_time?.slice(12)}</span>
                        {e.data?.tz_assumed && <span title={e.data.timezone}><HelpCircle className="h-3 w-3 text-amber-600" /></span>}
                        <span className={clsx("chip", KIND[e.timestamp_kind].cls)}>{KIND[e.timestamp_kind].label}</span>
                        <Badge>{titleCase(e.event_type)}</Badge>{e.data?.precision === "day" && <Badge tone="amber">date only</Badge>}
                        {e.data?.ambiguous_day_month && <Badge tone="amber">dd/mm ambiguous</Badge>}
                        {e.conflict && <Badge tone="red"><AlertTriangle className="h-3 w-3" />conflict</Badge>}
                        {simIds.has(e.id) && <Badge tone="violet">simultaneous</Badge>}
                        <span className="ml-auto"><SourceRef src={{ evidence_id: e.evidence_id, evidence_code: e.evidence_code, segment_id: e.segment_id, filename: e.filename }} /></span>
                      </div>
                      <div className="mt-1.5 text-sm font-medium text-slate-800">{e.title}</div>
                      {expanded === e.id && (
                        <div className="mt-2 space-y-1 border-t border-slate-100 pt-2 text-xs text-slate-600">
                          <div className="whitespace-pre-wrap">{e.description}</div>
                          <div><b>Raw timestamp:</b> {e.timestamp_raw || "—"} · <b>Timezone:</b> {e.data?.timezone || "—"} · <b>Source:</b> {e.filename}</div>
                          {e.actors?.length > 0 && <div><b>Actors:</b> {e.actors.join(", ")}</div>}
                        </div>)}
                    </div>
                    {silentAfter.has(e.id) && <div className="mt-2 rounded-md border border-dashed border-amber-300/50 px-3 py-1.5 text-xs text-amber-700">Silent period: no recorded events for {silentAfter.get(e.id).hours} h</div>}
                  </li>))}
              </ol>
            </div>))}
          {undated.length > 0 && (
            <div className="mt-6"><div className="mb-2 inline-flex items-center gap-1.5 rounded-md bg-slate-200 px-2.5 py-1 text-xs font-semibold text-slate-700"><HelpCircle className="h-3.5 w-3.5" />Undated events — cannot be placed in sequence</div>
              <div className="grid gap-2 md:grid-cols-2">{undated.map((e) => (
                <div key={e.id} className="card border-dashed p-3 text-sm"><div className="mb-1 flex items-center gap-2"><Badge>{titleCase(e.event_type)}</Badge>
                  {e.data?.claim_polarity && <Badge tone={e.data.claim_polarity === "negative" ? "amber" : "blue"}>{e.data.claim_polarity} claim</Badge>}
                  <span className="ml-auto"><SourceRef src={{ evidence_id: e.evidence_id, evidence_code: e.evidence_code, segment_id: e.segment_id }} /></span></div>{e.title}</div>))}</div></div>)}
        </div>
      </div>
    </div>
  );
}
