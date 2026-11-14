import clsx from "clsx";
import { Archive, ChevronDown, ChevronLeft } from "lucide-react";
import { createContext, useContext, useEffect, useState } from "react";
import { Link, NavLink, Navigate, Route, Routes, useLocation, useParams } from "react-router-dom";
import { Badge, ErrorBox, Loading, statusTone } from "../../components/ui";
import { ExplainButton } from "../../components/Assistant";
import { api } from "../../lib/api";
import { titleCase, useApi } from "../../lib/hooks";
import AdversarialTab from "./AdversarialTab";
import AuditTab from "./AuditTab";
import AuthenticityTab from "./AuthenticityTab";
import ConfidenceTab from "./ConfidenceTab";
import HypothesisTab from "./HypothesisTab";
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
import { ct, t } from "../../lib/i18n";

interface CaseCtx { c: any; reload: (silent?: boolean) => void; canWrite: boolean }
const Ctx = createContext<CaseCtx>(null as unknown as CaseCtx);
export const useCase = () => useContext(Ctx);

const TABS = [
  ["overview", "Summary"], ["evidence", "Evidence"], ["timeline", "Timeline"], ["graph", "Relationships"], ["hypotheses", "Hypothesis Lab"], ["authenticity", "Message Check"], ["confidence", "Confidence"],
  ["contradictions", "Contradictions"], ["gaps", "Gaps"], ["challenge", "Challenge"], ["reports", "Reports"],
  ["processing", "Processing"], ["entities", "Entities"], ["dna", "Evidence DNA"], ["missing", "Missing Evidence"], ["whatif", "What-If Lab"],
  ["replay", "Replay"], ["audit", "Integrity & Audit"],
];
const PRIMARY = 11;

export default function CaseWorkspace() {
  const { caseId } = useParams();
  const { data: c, error, loading, reload } = useApi<any>(`/api/cases/${caseId}`);
  useEffect(() => { if (c) setActiveCase({ id: c.id, title: ct(c, "title"), number: c.case_number }); }, [c?.id, c?.title, c?.translations]);
  if (loading && !c) return <Loading />;
  if (error) return <ErrorBox error={error} onRetry={reload} />;
  const canWrite = c.access && c.access !== "viewer";
  const counts: Record<string, number | undefined> = { evidence: c.counts.evidence, contradictions: c.counts.contradictions, gaps: c.counts.gaps_open };
  return (
    <Ctx.Provider value={{ c, reload, canWrite }}>
      <div className="mb-5">
        <Link to={c.is_scenario ? "/scenarios/history" : "/cases"} className="mb-2 inline-flex items-center gap-1 text-xs font-medium text-slate-500 hover:text-ink-900"><ChevronLeft className="h-3.5 w-3.5" />{c.is_scenario ? t("Scenario runs") : t("All cases")}</Link>
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div className="min-w-0">
            <div className="flex flex-wrap items-center gap-2"><span className="mono text-slate-500">{c.case_number}</span><Badge tone={statusTone(c.status)}>{t(c.status)}</Badge>
              <Badge>{t(titleCase(c.case_type))}</Badge><Badge tone={c.priority === "critical" || c.priority === "high" ? "red" : "slate"}>{t(c.priority)} {t("priority")}</Badge>
              {c.is_scenario && <Badge tone="violet">Scenario Lab</Badge>}<span className="text-xs text-slate-500">TZ default {c.default_timezone}</span></div>
            <h1 className="mt-1 text-[22px] font-semibold tracking-tight text-ink-900" title={ct(c, "title") !== c.title ? `${t("English original")}: ${c.title}` : undefined}>{ct(c, "title")}</h1>
          </div>
          {canWrite && c.status !== "archived" && (
            <button className="btn-outline" onClick={async () => { if (confirm("Archive this case? It becomes read-only in listings.")) { await api.post(`/api/cases/${c.id}/archive`); reload(); } }}>
              <Archive className="h-4 w-4" />Archive</button>)}
        </div>
        <div className="mt-4 flex items-end gap-1 border-b-2 border-ink-900">
          <div className="flex gap-1 overflow-x-auto scrollbar-thin">
            {TABS.slice(0, PRIMARY).map(([id, label]) => (
              <NavLink key={id} to={`/cases/${c.id}/${id}`} className={({ isActive }) => clsx("tab", isActive && "tab-active")}>
                {t(label)}{counts[id] ? <span className="ml-1.5 bg-ink-900 px-1.5 text-[11px] text-acid">{counts[id]}</span> : null}</NavLink>))}
          </div>
          <MoreTabs caseId={c.id} />
        </div>
      </div>
      <TabExplain />
      {c.counts.evidence > 0 && c.counts.evidence < 3 && <FewFiles caseId={c.id} n={c.counts.evidence} />}
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
        <Route path="authenticity" element={<AuthenticityTab />} />
        <Route path="confidence" element={<ConfidenceTab />} />
        <Route path="hypotheses" element={<HypothesisTab />} />
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
      <span>{t("You are in:")} {t(label)}</span><ExplainButton title={label} label={t("Explain this tab")} />
    </div>
  );
}

function MoreTabs({ caseId }: { caseId: string }) {
  const [open, setOpen] = useState(false);
  const { pathname } = useLocation();
  const extra = TABS.slice(PRIMARY);
  const current = extra.find(([id]) => pathname.includes(`/${id}`));
  return (
    <div className="relative ml-auto shrink-0" onMouseLeave={() => setOpen(false)}>
      <button className={clsx("tab inline-flex items-center gap-1", current && "tab-active")} onClick={() => setOpen(!open)}>
        {current ? t(current[1]) : t("More")}<ChevronDown className="h-3.5 w-3.5" /></button>
      {open && (
        <div className="absolute right-0 z-30 w-52 border-2 border-ink-900 bg-surface shadow-brutal">
          {extra.map(([id, label]) => (
            <NavLink key={id} to={`/cases/${caseId}/${id}`} onClick={() => setOpen(false)}
              className={({ isActive }) => clsx("block px-3 py-2 text-sm font-bold uppercase tracking-wide hover:bg-acid/60", isActive && "bg-acid")}>{t(label)}</NavLink>))}
        </div>)}
    </div>
  );
}

function FewFiles({ caseId, n }: { caseId: string; n: number }) {
  return (
    <div className="mb-4 flex flex-wrap items-center gap-2 border-2 border-ink-900 bg-acid/40 px-3 py-2 text-sm">
      <b>{t("Only")} {n} {t("evidence file(s) in this case.")}</b>
      <span>{t("Timeline, relationships and contradictions need several related files (chats, statements, bank or account records).")}</span>
      <NavLink to={`/cases/${caseId}/evidence`} className="btn-outline !py-1 text-xs">{t("Add evidence")}</NavLink>
    </div>
  );
}
