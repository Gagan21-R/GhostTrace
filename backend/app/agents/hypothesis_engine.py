"""Alternative Hypothesis Testing Engine.

Seven agents, orchestrated with LangGraph (same runner as the processing and challenge pipelines, so every agent's
output is recorded, replayable and audited):

  1 question_analyzer      what is disputed; documented facts vs allegations
  2 hypothesis_generator   3-5 distinguishable explanations, incl. ones that challenge the allegation (+ investigator's own)
  3 evidence_mapper        every evidence item x every hypothesis: supports / contradicts / inconclusive / not evaluated,
                           each cell citing exact segments
  4 counterevidence        attacks every hypothesis: contradicting records, alternative readings of its support,
                           unverified assumptions, conflicts between sources
  5 evaluator              explainable rubric (reliability, independence via Evidence DNA, contradictions) -> qualitative label
  6 next_evidence_planner  which lawful record would best separate the hypotheses still standing
  7 independent_reviewer   checks every citation exists and says what it is cited for; flags allegation-only support,
                           repeated-source bias and unfair comparisons

Rules: no probabilities, no guilt; labels describe the state of the evidence. Evidence text is data, never instructions.
Each run creates a new version; the previous one is kept and the differences are explained.
"""
from __future__ import annotations

import re
from collections import Counter, defaultdict

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..analysis import nlp
from ..analysis.dna import clusters
from ..analysis.index import CaseIndex, Seg
from ..models import (AnalysisRun, AuthenticityAssessment, Contradiction, EvidenceDependency, HypothesisAnalysis,
                      HypothesisFeedback, IntegrityFinding, User, utcnow)

LABELS = ["strongly_supported", "partially_supported", "inconclusive", "weakened", "contradicted"]
LABEL_TEXT = {"strongly_supported": "Strongly supported by available evidence", "partially_supported": "Partially supported",
              "inconclusive": "Inconclusive", "weakened": "Weakened by available evidence", "contradicted": "Contradicted by verified evidence"}


# ----------------------------------------------------------------------------------------------- signals
def _rx(p):
    return re.compile(p, re.I)


SIGNALS = {
    "payment_debit": (_rx(r"\b(?:debit(?:ed)?|imps|neft|upi/|paid to|transferred|sent rs|amount paid)\b"), "bank_or_receipt",
                      "Payment recorded as made"),
    "payment_success_screen": (_rx(r"\b(?:payment successful|successful|success|paid)\b"), "image", "Payment app shows success"),
    "payment_failed": (_rx(r"\b(?:failed|declined|unsuccessful|pending|on hold|reversed|reversal|chargeback|not processed)\b"), "any",
                       "Payment failed, pending or reversed"),
    "reversal_credit": (_rx(r"\b(?:reversal|reversed|refund(?:ed)?|chargeback)\b.*\b(?:credit\w*|cr)\b|\b(?:credit\w*|cr)\b.*\b(?:reversal|reversed|refund)"),
                        "bank_or_receipt", "Money credited back"),
    "shipment_record": (_rx(r"\b(?:awb|tracking (?:id|no|number)|shipped|dispatched|in transit|out for delivery|picked up|consignment|manifested)\b"),
                        "any", "Shipment recorded"),
    "delivered": (_rx(r"\bdelivered\b"), "any", "Delivery recorded"),
    "delay_reason": (_rx(r"\b(?:delay(?:ed)?|held up|stuck|backlog|rescheduled|weather|strike|address (?:issue|incomplete|not found)|undelivered)\b"),
                     "any", "A delay is reported"),
    "seller_unreachable": (_rx(r"\b(?:not reachable|unreachable|blocked (?:me|my number)|no response|switched off|not answering|stopped replying|"
                               r"account (?:deleted|deactivated)|number (?:is )?not in service)\b"), "any", "Seller could not be reached"),
    "seller_ack_payment": (_rx(r"\b(?:received (?:your|the) (?:payment|money|amount)|payment (?:is )?received|got (?:the|your) (?:money|payment))\b"),
                           "chat_or_email", "Seller acknowledges receiving payment"),
    "seller_denies_payment": (_rx(r"\b(?:(?:not|never) received (?:any |the |your )?(?:payment|money|amount)|no payment (?:has been |was )?received|"
                                  r"did not receive (?:the |any )?(?:payment|money))\b"), "chat_or_email", "Seller says no payment arrived"),
    "refund_refused": (_rx(r"\b(?:no refund|cannot refund|can't refund|won'?t refund|refund (?:is )?not possible|pay (?:extra|more)|additional (?:charge|fee))\b"),
                       "any", "Refund refused or more money demanded"),
    "refund_offered": (_rx(r"\b(?:refund (?:initiated|processed|will be (?:processed|sent))|will refund|refunded|returning (?:your|the) money)\b"),
                       "any", "Refund offered or made"),
    "new_contact_details": (_rx(r"\b(?:new number|changed (?:my )?number|new (?:account|upi)|use this (?:account|upi|number)|updated bank details|"
                                r"different (?:account|upi)|pay (?:on|to) this)\b"), "chat_or_email", "Payment details changed during the deal"),
    "genuine_seller_disowns": (_rx(r"\b(?:did not (?:talk|chat|speak) (?:to|with) you|not our (?:number|account|upi)|someone (?:is )?impersonating|"
                                   r"fake (?:account|profile|seller|page)|we never (?:sold|contacted|received)|not affiliated)\b"), "any",
                               "The real seller disowns the contact"),
    "allegation": (_rx(r"\b(?:fraud|cheat(?:ed)?|scam(?:med)?|duped|never delivered|did not deliver|not delivered|stole)\b"), "statement",
                   "Allegation in a complaint or statement"),
}

ALT_READINGS = {
    "payment_debit": "A debit shows money left the payer's account; it does not identify who controls the receiving account or why.",
    "payment_success_screen": "A success screen shows the app recorded an instruction; it does not prove settlement, the final recipient, or that the image is unedited.",
    "seller_unreachable": "Being unreachable can follow from a blocked number, travel or a network problem; it does not by itself show intent.",
    "shipment_record": "A tracking entry shows a label was created or scanned; it does not show that the right item was sent or will arrive.",
    "delay_reason": "A stated reason for delay is the seller's or courier's claim until the courier confirms it.",
    "seller_ack_payment": "An acknowledgement in chat comes from whoever controls that chat account, which may not be the genuine seller.",
    "seller_denies_payment": "A denial may be true (money went elsewhere) or self-serving; the beneficiary bank's record settles it.",
    "refund_refused": "Refusing a refund is consistent with fraud but also with a genuine policy dispute.",
    "refund_offered": "An offer to refund is not a refund until a credit appears in the payer's statement.",
    "new_contact_details": "Changed payment details are a classic impersonation sign, but sellers also legitimately change accounts.",
    "genuine_seller_disowns": "A seller disowning a contact may be truthful or an attempt to avoid responsibility; platform account records can confirm.",
    "payment_failed": "A 'pending' or 'failed' status may be a temporary state that later changed; the latest bank record governs.",
    "allegation": "An allegation records what the complainant believes; it is not independent evidence of what happened.",
}

RELIABILITY = {"high": 3, "medium": 2, "low": 1}


GENERIC_CATEGORY = re.compile(r"evidence|uncategori[sz]ed|general|misc|files?$|documents?$|^$", re.I)
_REL_CACHE: dict = {}


def _first_text(ev) -> str:
    """First characters of a file's extracted text (cached per evidence id for one engine run)."""
    if ev.id not in _REL_CACHE:
        from ..db import SessionLocal
        from ..models import ExtractedSegment
        with SessionLocal() as db:
            seg = db.scalars(select(ExtractedSegment).where(ExtractedSegment.evidence_id == ev.id).order_by(ExtractedSegment.seq)).first()
            _REL_CACHE[ev.id] = (seg.text if seg else "")[:300]
    return _REL_CACHE[ev.id]


def _reliability(ev) -> str:
    """How much a record can carry, judged from the file itself. A category is used only when it is specific: an uploader
    often applies one generic category (e.g. 'complaint evidence') to every file in a batch."""
    name = ev.original_filename.lower()
    cat = "" if GENERIC_CATEGORY.search(ev.category or "") else (ev.category or "").lower()
    if ev.detected_type == "spreadsheet" or re.search(r"bank|account[_ -]?log|login|server|carrier|courier|tracking|register|access[_ -]?log|"
                                                      r"call[_ -]?log|sms|statement\.csv|platform|provider", f"{name} {cat}"):
        return "high"
    if re.search(r"complaint|statement|affidavit|fir\b", f"{name} {cat}") or \
            re.match(r"\s*(?:statement of|complaint|i (?:believe|think) )", _first_text(ev), re.I):
        return "low"
    return "medium"


def _scope_ok(scope: str, ev, seg: Seg) -> bool:
    t = f"{ev.category} {ev.original_filename}".lower()
    if scope == "bank_or_receipt":
        return ev.detected_type in ("spreadsheet", "pdf", "image") or "bank" in t or "receipt" in t
    if scope == "image":
        return ev.detected_type == "image"
    if scope == "chat_or_email":
        return ev.detected_type in ("chat", "email")
    if scope == "statement":
        return _reliability(ev) == "low"
    return True


# Signals that describe something happening; "never delivered" or "not shipped" must not count as a delivery / shipment.
NEGATABLE = {"delivered", "shipment_record", "refund_offered", "payment_debit", "seller_ack_payment"}
_NEG = re.compile(r"\b(?:not|never|no|yet to|didn'?t|did not|hasn'?t|has not|haven'?t|without)\b[^.]{0,25}$", re.I)


def _hits(idx: CaseIndex, sig: str) -> list[dict]:
    rx, scope, what = SIGNALS[sig]
    out = []
    for s in idx.segments:
        ev = idx.evidence[s.evidence_id]
        if not s.text or not _scope_ok(scope, ev, s):
            continue
        m = next((x for x in rx.finditer(s.text) if not (sig in NEGATABLE and _NEG.search(s.text[max(0, x.start() - 40):x.start()]))), None)
        if m:
            out.append({"signal": sig, "evidence_id": ev.id, "code": ev.evidence_code, "segment_id": s.id, "locator": s.locator,
                        "excerpt": nlp_excerpt(s.text, m.start()), "matched": m.group(0), "what": what})
    return out


def nlp_excerpt(text: str, pos: int, width: int = 150) -> str:
    a = max(0, pos - 50)
    return ("…" if a else "") + text[a:a + width].replace("\n", " ").strip() + ("…" if a + width < len(text) else "")


def _identifier_check(idx: CaseIndex) -> dict:
    """Compare the payment destination actually used (bank statement / receipt) with the seller's identifier.

    The seller's identifier comes first from authoritative records (marketplace listing, seller profile, invoice, order);
    only if none exist do we fall back to identifiers the seller stated in chat or email. Mentions in negative sentences
    ("X is not our account") are never treated as the seller's identifier."""
    paid, official, stated = defaultdict(list), defaultdict(list), defaultdict(list)
    neg = re.compile(r"\b(?:not (?:ours|our)|is not|isn'?t|never|fake|wrong)\b", re.I)
    for f in idx.facts:
        if f.type not in ("upi", "account"):
            continue
        ev = idx.evidence[f.evidence_id]
        seg = idx.seg_by_id.get(f.segment_id)
        text = seg.text if seg else ""
        ref = {"evidence_id": ev.id, "code": ev.evidence_code, "segment_id": f.segment_id, "locator": f.locator, "excerpt": f.excerpt,
               "matched": f.value}
        cat = f"{'' if GENERIC_CATEGORY.search(ev.category or '') else ev.category} {ev.original_filename}".lower()
        whole = " ".join(s.text for s in idx.segments_of(ev.id))[:2000]
        if re.search(r"listing|profile|invoice|order", cat) or re.search(r"seller profile|payout upi|registered upi|listing:", whole, re.I):
            official[f.norm].append(ref)
        elif ev.detected_type == "spreadsheet" or re.search(r"bank|receipt|payment|statement", cat) or \
                re.search(r"\b(?:paid to|debited|transferred|successful)\b", whole, re.I):
            paid[f.norm].append(ref)
        elif ev.detected_type in ("chat", "email", "pdf") and not neg.search(text):
            stated[f.norm].append(ref)
    seller = official or stated
    if not paid or not seller:
        return {"status": "unknown", "match": [], "mismatch": [], "basis": "no comparable identifiers"}
    basis = "marketplace listing / invoice" if official else "identifier the seller stated in chat or email"
    common = set(paid) & set(seller)
    if common:
        return {"status": "match", "match": [r for k in common for r in paid[k] + seller[k]], "mismatch": [], "basis": basis}
    return {"status": "mismatch", "match": [], "mismatch": [r for k in paid for r in paid[k]] + [r for k in seller for r in seller[k]],
            "basis": basis}


# ----------------------------------------------------------------------------------------------- hypothesis templates
def _H(hid, title, desc, assumptions, supports, contradicts, challenges_allegation=False, decisive=(), explained=None):
    """decisive: contradicting signals that settle the matter when they come from a high-reliability record.
    explained: {signal: other_signal} - a contradicting signal that stops counting once other_signal is present
    (e.g. a debit no longer argues against 'payment failed' once the bank shows it was reversed)."""
    return {"id": hid, "title": title, "description": desc, "assumptions": assumptions, "supports": supports, "contradicts": contradicts,
            "challenges_allegation": challenges_allegation, "source": "engine", "decisive": list(decisive), "explained": explained or {}}


MARKETPLACE = [
    _H("H1", "Deliberate fraud", "The seller collected the payment with no intention of delivering.",
       ["The payment reached an account the seller controls", "No genuine shipment was made"],
       ["payment_debit", "seller_unreachable", "refund_refused", "seller_ack_payment"],
       ["shipment_record", "delivered", "refund_offered", "reversal_credit", "payment_failed", "genuine_seller_disowns", "identifier_mismatch"],
       decisive=["reversal_credit", "shipment_record", "delivered"]),  # a courier / bank system record settles it
    _H("H2", "Genuine delivery delay", "The seller accepted payment in good faith; shipping or logistics problems delayed delivery.",
       ["A real shipment exists", "The seller remains contactable"],
       ["shipment_record", "delay_reason", "refund_offered"], ["seller_unreachable", "refund_refused"], True),
    _H("H3", "Incorrect payment destination", "The buyer paid a wrong account or UPI ID; the intended seller never received the funds.",
       ["The paid identifier differs from the one the seller gave"],
       ["identifier_mismatch", "seller_denies_payment"], ["identifier_match", "seller_ack_payment"], True),
    _H("H4", "Payment processing issue", "The payment was initiated but failed, stayed pending, or was reversed.",
       ["The bank never completed the transfer, or reversed it"],
       ["payment_failed", "reversal_credit"], ["payment_debit", "seller_ack_payment"], True,
       explained={"payment_debit": "reversal_credit", "seller_ack_payment": "reversal_credit"}),
    _H("H5", "Seller impersonation", "A third party posed as the legitimate seller and redirected the payment.",
       ["The contact the buyer dealt with is not the genuine seller"],
       ["genuine_seller_disowns", "new_contact_details", "identifier_mismatch"], ["identifier_match", "seller_ack_payment"], True),
]
MESSAGE = [
    _H("H1", "Sent by the account holder", "The account holder personally wrote and sent the disputed message.",
       ["The message exists on the account", "The writing matches the holder"], ["auth:exists", "auth:style_match"],
       ["auth:compromise", "auth:fabrication"]),
    _H("H2", "Sent by someone else using the account", "Another person used the holder's account (linked device, SIM swap, shared phone).",
       ["Another device or person had access at that time"], ["auth:compromise"], ["auth:no_compromise", "auth:fabrication"], True),
    _H("H3", "Screenshot fabricated or edited", "The message never existed in this form; the screenshot was made or altered.",
       ["The screenshot is not supported by the source records"], ["auth:fabrication"], ["auth:exists"], True),
]
# Message-check indicator -> signal. 'No security events' says nothing about whether the message exists, so it only
# argues against compromise; it never supports or contradicts the fabrication explanation.
AUTH_SIGNAL = {"in_export": "exists", "acknowledged": "exists", "style_match": "style_match", "no_security_events": "no_compromise"}
GENERIC = [
    _H("H1", "The allegation is accurate as described", "Events happened the way the complaint says.",
       ["Independent records corroborate the complaint"], ["engine:supported", "allegation"], ["engine:contradicted"]),
    _H("H2", "An innocent or alternative explanation", "The records are explained by ordinary events rather than wrongdoing.",
       ["A non-culpable explanation fits the records"], ["engine:alternative"], ["engine:supported"], True),
    _H("H3", "Records are incomplete or unreliable", "Gaps, conflicts or integrity problems mean no explanation can yet be relied on.",
       ["Key records are missing, conflicting or of doubtful integrity"], ["contradiction", "integrity", "gap"], [], True),
]

SCAM = [
    _H("H1", "Deliberate scam", "The other party obtained the money by deception (fake offer, fake bill, fake verification).",
       ["The request was deceptive", "The money went to an account the other party controls"],
       ["nb:scam", "payment_debit", "suspicious_domain", "unverified_sender", "refund_refused"],
       ["refund_offered", "reversal_credit", "verified_sender", "delivered"], decisive=["reversal_credit"]),
    _H("H2", "Genuine transaction or service dispute", "The other party is legitimate; this is a disagreement over a real service, fee or refund.",
       ["The other party is a real, identifiable business"], ["verified_sender", "refund_offered", "delivered", "shipment_record"],
       ["suspicious_domain", "unverified_sender", "nb:scam"], True),
    _H("H3", "Victim's own account was taken over", "The victim did not make the payment; someone with access to the account or phone did.",
       ["Another device, SIM or session was used for the payment"], ["security_event"], ["victim_paid"], True),
    _H("H4", "Records incomplete or misread", "Key records are missing, conflicting or misread, so no explanation can yet be relied on.",
       ["Important records are missing or conflict"], ["contradiction", "gap"], [], True),
]

PLANNER = [
    {"id": "bank_status", "evidence": "Transaction status (UTR) and beneficiary details from the payer's bank",
     "source": "Payer's bank, on the account holder's request or police notice", "separates": ["H1", "H3", "H4", "H5"], "urgency": "high",
     "how": "A successful debit with beneficiary details confirms where the money went (H1/H3/H5); a failed or reversed status supports H4.",
     "present_if": ["reversal_credit"], "privacy": "Only the disputed transaction, not the full statement history.",
     "retests": ["payment_debit", "identifier_match", "identifier_mismatch", "seller_ack_payment", "seller_denies_payment"]},
    {"id": "beneficiary_kyc", "evidence": "KYC holder of the receiving UPI ID / account",
     "source": "Beneficiary bank via NPCI, through legal process", "separates": ["H1", "H3", "H5"], "urgency": "high",
     "how": "If the account belongs to the seller, H3/H5 weaken; if it belongs to someone else, H1 (seller fraud) weakens.",
     "present_if": [], "privacy": "Requires legal process; never obtained informally."},
    {"id": "courier", "evidence": "Courier tracking history for the AWB number",
     "source": "Courier company's public tracking or official response", "separates": ["H1", "H2"], "urgency": "medium",
     "how": "Genuine scans support H2; an invalid or unused AWB contradicts H2 and supports H1.", "present_if": ["shipment_record"],
     "privacy": "Shipment data only."},
    {"id": "platform", "evidence": "Marketplace seller account records (registered phone, payout account, chat logs)",
     "source": "Marketplace platform's grievance or law-enforcement channel", "separates": ["H1", "H5"], "urgency": "medium",
     "how": "Shows whether the contact the buyer dealt with is the registered seller.", "present_if": ["genuine_seller_disowns"],
     "privacy": "Limit the request to the disputed listing and dates."},
    {"id": "provider_log", "evidence": "Messaging account's linked-device / session log and IP subscriber",
     "source": "Messaging provider and ISP, through legal process", "separates": ["H1", "H2", "H3"], "urgency": "high",
     "how": "Shows which device sent the message: the holder's phone (H1) or another session (H2); no record at all supports H3.",
     "present_if": [], "privacy": "Restrict to the hours around the disputed message."},
    {"id": "device_extraction", "evidence": "Forensic extraction of both phones",
     "source": "Devices produced voluntarily or seized under warrant", "separates": ["H1", "H2", "H3"], "urgency": "medium",
     "how": "Confirms whether the message exists on each device and when it was sent.", "present_if": [],
     "privacy": "Scope the extraction to the relevant chat and dates."},
    {"id": "independent_record", "evidence": "An independent record of the disputed event (system log, third-party record)",
     "source": "The organisation that holds the record", "separates": ["H1", "H2", "H3"], "urgency": "medium",
     "how": "Corroborates or contradicts the complaint with a source that does not depend on either party.", "present_if": [],
     "privacy": "Request only the records about the disputed event."},
]
PLAN_SCOPE = {"marketplace_payment": ["bank_status", "beneficiary_kyc", "courier", "platform"],
              "payment_scam": ["beneficiary_kyc", "bank_status", "provider_log", "independent_record"],
              "message_authenticity": ["provider_log", "device_extraction"], "general": ["independent_record", "bank_status"]}


# ----------------------------------------------------------------------------------------------- agents
def question_analyzer(idx: CaseIndex, db: Session) -> dict:
    text = " ".join(s.text for s in idx.segments)[:200000].lower()
    auth = list(db.scalars(select(AuthenticityAssessment).where(AuthenticityAssessment.case_id == idx.case_id)))
    market = len(re.findall(r"\b(?:sell\w*|buyer|order\w*|deliver\w*|courier|ship\w*|marketplace|purchas\w*|listing|product|awb|laptop)\b", text))
    pay = len(re.findall(r"\b(?:paid|pay\w*|upi|debit\w*|transferred|imps|neft|refund\w*)\b", text))
    from ..models import MessageClassification
    scam_msgs = [m for m in db.scalars(select(MessageClassification).where(MessageClassification.case_id == idx.case_id))
                 if m.label in ("financial_fraud", "phishing", "credential_request", "extortion") and not m.uncertain]
    if auth:
        dtype = "message_authenticity"
        q = f"Who sent the disputed message shown in {auth[0].evidence_id and idx.evidence[auth[0].evidence_id].evidence_code}, and is the screenshot genuine?"
    elif market >= 3 and pay >= 2:
        dtype = "marketplace_payment"
        amt = next((f for f in idx.facts if f.type == "amount" and f.role == "paid"), None) or next((f for f in idx.facts if f.type == "amount"), None)
        q = f"Why did the buyer not receive the goods after paying{' ' + amt.value if amt else ''}, and where did the money go?"
    elif pay >= 2 and scam_msgs:
        dtype = "payment_scam"
        amt = next((f for f in idx.facts if f.type == "amount"), None)
        q = f"Was the money{' (' + amt.value + ')' if amt else ''} obtained by deception, is this a genuine dispute, or was the victim's account used without consent?"
    else:
        dtype = "general"
        q = "Do the records support the complaint as described, or does another explanation fit them better?"
    allegations, facts = [], []
    for s in idx.segments:
        ev = idx.evidence[s.evidence_id]
        ref = {"code": ev.evidence_code, "evidence_id": ev.id, "segment_id": s.id, "locator": s.locator, "excerpt": s.text[:160]}
        if _reliability(ev) == "low" and SIGNALS["allegation"][0].search(s.text):
            allegations.append(ref)
    for f in idx.facts:
        if f.type in ("amount", "txn_ref", "upi", "order_id", "phone", "email") and _reliability(idx.evidence[f.evidence_id]) != "low":
            ev = idx.evidence[f.evidence_id]
            facts.append({"type": f.type, "value": f.value, "code": ev.evidence_code, "evidence_id": ev.id, "segment_id": f.segment_id,
                          "locator": f.locator, "excerpt": f.excerpt})
    seen, uniq = set(), []
    for f in facts:
        if (f["type"], f["value"]) not in seen:
            seen.add((f["type"], f["value"]))
            uniq.append(f)
    return {"question": q, "dispute_type": dtype, "allegations": allegations[:8], "documented_facts": uniq[:14],
            "evidence_count": len(idx.evidence), "scope": "Only the evidence currently in this case. Nothing outside it is assumed."}


def hypothesis_generator(dtype: str, feedback: list[HypothesisFeedback]) -> list[dict]:
    base = {"marketplace_payment": MARKETPLACE, "message_authenticity": MESSAGE, "payment_scam": SCAM}.get(dtype, GENERIC)
    hyps = [dict(h, status="active") for h in base]
    by_id = {h["id"]: h for h in hyps}
    for fb in sorted(feedback, key=lambda f: f.created_at):
        p = fb.payload or {}
        if fb.action == "add":
            by_id[fb.hypothesis_id] = {"id": fb.hypothesis_id, "title": p.get("title", "Investigator hypothesis")[:120],
                                       "description": p.get("description", "")[:600], "assumptions": p.get("assumptions", []),
                                       "supports": [], "contradicts": [], "keywords": [k.lower() for k in p.get("keywords", []) if k][:10],
                                       "challenges_allegation": True, "source": "investigator", "status": "active"}
            hyps.append(by_id[fb.hypothesis_id])
        elif fb.hypothesis_id in by_id:
            h = by_id[fb.hypothesis_id]
            if fb.action == "edit":
                h.update({k: p[k][:600] for k in ("title", "description") if p.get(k)})
                h["edited"] = True
            elif fb.action == "reject":
                h["status"], h["rejected_note"] = "rejected", p.get("note", "")
            elif fb.action == "restore":
                h["status"] = "active"
            elif fb.action == "challenge":
                h.setdefault("challenges", []).append(p.get("note", ""))
    return hyps


def _signal_hits(idx: CaseIndex, db: Session, needed: set[str]) -> dict[str, list[dict]]:
    hits: dict[str, list[dict]] = {}
    for sig in needed & set(SIGNALS):
        hits[sig] = _hits(idx, sig)
    if needed & {"identifier_mismatch", "identifier_match"}:
        ic = _identifier_check(idx)
        hits["identifier_mismatch"] = [dict(r, signal="identifier_mismatch", what="Paid identifier differs from the one the seller gave") for r in ic["mismatch"]]
        hits["identifier_match"] = [dict(r, signal="identifier_match", what="Paid identifier matches the one the seller gave") for r in ic["match"]]
    if any(n.startswith("auth:") for n in needed):
        for kind in ("exists", "style_match", "no_compromise", "compromise", "fabrication"):
            hits[f"auth:{kind}"] = []
        for a in db.scalars(select(AuthenticityAssessment).where(AuthenticityAssessment.case_id == idx.case_id)):
            for ind in a.indicators:
                if ind.get("kind") not in ("authentic", "compromise", "fabrication"):
                    continue
                sig = AUTH_SIGNAL.get(ind.get("key"), ind["kind"]) if ind["kind"] == "authentic" else ind["kind"]
                for code in ind.get("refs") or [idx.evidence[a.evidence_id].evidence_code]:
                    ev = next((e for e in idx.evidence.values() if e.evidence_code == code), None)
                    seg = idx.segments_of(ev.id)[0] if ev and idx.segments_of(ev.id) else None
                    if ev and seg:
                        hits[f"auth:{sig}"].append({"signal": f"auth:{sig}", "evidence_id": ev.id, "code": ev.evidence_code,
                                                            "segment_id": seg.id, "locator": seg.locator, "excerpt": ind["text"][:180],
                                                            "matched": ind["key"], "what": ind["text"][:120], "derived": "message-check agent"})
    if needed & {"nb:scam", "suspicious_domain", "unverified_sender", "verified_sender", "security_event", "victim_paid"}:
        from ..models import EvidenceGap, MessageClassification, TimelineEvent
        hits["nb:scam"] = []
        for m in db.scalars(select(MessageClassification).where(MessageClassification.case_id == idx.case_id)):
            if m.label in ("financial_fraud", "phishing", "credential_request", "extortion") and not m.uncertain and m.evidence_id in idx.evidence \
                    and _reliability(idx.evidence[m.evidence_id]) != "low":
                seg = idx.seg_by_id.get(m.segment_id) or (idx.segments_of(m.evidence_id) or [None])[0]
                if seg:
                    hits["nb:scam"].append({"signal": "nb:scam", "evidence_id": m.evidence_id, "code": idx.evidence[m.evidence_id].evidence_code,
                                            "segment_id": seg.id, "locator": seg.locator, "excerpt": m.text[:160], "matched": m.label,
                                            "what": f"Naive Bayes: {m.label.replace('_', ' ')} ({m.confidence:.0%})", "derived": "naive bayes"})
        hits["suspicious_domain"] = []
        for f in idx.facts:
            dom = f.value.split("@")[-1] if f.type == "email" else f.extra.get("domain") if f.type == "url" else None
            if dom and nlp.url_risk(dom, nlp.KNOWN_BRAND_DOMAINS)["suspicious"]:
                ev = idx.evidence[f.evidence_id]
                hits["suspicious_domain"].append({"signal": "suspicious_domain", "evidence_id": ev.id, "code": ev.evidence_code, "segment_id": f.segment_id,
                                                  "locator": f.locator, "excerpt": f.excerpt, "matched": dom,
                                                  "what": "Domain shows phishing indicators: " + "; ".join(nlp.url_risk(dom, nlp.KNOWN_BRAND_DOMAINS)["indicators"])})
        hits["unverified_sender"], hits["verified_sender"] = [], []
        for s in idx.segments:
            if s.kind != "email_header":
                continue
            ev = idx.evidence[s.evidence_id]
            ar = s.data.get("authentication_results") or ""
            auth_res = (" ".join(map(str, ar)) if isinstance(ar, (list, tuple)) else str(ar)).lower()
            key = "verified_sender" if ("spf=pass" in auth_res and "dkim=pass" in auth_res) else "unverified_sender" if _reliability(ev) != "low" else None
            if key and not re.search(r"^from:.*@(?:gmail|yahoo|outlook|inboxmail|mailbox)\.", s.text, re.I | re.M):
                hits[key].append({"signal": key, "evidence_id": ev.id, "code": ev.evidence_code, "segment_id": s.id, "locator": s.locator,
                                  "excerpt": s.text[:160], "matched": "", "derived": "email header check",
                                  "what": "Sender authenticated (SPF and DKIM pass)" if key == "verified_sender" else "Sender cannot be verified (no SPF/DKIM pass)"})
        hits["security_event"] = []
        for e in db.scalars(select(TimelineEvent).where(TimelineEvent.case_id == idx.case_id,
                                                        TimelineEvent.event_type.in_(("device_link", "sim_change", "login", "password_reset", "recovery_change")))):
            seg = idx.seg_by_id.get(e.segment_id)
            if seg:
                hits["security_event"].append({"signal": "security_event", "evidence_id": e.evidence_id, "code": idx.evidence[e.evidence_id].evidence_code,
                                               "segment_id": seg.id, "locator": seg.locator, "excerpt": seg.text[:160], "matched": "",
                                               "what": f"Account security event: {e.event_type.replace('_', ' ')}", "derived": "timeline"})
        hits["victim_paid"] = []
        for s in idx.segments:
            ev = idx.evidence[s.evidence_id]
            if ev.detected_type in ("chat", "text") and re.search(r"\b(?:i )?paid\b|\bpaid rs\b|payment (?:done|sent)", s.text, re.I) and \
                    (s.author is None or not re.search(r"hr|support|officer|desk|team|bank", s.author or "", re.I)):
                hits["victim_paid"].append({"signal": "victim_paid", "evidence_id": ev.id, "code": ev.evidence_code, "segment_id": s.id,
                                            "locator": s.locator, "excerpt": s.text[:160], "matched": "", "derived": "message text",
                                            "what": "The victim says they made the payment themselves"})
    if "contradiction" in needed:
        hits["contradiction"] = []
        for c in db.scalars(select(Contradiction).where(Contradiction.case_id == idx.case_id, Contradiction.review_status != "dismissed")):
            for side in (c.source_a, c.source_b):
                if side.get("evidence_id") in idx.evidence and side.get("segment_id"):
                    hits["contradiction"].append({"signal": "contradiction", "evidence_id": side["evidence_id"], "code": side.get("evidence_code"),
                                                  "segment_id": side["segment_id"], "locator": side.get("locator", ""),
                                                  "excerpt": side.get("excerpt", "")[:160], "matched": c.code, "what": c.description[:120],
                                                  "derived": "contradiction detector"})
    if "integrity" in needed:
        hits["integrity"] = []
        for f in db.scalars(select(IntegrityFinding).where(IntegrityFinding.case_id == idx.case_id, IntegrityFinding.severity.in_(("medium", "high")))):
            segs = idx.segments_of(f.evidence_id) if f.evidence_id in idx.evidence else []
            if segs:
                hits["integrity"].append({"signal": "integrity", "evidence_id": f.evidence_id, "code": idx.evidence[f.evidence_id].evidence_code,
                                          "segment_id": segs[0].id, "locator": "file metadata", "excerpt": f.observation[:160],
                                          "matched": f.check, "what": f.observation[:120], "derived": "integrity inspection"})
    if needed & {"engine:supported", "engine:contradicted", "engine:alternative", "gap"}:
        from ..queries import primary_hypothesis
        from ..models import EvidenceGap
        h = primary_hypothesis(db, idx.case_id)
        hits["engine:supported"], hits["engine:contradicted"], hits["engine:alternative"], hits["gap"] = [], [], [], []
        if h:
            for cl in h.supporting or []:
                for src in (cl.get("verification") or {}).get("sources", [])[:1]:
                    if src and src.get("segment_id") in idx.seg_by_id:
                        key = "engine:supported" if h.decision == "SUPPORTED" else "engine:contradicted" if h.decision == "CONTRADICTED" else None
                        if key:
                            hits[key].append({"signal": key, "evidence_id": src["evidence_id"], "code": src.get("evidence_code"),
                                              "segment_id": src["segment_id"], "locator": src.get("locator", ""), "excerpt": cl.get("text", "")[:160],
                                              "matched": h.decision, "what": f"Challenge engine verified claim ({h.decision})",
                                              "derived": "challenge engine"})
            for k in (h.alternatives or [])[:4]:
                for src in ((k.get("verification") or {}).get("sources") or [])[:1]:
                    if src and src.get("segment_id") in idx.seg_by_id:
                        hits["engine:alternative"].append({"signal": "engine:alternative", "evidence_id": src["evidence_id"], "code": src.get("evidence_code"),
                                                           "segment_id": src["segment_id"], "locator": src.get("locator", ""),
                                                           "excerpt": k.get("text", "")[:160], "matched": "alternative", "what": "Documented alternative explanation",
                                                           "derived": "counter-investigation agent"})
        for g in db.scalars(select(EvidenceGap).where(EvidenceGap.case_id == idx.case_id, EvidenceGap.severity == "high", EvidenceGap.review_status == "open")):
            r = next((r for r in g.related if r.get("segment_id") in idx.seg_by_id), None)
            if r:
                hits["gap"].append({"signal": "gap", "evidence_id": r["evidence_id"], "code": r.get("evidence_code"), "segment_id": r["segment_id"],
                                    "locator": r.get("locator", ""), "excerpt": g.description[:160], "matched": g.category, "what": "High-severity evidence gap",
                                    "derived": "gap detector"})
    return hits


def evidence_mapper(idx: CaseIndex, hyps: list[dict], hits: dict[str, list[dict]]) -> list[dict]:
    rows = []
    for ev in sorted(idx.evidence.values(), key=lambda e: e.evidence_code):
        has_text = bool(idx.segments_of(ev.id))
        cells = {}
        for h in hyps:
            if not has_text:
                cells[h["id"]] = {"state": "not_evaluated", "refs": [], "reason": "No text could be extracted from this file."}
                continue
            sup = [dict(r, relation="supports") for sig in h["supports"] for r in hits.get(sig, []) if r["evidence_id"] == ev.id]
            con = [dict(r, relation="contradicts") for sig in h["contradicts"] for r in hits.get(sig, []) if r["evidence_id"] == ev.id
                   and not hits.get((h.get("explained") or {}).get(sig, ""), [])]
            if h.get("keywords"):
                for s in idx.segments_of(ev.id):
                    kw = next((k for k in h["keywords"] if k in s.text.lower()), None)
                    if kw:
                        sup.append({"signal": "keyword", "evidence_id": ev.id, "code": ev.evidence_code, "segment_id": s.id, "locator": s.locator,
                                    "excerpt": s.text[:160], "matched": kw, "what": f"Mentions '{kw}' (investigator keyword)", "relation": "supports"})
                        break
            state = "supports" if sup and not con else "contradicts" if con and not sup else "inconclusive"
            reason = ("; ".join(sorted({r["what"] for r in sup + con}))[:300] if sup or con
                      else "Read, but has no bearing on this explanation.")
            cells[h["id"]] = {"state": state, "refs": (sup + con)[:6], "reason": reason, "mixed": bool(sup and con)}
        rows.append({"evidence_id": ev.id, "code": ev.evidence_code, "file": ev.original_filename, "type": ev.detected_type,
                     "reliability": _reliability(ev), "allegation": _reliability(ev) == "low", "cells": cells})
    return rows


def counterevidence(hyps, matrix, db: Session, idx: CaseIndex) -> dict:
    cons = list(db.scalars(select(Contradiction).where(Contradiction.case_id == idx.case_id)))
    out = {}
    for h in hyps:
        hid = h["id"]
        contra = [r for row in matrix for r in row["cells"][hid]["refs"] if r["relation"] == "contradicts"]
        sup = [r for row in matrix for r in row["cells"][hid]["refs"] if r["relation"] == "supports"]
        readings = []
        for sig in sorted({r["signal"] for r in sup}):
            if sig in ALT_READINGS:
                readings.append({"signal": sig, "text": ALT_READINGS[sig], "refs": [r for r in sup if r["signal"] == sig][:2]})
        sup_sigs = {r["signal"] for r in sup}
        unverified = list(h["assumptions"]) if not sup_sigs else [a for a, sig in zip(h["assumptions"], h["supports"]) if sig not in sup_sigs]
        cited = {r["evidence_id"] for r in sup}
        conflicts = [{"code": c.code, "text": c.description[:200]} for c in cons
                     if {c.source_a.get("evidence_id"), c.source_b.get("evidence_id")} & cited]
        out[hid] = {"contradicting": contra[:8], "alternative_readings": readings, "unverified_assumptions": unverified,
                    "conflicts": conflicts[:5], "challenges": h.get("challenges", [])}
    return out


def evaluator(hyps, matrix, counter, deps, idx) -> list[dict]:
    cl = clusters(deps, list(idx.evidence))
    res = []
    for h in hyps:
        hid = h["id"]
        sup_rows = [r for r in matrix if r["cells"][hid]["state"] in ("supports",) or (r["cells"][hid].get("mixed") and
                    any(x["relation"] == "supports" for x in r["cells"][hid]["refs"]))]
        con_rows = [r for r in matrix if any(x["relation"] == "contradicts" for x in r["cells"][hid]["refs"])]
        sup_non_alleg = [r for r in sup_rows if not r["allegation"]]
        groups = {cl[r["evidence_id"]] for r in sup_non_alleg}
        con_groups = {cl[r["evidence_id"]] for r in con_rows}
        hi_sup = sum(1 for r in sup_non_alleg if r["reliability"] == "high")
        hi_con = sum(1 for r in con_rows if r["reliability"] == "high")
        decisive = [r for r in con_rows if r["reliability"] == "high" and
                    any(x["relation"] == "contradicts" and x["signal"] in h.get("decisive", []) for x in r["cells"][hid]["refs"])]
        if h["status"] == "rejected":
            label = "rejected"
        elif decisive:
            label = "contradicted"
        elif hi_con and (hi_sup == 0 or hi_con > hi_sup):
            label = "contradicted"
        elif len(con_groups) > len(groups):
            label = "weakened"
        elif len(groups) >= 2 and hi_sup >= 1 and not con_rows:
            label = "strongly_supported"
        elif groups and h.get("source") != "investigator":
            label = "partially_supported"
        elif groups:
            label = "partially_supported" if len(groups) >= 2 else "inconclusive"
        else:
            label = "inconclusive"
        dup = len(sup_non_alleg) - len(groups)
        basis = [f"{len(groups)} independent supporting source group(s) ({hi_sup} high-reliability record(s))",
                 f"{len(con_rows)} contradicting record(s) ({hi_con} high-reliability)"]
        if decisive:
            basis.append(f"decisive contradicting record: {decisive[0]['code']} ({decisive[0]['file']})")
        if dup > 0:
            basis.append(f"{dup} supporting file(s) are copies or derivatives and were counted once")
        alleg = [r for r in sup_rows if r["allegation"]]
        if alleg and not sup_non_alleg:
            basis.append("support comes only from the complaint/statement, which is an allegation, not independent evidence")
        if counter[hid]["unverified_assumptions"]:
            basis.append("unverified: " + "; ".join(counter[hid]["unverified_assumptions"][:3]))
        res.append({"id": hid, "title": h["title"], "label": label, "allegation_only": bool(alleg and not sup_non_alleg),
                    "source": h.get("source", "engine"), "label_text": LABEL_TEXT.get(label, "Rejected by investigator"),
                    "independent_support": len(groups), "contradicting": len(con_rows), "high_reliability_support": hi_sup,
                    "high_reliability_contradictions": hi_con, "basis": basis,
                    "key_support": [x for r in sup_non_alleg[:3] for x in r["cells"][hid]["refs"][:1]],
                    "key_contradictions": [x for r in con_rows[:3] for x in r["cells"][hid]["refs"] if x["relation"] == "contradicts"][:3]})
    order = {l: i for i, l in enumerate(LABELS + ["rejected"])}
    res.sort(key=lambda r: (order[r["label"]], -r["independent_support"], r["contradicting"]))
    for i, r in enumerate(res):
        r["rank"] = i + 1
    return res


def next_evidence_planner(dtype, comparison, hits, idx, counter=None) -> list[dict]:
    standing = {c["id"] for c in comparison if c["label"] not in ("contradicted", "rejected")}
    out = []
    for item in [p for p in PLANNER if p["id"] in PLAN_SCOPE.get(dtype, PLAN_SCOPE["general"])]:
        reopen = set()
        for c in comparison:  # contradicted only by things this record would re-check -> still worth testing
            sigs = {r["signal"] for r in ((counter or {}).get(c["id"], {}).get("contradicting") or [])}
            if c["label"] == "contradicted" and sigs and sigs <= set(item.get("retests", [])):
                reopen.add(c["id"])
        sep = [h for h in item["separates"] if h in standing | reopen]
        if len(sep) < 2:
            continue
        present = [sig for sig in item["present_if"] if hits.get(sig)]
        have_high = present and any(idx.evidence[r["evidence_id"]] and _reliability(idx.evidence[r["evidence_id"]]) == "high"
                                    for sig in present for r in hits[sig])
        if have_high:
            continue
        score = len(sep) * 2 + {"high": 3, "medium": 2, "low": 1}[item["urgency"]] + (0 if present else 1)
        out.append({**{k: item[k] for k in ("id", "evidence", "source", "how", "urgency", "privacy")}, "separates": sep,
                    "partially_present": bool(present), "priority_score": score})
    out.sort(key=lambda x: -x["priority_score"])
    for i, x in enumerate(out):
        x["rank"] = i + 1
    return out


def independent_reviewer(question, hyps, matrix, counter, comparison, idx) -> dict:
    issues, checked = [], 0
    for row in matrix:
        for hid, cell in row["cells"].items():
            for r in cell["refs"]:
                checked += 1
                seg = idx.seg_by_id.get(r["segment_id"])
                if not seg or seg.evidence_id != r["evidence_id"]:
                    issues.append({"severity": "high", "type": "ungrounded", "text": f"{hid}: citation {r.get('code')} {r.get('locator')} does not exist"})
                elif not r.get("derived") and r["signal"] not in ("identifier_mismatch", "identifier_match") and \
                        r.get("matched") and r["matched"].lower() not in seg.text.lower():
                    issues.append({"severity": "high", "type": "misquoted", "text": f"{hid}: {r['code']} {r['locator']} does not contain '{r['matched']}'"})
    for c in comparison:
        if c["label"] in ("strongly_supported", "partially_supported") and c["independent_support"] == 1 and c["high_reliability_support"] == 0:
            issues.append({"severity": "medium", "type": "single_source", "text": f"{c['id']} rests on a single, non-system source"})
        if c.get("allegation_only"):
            issues.append({"severity": "medium", "type": "circular", "text": f"{c['id']} is supported only by the complaint itself"})
        if c["contradicting"] and c["label"] == "strongly_supported":
            issues.append({"severity": "high", "type": "inconsistent", "text": f"{c['id']} labelled strong despite contradictions"})
    if not any(h.get("challenges_allegation") for h in hyps if h.get("status") == "active"):
        issues.append({"severity": "high", "type": "unfair", "text": "No active hypothesis challenges the allegation"})
    for h in hyps:
        if h["status"] == "active" and h["id"] not in counter:
            issues.append({"severity": "high", "type": "unchallenged", "text": f"{h['id']} was not challenged"})
    top = [c for c in comparison if c["label"] not in ("rejected",)]
    tied = len(top) >= 2 and top[0]["label"] == top[1]["label"]
    return {"status": "passed" if not any(i["severity"] == "high" for i in issues) else "issues_found", "citations_checked": checked,
            "issues": issues, "leading_is_tied": tied,
            "statement": ("No explanation is clearly ahead; treat all standing hypotheses as open." if tied else
                          f"{top[0]['id']} currently fits the evidence best; this is not a finding of guilt or liability." if top else "")}


def baseline_single_agent(dtype, hits) -> dict:
    """A naive single-agent investigator that confirms the first allegation if any payment/complaint record exists.
    Kept only to show what the adversarial engine guards against."""
    sig = hits.get("payment_debit") or hits.get("allegation") or hits.get("auth:exists") or hits.get("engine:supported")
    return {"method": "single agent: confirm the allegation when any supporting record exists, no counter-search",
            "conclusion": "H1 supported" if sig else "No conclusion", "considered_alternatives": 0, "cited": len(sig or [])}


def diff_versions(prev: HypothesisAnalysis | None, comparison, idx) -> dict:
    if not prev:
        return {"first_version": True, "changed": [], "new_evidence": []}
    before = {c["id"]: c for c in prev.comparison}
    new_ev = [e for e in idx.evidence if e not in set(prev.evidence_ids)]
    changed = []
    for c in comparison:
        b = before.get(c["id"])
        if b and b["label"] != c["label"]:
            because = [r for r in c["key_support"] + c["key_contradictions"] if r["evidence_id"] in new_ev]
            changed.append({"id": c["id"], "title": c["title"], "from": b["label"], "to": c["label"],
                            "because": ("New evidence " + ", ".join(sorted({r["code"] for r in because})) + ": " + because[0]["what"]) if because
                            else "Re-evaluation with updated findings or investigator feedback."})
    lead_b = prev.comparison[0]["id"] if prev.comparison else None
    lead_a = comparison[0]["id"] if comparison else None
    return {"first_version": False, "previous_version": prev.version, "changed": changed,
            "new_evidence": [idx.evidence[e].evidence_code for e in new_ev], "leading_before": lead_b, "leading_after": lead_a,
            "leading_changed": lead_b != lead_a}


# ----------------------------------------------------------------------------------------------- orchestration
def run(db: Session, case_id: str, user: User | None = None, trigger: str = "manual") -> HypothesisAnalysis:
    from . import orchestrator as orch
    run_row = AnalysisRun(case_id=case_id, kind="hypotheses", status="running", started_by=user.id if user else None)
    db.add(run_row)
    db.commit()
    r = orch.Runner(db, run_row, user)
    ctx: dict = {}

    def n1(state):
        ctx["idx"] = CaseIndex(db, case_id)
        ctx["q"] = question_analyzer(ctx["idx"], db)
        return {k: v for k, v in ctx["q"].items() if k != "documented_facts"} | {"facts": len(ctx["q"]["documented_facts"])}

    def n2(state):
        fb = list(db.scalars(select(HypothesisFeedback).where(HypothesisFeedback.case_id == case_id)))
        ctx["hyps"] = hypothesis_generator(ctx["q"]["dispute_type"], fb)
        return {"hypotheses": [{"id": h["id"], "title": h["title"], "status": h["status"], "source": h["source"]} for h in ctx["hyps"]]}

    def n3(state):
        _REL_CACHE.clear()
        needed = {s for h in ctx["hyps"] for s in h["supports"] + h["contradicts"]} | {"payment_debit", "allegation", "shipment_record",
                                                                                         "genuine_seller_disowns", "reversal_credit"}
        ctx["hits"] = _signal_hits(ctx["idx"], db, needed)
        ctx["matrix"] = evidence_mapper(ctx["idx"], ctx["hyps"], ctx["hits"])
        states = Counter(c["state"] for row in ctx["matrix"] for c in row["cells"].values())
        return {"evidence_items": len(ctx["matrix"]), "cells": dict(states)}

    def n4(state):
        ctx["counter"] = counterevidence(ctx["hyps"], ctx["matrix"], db, ctx["idx"])
        return {h: {"contradicting": len(v["contradicting"]), "alternative_readings": len(v["alternative_readings"]),
                    "unverified_assumptions": len(v["unverified_assumptions"])} for h, v in ctx["counter"].items()}

    def n5(state):
        deps = list(db.scalars(select(EvidenceDependency).where(EvidenceDependency.case_id == case_id)))
        ctx["cmp"] = evaluator(ctx["hyps"], ctx["matrix"], ctx["counter"], deps, ctx["idx"])
        return {"ranking": [f"{c['id']}: {c['label']}" for c in ctx["cmp"]]}

    def n6(state):
        ctx["next"] = next_evidence_planner(ctx["q"]["dispute_type"], ctx["cmp"], ctx["hits"], ctx["idx"], ctx["counter"])
        return {"recommendations": [x["evidence"] for x in ctx["next"]]}

    def n7(state):
        ctx["review"] = independent_reviewer(ctx["q"], ctx["hyps"], ctx["matrix"], ctx["counter"], ctx["cmp"], ctx["idx"])
        return {"status": ctx["review"]["status"], "issues": len(ctx["review"]["issues"]), "citations_checked": ctx["review"]["citations_checked"]}

    graph = orch._graph([("question_analyzer", r.node("question_analyzer", n1, 0.1)),
                         ("hypothesis_generator", r.node("hypothesis_generator", n2, 0.25)),
                         ("evidence_mapper", r.node("evidence_mapper", n3, 0.4)),
                         ("counterevidence", r.node("counterevidence", n4, 0.55)),
                         ("hypothesis_evaluator", r.node("hypothesis_evaluator", n5, 0.7)),
                         ("next_evidence_planner", r.node("next_evidence_planner", n6, 0.85)),
                         ("independent_reviewer", r.node("independent_reviewer", n7, 0.95))])
    st = graph.invoke({"case_id": case_id, "run_id": run_row.id, "results": {}, "errors": [], "halted": False})
    if st.get("errors"):
        run_row.status, run_row.error, run_row.finished_at = "failed", "; ".join(e["error"] for e in st["errors"])[:500], utcnow()
        db.commit()
        raise RuntimeError(run_row.error)
    prev = db.scalars(select(HypothesisAnalysis).where(HypothesisAnalysis.case_id == case_id).order_by(HypothesisAnalysis.version.desc())).first()
    row = HypothesisAnalysis(case_id=case_id, run_id=run_row.id, version=(prev.version + 1) if prev else 1, trigger=trigger,
                             evidence_ids=sorted(ctx["idx"].evidence), question=ctx["q"], hypotheses=ctx["hyps"], matrix=ctx["matrix"],
                             counter=ctx["counter"], comparison=ctx["cmp"], next_evidence=ctx["next"], review=ctx["review"],
                             changes=diff_versions(prev, ctx["cmp"], ctx["idx"]),
                             baseline=baseline_single_agent(ctx["q"]["dispute_type"], ctx["hits"]), created_by=user.id if user else None)
    db.add(row)
    run_row.status, run_row.stage, run_row.progress, run_row.finished_at = "completed", "done", 1.0, utcnow()
    db.commit()
    from .. import audit
    audit.record(db, "hypotheses.evaluated", user=user, case_id=case_id,
                 detail={"version": row.version, "leading": ctx["cmp"][0]["id"] if ctx["cmp"] else None, "trigger": trigger})
    return row
