"""Shared intake path used by the upload API and the Scenario Lab, so scenarios exercise
exactly the same code as real uploads."""
from __future__ import annotations

import io

from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from .. import audit, replay
from ..config import get_settings
from ..models import Case, Evidence, User
from ..storage import get_storage, make_key
from .intake import inspect_upload

settings = get_settings()


def next_evidence_code(db: Session, case_id: str) -> str:
    n = db.scalar(select(func.count()).select_from(Evidence).where(Evidence.case_id == case_id)) or 0
    return f"EV-{n + 1:03d}"


def dhash(data: bytes) -> str | None:
    """64-bit difference hash of an image; small Hamming distance = visually near-identical."""
    try:
        from PIL import Image
        img = Image.open(io.BytesIO(data)).convert("L").resize((9, 8))
        px = list(img.getdata())
        bits = "".join("1" if px[r * 9 + c] > px[r * 9 + c + 1] else "0" for r in range(8) for c in range(8))
        return f"{int(bits, 2):016x}"
    except Exception:
        return None


def ingest(db: Session, case: Case, user: User | None, filename: str, data: bytes, *, category: str = "uncategorised",
           tags: list[str] | None = None, collection_source: str = "", collected_at: str | None = None,
           collected_by: str | None = None, declared_mime: str | None = None) -> Evidence:
    safe_name = filename.replace("\\", "/").split("/")[-1][:255] or "unnamed"
    res = inspect_upload(safe_name, data, settings.max_upload_mb * 1024 * 1024)
    if not res.ok:
        audit.record(db, "evidence.rejected", user=user, case_id=case.id, detail={"filename": safe_name, "reason": res.reason,
                                                                                   "sha256": res.sha256, "size": res.size})
        replay.emit(db, case.id, "evidence.rejected", component="intake", actor=user, status="failed",
                    inputs=[replay.ref("file", None, safe_name)], summary=f"{safe_name} rejected: {res.reason}",
                    details={"sha256": res.sha256, "size": res.size}, commit=True)
        raise HTTPException(422, {"filename": safe_name, "reason": res.reason})
    dup = db.scalar(select(Evidence).where(Evidence.case_id == case.id, Evidence.sha256 == res.sha256, Evidence.deleted_at.is_(None))
                    .order_by(Evidence.intake_at))
    key = make_key(case.id, "original", safe_name)
    get_storage().put(key, data)
    warnings = list(res.warnings or [])
    if declared_mime and declared_mime not in ("application/octet-stream", "") and declared_mime.split(";")[0] != res.mime_type:
        warnings.append(f"Declared MIME type {declared_mime} differs from the type detected from content ({res.mime_type})")
    ev = Evidence(case_id=case.id, evidence_code=next_evidence_code(db, case.id), original_filename=safe_name, storage_key=key,
                  mime_type=res.mime_type, detected_type=res.detected_type, size_bytes=res.size, sha256=res.sha256,
                  category=(category or "uncategorised")[:64], tags=[t[:40] for t in (tags or [])][:20],
                  collection_source=(collection_source or "")[:2000], collected_at=collected_at, collected_by=collected_by,
                  uploaded_by=user.id if user else None, status="uploaded", duplicate_of=dup.id if dup else None,
                  perceptual_hash=dhash(data) if res.detected_type == "image" else None,
                  file_metadata={"intake_warnings": warnings, "declared_mime": declared_mime}, last_verification="match")
    db.add(ev)
    db.flush()
    audit.record(db, "evidence.intake", user=user, case_id=case.id, evidence_id=ev.id,
                 detail={"filename": safe_name, "sha256": res.sha256, "size": res.size, "type": res.detected_type,
                         "code": ev.evidence_code, "duplicate_of": dup.evidence_code if dup else None}, commit=False)
    me = replay.ref("evidence", ev.id, f"{ev.evidence_code} {safe_name}")
    replay.emit(db, case.id, "evidence.uploaded", component="evidence_vault", actor=user, outputs=[me],
                summary=f"{safe_name} stored write-once as {ev.evidence_code} ({res.size} bytes)",
                details={"collection_source": collection_source, "collected_by": collected_by})
    replay.emit(db, case.id, "hash.calculated", component="integrity", actor="sha256", inputs=[me],
                summary=f"SHA-256 {res.sha256}", details={"sha256": res.sha256})
    replay.emit(db, case.id, "filetype.validated", component="intake", actor="content-signature validator", inputs=[me],
                summary=f"Content signature matches .{safe_name.rsplit('.', 1)[-1]}; detected type {res.detected_type} ({res.mime_type})",
                details={"warnings": warnings}, status="warning" if warnings else "ok")
    if dup:
        replay.emit(db, case.id, "duplicate.detected", component="evidence_dna", actor="sha256", inputs=[me],
                    outputs=[replay.ref("evidence", dup.id, f"{dup.evidence_code} {dup.original_filename}")],
                    summary=f"{ev.evidence_code} is byte-identical to {dup.evidence_code}; it is not independent corroboration",
                    status="warning")
    db.commit()
    return ev
