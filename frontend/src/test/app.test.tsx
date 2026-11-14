import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it } from "vitest";
import App from "../App";
import { AuthProvider } from "../lib/auth";
import { CASE, ME, mockFetch } from "./mockApi";

const DASH = { stats: { total_cases: 1, active_cases: 1, completed_cases: 0, archived_cases: 0, evidence_files: 2, evidence_processed: 2, contradictions: 1,
  pending_reviews: 2, open_gaps: 1, running_jobs: 0, pending_processing: 0 }, evidence_by_type: { email: 2 }, contradictions_by_category: {},
  verdicts: {}, intake_14d: Array(14).fill(0), scenario_outcomes: {}, recent_runs: [], recent_activity: [], recent_cases: [], recent_reports: [],
  scenario_activity: [], integrity: { match: 2 }, unresolved_contradictions: 1, high_priority_gaps: 1, recent_decisions: [] };

const SEG = (id: string, loc: string) => ({ evidence_id: "e1", evidence_code: "EV-001", filename: "mail.eml", segment_id: id, locator: loc });
const TIMELINE = [
  { id: "t1", occurred_at: "2026-03-10T03:42:00Z", display_time: "10 Mar 2026 09:12 +05:30", timestamp_raw: "x", timestamp_kind: "source_reported", event_type: "email",
    title: "Email: Urgent KYC", description: "", actors: [], entity_ids: [], data: {}, conflict: false, evidence_id: "e1", segment_id: "s1", evidence_code: "EV-001", filename: "mail.eml", source_type: "email" },
  { id: "t2", occurred_at: "2026-03-10T04:17:00Z", display_time: "10 Mar 2026 09:47 +05:30", timestamp_raw: "x", timestamp_kind: "source_reported", event_type: "payment",
    title: "UPI debit 24999", description: "", actors: [], entity_ids: [], data: {}, conflict: true, evidence_id: "e2", segment_id: "s2", evidence_code: "EV-002", filename: "bank.csv", source_type: "spreadsheet" },
  { id: "t3", occurred_at: "2026-11-14T00:00:00Z", display_time: "14 Nov 2026 00:00 UTC", timestamp_raw: "x", timestamp_kind: "system_recorded", event_type: "evidence_received",
    title: "Received into EVIDENCE-X: EV-001", description: "", actors: [], entity_ids: [], data: {}, conflict: false, evidence_id: "e1", segment_id: "s1", evidence_code: "EV-001", filename: "mail.eml", source_type: "email" },
];

function renderAt(path: string) {
  localStorage.setItem("evx_token", "t");
  return render(<MemoryRouter initialEntries={[path]}><AuthProvider><App /></AuthProvider></MemoryRouter>);
}

describe("navigation and case selection", () => {
  it("shows the login page when signed out", async () => {
    mockFetch({});
    render(<MemoryRouter initialEntries={["/"]}><AuthProvider><App /></AuthProvider></MemoryRouter>);
    expect(await screen.findByRole("heading", { name: "Sign in" })).toBeTruthy();
  });

  it("renders the dashboard with live figures and the console navigation", async () => {
    mockFetch({ "GET /api/auth/me": ME, "GET /api/dashboard": DASH });
    renderAt("/");
    expect(await screen.findByText("Investigation workspace")).toBeTruthy();
    for (const label of ["Evidence Vault", "Evidence DNA", "Challenge Centre", "Missing Evidence", "What-If Lab", "Investigation Replay", "Scenario Lab", "Evaluation"])
      expect(screen.getAllByText(label).length).toBeGreaterThan(0);
    expect(screen.getByText("Integrity verification")).toBeTruthy();
  });

  it("asks for a case when a case-scoped section has no active case, then opens it", async () => {
    mockFetch({ "GET /api/auth/me": ME, "GET /api/cases?include_scenarios=true": [CASE], "GET /api/cases/c1": CASE,
      "GET /api/cases/c1/dna": { dependencies: [], shared_identifiers: [], source_groups: [], summary: { evidence: 2, independent_source_groups: 2, by_relation: {} } },
      "GET /api/cases/c1/history?limit=40": [] });
    renderAt("/go/dna");
    expect(await screen.findByText("Choose a case")).toBeTruthy();
    fireEvent.click(await screen.findByText("Test phishing case"));
    expect(await screen.findByText("No cross-file relationships yet")).toBeTruthy();
    expect(JSON.parse(localStorage.getItem("evx_active_case") || "{}").id).toBe("c1");
  });
});

describe("case workspace", () => {
  it("timeline hides upload times by default, filters and shows conflicts", async () => {
    mockFetch({ "GET /api/auth/me": ME, "GET /api/cases/c1": CASE, "GET /api/cases/c1/timeline": TIMELINE, "GET /api/cases/c1/entities": [],
      "GET /api/cases/c1/timeline/analysis": { silent_periods: [], simultaneous_groups: [], reported_vs_header: [] } });
    renderAt("/cases/c1/timeline");
    expect(await screen.findByText("Email: Urgent KYC")).toBeTruthy();
    expect(screen.queryByText(/Received into EVIDENCE-X/)).toBeNull();
    expect(screen.getByText("conflict")).toBeTruthy();
    fireEvent.click(screen.getByLabelText(/Show file & upload times/));
    expect(await screen.findByText(/Received into EVIDENCE-X/)).toBeTruthy();
    fireEvent.change(screen.getByPlaceholderText("Search events…"), { target: { value: "UPI" } });
    await waitFor(() => expect(screen.queryByText("Email: Urgent KYC")).toBeNull());
    expect(screen.getByText("UPI debit 24999")).toBeTruthy();
  });

  it("challenge centre shows candidates, decision and verifies a claim", async () => {
    const H = (rank: number, pattern: string, decision: string) => ({ id: `h${rank}`, run_id: "r1", rank, pattern, decision, verdict: "supported_with_reservations",
      statement: `Hypothesis ${pattern}`, supporting: [{ id: "C1", text: "Email dated 10 Mar", kind: "observation", citations: ["s1"], verification: { status: "verified", checks: [], sources: [SEG("s1", "header")] } }],
      counterevidence: [], alternatives: [{ id: "K1", kind: "alternative_explanation", text: "Refs differ: maybe two transfers", strength: "strong", citations: ["s2"], verification: { status: "verified", sources: [] } }],
      assumptions: ["Causation inferred"], missing_information: [], verification: { rejected: 0, rejected_items: [] },
      assessment: { reason: "Facts verified", confidence_band: "moderate", independent_sources: 3, verified_support: ["C1"], counter_considered: ["K1"], next_steps: [], limitations: [] },
      human_review_status: "pending", agents: [] });
    const calls = mockFetch({ "GET /api/auth/me": ME, "GET /api/cases/c1": CASE, "GET /api/cases/c1/hypotheses": [H(0, "phishing_payment_fraud", "SUPPORTED"), H(1, "delivery_dispute", "HOLD")],
      "GET /api/cases/c1/runs": [], "GET /api/cases/c1/evidence": [{ id: "e1", code: "EV-001", filename: "mail.eml" }],
      "GET /api/cases/c1/extracted-data?evidence_id=e1": { items: [{ segment_id: "s1", locator: "header", text: "From: alerts@x" }] },
      "POST /api/cases/c1/verify-claim": { status: "rejected", checks: ["quoted value '999' not found in cited source"], sources: [] } });
    renderAt("/cases/c1/challenge");
    expect((await screen.findAllByText("SUPPORTED")).length).toBeGreaterThan(0);
    fireEvent.click(screen.getByText(/delivery dispute/));
    expect((await screen.findAllByText("HOLD")).length).toBeGreaterThan(0);
    fireEvent.change(screen.getByPlaceholderText(/Claim, e.g./), { target: { value: "UTR is 999" } });
    fireEvent.change(screen.getByDisplayValue("Cite evidence…"), { target: { value: "e1" } });
    await screen.findByText(/header · From/);
    fireEvent.change(screen.getByDisplayValue("…at location"), { target: { value: "s1" } });
    fireEvent.change(screen.getByPlaceholderText(/Value that must appear/), { target: { value: "999" } });
    fireEvent.click(screen.getByText("Verify claim"));
    expect(await screen.findByText(/not found in cited source/)).toBeTruthy();
    expect(calls.some((c) => c.method === "POST" && c.url.endsWith("/verify-claim") && c.body.citations[0] === "s1")).toBe(true);
  });

  it("generates a report and offers PDF, DOCX and HTML", async () => {
    const calls = mockFetch({ "GET /api/auth/me": ME, "GET /api/cases/c1": CASE, "GET /api/reports?case_id=c1": [],
      "POST /api/cases/c1/reports": { id: "rep1" } });
    renderAt("/cases/c1/reports");
    fireEvent.click(await screen.findByText("Generate PDF"));
    await waitFor(() => expect(calls.some((c) => c.method === "POST" && c.url === "/api/cases/c1/reports")).toBe(true));
  });

  it("evidence vault uploads with metadata and lists results", async () => {
    mockFetch({ "GET /api/auth/me": ME, "GET /api/cases/c1": CASE, "GET /api/cases/c1/evidence": [] });
    const sent: FormData[] = [];
    class XHR { status = 200; responseText = JSON.stringify({ accepted: 1, rejected: 0, results: [{ filename: "a.txt", ok: true, evidence: { code: "EV-003", sha256: "a".repeat(64) } }] });
      upload: any = {}; onload: any; onerror: any; open() {} setRequestHeader() {} send(fd: FormData) { sent.push(fd); this.upload.onprogress?.({ lengthComputable: true, loaded: 1, total: 1 }); setTimeout(() => this.onload(), 0); } }
    (globalThis as any).XMLHttpRequest = XHR;
    const { container } = renderAt("/cases/c1/evidence");
    await screen.findByText(/Drop evidence files here/);
    const input = container.querySelector('input[type="file"]') as HTMLInputElement;
    fireEvent.change(input, { target: { files: [new File(["hello"], "a.txt", { type: "text/plain" })] } });
    fireEvent.change(screen.getByPlaceholderText(/Exported from victim/), { target: { value: "Phone export" } });
    fireEvent.click(screen.getByText("Upload & hash"));
    expect(await screen.findByText(/1 accepted/)).toBeTruthy();
    expect(sent[0].get("collection_source")).toBe("Phone export");
  });
});

describe("what-if lab", () => {
  it("labels results HYPOTHETICAL", async () => {
    mockFetch({ "GET /api/auth/me": ME, "GET /api/cases/c1": CASE, "GET /api/cases/c1/whatif": [{ id: "w1", title: "Bank SMS unreliable", status: "completed", assumptions: [], parent_id: null, decision_change: { from: "SUPPORTED", to: "SUPPORTED", changed: false } }],
      "GET /api/cases/c1/evidence": [], "GET /api/whatif/w1": { id: "w1", title: "Bank SMS unreliable", status: "completed", result: { label: "HYPOTHETICAL",
        assumptions_described: ["EV-006 is unrelated or unreliable and is set aside"], not_computable: [], changes: { decision: { from: "SUPPORTED", to: "SUPPORTED", changed: false },
        pattern: { from: "p", to: "p", changed: false }, contradictions_added: [], contradictions_removed: ["x"], gaps_added: [], gaps_removed: [], independent_sources: { from: 3, to: 2 } },
        supporting_under_assumption: [], challenging_under_assumption: [], would_resolve: [] } } });
    renderAt("/cases/c1/whatif");
    fireEvent.click(await screen.findByText("Bank SMS unreliable"));
    const labels = await screen.findAllByText("HYPOTHETICAL");
    expect(labels.length).toBeGreaterThan(1);
    expect(screen.getByText(/What if EV-006 is unrelated/)).toBeTruthy();
    expect(within(document.body).getByText("− x")).toBeTruthy();
  });
});
