import clsx from "clsx";
import { Archive, ChevronLeft } from "lucide-react";
import { createContext, useContext, useEffect } from "react";
import { Link, NavLink, Navigate, Route, Routes, useParams } from "react-router-dom";
import { Badge, ErrorBox, Loading, statusTone } from "../../components/ui";
import { ExplainButton } from "../../components/Assistant";
import { api } from "../../lib/api";
import { titleCase, useApi } from "../../lib/hooks";
import AdversarialTab from "./AdversarialTab";
import AuditTab from "./AuditTab";
import ContradictionsTab from "./ContradictionsTab";
import EvidenceTab from "./EvidenceTab";
import GapsTab from "./GapsTab";
import GraphTab from "./GraphTab";
import OverviewTab from "./OverviewTab";
import ProcessingTab from "./ProcessingTab";
import ReportsTab from "./ReportsTab";
import TimelineTab from "./TimelineTab";
import DnaTab from "./DnaTab";
import EntitiesTab from "./EntitiesTab";
import MissingEvidenceTab from "./MissingEvidenceTab";
import ReplayTab from "./ReplayTab";
import WhatIfTab from "./WhatIfTab";
import { setActiveCase } from "../../lib/activeCase";

interface CaseCtx { c: any; reload: (silent?: boolean) => void; canWrite: boolean }
const Ctx = createContext<CaseCtx>(null as unknown as CaseCtx);
export const useCase = () => useContext(Ctx);

const TABS = [
  ["overview", "Summary"], ["evidence", "Evidence"], ["processing", "Processing"], ["timeline", "Timeline"], ["entities", "Entities"],
  ["graph", "Relationships"], ["dna", "Evidence DNA"], ["contradictions", "Contradictions"], ["gaps", "Gaps"],
  ["challenge", "Challenge Centre"], ["missing", "Missing Evidence"], ["whatif", "What-If Lab"], ["replay", "Replay"],
  ["reports", "Reports"], ["audit", "Integrity & Audit"],
];

export default function CaseWorkspace() {
  const { caseId } = useParams();
  const { data: c, error, loading, reload } = useApi<any>(`/api/cases/${caseId}`);
  useEffect(() => { if (c) setActiveCase({ id: c.id, title: c.title, number: c.case_number }); }, [c?.id, c?.title]);
  if (loading && !c) return <Loading />;
  if (error) return <ErrorBox error={error} onRetry={reload} />;
  const canWrite = c.access && c.access !== "viewer";
  const counts: Record<string, number | undefined> = { evidence: c.counts.evidence, contradictions: c.counts.contradictions, gaps: c.counts.gaps_open };
  return (
    <Ctx.Provider value={{ c, reload, canWrite }}>
      <div className="mb-5">
        <Link to={c.is_scenario ? "/scenarios/history" : "/cases"} className="mb-2 inline-flex items-center gap-1 text-xs font-medium text-slate-500 hover:text-ink-900"><ChevronLeft className="h-3.5 w-3.5" />{c.is_scenario ? "Scenario runs" : "All cases"}</Link>
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div className="min-w-0">
            <div className="flex flex-wrap items-center gap-2"><span className="mono text-slate-500">{c.case_number}</span><Badge tone={statusTone(c.status)}>{c.status}</Badge>
              <Badge>{titleCase(c.case_type)}</Badge><Badge tone={c.priority === "critical" || c.priority === "high" ? "red" : "slate"}>{c.priority} priority</Badge>
              {c.is_scenario && <Badge tone="violet">Scenario Lab</Badge>}<span className="text-xs text-slate-500">TZ default {c.default_timezone}</span></div>
            <h1 className="mt-1 text-[22px] font-semibold tracking-tight text-ink-900">{c.title}</h1>
          </div>
          {canWrite && c.status !== "archived" && (
            <button className="btn-outline" onClick={async () => { if (confirm("Archive this case? It becomes read-only in listings.")) { await api.post(`/api/cases/${c.id}/archive`); reload(); } }}>
              <Archive className="h-4 w-4" />Archive</button>)}
        </div>
        <div className="mt-4 flex gap-1 overflow-x-auto border-b border-slate-200 scrollbar-thin">
          {TABS.map(([id, label]) => (
            <NavLink key={id} to={`/cases/${c.id}/${id}`} className={({ isActive }) => clsx("tab", isActive && "tab-active")}>
              {label}{counts[id] ? <span className="ml-1.5 rounded bg-slate-100 px-1.5 text-[11px] text-slate-600">{counts[id]}</span> : null}</NavLink>))}
        </div>
      </div>
      <TabExplain />
      <Routes>
        <Route index element={<Navigate to="overview" replace />} />
        <Route path="overview" element={<OverviewTab />} />
        <Route path="evidence" element={<EvidenceTab />} />
        <Route path="processing" element={<ProcessingTab />} />
        <Route path="timeline" element={<TimelineTab />} />
        <Route path="graph" element={<GraphTab />} />
        <Route path="contradictions" element={<ContradictionsTab />} />
        <Route path="gaps" element={<GapsTab />} />
        <Route path="adversarial" element={<Navigate to="../challenge" replace />} />
        <Route path="challenge" element={<AdversarialTab />} />
        <Route path="entities" element={<EntitiesTab />} />
        <Route path="dna" element={<DnaTab />} />
        <Route path="missing" element={<MissingEvidenceTab />} />
        <Route path="whatif" element={<WhatIfTab />} />
        <Route path="replay" element={<ReplayTab />} />
        <Route path="reports" element={<ReportsTab />} />
        <Route path="audit" element={<AuditTab />} />
      </Routes>
    </Ctx.Provider>
  );
}

function TabExplain() {
  const { "*": rest } = useParams();
  const id = (rest || "overview").split("/")[0];
  const label = TABS.find(([k]) => k === id)?.[1];
  if (!label) return null;
  return (
    <div className="mb-4 flex items-center gap-2 text-xs font-bold uppercase tracking-wider text-slate-600">
      <span>You are in: {label}</span><ExplainButton title={label} label="Explain this tab" />
    </div>
  );
}
