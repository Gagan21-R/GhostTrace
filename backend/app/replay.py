"""Investigation Replay event log.

Components call :func:`emit` at the moment they act, so the replay is reconstructed from what
actually happened (persisted rows), never from a generated narrative. Each event references the
evidence, segments, findings or runs it consumed and produced so the UI can open them.
"""
from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from .models import InvestigationEvent, User


def ref(type_: str, id_: str | None, label: str = "") -> dict:
    return {"type": type_, "id": id_, "label": label}


def emit(db: Session, case_id: str, action: str, *, component: str, actor: User | str | None = None,
         inputs: list[dict] | None = None, outputs: list[dict] | None = None, summary: str = "",
         details: dict[str, Any] | None = None, status: str = "ok", run_id: str | None = None,
         commit: bool = False) -> InvestigationEvent:
    who = actor.email if isinstance(actor, User) else (actor or component)
    ev = InvestigationEvent(case_id=case_id, action=action, actor=who, component=component, status=status,
                            inputs=inputs or [], outputs=outputs or [], summary=summary[:2000],
                            details=details or {}, run_id=run_id)
    db.add(ev)
    if commit:
        db.commit()
    else:
        db.flush()
    return ev
