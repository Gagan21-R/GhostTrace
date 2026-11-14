"""Integrity inspection: indicators for human review, never automatic proof of tampering.

Separates four things the UI keeps apart:
  * file integrity since intake        (SHA-256, handled by the vault)
  * provenance supplied at collection   (collection source/by/at)
  * metadata observations               (what the file's own metadata says)
  * potential anomalies                 (inconsistencies worth a human look)
Authenticity cannot be established by hashing; nothing here claims it.
"""
from __future__ import annotations

import re
from datetime import datetime, timedelta, timezone

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from .. import replay
from ..models import EvidenceDependency, IntegrityFinding
from . import nlp
from .index import CaseIndex

EDIT_TOOLS = re.compile(r"photoshop|gimp|paint\.net|pixelmator|snapseed|canva|acrobat pro|pdfelement|ilovepdf|smallpdf", re.I)


def _pdf_date(raw: str | None):
    if not raw:
        return None
    m = re.match(r"D?:?(\d{4})(\d{2})(\d{2})(\d{2})?(\d{2})?(\d{2})?", raw)
    if not m:
        return None
    y, mo, d, h, mi, s = (int(x) if x else 0 for x in m.groups())
    try:
        return datetime(y, mo, d, h, mi, s, tzinfo=timezone.utc)
    except ValueError:
        return None


def _iso(raw):
    try:
        dt = datetime.fromisoformat(str(raw).replace("Z", "+00:00"))
        return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
    except Exception:
        return None


def inspect_case(db: Session, idx: CaseIndex, run_id: str | None = None) -> dict:
    db.execute(delete(IntegrityFinding).where(IntegrityFinding.case_id == idx.case_id))
    out: list[IntegrityFinding] = []

    def add(ev, check, severity, observation, **detail):
        out.append(IntegrityFinding(case_id=idx.case_id, evidence_id=ev.id, check=check, severity=severity,
                                    observation=observation, detail=detail))

    for e in idx.evidence.values():
        meta = e.file_metadata or {}
        segs = idx.segments_of(e.id)
        content_dates = [d for s in segs[:200] for d in [nlp.parse_datetime(r)[0] for r, _ in nlp.find_dates(s.text)[:3]] if d]
        if s_ts := [nlp.parse_datetime(s.timestamp_raw)[0] for s in segs if s.timestamp_raw]:
            content_dates += [d for d in s_ts if d]
        intake = e.intake_at
        for w in meta.get("intake_warnings") or []:
            if "MIME" in w:
                add(e, "mime_mismatch", "medium", w)
        if e.duplicate_of:
            add(e, "exact_duplicate", "info", f"Byte-identical to {idx.ev(e.duplicate_of).evidence_code if e.duplicate_of in idx.evidence else 'another item'}; "
                "count it once when assessing corroboration.", duplicate_of=e.duplicate_of)
        if not (e.collection_source or "").strip():
            add(e, "provenance_missing", "low", "No collection record (who collected it, from where, when). Integrity since intake is "
                "verifiable; provenance before intake is not documented.")
        # ---- documents
        if e.detected_type == "pdf":
            info = meta.get("pdf_info") or {}
            c, m = _pdf_date(info.get("CreationDate")), _pdf_date(info.get("ModDate"))
            if not c and not m:
                add(e, "metadata_missing", "info", "PDF has no creation or modification date in its metadata.")
            if c and m and m < c - timedelta(minutes=1):
                add(e, "metadata_inconsistent", "medium", f"PDF modification date ({m:%d %b %Y}) is earlier than its creation date ({c:%d %b %Y}).")
            if c and m and m - c > timedelta(days=30):
                add(e, "late_modification", "low", f"PDF was modified {(m - c).days} days after it was created.")
            for d, label in ((c, "creation"), (m, "modification")):
                if d and intake and d > intake + timedelta(hours=24):
                    add(e, "future_timestamp", "medium", f"PDF {label} date ({d:%d %b %Y}) is after the file was received.")
            if EDIT_TOOLS.search(" ".join(str(v) for v in info.values())):
                add(e, "editing_software", "low", f"PDF metadata names editing software: {info.get('Producer') or info.get('Creator')}.")
        if e.detected_type == "docx":
            cp = meta.get("core_properties") or {}
            c, m = _iso(cp.get("created")), _iso(cp.get("modified"))
            if c and m and m < c - timedelta(minutes=1):
                add(e, "metadata_inconsistent", "medium", f"Document modified date ({m:%d %b %Y}) precedes its created date ({c:%d %b %Y}).")
            if c and content_dates and abs((min(content_dates) - c).days) > 365:
                add(e, "metadata_inconsistent", "low", f"Document 'created' metadata ({c:%d %b %Y}) is more than a year away from the dates "
                    f"in its content ({min(content_dates):%d %b %Y}); template or re-saved files often carry such dates.")
            if cp.get("last_modified_by") and cp.get("author") and cp["last_modified_by"] != cp["author"]:
                add(e, "metadata_observation", "info", f"Author '{cp['author']}' differs from last modified by '{cp['last_modified_by']}'.")
        if e.detected_type == "image":
            exif = meta.get("exif") or {}
            if not exif:
                add(e, "metadata_missing", "info", "No camera/EXIF metadata (normal for screenshots and messaging-app images).")
            if EDIT_TOOLS.search(exif.get("Software", "")):
                add(e, "editing_software", "medium", f"Image metadata names editing software: {exif.get('Software')}.")
            conf = meta.get("ocr_mean_confidence")
            if conf is not None and conf < 0.8:
                add(e, "low_extraction_confidence", "low", f"Mean OCR confidence is {conf:.0%}; extracted values should be checked against the image.")
        if e.detected_type == "email":
            hdr = next((s for s in segs if s.kind == "email_header"), None)
            if hdr:
                missing = [n for n, ok in (("Received", hdr.data.get("received")), ("Message-ID", hdr.data.get("message_id")),
                                          ("Date", hdr.data.get("date_iso")), ("Authentication-Results", hdr.data.get("authentication_results"))) if not ok]
                if missing:
                    add(e, "missing_email_headers", "medium" if "Received" in missing or "Message-ID" in missing else "low",
                        f"Email lacks header(s): {', '.join(missing)}. Routing and origin cannot be checked without them.", missing=missing)
                date = _iso(hdr.data.get("date_iso")) if hdr.data.get("date_iso") else None
                if date and intake and date > intake + timedelta(hours=24):
                    add(e, "future_timestamp", "medium", f"Email Date header ({date:%d %b %Y}) is after the file was received.")
        if content_dates and intake and max(content_dates) > intake + timedelta(days=1):
            add(e, "future_timestamp", "low", f"Content mentions a date ({max(content_dates):%d %b %Y}) after the file was received; check whether it is a planned date or an error.")

    # ---- copies that should match but do not
    deps = list(db.scalars(select(EvidenceDependency).where(EvidenceDependency.case_id == idx.case_id,
                                                            EvidenceDependency.relation.in_(("near_duplicate", "derived")))))
    for d in deps:
        def vals(ev_id, t):
            return {f.norm if t != "amount" else f.extra.get("amount") for f in idx.facts if f.evidence_id == ev_id and f.type == t}
        diffs = []
        for t in ("amount", "txn_ref", "order_id", "quantity"):
            va, vb = vals(d.evidence_a_id, t), vals(d.evidence_b_id, t)
            if va and vb and not (va & vb):
                diffs.append(f"{t}: {sorted(va)[:2]} vs {sorted(vb)[:2]}")
        if diffs:
            ea, eb = idx.ev(d.evidence_a_id), idx.ev(d.evidence_b_id)
            add(eb, "inconsistent_copies", "high", f"{eb.evidence_code} looks like a copy of {ea.evidence_code} ({d.relation.replace('_', ' ')}) "
                f"but key values differ: {'; '.join(diffs)}.", other=ea.id)

    for f in out:
        db.add(f)
    db.flush()
    flagged = [f for f in out if f.severity in ("medium", "high")]
    for f in flagged:
        replay.emit(db, idx.case_id, "integrity.anomaly_flagged", component="integrity_inspection", actor="integrity_inspection",
                    inputs=[replay.ref("evidence", f.evidence_id, idx.ev(f.evidence_id).evidence_code)],
                    outputs=[replay.ref("integrity_finding", f.id, f.check)], summary=f.observation, status="warning", run_id=run_id)
    by = {}
    for f in out:
        by[f.severity] = by.get(f.severity, 0) + 1
    return {"findings": len(out), "by_severity": by}
