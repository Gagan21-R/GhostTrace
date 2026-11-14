import { vi } from "vitest";

/** Route-table fetch mock: keys are "METHOD /path" prefixes (query string ignored unless included). */
export function mockFetch(routes: Record<string, unknown | ((body: any, url: string) => unknown)>) {
  const calls: { method: string; url: string; body: any }[] = [];
  const fn = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
    const url = String(input);
    const method = (init?.method || "GET").toUpperCase();
    let body: any = init?.body;
    if (typeof body === "string") { try { body = JSON.parse(body); } catch { /* keep */ } }
    calls.push({ method, url, body });
    const path = url.split("?")[0];
    const key = Object.keys(routes).sort((a, b) => b.length - a.length).find((k) => {
      const [m, p] = k.split(" ");
      return m === method && (p.includes("?") ? url.startsWith(p) : path === p);
    });
    if (!key) return new Response(JSON.stringify({ error: { message: `unmocked ${method} ${path}` } }), { status: 404 });
    const v = routes[key];
    const data = typeof v === "function" ? (v as any)(body, url) : v;
    return new Response(JSON.stringify(data), { status: 200, headers: { "Content-Type": "application/json" } });
  });
  vi.stubGlobal("fetch", fn);
  return calls;
}

export const ME = { access_token: "t", user: { id: "u1", email: "inv@example.com", full_name: "Ivy Investigator", role: "investigator", is_active: true, created_at: "2026-11-14T00:00:00Z" },
  permissions: ["analysis:run", "case:create", "evidence:upload", "report:generate", "review:decide", "scenario:run"] };

export const CASE = { id: "c1", case_number: "EVX-2026-0001", title: "Test phishing case", description: "desc", objective: "obj", case_type: "fraud",
  status: "active", priority: "high", is_scenario: false, default_timezone: "+05:30", allow_external_ai: false, access: "owner",
  created_at: "2026-11-14T00:00:00Z", updated_at: "2026-11-14T00:00:00Z", verdict: "supported_with_reservations", decision: "SUPPORTED",
  counts: { evidence: 2, entities: 3, events: 3, contradictions: 1, contradictions_pending: 1, gaps: 1, gaps_open: 1 }, last_run: null,
  members: [{ user_id: "u1", email: "inv@example.com", name: "Ivy Investigator", access: "owner" }] };
