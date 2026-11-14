"""Flagship intelligence APIs: Evidence DNA, integrity inspection, Missing Evidence Predictor,
What-If Lab, Investigation Replay, manual claim verification and evaluation summary."""
from __future__ import annotations

from collections import defaultdict

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from .. import audit, replay
from ..agents import adversarial as adv
from ..agents import whatif
from ..analysis import dna
from ..analysis.index import CaseIndex
from ..db import get_db
from ..models import (Contradiction, Entity, EntityMention, Evidence, EvidenceDependency, EvidenceRecommendation, ExtractedSegment,
                      Hypothesis, IntegrityFinding, InvestigationEvent, ScenarioDefinition, ScenarioRun, TimelineEvent, User,
                      VerificationResult, WhatIfScenario)
from ..security import get_case_or_403, get_current_user, require
from ..services import jobs

router = APIRouter(prefix="/api", tags=["flagship intelligence"])


def _codes(db, case_id):
    return {e.id: (e.evidence_code, e.original_filename, e.detected_type) for e in db.scalars(select(Evidence).where(Evidence.case_id == case_id))}


def _dep_out(d: EvidenceDependency, codes) -> dict:
    return {"id": d.id, "a": {"id": d.evidence_a_id, "code": codes.get(d.evidence_a_id, ("?",))[0], "filename": codes.get(d.evidence_a_id, ("", "?"))[1]},
            "b": {"id": d.evidence_b_id, "code": codes.get(d.evidence_b_id, ("?",))[0], "filename": codes.get(d.evidence_b_id, ("", "?"))[1]},
            "relation": d.relation, "direction": d.direction, "matches": d.matches, "text_similarity": d.text_similarity,
            "confidence": d.confidence, "explanation": d.explanation,
            "independent": d.relation == "independent", "dependent": d.relation in dna.DEPENDENT}


# ------------------------------------------------------------------ Evidence DNA
@router.get("/cases/{case_id}/dna")
def evidence_dna(case_id: str, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    get_case_or_403(db, user, case_id)
    codes = _codes(db, case_id)
    deps = list(db.scalars(select(EvidenceDependency).where(EvidenceDependency.case_id == case_id)))
    idx = CaseIndex(db, case_id)
    cl = dna.clusters(deps, list(idx.evidence))
    groups = defaultdict(list)
    for eid, g in cl.items():
        groups[g].append({"id": eid, "code": codes[eid][0], "filename": codes[eid][1], "type": codes[eid][2]})
    by = defaultdict(int)
    for d in deps:
        by[d.relation] += 1
    return {"dependencies": [_dep_out(d, codes) for d in sorted(deps, key=lambda d: (d.relation not in dna.DEPENDENT, -d.confidence))],
            "shared_identifiers": dna.fingerprint(idx, deps),
            "source_groups": sorted([sorted(v, key=lambda x: x["code"]) for v in groups.values()], key=lambda g: (-len(g), g[0]["code"])),
            "summary": {"evidence": len(idx.evidence), "independent_source_groups": len(groups), "by_relation": dict(by)}}


@router.get("/cases/{case_id}/dependencies")
def dependencies(case_id: str, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    get_case_or_403(db, user, case_id)
    codes = _codes(db, case_id)
    return [_dep_out(d, codes) for d in db.scalars(select(EvidenceDependency).where(EvidenceDependency.case_id == case_id))]


# ------------------------------------------------------------------ Integrity inspection
@router.get("/cases/{case_id}/integrity-findings")
def integrity_findings(case_id: str, evidence_id: str | None = None, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    get_case_or_403(db, user, case_id)
    codes = _codes(db, case_id)
    stmt = select(IntegrityFinding).where(IntegrityFinding.case_id == case_id)
    if evidence_id:
        stmt = stmt.where(IntegrityFinding.evidence_id == evidence_id)
    order = {"high": 0, "medium": 1, "low": 2, "info": 3}
    rows = sorted(db.scalars(stmt), key=lambda f: (order.get(f.severity, 4), codes.get(f.evidence_id, ("",))[0]))
    return [{"id": f.id, "evidence_id": f.evidence_id, "evidence_code": codes.get(f.evidence_id, ("?",))[0],
             "filename": codes.get(f.evidence_id, ("", "?"))[1], "check": f.check, "severity": f.severity,
             "observation": f.observation, "detail": f.detail} for f in rows]


# ------------------------------------------------------------------ Missing Evidence Predictor
@router.get("/cases/{case_id}/recommendations")
def recommendations(case_id: str, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    get_case_or_403(db, user, case_id)
    rows = db.scalars(select(EvidenceRecommendation).where(EvidenceRecommendation.case_id == case_id).order_by(EvidenceRecommendation.rank))
    return [{"id": r.id, "rank": r.rank, "question": r.question, "recommended_evidence": r.recommended_evidence, "why_it_matters": r.why_it_matters,
             "distinguishes": r.distinguishes, "could_confirm": r.could_confirm, "could_disprove": r.could_disprove,
             "authorised_source": r.authorised_source, "limitations": r.limitations, "score": r.score, "score_breakdown": r.score_breakdown,
             "linked": r.linked, "status": r.status} for r in rows]


class RecStatus(BaseModel):
    status: str = Field(pattern="^(open|requested|collected|not_available)$")


@router.patch("/recommendations/{rec_id}")
def update_recommendation(rec_id: str, body: RecStatus, db: Session = Depends(get_db), user: User = Depends(require("review:decide"))):
    r = db.get(EvidenceRecommendation, rec_id)
    if not r:
        raise HTTPException(404, "Recommendation not found")
    get_case_or_403(db, user, r.case_id, write=True)
    r.status = body.status
    db.commit()
    audit.record(db, "recommendation.status", user=user, case_id=r.case_id, detail={"rank": r.rank, "status": body.status})
    replay.emit(db, r.case_id, "recommendation.updated", component="missing_evidence", actor=user,
                outputs=[replay.ref("recommendation", r.id, f"#{r.rank}")], summary=f"Recommendation #{r.rank} marked {body.status}", commit=True)
    return {"ok": True, "status": r.status}


# ------------------------------------------------------------------ Investigation Replay
@router.get("/cases/{case_id}/replay")
def investigation_replay(case_id: str, component: str | None = None, status: str | None = None, run_id: str | None = None,
                         limit: int = Query(300, ge=1, le=2000), offset: int = Query(0, ge=0),
                         db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    get_case_or_403(db, user, case_id)
    stmt = select(InvestigationEvent).where(InvestigationEvent.case_id == case_id)
    if component:
        stmt = stmt.where(InvestigationEvent.component == component)
    if status:
        stmt = stmt.where(InvestigationEvent.status == status)
    if run_id:
        stmt = stmt.where(InvestigationEvent.run_id == run_id)
    total = db.scalar(select(func.count()).select_from(stmt.subquery()))
    comps = dict(db.execute(select(InvestigationEvent.component, func.count()).where(InvestigationEvent.case_id == case_id)
                            .group_by(InvestigationEvent.component)).all())
    rows = list(db.scalars(stmt.order_by(InvestigationEvent.id).offset(offset).limit(limit)))
    seg_ids = {r["id"] for e in rows for r in (e.inputs or []) + (e.outputs or []) if r.get("type") == "segment" and r.get("id")}
    segs = {s.id: s for s in db.scalars(select(ExtractedSegment).where(ExtractedSegment.id.in_(seg_ids)))} if seg_ids else {}
    codes = _codes(db, case_id)

    def enrich(refs):
        out = []
        for r in refs or []:
            if r.get("type") == "segment" and r.get("id") in segs:
                s = segs[r["id"]]
                r = {**r, "evidence_id": s.evidence_id, "label": r.get("label") or f"{codes.get(s.evidence_id, ('?',))[0]} {s.locator}"}
            out.append(r)
        return out
    return {"total": total, "offset": offset, "components": comps, "items": [
        {"id": e.id, "ts": e.ts, "action": e.action, "actor": e.actor, "component": e.component, "status": e.status,
         "inputs": enrich(e.inputs), "outputs": enrich(e.outputs), "summary": e.summary, "details": e.details, "run_id": e.run_id} for e in rows]}


# ------------------------------------------------------------------ Manual claim verification
class ClaimCheckIn(BaseModel):
    text: str = Field(min_length=3, max_length=2000)
    citations: list[str] = Field(min_length=1, max_length=10)
    expect: list[str] = Field(default=[], max_length=10)
    temporal: bool = False


@router.post("/cases/{case_id}/verify-claim")
def verify_claim(case_id: str, body: ClaimCheckIn, db: Session = Depends(get_db), user: User = Depends(require("review:decide"))):
    """Run the Verification agent's deterministic checks on a claim an investigator (or an AI draft) wants to cite."""
    get_case_or_403(db, user, case_id)
    ctx = adv.Ctx.load(db, CaseIndex(db, case_id))
    item = {"id": "M1", "text": body.text, "kind": "observation", "citations": body.citations, "expect": body.expect, "temporal": body.temporal}
    res = adv.verify_items(ctx, [item])[0]
    db.add(VerificationResult(case_id=case_id, item_id="M1", item_text=body.text, source="manual", status=res["status"],
                              checks=res["checks"], citations=body.citations, created_by=user.id))
    replay.emit(db, case_id, "verification.manual_check", component="verification", actor=user, status="warning" if res["status"] == "rejected" else "ok",
                inputs=[replay.ref("segment", c, "") for c in body.citations], summary=f"Claim '{body.text[:120]}' → {res['status']}: {'; '.join(res['checks'])}")
    db.commit()
    return res


@router.get("/cases/{case_id}/verification-results")
def verification_results(case_id: str, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    get_case_or_403(db, user, case_id)
    rows = db.scalars(select(VerificationResult).where(VerificationResult.case_id == case_id).order_by(VerificationResult.created_at.desc()).limit(500))
    return [{"id": v.id, "hypothesis_id": v.hypothesis_id, "item_id": v.item_id, "text": v.item_text, "source": v.source, "status": v.status,
             "checks": v.checks, "citations": v.citations, "created_at": v.created_at} for v in rows]


@router.get("/cases/{case_id}/challenge-runs")
def challenge_runs(case_id: str, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    get_case_or_403(db, user, case_id)
    rows = list(db.scalars(select(Hypothesis).where(Hypothesis.case_id == case_id).order_by(Hypothesis.created_at.desc(), Hypothesis.rank)))
    runs = defaultdict(list)
    for h in rows:
        runs[h.run_id].append({"id": h.id, "rank": h.rank, "pattern": h.pattern, "decision": h.decision, "verdict": h.verdict,
                               "statement": h.statement, "created_at": h.created_at})
    return [{"run_id": k, "candidates": v} for k, v in runs.items()]


# ------------------------------------------------------------------ Evidence relations (detail page)
@router.get("/evidence/{evidence_id}/related")
def evidence_related(evidence_id: str, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    e = db.get(Evidence, evidence_id)
    if not e:
        raise HTTPException(404, "Evidence not found")
    get_case_or_403(db, user, e.case_id)
    codes = _codes(db, e.case_id)
    ent_ids = {m.entity_id for m in db.scalars(select(EntityMention).where(EntityMention.evidence_id == e.id))}
    ents = list(db.scalars(select(Entity).where(Entity.id.in_(ent_ids)))) if ent_ids else []
    evs = list(db.scalars(select(TimelineEvent).where(TimelineEvent.evidence_id == e.id)))
    deps = list(db.scalars(select(EvidenceDependency).where((EvidenceDependency.evidence_a_id == e.id) | (EvidenceDependency.evidence_b_id == e.id))))
    findings = list(db.scalars(select(IntegrityFinding).where(IntegrityFinding.evidence_id == e.id)))
    cons = [c for c in db.scalars(select(Contradiction).where(Contradiction.case_id == e.case_id))
            if e.id in (c.source_a.get("evidence_id"), c.source_b.get("evidence_id"))]
    from ..analysis import nlp
    return {
        "entities": [{"id": x.id, "type": x.type, "value": x.value} for x in sorted(ents, key=lambda x: x.type)],
        "events": [{"id": t.id, "display_time": nlp.display_dt(t.occurred_at, t.data) if t.occurred_at else None, "kind": t.timestamp_kind,
                    "type": t.event_type, "title": t.title, "segment_id": t.segment_id} for t in sorted(evs, key=lambda t: (t.occurred_at is None, str(t.occurred_at)))],
        "related_evidence": [_dep_out(d, codes) for d in deps],
        "integrity_findings": [{"check": f.check, "severity": f.severity, "observation": f.observation} for f in findings],
        "contradictions": [{"id": c.id, "code": c.code, "description": c.description, "classification": c.classification} for c in cons],
    }


# ------------------------------------------------------------------ What-If Lab
class WhatIfIn(BaseModel):
    title: str = Field(min_length=3, max_length=200)
    parent_id: str | None = None
    assumption: dict


def _wi_out(w: WhatIfScenario, full=False) -> dict:
    o = {"id": w.id, "parent_id": w.parent_id, "title": w.title, "assumptions": w.assumptions, "status": w.status, "error": w.error,
         "discarded": w.discarded, "created_at": w.created_at, "label": "HYPOTHETICAL",
         "decision_change": (w.result or {}).get("changes", {}).get("decision")}
    if full:
        o["result"] = w.result
    return o


@router.get("/cases/{case_id}/whatif")
def list_whatif(case_id: str, include_discarded: bool = False, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    get_case_or_403(db, user, case_id)
    stmt = select(WhatIfScenario).where(WhatIfScenario.case_id == case_id).order_by(WhatIfScenario.created_at)
    if not include_discarded:
        stmt = stmt.where(WhatIfScenario.discarded.is_(False))
    return [_wi_out(w) for w in db.scalars(stmt)]


@router.post("/cases/{case_id}/whatif", status_code=202)
def create_whatif(case_id: str, body: WhatIfIn, db: Session = Depends(get_db), user: User = Depends(require("analysis:run"))):
    get_case_or_403(db, user, case_id)
    ev_ids = set(db.scalars(select(Evidence.id).where(Evidence.case_id == case_id)))
    seg_case = {}
    if body.assumption.get("segment_id"):
        seg = db.get(ExtractedSegment, body.assumption["segment_id"])
        seg_case = {seg.id: seg.case_id} if seg else {}
    try:
        a = whatif.validate(body.assumption, ev_ids, seg_case, case_id)
    except ValueError as e:
        raise HTTPException(422, str(e))
    chain = []
    if body.parent_id:
        parent = db.get(WhatIfScenario, body.parent_id)
        if not parent or parent.case_id != case_id:
            raise HTTPException(404, "Parent scenario not found")
        chain = list(parent.assumptions or [])
    w = WhatIfScenario(case_id=case_id, parent_id=body.parent_id, title=body.title, assumptions=chain + [a], created_by=user.id)
    db.add(w)
    db.commit()
    audit.record(db, "whatif.created", user=user, case_id=case_id, detail={"id": w.id, "assumption": a})
    jobs.submit(whatif.run, w.id)
    return _wi_out(w)


@router.get("/whatif/{wid}")
def get_whatif(wid: str, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    w = db.get(WhatIfScenario, wid)
    if not w:
        raise HTTPException(404, "Scenario not found")
    get_case_or_403(db, user, w.case_id)
    return _wi_out(w, full=True)


@router.post("/whatif/{wid}/discard")
def discard_whatif(wid: str, db: Session = Depends(get_db), user: User = Depends(require("analysis:run"))):
    w = db.get(WhatIfScenario, wid)
    if not w:
        raise HTTPException(404, "Scenario not found")
    get_case_or_403(db, user, w.case_id)
    w.discarded = True
    db.commit()
    audit.record(db, "whatif.discarded", user=user, case_id=w.case_id, detail={"id": w.id})
    return {"ok": True}


@router.get("/cases/{case_id}/whatif-compare")
def compare_whatif(case_id: str, ids: str, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    get_case_or_403(db, user, case_id)
    rows = [db.get(WhatIfScenario, i) for i in ids.split(",")[:6]]
    rows = [w for w in rows if w and w.case_id == case_id and w.status == "completed"]
    return {"label": "HYPOTHETICAL", "scenarios": [{"id": w.id, "title": w.title, "assumptions": w.result.get("assumptions_described"),
                                                     "decision": (w.result.get("after") or {}).get("hypothesis", {}).get("decision"),
                                                     "pattern": (w.result.get("after") or {}).get("hypothesis", {}).get("pattern"),
                                                     "contradictions": len(w.result.get("after", {}).get("contradictions", [])),
                                                     "gaps": len(w.result.get("after", {}).get("gaps", [])),
                                                     "independent_sources": w.result.get("changes", {}).get("independent_sources", {}).get("to")} for w in rows]}


# ------------------------------------------------------------------ Evaluation summary
METRIC_DEFS = {
    "critical_findings": "Critical ground-truth findings matched by engine output / critical findings in ground truth.",
    "all_findings": "All ground-truth findings matched / all findings in ground truth.",
    "contradiction_precision": "Expected contradictions detected / (expected detected + unexpected contradictions outside allowed categories).",
    "contradiction_recall": "Expected contradictions detected / expected contradictions.",
    "entity_precision": "Extracted entities of scored types that are in the ground truth / extracted entities of those types.",
    "entity_recall": "Ground-truth entity values extracted / ground-truth entity values.",
    "entity_f1": "Harmonic mean of entity precision and recall.",
    "dependency_precision": "Expected evidence dependencies detected with the right relation / dependent relations reported.",
    "dependency_recall": "Expected evidence dependencies detected with the right relation / expected dependencies.",
    "timestamp_accuracy": "Expected events found in the right file at the right local time (±2 min) / expected events.",
    "timeline_order_accuracy": "Consecutive ground-truth event pairs placed in the right order / pairs.",
    "ocr_char_similarity": "Mean best character-sequence similarity between reference lines and OCR output.",
    "asr_similarity": "Sequence similarity between reference transcript and ASR output.",
    "hash_verification_accuracy": "Correct results over re-hash of every original plus a 1-bit tamper simulation per file.",
    "source_reference_coverage": "Findings/events whose source references resolve to stored segments / findings and events.",
    "unsupported_claim_rate": "Claims and challenges rejected by the Verification agent / items checked.",
    "processing_time": "Wall-clock time for the whole scenario run.",
}


@router.get("/evaluation/summary")
def evaluation_summary(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    out = []
    for sd in db.scalars(select(ScenarioDefinition).where(ScenarioDefinition.id != "custom-dataset").order_by(ScenarioDefinition.number)):
        r = db.scalar(select(ScenarioRun).where(ScenarioRun.scenario_id == sd.id, ScenarioRun.status == "completed")
                      .order_by(ScenarioRun.finished_at.desc()).limit(1))
        ev = (r.evaluation or {}) if r else {}
        metrics = {k: (ev.get("metrics", {}).get(k) or {"value": None, "display": "NOT EVALUATED", "basis": "no completed run"}) for k in METRIC_DEFS}
        for k, m in metrics.items():
            if m.get("value") is None:
                metrics[k] = {**m, "display": "NOT EVALUATED"}
        human = None
        if r and r.case_id:
            cons = list(db.scalars(select(Contradiction).where(Contradiction.case_id == r.case_id)))
            reviewed = [c for c in cons if c.review_status in ("confirmed", "dismissed")]
            fps = {f["code"] for f in ev.get("false_positives", [])}
            agree = sum(1 for c in reviewed if (c.review_status == "confirmed") == (c.code not in fps))
            human = {"reviewed": len(reviewed), "agree_with_ground_truth": agree} if reviewed else None
        conf = None
        if r and r.case_id:
            cons = list(db.scalars(select(Contradiction).where(Contradiction.case_id == r.case_id)))
            fps = {f["code"] for f in ev.get("false_positives", [])}
            tp = [c.confidence for c in cons if c.code not in fps]
            fp = [c.confidence for c in cons if c.code in fps]
            conf = {"mean_confidence_correct": round(sum(tp) / len(tp), 2) if tp else None,
                    "mean_confidence_false_positive": round(sum(fp) / len(fp), 2) if fp else None}
        out.append({"scenario_id": sd.id, "title": sd.title, "expected_outcome": (sd.ground_truth or {}).get("expected_outcome"),
                    "run_id": r.id if r else None, "test_code": r.test_code if r else None, "outcome": r.outcome if r else "NOT EVALUATED",
                    "finished_at": r.finished_at if r else None, "metrics": metrics, "model_confidence": conf, "human_review": human,
                    "decision": (ev.get("actual") or {}).get("decision")})
    return {"definitions": METRIC_DEFS, "scenarios": out}
