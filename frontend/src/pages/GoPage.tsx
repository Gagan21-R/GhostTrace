import { FolderOpen } from "lucide-react";
import { ct, t } from "../lib/i18n";
import { Navigate, useNavigate, useParams } from "react-router-dom";
import { Badge, Empty, ErrorBox, Loading, PageHeader } from "../components/ui";
import { getActiveCase, setActiveCase } from "../lib/activeCase";
import { titleCase, useApi } from "../lib/hooks";

const NAMES: Record<string, string> = { evidence: "Evidence Vault", dna: "Evidence DNA", timeline: "Timeline", graph: "Entity Graph",
  challenge: "Challenge Centre", missing: "Missing Evidence", whatif: "What-If Lab", replay: "Investigation Replay" };

/** Resolves a case-scoped section to the active case, or asks which case to open. */
export default function GoPage() {
  const { section = "overview" } = useParams();
  const nav = useNavigate();
  const active = getActiveCase();
  const { data, error, loading } = useApi<any[]>(active ? null : "/api/cases?include_scenarios=true");
  if (active) return <Navigate to={`/cases/${active.id}/${section}`} replace />;
  return (
    <div className="max-w-3xl">
      <PageHeader eyebrow={NAMES[section] || titleCase(section)} title="Choose a case" subtitle="This section works on one case at a time." />
      {loading ? <Loading /> : error ? <ErrorBox error={error} /> : !data!.length ? <Empty title="No cases yet" hint="Create a case or run a Scenario Lab simulation first." /> : (
        <div className="card divide-y divide-slate-200">
          {data!.map((c) => (
            <button key={c.id} className="flex w-full items-center gap-3 px-4 py-3 text-left hover:bg-slate-100"
              onClick={() => { setActiveCase({ id: c.id, title: ct(c, "title"), number: c.case_number }); nav(`/cases/${c.id}/${section}`); }}>
              <FolderOpen className="h-4 w-4 text-slate-400" /><span className="mono text-slate-500">{c.case_number}</span>
              <span className="flex-1 truncate font-medium">{ct(c, "title")}</span>{c.is_scenario && <Badge tone="violet">scenario</Badge>}
              <span className="text-xs text-slate-500">{c.counts.evidence} items</span></button>))}
        </div>)}
    </div>
  );
}
