import { Navigate, Route, Routes } from "react-router-dom";
import { AssistantProvider } from "./components/Assistant";
import { EvidenceViewerProvider } from "./components/EvidenceViewer";
import Layout from "./components/Layout";
import { Loading } from "./components/ui";
import { useAuth } from "./lib/auth";
import AuditPage from "./pages/AuditPage";
import CaseWorkspace from "./pages/case/CaseWorkspace";
import CasesPage from "./pages/CasesPage";
import Dashboard from "./pages/Dashboard";
import LoginPage from "./pages/LoginPage";
import NewCasePage from "./pages/NewCasePage";
import EvaluationPage from "./pages/EvaluationPage";
import EvidencePage from "./pages/EvidencePage";
import GoPage from "./pages/GoPage";
import ProfilePage from "./pages/ProfilePage";
import ReportPreviewPage from "./pages/ReportPreviewPage";
import ReportsPage from "./pages/ReportsPage";
import ScenarioDetail from "./pages/scenarios/ScenarioDetail";
import ScenarioHistory from "./pages/scenarios/ScenarioHistory";
import ScenarioLab from "./pages/scenarios/ScenarioLab";
import ScenarioRunPage from "./pages/scenarios/ScenarioRunPage";
import SettingsPage from "./pages/SettingsPage";
import UsersPage from "./pages/UsersPage";

export default function App() {
  const { user, loading } = useAuth();
  if (loading) return <Loading label="Starting EVIDENCE-X" />;
  if (!user) return (
    <AssistantProvider><Routes>
      <Route path="/login" element={<LoginPage />} />
      <Route path="/register" element={<LoginPage register />} />
      <Route path="*" element={<Navigate to="/login" replace />} />
    </Routes></AssistantProvider>
  );
  return (
    <AssistantProvider><EvidenceViewerProvider>
      <Routes>
        <Route element={<Layout />}>
          <Route index element={<Dashboard />} />
          <Route path="cases" element={<CasesPage />} />
          <Route path="cases/new" element={<NewCasePage />} />
          <Route path="cases/:caseId/*" element={<CaseWorkspace />} />
          <Route path="scenarios" element={<ScenarioLab />} />
          <Route path="scenarios/history" element={<ScenarioHistory />} />
          <Route path="scenarios/runs/:runId" element={<ScenarioRunPage />} />
          <Route path="scenarios/:scenarioId" element={<ScenarioDetail />} />
          <Route path="reports" element={<ReportsPage />} />
          <Route path="reports/:reportId" element={<ReportPreviewPage />} />
          <Route path="evidence/:evidenceId" element={<EvidencePage />} />
          <Route path="profile" element={<ProfilePage />} />
          <Route path="go/:section" element={<GoPage />} />
          <Route path="evaluation" element={<EvaluationPage />} />
          <Route path="audit" element={<AuditPage />} />
          <Route path="users" element={<UsersPage />} />
          <Route path="settings" element={<SettingsPage />} />
          <Route path="login" element={<Navigate to="/" replace />} />
          <Route path="*" element={<Navigate to="/" replace />} />
        </Route>
      </Routes>
    </EvidenceViewerProvider></AssistantProvider>
  );
}
