from __future__ import annotations

from datetime import timedelta

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from .. import audit
from ..agents.orchestrator import orchestrator_info
from ..config import get_settings
from ..db import get_db
from ..models import (AnalysisRun, AuditEvent, Case, Contradiction, Evidence, EvidenceGap, Hypothesis, Report, ScenarioRun, User,
                      utcnow)
from ..security import accessible_case_ids, get_case_or_403, get_current_user, require
from ..services.engines import engine_status

router = APIRouter(prefix="/api", tags=["dashboard & audit"])


@router.get("/dashboard")
def dashboard(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    ids = accessible_case_ids(db, user)

    def scope(stmt, col):
        return stmt.where(col.in_(ids)) if ids is not None else stmt

    real = select(Case.id).where(Case.is_scenario.is_(False))
    real = scope(real, Case.id)
    case_ids = list(db.scalars(real))

    def count(model, *conds):
        return db.scalar(select(func.count()).select_from(model).where(model.case_id.in_(case_ids), *conds)) or 0

    cases = list(db.scalars(select(Case).where(Case.id.in_(case_ids))))
    runs = list(db.scalars(select(AnalysisRun).where(AnalysisRun.case_id.in_(case_ids)).order_by(AnalysisRun.started_at.desc()).limit(8)))
    titles = {c.id: c.title for c in cases}
    acts = list(db.scalars(scope(select(AuditEvent).order_by(AuditEvent.id.desc()), AuditEvent.case_id).limit(15)))
    week = [0] * 14
    now = utcnow()
    for e in db.scalars(select(Evidence.intake_at).where(Evidence.case_id.in_(case_ids), Evidence.intake_at >= now - timedelta(days=14))):
        week[max(0, min(13, 13 - (now - e).days))] += 1
    by_type = dict(db.execute(select(Evidence.detected_type, func.count()).where(Evidence.case_id.in_(case_ids)).group_by(Evidence.detected_type)).all())
    contra_cat = dict(db.execute(select(Contradiction.category, func.count()).where(Contradiction.case_id.in_(case_ids)).group_by(Contradiction.category)).all())
    verdicts = {}
    for c in cases:
        from ..queries import primary_hypothesis
        ph = primary_hypothesis(db, c.id)
        h = ph.decision if ph else None
        if h:
            verdicts[h] = verdicts.get(h, 0) + 1
    srun = list(db.scalars(select(ScenarioRun).where(ScenarioRun.status == "completed").order_by(ScenarioRun.finished_at.desc()).limit(50)))
    outcomes = {}
    for r in srun:
        outcomes[r.outcome] = outcomes.get(r.outcome, 0) + 1
    return {
        "stats": {"total_cases": len(cases), "active_cases": sum(c.status == "active" for c in cases),
                  "completed_cases": sum(c.status == "completed" for c in cases), "archived_cases": sum(c.status == "archived" for c in cases),
                  "evidence_files": count(Evidence, Evidence.deleted_at.is_(None)),
                  "evidence_processed": count(Evidence, Evidence.status == "processed"),
                  "contradictions": count(Contradiction), "pending_reviews": count(Contradiction, Contradiction.review_status == "pending")
                  + count(Hypothesis, Hypothesis.human_review_status == "pending"),
                  "open_gaps": count(EvidenceGap, EvidenceGap.review_status == "open"),
                  "running_jobs": count(AnalysisRun, AnalysisRun.status.in_(("queued", "running"))),
                  "pending_processing": count(Evidence, Evidence.status.in_(("uploaded", "processing")), Evidence.deleted_at.is_(None))},
        "evidence_by_type": by_type, "contradictions_by_category": contra_cat, "verdicts": verdicts, "intake_14d": week,
        "scenario_outcomes": outcomes,
        "integrity": {k or "not_verified": v for k, v in db.execute(select(Evidence.last_verification, func.count()).where(
            Evidence.case_id.in_(case_ids), Evidence.deleted_at.is_(None)).group_by(Evidence.last_verification)).all()},
        "unresolved_contradictions": count(Contradiction, Contradiction.review_status == "pending"),
        "high_priority_gaps": count(EvidenceGap, EvidenceGap.severity == "high", EvidenceGap.review_status == "open"),
        "recent_decisions": [{"case_id": h.case_id, "case": titles.get(h.case_id), "decision": h.decision, "pattern": h.pattern,
                              "human_review": h.human_review_status, "created_at": h.created_at}
                             for h in db.scalars(select(Hypothesis).where(Hypothesis.case_id.in_(case_ids), Hypothesis.rank == 0)
                                                 .order_by(Hypothesis.created_at.desc()).limit(6))],
        "recent_cases": [{"id": c.id, "title": c.title, "case_number": c.case_number, "status": c.status, "priority": c.priority,
                          "updated_at": c.updated_at} for c in sorted(cases, key=lambda c: c.updated_at, reverse=True)[:6]],
        "recent_reports": [{"id": r.id, "case_id": r.case_id, "title": r.title, "kind": r.kind, "created_at": r.created_at}
                           for r in db.scalars(select(Report).where(Report.case_id.in_(case_ids)).order_by(Report.created_at.desc()).limit(6))],
        "scenario_activity": [{"id": r.id, "test_code": r.test_code, "scenario_id": r.scenario_id, "outcome": r.outcome,
                               "finished_at": r.finished_at} for r in srun[:6]],
        "recent_runs": [{"id": r.id, "case_id": r.case_id, "case": titles.get(r.case_id), "kind": r.kind, "status": r.status,
                         "stage": r.stage, "progress": r.progress, "started_at": r.started_at} for r in runs],
        "recent_activity": [{"ts": a.ts, "action": a.action, "user": a.user_email, "case_id": a.case_id,
                             "case": titles.get(a.case_id), "detail": a.detail} for a in acts],
    }


@router.get("/cases/{case_id}/audit")
def case_audit(case_id: str, limit: int = Query(300, le=2000), db: Session = Depends(get_db), user: User = Depends(require("audit:view"))):
    get_case_or_403(db, user, case_id)
    rows = db.scalars(select(AuditEvent).where(AuditEvent.case_id == case_id).order_by(AuditEvent.id.desc()).limit(limit))
    return [{"id": a.id, "ts": a.ts, "action": a.action, "user": a.user_email, "evidence_id": a.evidence_id, "detail": a.detail,
             "hash": a.hash, "prev_hash": a.prev_hash} for a in rows]


@router.get("/audit/verify")
def verify_audit(db: Session = Depends(get_db), user: User = Depends(require("audit:view"))):
    return audit.verify_chain(db)


@router.get("/system/status")
def status(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    s = get_settings()
    return {"engines": engine_status(), "orchestration": orchestrator_info(),
            "storage": s.storage_backend, "database": s.database_url.split(":")[0], "graph": s.graph_backend,
            "max_upload_mb": s.max_upload_mb, "retention_days": s.retention_days,
            "llm_mode": "live LLM augmentation" if engine_status()["llm"]["configured"] else
                        "deterministic engine only (no LLM key configured) - results are rule-based, not LLM-generated"}


@router.post("/system/retention/apply")
def apply_retention(db: Session = Depends(get_db), user: User = Depends(require("user:manage"))):
    s = get_settings()
    if not s.retention_days:
        return {"purged": 0, "note": "RETENTION_DAYS is 0 (keep indefinitely)"}
    cutoff = utcnow() - timedelta(days=s.retention_days)
    from ..storage import get_storage
    purged = 0
    for e in db.scalars(select(Evidence).join(Case, Case.id == Evidence.case_id).where(
            Case.status == "archived", Evidence.intake_at < cutoff, Evidence.legal_hold.is_(False))):
        get_storage().delete(e.storage_key)
        e.deleted_at = e.deleted_at or utcnow()
        e.status = "purged"
        purged += 1
        audit.record(db, "evidence.purged", user=user, case_id=e.case_id, evidence_id=e.id, detail={"policy_days": s.retention_days}, commit=False)
    db.commit()
    return {"purged": purged}
