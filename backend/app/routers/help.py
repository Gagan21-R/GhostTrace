"""Explain assistant, public landing-page data and the contact form.

``/api/help/*`` and ``/api/public/*`` contain no case data and work without signing in. The help
assistant only uses the external LLM when it is switched on *and* the caller is signed in.
"""
from __future__ import annotations

import re
import threading
import time
from collections import defaultdict, deque

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.security import OAuth2PasswordBearer
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import select
from sqlalchemy.orm import Session

from .. import audit
from ..config import get_settings
from ..db import get_db
from ..help import assistant
from ..help.knowledge import T
from ..models import ContactMessage, ScenarioDefinition, ScenarioRun, User
from ..security import get_current_user, require

router = APIRouter(tags=["help & public"])
_optional_token = OAuth2PasswordBearer(tokenUrl="/api/auth/login", auto_error=False)


def optional_user(token: str | None = Depends(_optional_token), db: Session = Depends(get_db)) -> User | None:
    if not token:
        return None
    try:
        return get_current_user(token, db)
    except HTTPException:
        return None


# ------------------------------------------------------------------ help
class ExplainIn(BaseModel):
    title: str = Field(..., min_length=1, max_length=200)
    page: str = Field("", max_length=200)
    topic: str | None = Field(None, max_length=64)
    context: str = Field("", max_length=500)


class ChatMsg(BaseModel):
    role: str = Field(..., pattern="^(user|assistant)$")
    content: str = Field(..., min_length=1, max_length=4000)


class ChatIn(BaseModel):
    messages: list[ChatMsg] = Field(..., min_length=1, max_length=30)
    page: str = Field("", max_length=200)


@router.get("/api/help/topics")
def topics():
    return {"mode_available": assistant.mode(),
            "topics": [{"key": t["key"], "title": t["title"], "summary": t["what"].split(". ")[0] + "."} for t in T.values()]}


@router.get("/api/help/topics/{key}")
def topic(key: str):
    t = T.get(key)
    if not t:
        raise HTTPException(404, "Unknown help topic")
    return {"answer": assistant.render(t), "topic": key, "related": assistant.related(t), "mode": "guide"}


@router.post("/api/help/explain")
def explain(body: ExplainIn):
    return assistant.explain(body.title, body.page, body.topic, body.context)


@router.post("/api/help/chat")
def chat(body: ChatIn, user: User | None = Depends(optional_user)):
    msgs = [m.model_dump() for m in body.messages]
    if user is None:  # anonymous visitors always get the offline guide
        last = next((m["content"] for m in reversed(msgs) if m["role"] == "user"), "")
        return assistant._guide_reply(last, body.page)
    return assistant.chat(msgs, body.page)


# ------------------------------------------------------------------ public landing data
@router.get("/api/public/showcase")
def showcase(db: Session = Depends(get_db)):
    """Scenario Lab case studies with their latest measured result. Synthetic data only."""
    out = []
    for sd in db.scalars(select(ScenarioDefinition).where(ScenarioDefinition.number < 90).order_by(ScenarioDefinition.number)):
        run = db.scalar(select(ScenarioRun).where(ScenarioRun.scenario_id == sd.id, ScenarioRun.status == "completed")
                        .order_by(ScenarioRun.started_at.desc()).limit(1))
        m = (run.metrics or {}) if run else {}
        ev = (run.evaluation or {}) if run else {}
        out.append({"id": sd.id, "number": sd.number, "title": sd.title, "summary": sd.summary, "difficulty": sd.difficulty,
                    "case_type": sd.case_type, "files": len(sd.files or []),
                    "file_types": sorted({f["file"].rsplit(".", 1)[-1] for f in (sd.files or []) if "file" in f}),
                    "variant_of": sd.variant_of,
                    "expected_outcome": (sd.ground_truth or {}).get("expected_outcome"),
                    "outcome": run.outcome if run else None,
                    "decision": (ev.get("actual") or {}).get("decision"),
                    "matches_expected": ev.get("outcome_matches_expected"),
                    "duration_ms": run.duration_ms if run else None,
                    "critical_found": m.get("critical_findings"),
                    "critical_total": sum(1 for f in (sd.ground_truth or {}).get("findings", []) if f.get("critical")),
                    "metrics": {k: m.get(k) for k in (
                        "contradiction_recall", "contradiction_precision", "dependency_recall", "timestamp_accuracy")}})
    return out


# ------------------------------------------------------------------ contact form
_EMAIL = re.compile(r"^[^@\s]{1,64}@[^@\s]{1,190}\.[A-Za-z]{2,24}$")
_hits: dict[str, deque] = defaultdict(deque)
_hits_lock = threading.Lock()


class ContactIn(BaseModel):
    name: str = Field(..., min_length=2, max_length=120)
    email: str = Field(..., max_length=254)
    organisation: str = Field("", max_length=160)
    topic: str = Field("general", pattern="^(general|demo|partnership|press|support)$")
    message: str = Field(..., min_length=10, max_length=4000)
    website: str = Field("", max_length=200)  # honeypot: humans leave it empty

    @field_validator("email")
    @classmethod
    def _email(cls, v: str) -> str:
        v = v.strip()
        if not _EMAIL.match(v):
            raise ValueError("Enter a valid email address")
        return v

    @field_validator("name", "organisation", "message")
    @classmethod
    def _strip(cls, v: str) -> str:
        return v.strip()


def _rate_limited(ip: str) -> bool:
    limit = get_settings().contact_rate_per_hour
    now = time.monotonic()
    with _hits_lock:
        q = _hits[ip]
        while q and now - q[0] > 3600:
            q.popleft()
        if len(q) >= limit:
            return True
        q.append(now)
        return False


@router.post("/api/public/contact", status_code=201)
def contact(body: ContactIn, request: Request, db: Session = Depends(get_db)):
    ip = request.client.host if request.client else "unknown"
    if body.website:  # bot filled the hidden field - pretend success, store nothing
        return {"status": "received"}
    if _rate_limited(ip):
        raise HTTPException(429, "Too many messages from this address. Please try again later.")
    msg = ContactMessage(name=body.name, email=body.email, organisation=body.organisation, topic=body.topic,
                         message=body.message, client_ip=ip)
    db.add(msg)
    db.commit()
    return {"status": "received", "id": msg.id}


@router.get("/api/admin/contact-messages")
def list_contact(db: Session = Depends(get_db), user: User = Depends(require("user:manage"))):
    rows = db.scalars(select(ContactMessage).order_by(ContactMessage.created_at.desc()).limit(200))
    return [{"id": m.id, "name": m.name, "email": m.email, "organisation": m.organisation, "topic": m.topic,
             "message": m.message, "status": m.status, "created_at": m.created_at} for m in rows]


class ContactStatus(BaseModel):
    status: str = Field(..., pattern="^(new|read|archived)$")


@router.patch("/api/admin/contact-messages/{msg_id}")
def update_contact(msg_id: str, body: ContactStatus, db: Session = Depends(get_db), user: User = Depends(require("user:manage"))):
    m = db.get(ContactMessage, msg_id)
    if not m:
        raise HTTPException(404, "Message not found")
    m.status = body.status
    audit.record(db, "contact_message_status", user=user, detail={"id": msg_id, "status": body.status}, commit=False)
    db.commit()
    return {"id": m.id, "status": m.status}
