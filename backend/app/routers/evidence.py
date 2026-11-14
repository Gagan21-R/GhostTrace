from __future__ import annotations

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile
from fastapi.responses import Response
from sqlalchemy import select
from sqlalchemy.orm import Session

from .. import audit
from ..db import get_db
from ..models import AuditEvent, Evidence, EvidenceDerivative, ExtractedSegment, User, utcnow
from ..schemas import EvidenceUpdate
from ..security import get_case_or_403, get_current_user, require
from ..services.evidence_service import ingest
from ..services.intake import sha256_bytes
from ..storage import get_storage

router = APIRouter(prefix="/api", tags=["evidence"])

INLINE_TYPES = {"image/png", "image/jpeg", "image/webp", "application/pdf", "audio/mpeg", "audio/wav", "video/mp4"}


def ev_out(e: Evidence, segments: int | None = None) -> dict:
    meta = e.file_metadata or {}
    return {"id": e.id, "case_id": e.case_id, "code": e.evidence_code, "filename": e.original_filename, "mime_type": e.mime_type,
            "type": e.detected_type, "size": e.size_bytes, "sha256": e.sha256, "category": e.category, "tags": e.tags or [],
            "collection_source": e.collection_source, "collected_at": e.collected_at, "collected_by": e.collected_by,
            "uploaded_by": e.uploaded_by, "intake_at": e.intake_at, "status": e.status, "processing_error": e.processing_error,
            "metadata": meta, "extraction": meta.get("extraction"), "last_verified_at": e.last_verified_at,
            "last_verification": e.last_verification, "legal_hold": e.legal_hold, "deleted": e.deleted_at is not None,
            "injection_indicators": meta.get("prompt_injection_indicators", []), "segments": segments,
            "duplicate_of": e.duplicate_of, "perceptual_hash": e.perceptual_hash}


@router.post("/cases/{case_id}/evidence", status_code=201)
async def upload(case_id: str, files: list[UploadFile] = File(...), category: str = Form("uncategorised"),
                 tags: str = Form(""), collection_source: str = Form(""), collected_by: str = Form(""),
                 collected_at: str = Form(""), db: Session = Depends(get_db), user: User = Depends(require("evidence:upload"))):
    case = get_case_or_403(db, user, case_id, write=True)
    if len(files) > 50:
        raise HTTPException(422, "At most 50 files per upload")
    results = []
    for f in files:
        data = await f.read()
        try:
            ev = ingest(db, case, user, f.filename or "unnamed", data, category=category,
                        tags=[t.strip() for t in tags.split(",") if t.strip()], collection_source=collection_source,
                        collected_by=collected_by or None, collected_at=collected_at or None, declared_mime=f.content_type)
            results.append({"filename": f.filename, "ok": True, "evidence": ev_out(ev)})
        except HTTPException as e:
            detail = e.detail if isinstance(e.detail, dict) else {"reason": str(e.detail)}
            results.append({"filename": f.filename, "ok": False, "status": e.status_code, "reason": detail.get("reason")})
    return {"results": results, "accepted": sum(r["ok"] for r in results), "rejected": sum(not r["ok"] for r in results)}


@router.get("/cases/{case_id}/evidence")
def list_evidence(case_id: str, type: str | None = None, status: str | None = None, category: str | None = None,
                  q: str | None = Query(None, max_length=200), include_deleted: bool = False,
                  db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    get_case_or_403(db, user, case_id)
    stmt = select(Evidence).where(Evidence.case_id == case_id).order_by(Evidence.evidence_code)
    if not include_deleted:
        stmt = stmt.where(Evidence.deleted_at.is_(None))
    if type:
        stmt = stmt.where(Evidence.detected_type == type)
    if status:
        stmt = stmt.where(Evidence.status == status)
    if category:
        stmt = stmt.where(Evidence.category == category)
    evs = list(db.scalars(stmt))
    if q:
        ql = q.lower()
        hit_ids = set(db.scalars(select(ExtractedSegment.evidence_id).where(ExtractedSegment.case_id == case_id,
                                                                           ExtractedSegment.text.ilike(f"%{q}%"))))
        evs = [e for e in evs if ql in e.original_filename.lower() or ql in (e.category or "").lower()
               or any(ql in t.lower() for t in e.tags or []) or e.id in hit_ids or ql == e.sha256]
    counts = {}
    for eid in db.scalars(select(ExtractedSegment.evidence_id).where(ExtractedSegment.case_id == case_id)):
        counts[eid] = counts.get(eid, 0) + 1
    return [ev_out(e, counts.get(e.id, 0)) for e in evs]


def _get_ev(db, user, evidence_id, write=False) -> Evidence:
    e = db.get(Evidence, evidence_id)
    if not e:
        raise HTTPException(404, "Evidence not found")
    get_case_or_403(db, user, e.case_id, write=write)
    return e


@router.get("/evidence/{evidence_id}")
def get_evidence(evidence_id: str, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    e = _get_ev(db, user, evidence_id)
    segs = list(db.scalars(select(ExtractedSegment).where(ExtractedSegment.evidence_id == e.id).order_by(ExtractedSegment.seq)))
    ders = list(db.scalars(select(EvidenceDerivative).where(EvidenceDerivative.evidence_id == e.id)))
    hist = list(db.scalars(select(AuditEvent).where(AuditEvent.evidence_id == e.id).order_by(AuditEvent.id)))
    out = ev_out(e, len(segs))
    out["segment_list"] = [{"id": s.id, "seq": s.seq, "locator": s.locator, "kind": s.kind, "author": s.author,
                            "timestamp_raw": s.timestamp_raw, "text": s.text, "method": s.method, "confidence": s.confidence,
                            "data": s.data} for s in segs]
    out["derivatives"] = [{"id": d.id, "kind": d.kind, "sha256": d.sha256, "method": d.method, "created_at": d.created_at} for d in ders]
    out["history"] = [{"ts": h.ts, "action": h.action, "user": h.user_email, "detail": h.detail} for h in hist]
    return out


@router.patch("/evidence/{evidence_id}")
def update_evidence(evidence_id: str, body: EvidenceUpdate, db: Session = Depends(get_db), user: User = Depends(require("evidence:upload"))):
    e = _get_ev(db, user, evidence_id, write=True)
    changes = body.model_dump(exclude_none=True)
    for k, v in changes.items():
        setattr(e, k, v)
    db.commit()
    audit.record(db, "evidence.metadata_updated", user=user, case_id=e.case_id, evidence_id=e.id, detail=changes)
    return ev_out(e)


@router.post("/evidence/{evidence_id}/verify")
def verify(evidence_id: str, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    e = _get_ev(db, user, evidence_id)
    try:
        current = sha256_bytes(get_storage().get(e.storage_key))
        result = "match" if current == e.sha256 else "mismatch"
    except FileNotFoundError:
        current, result = None, "missing"
    e.last_verification, e.last_verified_at = result, utcnow()
    db.commit()
    audit.record(db, "evidence.verified", user=user, case_id=e.case_id, evidence_id=e.id,
                 detail={"result": result, "expected": e.sha256, "computed": current})
    return {"evidence_id": e.id, "result": result, "expected_sha256": e.sha256, "computed_sha256": current,
            "verified_at": e.last_verified_at,
            "note": "A match shows the stored file is byte-identical to the file received at intake. It does not prove the "
                    "file was genuine or unaltered before intake."}


@router.post("/cases/{case_id}/verify-all")
def verify_all(case_id: str, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    get_case_or_403(db, user, case_id)
    out = []
    for e in db.scalars(select(Evidence).where(Evidence.case_id == case_id, Evidence.deleted_at.is_(None))):
        try:
            res = "match" if sha256_bytes(get_storage().get(e.storage_key)) == e.sha256 else "mismatch"
        except FileNotFoundError:
            res = "missing"
        e.last_verification, e.last_verified_at = res, utcnow()
        out.append({"evidence_id": e.id, "code": e.evidence_code, "filename": e.original_filename, "result": res})
    db.commit()
    audit.record(db, "case.integrity_verified", user=user, case_id=case_id,
                 detail={"checked": len(out), "mismatches": sum(o["result"] != "match" for o in out)})
    return {"checked": len(out), "results": out}


@router.get("/evidence/{evidence_id}/file")
def download(evidence_id: str, derivative: str | None = None, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    e = _get_ev(db, user, evidence_id)
    if derivative:
        d = db.get(EvidenceDerivative, derivative)
        if not d or d.evidence_id != e.id:
            raise HTTPException(404, "Derivative not found")
        data, mime, name = get_storage().get(d.storage_key), "text/plain; charset=utf-8", f"{e.evidence_code}_{d.kind}.txt"
    else:
        data = get_storage().get(e.storage_key)
        mime = e.mime_type if e.mime_type in INLINE_TYPES else "text/plain; charset=utf-8" if e.detected_type in (
            "text", "chat", "email", "spreadsheet") and not e.original_filename.endswith(".xlsx") else "application/octet-stream"
        name = e.original_filename
    audit.record(db, "evidence.accessed", user=user, case_id=e.case_id, evidence_id=e.id,
                 detail={"derivative": derivative or "original"})
    disp = "inline" if mime in INLINE_TYPES or mime.startswith("text/plain") else "attachment"
    safe = "".join(ch for ch in name if ch.isalnum() or ch in "._-") or "file"
    return Response(data, media_type=mime, headers={"Content-Disposition": f'{disp}; filename="{safe}"',
                                                    "X-Content-Type-Options": "nosniff",
                                                    "Content-Security-Policy": "sandbox; default-src 'none'",
                                                    "Cache-Control": "private, no-store"})


@router.delete("/evidence/{evidence_id}")
def delete_evidence(evidence_id: str, db: Session = Depends(get_db), user: User = Depends(require("evidence:delete"))):
    e = _get_ev(db, user, evidence_id, write=True)
    if e.legal_hold:
        raise HTTPException(409, "Evidence is under legal hold and cannot be deleted")
    e.deleted_at = utcnow()  # soft delete: the original stays in write-once storage until retention purge
    db.commit()
    audit.record(db, "evidence.deleted", user=user, case_id=e.case_id, evidence_id=e.id, detail={"soft": True})
    return {"ok": True, "note": "Evidence hidden from analysis. The original remains in storage until the retention policy purges it."}
