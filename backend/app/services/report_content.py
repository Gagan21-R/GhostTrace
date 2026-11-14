"""Report content model.

One structured document (20 numbered sections) is built from the case's persisted data and then
rendered as PDF, DOCX or HTML. Every factual row carries a citation in the form
``[EV-001 | Page 3]`` and, where available, the evidence/segment IDs so the HTML and in-app views
can link straight to the cited location. Labels:

  ENGINE  produced by GhostTrace agents and rules (requires human review)
  HUMAN   decisions recorded by a human reviewer
  SYSTEM  deterministic platform records (hashes, intake times, audit counts)
"""
from __future__ import annotations

import re
from collections import Counter, defaultdict
from datetime import datetime, timezone

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..analysis import nlp
from ..models import (AuditEvent, Case, Contradiction, Entity, Evidence, EvidenceDependency, EvidenceGap, EvidenceRecommendation,
                      IntegrityFinding, InvestigationEvent, Relationship, TimelineEvent, User)
from ..queries import latest_hypotheses


def _iso(dt):
    return dt.strftime("%Y-%m-%d %H:%M UTC") if dt else "—"


def locator_label(loc: str | None) -> str:
    """Human citation label for a segment locator. Unknown positions are stated, never invented."""
    if not loc:
        return "location unavailable"
    l = loc.strip()
    if m := re.match(r"^page (\d+) line (\d+)$", l):
        return f"Page {m[1]} | OCR line {m[2]}"
    if m := re.match(r"^page (\d+)$", l):
        return f"Page {m[1]}"
    if m := re.match(r"^(?:msg (\d+) )?(header|body)$", l):
        part = "Email header" if m[2] == "header" else "Email body"
        return f"Message {m[1]} | {part}" if m[1] else part
    if m := re.match(r"^msg (.+)$", l):
        return f"Message {m[1]}"
    if m := re.match(r"^(.+) row (\d+)$", l):
        return f"Sheet {m[1]} | Row {m[2]}"
    if m := re.match(r"^line (\d+)$", l):
        return f"OCR line {m[1]}"
    if m := re.match(r"^frame (.+)$", l):
        return f"Video frame {m[1]}"
    if re.match(r"^\d\d:\d\d", l):
        return f"Audio {l}"
    if m := re.match(r"^(?:para|block|heading) (\d+)$", l):
        return f"Paragraph {m[1]}"
    return l


def cite(code: str | None, locator: str | None, evidence_id: str | None = None, segment_id: str | None = None) -> dict:
    return {"text": f"[{code or 'EV-?'} | {locator_label(locator)}]", "evidence_id": evidence_id, "segment_id": segment_id}


def build(db: Session, case: Case, scenario: dict | None = None) -> dict:
    evs = list(db.scalars(select(Evidence).where(Evidence.case_id == case.id, Evidence.deleted_at.is_(None)).order_by(Evidence.evidence_code)))
    code = {e.id: e.evidence_code for e in evs}
    from ..models import ExtractedSegment
    seg_loc = dict(db.execute(select(ExtractedSegment.id, ExtractedSegment.locator).where(ExtractedSegment.case_id == case.id)).all())

    def c_seg(evidence_id, segment_id, locator=None):
        return cite(code.get(evidence_id), locator or seg_loc.get(segment_id), evidence_id, segment_id)

    def c_src(src: dict | None):
        if not src or not src.get("evidence_id"):
            return {"text": "[source unavailable]"}
        return cite(src.get("evidence_code") or code.get(src["evidence_id"]), src.get("locator") or seg_loc.get(src.get("segment_id")),
                    src["evidence_id"], src.get("segment_id"))

    ents = list(db.scalars(select(Entity).where(Entity.case_id == case.id)))
    ent_by = {e.id: e for e in ents}
    rels = list(db.scalars(select(Relationship).where(Relationship.case_id == case.id)))
    tl = [t for t in db.scalars(select(TimelineEvent).where(TimelineEvent.case_id == case.id))]
    tl.sort(key=lambda e: (e.occurred_at is None, e.occurred_at or datetime.min.replace(tzinfo=timezone.utc)))
    cons = list(db.scalars(select(Contradiction).where(Contradiction.case_id == case.id).order_by(Contradiction.code)))
    gaps = list(db.scalars(select(EvidenceGap).where(EvidenceGap.case_id == case.id).order_by(EvidenceGap.code)))
    deps = list(db.scalars(select(EvidenceDependency).where(EvidenceDependency.case_id == case.id)))
    findings = list(db.scalars(select(IntegrityFinding).where(IntegrityFinding.case_id == case.id)))
    recs = list(db.scalars(select(EvidenceRecommendation).where(EvidenceRecommendation.case_id == case.id).order_by(EvidenceRecommendation.rank)))
    hyps = latest_hypotheses(db, case.id)
    h = hyps[0] if hyps else None
    owner = db.get(User, case.created_by) if case.created_by else None
    audit_counts = dict(db.execute(select(AuditEvent.action, func.count()).where(AuditEvent.case_id == case.id).group_by(AuditEvent.action)).all())
    replay_counts = dict(db.execute(select(InvestigationEvent.component, func.count()).where(InvestigationEvent.case_id == case.id)
                                    .group_by(InvestigationEvent.component)).all())
    failed_events = list(db.scalars(select(InvestigationEvent).where(InvestigationEvent.case_id == case.id, InvestigationEvent.status == "failed")))

    S: list[dict] = []

    def section(title, label, *blocks):
        S.append({"n": len(S) + 1, "title": title, "label": label, "blocks": [b for b in blocks if b]})

    def para(t):
        return {"type": "para", "text": t}

    def table(cols, rows, widths=None):
        return {"type": "table", "columns": cols, "rows": rows, "widths": widths} if rows else para("None recorded.")

    def lst(items):
        return {"type": "list", "items": items} if items else para("None.")

    section("Case overview", "SYSTEM", table(["Field", "Value"], [
        ["Title", case.title], ["Case number", case.case_number], ["Type", case.case_type], ["Status", case.status],
        ["Priority", case.priority], ["Owner", owner.full_name if owner else "—"], ["Opened", _iso(case.created_at)],
        ["Default timezone", case.default_timezone], ["External AI authorised", "yes" if case.allow_external_ai else "no"],
        ["Description", case.description or "—"]], [35, 145]))
    section("Investigation scope", "SYSTEM",
            para(case.objective or "Establish what the evidence shows, what it does not show, and what is still needed."),
            para(f"Scope of this report: {len(evs)} evidence item(s) in the case at generation time. Findings describe what the "
                 "available records show; they are not determinations of guilt or identity."))
    section("Evidence inventory", "SYSTEM", table(["Code", "File", "Type", "Category", "Size", "Received", "Collected by / source"], [
        [e.evidence_code, e.original_filename, e.detected_type, e.category, f"{e.size_bytes:,} B", _iso(e.intake_at),
         f"{e.collected_by or '—'} / {e.collection_source or 'not recorded'}"] for e in evs], [14, 40, 16, 20, 16, 26, 48]))
    integ_rows = [[e.evidence_code, e.sha256, e.last_verification or "not re-verified", _iso(e.last_verified_at),
                   (f"duplicate of {code.get(e.duplicate_of)}" if e.duplicate_of else "")] for e in evs]
    sev = Counter(f.severity for f in findings)
    section("Integrity and provenance summary", "SYSTEM",
            para("A SHA-256 match shows the stored file is byte-identical to the one received at intake. It does not establish "
                 "that the file was genuine or unaltered before intake, nor legal admissibility."),
            table(["Code", "SHA-256 at intake", "Last check", "Checked at", "Note"], integ_rows, [14, 72, 22, 30, 42]),
            para(f"Integrity inspection: {len(findings)} observation(s) - {sev.get('high', 0)} high, {sev.get('medium', 0)} medium, "
                 f"{sev.get('low', 0)} low, {sev.get('info', 0)} informational. These are indicators for human review, not proof of tampering."),
            table(["Evidence", "Check", "Severity", "Observation"], [[cite(code.get(f.evidence_id), "file metadata", f.evidence_id),
                                                                     f.check.replace("_", " "), f.severity, f.observation]
                                                                    for f in sorted(findings, key=lambda f: ("high", "medium", "low", "info").index(f.severity))
                                                                    if f.severity != "info"], [24, 30, 16, 110]))
    section("Extraction methodology", "SYSTEM",
            para("Each file is parsed by a format-specific extractor. OCR uses PP-OCR models (RapidOCR/PaddleOCR); speech uses "
                 "faster-whisper. Every extracted segment keeps its evidence ID, location, extractor and confidence."),
            table(["Code", "Extractor (version)", "Segments", "Status", "Parameters / warnings"], [
                [e.evidence_code, (e.file_metadata or {}).get("extraction", {}).get("tool_version") or (e.file_metadata or {}).get("extraction", {}).get("method", "—"),
                 str((e.file_metadata or {}).get("extraction", {}).get("segments", "—")), e.status,
                 "; ".join([f"{k}={v}" for k, v in ((e.file_metadata or {}).get("extraction", {}).get("parameters") or {}).items()]
                           + list((e.file_metadata or {}).get("extraction", {}).get("warnings") or []))[:200] or "—"] for e in evs], [14, 52, 18, 20, 76]))
    mention_src = defaultdict(list)
    from ..models import EntityMention
    for m in db.scalars(select(EntityMention).where(EntityMention.case_id == case.id)):
        if len(mention_src[m.entity_id]) < 3:
            mention_src[m.entity_id].append(c_seg(m.evidence_id, m.segment_id))
    key_ents = sorted(ents, key=lambda e: -len((e.attributes or {}).get("sources", [])))[:60]
    section("Key entities", "ENGINE", table(["Type", "Value", "Files", "Cited at"], [
        [e.type, e.value, str(len((e.attributes or {}).get("sources", []))), mention_src.get(e.id, [])] for e in key_ents], [24, 70, 12, 74]))
    tl_rows = []
    for e in tl:
        if e.timestamp_kind == "system_recorded":
            continue
        tl_rows.append([nlp.display_dt(e.occurred_at, e.data) if e.occurred_at else "time unknown", e.timestamp_kind.replace("_", " "),
                        f"{'⚠ ' if e.conflict else ''}{e.title}", c_seg(e.evidence_id, e.segment_id)])
    section("Reconstructed timeline", "ENGINE",
            para("Timestamp basis: 'source reported' = stated inside the record; 'metadata derived' = file metadata (not the event time); "
                 "'estimated' = resolved from a relative phrase; 'unknown' = no time information. ⚠ = conflicting dates."),
            table(["When", "Basis", "Event", "Source"], tl_rows[:200], [40, 24, 82, 34]))
    section("Relationship analysis", "ENGINE",
            para("'Observed' links come directly from a record; 'inferred' links are leads only. A shared identifier does not establish "
                 "that two names belong to one person."),
            table(["Entity A", "Relationship", "Entity B", "Basis", "Sources"], [
                [ent_by[r.source_entity_id].value, r.rel_type.replace("_", " "), ent_by[r.target_entity_id].value, r.basis,
                 [c_seg(r.evidence_ids[0] if r.evidence_ids else None, s) for s in (r.segment_ids or [])[:2]]]
                for r in rels if r.source_entity_id in ent_by and r.target_entity_id in ent_by and r.rel_type != "co_mentioned"][:80], [40, 28, 40, 16, 56]))
    if h:
        section("Supporting evidence", "ENGINE", table(["Claim", "Verification", "Sources"], [
            [cl["text"], cl.get("verification", {}).get("status", "—"), [c_src(s) for s in cl.get("verification", {}).get("sources", []) if s]]
            for cl in h.supporting], [100, 24, 56]))
    else:
        section("Supporting evidence", "ENGINE", para("No challenge run has been performed for this case."))
    section("Contradictory evidence", "ENGINE", *([
        {"type": "card", "title": f"{c.code} · {c.classification} · {c.category.replace('_', ' ')} · priority {c.priority} · review: {c.review_status}",
         "rows": [["Finding", c.description], ["Source A", [c_src(c.source_a), f" {c.source_a.get('excerpt', '')[:180]}"]],
                  ["Source B", [c_src(c.source_b), f" {c.source_b.get('excerpt', '')[:180]}"]], ["Why it conflicts", c.reason],
                  ["Why linked", c.same_event_basis], ["Verify by", c.suggested_action]]
         + ([["Reviewer note [HUMAN]", c.reviewer_note]] if c.reviewer_note else [])} for c in cons] or [para("No contradictions between linked records were detected.")]))
    dep_rows = [[f"{code.get(d.evidence_a_id)} ↔ {code.get(d.evidence_b_id)}", d.relation.replace("_", " "), d.explanation,
                 [c_src({"evidence_id": m["a"]["evidence_id"], "segment_id": m["a"]["segment_id"], "locator": m["a"]["locator"]}) for m in (d.matches or [])[:1]]
                 + [c_src({"evidence_id": m["b"]["evidence_id"], "segment_id": m["b"]["segment_id"], "locator": m["b"]["locator"]}) for m in (d.matches or [])[:1]]]
                for d in deps if d.relation != "independent"]
    section("Evidence dependency observations", "ENGINE",
            para("Duplicated, derived and same-source records are not independent corroboration; corroboration counts below treat each "
                 "group of copies as one source."),
            table(["Pair", "Relation", "Explanation", "Matched at"], dep_rows, [26, 22, 92, 40]))
    section("Evidence gaps", "ENGINE", *([
        {"type": "card", "title": f"{g.code} · {g.category.replace('_', ' ')} · severity {g.severity} · {g.review_status}",
         "rows": [["Gap", g.description], ["Why it matters", g.why_it_matters or "—"],
                  ["Sources", [c_src(r) for r in g.related[:4]] or "—"], ["To resolve", "; ".join(g.checklist)]]} for g in gaps]
        or [para("No evidence gaps identified.")]), para("A missing record marks what is unknown; it never implies wrongdoing."))
    section("Competing hypotheses", "ENGINE", table(["#", "Hypothesis", "Decision", "Verdict"], [
        [str(x.rank + 1), x.statement, x.decision, x.verdict.replace("_", " ")] for x in hyps], [8, 120, 26, 26]) if hyps
        else para("No hypotheses generated."))
    if h:
        section("Counter-investigation results", "ENGINE", table(["Challenge", "Kind", "Strength", "Sources"], [
            [k["text"] + (" (LLM-suggested, verified)" if k.get("source") == "llm" else ""), k["kind"].replace("_", " "), k.get("strength", ""),
             [c_src(s) for s in (k.get("verification") or {}).get("sources", []) if s]] for k in h.counterevidence], [96, 26, 18, 40]))
        v = h.verification or {}
        section("Verification findings", "ENGINE",
                para(f"{v.get('total', 0)} claim(s) and challenge(s) were checked against the original segments; {v.get('rejected', 0)} rejected "
                     f"(unsupported-claim rate {round(100 * (v.get('unsupported_claim_rate') or 0), 1)}%)."),
                table(["Item", "Status", "Checks"], [[x["id"], x["status"], "; ".join(x["checks"])] for x in (v.get("claims", []) + v.get("counter", []))],
                      [14, 26, 140]))
        section("Alternative explanations", "ENGINE", lst([k["text"] for k in h.alternatives]))
    else:
        for t in ("Counter-investigation results", "Verification findings", "Alternative explanations"):
            section(t, "ENGINE", para("No challenge run has been performed for this case."))
    section("Missing evidence recommendations", "ENGINE", table(["#", "Question", "Recommended evidence", "Authorised source", "Score"], [
        [str(r.rank), r.question, r.recommended_evidence, r.authorised_source, f"{r.score:.2f}"] for r in recs], [8, 62, 54, 44, 12]),
        para("Recommendations name lawful, authorised sources only. They do not assume the record exists."))
    if h:
        a = h.assessment or {}
        section("Final reviewer decision", "ENGINE + HUMAN", table(["Field", "Value"], [
            ["Decision [ENGINE]", f"{h.decision} - {h.verdict.replace('_', ' ')} (confidence {a.get('confidence_band', '—')})"],
            ["Reason", a.get("reason", "—")], ["Independent supporting sources", str(a.get("independent_sources", "—"))],
            ["Unresolved contradictions", ", ".join(a.get("unresolved_contradictions", [])) or "none"],
            ["Open high-severity gaps", ", ".join(a.get("open_high_gaps", [])) or "none"],
            ["Human review [HUMAN]", f"{h.human_review_status}" + (f" - {h.human_review_note}" if h.human_review_note else "")]], [50, 130]))
    else:
        section("Final reviewer decision", "ENGINE", para("No challenge run has been performed for this case."))
    lims = list((h.assessment or {}).get("limitations", [])) if h else []
    lims += ["Findings come from deterministic rules applied to extracted text; extraction errors (OCR, transcription) propagate.",
             "Timestamps marked metadata, estimated, or with an assumed timezone are less reliable than source-reported times.",
             "Inferred relationships are leads, not established identity. Missing evidence is not evidence of wrongdoing.",
             "Integrity since intake is verified; authenticity before intake is not established by hashing."]
    from ..analysis import confidence as _conf
    cr = _conf.compute(db, case.id)
    if cr.get("score") is not None:
        section("Model confidence report", "SYSTEM",
                para(f"Overall model confidence: {cr['score']} / 100 ({cr['band']}). This measures how reliable the model's output is "
                     "for this case; it is not a finding about any person."),
                table(["Component", "Score", "Weight", "Basis"], [[c["name"], f"{c['score']}/100", f"{round(c['weight'] * 100)}%", c["detail"]]
                                                               for c in cr["components"]], [46, 18, 16, 100]),
                para("Weakest parts: " + (", ".join(cr["weakest"]) if cr.get("weakest") else "none below 80/100") + "."),
                lst(cr.get("notes", [])))
    section("Confidence and limitations", "SYSTEM", lst(list(dict.fromkeys(lims))))
    section("Audit and processing summary", "SYSTEM",
            table(["Audit action", "Count"], [[k, str(v)] for k, v in sorted(audit_counts.items())], [120, 60]),
            table(["Replay component", "Events"], [[k, str(v)] for k, v in sorted(replay_counts.items())], [120, 60]),
            para(f"{len(failed_events)} failed operation(s) recorded" + (": " + "; ".join(e.summary[:100] for e in failed_events[:5]) if failed_events else ".")))

    return {
        "format": "evidencex-report/2",
        "case": {"id": case.id, "number": case.case_number, "title": case.title, "type": case.case_type, "status": case.status},
        "generated_at": _iso(datetime.now(timezone.utc)),
        "sections": S,
        "scenario": scenario,
        "stats": {"evidence": len(evs), "entities": len(ents), "events": len(tl), "contradictions": len(cons), "gaps": len(gaps),
                  "dependencies": sum(1 for d in deps if d.relation != "independent"), "recommendations": len(recs)},
        "hypothesis": None if not h else {"statement": h.statement, "decision": h.decision, "verdict": h.verdict,
                                          "human_review": h.human_review_status},
    }
