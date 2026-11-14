"""Naive Bayes classification, message authenticity (impersonation / fake screenshot) and the tool-calling console."""
from __future__ import annotations

import time

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from .. import audit
from ..analysis import naive_bayes as nb
from ..analysis.authenticity import VERDICTS
from ..db import get_db
from ..models import AuthenticityAssessment, Evidence, MessageClassification, User
from ..security import get_case_or_403, get_current_user
from ..tools import case_tools  # noqa: F401
from ..tools.case_tools import CaseCtx
from ..tools.registry import REGISTRY, ToolSession

router = APIRouter(prefix="/api", tags=["naive bayes, authenticity, tools"])


class TextIn(BaseModel):
    text: str = Field(min_length=1, max_length=4000)


@router.post("/nb/classify")
def nb_classify(body: TextIn, user: User = Depends(get_current_user)):
    return nb.classify(body.text)


@router.get("/nb/model")
def nb_model(user: User = Depends(get_current_user)):
    return nb.model_card()


def _codes(db, case_id):
    return {e.id: (e.evidence_code, e.original_filename) for e in db.scalars(select(Evidence).where(Evidence.case_id == case_id))}


@router.get("/cases/{case_id}/classifications")
def classifications(case_id: str, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    get_case_or_403(db, user, case_id)
    codes = _codes(db, case_id)
    rows = list(db.scalars(select(MessageClassification).where(MessageClassification.case_id == case_id)))
    out = [{"id": r.id, "evidence_id": r.evidence_id, "code": codes.get(r.evidence_id, ("?", ""))[0],
            "file": codes.get(r.evidence_id, ("", "?"))[1], "scope": r.scope, "locator": r.locator, "author": r.author,
            "text": r.text, "label": r.label, "label_name": nb.LABELS.get(r.label, r.label),
            "language": nb.detect_language(r.text), "language_name": nb.LANG_NAMES[nb.detect_language(r.text)], "confidence": r.confidence,
            "uncertain": r.uncertain, "probabilities": r.probabilities, "top_terms": r.top_terms} for r in rows]
    out.sort(key=lambda x: (x["scope"] != "message", x["label"] == "benign", -x["confidence"]))
    return {"items": out, "labels": nb.LABELS}


@router.get("/cases/{case_id}/authenticity")
def authenticity(case_id: str, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    get_case_or_403(db, user, case_id)
    codes = _codes(db, case_id)
    rows = list(db.scalars(select(AuthenticityAssessment).where(AuthenticityAssessment.case_id == case_id)
                           .order_by(AuthenticityAssessment.created_at)))
    out = []
    for r in rows:
        auth = next((i["weight"] for i in r.indicators if i["kind"] == "score"), 0)
        out.append({"id": r.id, "evidence_id": r.evidence_id, "code": codes.get(r.evidence_id, ("?", ""))[0],
                    "file": codes.get(r.evidence_id, ("", "?"))[1], "disputed_text": r.disputed_text, "claimed_sender": r.claimed_sender,
                    "message_time": r.message_time, "verdict": r.verdict, "verdict_label": VERDICTS.get(r.verdict, r.verdict),
                    "scores": {"fabrication": r.fabrication_score, "compromise": r.compromise_score, "authentic": auth},
                    "indicators": [i for i in r.indicators if i["kind"] != "score"], "tool_trace": r.tool_trace,
                    "recommendations": r.recommendations, "summary": r.summary, "mode": r.mode})
    return {"assessments": out, "verdicts": VERDICTS}


@router.get("/cases/{case_id}/confidence")
def case_confidence(case_id: str, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    from ..analysis import confidence
    get_case_or_403(db, user, case_id)
    return confidence.compute(db, case_id)


@router.get("/tools")
def tools(user: User = Depends(get_current_user)):
    return {"tools": REGISTRY.catalogue(),
            "note": "Read-only, case-scoped tools. Agents call them through one audited path; an LLM planner (when enabled for a "
                    "case) receives these exact schemas for native tool use."}


class ToolCall(BaseModel):
    input: dict = Field(default_factory=dict)


@router.post("/cases/{case_id}/tools/{name}")
def call_tool(case_id: str, name: str, body: ToolCall, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    get_case_or_403(db, user, case_id)
    if name not in REGISTRY.tools or REGISTRY.tools[name].category != "case":
        raise HTTPException(404, "unknown case tool")
    s = ToolSession(REGISTRY, CaseCtx.load(db, case_id), planner=f"user:{user.email}")
    t0 = time.perf_counter()
    out = s.call(name, body.input, "manual call from the tool console")
    audit.record(db, "tool.call", user=user, case_id=case_id, detail={"tool": name, "input": body.input,
                                                                                "status": s.trace[-1]["status"]})
    db.commit()
    return {"tool": name, "output": out, "trace": s.trace[-1], "ms": round((time.perf_counter() - t0) * 1000, 1)}
