"""Missing Evidence Predictor.

Turns unresolved questions (open gaps, unresolved contradictions, unverified assumptions in the
leading hypothesis, documented alternative explanations) into ranked, explainable collection
recommendations. It never claims that a recommended record exists, and it only recommends lawful,
authorised sources.

Score (0-1) = 0.30*importance + 0.25*discrimination + 0.20*relevance + 0.15*information value + 0.10*availability
"""
from __future__ import annotations

from sqlalchemy import delete
from sqlalchemy.orm import Session

from ..models import EvidenceRecommendation
from .adversarial import Ctx

W = {"importance": 0.30, "discrimination": 0.25, "relevance": 0.20, "information_value": 0.15, "availability": 0.10}

SOURCES = {
    "missing_payment_confirmation": ("Bank or payment-provider transaction record (UTR/RRN detail, beneficiary account)",
                                     "Account holder's bank, with their consent, or through a lawful request to the provider"),
    "refund_unconfirmed": ("Bank statement / provider record of the refund credit", "Account holder's bank statement; seller or marketplace refund record"),
    "missing_delivery_confirmation": ("Courier proof-of-delivery (handover scan, recipient signature/photo, GPS location)",
                                      "Courier company via the buyer or seller account, or a formal request"),
    "unverified_sender": ("Original message with full headers and the mail provider's SPF/DKIM/DMARC evaluation",
                          "Recipient's mailbox export by the account holder; mail provider through lawful process"),
    "missing_original": ("Native record from the source system (not a screenshot)", "The system that produced the record, via the account holder"),
    "incomplete_conversation": ("Complete conversation export including media", "Account holder's own device or platform data download"),
    "missing_attachment": ("The referenced attachment file", "Sender's or recipient's device or mailbox export"),
    "incomplete_login_records": ("Complete session/security log covering the whole incident window",
                                 "Account holder's 'download your data' export; provider security team on lawful request"),
    "uncorroborated_claim": ("An independent record of the claimed event", "Whichever system or witness would have recorded it, through authorised channels"),
    "missing_timestamps": ("Records that carry times for the undated events", "The source systems of those events"),
    "ambiguous_timestamps": ("Locale/date-format confirmation of the exporting device", "Device owner or export settings"),
    "collection_info_missing": ("Collection record: who collected the item, from where, when and how", "The person who collected it"),
    "content_not_preserved": ("Platform preservation / archive capture of the online content", "Platform preservation request via the appropriate legal channel"),
    "undocumented_access_change": ("Change ticket, approver identity and IAM audit entry for the change",
                                   "Organisation's IAM and change-management systems via an authorised internal investigation"),
}
SEV = {"high": 1.0, "medium": 0.6, "low": 0.3}


def predict(db: Session, ctx: Ctx, primary: dict, others: list[dict], counter: dict, run_id: str) -> list[dict]:
    db.execute(delete(EvidenceRecommendation).where(EvidenceRecommendation.case_id == ctx.idx.case_id))
    cited = {s for c in primary["claims"] for s in c["citations"]}
    alts = [k for k in counter["items"] if k["kind"] == "alternative_explanation"]
    competing = [primary["statement"]] + [k["text"] for k in alts][:4] + [o["statement"] for o in others][:2]
    recs: list[dict] = []

    def add(question, evidence, why, distinguishes, confirm, disprove, source, limits, importance, info, segs, linked):
        relevance = 1.0 if set(segs) & cited else 0.4
        discrimination = min(1.0, max(0.3, len(distinguishes) / 3))
        availability = 1.0 if source else 0.5
        parts = {"importance": round(importance, 2), "discrimination": round(discrimination, 2), "relevance": relevance,
                 "information_value": info, "availability": availability}
        score = round(sum(W[k] * v for k, v in parts.items()), 3)
        recs.append(dict(question=question, recommended_evidence=evidence, why_it_matters=why, distinguishes=distinguishes,
                         could_confirm=confirm, could_disprove=disprove, authorised_source=source, limitations=limits,
                         score=score, score_breakdown=parts, linked=linked))

    for c in ctx.contradictions:
        if c.review_status == "dismissed":
            continue
        a, b = c.source_a, c.source_b
        add(f"{c.description} - which record is correct, {a.get('evidence_code')} or {b.get('evidence_code')}?",
            c.suggested_action, f"{c.code} ({c.category.replace('_', ' ')}) leaves the {c.field} unresolved; any conclusion that depends on it is uncertain.",
            [f"{a.get('evidence_code')} is accurate", f"{b.get('evidence_code')} is accurate", "the records describe different events"],
            f"A system-of-record entry matching {a.get('value')} would support {a.get('evidence_code')}.",
            f"An entry matching {b.get('value')} would support {b.get('evidence_code')} instead; neither matching suggests different events.",
            "The issuing system of the disputed record, through the account holder or a lawful request",
            "The authoritative record may also be unavailable or subject to retention limits.",
            {"high": 1.0, "medium": 0.7, "low": 0.4}.get(c.priority, 0.6), 0.9,
            [a.get("segment_id"), b.get("segment_id")], {"contradiction": c.code})
    for cl in primary["claims"]:
        if cl["kind"] != "inference":
            continue
        add(f"Is it established that: {cl['text']}", "A record that directly links the steps of the inference (e.g. a message or log that connects the actors and events)",
            "The leading hypothesis relies on this inference; it is drawn from sequence or co-occurrence, not directly recorded.",
            competing[:3], "A direct record of the link would turn the inference into an observation.",
            "A record showing a different actor, cause or sequence would favour an alternative explanation.",
            "Parties' own records or the relevant service provider, through authorised requests",
            "Absence of such a record does not disprove the inference.", 0.85, 0.8, cl["citations"], {"claim": cl["id"]})
    for k in alts[:4]:
        add(f"Does this alternative explanation hold? {k['text'][:220]}", "Records that bear on the alternative (e.g. scheduling records, travel/device records, charge breakdowns)",
            "A documented alternative explanation competes with the leading hypothesis; resolving it changes the assessment.",
            [primary["statement"][:120], k["text"][:120]], "Evidence consistent with the alternative would weaken the leading hypothesis.",
            "Evidence inconsistent with it would remove a competing explanation.",
            "The organisation or person the alternative concerns, through authorised channels",
            "The alternative may be neither confirmed nor excluded by available records.",
            0.8 if k["strength"] == "strong" else 0.55, 0.75, k["citations"], {"counter_item": k["id"]})
    for g in ctx.gaps:
        if g.review_status != "open":
            continue
        ev, src = SOURCES.get(g.category, ("; ".join(g.checklist[:2]), "Authorised source to be identified"))
        add(f"{g.description}", ev, g.why_it_matters or "This record is needed to evaluate the claim it relates to.",
            competing[:2] if g.severity == "high" else competing[:1],
            "If obtained and consistent, it corroborates the related claim independently.",
            "If obtained and inconsistent, it contradicts the related claim.", src,
            "Whether this record exists has not been established; do not assume it does.", SEV.get(g.severity, 0.5), 0.6,
            [r.get("segment_id") for r in g.related], {"gap": g.code})

    seen, uniq = set(), []
    for r in sorted(recs, key=lambda r: -r["score"]):
        if r["question"] in seen:
            continue
        seen.add(r["question"])
        uniq.append(r)
    recs = uniq
    rows = []
    for i, r in enumerate(recs[:15], 1):
        row = EvidenceRecommendation(case_id=ctx.idx.case_id, run_id=run_id, rank=i, **r)
        db.add(row)
        rows.append(row)
    db.flush()
    return [{"rank": r.rank, "question": r.question, "score": r.score} for r in rows]
