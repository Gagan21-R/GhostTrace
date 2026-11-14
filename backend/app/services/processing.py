"""Per-evidence extraction job. Reads the write-once original, never modifies it, and stores
segments plus a text derivative (with its own hash) separately."""
from __future__ import annotations

import re
import time

from sqlalchemy import delete
from sqlalchemy.orm import Session

from .. import audit, replay
from ..models import utcnow
from .engines import tool_version
from ..models import Evidence, EvidenceDerivative, ExtractedSegment
from ..storage import get_storage, make_key
from .extraction import extract
from .intake import sha256_bytes


INJECTION_RX = re.compile(r"ignore (?:all |any )?(?:previous|prior|above) (?:instructions|prompts)|disregard (?:the|your|all) "
                          r"(?:instructions|rules)|you are (?:now )?(?:an? )?(?:ai|assistant|chatbot|language model|chatgpt)\b|system prompt|"
                          r"act as (?:an? )?(?:administrator|admin|system)|mark (?:this|the) (?:case|evidence) as (?:closed|verified|genuine)|"
                          r"do not (?:report|flag|mention) this", re.I)


def process_evidence(db: Session, ev: Evidence, user=None) -> dict:
    me = replay.ref("evidence", ev.id, f"{ev.evidence_code} {ev.original_filename}")
    store = get_storage()
    t0 = time.perf_counter()
    data = store.get(ev.storage_key)
    if sha256_bytes(data) != ev.sha256:
        ev.status = "failed"
        ev.processing_error = "Integrity check failed before processing: stored file no longer matches intake hash"
        ev.last_verification = "mismatch"
        audit.record(db, "evidence.integrity_failure", user=user, case_id=ev.case_id, evidence_id=ev.id,
                     detail={"stage": "pre-processing"}, commit=False)
        replay.emit(db, ev.case_id, "integrity.check_failed", component="integrity", actor="sha256", status="failed",
                    inputs=[me], summary="Stored file no longer matches its intake hash; extraction refused")
        return {"evidence_id": ev.id, "status": "failed", "error": ev.processing_error}
    ev.status = "processing"
    db.flush()
    replay.emit(db, ev.case_id, "extraction.started", component="extraction", actor="extraction pipeline", inputs=[me],
                summary=f"Extracting {ev.detected_type} evidence {ev.original_filename}")
    try:
        ex = extract(ev.detected_type, data, ev.original_filename)
    except Exception as e:
        ev.status = "failed"
        ev.processing_error = f"{type(e).__name__}: {e}"[:500]
        audit.record(db, "evidence.processing_failed", user=user, case_id=ev.case_id, evidence_id=ev.id,
                     detail={"error": ev.processing_error}, commit=False)
        replay.emit(db, ev.case_id, "extraction.failed", component="extraction", actor="extraction pipeline", inputs=[me],
                    status="failed", summary=ev.processing_error)
        return {"evidence_id": ev.id, "status": "failed", "error": ev.processing_error}

    db.execute(delete(ExtractedSegment).where(ExtractedSegment.evidence_id == ev.id))
    for i, s in enumerate(ex.segments):
        db.add(ExtractedSegment(case_id=ev.case_id, evidence_id=ev.id, seq=i, **s))
    meta = dict(ev.file_metadata or {})
    meta.update(ex.metadata)
    # Evidence is untrusted: flag embedded instructions aimed at AI systems. They are never executed;
    # the flag tells investigators the item may try to manipulate automated analysis.
    hits = sorted({m.group(0).lower() for s in ex.segments for m in INJECTION_RX.finditer(s["text"])})
    meta["prompt_injection_indicators"] = hits[:10]
    meta["extraction"] = {"method": ex.method, "segments": len(ex.segments), "warnings": ex.warnings,
                          "unavailable_engine": ex.unavailable, "duration_ms": int((time.perf_counter() - t0) * 1000),
                          "tool": ex.method.split(":")[-1], "tool_version": tool_version(ex.method),
                          "parameters": ex.parameters, "processed_at": utcnow().isoformat()}
    ev.file_metadata = meta
    if ex.segments:
        text = ex.full_text.encode("utf-8")
        key = make_key(ev.case_id, "derived", "x.txt")
        store.put(key, text)
        kind = "ocr_text" if ev.detected_type == "image" else "transcript" if ev.detected_type in ("audio", "video") else "extracted_text"
        db.add(EvidenceDerivative(evidence_id=ev.id, kind=kind, storage_key=key, sha256=sha256_bytes(text), method=ex.method))
    if ex.unavailable:
        ev.status = "unsupported" if not ex.segments else "processed"
        ev.processing_error = "; ".join(ex.warnings)
    else:
        ev.status = "processed"
        ev.processing_error = "; ".join(ex.warnings) or None
    audit.record(db, "evidence.processed", user=user, case_id=ev.case_id, evidence_id=ev.id,
                 detail={"method": ex.method, "segments": len(ex.segments), "status": ev.status}, commit=False)
    label = "OCR" if "ocr" in ex.method else "transcription" if "asr" in ex.method else "parsing"
    replay.emit(db, ev.case_id, f"extraction.completed", component="extraction", actor=f"{ex.method} {tool_version(ex.method)}",
                inputs=[me], outputs=[replay.ref("segments", ev.id, f"{len(ex.segments)} segments")],
                status="warning" if (ex.unavailable or ex.warnings) else "ok",
                summary=f"{label.capitalize()} of {ev.evidence_code} produced {len(ex.segments)} segment(s)"
                        + (f"; {'; '.join(ex.warnings)}" if ex.warnings else ""),
                details={"method": ex.method, "unavailable_engine": ex.unavailable})
    db.flush()
    return {"evidence_id": ev.id, "status": ev.status, "segments": len(ex.segments), "method": ex.method,
            "warnings": ex.warnings}
