import clsx from "clsx";
import cytoscape from "cytoscape";
import { motion } from "framer-motion";
import { Camera, Crosshair, Expand, Flame, Maximize2, Minimize2, Network, Route as RouteIcon, Shrink, Sparkles } from "lucide-react";
import { t } from "../../lib/i18n";
import { useEffect, useMemo, useRef, useState } from "react";
import { SourceRef } from "../../components/EvidenceViewer";
import { Badge, Empty, ErrorBox, Loading } from "../../components/ui";
import { titleCase, useApi } from "../../lib/hooks";
import { useCase } from "./CaseWorkspace";

export const ENTITY_COLORS: Record<string, string> = {
  person: "#e4ff3a", organisation: "#c4b5fd", email: "#93c5fd", phone: "#60a5fa", website: "#ff8a65", username: "#d8b4fe",
  account: "#5eead4", transaction: "#86efac", order: "#fde047", shipment: "#fdba74", ip_address: "#fb7185", device: "#f0abfc",
  location: "#67e8f9", document_ref: "#cbd5e1", document: "#e2e8f0", upi_id: "#bef264",
};
const ICON: Record<string, string> = {
  person: "👤", organisation: "🏢", email: "✉️", phone: "📞", website: "🌐", username: "🆔", account: "🏦", transaction: "💸",
  order: "📦", shipment: "🚚", ip_address: "🛰️", device: "💻", location: "📍", document_ref: "🧾", document: "📄", upi_id: "💳",
};
const iconUri = (t: string) => `data:image/svg+xml;utf8,${encodeURIComponent(
  `<svg xmlns="http://www.w3.org/2000/svg" width="64" height="64"><text x="32" y="44" font-size="34" text-anchor="middle">${ICON[t] || "●"}</text></svg>`)}`;

const LAYOUTS: Record<string, any> = {
  Force: { name: "cose", animate: true, animationDuration: 700, nodeRepulsion: () => 12000, idealEdgeLength: () => 110, padding: 40, randomize: false },
  Radial: { name: "concentric", animate: true, animationDuration: 700, concentric: (n: any) => n.degree(), levelWidth: () => 2, padding: 40, minNodeSpacing: 30 },
  Circle: { name: "circle", animate: true, animationDuration: 700, padding: 40 },
  Grid: { name: "grid", animate: true, animationDuration: 700, padding: 40, avoidOverlap: true },
  Tree: { name: "breadthfirst", animate: true, animationDuration: 700, padding: 40, spacingFactor: 1.2, directed: false },
};

export default function GraphTab() {
  const { c } = useCase();
  const [docs, setDocs] = useState(false);
  const { data, error, loading } = useApi<any>(`/api/cases/${c.id}/graph?include_documents=${docs}`, [docs]);
  const ents = useApi<any[]>(`/api/cases/${c.id}/entities`);
  const box = useRef<HTMLDivElement>(null);
  const wrap = useRef<HTMLDivElement>(null);
  const cy = useRef<cytoscape.Core | null>(null);
  const [hidden, setHidden] = useState<Set<string>>(new Set(["document_ref"]));
  const [showInferred, setShowInferred] = useState(true);
  const [layout, setLayout] = useState("Force");
  const [sel, setSel] = useState<{ kind: "node" | "edge"; id: string } | null>(null);
  const [focus, setFocus] = useState<string | null>(null);
  const [pathMode, setPathMode] = useState(false);
  const [pathInfo, setPathInfo] = useState<string | null>(null);
  const [hover, setHover] = useState<{ x: number; y: number; label: string; type: string; deg: number } | null>(null);
  const [full, setFull] = useState(false);
  const [riskOnly, setRiskOnly] = useState(false);
  const [search, setSearch] = useState("");
  const selRef = useRef(sel); selRef.current = sel;
  const pathRef = useRef(pathMode); pathRef.current = pathMode;
  const risky = useMemo(() => new Set((ents.data || []).filter((e: any) => e.risk?.indicators?.length).map((e: any) => e.id)), [ents.data]);
  const types = useMemo(() => Array.from(new Set((data?.nodes || []).map((n: any) => n.type))).sort() as string[], [data]);

  useEffect(() => {
    if (!box.current || !data) return;
    let nodes = data.nodes.filter((n: any) => !hidden.has(n.type));
    let edges = data.edges.filter((e: any) => showInferred || e.basis !== "inferred");
    if (focus) {
      const nb = new Set([focus]);
      edges.forEach((e: any) => { if (e.source === focus) nb.add(e.target); if (e.target === focus) nb.add(e.source); });
      nodes = nodes.filter((n: any) => nb.has(n.id));
    }
    const vis = new Set(nodes.map((n: any) => n.id));
    edges = edges.filter((e: any) => vis.has(e.source) && vis.has(e.target));
    const deg = new Map<string, number>();
    edges.forEach((e: any) => { deg.set(e.source, (deg.get(e.source) || 0) + 1); deg.set(e.target, (deg.get(e.target) || 0) + 1); });
    nodes = nodes.filter((n: any) => deg.get(n.id) || focus === n.id || n.mentions > 1);
    const maxDeg = Math.max(1, ...Array.from(deg.values()));
    cy.current?.destroy();
    const g = cytoscape({
      container: box.current,
      elements: [
        ...nodes.map((n: any) => ({
          data: { id: n.id, label: n.label.length > 26 ? n.label.slice(0, 24) + "…" : n.label, type: n.type, deg: deg.get(n.id) || 0,
                  size: 34 + 36 * ((deg.get(n.id) || 0) / maxDeg) + Math.min(14, (n.betweenness || 0) * 60) },
          classes: [risky.has(n.id) ? "risky" : "", (deg.get(n.id) || 0) / maxDeg > 0.6 ? "hub" : ""].join(" "),
        })),
        ...edges.map((e: any) => ({ data: { id: e.id, source: e.source, target: e.target, basis: e.basis, type: e.type, rel: e.type.replace(/_/g, " "),
                                             w: Math.min(7, 1.5 + e.weight * 0.8) } })),
      ],
      style: [
        { selector: "node", style: {
            "background-color": (el: any) => ENTITY_COLORS[el.data("type")] || "#e2e8f0", "background-image": (el: any) => iconUri(el.data("type")),
            "background-fit": "contain", "background-clip": "none", "background-width": "62%", "background-height": "62%",
            width: "data(size)", height: "data(size)", "border-width": 3, "border-color": "#0b0b0b",
            label: "data(label)", "font-size": 11, "font-weight": 700, "font-family": "Space Grotesk, sans-serif", color: "#0b0b0b",
            "text-valign": "bottom", "text-margin-y": 6, "text-background-color": "#fffdf6", "text-background-opacity": 1,
            "text-background-padding": "3px", "text-border-width": 2, "text-border-color": "#0b0b0b", "text-border-opacity": 1,
            "text-max-width": "140px", "text-wrap": "ellipsis", "transition-property": "opacity, border-width, width, height", "transition-duration": 200 } as any },
        { selector: "node.hub", style: { "border-width": 5, "underlay-color": "#e4ff3a", "underlay-opacity": 0.9, "underlay-padding": 8, "underlay-shape": "ellipse" } as any },
        { selector: "node.risky", style: { "border-color": "#ff4f1f", "border-width": 5 } as any },
        { selector: "node.pulse", style: { "border-width": 9 } as any },
        { selector: "edge", style: { width: "data(w)", "line-color": "#0b0b0b", "curve-style": "bezier", opacity: 0.8, "target-arrow-shape": "none",
            "transition-property": "opacity, line-color, width", "transition-duration": 200 } as any },
        { selector: "edge[type = 'emailed'], edge[type = 'paid'], edge[type = 'sent']", style: { "target-arrow-shape": "triangle", "target-arrow-color": "#2b4bff", "line-color": "#2b4bff" } },
        { selector: "edge[basis = 'inferred']", style: { "line-style": "dashed", "line-color": "#ff4f1f", "line-dash-pattern": [8, 5] } as any },
        { selector: "edge[type = 'co_mentioned']", style: { "line-color": "#8f887a", opacity: 0.55 } },
        { selector: "edge.show-label", style: { label: "data(rel)", "font-size": 10, "font-weight": 700, "text-background-color": "#e4ff3a",
            "text-background-opacity": 1, "text-background-padding": "2px", "text-rotation": "autorotate" } as any },
        { selector: ".faded", style: { opacity: 0.12 } },
        { selector: "edge.path", style: { "line-color": "#e4ff3a", width: 8, opacity: 1, "line-style": "solid" } as any },
        { selector: "node.path", style: { "border-color": "#2b4bff", "border-width": 7 } as any },
        { selector: "node:selected", style: { "border-color": "#2b4bff", "border-width": 7 } as any },
        { selector: "edge:selected", style: { "line-color": "#2b4bff", width: 7, opacity: 1 } as any },
      ],
      layout: LAYOUTS[layout],
      wheelSensitivity: 0.25,
      minZoom: 0.2, maxZoom: 3,
    });
    cy.current = g;
    const neighbourhood = (n: any) => n.closedNeighborhood();
    g.on("mouseover", "node", (ev) => {
      const n = ev.target;
      g.elements().addClass("faded"); neighbourhood(n).removeClass("faded"); n.connectedEdges().addClass("show-label");
      const p = n.renderedPosition();
      setHover({ x: p.x, y: p.y, label: n.data("label"), type: n.data("type"), deg: n.data("deg") });
    });
    g.on("mouseout", "node", (ev) => { g.elements().removeClass("faded"); ev.target.connectedEdges().removeClass("show-label"); setHover(null); });
    g.on("mouseover", "edge", (ev) => ev.target.addClass("show-label"));
    g.on("mouseout", "edge", (ev) => ev.target.removeClass("show-label"));
    g.on("tap", "node", (ev) => {
      const id = ev.target.id();
      if (pathRef.current && selRef.current?.kind === "node" && selRef.current.id !== id) {
        const res = g.elements().aStar({ root: g.getElementById(selRef.current.id), goal: ev.target });
        g.elements().removeClass("path faded");
        if (res.found) {
          g.elements().addClass("faded"); res.path.removeClass("faded").addClass("path");
          setPathInfo(res.path.nodes().map((n: any) => n.data("label")).join("  →  "));
          g.animate({ fit: { eles: res.path, padding: 60 } } as any, { duration: 500 });
        } else setPathInfo("No connecting path.");
        return;
      }
      g.elements().removeClass("path"); setPathInfo(null);
      setSel({ kind: "node", id });
      g.animate({ center: { eles: ev.target }, zoom: Math.max(g.zoom(), 1.1) } as any, { duration: 400 });
    });
    g.on("tap", "edge", (ev) => setSel({ kind: "edge", id: ev.target.id() }));
    g.on("dbltap", "node", (ev) => setFocus((f) => (f === ev.target.id() ? null : ev.target.id())));
    g.on("tap", (ev) => { if (ev.target === g) { setSel(null); g.elements().removeClass("path faded"); setPathInfo(null); } });
    let on = false;  // risky nodes pulse
    const t = setInterval(() => { on = !on; g.nodes(".risky").toggleClass("pulse", on); }, 700);
    return () => { clearInterval(t); g.destroy(); cy.current = null; };
  }, [data, hidden, showInferred, focus, layout, risky]);

  useEffect(() => {  // spotlight risky entities
    const g = cy.current;
    if (!g) return;
    if (riskOnly && g.nodes(".risky").length) { g.elements().addClass("faded"); g.nodes(".risky").closedNeighborhood().removeClass("faded"); }
    else g.elements().removeClass("faded");
  }, [riskOnly, data]);

  useEffect(() => { setTimeout(() => cy.current?.resize().fit(undefined, 40), 60); }, [full]);

  if (loading && !data) return <Loading />;
  if (error) return <ErrorBox error={error} />;
  if (!data?.nodes.length) return <Empty title="No entities yet" hint="Process the evidence first." icon={<Network className="h-5 w-5" />} />;
  const node = sel?.kind === "node" ? data.nodes.find((n: any) => n.id === sel.id) : null;
  const ent = node ? ents.data?.find((x) => x.id === node.id) : null;
  const edge = sel?.kind === "edge" ? data.edges.find((e: any) => e.id === sel.id) : null;
  const label = (id: string) => data.nodes.find((n: any) => n.id === id)?.label || id;
  const connections = node ? data.edges.filter((e: any) => e.source === node.id || e.target === node.id) : [];
  const hubs = [...data.nodes].sort((a: any, b: any) => (b.betweenness || 0) - (a.betweenness || 0) || b.mentions - a.mentions).slice(0, 6);
  const jump = (id: string) => {
    const n = data.nodes.find((x: any) => x.id === id);
    if (n) setHidden((h) => { const x = new Set(h); x.delete(n.type); return x; });
    setSel({ kind: "node", id });
    setTimeout(() => { const el = cy.current?.getElementById(id); if (el?.length) { cy.current!.elements().unselect(); el.select(); cy.current!.animate({ center: { eles: el }, zoom: 1.5 } as any, { duration: 450 }); } }, 80);
  };
  const exportPng = () => {
    const uri = cy.current?.png({ full: true, scale: 2, bg: "#f3efe4" });
    if (!uri) return;
    const a = document.createElement("a"); a.href = uri; a.download = `${c.case_number}-graph.png`; a.click();
  };

  return (
    <div ref={wrap} className={clsx("grid gap-4", full ? "fixed inset-0 z-40 bg-paper p-4 xl:grid-cols-[1fr_340px]" : "xl:grid-cols-[1fr_340px]")}>
      <div className="card relative overflow-hidden">
        <div className="flex flex-wrap items-center gap-1.5 border-b-2 border-ink-900 p-2.5">
          {Object.keys(LAYOUTS).map((l) => (
            <button key={l} onClick={() => setLayout(l)} className={clsx("chip border-2 border-ink-900 font-bold uppercase", layout === l ? "bg-ink-900 text-acid" : "bg-surface")}>{l}</button>))}
          <span className="mx-1 h-5 w-0.5 bg-ink-900" />
          <button onClick={() => { setPathMode(!pathMode); setPathInfo(null); }} className={clsx("chip border-2 border-ink-900 font-bold", pathMode ? "bg-volt text-white" : "bg-surface")} title="Select one node, then another">
            <RouteIcon className="h-3.5 w-3.5" />{t("Path finder")}</button>
          {risky.size > 0 && <button onClick={() => setRiskOnly(!riskOnly)} className={clsx("chip border-2 border-ink-900 font-bold", riskOnly ? "bg-flame text-white" : "bg-surface")}>
            <Flame className="h-3.5 w-3.5" />Risky ({risky.size})</button>}
          <label className="flex items-center gap-1 text-xs font-semibold"><input type="checkbox" checked={showInferred} onChange={(e) => setShowInferred(e.target.checked)} />leads</label>
          <label className="flex items-center gap-1 text-xs font-semibold"><input type="checkbox" checked={docs} onChange={(e) => setDocs(e.target.checked)} />files</label>
          <div className="ml-auto flex items-center gap-1">
            <form onSubmit={(e) => { e.preventDefault(); const hit = data.nodes.find((n: any) => n.label.toLowerCase().includes(search.trim().toLowerCase())); if (hit) jump(hit.id); }}>
              <input className="input !w-36 !py-1 text-xs" placeholder={t("Find…")} value={search} onChange={(e) => setSearch(e.target.value)} />
            </form>
            {focus && <button className="btn-ghost !px-2 !py-1" title="Show all" onClick={() => setFocus(null)}><Maximize2 className="h-4 w-4" /></button>}
            <button className="btn-ghost !px-2 !py-1" title="Fit" onClick={() => cy.current?.animate({ fit: { padding: 40 } } as any, { duration: 400 })}><Crosshair className="h-4 w-4" /></button>
            <button className="btn-ghost !px-2 !py-1" title="Save PNG" onClick={exportPng}><Camera className="h-4 w-4" /></button>
            <button className="btn-ghost !px-2 !py-1" title={full ? "Exit full screen" : "Full screen"} onClick={() => setFull(!full)}>{full ? <Shrink className="h-4 w-4" /> : <Expand className="h-4 w-4" />}</button>
          </div>
        </div>
        <div className="flex flex-wrap gap-1 border-b border-slate-200 px-2.5 py-1.5">
          {types.map((t) => (
            <button key={t} onClick={() => { const h = new Set(hidden); h.has(t) ? h.delete(t) : h.add(t); setHidden(h); }}
              className={clsx("chip border text-[11px]", hidden.has(t) ? "border-slate-300 text-slate-400 line-through" : "border-ink-900")} style={{ background: hidden.has(t) ? undefined : ENTITY_COLORS[t] }}>
              {ICON[t]} {titleCase(t)}</button>))}
        </div>
        <div ref={box} className={clsx("bg-[radial-gradient(circle_at_1px_1px,#bcb4a0_1px,transparent_0)] [background-size:22px_22px]", full ? "h-[calc(100vh-150px)]" : "h-[600px]")} />
        {hover && (
          <div className="pointer-events-none absolute z-10 border-2 border-ink-900 bg-surface px-2 py-1 text-xs shadow-brutal-sm" style={{ left: hover.x + 18, top: hover.y + 90 }}>
            <b>{ICON[hover.type]} {hover.label}</b><div className="text-slate-600">{titleCase(hover.type)} · {hover.deg} link(s)</div></div>)}
        {pathMode && !pathInfo && <div className="absolute bottom-3 left-3 border-2 border-ink-900 bg-volt px-2 py-1 text-xs font-bold text-white">{t("Click a start node, then an end node")}</div>}
        {pathInfo && <motion.div initial={{ y: 20, opacity: 0 }} animate={{ y: 0, opacity: 1 }} className="absolute bottom-3 left-3 right-3 border-2 border-ink-900 bg-acid px-3 py-2 text-xs font-bold">
          <RouteIcon className="mr-1 inline h-3.5 w-3.5" />{pathInfo}</motion.div>}
      </div>

      <div className="space-y-3">
        {!sel && (
          <div className="card p-4">
            <div className="label mb-2 flex items-center gap-1"><Sparkles className="h-3.5 w-3.5" />{t("Key connectors")}</div>
            <div className="space-y-1.5">{hubs.map((h: any) => (
              <button key={h.id} onClick={() => jump(h.id)} className="flex w-full items-center gap-2 border-2 border-ink-900 bg-surface px-2 py-1.5 text-left text-sm shadow-brutal-sm hover:-translate-y-px hover:bg-acid/40">
                <span>{ICON[h.type]}</span><span className="min-w-0 flex-1 truncate font-semibold">{h.label}</span>
                {risky.has(h.id) && <Flame className="h-4 w-4 text-flame" />}</button>))}</div>
            <div className="mt-3 grid grid-cols-2 gap-2 text-center">
              <div className="border-2 border-ink-900 p-2"><div className="font-display text-2xl">{data.nodes.length}</div><div className="text-[10px] font-bold uppercase">{t("entities")}</div></div>
              <div className="border-2 border-ink-900 p-2"><div className="font-display text-2xl">{data.edges.length}</div><div className="text-[10px] font-bold uppercase">{t("links")}</div></div>
            </div>
            <p className="mt-3 text-[11px] text-slate-500">{t("Hover to spotlight · click to inspect · double-click to isolate · dashed orange = inferred lead.")}</p>
          </div>)}
        {node && (
          <motion.div key={node.id} initial={{ x: 20, opacity: 0 }} animate={{ x: 0, opacity: 1 }} className="card p-4">
            <div className="flex items-center gap-2"><span className="flex h-9 w-9 items-center justify-center border-2 border-ink-900 text-lg" style={{ background: ENTITY_COLORS[node.type] }}>{ICON[node.type]}</span>
              <Badge>{titleCase(node.type)}</Badge>{risky.has(node.id) && <Badge tone="red">risk</Badge>}</div>
            <div className="mt-2 break-all text-lg font-bold">{node.label}</div>
            {ent?.risk?.indicators?.length > 0 && <div className="mt-2 border-2 border-flame bg-flame/10 p-2 text-xs">{ent.risk.indicators.join("; ")}</div>}
            <div className="mt-3 flex gap-2">
              <button className="btn-outline !py-1 text-xs" onClick={() => setFocus(focus === node.id ? null : node.id)}>
                {focus === node.id ? <><Maximize2 className="h-3.5 w-3.5" />Show all</> : <><Minimize2 className="h-3.5 w-3.5" />Isolate</>}</button>
              <button className="btn-outline !py-1 text-xs" onClick={() => { setPathMode(true); setPathInfo(null); }}><RouteIcon className="h-3.5 w-3.5" />{t("Path from here")}</button>
            </div>
            <div className="label mb-1 mt-4">{t("Connected to")} ({connections.length})</div>
            <ul className="max-h-48 space-y-1 overflow-auto text-xs">{connections.slice(0, 25).map((e: any) => (
              <li key={e.id}><button className="text-left hover:underline" onClick={() => jump(e.source === node.id ? e.target : e.source)}>
                <Badge tone={e.basis === "inferred" ? "amber" : "slate"}>{e.type.replace(/_/g, " ")}</Badge> {label(e.source === node.id ? e.target : e.source)}</button></li>))}</ul>
            <div className="label mb-1 mt-4">{t("Seen in")} ({ent?.mentions.length || 0})</div>
            <ul className="max-h-48 space-y-1.5 overflow-auto">{(ent?.mentions || []).slice(0, 15).map((m: any, i: number) => (
              <li key={i} className="text-xs"><SourceRef src={m} /><div className="mt-0.5 text-slate-600">{m.snippet}</div></li>))}</ul>
          </motion.div>)}
        {edge && (
          <motion.div key={edge.id} initial={{ x: 20, opacity: 0 }} animate={{ x: 0, opacity: 1 }} className="card p-4">
            <Badge tone={edge.basis === "inferred" ? "amber" : "green"}>{edge.basis === "inferred" ? "Inferred lead" : "Seen in records"}</Badge>
            <div className="mt-2 text-sm"><b>{label(edge.source)}</b> <span className="text-slate-500">— {edge.type.replace(/_/g, " ")} —</span> <b>{label(edge.target)}</b></div>
            <p className="mt-2 text-xs text-slate-600">{edge.description}</p>
            <div className="mt-3 flex flex-wrap gap-1.5">{edge.segment_ids.slice(0, 10).map((sid: string, i: number) => {
              const ev = edge.evidence[Math.min(i, edge.evidence.length - 1)];
              return <SourceRef key={sid} src={{ evidence_id: ev?.evidence_id, evidence_code: ev?.code, segment_id: sid }} />; })}</div>
          </motion.div>)}
      </div>
    </div>
  );
}
