from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from .. import audit
from ..db import get_db
from ..models import (AnalysisRun, Case, CaseMember, Contradiction, Entity, Evidence, EvidenceGap, Hypothesis, TimelineEvent, User)
from ..schemas import CaseIn, CaseUpdate, MemberIn
from ..security import accessible_case_ids, case_access, get_case_or_403, get_current_user, require

router = APIRouter(prefix="/api/cases", tags=["cases"])


def clean_translations(tr: dict) -> dict:
    """Keep only Hindi / Kannada title, description and objective, with sane lengths."""
    limits = {"title": 200, "description": 5000, "objective": 3000}
    return {lang: {k: str(v).strip()[:limits[k]] for k, v in (fields or {}).items() if k in limits and str(v).strip()}
            for lang, fields in (tr or {}).items() if lang in ("hi", "kn")}


def case_summary(db: Session, c: Case, user: User | None = None) -> dict:
    def cnt(model, *conds):
        return db.scalar(select(func.count()).select_from(model).where(model.case_id == c.id, *conds)) or 0
    last = db.scalar(select(AnalysisRun).where(AnalysisRun.case_id == c.id).order_by(AnalysisRun.started_at.desc()).limit(1))
    from ..queries import primary_hypothesis
    hyp = primary_hypothesis(db, c.id)
    return {
        "id": c.id, "case_number": c.case_number, "title": c.title, "description": c.description, "objective": c.objective,
        "translations": c.translations or {},
        "case_type": c.case_type, "status": c.status, "priority": c.priority, "is_scenario": c.is_scenario,
        "default_timezone": c.default_timezone, "allow_external_ai": c.allow_external_ai,
        "created_at": c.created_at, "updated_at": c.updated_at,
        "access": case_access(db, user, c.id) if user else None,
        "counts": {"evidence": cnt(Evidence, Evidence.deleted_at.is_(None)), "entities": cnt(Entity), "events": cnt(TimelineEvent),
                   "contradictions": cnt(Contradiction), "contradictions_pending": cnt(Contradiction, Contradiction.review_status == "pending"),
                   "gaps": cnt(EvidenceGap), "gaps_open": cnt(EvidenceGap, EvidenceGap.review_status == "open")},
        "last_run": None if not last else {"id": last.id, "kind": last.kind, "status": last.status, "stage": last.stage,
                                           "progress": last.progress, "started_at": last.started_at},
        "verdict": hyp.verdict if hyp else None, "decision": hyp.decision if hyp else None,
    }


@router.get("")
def list_cases(include_scenarios: bool = False, status: str | None = None, q: str | None = Query(None, max_length=100),
               db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    ids = accessible_case_ids(db, user)
    stmt = select(Case).order_by(Case.updated_at.desc())
    if ids is not None:
        stmt = stmt.where(Case.id.in_(ids))
    if not include_scenarios:
        stmt = stmt.where(Case.is_scenario.is_(False))
    if status:
        stmt = stmt.where(Case.status == status)
    if q:
        like = f"%{q}%"
        stmt = stmt.where((Case.title.ilike(like)) | (Case.case_number.ilike(like)) | (Case.description.ilike(like)))
    return [case_summary(db, c, user) for c in db.scalars(stmt.limit(500))]


@router.post("", status_code=201)
def create_case(body: CaseIn, db: Session = Depends(get_db), user: User = Depends(require("case:create"))):
    n = db.scalar(select(func.count()).select_from(Case)) or 0
    data = body.model_dump()
    data["translations"] = clean_translations(data.get("translations") or {})
    c = Case(case_number=f"EVX-2026-{n + 1:04d}", created_by=user.id, **data)
    db.add(c)
    db.flush()
    db.add(CaseMember(case_id=c.id, user_id=user.id, access="owner"))
    db.commit()
    audit.record(db, "case.created", user=user, case_id=c.id, detail={"title": c.title, "number": c.case_number})
    return case_summary(db, c, user)


@router.get("/{case_id}")
def get_case(case_id: str, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    c = get_case_or_403(db, user, case_id)
    out = case_summary(db, c, user)
    out["members"] = [{"user_id": m.user_id, "email": db.get(User, m.user_id).email, "name": db.get(User, m.user_id).full_name,
                       "access": m.access} for m in c.members]
    return out


@router.patch("/{case_id}")
def update_case(case_id: str, body: CaseUpdate, db: Session = Depends(get_db), user: User = Depends(require("case:edit"))):
    c = get_case_or_403(db, user, case_id, write=True)
    changes = body.model_dump(exclude_none=True)
    if "allow_external_ai" in changes and case_access(db, user, case_id) != "owner":
        raise HTTPException(403, "Only the case owner can authorise sending evidence to an external AI provider")
    if "translations" in changes:
        changes["translations"] = clean_translations(changes["translations"])
    for k, v in changes.items():
        setattr(c, k, v)
    db.commit()
    audit.record(db, "case.updated", user=user, case_id=c.id, detail=changes)
    return case_summary(db, c, user)


@router.post("/{case_id}/archive")
def archive_case(case_id: str, db: Session = Depends(get_db), user: User = Depends(require("case:archive"))):
    c = get_case_or_403(db, user, case_id, write=True)
    c.status = "archived"
    db.commit()
    audit.record(db, "case.archived", user=user, case_id=c.id)
    return case_summary(db, c, user)


@router.post("/{case_id}/members")
def add_member(case_id: str, body: MemberIn, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    c = get_case_or_403(db, user, case_id, write=True)
    if case_access(db, user, case_id) != "owner":
        raise HTTPException(403, "Only case owners can share a case")
    target = db.scalar(select(User).where(User.email == body.email.lower()))
    if not target:
        raise HTTPException(404, "No user with that email")
    m = db.scalar(select(CaseMember).where(CaseMember.case_id == c.id, CaseMember.user_id == target.id))
    if m:
        m.access = body.access
    else:
        db.add(CaseMember(case_id=c.id, user_id=target.id, access=body.access))
    db.commit()
    audit.record(db, "case.shared", user=user, case_id=c.id, detail={"with": target.email, "access": body.access})
    return {"ok": True}


@router.delete("/{case_id}/members/{user_id}")
def remove_member(case_id: str, user_id: str, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    c = get_case_or_403(db, user, case_id, write=True)
    if case_access(db, user, case_id) != "owner" or user_id == user.id:
        raise HTTPException(403, "Only owners can remove other members")
    m = db.scalar(select(CaseMember).where(CaseMember.case_id == c.id, CaseMember.user_id == user_id))
    if m:
        db.delete(m)
        db.commit()
        audit.record(db, "case.unshared", user=user, case_id=c.id, detail={"user_id": user_id})
    return {"ok": True}
