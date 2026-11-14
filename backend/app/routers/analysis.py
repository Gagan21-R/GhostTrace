from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from .. import audit, replay
from ..agents import orchestrator as orch
from ..analysis import nlp
from ..db import get_db
from ..models import (AgentExecution, AnalysisRun, Contradiction, Entity, EntityMention, Evidence, EvidenceGap, Hypothesis,
                      Relationship, TimelineEvent, User)
from ..schemas import ReviewIn
from ..security import get_case_or_403, get_current_user, require
from ..services import jobs

router = APIRouter(prefix="/api", tags=["analysis"])


def _active(db, case_id):
    return db.scalar(select(AnalysisRun).where(AnalysisRun.case_id == case_id, AnalysisRun.status.in_(("queued", "running"))))


def _job(db, run_id, user_id, kind):
    run = db.get(AnalysisRun, run_id)
    user = db.get(User, user_id)
    run.status = "running"
    db.commit()
    try:
        st = orch.run_processing(db, run, user) if kind == "processing" else orch.run_adversarial(db, run, user)
        orch.finish(db, run, st, user)
    except Exception as e:
        db.rollback()
        run = db.get(AnalysisRun, run_id)
        run.status, run.error, run.stage = "failed", f"{type(e).__name__}: {e}", "failed"
        db.commit()


def _start(db, case_id, user, kind):
    if _active(db, case_id):
        raise HTTPException(409, "An analysis run is already in progress for this case")
    run = AnalysisRun(case_id=case_id, kind=kind, status="queued", started_by=user.id)
    db.add(run)
    db.commit()
    audit.record(db, f"analysis.{kind}.started", user=user, case_id=case_id, detail={"run_id": run.id})
    jobs.submit(_job, run.id, user.id, kind)
    return {"run_id": run.id, "status": "queued", "kind": kind}


def full_chain(db, proc_id, user_id):
    """Processing -> challenge run (when there are findings to test) -> alternative hypothesis engine."""
    _job(db, proc_id, user_id, "processing")
    proc = db.get(AnalysisRun, proc_id)
    has_findings = db.scalar(select(TimelineEvent.id).where(TimelineEvent.case_id == proc.case_id).limit(1)) or \
        db.scalar(select(Entity.id).where(Entity.case_id == proc.case_id).limit(1))
    if proc.status != "completed" or not has_findings:
        return
    adv = AnalysisRun(case_id=proc.case_id, kind="adversarial", status="queued", started_by=user_id)
    db.add(adv)
    db.commit()
    _job(db, adv.id, user_id, "adversarial")
    try:
        from ..agents import hypothesis_engine
        hypothesis_engine.run(db, proc.case_id, db.get(User, user_id), trigger="analysis chain")
    except Exception as e:  # the hypothesis engine must never undo a completed analysis
        import logging
        logging.getLogger("evidencex.hypotheses").warning("hypothesis engine failed: %s", e)
        db.rollback()


def start_full(db, case_id, user, trigger):
    if _active(db, case_id):
        return {"status": "skipped", "reason": "an analysis run is already in progress"}
    proc = AnalysisRun(case_id=case_id, kind="processing", status="queued", started_by=user.id)
    db.add(proc)
    db.commit()
    audit.record(db, "analysis.processing.started", user=user, case_id=case_id, detail={"run_id": proc.id, "trigger": trigger})
    jobs.submit(full_chain, proc.id, user.id)
    return {"status": "queued", "processing_run": proc.id}


@router.get("/runs/active")
def active_runs(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    """Everything currently processing that this user may see, with the page where it can be watched live."""
    from ..models import Case, CaseMember, ScenarioRun
    out = []
    member_cases = set(db.scalars(select(CaseMember.case_id).where(CaseMember.user_id == user.id)))
    for r in db.scalars(select(AnalysisRun).where(AnalysisRun.status.in_(("queued", "running"))).order_by(AnalysisRun.started_at)):
        if r.case_id not in member_cases and user.role != "admin":
            continue
        case = db.get(Case, r.case_id)
        if case is None or case.is_scenario:
            continue  # scenario cases are reported through their scenario run below
        out.append({"kind": r.kind, "label": {"processing": "Evidence processing", "adversarial": "Challenge engine",
                                             "hypotheses": "Hypothesis engine"}.get(r.kind, r.kind),
                    "title": case.title, "case_id": case.id, "stage": r.stage, "progress": r.progress,
                    "link": f"/cases/{case.id}/processing?live=1"})
    for s in db.scalars(select(ScenarioRun).where(ScenarioRun.status.in_(("queued", "running")))):
        if s.triggered_by != user.id and user.role != "admin":
            continue
        out.append({"kind": "scenario", "label": f"Scenario {s.test_code}", "title": s.scenario_id, "case_id": s.case_id,
                    "stage": s.stage, "progress": s.progress, "link": f"/scenarios/runs/{s.id}"})
    return out


@router.post("/cases/{case_id}/analyse", status_code=202)
def analyse_all(case_id: str, db: Session = Depends(get_db), user: User = Depends(require("analysis:run"))):
    """Run the whole analysis (processing, challenge, hypotheses) in one go - used after uploads and recordings."""
    get_case_or_403(db, user, case_id, write=True)
    if not db.scalar(select(Evidence.id).where(Evidence.case_id == case_id, Evidence.deleted_at.is_(None)).limit(1)):
        raise HTTPException(422, "Upload evidence before starting processing")
    out = start_full(db, case_id, user, "manual")
    if out["status"] != "queued":
        raise HTTPException(409, out["reason"])
    return out


@router.post("/cases/{case_id}/process", status_code=202)
def start_processing(case_id: str, db: Session = Depends(get_db), user: User = Depends(require("analysis:run"))):
    get_case_or_403(db, user, case_id, write=True)
    if not db.scalar(select(Evidence.id).where(Evidence.case_id == case_id, Evidence.deleted_at.is_(None)).limit(1)):
        raise HTTPException(422, "Upload evidence before starting processing")
    return _start(db, case_id, user, "processing")


@router.post("/cases/{case_id}/adversarial", status_code=202)
def start_adversarial(case_id: str, db: Session = Depends(get_db), user: User = Depends(require("analysis:run"))):
    get_case_or_403(db, user, case_id, write=True)
    if not db.scalar(select(TimelineEvent.id).where(TimelineEvent.case_id == case_id).limit(1)) and \
            not db.scalar(select(Entity.id).where(Entity.case_id == case_id).limit(1)):
        raise HTTPException(422, "Run evidence processing first - the adversarial engine works on extracted findings")
    return _start(db, case_id, user, "adversarial")


@router.get("/cases/{case_id}/runs")
def list_runs(case_id: str, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    get_case_or_403(db, user, case_id)
    runs = db.scalars(select(AnalysisRun).where(AnalysisRun.case_id == case_id).order_by(AnalysisRun.started_at.desc()).limit(30))
    return [{"id": r.id, "kind": r.kind, "status": r.status, "stage": r.stage, "progress": r.progress, "error": r.error,
             "started_at": r.started_at, "finished_at": r.finished_at, "log": (r.log or [])[-60:]} for r in runs]


@router.get("/runs/{run_id}")
def get_run(run_id: str, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    r = db.get(AnalysisRun, run_id)
    if not r:
        raise HTTPException(404, "Run not found")
    get_case_or_403(db, user, r.case_id)
    agents = db.scalars(select(AgentExecution).where(AgentExecution.run_id == r.id).order_by(AgentExecution.seq))
    return {"id": r.id, "case_id": r.case_id, "kind": r.kind, "status": r.status, "stage": r.stage, "progress": r.progress,
            "error": r.error, "started_at": r.started_at, "finished_at": r.finished_at, "log": r.log or [],
            "agents": [{"agent": a.agent, "status": a.status, "mode": a.mode, "attempts": a.attempts, "duration_ms": a.duration_ms,
                        "error": a.error, "output": a.output} for a in agents]}


@router.get("/cases/{case_id}/entities")
def entities(case_id: str, type: str | None = None, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    get_case_or_403(db, user, case_id)
    stmt = select(Entity).where(Entity.case_id == case_id)
    if type:
        stmt = stmt.where(Entity.type == type)
    ents = list(db.scalars(stmt))
    mentions: dict[str, list] = {}
    codes = {e.id: (e.evidence_code, e.original_filename) for e in db.scalars(select(Evidence).where(Evidence.case_id == case_id))}
    for m in db.scalars(select(EntityMention).where(EntityMention.case_id == case_id)):
        mentions.setdefault(m.entity_id, []).append({"evidence_id": m.evidence_id, "evidence_code": codes.get(m.evidence_id, ("?",))[0],
                                                     "filename": codes.get(m.evidence_id, ("", "?"))[1], "segment_id": m.segment_id,
                                                     "snippet": m.snippet, "method": m.method, "confidence": m.confidence})
    return [{"id": e.id, "type": e.type, "value": e.value, "normalized": e.normalized, "confidence": e.confidence,
             "attributes": e.attributes, "mentions": mentions.get(e.id, []),
             "risk": nlp.url_risk(e.normalized, nlp.KNOWN_BRAND_DOMAINS) if e.type == "website" else None}
            for e in sorted(ents, key=lambda x: (-len(mentions.get(x.id, [])), x.type))]


def timeline_analysis(rows: list[dict]) -> dict:
    """Silent periods, simultaneous events across sources, and header-vs-body reported times."""
    from datetime import timedelta
    inc = [r for r in rows if r["occurred_at"] and r["timestamp_kind"] in ("source_reported", "estimated")]
    inc.sort(key=lambda r: r["occurred_at"])
    gaps = [(inc[i], inc[i + 1], inc[i + 1]["occurred_at"] - inc[i]["occurred_at"]) for i in range(len(inc) - 1)]
    silent = []
    if len(gaps) >= 3:
        med = sorted(g[2] for g in gaps)[len(gaps) // 2]
        thr = max(timedelta(hours=24), med * 3)
        silent = [{"from": a["display_time"], "to": b["display_time"], "after_event": a["id"], "before_event": b["id"],
                   "hours": round(d.total_seconds() / 3600, 1)} for a, b, d in gaps if d >= thr]
    groups, cur = [], []
    for r in inc:
        if cur and (r["occurred_at"] - cur[0]["occurred_at"]) <= timedelta(minutes=2):
            cur.append(r)
        else:
            if len({x["evidence_id"] for x in cur}) > 1:
                groups.append([x["id"] for x in cur])
            cur = [r]
    if len({x["evidence_id"] for x in cur}) > 1:
        groups.append([x["id"] for x in cur])
    comparisons = []
    by_ev: dict[str, list] = {}
    for r in rows:
        if r["occurred_at"] and r["timestamp_kind"] == "source_reported":
            by_ev.setdefault(r["evidence_id"], []).append(r)
    for ev_id, rs in by_ev.items():
        hdr = [x for x in rs if x["title"].startswith("Email:")]
        body = [x for x in rs if not x["title"].startswith("Email:") and x["data"].get("channel") == "email"]
        for h in hdr:
            for b in body:
                diff = (h["occurred_at"] - b["occurred_at"]).total_seconds() / 60
                if 0 < abs(diff) <= 24 * 60:
                    comparisons.append({"evidence_code": h["evidence_code"], "header_time": h["display_time"], "reported_in_body": b["display_time"],
                                        "minutes_apart": round(diff, 1), "event": b["title"][:120],
                                        "note": "The email was sent after the time it reports" if diff > 0 else "The email reports a time after it was sent"})
    return {"silent_periods": silent, "simultaneous_groups": groups, "reported_vs_header": comparisons}


@router.get("/cases/{case_id}/timeline")
def timeline(case_id: str, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    get_case_or_403(db, user, case_id)
    codes = {e.id: (e.evidence_code, e.original_filename, e.detected_type) for e in db.scalars(select(Evidence).where(Evidence.case_id == case_id))}
    evs = list(db.scalars(select(TimelineEvent).where(TimelineEvent.case_id == case_id)))
    evs.sort(key=lambda e: (e.occurred_at is None, e.occurred_at.isoformat() if e.occurred_at else ""))
    return [{"id": e.id, "occurred_at": e.occurred_at, "display_time": nlp.display_dt(e.occurred_at, e.data) if e.occurred_at else None,
             "timestamp_raw": e.timestamp_raw, "timestamp_kind": e.timestamp_kind, "event_type": e.event_type, "title": e.title,
             "description": e.description, "actors": e.actors, "entity_ids": e.entity_ids, "data": e.data, "conflict": e.conflict,
             "evidence_id": e.evidence_id, "segment_id": e.segment_id, "evidence_code": codes.get(e.evidence_id, ("?",))[0],
             "filename": codes.get(e.evidence_id, ("", "?"))[1], "source_type": codes.get(e.evidence_id, ("", "", "?"))[2]} for e in evs]


@router.get("/cases/{case_id}/timeline/analysis")
def timeline_insights(case_id: str, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return timeline_analysis(timeline(case_id, db, user))


@router.get("/cases/{case_id}/graph")
def graph(case_id: str, include_documents: bool = False, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    get_case_or_403(db, user, case_id)
    ents = {e.id: e for e in db.scalars(select(Entity).where(Entity.case_id == case_id))}
    rels = list(db.scalars(select(Relationship).where(Relationship.case_id == case_id)))
    codes = {e.id: (e.evidence_code, e.original_filename) for e in db.scalars(select(Evidence).where(Evidence.case_id == case_id))}
    nodes = [{"id": e.id, "label": e.value, "type": e.type, "mentions": len((e.attributes or {}).get("sources", [])),
              "centrality": (e.attributes or {}).get("degree_centrality", 0), "betweenness": (e.attributes or {}).get("betweenness", 0),
              "inferred_only": False} for e in ents.values()]
    edges = [{"id": r.id, "source": r.source_entity_id, "target": r.target_entity_id, "type": r.rel_type, "basis": r.basis,
              "weight": r.weight, "description": r.description, "confidence": r.confidence,
              "evidence": [{"evidence_id": i, "code": codes.get(i, ("?",))[0], "filename": codes.get(i, ("", "?"))[1]} for i in r.evidence_ids],
              "segment_ids": r.segment_ids} for r in rels if r.source_entity_id in ents and r.target_entity_id in ents]
    if include_documents:
        for ev_id, (code, name) in codes.items():
            nodes.append({"id": "doc:" + ev_id, "label": f"{code} {name}", "type": "document", "mentions": 0, "centrality": 0,
                          "betweenness": 0, "inferred_only": False})
        for m in db.scalars(select(EntityMention).where(EntityMention.case_id == case_id)):
            eid = f"{m.entity_id}-{m.evidence_id}"
            if not any(x["id"] == eid for x in edges[-50:]):
                edges.append({"id": eid, "source": m.entity_id, "target": "doc:" + m.evidence_id, "type": "appears_in", "basis": "observed",
                              "weight": 1, "description": "Entity appears in this evidence item", "confidence": m.confidence,
                              "evidence": [{"evidence_id": m.evidence_id, "code": codes.get(m.evidence_id, ("?",))[0]}], "segment_ids": [m.segment_id]})
    return {"nodes": nodes, "edges": edges}


def _contra_out(c: Contradiction) -> dict:
    return {"id": c.id, "code": c.code, "category": c.category, "field": c.field, "key": c.key, "description": c.description,
            "source_a": c.source_a, "source_b": c.source_b, "reason": c.reason, "confidence": c.confidence, "priority": c.priority, "classification": c.classification,
            "same_event_basis": c.same_event_basis, "suggested_action": c.suggested_action, "review_status": c.review_status,
            "reviewer_note": c.reviewer_note, "reviewed_by": c.reviewed_by, "created_at": c.created_at}


@router.get("/cases/{case_id}/contradictions")
def contradictions(case_id: str, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    get_case_or_403(db, user, case_id)
    return [_contra_out(c) for c in db.scalars(select(Contradiction).where(Contradiction.case_id == case_id).order_by(Contradiction.code))]


@router.patch("/contradictions/{cid}")
def review_contradiction(cid: str, body: ReviewIn, db: Session = Depends(get_db), user: User = Depends(require("review:decide"))):
    c = db.get(Contradiction, cid)
    if not c:
        raise HTTPException(404, "Not found")
    get_case_or_403(db, user, c.case_id)
    if body.status not in ("pending", "confirmed", "dismissed"):
        raise HTTPException(422, "status must be pending, confirmed or dismissed")
    c.review_status, c.reviewer_note, c.reviewed_by = body.status, body.note, user.id
    db.commit()
    audit.record(db, "review.contradiction", user=user, case_id=c.case_id, detail={"code": c.code, "status": body.status, "note": body.note})
    replay.emit(db, c.case_id, "human.review", component="human_review", actor=user, inputs=[replay.ref("contradiction", c.id, c.code)],
                summary=f"{c.code} marked {body.status}" + (f": {body.note}" if body.note else ""), commit=True)
    return _contra_out(c)


@router.get("/cases/{case_id}/gaps")
def gaps(case_id: str, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    get_case_or_403(db, user, case_id)
    return [{"id": g.id, "code": g.code, "category": g.category, "key": g.key, "description": g.description, "related": g.related,
             "checklist": g.checklist, "why_it_matters": g.why_it_matters, "severity": g.severity, "review_status": g.review_status, "reviewer_note": g.reviewer_note,
             "created_at": g.created_at}
            for g in db.scalars(select(EvidenceGap).where(EvidenceGap.case_id == case_id).order_by(EvidenceGap.code))]


@router.patch("/gaps/{gid}")
def review_gap(gid: str, body: ReviewIn, db: Session = Depends(get_db), user: User = Depends(require("review:decide"))):
    g = db.get(EvidenceGap, gid)
    if not g:
        raise HTTPException(404, "Not found")
    get_case_or_403(db, user, g.case_id)
    if body.status not in ("open", "resolved", "dismissed"):
        raise HTTPException(422, "status must be open, resolved or dismissed")
    g.review_status, g.reviewer_note = body.status, body.note
    db.commit()
    audit.record(db, "review.gap", user=user, case_id=g.case_id, detail={"code": g.code, "status": body.status, "note": body.note})
    replay.emit(db, g.case_id, "human.review", component="human_review", actor=user, inputs=[replay.ref("gap", g.id, g.code)],
                summary=f"{g.code} marked {body.status}" + (f": {body.note}" if body.note else ""), commit=True)
    return {"ok": True, "review_status": g.review_status}


def _hyp_out(h: Hypothesis, db) -> dict:
    agents = db.scalars(select(AgentExecution).where(AgentExecution.run_id == h.run_id).order_by(AgentExecution.seq))
    return {"id": h.id, "run_id": h.run_id, "statement": h.statement, "pattern": h.pattern, "supporting": h.supporting,
            "counterevidence": h.counterevidence, "alternatives": h.alternatives, "assumptions": h.assumptions,
            "missing_information": h.missing_information, "verification": h.verification, "assessment": h.assessment,
            "verdict": h.verdict, "decision": h.decision, "rank": h.rank, "human_review_status": h.human_review_status, "human_review_note": h.human_review_note,
            "created_at": h.created_at,
            "agents": [{"agent": a.agent, "status": a.status, "mode": a.mode, "duration_ms": a.duration_ms, "output": a.output,
                        "error": a.error} for a in agents]}


@router.get("/cases/{case_id}/hypotheses")
def hypotheses(case_id: str, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    get_case_or_403(db, user, case_id)
    from ..queries import latest_hypotheses
    return [_hyp_out(h, db) for h in latest_hypotheses(db, case_id)]


@router.patch("/hypotheses/{hid}")
def review_hypothesis(hid: str, body: ReviewIn, db: Session = Depends(get_db), user: User = Depends(require("review:decide"))):
    h = db.get(Hypothesis, hid)
    if not h:
        raise HTTPException(404, "Not found")
    get_case_or_403(db, user, h.case_id)
    if body.status not in ("pending", "accepted", "rejected", "needs_more_evidence"):
        raise HTTPException(422, "status must be pending, accepted, rejected or needs_more_evidence")
    h.human_review_status, h.human_review_note = body.status, body.note
    db.commit()
    audit.record(db, "review.hypothesis", user=user, case_id=h.case_id, detail={"status": body.status, "note": body.note})
    replay.emit(db, h.case_id, "human.review", component="human_review", actor=user, inputs=[replay.ref("hypothesis", h.id, h.pattern)],
                summary=f"Reviewer decision {h.decision} on '{h.pattern}' marked {body.status} by a human" + (f": {body.note}" if body.note else ""), commit=True)
    return _hyp_out(h, db)
