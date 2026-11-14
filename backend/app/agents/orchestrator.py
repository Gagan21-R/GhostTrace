"""LangGraph orchestration of the eleven EVIDENCE-X agents.

Processing graph:   intake -> extraction -> entity_intelligence -> timeline -> relationship
                    -> contradiction -> evidence_gap
Adversarial graph:  investigation -> counter_investigation -> verification -> skeptical_review -> report

Every node runs with retry handling, writes an AgentExecution record (structured JSON output,
mode, duration, attempts) and updates the AnalysisRun progress that the UI polls.
The database session lives in the closure, not in graph state, so state stays serialisable.
"""
from __future__ import annotations

import logging
import time
import traceback
from typing import Any, Callable, TypedDict

from sqlalchemy import select
from sqlalchemy.orm import Session

from .. import audit
from .. import replay
from ..analysis import contradictions as contra
from ..analysis import dna, integrity
from ..analysis import gaps as gapmod
from ..analysis.entities import build_entities
from ..analysis.index import CaseIndex
from ..analysis.timeline import build_timeline
from ..models import (AgentExecution, AnalysisRun, Entity, Evidence, Hypothesis, HypothesisEvidence, Relationship,
                      VerificationResult, utcnow)
from ..services.processing import process_evidence
from . import adversarial as adv
from .compat import END, LANGGRAPH_AVAILABLE, START, StateGraph, XXHASH_SHIM_ACTIVE

log = logging.getLogger("evidencex.orchestrator")


class RunState(TypedDict, total=False):
    case_id: str
    run_id: str
    results: dict
    errors: list
    halted: bool


class SimpleGraph:
    """Minimal sequential fallback with the same add_node/add_edge/compile/invoke surface,
    used only if LangGraph cannot be imported in this environment."""

    def __init__(self, _state_type):
        self.nodes: dict[str, Callable] = {}
        self.edges: dict[str, str] = {}

    def add_node(self, name, fn):
        self.nodes[name] = fn

    def add_edge(self, a, b):
        self.edges[a] = b

    def compile(self):
        return self

    def invoke(self, state):
        cur = self.edges.get("__start__")
        while cur and cur != "__end__":
            state = {**state, **(self.nodes[cur](state) or {})}
            cur = self.edges.get(cur)
        return state


ORCHESTRATOR = "langgraph" if LANGGRAPH_AVAILABLE else "sequential-fallback"


def _graph(nodes: list[tuple[str, Callable]]):
    if LANGGRAPH_AVAILABLE:
        g = StateGraph(RunState)
        start, end = START, END
    else:
        g = SimpleGraph(RunState)
        start, end = "__start__", "__end__"
    prev = start
    for name, fn in nodes:
        g.add_node(name, fn)
        g.add_edge(prev, name)
        prev = name
    g.add_edge(prev, end)
    return g.compile()


class Runner:
    def __init__(self, db: Session, run: AnalysisRun, user=None, progress_cb: Callable[[str, float], None] | None = None,
                 span: tuple[float, float] = (0.0, 1.0)):
        self.db, self.run, self.user, self.cb = db, run, user, progress_cb
        self.span = span
        self.seq = len(list(db.scalars(select(AgentExecution.id).where(AgentExecution.run_id == run.id))))

    def _progress(self, stage: str, frac: float, msg: str):
        p = self.span[0] + (self.span[1] - self.span[0]) * frac
        self.run.stage, self.run.progress = stage, round(p, 3)
        self.run.log = (self.run.log or []) + [{"t": utcnow().isoformat(), "stage": stage, "msg": msg}]
        self.db.commit()
        if self.cb:
            self.cb(stage, p)

    def node(self, name: str, fn: Callable[[dict], dict], frac: float, retries: int = 1, critical: bool = True):
        def _wrapped(state: RunState) -> dict:
            if state.get("halted"):
                return {}
            self._progress(name, frac, f"{name} agent started")
            attempts, err, out = 0, None, None
            t0 = time.perf_counter()
            while attempts <= retries:
                attempts += 1
                try:
                    out = fn(state)
                    err = None
                    break
                except Exception as e:
                    self.db.rollback()
                    err = f"{type(e).__name__}: {e}"
                    log.error("agent %s failed (attempt %d): %s\n%s", name, attempts, err, traceback.format_exc())
            self.seq += 1
            mode = (out or {}).pop("_mode", "deterministic") if isinstance(out, dict) else "deterministic"
            self.db.add(AgentExecution(run_id=self.run.id, case_id=self.run.case_id, agent=name, seq=self.seq,
                                       status="failed" if err else "completed", mode=mode, attempts=attempts,
                                       output=_jsonable(out or {}), error=err,
                                       duration_ms=int((time.perf_counter() - t0) * 1000)))
            self.db.commit()
            replay.emit(self.db, self.run.case_id, f"agent.{name}", component=name, actor=f"{name} agent ({mode})",
                        status="failed" if err else "ok", run_id=self.run.id,
                        summary=err or summarise(name, out or {}), details={"attempts": attempts, "mode": mode,
                                                                              "duration_ms": int((time.perf_counter() - t0) * 1000)},
                        outputs=[replay.ref("agent_execution", self.run.id, name)], commit=True)
            results = dict(state.get("results") or {})
            results[name] = out or {}
            errors = list(state.get("errors") or [])
            if err:
                errors.append({"agent": name, "error": err})
                self._progress(name, frac, f"{name} agent FAILED: {err}")
                return {"results": results, "errors": errors, "halted": critical}
            self._progress(name, frac, f"{name} agent completed")
            return {"results": results, "errors": errors}
        return _wrapped


def summarise(name: str, out: dict) -> str:
    """One-line, factual summary of an agent's structured output for the replay timeline."""
    keys = {"intake": ("evidence_items",), "entity_intelligence": ("entities", "relationships"), "timeline": ("events",),
            "relationship": ("nodes", "edges", "inferred"), "evidence_dna": ("pairs", "shared_identifiers"),
            "integrity_inspection": ("findings",), "contradiction": ("contradictions",), "evidence_gap": ("gaps",),
            "missing_evidence": ("recommendations",)}
    if name in keys:
        return ", ".join(f"{k.replace('_', ' ')}: {out.get(k)}" for k in keys[name] if k in out) or "completed"
    if name == "extraction":
        files = out.get("files", [])
        return f"{len(files)} file(s) processed, {sum(1 for f in files if f.get('status') == 'failed')} failed"
    if name == "investigation":
        return f"{len(out.get('candidates', []))} candidate hypothesis(es): " + "; ".join(c["pattern"] for c in out.get("candidates", []))
    if name == "counter_investigation":
        return "; ".join(f"{r['hypothesis_pattern']}: {len(r['items'])} challenge(s)" for r in out.get("results", []))
    if name == "verification":
        return "; ".join(f"{r['pattern']}: {r['rejected']}/{r['total']} item(s) rejected" for r in out.get("results", []))
    if name == "skeptical_review":
        return "; ".join(f"{r['pattern']}: {r['decision']}" for r in out.get("results", []))
    return "completed"


def _jsonable(o: Any):
    import json
    return json.loads(json.dumps(o, default=str))


# ----------------------------------------------------------------------------- processing agents
def processing_graph(r: Runner):
    db, case_id, user = r.db, r.run.case_id, r.user

    def intake(state):
        evs = list(db.scalars(select(Evidence).where(Evidence.case_id == case_id, Evidence.deleted_at.is_(None))))
        from ..storage import get_storage
        from ..services.intake import sha256_bytes
        store = get_storage()
        checks = []
        for e in evs:
            try:
                ok = sha256_bytes(store.get(e.storage_key)) == e.sha256
                e.last_verification, e.last_verified_at = ("match" if ok else "mismatch"), utcnow()
            except FileNotFoundError:
                ok, e.last_verification = False, "missing"
            checks.append({"evidence": e.evidence_code, "file": e.original_filename, "type": e.detected_type, "hash_ok": ok})
        db.flush()
        return {"evidence_items": len(evs), "integrity_checks": checks,
                "queued": [c["evidence"] for c in checks if c["hash_ok"]]}

    def extraction(state):
        out = []
        evs = list(db.scalars(select(Evidence).where(Evidence.case_id == case_id, Evidence.deleted_at.is_(None))
                              .order_by(Evidence.evidence_code)))
        for i, e in enumerate(evs):
            r._progress("extraction", 0.1 + 0.4 * (i / max(1, len(evs))), f"Extracting {e.original_filename}")
            res = process_evidence(db, e, user)
            res["file"] = e.original_filename
            out.append(res)
            db.commit()
        return {"files": out, "_mode": "deterministic+ml-engines"}

    def entity(state):
        idx = CaseIndex(db, case_id)
        res = build_entities(db, idx)
        db.commit()
        return res

    def timeline(state):
        res = build_timeline(db, CaseIndex(db, case_id))
        db.commit()
        return res

    def relationship(state):
        import networkx as nx
        ents = {e.id: e for e in db.scalars(select(Entity).where(Entity.case_id == case_id))}
        rels = list(db.scalars(select(Relationship).where(Relationship.case_id == case_id)))
        g = nx.Graph()
        for e in ents.values():
            g.add_node(e.id)
        for rel in rels:
            g.add_edge(rel.source_entity_id, rel.target_entity_id, weight=rel.weight)
        cent = nx.degree_centrality(g) if g.number_of_nodes() > 1 else {}
        btw = nx.betweenness_centrality(g) if 2 < g.number_of_nodes() < 800 else {}
        for eid, e in ents.items():
            a = dict(e.attributes or {})
            a["degree_centrality"] = round(cent.get(eid, 0.0), 4)
            a["betweenness"] = round(btw.get(eid, 0.0), 4)
            e.attributes = a
        db.commit()
        top = sorted(ents.values(), key=lambda e: -(e.attributes or {}).get("betweenness", 0))[:6]
        return {"nodes": g.number_of_nodes(), "edges": g.number_of_edges(),
                "components": nx.number_connected_components(g) if g.number_of_nodes() else 0,
                "observed": sum(1 for x in rels if x.basis == "observed"),
                "inferred": sum(1 for x in rels if x.basis == "inferred"),
                "key_entities": [{"type": e.type, "value": e.value} for e in top]}

    def evidence_dna(state):
        res = dna.analyse(db, CaseIndex(db, case_id), r.run.id)
        db.commit()
        return res

    def integrity_inspection(state):
        res = integrity.inspect_case(db, CaseIndex(db, case_id), r.run.id)
        db.commit()
        return res

    def contradiction(state):
        res = contra.detect(db, CaseIndex(db, case_id))
        db.commit()
        return res

    def gap(state):
        res = gapmod.detect(db, CaseIndex(db, case_id))
        db.commit()
        return res

    return _graph([
        ("intake", r.node("intake", intake, 0.05)),
        ("extraction", r.node("extraction", extraction, 0.1)),
        ("entity_intelligence", r.node("entity_intelligence", entity, 0.55)),
        ("timeline", r.node("timeline", timeline, 0.65)),
        ("relationship", r.node("relationship", relationship, 0.7)),
        ("evidence_dna", r.node("evidence_dna", evidence_dna, 0.74)),
        ("integrity_inspection", r.node("integrity_inspection", integrity_inspection, 0.78)),
        ("contradiction", r.node("contradiction", contradiction, 0.82)),
        ("evidence_gap", r.node("evidence_gap", gap, 0.9)),
    ])


# ----------------------------------------------------------------------------- adversarial agents
ADVERSARIAL_TIME_LIMIT_S = 180  # whole challenge run; each LLM call additionally has its own client timeout


def adversarial_graph(r: Runner):
    """Every candidate hypothesis is challenged independently. Agents exchange validated JSON
    (agents/schemas.py); a malformed output fails that agent instead of propagating."""
    from pydantic import ValidationError  # noqa: F401
    from . import predictor
    from . import schemas as S
    db, case_id = r.db, r.run.case_id
    box: dict = {"t0": time.perf_counter()}

    def ctx():
        if "ctx" not in box:
            box["ctx"] = adv.Ctx.load(db, CaseIndex(db, case_id))
        return box["ctx"]

    def budget():
        if time.perf_counter() - box["t0"] > ADVERSARIAL_TIME_LIMIT_S:
            raise TimeoutError(f"Challenge run exceeded its {ADVERSARIAL_TIME_LIMIT_S}s time limit")

    def investigation(state):
        cands = adv.investigation_candidates(ctx())
        out = {"candidates": cands, "limits": {"max_candidates": adv.MAX_CANDIDATES, "time_limit_s": ADVERSARIAL_TIME_LIMIT_S}}
        S.InvestigationOutput.model_validate(out)
        box["cands"] = cands
        return out

    def counter(state):
        res = []
        for h in box["cands"]:
            budget()
            c = adv.counter_agent(ctx(), h)
            S.CounterOutput.model_validate({"hypothesis_pattern": h["pattern"], **c})
            res.append({"hypothesis_pattern": h["pattern"], **c})
        box["counter"] = res
        return {"results": res, "_mode": res[0]["mode"] if res else "deterministic"}

    def verification(state):
        res = []
        for h, c in zip(box["cands"], box["counter"]):
            budget()
            v = adv.verification_agent(ctx(), h, c)
            S.VerificationOutput.model_validate(v)
            res.append(v)
        box["ver"] = res
        return {"results": [{"pattern": h["pattern"], **{k: v[k] for k in ("claims", "counter", "rejected", "total", "unsupported_claim_rate")}}
                            for h, v in zip(box["cands"], res)]}

    def review(state):
        res = []
        for h, c, v in zip(box["cands"], box["counter"], box["ver"]):
            rv = adv.reviewer_agent(ctx(), h, c, v)
            S.Review.model_validate(rv)
            res.append(rv)
        box["review"] = res
        return {"results": [{"pattern": h["pattern"], "decision": rv["decision"], "verdict": rv["verdict"], "reason": rv["reason"],
                             "independent_sources": rv["independent_sources"]} for h, rv in zip(box["cands"], res)]}

    def missing_evidence(state):
        recs = predictor.predict(db, ctx(), box["cands"][0], box["cands"][1:], box["counter"][0], r.run.id)
        db.commit()
        return {"recommendations": len(recs), "top": recs[:5]}

    def report(state):
        ids = []
        for rank, (h, c, v, rv) in enumerate(zip(box["cands"], box["counter"], box["ver"], box["review"])):
            cv, kv = v["claim_index"], v["counter_index"]
            hyp = Hypothesis(
                case_id=case_id, run_id=r.run.id, rank=rank, statement=h["statement"], pattern=h["pattern"],
                supporting=[{**cl, "verification": cv[cl["id"]]} for cl in h["claims"] if cl["kind"] == "observation" and cv[cl["id"]]["status"] != "rejected"],
                counterevidence=[{**k, "verification": kv[k["id"]]} for k in c["items"] if kv[k["id"]]["status"] != "rejected"
                                 and k["kind"] in ("contradiction", "challenge", "weak_association")],
                alternatives=[{**k, "verification": kv[k["id"]]} for k in c["items"] if kv[k["id"]]["status"] != "rejected"
                              and k["kind"] == "alternative_explanation"] + [{"kind": "other_pattern", "text": o["statement"], "pattern": o["pattern"]}
                                                                            for o in h.get("other_patterns", [])],
                assumptions=h.get("assumptions", []) + [cl["text"] for cl in h["claims"] if cl["kind"] == "inference"],
                missing_information=[{**k, "verification": kv[k["id"]]} for k in c["items"] if k["kind"] == "missing_information" and kv[k["id"]]["status"] != "rejected"],
                verification={"claims": v["claims"], "counter": v["counter"], "rejected": v["rejected"], "total": v["total"],
                              "unsupported_claim_rate": v["unsupported_claim_rate"],
                              "rejected_items": [x for x in v["claims"] + v["counter"] if x["status"] == "rejected"]},
                assessment=rv, verdict=rv["verdict"], decision=rv["decision"])
            db.add(hyp)
            db.flush()
            items = {it["id"]: it for it in h["claims"] + c["items"]}
            for vr in v["claims"] + v["counter"]:
                it = items.get(vr["id"], {})
                db.add(VerificationResult(case_id=case_id, hypothesis_id=hyp.id, item_id=vr["id"], item_text=it.get("text", "")[:2000],
                                          source=it.get("source", "engine"), status=vr["status"], checks=vr["checks"],
                                          citations=it.get("citations", [])))
            idx = ctx().idx
            for role, coll in (("supports", [cl for cl in h["claims"] if cl["kind"] == "observation"]), ("challenges", c["items"])):
                for it in coll:
                    for sid in it["citations"]:
                        if sid in idx.seg_by_id:
                            db.add(HypothesisEvidence(hypothesis_id=hyp.id, case_id=case_id, evidence_id=idx.seg_by_id[sid].evidence_id,
                                                      segment_id=sid, role=role, claim_id=it["id"]))
            href = replay.ref("hypothesis", hyp.id, h["pattern"])
            replay.emit(db, case_id, "hypothesis.created", component="investigation", actor="investigation agent", outputs=[href],
                        run_id=r.run.id, summary=f"Candidate {rank + 1}: {h['statement']}",
                        inputs=[replay.ref("segment", s_, "") for cl in h["claims"] for s_ in cl["citations"]][:12])
            replay.emit(db, case_id, "counter_investigation.performed", component="counter_investigation", actor="counter-investigation agent",
                        inputs=[href], run_id=r.run.id, summary=f"{len(c['items'])} challenge(s): " + "; ".join(k["text"][:90] for k in c["items"][:3]),
                        outputs=[replay.ref("segment", s_, "") for k in c["items"] for s_ in k["citations"]][:12])
            replay.emit(db, case_id, "verification.completed", component="verification", actor="verification agent", inputs=[href],
                        run_id=r.run.id, status="warning" if v["rejected"] else "ok",
                        summary=f"{v['total']} item(s) checked against the original segments; {v['rejected']} rejected")
            replay.emit(db, case_id, "reviewer.decision", component="skeptical_review", actor="skeptical reviewer agent", inputs=[href],
                        run_id=r.run.id, summary=f"{rv['decision']} ({rv['verdict'].replace('_', ' ')}): {rv['reason']}")
            ids.append(hyp.id)
        db.commit()
        return {"hypothesis_ids": ids, "decision": box["review"][0]["decision"], "verdict": box["review"][0]["verdict"]}

    return _graph([
        ("investigation", r.node("investigation", investigation, 0.12)),
        ("counter_investigation", r.node("counter_investigation", counter, 0.3)),
        ("verification", r.node("verification", verification, 0.5)),
        ("skeptical_review", r.node("skeptical_review", review, 0.65)),
        ("missing_evidence", r.node("missing_evidence", missing_evidence, 0.78)),
        ("report", r.node("report", report, 0.9)),
    ])


def run_processing(db: Session, run: AnalysisRun, user=None, cb=None, span=(0.0, 1.0)) -> dict:
    state = processing_graph(Runner(db, run, user, cb, span)).invoke({"case_id": run.case_id, "run_id": run.id, "results": {}, "errors": []})
    return state


def run_adversarial(db: Session, run: AnalysisRun, user=None, cb=None, span=(0.0, 1.0)) -> dict:
    state = adversarial_graph(Runner(db, run, user, cb, span)).invoke({"case_id": run.case_id, "run_id": run.id, "results": {}, "errors": []})
    return state


def finish(db: Session, run: AnalysisRun, state: dict, user=None):
    run.status = "failed" if state.get("errors") else "completed"
    run.error = "; ".join(f"{e['agent']}: {e['error']}" for e in state.get("errors", [])) or None
    run.progress = 1.0
    run.stage = "done" if run.status == "completed" else "failed"
    run.finished_at = utcnow()
    db.commit()
    audit.record(db, f"analysis.{run.kind}.{run.status}", user=user, case_id=run.case_id,
                 detail={"run_id": run.id, "orchestrator": ORCHESTRATOR, "errors": state.get("errors", [])})


def orchestrator_info() -> dict:
    return {"orchestrator": ORCHESTRATOR, "xxhash_shim_active": XXHASH_SHIM_ACTIVE}
