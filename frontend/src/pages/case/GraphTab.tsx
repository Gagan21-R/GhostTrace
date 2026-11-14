import clsx from "clsx";
import cytoscape from "cytoscape";
import { Maximize2, Minimize2, Network, RotateCcw } from "lucide-react";
import { useEffect, useMemo, useRef, useState } from "react";
import { SourceRef } from "../../components/EvidenceViewer";
import { Badge, Empty, ErrorBox, Loading } from "../../components/ui";
import { titleCase, useApi } from "../../lib/hooks";
import { useCase } from "./CaseWorkspace";

export const ENTITY_COLORS: Record<string, string> = {
  person: "#fffdf6", organisation: "#94a3b8", email: "#1d4ed8", phone: "#2563eb", website: "#dc2626", username: "#7c3aed",
  account: "#0d9488", transaction: "#059669", order: "#ca8a04", shipment: "#d97706", ip_address: "#e11d48", device: "#9333ea",
  location: "#0891b2", document_ref: "#64748b", document: "#475569",
};

export default function GraphTab() {
  const { c } = useCase();
  const [docs, setDocs] = useState(false);
  const { data, error, loading } = useApi<any>(`/api/cases/${c.id}/graph?include_documents=${docs}`, [docs]);
  const ents = useApi<any[]>(`/api/cases/${c.id}/entities`);
  const box = useRef<HTMLDivElement>(null);
  const cy = useRef<cytoscape.Core | null>(null);
  const [hidden, setHidden] = useState<Set<string>>(new Set(["document_ref"]));
  const [showInferred, setShowInferred] = useState(true);
  const [showCo, setShowCo] = useState(true);
  const [sel, setSel] = useState<{ kind: "node" | "edge"; id: string } | null>(null);
  const [focus, setFocus] = useState<string | null>(null);
  const [search, setSearch] = useState(""); const [searchMiss, setSearchMiss] = useState(false);
  const [pathInfo, setPathInfo] = useState<string | null>(null);
  const selRef = useRef(sel); selRef.current = sel;
  const types = useMemo(() => Array.from(new Set((data?.nodes || []).map((n: any) => n.type))).sort() as string[], [data]);

  useEffect(() => {
    if (!box.current || !data) return;
    const visible = new Set<string>();
    let nodes = data.nodes.filter((n: any) => !hidden.has(n.type));
    let edges = data.edges.filter((e: any) => (showInferred || e.basis !== "inferred") && (showCo || e.type !== "co_mentioned"));
    if (focus) {  // expand/collapse: show only the focused node's neighbourhood
      const nb = new Set([focus]);
      edges.forEach((e: any) => { if (e.source === focus) nb.add(e.target); if (e.target === focus) nb.add(e.source); });
      nodes = nodes.filter((n: any) => nb.has(n.id));
    }
    nodes.forEach((n: any) => visible.add(n.id));
    edges = edges.filter((e: any) => visible.has(e.source) && visible.has(e.target));
    const deg = new Map<string, number>(); edges.forEach((e: any) => { deg.set(e.source, (deg.get(e.source) || 0) + 1); deg.set(e.target, (deg.get(e.target) || 0) + 1); });
    nodes = nodes.filter((n: any) => deg.get(n.id) || focus === n.id || n.mentions > 1);
    cy.current?.destroy();
    cy.current = cytoscape({
      container: box.current,
      elements: [
        ...nodes.map((n: any) => ({ data: { id: n.id, label: n.label.length > 28 ? n.label.slice(0, 26) + "…" : n.label, type: n.type, size: 18 + Math.min(30, (n.betweenness || 0) * 120 + (deg.get(n.id) || 0) * 2.5) } })),
        ...edges.map((e: any) => ({ data: { id: e.id, source: e.source, target: e.target, basis: e.basis, type: e.type, w: Math.min(5, 0.8 + e.weight * 0.6) } })),
      ],
      style: [
        { selector: "node", style: { "background-color": (el: any) => ENTITY_COLORS[el.data("type")] || "#64748b", label: "data(label)", "font-size": 9, "font-family": "Space Grotesk, sans-serif",
            color: "#0b0b0b", "text-valign": "bottom", "text-margin-y": 4, width: "data(size)", height: "data(size)", "border-width": 2, "border-color": "#0b0b0b", "text-wrap": "ellipsis", "text-max-width": "120px" } as any },
        { selector: "node[type = 'document']", style: { shape: "round-rectangle", "background-color": "#475569" } },
        { selector: "edge", style: { width: "data(w)", "line-color": "#4a463e", "curve-style": "bezier", opacity: 0.75 } as any },
        { selector: "edge[type = 'emailed']", style: { "target-arrow-shape": "triangle", "target-arrow-color": "#1d4ed8", "line-color": "#1d4ed8" } },
        { selector: "edge[basis = 'inferred']", style: { "line-style": "dashed", "line-color": "#ff4f1f", "line-dash-pattern": [6, 4] } as any },
        { selector: "edge[type = 'co_mentioned']", style: { "line-color": "#bcb4a0", opacity: 0.8 } },
        { selector: ".faded", style: { opacity: 0.15 } },
        { selector: "edge.path", style: { "line-color": "#f59e0b", width: 4, opacity: 1 } as any },
        { selector: "node.path", style: { "border-color": "#f59e0b", "border-width": 4 } as any },
        { selector: ":selected", style: { "border-color": "#3b82f6", "border-width": 4, "line-color": "#3b82f6", "target-arrow-color": "#3b82f6", opacity: 1 } },
      ],
      layout: { name: "cose", animate: false, nodeRepulsion: () => 9000, idealEdgeLength: () => 90, padding: 30 } as any,
      wheelSensitivity: 0.25,
    });
    cy.current.on("tap", "node", (ev) => {
      const id = ev.target.id();
      if ((ev.originalEvent as MouseEvent)?.shiftKey && selRef.current?.kind === "node" && selRef.current.id !== id) {
        const from = cy.current!.getElementById(selRef.current.id);
        const res = cy.current!.elements().aStar({ root: from, goal: ev.target });
        cy.current!.elements().removeClass("path faded");
        if (res.found) {
          cy.current!.elements().addClass("faded");
          res.path.removeClass("faded").addClass("path");
          setPathInfo(`${res.path.nodes().length - 1} step(s): ` + res.path.nodes().map((n: any) => n.data("label")).join(" → "));
        } else setPathInfo("No connecting path between these entities.");
        return;
      }
      cy.current!.elements().removeClass("path faded"); setPathInfo(null);
      setSel({ kind: "node", id });
    });
    cy.current.on("tap", "edge", (ev) => setSel({ kind: "edge", id: ev.target.id() }));
    cy.current.on("dbltap", "node", (ev) => setFocus((f) => (f === ev.target.id() ? null : ev.target.id())));
    return () => { cy.current?.destroy(); cy.current = null; };
  }, [data, hidden, showInferred, showCo, focus]);

  if (loading && !data) return <Loading />;
  if (error) return <ErrorBox error={error} />;
  if (!data?.nodes.length) return <Empty title="No entities yet" hint="Run evidence processing to extract entities and relationships." icon={<Network className="h-5 w-5" />} />;
  const node = sel?.kind === "node" ? data.nodes.find((n: any) => n.id === sel.id) : null;
  const ent = node ? ents.data?.find((x) => x.id === node.id) : null;
  const edge = sel?.kind === "edge" ? data.edges.find((e: any) => e.id === sel.id) : null;
  const label = (id: string) => data.nodes.find((n: any) => n.id === id)?.label || id;
  const connections = node ? data.edges.filter((e: any) => e.source === node.id || e.target === node.id) : [];
  return (
    <div className="grid gap-4 xl:grid-cols-[1fr_360px]">
      <div className="card overflow-hidden">
        <div className="flex flex-wrap items-center gap-1.5 border-b border-slate-100 p-3">
          {types.map((t) => (
            <button key={t} onClick={() => { const h = new Set(hidden); h.has(t) ? h.delete(t) : h.add(t); setHidden(h); }}
              className={clsx("chip border", hidden.has(t) ? "border-slate-200 bg-surface text-slate-400 line-through" : "border-transparent bg-slate-100 text-slate-700")}>
              <span className="h-2 w-2 rounded-full" style={{ background: ENTITY_COLORS[t] || "#64748b" }} />{titleCase(t)}</button>))}
          <span className="mx-1 h-4 w-px bg-slate-200" />
          <label className="flex items-center gap-1 text-xs"><input type="checkbox" checked={showInferred} onChange={(e) => setShowInferred(e.target.checked)} /><span className="border-b-2 border-dashed border-amber-500">inferred</span></label>
          <label className="flex items-center gap-1 text-xs"><input type="checkbox" checked={showCo} onChange={(e) => setShowCo(e.target.checked)} />co-mentions</label>
          <label className="flex items-center gap-1 text-xs"><input type="checkbox" checked={docs} onChange={(e) => setDocs(e.target.checked)} />documents</label>
          <div className="ml-auto flex gap-1">
            <form onSubmit={(e) => {
              e.preventDefault();
              const term = search.trim().toLowerCase();
              const hit = data.nodes.find((n: any) => n.label.toLowerCase().includes(term));
              if (!hit) { setSearchMiss(true); return; }
              setSearchMiss(false); setFocus(null); setHidden((h) => { const x = new Set(h); x.delete(hit.type); return x; });
              setSel({ kind: "node", id: hit.id });
              setTimeout(() => { const el = cy.current?.getElementById(hit.id); if (el && el.length) { cy.current!.elements().unselect(); el.select(); cy.current!.animate({ center: { eles: el }, zoom: 1.6 } as any, { duration: 300 }); } }, 50);
            }}>
              <input className={clsx("input !w-48 !py-1 text-xs", searchMiss && "!border-rose-400")} placeholder="Find entity…" value={search} onChange={(e) => { setSearch(e.target.value); setSearchMiss(false); }} />
            </form>
            {focus && <button className="btn-ghost !py-1 text-xs" onClick={() => setFocus(null)}><Maximize2 className="h-3.5 w-3.5" />Expand all</button>}
            <button className="btn-ghost !py-1 text-xs" onClick={() => cy.current?.fit(undefined, 30)}><RotateCcw className="h-3.5 w-3.5" />Fit</button></div>
        </div>
        <div ref={box} className="h-[620px] bg-[radial-gradient(circle_at_1px_1px,#d6cfbd_1px,transparent_0)] [background-size:18px_18px]" />
        <div className="border-t border-slate-100 px-3 py-2 text-[11px] text-slate-500">Click a node or link for its sources · shift-click a second node to highlight the shortest connecting path · double-click to collapse to a neighbourhood · node size reflects connectivity. Dashed amber links are inferred leads, not established identity.</div>
      </div>
      <div className="space-y-3">
        {pathInfo && <div className="card border-amber-300/50 p-3 text-xs"><div className="label mb-1">Shortest path</div>{pathInfo}
          <div className="mt-1 text-slate-500">A path shows how records connect; it is not evidence of a relationship between people.</div></div>}
        {!sel && <div className="card p-4 text-sm text-slate-500">Select an entity or a relationship to see the evidence behind it.</div>}
        {node && (
          <div className="card p-4">
            <div className="flex items-center gap-2"><span className="h-3 w-3 rounded-full" style={{ background: ENTITY_COLORS[node.type] }} /><Badge>{titleCase(node.type)}</Badge></div>
            <div className="mt-2 break-all text-lg font-semibold">{node.label}</div>
            {ent?.risk?.indicators?.length > 0 && <div className="mt-2 rounded-lg bg-rose-50 p-2 text-xs text-rose-800"><b>Risk indicators:</b> {ent.risk.indicators.join("; ")}. Indicators are signals, not proof.</div>}
            {ent?.attributes?.chat_display_name && <div className="mt-2 text-xs text-amber-700">Name taken from a chat display name, which the account holder controls.</div>}
            <div className="mt-3 flex gap-2"><button className="btn-outline !py-1 text-xs" onClick={() => setFocus(focus === node.id ? null : node.id)}>
              {focus === node.id ? <><Maximize2 className="h-3.5 w-3.5" />Expand</> : <><Minimize2 className="h-3.5 w-3.5" />Collapse to neighbours</>}</button></div>
            <div className="label mb-1 mt-4">Mentions ({ent?.mentions.length || 0})</div>
            <ul className="max-h-60 space-y-1.5 overflow-auto">{(ent?.mentions || []).map((m: any, i: number) => (
              <li key={i} className="text-xs"><SourceRef src={m} /><div className="mt-0.5 text-slate-600">{m.snippet}</div></li>))}</ul>
            <div className="label mb-1 mt-4">Connections ({connections.length})</div>
            <ul className="space-y-1 text-xs">{connections.slice(0, 20).map((e: any) => (
              <li key={e.id}><button className="text-left hover:text-accent-700" onClick={() => setSel({ kind: "edge", id: e.id })}>
                <Badge tone={e.basis === "inferred" ? "amber" : "slate"}>{e.type.replace(/_/g, " ")}</Badge> {label(e.source === node.id ? e.target : e.source)}</button></li>))}</ul>
          </div>)}
        {edge && (
          <div className="card p-4">
            <Badge tone={edge.basis === "inferred" ? "amber" : "green"}>{edge.basis === "inferred" ? "Inferred association" : "Direct observation"}</Badge>
            <div className="mt-2 text-sm"><b>{label(edge.source)}</b> <span className="text-slate-500">— {edge.type.replace(/_/g, " ")} —</span> <b>{label(edge.target)}</b></div>
            <p className="mt-2 text-xs text-slate-600">{edge.description}</p>
            <div className="mt-2 text-xs text-slate-500">Seen in {edge.weight} record segment(s) · confidence {Math.round(edge.confidence * 100)}%</div>
            <div className="label mb-1 mt-3">Connecting evidence</div>
            <div className="flex flex-wrap gap-1.5">{edge.segment_ids.slice(0, 12).map((sid: string, i: number) => {
              const ev = edge.evidence[Math.min(i, edge.evidence.length - 1)];
              return <SourceRef key={sid} src={{ evidence_id: ev?.evidence_id, evidence_code: ev?.code, segment_id: sid }} />; })}</div>
          </div>)}
      </div>
    </div>
  );
}
