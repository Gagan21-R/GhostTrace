"""Append-only, hash-chained audit log.

Each event stores ``hash = sha256(prev_hash + canonical_json(event))`` so any later edit
or deletion of a row breaks the chain and is detected by :func:`verify_chain`.
"""
from __future__ import annotations

import hashlib
import json
import threading

from sqlalchemy import select
from sqlalchemy.orm import Session

from .models import AuditEvent, User, utcnow

GENESIS = "0" * 64
_lock = threading.Lock()


def _digest(prev_hash: str, ts: str, user_id, case_id, evidence_id, action, detail) -> str:
    body = json.dumps({"ts": ts, "user": user_id, "case": case_id, "evidence": evidence_id,
                       "action": action, "detail": detail}, sort_keys=True, default=str)
    return hashlib.sha256((prev_hash + body).encode()).hexdigest()


def record(db: Session, action: str, *, user: User | None = None, case_id: str | None = None,
           evidence_id: str | None = None, detail: dict | None = None, commit: bool = True) -> AuditEvent:
    detail = detail or {}
    with _lock:
        last = db.scalar(select(AuditEvent).order_by(AuditEvent.id.desc()).limit(1))
        prev = last.hash if last else GENESIS
        ts = utcnow()
        h = _digest(prev, ts.isoformat(), user.id if user else None, case_id, evidence_id, action, detail)
        ev = AuditEvent(ts=ts, user_id=user.id if user else None, user_email=user.email if user else "system",
                        case_id=case_id, evidence_id=evidence_id, action=action, detail=detail,
                        prev_hash=prev, hash=h)
        db.add(ev)
        if commit:
            db.commit()
        else:
            db.flush()
    return ev


def verify_chain(db: Session) -> dict:
    prev = GENESIS
    count = 0
    for ev in db.scalars(select(AuditEvent).order_by(AuditEvent.id)):
        expected = _digest(prev, ev.ts.isoformat(), ev.user_id, ev.case_id, ev.evidence_id, ev.action, ev.detail)
        if ev.prev_hash != prev or ev.hash != expected:
            return {"valid": False, "checked": count, "broken_at": ev.id}
        prev = ev.hash
        count += 1
    return {"valid": True, "checked": count, "head": prev}
