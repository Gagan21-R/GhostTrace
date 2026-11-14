"""Pipeline step: OCR / parsed text -> Naive Bayes label, for whole items and for individual messages."""
from __future__ import annotations

from collections import Counter

from sqlalchemy import delete
from sqlalchemy.orm import Session

from ..models import MessageClassification
from . import naive_bayes as nb
from .index import CaseIndex

TEXT_TYPES = {"image", "chat", "email", "pdf", "docx", "text", "audio", "video", "html"}
MESSAGE_KINDS = {"message", "ocr_line", "email_body", "transcript", "paragraph", "page"}


def run_case(db: Session, idx: CaseIndex) -> dict:
    db.execute(delete(MessageClassification).where(MessageClassification.case_id == idx.case_id))
    counts, flagged = Counter(), 0
    for e in idx.evidence.values():
        if e.detected_type not in TEXT_TYPES:
            continue
        segs = idx.segments_of(e.id)
        doc = " ".join(s.text for s in segs if s.kind not in ("email_header", "system"))[:6000]
        if len(doc.split()) >= 3:
            r = nb.classify(doc)
            db.add(MessageClassification(case_id=idx.case_id, evidence_id=e.id, scope="document", locator="whole item", text=doc[:400],
                                         label=r["label"], confidence=r["confidence"], uncertain=r["uncertain"],
                                         probabilities=r["probabilities"], top_terms=r["top_terms"]))
            counts[r["label"]] += 1
        for s in segs:
            if s.kind not in MESSAGE_KINDS or len(s.text.split()) < 4 or len(s.text) > 600:
                continue
            r = nb.classify(s.text)
            if r["label"] == "benign" or r["uncertain"]:
                continue
            flagged += 1
            db.add(MessageClassification(case_id=idx.case_id, evidence_id=e.id, segment_id=s.id, scope="message", locator=s.locator,
                                         author=s.author, text=s.text[:600], label=r["label"], confidence=r["confidence"],
                                         uncertain=False, probabilities=r["probabilities"], top_terms=r["top_terms"]))
    db.flush()
    return {"items_classified": sum(counts.values()), "by_label": dict(counts), "messages_flagged": flagged,
            "model": "multinomial naive bayes", "_mode": "deterministic-ml"}
