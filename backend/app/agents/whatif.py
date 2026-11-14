"""What-If Lab: hypothetical analysis in an isolated sandbox.

A scenario copies the case's evidence records and extracted segments into a throwaway in-memory
database, applies the investigator's assumptions there, and re-runs the deterministic analysis and
the challenge agents. Nothing is written back to the case: results are stored only on the
WhatIfScenario row and are labelled HYPOTHETICAL everywhere.

Supported assumptions (cumulative along a branch):
  exclude_evidence   {evidence_id}                    "what if this item is unrelated/unreliable?"
  timestamp_override {segment_id, value|null}         "what if this timestamp is wrong / unknown?"
  unlink_identifier  {evidence_id, value}             "what if this record does not refer to that order/transaction?"
  different_sender   {evidence_id, sender}            "what if the email was forwarded and the original sender differs?"
  same_source        {evidence_a, evidence_b}         "what if these two records come from one source?"
  narrative          {note}                           recorded for discussion; no record changes, so nothing is recomputed
"""
from __future__ import annotations

import re
import time
import traceback

from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from .. import replay
from ..analysis import contradictions as contra
from ..analysis import dna, gaps as gapmod, nlp
from ..analysis.entities import build_entities
from ..analysis.index import CaseIndex
from ..analysis.timeline import build_timeline
from ..db import Base
from ..models import (Case, Contradiction, Evidence, EvidenceDependency, EvidenceGap, ExtractedSegment, WhatIfScenario, utcnow)
from ..queries import primary_hypothesis
from . import adversarial as adv

TYPES = {"exclude_evidence", "timestamp_override", "unlink_identifier", "different_sender", "same_source", "narrative"}


def _clone(obj, cls, **over):
    vals = {c.name: getattr(obj, c.key if hasattr(obj, c.key) else c.name) for c in cls.__table__.columns}
    vals.update(over)
    return cls(**vals)


def describe(a: dict, codes: dict) -> str:
    t = a["type"]
    if t == "exclude_evidence":
        return f"{codes.get(a['evidence_id'], '?')} is unrelated or unreliable and is set aside"
    if t == "timestamp_override":
        return f"the timestamp of segment {a.get('label') or a['segment_id'][:8]} is " + (f"actually {a['value']}" if a.get("value") else "unknown")
    if t == "unlink_identifier":
        return f"{codes.get(a['evidence_id'], '?')} does not refer to {a['value']}"
    if t == "different_sender":
        return f"the original sender of {codes.get(a['evidence_id'], '?')} was {a['sender']}"
    if t == "same_source":
        return f"{codes.get(a['evidence_a'], '?')} and {codes.get(a['evidence_b'], '?')} come from one source"
    return a.get("note", "")


def snapshot(db: Session, case_id: str, hyp_override: dict | None = None) -> dict:
    """Comparable summary of a case state (real or sandbox)."""
    h = hyp_override
    if h is None:
        ph = primary_hypothesis(db, case_id)
        h = None if not ph else {"pattern": ph.pattern, "statement": ph.statement, "decision": ph.decision, "verdict": ph.verdict,
                                 "independent_sources": (ph.assessment or {}).get("independent_sources"),
                                 "supporting": len(ph.supporting or []), "reason": (ph.assessment or {}).get("reason")}
    cons = list(db.scalars(select(Contradiction).where(Contradiction.case_id == case_id)))
    gaps = list(db.scalars(select(EvidenceGap).where(EvidenceGap.case_id == case_id)))
    return {"hypothesis": h, "contradictions": sorted(c.description for c in cons), "gaps": sorted(g.description for g in gaps)}


def run(db: Session, scenario_id: str):
    sc = db.get(WhatIfScenario, scenario_id)
    sc.status = "running"
    db.commit()
    t0 = time.perf_counter()
    eng = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    try:
        Base.metadata.create_all(eng)
        sb: Session = sessionmaker(bind=eng, expire_on_commit=False)()
        case = db.get(Case, sc.case_id)
        codes = {e.id: e.evidence_code for e in db.scalars(select(Evidence).where(Evidence.case_id == case.id))}
        A = sc.assumptions or []
        excluded = {a["evidence_id"] for a in A if a["type"] == "exclude_evidence"}
        sb.add(_clone(case, Case, allow_external_ai=False))  # the sandbox never contacts external AI
        sb.flush()
        for e in db.scalars(select(Evidence).where(Evidence.case_id == case.id, Evidence.deleted_at.is_(None))):
            if e.id not in excluded:
                sb.add(_clone(e, Evidence))
        sb.flush()
        segs = [s for s in db.scalars(select(ExtractedSegment).where(ExtractedSegment.case_id == case.id)) if s.evidence_id not in excluded]
        clones = {s.id: _clone(s, ExtractedSegment, data=dict(s.data or {})) for s in segs}
        applied, not_computable = [], []
        for a in A:
            t = a["type"]
            if t == "timestamp_override" and a.get("segment_id") in clones:
                s = clones[a["segment_id"]]
                new = a.get("value")
                s.timestamp_raw = new
                s.text = nlp.DATE_RE.sub(new or "[date unknown]", s.text)
                applied.append(a)
            elif t == "unlink_identifier":
                rx = re.compile(re.escape(a["value"]), re.I)
                for s in clones.values():
                    if s.evidence_id == a["evidence_id"] and rx.search(s.text):
                        s.text = rx.sub("[reference withheld]", s.text)
                        s.data = {**s.data, "fields": {k: ("[reference withheld]" if rx.search(str(v)) else v) for k, v in (s.data.get("fields") or {}).items()}}
                applied.append(a)
            elif t == "different_sender":
                for s in clones.values():
                    if s.evidence_id == a["evidence_id"] and s.kind == "email_header":
                        old = (s.data.get("from") or [{}])[0].get("address", "")
                        s.data = {**s.data, "from": [{"name": "", "address": a["sender"]}]}
                        s.text = s.text.replace(old, a["sender"]) if old else s.text
                        s.author = a["sender"]
                applied.append(a)
            elif t in ("exclude_evidence", "same_source"):
                applied.append(a)
            elif t == "narrative":
                not_computable.append(a)
        for s in clones.values():
            sb.add(s)
        sb.commit()

        idx = CaseIndex(sb, case.id)
        build_entities(sb, idx)
        build_timeline(sb, CaseIndex(sb, case.id))
        dna.analyse(sb, CaseIndex(sb, case.id))
        for a in A:
            if a["type"] == "same_source" and a["evidence_a"] in codes and a["evidence_b"] in codes:
                sb.add(EvidenceDependency(case_id=case.id, evidence_a_id=a["evidence_a"], evidence_b_id=a["evidence_b"], relation="shared_source",
                                          confidence=1.0, explanation="HYPOTHETICAL: assumed to come from one source"))
        sb.flush()
        contra.detect(sb, CaseIndex(sb, case.id))
        gapmod.detect(sb, CaseIndex(sb, case.id))
        sb.commit()
        ctx = adv.Ctx.load(sb, CaseIndex(sb, case.id))
        cands = adv.investigation_candidates(ctx)
        h = cands[0]
        c = adv.counter_agent(ctx, h)
        v = adv.verification_agent(ctx, h, c)
        rv = adv.reviewer_agent(ctx, h, c, v)
        from .predictor import predict
        recs = predict(sb, ctx, h, cands[1:], c, run_id="whatif")
        cv = v["claim_index"]
        hyp = {"pattern": h["pattern"], "statement": h["statement"], "decision": rv["decision"], "verdict": rv["verdict"],
               "independent_sources": rv["independent_sources"], "reason": rv["reason"],
               "supporting": len([cl for cl in h["claims"] if cl["kind"] == "observation" and cv[cl["id"]]["status"] != "rejected"])}
        after = snapshot(sb, case.id, hyp)
        before = snapshot(db, case.id)
        bh, ah = before["hypothesis"] or {}, after["hypothesis"] or {}
        supports = [{"text": cl["text"], "status": cv[cl["id"]]["status"], "sources": cv[cl["id"]]["sources"]}
                    for cl in h["claims"] if cl["kind"] == "observation"]
        challenges = [{"kind": k["kind"], "text": k["text"], "sources": v["counter_index"][k["id"]]["sources"]} for k in c["items"]]
        sc.result = {
            "label": "HYPOTHETICAL",
            "assumptions_described": [describe(a, codes) for a in A],
            "not_computable": [a.get("note", "") for a in not_computable],
            "before": before, "after": after,
            "changes": {
                "decision": {"from": bh.get("decision"), "to": ah.get("decision"), "changed": bh.get("decision") != ah.get("decision")},
                "pattern": {"from": bh.get("pattern"), "to": ah.get("pattern"), "changed": bh.get("pattern") != ah.get("pattern")},
                "contradictions_added": sorted(set(after["contradictions"]) - set(before["contradictions"])),
                "contradictions_removed": sorted(set(before["contradictions"]) - set(after["contradictions"])),
                "gaps_added": sorted(set(after["gaps"]) - set(before["gaps"])),
                "gaps_removed": sorted(set(before["gaps"]) - set(after["gaps"])),
                "independent_sources": {"from": bh.get("independent_sources"), "to": ah.get("independent_sources")},
            },
            "supporting_under_assumption": supports, "challenging_under_assumption": challenges,
            "would_resolve": recs[:3], "affected_hypotheses": [x["pattern"] for x in cands],
            "duration_ms": int((time.perf_counter() - t0) * 1000),
        }
        sc.status = "completed"
        db.commit()
        replay.emit(db, sc.case_id, "whatif.simulated", component="whatif_lab", actor="what-if sandbox",
                    outputs=[replay.ref("whatif", sc.id, sc.title)],
                    summary=f"HYPOTHETICAL '{sc.title}': decision {bh.get('decision')} → {ah.get('decision')}; "
                            f"{len(sc.result['changes']['contradictions_added'])} contradiction(s) added, "
                            f"{len(sc.result['changes']['contradictions_removed'])} removed. Case records unchanged.", commit=True)
        sb.close()
    except Exception as e:
        db.rollback()
        sc = db.get(WhatIfScenario, scenario_id)
        sc.status, sc.error = "failed", f"{type(e).__name__}: {e}\n{traceback.format_exc()[-800:]}"
        db.commit()
    finally:
        eng.dispose()


def validate(assumption: dict, evidence_ids: set[str], segment_case: dict[str, str], case_id: str) -> dict:
    t = assumption.get("type")
    if t not in TYPES:
        raise ValueError(f"Unknown assumption type '{t}'")
    need = {"exclude_evidence": ["evidence_id"], "timestamp_override": ["segment_id"], "unlink_identifier": ["evidence_id", "value"],
            "different_sender": ["evidence_id", "sender"], "same_source": ["evidence_a", "evidence_b"], "narrative": ["note"]}[t]
    for k in need:
        if not str(assumption.get(k) or "").strip():
            raise ValueError(f"Assumption '{t}' needs '{k}'")
    for k in ("evidence_id", "evidence_a", "evidence_b"):
        if k in assumption and assumption[k] not in evidence_ids:
            raise ValueError(f"{k} does not belong to this case")
    if t == "timestamp_override" and segment_case.get(assumption["segment_id"]) != case_id:
        raise ValueError("segment_id does not belong to this case")
    clean = {k: (str(v)[:300] if v is not None else None) for k, v in assumption.items()}
    return clean
