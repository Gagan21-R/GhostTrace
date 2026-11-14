"""Record a person's voice in the browser, store it as evidence, detect Kannada / Hindi / English, then re-run the analysis."""
from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from sqlalchemy.orm import Session

from .. import audit
from ..db import get_db
from ..models import AnalysisRun, User
from ..security import get_case_or_403, require
from ..services.evidence_service import ingest
from ..services.processing import process_evidence
from .analysis import start_full

router = APIRouter(prefix="/api", tags=["voice"])

LANG_NAMES = {"en": "English", "hi": "Hindi", "kn": "Kannada"}
EXT = {"audio/webm": ".webm", "audio/ogg": ".ogg", "audio/wav": ".wav", "audio/x-wav": ".wav", "audio/mpeg": ".mp3"}


@router.post("/cases/{case_id}/voice", status_code=201)
async def record_voice(case_id: str, audio: UploadFile = File(...), speaker: str = Form(""), consent: bool = Form(False),
                       reanalyse: bool = Form(True), db: Session = Depends(get_db), user: User = Depends(require("evidence:upload"))):
    case = get_case_or_403(db, user, case_id, write=True)
    if not consent:
        raise HTTPException(422, "Confirm that the person consented to being recorded")
    data = await audio.read()
    if len(data) < 2000:
        raise HTTPException(422, "Recording is too short")
    mime = (audio.content_type or "audio/webm").split(";")[0].strip()
    now = datetime.now(timezone.utc)
    name = f"voice_{now:%Y%m%d_%H%M%S}{EXT.get(mime, '.webm')}"
    who = speaker.strip()[:120] or "unnamed speaker"
    ev = ingest(db, case, user, name, data, category="voice recording", tags=["voice", "recorded-in-app"],
                collection_source=f"Recorded in GhostTrace by {user.full_name}; speaker: {who}; consent confirmed",
                collected_by=user.full_name, collected_at=now.isoformat(), declared_mime=mime)
    res = process_evidence(db, ev, user)
    db.commit()
    db.refresh(ev)
    meta = ev.file_metadata or {}
    lang = meta.get("language")
    from sqlalchemy import select
    from ..models import ExtractedSegment
    transcript = " ".join(s.text.strip() for s in db.scalars(select(ExtractedSegment).where(ExtractedSegment.evidence_id == ev.id)
                                                            .order_by(ExtractedSegment.seq)))
    out = {"evidence_id": ev.id, "code": ev.evidence_code, "sha256": ev.sha256, "status": ev.status,
           "language": lang, "language_name": LANG_NAMES.get(lang, lang or "unknown"),
           "language_probability": meta.get("language_probability"), "language_candidates": meta.get("language_candidates"),
           "duration_s": meta.get("duration_s"), "transcript": transcript[:2000], "error": res.get("error") or ev.processing_error}
    audit.record(db, "voice.recorded", user=user, case_id=case.id, evidence_id=ev.id,
                 detail={"speaker": who, "language": lang, "probability": meta.get("language_probability")})
    if reanalyse:
        out["reanalysis"] = start_full(db, case.id, user, "voice recording")
    return out
