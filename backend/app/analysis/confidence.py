"""Model confidence report: how far can this case's output be trusted?

The score (0-100) is a weighted average of components that are each measured, not guessed:

  integrity      share of files whose SHA-256 still matches the value recorded at intake
  extraction     share of files read successfully x how clearly OCR / speech-to-text read them (their own confidence)
  timestamps     share of timeline events whose time is written in the record itself (not estimated / unknown)
  traceability   share of findings that point back to an exact source location
  verification   share of the engine's claims that passed the Verification agent
  labels         average confidence of the Naive Bayes message labels (uncertain labels count as 0.5)
  benchmark      measured accuracy on the Scenario Lab ground truth (critical findings found + expected outcome matched)

A component with nothing to measure in this case is left out and the weights are renormalised, so the score is
never padded with assumptions. It describes the reliability of the model's output, never anyone's guilt.
"""
from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..models import (Contradiction, Evidence, EvidenceGap, ExtractedSegment, MessageClassification, ScenarioRun, TimelineEvent)
from . import naive_bayes as nb

WEIGHTS = {"integrity": 0.15, "extraction": 0.20, "timestamps": 0.10, "traceability": 0.15, "verification": 0.15,
           "labels": 0.10, "benchmark": 0.15}
NAMES = {"integrity": "File integrity (SHA-256)", "extraction": "Reading quality (OCR / speech / parsing)",
         "timestamps": "Timestamp reliability", "traceability": "Source traceability", "verification": "Claim verification",
         "labels": "Naive Bayes label confidence", "benchmark": "Measured accuracy (Scenario Lab)"}
LANG_ASR_NOTE = {"kn": "Kannada speech is transcribed less accurately than English by the base speech model.",
                 "hi": "Hindi speech is transcribed somewhat less accurately than English by the base speech model."}


def _band(score: float) -> str:
    return "High" if score >= 80 else "Moderate" if score >= 60 else "Low"


def benchmark(db: Session) -> dict | None:
    latest: dict[str, ScenarioRun] = {}
    for r in db.scalars(select(ScenarioRun).where(ScenarioRun.status == "completed").order_by(ScenarioRun.started_at)):
        if r.evaluation:
            latest[r.scenario_id] = r
    if not latest:
        return None
    matched, found, total = 0, 0, 0
    for r in latest.values():
        ev = r.evaluation or {}
        matched += bool(ev.get("outcome_matches_expected"))
        crit = str((ev.get("metrics") or {}).get("critical_findings", ""))
        if "/" in crit:
            a, b = crit.split("/")[:2]
            if a.strip().isdigit() and b.strip().isdigit():
                found, total = found + int(a), total + int(b)
    n = len(latest)
    outcome = matched / n
    crit_rate = found / total if total else outcome
    return {"scenarios": n, "outcome_match": round(outcome, 3), "critical_found": round(crit_rate, 3),
            "score": round(0.5 * outcome + 0.5 * crit_rate, 3)}


def compute(db: Session, case_id: str) -> dict:
    evs = list(db.scalars(select(Evidence).where(Evidence.case_id == case_id, Evidence.deleted_at.is_(None))))
    comps: dict[str, dict] = {}
    notes: list[str] = []
    if not evs:
        return {"score": None, "band": "No evidence", "components": [], "notes": ["Upload and process evidence first."]}

    ok = sum(1 for e in evs if e.last_verification == "match")
    checked = sum(1 for e in evs if e.last_verification)
    if checked:
        comps["integrity"] = {"value": ok / checked, "detail": f"{ok} of {checked} files match their intake SHA-256."}

    segs = list(db.scalars(select(ExtractedSegment).where(ExtractedSegment.case_id == case_id)))
    read_ok = sum(1 for e in evs if e.status == "processed")
    ml = [s.confidence for s in segs if s.kind in ("ocr_line", "transcript")]
    ml_conf = sum(ml) / len(ml) if ml else 1.0
    share = read_ok / len(evs)
    comps["extraction"] = {"value": share * (0.4 + 0.6 * ml_conf),
                           "detail": f"{read_ok} of {len(evs)} files read; " + (f"OCR / speech average confidence {ml_conf:.0%} over {len(ml)} lines."
                                                                                  if ml else "all text came from structured files (no OCR or speech).")}
    langs = defaultdict(int)
    for e in evs:
        lg = ((e.file_metadata or {}).get("extraction") or {}).get("language") or (e.file_metadata or {}).get("language")
        if e.detected_type in ("audio", "video") and lg:
            langs[lg] += 1
    for lg in langs:
        if lg in LANG_ASR_NOTE:
            notes.append(LANG_ASR_NOTE[lg])

    events = [x for x in db.scalars(select(TimelineEvent).where(TimelineEvent.case_id == case_id))
              if x.timestamp_kind != "system_recorded" and x.event_type not in ("file_created", "file_modified")]
    if events:
        src = sum(1 for x in events if x.timestamp_kind == "source_reported")
        part = sum(1 for x in events if x.timestamp_kind == "metadata_derived")
        comps["timestamps"] = {"value": (src + 0.6 * part) / len(events),
                               "detail": f"{src} of {len(events)} event times are written in the records; {part} come from file metadata."}
        linked = sum(1 for x in events if x.segment_id)
        cons = list(db.scalars(select(Contradiction).where(Contradiction.case_id == case_id)))
        gaps = list(db.scalars(select(EvidenceGap).where(EvidenceGap.case_id == case_id)))
        refs = [bool(x.segment_id) for x in events] + [bool(c.source_a.get("evidence_id") and c.source_b.get("evidence_id")) for c in cons] + \
               [bool(g.related) for g in gaps]
        comps["traceability"] = {"value": sum(refs) / len(refs),
                                 "detail": f"{sum(refs)} of {len(refs)} findings (events, contradictions, gaps) link to an exact source."}

    from ..queries import primary_hypothesis
    hyp = primary_hypothesis(db, case_id)
    if hyp and hyp.verification:
        v = hyp.verification
        tot = v.get("total") or 0
        if tot:
            comps["verification"] = {"value": 1 - (v.get("rejected", 0) / tot),
                                     "detail": f"{tot - v.get('rejected', 0)} of {tot} engine claims passed verification against the original files."}

    cls = list(db.scalars(select(MessageClassification).where(MessageClassification.case_id == case_id)))
    if cls:
        vals = [0.5 if c.uncertain else c.confidence for c in cls]
        unc = sum(1 for c in cls if c.uncertain)
        card = nb.model_card()
        comps["labels"] = {"value": (sum(vals) / len(vals)) * (0.5 + 0.5 * card["loo_accuracy"]),
                           "detail": f"{len(cls)} labels, {unc} uncertain; classifier's measured accuracy {card['loo_accuracy']:.0%}."}

    bm = benchmark(db)
    if bm:
        comps["benchmark"] = {"value": bm["score"], "detail": f"{bm['scenarios']} scenarios: outcome correct in {bm['outcome_match']:.0%}, "
                                                            f"critical findings found {bm['critical_found']:.0%}."}

    wsum = sum(WEIGHTS[k] for k in comps)
    score = 100 * sum(WEIGHTS[k] * c["value"] for k, c in comps.items()) / wsum
    out = [{"key": k, "name": NAMES[k], "score": round(100 * c["value"]), "weight": round(WEIGHTS[k] / wsum, 3), "detail": c["detail"]}
           for k, c in sorted(comps.items(), key=lambda kv: -WEIGHTS[kv[0]])]
    weakest = sorted(out, key=lambda c: c["score"])[:2]
    if hyp is None:
        notes.append("No challenge run yet: claim verification is not part of this score.")
    notes.append("The score measures how reliable the model's output is. It is not a finding about any person.")
    return {"score": round(score), "band": _band(score), "components": out,
            "weakest": [w["name"] for w in weakest if w["score"] < 80],
            "missing": [NAMES[k] for k in WEIGHTS if k not in comps], "notes": notes,
            "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")}
