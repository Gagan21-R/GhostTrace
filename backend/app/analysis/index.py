"""CaseIndex: an in-memory, read-only view over a case's extracted segments and the typed
facts found in them. All downstream analysis (entities, timeline, contradictions, gaps,
agents) works from this index so every finding can point back to a segment."""
from __future__ import annotations

import re
from dataclasses import dataclass, field

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..models import Evidence, ExtractedSegment
from ..services.engines import get_nlp
from . import nlp

PERSON_KEYS = {"name", "customer", "customer name", "employee", "employee name", "sender", "recipient", "reported by",
               "complainant", "manager", "agent", "account holder", "beneficiary", "beneficiary name", "payee",
               "payer", "user", "approved by", "issued by", "signed", "delivered to", "received by", "requested by",
               "changed by", "performed by", "statement of", "interviewee", "attendees", "buyer", "contact person"}
ORG_KEYS = {"company", "seller", "merchant", "bank", "courier", "carrier", "organisation", "organization", "vendor",
            "store", "platform", "service", "department", "issuer"}
ORG_HINT = re.compile(r"\b(?:Ltd|Pvt|Inc|LLC|LLP|Corp|Bank|Services|Store|Courier|Logistics|Mart|Express|Technologies|"
                      r"Solutions|Retail|Traders|Enterprises|Team|Department|HR|Support)\b", re.I)


@dataclass
class Fact:
    type: str
    value: str
    norm: str
    segment_id: str
    evidence_id: str
    locator: str
    excerpt: str
    label: str = ""
    role: str = ""
    extra: dict = field(default_factory=dict)


@dataclass
class Seg:
    id: str
    evidence_id: str
    seq: int
    locator: str
    kind: str
    author: str | None
    timestamp_raw: str | None
    text: str
    method: str
    confidence: float
    data: dict


def _excerpt(text: str, start: int, width: int = 90) -> str:
    a = max(0, start - width // 2)
    b = min(len(text), start + width)
    s = text[a:b].replace("\n", " ").strip()
    return ("…" if a > 0 else "") + s + ("…" if b < len(text) else "")


def _role_from_label(label: str, text_ctx: str = "") -> str:
    ctx = (label + " " + text_ctx).lower()
    for role, words in (("refund", ("refund",)), ("delivered", ("deliver", "received", "receiv")),
                        ("ordered", ("order", "ordered", "purchase")), ("invoiced", ("invoice", "bill", "total due", "grand total")),
                        ("paid", ("paid", "payment", "debited", "transferred", "amount sent", "debit")),
                        ("credited", ("credited", "credit")), ("shipped", ("shipped", "dispatch"))):
        if any(w in ctx for w in words):
            return role
    return ""


class CaseIndex:
    def __init__(self, db: Session, case_id: str):
        from ..models import Case
        self.case_id = case_id
        case = db.get(Case, case_id)
        self.tz = (case.default_timezone if case else None) or "UTC"
        self.allow_ai = bool(case and case.allow_external_ai)
        self.evidence: dict[str, Evidence] = {e.id: e for e in db.scalars(
            select(Evidence).where(Evidence.case_id == case_id, Evidence.deleted_at.is_(None)))}
        self.segments: list[Seg] = [
            Seg(s.id, s.evidence_id, s.seq, s.locator, s.kind, s.author, s.timestamp_raw, s.text or "", s.method,
                s.confidence, s.data or {})
            for s in db.scalars(select(ExtractedSegment).where(ExtractedSegment.case_id == case_id)
                                .order_by(ExtractedSegment.evidence_id, ExtractedSegment.seq))
            if s.evidence_id in self.evidence]
        self.seg_by_id = {s.id: s for s in self.segments}
        self.facts: list[Fact] = []
        for s in self.segments:
            self.facts.extend(self._facts_for(s))

    # -------------------------------------------------------------- helpers
    def ev(self, evidence_id: str) -> Evidence:
        return self.evidence[evidence_id]

    def ref(self, seg: Seg, excerpt: str | None = None) -> dict:
        e = self.evidence[seg.evidence_id]
        return {"evidence_id": e.id, "evidence_code": e.evidence_code, "filename": e.original_filename,
                "segment_id": seg.id, "locator": seg.locator, "excerpt": (excerpt or seg.text[:220]).strip()}

    def facts_of(self, *types: str) -> list[Fact]:
        return [f for f in self.facts if f.type in types]

    def evidence_category(self, evidence_id: str) -> str:
        return (self.evidence[evidence_id].category or "").lower()

    # -------------------------------------------------------------- fact extraction
    def _facts_for(self, s: Seg) -> list[Fact]:
        out: list[Fact] = []
        text = s.text
        fields: dict = s.data.get("fields") or {}

        def add(t, value, norm, start=0, label="", role="", **extra):
            out.append(Fact(t, value, norm, s.id, s.evidence_id, s.locator, _excerpt(text, start), label, role, extra))

        # Structured key/value fields first (labels give roles).
        for k, v in fields.items():
            v = str(v)
            for a in nlp.find_amounts(v):
                add("amount", a["raw"], f"{a['currency']} {a['value']}", text.find(v), k, _role_from_label(k),
                    currency=a["currency"], amount=a["value"])
            if not nlp.find_amounts(v) and re.search(r"amount|total|price|paid|refund|debit|credit", k) and re.fullmatch(r"[\d,]+(?:\.\d{1,2})?", v.strip()):
                n = nlp.normalize_amount("", v.strip())
                if n:
                    add("amount", v, f"UNK {n[1].quantize(__import__('decimal').Decimal('0.01'))}", text.find(v), k,
                        _role_from_label(k), currency="UNK", amount=str(n[1]))
            if re.search(r"\b(?:qty|quantity|units|count)\b", k) and re.match(r"^\d{1,6}\b", v.strip()):
                add("quantity", v.strip().split()[0], v.strip().split()[0], text.find(v), k, _role_from_label(k))
            if re.search(r"location|city|region|geo", k) and v.strip():
                add("location", v.strip(), v.strip().lower(), text.find(v), k)
            if re.search(r"device|browser|user agent|platform", k) and v.strip() and k not in ORG_KEYS:
                add("device", v.strip(), v.strip().lower(), text.find(v), k)
            if re.search(r"\bstatus\b", k) and v.strip():
                add("status", v.strip(), v.strip().lower(), text.find(v), k)
            if re.search(r"order\s*(?:id|no|number|#)?$", k) and re.search(r"\d{4,}", v):
                add("order_id", v.strip(), v.strip().upper().lstrip("#"), text.find(v), k)
            if re.search(r"(?:utr|txn|transaction|reference|ref|rrn)", k) and re.fullmatch(r"[A-Za-z0-9-]{6,24}", v.strip()):
                add("txn_ref", v.strip(), v.strip().upper(), text.find(v), k)
            if re.search(r"tracking|awb", k) and re.fullmatch(r"[A-Za-z0-9]{8,20}", v.strip()):
                add("tracking", v.strip(), v.strip().upper(), text.find(v), k)
            kl = k.strip().lower()
            if kl in PERSON_KEYS or kl in ORG_KEYS:
                for part in re.split(r",|;| and ", v):
                    part = re.sub(r"\(.*?\)|<.*?>", "", part).strip()
                    if not part or nlp.EMAIL_RE.fullmatch(part) or len(part) > 60 or re.search(r"\d{3,}", part):
                        continue
                    is_org = kl in ORG_KEYS or bool(ORG_HINT.search(part))
                    add("organisation" if is_org else "person", part, part.lower(), text.find(part), k)

        # Free-text patterns.
        for m in nlp.EMAIL_RE.finditer(text):
            line_start = text.rfind("\n", 0, m.start()) + 1
            if re.match(r"\s*(?:message-id|in-reply-to|references)\s*:", text[line_start:m.start()], re.I) or \
                    text[max(0, m.start() - 1):m.start()] == "<" and re.match(r"[0-9a-f]{12,}@", m.group(0)):
                continue  # Message-IDs look like addresses but identify a message, not a person
            add("email", m.group(0), m.group(0).lower(), m.start())
        for m in nlp.UPI_RE.finditer(text):
            if not nlp.EMAIL_RE.match(text, m.start()):
                add("upi", m.group(0), m.group(0).lower(), m.start())
        urls = set()
        for m in nlp.URL_RE.finditer(text):
            u = m.group(0).rstrip(".,;")
            urls.add(nlp.domain_of(u))
            add("url", u, u.lower().rstrip("/"), m.start(), domain=nlp.domain_of(u))
        for m in nlp.BARE_DOMAIN_RE.finditer(text):
            d = nlp.domain_of(m.group(0))
            pre = text[max(0, m.start() - 1):m.start()]
            if d not in urls and pre not in ("@", ".", "/") and not nlp.EMAIL_RE.search(text[max(0, m.start() - 40):m.end()]):
                urls.add(d)
                add("url", m.group(0).rstrip(".,;"), m.group(0).lower().rstrip(".,;/"), m.start(), domain=d)
        for m in nlp.IPV4_RE.finditer(text):
            add("ip", m.group(0), m.group(0), m.start())
        masked = set()
        for rx, t in ((nlp.TXN_RE, "txn_ref"), (nlp.ORDER_RE, "order_id"), (nlp.INVOICE_RE, "invoice_no"),
                      (nlp.TRACKING_RE, "tracking"), (nlp.ACCOUNT_RE, "account"), (nlp.TICKET_RE, "ticket")):
            for m in rx.finditer(text):
                v = m.group(1).strip()
                if t == "txn_ref" and not re.search(r"\d", v):
                    continue
                masked.update(re.sub(r"\D", "", v)[-10:] for _ in [0])
                add(t, v, v.upper().lstrip("#"), m.start(), label=m.group(0).split(v)[0].strip(" :#-"))
        dates_spans = [(st, st + len(raw)) for raw, st in nlp.find_dates(text)]
        for m in nlp.PHONE_RE.finditer(text):
            if any(a <= m.start() < b for a, b in dates_spans):
                continue
            n = nlp.normalize_phone(m.group(0))
            if not n or n in masked or nlp.IPV4_RE.search(m.group(0)):
                continue
            pre = text[max(0, m.start() - 25):m.start()].lower()
            if re.search(r"(?:utr|ref|txn|order|invoice|awb|tracking|a/c|account|id|no\.?)\W*$", pre):
                continue
            add("phone", m.group(0).strip(), n, m.start())
        for m in nlp.HANDLE_RE.finditer(text):
            add("username", "@" + m.group(1), m.group(1).lower(), m.start())
        for a in nlp.find_amounts(text):
            if any(f.type == "amount" and f.extra.get("amount") == a["value"] for f in out):
                continue
            ctx = text[max(0, a["start"] - 60):a["start"] + 30]
            add("amount", a["raw"], f"{a['currency']} {a['value']}", a["start"], "", _role_from_label("", ctx),
                currency=a["currency"], amount=a["value"])
        for m in nlp.QTY_RE.finditer(text):
            if not any(f.type == "quantity" and f.value == m.group(1) for f in out):
                add("quantity", m.group(1), m.group(1), m.start(), m.group(0), _role_from_label(m.group(0), text[max(0, m.start() - 40):m.start()]))
        for m in nlp.QTY_UNITS_RE.finditer(text):
            if not any(f.type == "quantity" and f.value == m.group(1) for f in out):
                ctx = text[max(0, m.start() - 50):m.end() + 10]
                add("quantity", m.group(1), m.group(1), m.start(), "", _role_from_label("", ctx))
        if not any(f.type == "device" for f in out):
            for m in nlp.DEVICE_RE.finditer(text):
                add("device", m.group(1).strip(), m.group(1).strip().lower(), m.start())
                break
        # Participants of messages / emails.
        if s.kind == "email_header":
            for role in ("from", "to"):
                for p in s.data.get(role, []):
                    if p.get("name"):
                        add("person", p["name"], p["name"].lower(), text.find(p["name"]), role, email=p.get("address", "").lower())
        if s.author and s.kind in ("message", "system"):
            a = s.author.strip()
            if nlp.normalize_phone(a) and not re.search(r"[A-Za-z]", a):
                add("phone", a, nlp.normalize_phone(a), 0, "sender", chat_author=True)
            else:
                add("person", a, a.lower(), 0, "sender", chat_author=True)
        # Optional statistical NER (spaCy) for names/orgs/places in narrative text.
        if s.kind in ("paragraph", "page", "transcript", "email_body", "message") and len(text) > 30:
            model = get_nlp()
            if model is not None:
                doc = model(text[:5000])
                for ent in doc.ents:
                    val = ent.text.strip()
                    if ent.label_ == "PERSON" and len(val.split()) >= 2 and val[0].isupper() and not re.search(r"\d|@|:", val):
                        add("person", val, val.lower(), ent.start_char, "", "", ner=True, confidence=0.6)
                    elif ent.label_ == "GPE" and val[0].isupper() and len(val) > 2:
                        add("location", val, val.lower(), ent.start_char, "", "", ner=True, confidence=0.6)
        return out

    # -------------------------------------------------------------- views
    def segments_of(self, evidence_id: str) -> list[Seg]:
        return [s for s in self.segments if s.evidence_id == evidence_id]

    def search(self, rx: re.Pattern) -> list[Seg]:
        return [s for s in self.segments if rx.search(s.text)]
