"""Entity Intelligence + Relationship agents (deterministic core).

Observed relationships come directly from a record (an email header, a chat author sharing
a number). Inferred associations (e.g. the same phone number used under two names) are
stored with basis="inferred" and an explicit caveat - they never assert identity."""
from __future__ import annotations

from collections import defaultdict
from itertools import combinations

from sqlalchemy import delete
from sqlalchemy.orm import Session

from ..models import Entity, EntityMention, Relationship
from .index import CaseIndex

FACT_TO_ENTITY = {"person": "person", "organisation": "organisation", "email": "email", "phone": "phone",
                  "url": "website", "username": "username", "account": "account", "txn_ref": "transaction",
                  "order_id": "order", "invoice_no": "document_ref", "tracking": "shipment", "ip": "ip_address",
                  "device": "device", "location": "location", "ticket": "document_ref", "upi": "upi_id"}


def _entity_key(f) -> tuple[str, str]:
    etype = FACT_TO_ENTITY[f.type]
    norm = f.extra.get("domain") if f.type == "url" else f.norm
    return etype, norm


def build_entities(db: Session, idx: CaseIndex) -> dict:
    case_id = idx.case_id
    db.execute(delete(Relationship).where(Relationship.case_id == case_id))
    db.execute(delete(EntityMention).where(EntityMention.case_id == case_id))
    db.execute(delete(Entity).where(Entity.case_id == case_id))
    db.flush()

    entities: dict[tuple[str, str], Entity] = {}
    seg_entities: dict[str, set[tuple[str, str]]] = defaultdict(set)
    mentions = 0
    for f in idx.facts:
        if f.type not in FACT_TO_ENTITY:
            continue
        key = _entity_key(f)
        if not key[1]:
            continue
        ent = entities.get(key)
        conf = float(f.extra.get("confidence", idx.seg_by_id[f.segment_id].confidence))
        if ent is None:
            ent = Entity(case_id=case_id, type=key[0], value=f.extra.get("domain") or f.value if f.type == "url" else f.value,
                         normalized=key[1], confidence=conf, attributes={"urls": [], "sources": [], "labels": []})
            db.add(ent)
            entities[key] = ent
        else:
            ent.confidence = max(ent.confidence, conf)
        attrs = dict(ent.attributes)
        if f.type == "url" and f.value not in attrs["urls"]:
            attrs["urls"] = attrs["urls"] + [f.value]
        if f.evidence_id not in attrs["sources"]:
            attrs["sources"] = attrs["sources"] + [f.evidence_id]
        if f.label and f.label not in attrs["labels"]:
            attrs["labels"] = attrs["labels"] + [f.label]
        if f.extra.get("chat_author"):
            attrs["chat_display_name"] = True
        if f.extra.get("ner"):
            attrs["ner"] = True
        ent.attributes = attrs
        db.flush()
        db.add(EntityMention(case_id=case_id, entity_id=ent.id, evidence_id=f.evidence_id, segment_id=f.segment_id,
                             snippet=f.excerpt, method=idx.seg_by_id[f.segment_id].method if not f.extra.get("ner") else "spacy-ner",
                             confidence=conf))
        seg_entities[f.segment_id].add(key)
        mentions += 1

    # ---------------------------------------------------------------- relationships
    rels: dict[tuple, dict] = {}

    def link(a, b, rtype, basis, seg_id, desc, conf=1.0):
        if a == b or a not in entities or b not in entities:
            return
        k = (a, b, rtype) if rtype in ("emailed", "sent_by") else (tuple(sorted([a, b])) + (rtype,))
        r = rels.setdefault(k, {"a": k[0], "b": k[1], "type": rtype, "basis": basis, "segs": [], "evs": set(),
                                "desc": desc, "conf": conf})
        if seg_id not in r["segs"]:
            r["segs"].append(seg_id)
            r["evs"].add(idx.seg_by_id[seg_id].evidence_id)

    for s in idx.segments:
        keys = seg_entities.get(s.id, set())
        if s.kind == "email_header":
            frm = [("email", p["address"].lower()) for p in s.data.get("from", [])]
            to = [("email", p["address"].lower()) for p in s.data.get("to", [])]
            for a in frm:
                for b in to:
                    link(a, b, "emailed", "observed", s.id, "Email header From → To")
            for role in ("from", "to"):
                for p in s.data.get(role, []):
                    if p.get("name"):
                        link(("person", p["name"].lower()), ("email", p["address"].lower()), "uses_identifier", "observed",
                             s.id, "Display name and address appear together in an email header (display names are sender-controlled)", 0.8)
            continue
        author_key = None
        if s.author and s.kind == "message":
            for k in keys:
                if k[0] in ("person", "phone") and (k[1] == s.author.strip().lower() or k[1] in s.author.replace(" ", "")):
                    author_key = k
        for a, b in combinations(sorted(keys), 2):
            if author_key in (a, b):
                other = b if a == author_key else a
                if other[0] in ("person",):
                    continue
                link(author_key, other, "shared_by_author", "observed", s.id,
                     "Identifier appears in a message authored by this chat participant")
            else:
                link(a, b, "co_mentioned", "observed", s.id, "Mentioned together in the same record segment", 0.6)

    # Chat participants who exchanged messages in the same conversation.
    by_ev = defaultdict(set)
    for s in idx.segments:
        if s.kind == "message" and s.author:
            for k in seg_entities.get(s.id, set()):
                if k[1] == s.author.strip().lower() or (k[0] == "phone" and k[1] in s.author.replace(" ", "")):
                    by_ev[s.evidence_id].add((k, s.id))
    for ev_id, parts in by_ev.items():
        uniq = {}
        for k, sid in parts:
            uniq.setdefault(k, sid)
        for (a, sa), (b, sb) in combinations(sorted(uniq.items()), 2):
            link(a, b, "communicated_with", "observed", sa, "Participants in the same conversation export")

    # Inferred: the same identifier associated with different names across records.
    ident_people = defaultdict(set)
    for r in list(rels.values()):
        if r["type"] in ("shared_by_author", "uses_identifier"):
            p, i = (r["a"], r["b"]) if r["a"][0] == "person" else (r["b"], r["a"])
            if p[0] == "person" and i[0] in ("phone", "email", "account", "username"):
                ident_people[i].add((p, r["segs"][0]))
    for ident, people in ident_people.items():
        plist = sorted(people)
        for (p1, s1), (p2, s2) in combinations(plist, 2):
            if p1 != p2:
                link(p1, p2, "possible_association", "inferred", s1,
                     f"Both names are associated with the same {ident[0]} ({entities[ident].value}). A shared identifier "
                     f"does NOT establish that they are the same person.", 0.4)
                rels[tuple(sorted([p1, p2])) + ("possible_association",)]["segs"].append(s2)

    count = 0
    for r in rels.values():
        a, b = entities[r["a"]], entities[r["b"]]
        db.add(Relationship(case_id=case_id, source_entity_id=a.id, target_entity_id=b.id, rel_type=r["type"],
                            basis=r["basis"], weight=float(len(r["segs"])), evidence_ids=sorted(r["evs"]),
                            segment_ids=r["segs"], description=r["desc"], confidence=r["conf"]))
        count += 1
    db.flush()
    by_type = defaultdict(int)
    for (t, _), _e in entities.items():
        by_type[t] += 1
    return {"entities": len(entities), "mentions": mentions, "relationships": count, "by_type": dict(by_type)}
