"""Alternative Hypothesis Testing Engine API."""
from __future__ import annotations

import html
import re

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from .. import audit
from ..agents import hypothesis_engine as eng
from ..db import get_db
from ..models import Evidence, HypothesisAnalysis, HypothesisFeedback, User
from ..security import get_case_or_403, get_current_user, require

router = APIRouter(prefix="/api", tags=["hypothesis lab"])


def _out(a: HypothesisAnalysis | None) -> dict | None:
    if not a:
        return None
    return {"id": a.id, "version": a.version, "trigger": a.trigger, "created_at": a.created_at, "question": a.question,
            "hypotheses": a.hypotheses, "matrix": a.matrix, "counter": a.counter, "comparison": a.comparison,
            "next_evidence": a.next_evidence, "review": a.review, "changes": a.changes, "baseline": a.baseline,
            "approval": {"status": a.approval_status, "note": a.approval_note}, "labels": eng.LABEL_TEXT, "run_id": a.run_id}


def _latest(db, case_id):
    return db.scalars(select(HypothesisAnalysis).where(HypothesisAnalysis.case_id == case_id).order_by(HypothesisAnalysis.version.desc())).first()


@router.get("/cases/{case_id}/hypothesis-lab")
def get_latest(case_id: str, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    get_case_or_403(db, user, case_id)
    versions = [{"version": v.version, "created_at": v.created_at, "trigger": v.trigger, "leading": (v.comparison or [{}])[0].get("id"),
                 "approval": v.approval_status, "evidence": len(v.evidence_ids or [])}
                for v in db.scalars(select(HypothesisAnalysis).where(HypothesisAnalysis.case_id == case_id).order_by(HypothesisAnalysis.version))]
    revised = next((v for v in db.scalars(select(HypothesisAnalysis).where(HypothesisAnalysis.case_id == case_id)
                                         .order_by(HypothesisAnalysis.version.desc()))
                    if (v.changes or {}).get("changed") or (v.changes or {}).get("leading_changed")), None)
    last_revision = {"version": revised.version, **revised.changes} if revised else None
    return {"analysis": _out(_latest(db, case_id)), "versions": versions, "last_revision": last_revision}


@router.get("/cases/{case_id}/hypothesis-lab/versions/{version}")
def get_version(case_id: str, version: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    get_case_or_403(db, user, case_id)
    a = db.scalars(select(HypothesisAnalysis).where(HypothesisAnalysis.case_id == case_id, HypothesisAnalysis.version == version)).first()
    if not a:
        raise HTTPException(404, "No such version")
    return _out(a)


def _bg_run(db, case_id, user_id):
    eng.run(db, case_id, db.get(User, user_id), trigger="investigator re-evaluation")


@router.post("/cases/{case_id}/hypothesis-lab/run")
def run(case_id: str, background: bool = False, db: Session = Depends(get_db), user: User = Depends(require("analysis:run"))):
    get_case_or_403(db, user, case_id, write=True)
    if not db.scalar(select(Evidence.id).where(Evidence.case_id == case_id, Evidence.deleted_at.is_(None)).limit(1)):
        raise HTTPException(422, "Upload and process evidence first")
    if background:  # the UI watches it on the live processing page
        from ..services import jobs
        jobs.submit(_bg_run, case_id, user.id)
        return {"status": "queued"}
    return _out(eng.run(db, case_id, user, trigger="investigator re-evaluation"))


class HypIn(BaseModel):
    title: str = Field(min_length=3, max_length=120)
    description: str = Field("", max_length=600)
    keywords: list[str] = Field(default_factory=list, max_length=10)
    assumptions: list[str] = Field(default_factory=list, max_length=5)


class NoteIn(BaseModel):
    note: str = Field("", max_length=1000)


class EditIn(BaseModel):
    title: str | None = Field(None, max_length=120)
    description: str | None = Field(None, max_length=600)


def _fb(db, case_id, user, hid, action, payload):
    db.add(HypothesisFeedback(case_id=case_id, user_id=user.id, hypothesis_id=hid, action=action, payload=payload))
    db.commit()
    audit.record(db, f"hypothesis.{action}", user=user, case_id=case_id, detail={"hypothesis": hid, **payload})
    return _out(eng.run(db, case_id, user, trigger=f"investigator {action} {hid}"))


@router.post("/cases/{case_id}/hypothesis-lab/custom")
def add(case_id: str, body: HypIn, db: Session = Depends(get_db), user: User = Depends(require("review:decide"))):
    get_case_or_403(db, user, case_id, write=True)
    n = len(list(db.scalars(select(HypothesisFeedback).where(HypothesisFeedback.case_id == case_id, HypothesisFeedback.action == "add"))))
    kw = [k.strip()[:40] for k in body.keywords if k.strip()] or [w for w in re.findall(r"[a-z]{5,}", body.title.lower())][:4]
    return _fb(db, case_id, user, f"X{n + 1}", "add", {"title": body.title, "description": body.description, "keywords": kw,
                                                        "assumptions": body.assumptions})


@router.post("/cases/{case_id}/hypothesis-lab/{hid}/{action}")
def act(case_id: str, hid: str, action: str, body: NoteIn, db: Session = Depends(get_db), user: User = Depends(require("review:decide"))):
    get_case_or_403(db, user, case_id, write=True)
    if action not in ("reject", "restore", "challenge"):
        raise HTTPException(404, "Unknown action")
    if action == "challenge" and len(body.note.strip()) < 5:
        raise HTTPException(422, "Explain the challenge")
    return _fb(db, case_id, user, hid[:16], action, {"note": body.note})


@router.patch("/cases/{case_id}/hypothesis-lab/{hid}")
def edit(case_id: str, hid: str, body: EditIn, db: Session = Depends(get_db), user: User = Depends(require("review:decide"))):
    get_case_or_403(db, user, case_id, write=True)
    return _fb(db, case_id, user, hid[:16], "edit", {k: v for k, v in body.model_dump().items() if v})


class ApproveIn(BaseModel):
    decision: str = Field(pattern="^(approved|rejected)$")
    note: str = Field("", max_length=1000)


@router.post("/cases/{case_id}/hypothesis-lab/approve")
def approve(case_id: str, body: ApproveIn, db: Session = Depends(get_db), user: User = Depends(require("review:decide"))):
    get_case_or_403(db, user, case_id, write=True)
    a = _latest(db, case_id)
    if not a:
        raise HTTPException(404, "Nothing to approve")
    a.approval_status, a.approval_note, a.approved_by = body.decision, body.note, user.id
    db.commit()
    audit.record(db, "hypotheses.reviewed", user=user, case_id=case_id, detail={"version": a.version, "decision": body.decision, "note": body.note})
    return _out(a)


@router.get("/cases/{case_id}/hypothesis-lab/report", response_class=HTMLResponse)
def report(case_id: str, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    case = get_case_or_403(db, user, case_id)
    a = _latest(db, case_id)
    if not a:
        raise HTTPException(404, "Run the hypothesis engine first")
    e = html.escape
    hyps = {h["id"]: h for h in a.hypotheses}
    rows = "".join(f"<tr><td>{e(c['id'])}</td><td>{e(c['title'])}</td><td><b>{e(c['label_text'])}</b></td><td>{e('; '.join(c['basis']))}</td></tr>"
                   for c in a.comparison)
    mat_head = "".join(f"<th>{e(h)}</th>" for h in hyps)
    mat = "".join("<tr><td>" + e(r["code"] + " " + r["file"]) + "</td>" + "".join(
        f"<td>{e(r['cells'][h]['state'].replace('_', ' '))}<br><small>{e('; '.join((x['code'] or '') + ' ' + (x['locator'] or '') for x in r['cells'][h]['refs'][:2]))}</small></td>"
        for h in hyps) + "</tr>" for r in a.matrix)
    nxt = "".join(f"<li><b>{e(n['evidence'])}</b> ({e(n['source'])}): {e(n['how'])}</li>" for n in a.next_evidence)
    issues = "".join(f"<li>[{e(i['severity'])}] {e(i['text'])}</li>" for i in a.review.get("issues", [])) or "<li>None</li>"
    changes = "".join(f"<li>{e(c['id'])}: {e(c['from'])} → {e(c['to'])}. {e(c['because'])}</li>" for c in a.changes.get("changed", [])) or "<li>No label changes</li>"
    body = f"""<!doctype html><html><head><meta charset="utf-8"><title>Hypothesis report {e(case.case_number)} v{a.version}</title>
<style>body{{font-family:Segoe UI,Arial,sans-serif;margin:32px;color:#111}}table{{border-collapse:collapse;width:100%;margin:8px 0 20px}}
td,th{{border:1px solid #999;padding:6px;font-size:12px;vertical-align:top;text-align:left}}h1{{font-size:22px}}h2{{font-size:16px;margin-top:24px}}
.note{{background:#f3efe4;padding:8px;border-left:4px solid #111}}</style></head><body>
<h1>Alternative hypothesis assessment — {e(case.case_number)} · {e(case.title)}</h1>
<p>Version {a.version} · {a.created_at:%Y-%m-%d %H:%M UTC} · trigger: {e(a.trigger)} · human approval: <b>{e(a.approval_status)}</b>{(' — ' + e(a.approval_note)) if a.approval_note else ''}</p>
<p class="note">Labels describe the state of the available evidence. They are not findings of guilt, liability or the truth of any allegation.</p>
<h2>Question</h2><p>{e(a.question.get('question', ''))}</p>
<h2>Hypothesis comparison</h2><table><tr><th>ID</th><th>Hypothesis</th><th>Assessment</th><th>Basis</th></tr>{rows}</table>
<h2>Evidence matrix</h2><table><tr><th>Evidence</th>{mat_head}</tr>{mat}</table>
<h2>What changed since the previous version</h2><ul>{changes}</ul>
<h2>Recommended verification steps</h2><ol>{nxt or '<li>None</li>'}</ol>
<h2>Independent review</h2><p>{e(a.review.get('statement', ''))}</p><ul>{issues}</ul>
<h2>Limitations</h2><ul><li>Assessments use only evidence in this case and deterministic rules; extraction errors propagate.</li>
<li>Copies of the same source are counted once (Evidence DNA).</li><li>No probabilities are given because no calibrated model exists for them.</li></ul>
</body></html>"""
    audit.record(db, "hypotheses.exported", user=user, case_id=case_id, detail={"version": a.version})
    return HTMLResponse(body, headers={"Content-Disposition": f'inline; filename="hypotheses-{case.case_number}-v{a.version}.html"'})
