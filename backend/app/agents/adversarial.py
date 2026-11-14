"""Adversarial Investigation Engine: Investigation -> Counter-Investigation -> Verification -> Skeptical Review.

Each agent has a narrow role and exchanges structured JSON:

* Investigation agent proposes the best-supported hypothesis from a library of
  investigation patterns, citing segment IDs for every claim and listing its assumptions.
* Counter-investigation agent searches the evidence independently for records that weaken
  the hypothesis, alternative explanations and weak (inferred) associations.
* Verification agent deterministically checks every citation: the segment exists in this case,
  the quoted values appear in it, and temporal claims rest on a known timestamp.
* Skeptical reviewer weighs verified support against counter-evidence and gaps and issues a
  balanced verdict - never a finding of guilt.
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass
from datetime import timedelta
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..analysis import nlp
from ..analysis.index import CaseIndex
from ..models import AuthenticityAssessment, Contradiction, Entity, EvidenceDependency, EvidenceGap, Relationship, TimelineEvent
from .llm import CHALLENGE_SCHEMA, evidence_block, get_llm

GUILT_RX = re.compile(r"\b(?:is guilty|committed the (?:crime|fraud)|proves? (?:that )?(?:he|she|they) (?:did|is)|"
                      r"is the (?:culprit|perpetrator|attacker)|definitely (?:did|is))\b", re.I)


@dataclass
class Ctx:
    idx: CaseIndex
    events: list[TimelineEvent]
    contradictions: list[Contradiction]
    gaps: list[EvidenceGap]
    entities: dict[str, Entity]
    relationships: list[Relationship]
    dependencies: list = None
    authenticity: list = None

    @classmethod
    def load(cls, db: Session, idx: CaseIndex) -> "Ctx":
        cid = idx.case_id
        ev = list(db.scalars(select(TimelineEvent).where(TimelineEvent.case_id == cid)))
        ev.sort(key=lambda e: (e.occurred_at is None, e.occurred_at or 0))
        return cls(idx, ev,
                   list(db.scalars(select(Contradiction).where(Contradiction.case_id == cid))),
                   list(db.scalars(select(EvidenceGap).where(EvidenceGap.case_id == cid))),
                   {e.id: e for e in db.scalars(select(Entity).where(Entity.case_id == cid))},
                   list(db.scalars(select(Relationship).where(Relationship.case_id == cid))),
                   list(db.scalars(select(EvidenceDependency).where(EvidenceDependency.case_id == cid))),
                   list(db.scalars(select(AuthenticityAssessment).where(AuthenticityAssessment.case_id == cid))))

    def of(self, *types) -> list[TimelineEvent]:
        return [e for e in self.events if e.event_type in types]

    def is_statement(self, ev_id: str) -> bool:
        e = self.idx.ev(ev_id)
        return "statement" in (e.category or "").lower() or "statement" in e.original_filename.lower()


def _claim(cid, text, segs, kind="observation", expect=None, temporal=False, source="engine"):
    return {"id": cid, "text": text, "kind": kind, "citations": [s for s in segs if s], "expect": expect or [],
            "temporal": temporal, "source": source}


_TZ = {"offset": "UTC"}


def _fmt(dt):
    return nlp.display_dt(dt, {"display_offset": _TZ["offset"]}) if dt else "an unknown time"


def _num(s: str) -> str:
    return re.sub(r"[^\d.]", "", s).rstrip("0").rstrip(".") if s else s


# =============================================================================== Investigation patterns
def p_phishing(ctx: Ctx) -> dict | None:
    idx = ctx.idx
    sus = []
    for f in idx.facts_of("url"):
        r = nlp.url_risk(f.value, nlp.KNOWN_BRAND_DOMAINS)
        if r["suspicious"]:
            sus.append((f, r))
    pays = [e for e in ctx.of("payment") if e.occurred_at]
    headers = [s for s in idx.segments if s.kind == "email_header"]
    if not sus or not pays or not headers:
        return None
    hdr_time = {}
    for s in headers:
        ev_ = next((e for e in ctx.events if e.segment_id == s.id and e.occurred_at), None)
        hdr_time[s.evidence_id] = ev_.occurred_at if ev_ else None
    in_email = [(f, r) for f, r in sus if idx.ev(f.evidence_id).detected_type == "email"]
    in_email.sort(key=lambda fr: (hdr_time.get(fr[0].evidence_id) is None, hdr_time.get(fr[0].evidence_id) or 0))
    f_url, risk = (in_email or sus)[0]
    hdr = next((s for s in headers if s.evidence_id == f_url.evidence_id), headers[0])
    sender = (hdr.data.get("from") or [{}])[0]
    recipient = (hdr.data.get("to") or [{}])[0]
    email_ev = next((e for e in ctx.events if e.segment_id == hdr.id), None)
    t0 = email_ev.occurred_at if email_ev else None
    pays_after = [p for p in pays if not t0 or p.occurred_at >= t0] or pays
    rank = {"spreadsheet": 0, "pdf": 1, "email": 2, "text": 3, "image": 4}
    amt_segs = {f.segment_id for f in idx.facts_of("amount")}
    fin = [p for p in pays_after if idx.ev(p.evidence_id).detected_type in rank and not ctx.is_statement(p.evidence_id)
           and p.segment_id in amt_segs]
    fin.sort(key=lambda p: (rank[idx.ev(p.evidence_id).detected_type], p.occurred_at))
    pay = (fin or pays_after)[0]
    pay_amt = next((f for f in idx.facts_of("amount") if f.segment_id == pay.segment_id), None)
    chat_req = [s for s in idx.segments if s.kind == "message" and s.author and re.search(r"\b(?:pay|transfer|upi|amount|fee|charge)\b", s.text, re.I)
                and s.author.lower() not in (recipient.get("name") or "").lower()]
    claims = [
        _claim("C1", f"An email from {sender.get('address')} to {recipient.get('address')} with subject "
                     f"'{hdr.data.get('subject')}' is dated {_fmt(t0)}.", [hdr.id], expect=[sender.get("address", "")], temporal=True),
        _claim("C2", f"The email/evidence links to {risk['domain']}, which shows phishing indicators: "
                     f"{'; '.join(risk['indicators'])}.", [f_url.segment_id], expect=[risk["domain"]]),
    ]
    if chat_req:
        claims.append(_claim("C3", f"In a chat, '{chat_req[0].author}' discussed or requested a payment.", [chat_req[0].id],
                             expect=[]))
    claims.append(_claim("C4", f"A payment{' of ' + pay_amt.value if pay_amt else ''} is recorded at {_fmt(pay.occurred_at)}.",
                         [pay.segment_id], expect=[pay_amt.value] if pay_amt else [], temporal=True))
    claims.append(_claim("C5", "The email, the chat and the payment form one sequence that led to the payment.",
                         [hdr.id] + ([chat_req[0].id] if chat_req else []) + [pay.segment_id], kind="inference"))
    linked = any(r.basis == "observed" and {ctx.entities[r.source_entity_id].type, ctx.entities[r.target_entity_id].type} in
                 ({"website", "phone"}, {"email", "phone"}) for r in ctx.relationships
                 if r.source_entity_id in ctx.entities and r.target_entity_id in ctx.entities)
    assumptions = ["The payment was made because of the email and chat (causation is inferred from sequence, not directly recorded)."]
    if not linked:
        assumptions.append("The chat counterpart and the email sender are the same actor - no record directly links them.")
    return {"pattern": "phishing_payment_fraud", "score": 3 + len(chat_req[:1]) + len(sus[:2]),
            "statement": (f"The evidence is consistent with a phishing-led payment fraud: an email from {sender.get('address')} "
                          f"pointing to {risk['domain']} preceded a payment"
                          f"{' of ' + pay_amt.value if pay_amt else ''} on {_fmt(pay.occurred_at)}"
                          f"{', arranged in a chat with ' + chat_req[0].author if chat_req else ''}."),
            "claims": claims, "assumptions": assumptions}


def p_account_takeover(ctx: Ctx) -> dict | None:
    signin = [e for e in ctx.of("security_alert", "login") if e.occurred_at]
    resets = [e for e in ctx.of("password_reset") if e.occurred_at]
    recov = [e for e in ctx.of("recovery_change") if e.occurred_at]
    if sum(bool(x) for x in (signin, resets, recov)) < 2:
        return None
    idx = ctx.idx
    anchor = (resets or recov)[0]
    near = [e for e in signin if abs(e.occurred_at - anchor.occurred_at) <= timedelta(hours=24) and not ctx.is_statement(e.evidence_id)]
    s0 = near[0] if near else signin[0] if signin else None
    claims, n = [], 1
    if s0:
        dev = next((f for f in idx.facts_of("device", "location", "ip") if f.segment_id == s0.segment_id), None)
        claims.append(_claim(f"C{n}", f"Account activity (sign-in/alert) recorded at {_fmt(s0.occurred_at)}"
                                      f"{' with ' + dev.type + ' ' + dev.value if dev else ''}.", [s0.segment_id],
                             expect=[dev.value] if dev else [], temporal=True)); n += 1
    for lst, label in ((resets, "A password reset"), (recov, "A change to account-recovery settings")):
        if lst:
            e = next((x for x in lst if not ctx.is_statement(x.evidence_id)), lst[0])
            claims.append(_claim(f"C{n}", f"{label} is recorded at {_fmt(e.occurred_at)}.", [e.segment_id], temporal=True)); n += 1
    denial = []
    for s in idx.segments:
        if ctx.is_statement(s.evidence_id):
            for c in nlp.claims_in(s.text):
                if c["polarity"] == "negative" and c["event_type"] in ("password_reset", "login", "recovery_change", "security_alert", "mfa"):
                    denial.append((s, c))
    if denial:
        s, c = denial[0]
        claims.append(_claim(f"C{n}", f"The account holder states: \"{c['sentence'][:180]}\"", [s.id],
                             expect=[c["sentence"][:40]])); n += 1
    claims.append(_claim(f"C{n}", "These actions were performed by someone other than the account holder.",
                         [c["citations"][0] for c in claims], kind="inference"))
    return {"pattern": "account_compromise", "score": 2 + len(claims),
            "statement": ("Account activity is consistent with unauthorised access: a sign-in/alert"
                          f"{' at ' + _fmt(s0.occurred_at) if s0 else ''} was followed by "
                          f"{'a password reset' if resets else ''}{' and ' if resets and recov else ''}"
                          f"{'a recovery-setting change' if recov else ''}"
                          f"{', which the account holder says they did not perform' if denial else ''}."),
            "claims": claims,
            "assumptions": ["The account holder's statement is accurate.",
                            "Device, IP and location values identify a session, not a person; they do not establish who acted.",
                            "Alert locations are provider IP-geolocation estimates."]}


ADVERSE_RX = re.compile(r"revok|remov|downgrad|restrict|disabl|excluded|warning|pip|disciplin|reassign|demot", re.I)


def p_retaliation(ctx: Ctx) -> dict | None:
    comp = [e for e in ctx.of("complaint") if e.occurred_at and not ctx.is_statement(e.evidence_id)] or \
           [e for e in ctx.of("complaint") if e.occurred_at]
    if not comp:
        return None
    t = comp[0].occurred_at
    adverse = [e for e in ctx.events if e.occurred_at and e.occurred_at > t and e.event_type in ("access_change", "warning", "meeting")
               and ADVERSE_RX.search(e.description or e.title) and (e.data or {}).get("channel") in ("log", "email", "chat", "pdf", "docx")]
    if not adverse:
        return None
    claims = [_claim("C1", f"A complaint is recorded at {_fmt(t)}.", [comp[0].segment_id], temporal=True)]
    for i, e in enumerate(adverse[:4], 2):
        claims.append(_claim(f"C{i}", f"After the complaint, at {_fmt(e.occurred_at)}: {e.title[:150]}", [e.segment_id], temporal=True))
    ack = [s for s in ctx.idx.segments if re.search(r"received (?:your|the) complaint|acknowledg\w+ (?:receipt|your complaint)", s.text, re.I)]
    if ack:
        claims.append(_claim(f"C{len(claims) + 1}", "The complaint was acknowledged by the organisation.", [ack[0].id]))
    claims.append(_claim(f"C{len(claims) + 1}", "The adverse changes were made because of the complaint.",
                         [comp[0].segment_id] + [e.segment_id for e in adverse[:2]], kind="inference"))
    return {"pattern": "workplace_retaliation", "score": 2 + len(adverse),
            "statement": (f"{len(adverse)} adverse change(s) were recorded after the complaint of {_fmt(t)}. The timing is "
                          "consistent with possible retaliation; timing alone does not establish the reason for the changes."),
            "claims": claims,
            "assumptions": ["The decision-makers knew about the complaint when the changes were made.",
                            "The changes were caused by the complaint rather than by an independent reason."]}


def p_delivery_dispute(ctx: Ctx) -> dict | None:
    idx = ctx.idx
    orders = idx.facts_of("order_id")
    conf = [c for c in ctx.contradictions if c.category in ("quantity_conflict", "amount_conflict", "identifier_mismatch", "date_conflict")
            and (c.field in ("quantity", "amount", "order_id", "timestamp"))]
    if not orders or not conf:
        return None
    # Anchor on the order most involved in the conflicts, not simply the first one mentioned.
    from collections import Counter
    tally = Counter(f.norm for f in orders for c in conf if f.norm.lower() in (c.key + " " + json.dumps([c.source_a, c.source_b])).lower())
    best = tally.most_common(1)[0][0] if tally else orders[0].norm
    oid = next(f for f in orders if f.norm == best)
    claims = [_claim("C1", f"Order {oid.value} is documented.", [oid.segment_id], expect=[oid.value])]
    for i, c in enumerate(conf[:5], 2):
        claims.append(_claim(f"C{i}", f"{c.description} ({c.code}).", [c.source_a.get("segment_id"), c.source_b.get("segment_id")],
                             expect=[] if c.category == "date_conflict" else [str(c.source_a.get("value") or "")[:20], str(c.source_b.get("value") or "")[:20]]))
    promise = [s for s in idx.segments if re.search(r"\b(?:will|shall)\b.{0,40}\brefund|refund within", s.text, re.I)]
    if promise:
        claims.append(_claim(f"C{len(claims) + 1}", "A refund was promised in correspondence.", [promise[0].id]))
    claims.append(_claim(f"C{len(claims) + 1}", "The seller did not deliver what was ordered and paid for.",
                         [oid.segment_id] + [conf[0].source_b.get("segment_id")], kind="inference"))
    return {"pattern": "delivery_dispute", "score": 2 + len(conf),
            "statement": (f"Records for order {oid.value} disagree: " + "; ".join(c.description for c in conf[:3]) +
                          ". The delivery does not appear to match the order as invoiced and paid."),
            "claims": claims,
            "assumptions": ["All records with the same order reference describe the same order.",
                            "The delivery record reflects what the customer physically received."]}


def p_harassment(ctx: Ctx) -> dict | None:
    idx = ctx.idx
    threats = [s for s in idx.segments if nlp.classify_event(s.text) == "threat" or re.search(r"\b(?:regret|leak|expose|watch your back)\b", s.text, re.I)]
    pres = [g for g in ctx.gaps if g.category in ("content_not_preserved", "incomplete_conversation", "missing_attachment", "collection_info_missing")]
    if not threats and not pres:
        return None
    if not threats:
        return None
    authors = sorted({s.author for s in threats if s.author})
    claims = [_claim(f"C{i}", f"Threatening/harassing content: \"{s.text[:140]}\"" + (f" (sent by '{s.author}')" if s.author else ""),
                     [s.id], expect=[s.text[:30]]) for i, s in enumerate(threats[:4], 1)]
    n = len(claims) + 1
    for g in pres[:3]:
        segs = [r.get("segment_id") for r in g.related if r.get("segment_id")]
        if segs:
            claims.append(_claim(f"C{n}", f"Preservation issue: {g.description[:200]}", segs[:2])); n += 1
    if authors:
        claims.append(_claim(f"C{n}", f"The account(s) {', '.join(authors)} are operated by the person the complainant names.",
                             [threats[0].id], kind="inference"))
    return {"pattern": "online_harassment_preservation", "score": 2 + len(threats) + len(pres),
            "statement": (f"The collection documents {len(threats)} harassing/threatening item(s)"
                          f"{' from ' + ', '.join(authors) if authors else ''}; {len(pres)} preservation issue(s) mean part of "
                          "the record is incomplete or at risk of loss."),
            "claims": claims,
            "assumptions": ["The displayed account names correspond to the person the complainant believes is responsible.",
                            "Screenshots faithfully reflect the online content at capture time."]}


PATTERNS = [p_phishing, p_account_takeover, p_retaliation, p_delivery_dispute, p_harassment]


def investigation_agent(ctx: Ctx) -> dict:
    _TZ["offset"] = ctx.idx.tz
    candidates = []
    for p in PATTERNS:
        try:
            h = p(ctx)
        except Exception as e:  # a failing pattern must not kill the run
            h = None
            candidates.append({"pattern": p.__name__, "error": str(e)})
        if h:
            candidates.append(h)
    viable = [c for c in candidates if "claims" in c]
    if not viable:
        key = [e for e in ctx.events if e.occurred_at and e.segment_id][:5]
        claims = [_claim(f"C{i}", f"Recorded event: {e.title[:150]}", [e.segment_id], temporal=True) for i, e in enumerate(key, 1)]
        if not claims:  # e.g. a single recording with no dated events: cite what was extracted instead
            claims = [_claim(f"C{i}", f"Recorded content ({s.locator}): {s.text[:150]}", [s.id])
                      for i, s in enumerate([s for s in ctx.idx.segments if s.text.strip()][:3], 1)]
        return {"pattern": "insufficient_signals", "score": 0,
                "statement": "The evidence does not match any supported investigation pattern strongly enough to form a hypothesis.",
                "claims": claims,
                "assumptions": [], "other_patterns": []}
    viable.sort(key=lambda c: -c["score"])
    top = viable[0]
    top["other_patterns"] = [{"pattern": c["pattern"], "statement": c["statement"]} for c in viable[1:]]
    return top


MAX_CANDIDATES = 3


def investigation_candidates(ctx: Ctx) -> list[dict]:
    """All viable hypotheses (best first), capped - each one is challenged separately."""
    top = investigation_agent(ctx)
    others = []
    for p in PATTERNS:
        if p.__name__ == "p_" + top["pattern"] or top["pattern"] == "insufficient_signals":
            continue
        try:
            h = p(ctx)
        except Exception:
            h = None
        if h and h["pattern"] != top["pattern"]:
            others.append(h)
    others.sort(key=lambda c: -c["score"])
    return [top] + others[:MAX_CANDIDATES - 1]


# =============================================================================== Counter-investigation
def _seg_ref(idx, sid, excerpt=None):
    s = idx.seg_by_id.get(sid)
    return idx.ref(s, excerpt) if s else None


def counter_agent(ctx: Ctx, hyp: dict) -> dict:
    idx = ctx.idx
    cited = {sid for c in hyp["claims"] for sid in c["citations"]}
    items: list[dict] = []

    def add(kind, text, segs, strength="moderate", source="engine"):
        segs = [s for s in segs if s]
        if any(i["text"] == text for i in items):
            return
        items.append({"id": f"K{len(items) + 1}", "kind": kind, "text": text, "citations": segs, "strength": strength, "source": source})

    used_as_support = {c.code for c in ctx.contradictions if any(c.code in cl["text"] for cl in hyp["claims"])}
    for c in ctx.contradictions:
        sa, sb = c.source_a.get("segment_id"), c.source_b.get("segment_id")
        if c.code in used_as_support:
            continue  # the hypothesis is built on this conflict; it is not counter-evidence to itself
        if sa in cited or sb in cited:
            add("contradiction", f"{c.code}: {c.description}. {c.reason}", [sa, sb],
                "strong" if c.confidence >= 0.8 else "moderate")
    for r in ctx.relationships:
        if r.basis == "inferred" and set(r.segment_ids or []) & cited:
            add("weak_association", f"Association between '{ctx.entities[r.source_entity_id].value}' and "
                                    f"'{ctx.entities[r.target_entity_id].value}' is inferred only: {r.description}",
                (r.segment_ids or [])[:2], "moderate")

    pat = hyp["pattern"]
    text_of = lambda s: s.text  # noqa: E731
    if pat == "phishing_payment_fraud":
        for s in idx.segments:
            if s.kind == "email_header" and s.id in cited:
                ar = " ".join(s.data.get("authentication_results") or [])
                if re.search(r"spf=pass", ar) and re.search(r"dkim=pass", ar):
                    add("alternative_explanation", "The email passed SPF and DKIM checks for its sending domain; it may be a "
                        "legitimate message from that domain.", [s.id], "strong")
        for c in ctx.contradictions:
            if c.category == "transaction_reference_mismatch":
                add("alternative_explanation", "The receipt and the bank record carry different transaction references; they may "
                    "describe different transfers, so the money trail from victim to the suspected recipient is not established.",
                    [c.source_a.get("segment_id"), c.source_b.get("segment_id")], "strong")
        if any("same actor" in a for a in hyp.get("assumptions", [])):
            add("challenge", "No record links the chat counterpart to the email sender; they could be unrelated parties.",
                [c for cl in hyp["claims"] if cl["id"] in ("C1", "C3") for c in cl["citations"]], "moderate")
    if pat == "account_compromise":
        for s in idx.segments:
            if re.search(r"\b(?:travel(?:l)?ing|vpn|new phone|changed my phone|on holiday|abroad|roaming)\b", s.text, re.I):
                add("alternative_explanation", "The record mentions travel/VPN/new device - an unfamiliar sign-in location or "
                    "device could be the account holder's own activity.", [s.id], "strong" if ctx.is_statement(s.evidence_id) else "moderate")
            if (re.search(r"\b(?:shared|sent|gave|told|here is|here's)\b.{0,40}\b(?:code|otp|password)\b", s.text, re.I)
                    and not nlp.NEGATION_RE.search(s.text) and not ctx.is_statement(s.evidence_id)):
                add("alternative_explanation", "The account holder appears to have disclosed a code/password; access may have "
                    "resulted from social engineering using credentials the holder provided, not a technical intrusion.", [s.id], "moderate")
            if re.search(r"\bI (?:reset|changed) (?:my|the) password\b", s.text, re.I):
                add("contradiction", "A record indicates the account holder changed their own password.", [s.id], "strong")
        for c in ctx.contradictions:
            if c.category == "attribute_conflict":
                add("challenge", f"Records disagree about the session attributes ({c.description}); device/location values "
                    "are not reliable identifiers.", [c.source_a.get("segment_id"), c.source_b.get("segment_id")], "moderate")
    if pat == "workplace_retaliation":
        comp_t = next((e.occurred_at for e in ctx.of("complaint") if e.occurred_at), None)
        for s in idx.segments:
            if re.search(r"\b(?:quarterly|scheduled|periodic|annual|routine)\b.{0,60}\b(?:review|audit|recertification)\b", s.text, re.I):
                add("alternative_explanation", "A policy/notice describes a scheduled access review; the access change may be part "
                    "of that routine process rather than a response to the complaint.", [s.id], "strong")
            if re.search(r"\b(?:all (?:team )?members|department-wide|organi[sz]ation-wide|reorgani[sz]ation|restructur\w+)\b", s.text, re.I):
                add("alternative_explanation", "A record describes a broader organisational change that could explain the change.", [s.id], "moderate")
        if comp_t:
            for e in ctx.of("warning"):
                if e.occurred_at and e.occurred_at < comp_t:
                    add("alternative_explanation", "A warning/performance issue predates the complaint; later actions may relate to it.",
                        [e.segment_id], "moderate")
        for c in ctx.contradictions:
            if c.category == "date_conflict" and "access" in c.description:
                add("challenge", f"The organisation's account of when access changed is contradicted ({c.code}); the explanation "
                    "offered for the change is itself unverified.", [c.source_a.get("segment_id"), c.source_b.get("segment_id")], "strong")
    if pat == "delivery_dispute":
        amts = [c for c in ctx.contradictions if c.category == "amount_conflict"]
        for c in amts:
            try:
                diff = abs(Decimal(_num(str(c.source_a["value"]))) - Decimal(_num(str(c.source_b["value"]))))
            except Exception:
                continue
            match = [f for f in idx.facts_of("amount") if f.extra.get("amount") and Decimal(f.extra["amount"]) == diff]
            if match:
                add("alternative_explanation", f"The {diff} difference between the two amounts equals an amount recorded elsewhere "
                    f"('{match[0].label or match[0].excerpt[:60]}'); the gap may be an extra charge rather than an overpayment.",
                    [match[0].segment_id], "strong")
            else:
                add("challenge", f"No recorded charge explains the {diff} difference between invoice and payment; "
                    "arithmetic was checked against every amount in the case.", [c.source_a.get("segment_id"), c.source_b.get("segment_id")], "moderate")
        for s in idx.segments:
            if re.search(r"\b(?:partial (?:shipment|delivery)|second shipment|remaining (?:units|items|quantity)|balance (?:quantity|units)|split (?:shipment|delivery))\b", s.text, re.I):
                add("alternative_explanation", "A record mentions a partial or split shipment; the shortfall may be pending delivery.", [s.id], "moderate")
        for c in ctx.contradictions:
            if c.category == "identifier_mismatch":
                add("alternative_explanation", f"Near-identical order references ({c.source_a.get('value')} / {c.source_b.get('value')}) "
                    "mean some correspondence may concern a different order.", [c.source_a.get("segment_id"), c.source_b.get("segment_id")], "moderate")
    if pat == "online_harassment_preservation":
        add("challenge", "The identity of the person behind the account(s) is not established by display names or handles.",
            [cl["citations"][0] for cl in hyp["claims"][:1]], "moderate")
        for s in idx.segments:
            if s.data.get("edited") or s.data.get("deleted"):
                add("challenge", "Some messages are marked edited/deleted; surrounding context may be missing.", [s.id], "moderate")
                break

    for g in ctx.gaps:
        if g.severity == "high":
            add("missing_information", f"{g.code}: {g.description}", [r.get("segment_id") for r in g.related][:2], "moderate")

    llm_mode = "deterministic"
    llm = get_llm()
    if llm.available() and not ctx.idx.allow_ai:
        llm_mode = "deterministic (external AI not authorised for this case - evidence was not sent)"
    elif llm.available():
        segs = [{"id": s.id, "file": idx.ev(s.evidence_id).original_filename, "locator": s.locator, "text": s.text} for s in idx.segments]
        out = llm.complete_json(
            "Role: Counter-Investigation Agent. Independently look for evidence that weakens the hypothesis below, alternative "
            "explanations, and information that is missing. Output at most 6 items.",
            f"Hypothesis: {hyp['statement']}\nAssumptions: {hyp.get('assumptions')}\n\n{evidence_block(segs)}", CHALLENGE_SCHEMA)
        if out:
            llm_mode = "llm-augmented"
            for it in (out.get("items") or [])[:6]:
                add(it.get("kind", "challenge"), str(it.get("text", ""))[:600], list(it.get("segment_ids") or [])[:4], "moderate", "llm")
        else:
            llm_mode = f"deterministic (LLM unavailable: {getattr(llm, 'last_error', None)})"
    return {"items": items, "mode": llm_mode}


# =============================================================================== Verification
def _norm(s: str) -> str:
    return re.sub(r"\s+", " ", s or "").strip().lower()


def verify_items(ctx: Ctx, items: list[dict]) -> list[dict]:
    idx = ctx.idx
    ev_by_seg: dict[str, list[TimelineEvent]] = {}
    for e in ctx.events:
        ev_by_seg.setdefault(e.segment_id, []).append(e)
    results = []
    for it in items:
        checks, status = [], "verified"
        cites = it.get("citations") or []
        if not cites:
            checks.append("no source cited")
            status = "rejected"
        valid = [c for c in cites if c in idx.seg_by_id]
        missing = [c for c in cites if c not in idx.seg_by_id]
        if missing:
            checks.append(f"{len(missing)} cited segment(s) do not exist in this case")
            status = "rejected" if not valid else "partially_verified"
        texts = " ".join(_norm(idx.seg_by_id[c].text) for c in valid)
        for exp in it.get("expect") or []:
            if exp and _norm(exp) not in texts and _norm(_num(exp)) not in re.sub(r"[^\d. a-z]", "", texts):
                checks.append(f"quoted value '{exp}' not found in cited source")
                status = "rejected" if status != "rejected" and it.get("kind") == "observation" else status
        if it.get("temporal") and valid:
            kinds = {e.timestamp_kind for c in valid for e in ev_by_seg.get(c, [])}
            if not kinds or kinds == {"unknown"}:
                checks.append("timestamp provenance unknown")
                status = "partially_verified" if status == "verified" else status
            elif kinds - {"source_reported"}:
                checks.append(f"timestamp provenance: {', '.join(sorted(kinds))}")
        if GUILT_RX.search(it.get("text", "")):
            checks.append("contains a conclusion of guilt/identity - not permitted")
            status = "rejected"
        if it.get("kind") == "inference" and status == "verified":
            status = "inference"
            checks.append("inference: sources exist but do not directly record this conclusion")
        if not checks:
            checks.append("all citations exist and contain the quoted values")
        results.append({"id": it["id"], "status": status, "checks": checks,
                        "sources": [_seg_ref(idx, c) for c in valid]})
    return results


def verification_agent(ctx: Ctx, hyp: dict, counter: dict) -> dict:
    claim_v = verify_items(ctx, hyp["claims"])
    counter_v = verify_items(ctx, counter["items"])
    cv = {r["id"]: r for r in claim_v}
    kv = {r["id"]: r for r in counter_v}
    rejected = [r for r in claim_v + counter_v if r["status"] == "rejected"]
    total = len(claim_v) + len(counter_v)
    return {"claims": claim_v, "counter": counter_v, "claim_index": cv, "counter_index": kv,
            "rejected": len(rejected), "total": total,
            "unsupported_claim_rate": round(len(rejected) / total, 3) if total else 0.0}


# =============================================================================== Skeptical reviewer
def reviewer_agent(ctx: Ctx, hyp: dict, counter: dict, ver: dict) -> dict:
    cv, kv = ver["claim_index"], ver["counter_index"]
    support = [c for c in hyp["claims"] if cv[c["id"]]["status"] in ("verified", "partially_verified") and c["kind"] == "observation"]
    inferences = [c for c in hyp["claims"] if c["kind"] == "inference"]
    rejected_claims = [c for c in hyp["claims"] if cv[c["id"]]["status"] == "rejected"]
    counters = [k for k in counter["items"] if kv[k["id"]]["status"] != "rejected"]
    strong_alt, _seen_c = [], set()
    for k in counters:  # one strong item per distinct set of source records
        if k["kind"] in ("alternative_explanation", "contradiction") and k["strength"] == "strong":
            key = frozenset(k["citations"])
            if key not in _seen_c:
                _seen_c.add(key)
                strong_alt.append(k)
    unresolved = [c for c in ctx.contradictions if c.review_status != "dismissed"]
    high_gaps = [g for g in ctx.gaps if g.severity == "high" and g.review_status == "open"]

    from ..analysis.dna import clusters
    cl = clusters(ctx.dependencies or [], list(ctx.idx.evidence))
    support_evs = {ctx.idx.seg_by_id[s].evidence_id for c in support for s in c["citations"] if s in ctx.idx.seg_by_id}
    independent = len({cl[e] for e in support_evs}) if support_evs else 0
    collapsed = len(support_evs) - independent

    if hyp["pattern"] == "insufficient_signals" or len(support) < 2:
        verdict, band = "insufficient_evidence", "low"
        reason = "Fewer than two independently verified observations support any hypothesis."
    elif strong_alt and (hyp["pattern"] == "workplace_retaliation" or len(strong_alt) >= 2 or rejected_claims):
        verdict, band = "contested", "low"
        reason = f"{len(strong_alt)} documented alternative explanation(s)/counter-record(s) carry comparable weight."
    elif high_gaps or strong_alt or inferences:
        verdict, band = "supported_with_reservations", "moderate"
        reason = ("The observed facts are verified, but the hypothesis relies on inference"
                  f"{' and ' + str(len(high_gaps)) + ' high-severity evidence gap(s) remain' if high_gaps else ''}.")
    else:
        verdict, band = "supported", "moderate"
        reason = "Observed facts are verified and no material counter-evidence was found."
    if verdict.startswith("supported") and independent < 2:
        verdict, band = "contested", "low"
        reason = (f"All verified support traces back to a single source ({len(support_evs)} file(s) that duplicate or derive from "
                  "each other); there is no independent corroboration.")
    elif collapsed:
        reason += f" {collapsed} supporting file(s) duplicate or derive from others and were counted once."

    # Decision: SUPPORTED / CONTRADICTED / INCONCLUSIVE / HOLD
    contradicting = [k for k in counters if k["kind"] == "contradiction" and k["strength"] == "strong"]
    hit_claims = {c["id"] for c in support for k in contradicting if set(c["citations"]) & set(k["citations"])}
    disputed = [a for a in (ctx.authenticity or []) if a.verdict in ("possible_impersonation", "likely_fabricated")]
    if disputed and verdict.startswith("supported"):
        a = disputed[0]
        verdict, band = "supported_with_reservations", "low"
        reason += (f" The message authenticity check rates a key message as '{a.verdict.replace('_', ' ')}', so who sent it (or whether "
                   "it exists) is unresolved until provider / device records are obtained.")
    if verdict == "insufficient_evidence" or rejected_claims or disputed:
        decision = "HOLD"
    elif support and len(hit_claims) * 2 >= len(support):
        decision = "CONTRADICTED"
    elif verdict == "contested":
        decision = "INCONCLUSIVE"
    else:
        decision = "SUPPORTED"

    next_steps = []
    for g in high_gaps[:5]:
        next_steps.extend(g.checklist[:1])
    for c in unresolved[:5]:
        if c.suggested_action not in next_steps:
            next_steps.append(c.suggested_action)
    limitations = [
        "Findings are generated by deterministic rules over extracted text; extraction errors (OCR/transcription) propagate.",
        "Timestamps without a stated timezone are compared as reported local time.",
        "No conclusion about any individual's guilt or identity is drawn; human review is required.",
    ]
    if any(ctx.idx.ev(s.evidence_id).detected_type == "image" for s in ctx.idx.segments):
        limitations.append("Some facts come from OCR of screenshots, which can misread characters.")
    return {
        "verdict": verdict, "decision": decision, "confidence_band": band, "reason": reason,
        "independent_sources": independent, "supporting_files": len(support_evs), "contradicted_claims": sorted(hit_claims),
        "summary": (f"Hypothesis ({hyp['pattern'].replace('_', ' ')}): {hyp['statement']} Reviewer verdict: "
                    f"{verdict.replace('_', ' ')} ({band} confidence). {reason}"),
        "verified_support": [c["id"] for c in support], "inferences": [c["id"] for c in inferences],
        "rejected_claims": [c["id"] for c in rejected_claims],
        "counter_considered": [k["id"] for k in counters], "strong_counter": [k["id"] for k in strong_alt],
        "unresolved_contradictions": [c.code for c in unresolved], "open_high_gaps": [g.code for g in high_gaps],
        "next_steps": next_steps[:8], "limitations": limitations, "human_review_required": True,
    }
