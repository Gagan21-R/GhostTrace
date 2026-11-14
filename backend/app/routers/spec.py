"""Endpoints named in the GhostTrace API specification that are not already served elsewhere.

Where the spec path is an alias of an existing endpoint, it delegates to the same handler, so
authorisation, auditing and response schemas are identical.
"""
from __future__ import annotations

import csv
import io
import json

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import Response
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..analysis import nlp
from ..db import get_db
from ..models import (AgentExecution, AnalysisRun, AuditEvent, Entity, Evidence, ExtractedSegment, Relationship, Report,
                      ScenarioRun, TimelineEvent, User)
from ..security import get_case_or_403, get_current_user, require
from . import analysis, evidence, reports, scenarios

router = APIRouter(prefix="/api", tags=["specification endpoints"])


# ------------------------------------------------------------------ evidence
@router.get("/evidence/{evidence_id}/preview")
def evidence_preview(evidence_id: str, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    """Original file, served inline with sandboxing headers (images, PDF, audio, video; text as text/plain)."""
    return evidence.download(evidence_id, None, db, user)


@router.get("/evidence/{evidence_id}/history")
def evidence_history(evidence_id: str, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    e = evidence._get_ev(db, user, evidence_id)
    rows = db.scalars(select(AuditEvent).where(AuditEvent.evidence_id == e.id).order_by(AuditEvent.id))
    return [{"ts": a.ts, "action": a.action, "user": a.user_email, "detail": a.detail, "hash": a.hash} for a in rows]


@router.get("/cases/{case_id}/extracted-data")
def extracted_data(case_id: str, evidence_id: str | None = None, limit: int = Query(500, le=5000), offset: int = 0,
                   db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    get_case_or_403(db, user, case_id)
    codes = {e.id: (e.evidence_code, e.original_filename) for e in db.scalars(select(Evidence).where(Evidence.case_id == case_id))}
    stmt = select(ExtractedSegment).where(ExtractedSegment.case_id == case_id)
    if evidence_id:
        stmt = stmt.where(ExtractedSegment.evidence_id == evidence_id)
    total = db.scalar(select(func.count()).select_from(stmt.subquery()))
    segs = db.scalars(stmt.order_by(ExtractedSegment.evidence_id, ExtractedSegment.seq).offset(offset).limit(limit))
    return {"total": total, "offset": offset, "items": [
        {"segment_id": s.id, "evidence_id": s.evidence_id, "evidence_code": codes.get(s.evidence_id, ("?",))[0],
         "filename": codes.get(s.evidence_id, ("", "?"))[1], "locator": s.locator, "kind": s.kind, "author": s.author,
         "timestamp_raw": s.timestamp_raw, "text": s.text, "method": s.method, "confidence": s.confidence, "data": s.data}
        for s in segs]}


# ------------------------------------------------------------------ processing & intelligence
@router.get("/cases/{case_id}/processing-status")
def processing_status(case_id: str, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    get_case_or_403(db, user, case_id)
    run = db.scalar(select(AnalysisRun).where(AnalysisRun.case_id == case_id, AnalysisRun.kind == "processing")
                    .order_by(AnalysisRun.started_at.desc()).limit(1))
    by_status = dict(db.execute(select(Evidence.status, func.count()).where(Evidence.case_id == case_id, Evidence.deleted_at.is_(None))
                                .group_by(Evidence.status)).all())
    return {"evidence_by_status": by_status, "pending": by_status.get("uploaded", 0) + by_status.get("processing", 0),
            "run": None if not run else {"id": run.id, "status": run.status, "stage": run.stage, "progress": run.progress,
                                         "started_at": run.started_at, "finished_at": run.finished_at, "error": run.error}}


@router.get("/cases/{case_id}/relationships")
def relationships(case_id: str, basis: str | None = Query(None, pattern="^(observed|inferred)$"),
                  db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    get_case_or_403(db, user, case_id)
    ents = {e.id: e for e in db.scalars(select(Entity).where(Entity.case_id == case_id))}
    stmt = select(Relationship).where(Relationship.case_id == case_id)
    if basis:
        stmt = stmt.where(Relationship.basis == basis)
    return [{"id": r.id, "source": {"id": r.source_entity_id, "type": ents[r.source_entity_id].type, "value": ents[r.source_entity_id].value},
             "target": {"id": r.target_entity_id, "type": ents[r.target_entity_id].type, "value": ents[r.target_entity_id].value},
             "type": r.rel_type, "basis": r.basis, "weight": r.weight, "confidence": r.confidence, "description": r.description,
             "evidence_ids": r.evidence_ids, "segment_ids": r.segment_ids}
            for r in db.scalars(stmt) if r.source_entity_id in ents and r.target_entity_id in ents]


@router.get("/cases/{case_id}/evidence-gaps")
def evidence_gaps(case_id: str, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return analysis.gaps(case_id, db, user)


@router.post("/cases/{case_id}/investigate", status_code=202)
def investigate(case_id: str, db: Session = Depends(get_db), user: User = Depends(require("analysis:run"))):
    """Run the adversarial investigation engine (same as /adversarial)."""
    return analysis.start_adversarial(case_id, db, user)


@router.get("/cases/{case_id}/agent-executions")
def agent_executions(case_id: str, run_id: str | None = None, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    get_case_or_403(db, user, case_id)
    stmt = select(AgentExecution).where(AgentExecution.case_id == case_id)
    if run_id:
        stmt = stmt.where(AgentExecution.run_id == run_id)
    return [{"id": a.id, "run_id": a.run_id, "agent": a.agent, "seq": a.seq, "status": a.status, "mode": a.mode,
             "attempts": a.attempts, "duration_ms": a.duration_ms, "error": a.error, "started_at": a.started_at, "output": a.output}
            for a in db.scalars(stmt.order_by(AgentExecution.started_at.desc(), AgentExecution.seq).limit(500))]


@router.get("/cases/{case_id}/timeline/export")
def timeline_export(case_id: str, format: str = Query("csv", pattern="^(csv|json)$"), db: Session = Depends(get_db),
                    user: User = Depends(get_current_user)):
    case = get_case_or_403(db, user, case_id)
    rows = analysis.timeline(case_id, db, user)
    cols = ["display_time", "timestamp_kind", "timestamp_raw", "event_type", "title", "evidence_code", "filename", "conflict"]
    if format == "json":
        body = json.dumps([{k: r[k] for k in cols + ["occurred_at", "data"]} for r in rows], default=str, indent=1)
        return Response(body, media_type="application/json",
                        headers={"Content-Disposition": f'attachment; filename="{case.case_number}_timeline.json"'})
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(cols + ["timezone_note"])
    for r in rows:
        w.writerow([r[k] if r[k] is not None else "" for k in cols] + [(r["data"] or {}).get("timezone", "")])
    return Response(buf.getvalue(), media_type="text/csv",
                    headers={"Content-Disposition": f'attachment; filename="{case.case_number}_timeline.csv"'})


@router.get("/cases/{case_id}/history")
def case_history(case_id: str, limit: int = Query(200, le=1000), db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    """Case history for every member (the full hash-chained audit view needs audit:view)."""
    get_case_or_403(db, user, case_id)
    rows = db.scalars(select(AuditEvent).where(AuditEvent.case_id == case_id).order_by(AuditEvent.id.desc()).limit(limit))
    return [{"ts": a.ts, "action": a.action, "user": a.user_email, "evidence_id": a.evidence_id} for a in rows]


# ------------------------------------------------------------------ reports
@router.get("/cases/{case_id}/reports")
def case_reports(case_id: str, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    get_case_or_403(db, user, case_id)
    return reports.list_reports(case_id, db, user)


@router.get("/reports/{report_id}/download")
def report_download(report_id: str, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return reports.report_pdf(report_id, db, user)


@router.get("/reports/{report_id}/preview")
def report_preview(report_id: str, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    resp = reports.report_pdf(report_id, db, user)
    resp.headers["Content-Disposition"] = resp.headers["Content-Disposition"].replace("attachment", "inline")
    return resp


# ------------------------------------------------------------------ scenario lab
@router.post("/scenarios/{scenario_id}/runs", status_code=202)
def scenario_runs_create(scenario_id: str, db: Session = Depends(get_db), user: User = Depends(require("scenario:run"))):
    return scenarios.start(scenario_id, db, user)


@router.get("/scenarios/runs/{run_id}/status")
def scenario_run_status(run_id: str, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    r = db.get(ScenarioRun, run_id)
    if not r:
        raise HTTPException(404, "Run not found")
    agents = []
    if r.case_id:
        agents = [{"agent": a.agent, "status": a.status, "mode": a.mode, "duration_ms": a.duration_ms}
                  for a in db.scalars(select(AgentExecution).where(AgentExecution.case_id == r.case_id).order_by(AgentExecution.started_at, AgentExecution.seq))]
    return {"id": r.id, "status": r.status, "stage": r.stage, "progress": r.progress, "outcome": r.outcome, "agents": agents}


@router.get("/scenarios/runs/{run_id}/results")
def scenario_run_results(run_id: str, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    r = db.get(ScenarioRun, run_id)
    if not r:
        raise HTTPException(404, "Run not found")
    if r.status != "completed":
        raise HTTPException(409, f"Run is {r.status}; results are available when it completes")
    return {"outcome": r.outcome, "reason": r.outcome_reason, **(r.evaluation or {})}


@router.get("/scenarios/runs/{run_id}/report")
def scenario_run_report(run_id: str, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return scenarios.run_report(run_id, db, user)


@router.get("/scenarios/{scenario_id}/history")
def scenario_history(scenario_id: str, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return scenarios.list_runs(scenario_id, db, user)


class CompareIn(BaseModel):
    run_ids: list[str] = Field(min_length=2, max_length=6)


@router.post("/scenarios/compare")
def scenario_compare(body: CompareIn, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return scenarios.compare(",".join(body.run_ids), db, user)
