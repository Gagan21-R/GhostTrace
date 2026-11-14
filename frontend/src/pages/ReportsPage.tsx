import { Empty, ErrorBox, Loading, PageHeader } from "../components/ui";
import { useApi } from "../lib/hooks";
import { ReportList } from "./case/ReportsTab";

export default function ReportsPage() {
  const { data, error, loading } = useApi<any[]>("/api/reports");
  return (
    <div>
      <PageHeader eyebrow="Reports" title="Investigation reports" subtitle="Evidence-linked PDF reports from your cases and Scenario Lab runs. Each report's SHA-256 is recorded in the audit log when generated." />
      {loading && !data ? <Loading /> : error ? <ErrorBox error={error} /> : !data!.length ?
        <Empty title="No reports yet" hint="Open a case and generate a report from its Reports tab, or complete a Scenario Lab run." /> : <ReportList reports={data!} />}
    </div>
  );
}
