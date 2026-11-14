"""Deterministic ground-truth evaluation for Scenario Lab runs.

PASS  - all critical expected findings were produced, no forbidden finding/claim appeared,
        processing completed, and the reviewer reached a conclusion it could support.
HOLD  - nothing critical was missed or violated, but the reviewer judged the evidence
        insufficient or contested and requested further verification.
FAIL  - a critical expected finding was missed, a forbidden finding/unsupported claim
        appeared, or a required processing step failed.

Metrics are measured from this run only; nothing is estimated or invented.
"""
from __future__ import annotations

import difflib
import json
import re

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..analysis import nlp
from ..models import (AnalysisRun, Contradiction, Entity, Evidence, EvidenceGap, ExtractedSegment, Hypothesis, Relationship,
                      TimelineEvent)
from ..services.intake import sha256_bytes
from ..storage import get_storage


def _pct(x):
    return None if x is None else round(100 * x, 1)


def _m(value, display, basis):
    return {"value": value, "display": display, "basis": basis}


def evaluate(db: Session, case_id: str, gt: dict, runs: list[AnalysisRun], duration_ms: int) -> dict:
    evs = {e.id: e for e in db.scalars(select(Evidence).where(Evidence.case_id == case_id))}
    by_name = {e.original_filename: e for e in evs.values()}
    cons = list(db.scalars(select(Contradiction).where(Contradiction.case_id == case_id)))
    gaps = list(db.scalars(select(EvidenceGap).where(EvidenceGap.case_id == case_id)))
    ents = list(db.scalars(select(Entity).where(Entity.case_id == case_id)))
    ent_by = {e.id: e for e in ents}
    rels = list(db.scalars(select(Relationship).where(Relationship.case_id == case_id)))
    events = [e for e in db.scalars(select(TimelineEvent).where(TimelineEvent.case_id == case_id))
              if e.timestamp_kind not in ("system_recorded",) and e.event_type not in ("file_created", "file_modified")]
    segs = list(db.scalars(select(ExtractedSegment).where(ExtractedSegment.case_id == case_id)))
    seg_ids = {s.id for s in segs}
    from ..queries import primary_hypothesis
    hyp = primary_hypothesis(db, case_id)

    def con_text(c):
        return json.dumps([c.description, c.key, c.reason, c.source_a, c.source_b], default=str)

    def gap_text(g):
        return json.dumps([g.description, g.key, g.related], default=str)

    def related_file(g, fname):
        e = by_name.get(fname)
        return bool(e) and (g.key.startswith(e.id) or any(r.get("evidence_id") == e.id for r in g.related))

    counter_items = (hyp.counterevidence + hyp.alternatives + hyp.missing_information) if hyp else []
    from ..models import EvidenceDependency
    from ..analysis.dna import DEPENDENT
    deps = list(db.scalars(select(EvidenceDependency).where(EvidenceDependency.case_id == case_id)))
    matched_dep_ids: set = set()
    findings_out, matched_con_ids = [], set()
    for f in gt["findings"]:
        m, status, by = f["match"], "missed", None
        t = f["type"]
        if t == "entity":
            hit = next((e for e in ents if e.type == m["type"] and (e.normalized.lower() == m["value"].lower() or m["value"].lower() in e.normalized.lower())), None)
            if hit:
                status, by = "found", f"entity {hit.type}: {hit.value}"
        elif t == "suspicious_url":
            for e in ents:
                if e.type == "website" and e.normalized == m["domain"] and nlp.url_risk(e.normalized, nlp.KNOWN_BRAND_DOMAINS)["suspicious"]:
                    status, by = "found", f"website {e.value}: {'; '.join(nlp.url_risk(e.normalized, nlp.KNOWN_BRAND_DOMAINS)['indicators'])}"
        elif t == "contradiction":
            for c in cons:
                if c.category != m["category"]:
                    continue
                txt = con_text(c)
                ok = True
                if "values" in m:
                    vals = {str(c.source_a.get("value", "")).upper(), str(c.source_b.get("value", "")).upper()}
                    ok = all(any(v.upper() in x for x in vals) for v in m["values"])
                if "contains" in m:
                    ok = ok and m["contains"].lower() in txt.lower()
                if "field" in m:
                    ok = ok and c.field == m["field"]
                if ok:
                    status, by = "found", f"{c.code}: {c.description}"
                    matched_con_ids.add(c.id)
        elif t == "gap":
            for g in gaps:
                if g.category != m["category"]:
                    continue
                ok = ("file" not in m or related_file(g, m["file"])) and ("contains" not in m or m["contains"].lower() in gap_text(g).lower())
                if ok:
                    status, by = "found", f"{g.code}: {g.description[:120]}"
                    break
        elif t == "relationship":
            for r in rels:
                a, b = ent_by.get(r.source_entity_id), ent_by.get(r.target_entity_id)
                if a and b and {m["a"].lower(), m["b"].lower()} <= {a.normalized.lower(), b.normalized.lower()} and r.basis == "observed":
                    status, by = "found", f"{a.value} —{r.rel_type}— {b.value}"
        elif t == "hypothesis":
            if hyp and hyp.pattern == m["pattern"]:
                status, by = "found", hyp.statement[:140]
        elif t == "verdict":
            if hyp and (hyp.verdict in m.get("verdicts", []) or hyp.decision in m.get("decisions", [])):
                status, by = "found", f"decision {hyp.decision} (verdict {hyp.verdict})"
        elif t == "counter":
            hit = next((k for k in counter_items if m["contains"].lower() in str(k.get("text", "")).lower()), None)
            if hit:
                status, by = "found", hit["text"][:140]
        elif t == "extraction":
            e = by_name.get(m["file"])
            text = " ".join(s.text for s in segs if e and s.evidence_id == e.id).lower()
            if e and all(w.lower() in text for w in m["contains"]):
                status, by = "found", f"{e.original_filename} via {(e.file_metadata or {}).get('extraction', {}).get('method')}"
            elif e and (e.file_metadata or {}).get("extraction", {}).get("unavailable_engine"):
                status, by = "blocked", "engine unavailable"
        elif t == "dependency":
            ea, eb = by_name.get(m["files"][0]), by_name.get(m["files"][1])
            hit = ea and eb and next((d for d in deps if {d.evidence_a_id, d.evidence_b_id} == {ea.id, eb.id} and d.relation in m["relations"]), None)
            if hit:
                status, by = "found", f"{hit.relation}: {hit.explanation[:110]}"
                matched_dep_ids.add(hit.id)
        elif t == "integrity":
            ok = all(e.sha256 and e.last_verification == "match" for e in evs.values())
            if ok:
                status, by = "found", f"{len(evs)}/{len(evs)} items hashed (SHA-256) and re-verified"
        findings_out.append({**{k: f[k] for k in ("id", "description", "critical", "type")}, "status": status, "matched_by": by})

    # ---------------------------------------------------------------- forbidden checks
    violations = []
    all_text = " ".join([hyp.statement if hyp else ""] + [json.dumps(hyp.assessment) if hyp else ""] +
                        [str(k.get("text", "")) for k in counter_items] + [c.description for c in cons] + [g.description for g in gaps])
    for fb in gt.get("forbidden", []):
        if fb["type"] == "gap":
            e = by_name.get(fb["file"])
            if any(g.category == fb["category"] and e and related_file(g, fb["file"]) for g in gaps):
                violations.append(fb["description"])
        elif fb["type"] == "suspicious_url":
            if nlp.url_risk(fb["domain"], nlp.KNOWN_BRAND_DOMAINS)["suspicious"]:
                violations.append(fb["description"])
        elif fb["type"] == "contradiction_value":
            if any(fb["value"].lower() in con_text(c).lower() for c in cons):
                violations.append(fb["description"])
        elif fb["type"] == "text":
            if re.search(fb["pattern"], all_text, re.I):
                violations.append(fb["description"])

    # Irrelevant (control) records must not be used as support or linked into conflicts.
    for fname in gt.get("irrelevant_records", []):
        e = by_name.get(fname)
        if not e:
            continue
        cited = hyp and any(src and src.get("evidence_id") == e.id for cl in hyp.supporting
                            for src in (cl.get("verification") or {}).get("sources", []))
        if cited:
            violations.append(f"Irrelevant record {fname} was cited as supporting evidence")
        if any(e.id in (c.source_a.get("evidence_id"), c.source_b.get("evidence_id")) for c in cons):
            violations.append(f"Irrelevant record {fname} was linked into a contradiction")
    max_unsup = (gt.get("verification") or {}).get("max_unsupported_claim_rate")
    if max_unsup is not None and hyp and (hyp.verification or {}).get("unsupported_claim_rate", 0) > max_unsup:
        violations.append(f"Unsupported-claim rate {(hyp.verification or {}).get('unsupported_claim_rate')} exceeds {max_unsup}")

    # Timestamp accuracy: expected events located in the right file with the right local time (±2 min).
    from datetime import datetime as _dt, timedelta as _td
    from ..models import Case as _Case
    tz = nlp.tz_from_offset(getattr(db.get(_Case, case_id), "default_timezone", "UTC"))
    ts_hits, ts_total, ts_detail = 0, 0, []
    for item in gt.get("expected_events", []):
        ts_total += 1
        e = by_name.get(item["file"])
        want = _dt.strptime(item["local_time"], "%Y-%m-%d %H:%M").replace(tzinfo=tz)
        cands = [ev for ev in events if e and ev.evidence_id == e.id and ev.occurred_at and item["contains"].lower() in (ev.title + " " + ev.description).lower()]
        ok = any(abs(ev.occurred_at - want) <= _td(minutes=2) for ev in cands)
        ts_hits += ok
        ts_detail.append({"file": item["file"], "expected": item["local_time"], "found": ok,
                          "actual": [nlp.display_dt(ev.occurred_at, ev.data) for ev in cands[:3]]})
    ambiguous = []
    for item in gt.get("ambiguous_records", []):
        e = by_name.get(item["file"])
        flagged = bool(e) and any(any(r.get("evidence_id") == e.id for r in g.related) or g.key.startswith(e.id) for g in gaps)
        ambiguous.append({**item, "flagged_by_engine": flagged})

    # ---------------------------------------------------------------- contradiction precision / recall
    exp_cons = [f for f in gt["findings"] if f["type"] == "contradiction"]
    found_exp = [f for f in findings_out if f["type"] == "contradiction" and f["status"] == "found"]
    allowed = gt.get("allowed_contradictions", [])

    def is_allowed(c):
        return any(c.category == a["category"] and ("contains" not in a or a["contains"] in con_text(c).lower()) for a in allowed)

    fps = [c for c in cons if c.id not in matched_con_ids and not is_allowed(c)]
    tp = len(matched_con_ids)
    con_precision = tp / (tp + len(fps)) if (tp + len(fps)) else None
    con_recall = len(found_exp) / len(exp_cons) if exp_cons else None

    # ---------------------------------------------------------------- dependency precision / recall
    exp_deps = [f for f in gt["findings"] if f["type"] == "dependency"]
    allowed_dep = {a["relation"] for a in gt.get("allowed_dependencies", [])}
    dep_fp = [d for d in deps if d.relation in DEPENDENT and d.id not in matched_dep_ids and d.relation not in allowed_dep]
    dep_tp = len(matched_dep_ids)
    dep_precision = dep_tp / (dep_tp + len(dep_fp)) if exp_deps and (dep_tp + len(dep_fp)) else None
    dep_recall = sum(1 for f in findings_out if f["type"] == "dependency" and f["status"] == "found") / len(exp_deps) if exp_deps else None

    # ---------------------------------------------------------------- entity P/R/F1 on scored types
    se = gt.get("scored_entities", {"types": [], "values": []})
    pred = {e.normalized.lower() for e in ents if e.type in se["types"]}
    expv = {v.lower() for v in se["values"]}
    if expv:
        tp_e = len(pred & expv)
        ep = tp_e / len(pred) if pred else 0.0
        er = tp_e / len(expv)
        ef1 = 2 * ep * er / (ep + er) if ep + er else 0.0
    else:
        ep = er = ef1 = None

    # ---------------------------------------------------------------- timeline ordering
    seq = gt.get("timeline_sequence", [])
    located = []
    for item in seq:
        e = by_name.get(item["file"])
        cands = [ev for ev in events if e and ev.evidence_id == e.id and ev.occurred_at and
                 item["contains"].lower() in (ev.title + " " + ev.description).lower()]
        located.append(min(cands, key=lambda x: x.occurred_at) if cands else None)
    pairs = [(located[i], located[i + 1]) for i in range(len(located) - 1)]
    tl_acc = (sum(1 for a, b in pairs if a and b and a.occurred_at <= b.occurred_at) / len(pairs)) if pairs else None

    # ---------------------------------------------------------------- OCR / ASR accuracy (character similarity)
    def best_ratio(expected, lines):
        return max((difflib.SequenceMatcher(None, expected.lower(), l.lower()).ratio() for l in lines), default=0.0)

    ocr_scores, ocr_engine = [], None
    for fname, exps in (gt.get("ocr_expect") or {}).items():
        e = by_name.get(fname)
        if not e:
            continue
        lines = [s.text for s in segs if s.evidence_id == e.id]
        ocr_engine = (e.file_metadata or {}).get("extraction", {}).get("method")
        for x in exps:
            ocr_scores.append(best_ratio(x, lines))
    asr_scores = []
    for fname, ref in (gt.get("asr_expect") or {}).items():
        e = by_name.get(fname)
        if not e:
            continue
        hyp_txt = re.sub(r"[^a-z0-9 ]", " ", " ".join(s.text for s in segs if s.evidence_id == e.id).lower())
        hyp_txt = re.sub(r"\s+", " ", hyp_txt).strip()
        if hyp_txt:
            asr_scores.append(difflib.SequenceMatcher(None, ref, hyp_txt).ratio())

    # ---------------------------------------------------------------- hash verification accuracy (incl. tamper simulation)
    store, correct, trials = get_storage(), 0, 0
    for e in evs.values():
        data = store.get(e.storage_key)
        trials += 2
        correct += int(sha256_bytes(data) == e.sha256)
        tampered = bytearray(data)
        tampered[len(tampered) // 2] ^= 0x01
        correct += int(sha256_bytes(bytes(tampered)) != e.sha256)

    # ---------------------------------------------------------------- source-reference coverage
    refs = [(c.source_a.get("segment_id") in seg_ids or c.source_a.get("locator") == "intake hash") and c.source_b.get("segment_id") in seg_ids for c in cons]
    refs += [all((r.get("segment_id") in seg_ids or r.get("locator") == "metadata") for r in g.related) and bool(g.related) for g in gaps]
    refs += [ev.segment_id in seg_ids for ev in events]
    if hyp:
        refs += [bool((cl.get("verification") or {}).get("sources")) for cl in hyp.supporting]
    coverage = sum(refs) / len(refs) if refs else None

    unsupported = (hyp.verification or {}).get("unsupported_claim_rate") if hyp else None
    proc_errors = [f"{r.kind}: {r.error}" for r in runs if r.status == "failed"]
    failed_files = [f"{e.original_filename}: {e.processing_error}" for e in evs.values() if e.status == "failed"]
    blocked = [f"{e.original_filename}: {e.processing_error}" for e in evs.values() if e.status == "unsupported"]
    review_pending = sum(1 for c in cons if c.review_status == "pending") + (1 if hyp and hyp.human_review_status == "pending" else 0)

    crit_missed = [f for f in findings_out if f["critical"] and f["status"] != "found"]
    if proc_errors or crit_missed or violations:
        outcome = "FAIL"
        bits = []
        if proc_errors:
            bits.append(f"{len(proc_errors)} processing stage(s) failed")
        if crit_missed:
            bits.append(f"{len(crit_missed)} critical expected finding(s) missed: " + ", ".join(f["id"] for f in crit_missed))
        if violations:
            bits.append(f"{len(violations)} forbidden finding(s)")
        reason = "; ".join(bits)
    elif hyp is None or hyp.decision != "SUPPORTED":
        outcome = "HOLD"
        reason = (f"All critical findings detected, but the reviewer decision is {hyp.decision if hyp else 'none'} "
                  f"({hyp.verdict.replace('_', ' ') if hyp else 'no hypothesis'}) - further verification is required before any conclusion.")
    else:
        outcome = "PASS"
        reason = f"All {sum(1 for f in findings_out if f['critical'])} critical findings detected; reviewer decision SUPPORTED ({hyp.verdict.replace('_', ' ')})."

    recs = []
    for f in findings_out:
        if f["status"] != "found":
            recs.append(f"Improve detection for {f['id']} ({f['description']}).")
    if fps:
        recs.append(f"Review {len(fps)} unexpected contradiction(s) for rule precision: " + ", ".join(c.code for c in fps[:5]))
    if blocked:
        recs.append("Install/enable the missing extraction engine(s) for: " + "; ".join(blocked[:3]))

    metrics = {
        "critical_findings": _m(len([f for f in findings_out if f["critical"] and f["status"] == "found"]),
                                f"{len([f for f in findings_out if f['critical'] and f['status'] == 'found'])}/{len([f for f in findings_out if f['critical']])}",
                                "critical expected findings matched"),
        "all_findings": _m(len([f for f in findings_out if f["status"] == "found"]),
                           f"{len([f for f in findings_out if f['status'] == 'found'])}/{len(findings_out)}", "all expected findings matched"),
        "contradiction_precision": _m(con_precision, f"{_pct(con_precision)}%" if con_precision is not None else "n/a",
                                      f"{tp} matched, {len(fps)} unexpected (allowed categories excluded)"),
        "contradiction_recall": _m(con_recall, f"{_pct(con_recall)}%" if con_recall is not None else "n/a",
                                   f"{len(found_exp)}/{len(exp_cons)} expected contradictions"),
        "entity_precision": _m(ep, f"{_pct(ep)}%" if ep is not None else "n/a", f"types {', '.join(se['types'])}"),
        "entity_recall": _m(er, f"{_pct(er)}%" if er is not None else "n/a", f"{len(pred & expv) if expv else 0}/{len(expv)} expected values"),
        "entity_f1": _m(ef1, f"{_pct(ef1)}%" if ef1 is not None else "n/a", "harmonic mean of precision and recall"),
        "dependency_precision": _m(dep_precision, f"{_pct(dep_precision)}%" if dep_precision is not None else "n/a",
                                   f"{dep_tp} expected dependencies matched, {len(dep_fp)} unexpected dependent pairs (allowed relations excluded)"),
        "dependency_recall": _m(dep_recall, f"{_pct(dep_recall)}%" if dep_recall is not None else "n/a",
                                f"{sum(1 for f in findings_out if f['type'] == 'dependency' and f['status'] == 'found')}/{len(exp_deps)} expected dependencies"),
        "timestamp_accuracy": _m(ts_hits / ts_total if ts_total else None, f"{_pct(ts_hits / ts_total)}%" if ts_total else "n/a",
                                 f"{ts_hits}/{ts_total} expected events found with the correct local time (±2 min)"),
        "timeline_order_accuracy": _m(tl_acc, f"{_pct(tl_acc)}%" if tl_acc is not None else "n/a",
                                      f"{len(pairs)} consecutive ground-truth event pairs; {sum(1 for x in located if x is None)} not located"),
        "ocr_char_similarity": _m(sum(ocr_scores) / len(ocr_scores) if ocr_scores else None,
                                  f"{_pct(sum(ocr_scores) / len(ocr_scores))}%" if ocr_scores else "n/a",
                                  f"{len(ocr_scores)} reference lines, engine {ocr_engine or 'n/a'}"),
        "asr_similarity": _m(sum(asr_scores) / len(asr_scores) if asr_scores else None,
                             f"{_pct(sum(asr_scores) / len(asr_scores))}%" if asr_scores else "n/a", "sequence similarity vs reference transcript"),
        "hash_verification_accuracy": _m(correct / trials if trials else None, f"{_pct(correct / trials)}%" if trials else "n/a",
                                         f"{trials} checks: original re-hash + 1-bit tamper simulation per file"),
        "source_reference_coverage": _m(coverage, f"{_pct(coverage)}%" if coverage is not None else "n/a",
                                        f"{len(refs)} findings/events checked for valid source links"),
        "unsupported_claim_rate": _m(unsupported, f"{_pct(unsupported)}%" if unsupported is not None else "n/a",
                                     "claims rejected by the Verification agent"),
        "false_positive_count": _m(len(fps), str(len(fps)), "contradictions outside expected/allowed set"),
        "processing_time": _m(duration_ms, f"{duration_ms / 1000:.1f} s", "wall-clock for full pipeline"),
        "human_reviews_pending": _m(review_pending, str(review_pending), "contradictions + hypothesis awaiting human review"),
    }
    expected_outcome = gt.get("expected_outcome")
    return {"outcome": outcome, "outcome_reason": reason, "expected_outcome": expected_outcome,
            "outcome_matches_expected": outcome == expected_outcome,
            "findings": findings_out, "timestamp_checks": ts_detail, "ambiguous_records": ambiguous,
            "irrelevant_records": gt.get("irrelevant_records", []), "false_positives": [{"code": c.code, "description": c.description} for c in fps],
            "violations": violations, "metrics": metrics, "errors": proc_errors + failed_files,
            "blocked": blocked, "recommendations": recs,
            "actual": {"contradictions": len(cons), "gaps": len(gaps), "entities": len(ents), "events": len(events),
                       "verdict": hyp.verdict if hyp else None, "decision": hyp.decision if hyp else None, "pattern": hyp.pattern if hyp else None}}
