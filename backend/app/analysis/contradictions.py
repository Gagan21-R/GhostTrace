"""Contradiction agent (deterministic rules).

A contradiction is only raised when two records are *linked* to the same subject (a shared
order ID, transaction, amount + date, or an entity) - the ``same_event_basis`` field says
why we believe they describe the same thing, and ``reason`` explains how they differ.
Records describing genuinely different events are therefore not reported as conflicts.
"""
from __future__ import annotations

import re
from collections import defaultdict
from datetime import timedelta, timezone

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from ..models import Contradiction, TimelineEvent
from . import nlp
from .index import CaseIndex, Fact

KEY_TYPES = ("order_id", "txn_ref", "invoice_no", "tracking")


DIRECT = {"transaction_reference_mismatch", "amount_conflict", "quantity_conflict", "integrity_mismatch"}


def classify(category: str, confidence: float) -> str:
    """direct: the same record/identifier carries incompatible values; contextual: a statement conflicts with a
    record; potential: the records may describe different events or the link is weaker."""
    if category in DIRECT and confidence >= 0.75:
        return "direct"
    if category == "statement_vs_record":
        return "contextual"
    return "potential"


HIGH_IMPACT = {"transaction_reference_mismatch", "amount_conflict", "quantity_conflict", "integrity_mismatch", "statement_vs_record"}


def priority_of(category: str, confidence: float) -> str:
    """Review priority: how much the conflict could change the investigation if confirmed."""
    if category in HIGH_IMPACT and confidence >= 0.75:
        return "high"
    if confidence >= 0.6 or category in HIGH_IMPACT:
        return "medium"
    return "low"


def _d(e) -> str:
    d = e.data or {}
    if d.get("precision") == "day":
        tz = nlp.tz_from_offset(d.get("display_offset")) or timezone.utc
        return e.occurred_at.astimezone(tz).strftime("%d %b %Y") + " (date only)"
    return nlp.display_dt(e.occurred_at, d)
SINGULAR_EVENTS = {"delivery", "refund", "access_change", "complaint", "password_reset", "order", "payment",
                   "recovery_change", "warning"}


def _side(idx: CaseIndex, f_or_seg_id, value, excerpt=None) -> dict:
    seg = idx.seg_by_id[f_or_seg_id]
    r = idx.ref(seg, excerpt)
    r["value"] = value
    return r


def _keys_for(idx: CaseIndex, f: Fact) -> set[tuple[str, str]]:
    same_seg = {(k.type, k.norm) for k in idx.facts if k.segment_id == f.segment_id and k.type in KEY_TYPES}
    if same_seg:
        return same_seg
    ev_keys = defaultdict(set)
    for k in idx.facts:
        if k.evidence_id == f.evidence_id and k.type in KEY_TYPES:
            ev_keys[k.type].add(k.norm)
    return {(t, next(iter(v))) for t, v in ev_keys.items() if len(v) == 1}


def detect(db: Session, idx: CaseIndex) -> dict:
    db.execute(delete(Contradiction).where(Contradiction.case_id == idx.case_id))
    found: list[dict] = []
    seen_pairs: set = set()

    def add(category, field, key, desc, a, b, reason, conf, basis, action):
        if category in ("transaction_reference_mismatch", "identifier_mismatch", "amount_conflict", "quantity_conflict"):
            # One finding per pair of conflicting values, however many records repeat them.
            pair = (category, field, key if category in ("amount_conflict", "quantity_conflict") else "", frozenset([str(a["value"]), str(b["value"])]))
        else:
            pair = (category, field, frozenset([f"{a['segment_id']}|{a['value']}", f"{b['segment_id']}|{b['value']}"]))
        if pair in seen_pairs or a["evidence_id"] == b["evidence_id"] and a["segment_id"] == b["segment_id"]:
            return
        seen_pairs.add(pair)
        found.append(dict(category=category, field=field, key=key, description=desc, source_a=a, source_b=b,
                          reason=reason, confidence=round(conf, 2), same_event_basis=basis, suggested_action=action))

    # ---------------------------------------------------------------- R1 amount conflicts per linked record
    amounts = [f for f in idx.facts_of("amount") if f.role in ("paid", "invoiced", "ordered")
               and (f.label == "" or re.search(r"total|amount|paid|debit|grand|payable|price", f.label + " " + f.role))]
    by_key = defaultdict(list)
    for f in amounts:
        for k in _keys_for(idx, f):
            by_key[k].append(f)
    for key, fs in by_key.items():
        # Use the largest labelled total per evidence item as that record's figure.
        per_ev: dict[str, Fact] = {}
        for f in fs:
            cur = per_ev.get(f.evidence_id)
            if cur is None or float(f.extra.get("amount", 0)) > float(cur.extra.get("amount", 0)):
                per_ev[f.evidence_id] = f
        items = list(per_ev.values())
        for i in range(len(items)):
            for j in range(i + 1, len(items)):
                a, b = items[i], items[j]
                if a.extra.get("amount") != b.extra.get("amount") and a.extra.get("currency") in (b.extra.get("currency"), "UNK") \
                        or (a.extra.get("amount") != b.extra.get("amount") and b.extra.get("currency") == "UNK"):
                    add("amount_conflict", "amount", f"{key[0]} {key[1]}",
                        f"Different amounts recorded for {key[0].replace('_', ' ')} {key[1]}: {a.value} vs {b.value}",
                        _side(idx, a.segment_id, a.value, a.excerpt), _side(idx, b.segment_id, b.value, b.excerpt),
                        f"'{a.label or a.role}' in {idx.ev(a.evidence_id).original_filename} differs from "
                        f"'{b.label or b.role}' in {idx.ev(b.evidence_id).original_filename}.",
                        0.85, f"Both records reference the same {key[0].replace('_', ' ')} ({key[1]}).",
                        "Obtain the bank/payment-gateway statement for this reference and the final invoice; confirm "
                        "whether a partial payment, fee, tax or a second transaction explains the difference.")

    # ---------------------------------------------------------------- R2 transaction reference mismatch
    pay = [f for f in idx.facts_of("amount") if f.role in ("paid", "credited", "")]
    txns = idx.facts_of("txn_ref")
    seg_txn = defaultdict(list)
    for t in txns:
        seg_txn[t.segment_id].append(t)
    pay_with_ref = []
    for f in pay:
        refs = seg_txn.get(f.segment_id) or [t for t in txns if t.evidence_id == f.evidence_id]
        if len({t.norm for t in refs}) == 1:
            pay_with_ref.append((f, refs[0]))
    for i in range(len(pay_with_ref)):
        for j in range(i + 1, len(pay_with_ref)):
            (fa, ta), (fb, tb) = pay_with_ref[i], pay_with_ref[j]
            if fa.evidence_id == fb.evidence_id or ta.norm == tb.norm:
                continue
            if fa.extra.get("amount") == fb.extra.get("amount"):
                d = nlp.levenshtein(ta.norm, tb.norm)
                close = d <= 3 and len(ta.norm) == len(tb.norm)
                add("transaction_reference_mismatch", "txn_ref", f"amount {fa.norm}",
                    f"Same payment amount ({fa.value}) carries different transaction references: {ta.value} vs {tb.value}",
                    _side(idx, ta.segment_id, ta.value, ta.excerpt), _side(idx, tb.segment_id, tb.value, tb.excerpt),
                    ("The references differ by only %d character(s) - possibly a transcription error or an altered "
                     "receipt." % d) if close else "Two different references are reported for a payment of the same amount.",
                    0.8 if close else 0.55,
                    f"Both records report a payment of {fa.value}; they may describe the same transfer or two separate transfers.",
                    "Request the bank's transaction detail for both references (UTR/RRN) and compare beneficiary, time and amount.")

    # ---------------------------------------------------------------- R3 quantity conflicts
    qtys = idx.facts_of("quantity")
    qkey = defaultdict(list)
    for q in qtys:
        for k in _keys_for(idx, q):
            qkey[k].append(q)
    for key, fs in qkey.items():
        ordered = [q for q in fs if q.role in ("ordered", "invoiced", "")]
        delivered = [q for q in fs if q.role in ("delivered", "shipped")]
        for d in delivered:
            for o in ordered:
                if o.evidence_id != d.evidence_id and o.value != d.value:
                    add("quantity_conflict", "quantity", f"{key[0]} {key[1]}",
                        f"Quantity for {key[1]}: {o.value} ({o.role or 'stated'}) vs {d.value} ({d.role})",
                        _side(idx, o.segment_id, o.value, o.excerpt), _side(idx, d.segment_id, d.value, d.excerpt),
                        "Ordered/invoiced quantity does not match the delivered/received quantity.", 0.85,
                        f"Both records reference {key[0].replace('_', ' ')} {key[1]}.",
                        "Obtain the courier's weight/package manifest and proof-of-delivery; compare with product photographs.")
                    break

    # ---------------------------------------------------------------- R4 near-duplicate identifiers
    for t in ("order_id", "txn_ref", "invoice_no", "tracking"):
        vals = defaultdict(list)
        for f in idx.facts_of(t):
            vals[f.norm].append(f)
        keys = sorted(vals)
        for i in range(len(keys)):
            for j in range(i + 1, len(keys)):
                a, b = keys[i], keys[j]
                if len(a) == len(b) and 1 <= nlp.levenshtein(a, b) <= 2 and len(a) >= 6:
                    fa, fb = vals[a][0], vals[b][0]
                    if t == "txn_ref" and any(c["category"] == "transaction_reference_mismatch" and
                                              {c["source_a"]["value"], c["source_b"]["value"]} == {fa.value, fb.value} for c in found):
                        continue
                    add("identifier_mismatch", t, f"{a} / {b}",
                        f"Near-identical {t.replace('_', ' ')}s: {fa.value} vs {fb.value}",
                        _side(idx, fa.segment_id, fa.value, fa.excerpt), _side(idx, fb.segment_id, fb.value, fb.excerpt),
                        f"The identifiers differ by {nlp.levenshtein(a, b)} character(s). They may be a typo for the same "
                        f"record, or two genuinely different records.", 0.6,
                        "Identifiers are near-duplicates of each other; same-record status is NOT established.",
                        "Confirm with the issuing party which identifier is correct and whether both exist.")

    # ---------------------------------------------------------------- R5 conflicting dates for the same event
    events = list(db.scalars(select(TimelineEvent).where(TimelineEvent.case_id == idx.case_id)))
    seg_keys = defaultdict(set)
    for f in idx.facts:
        if f.type in KEY_TYPES:
            seg_keys[f.segment_id].add((f.type, f.norm))
        elif f.type == "amount" and f.role in ("paid", "refund", "credited"):
            seg_keys[f.segment_id].add(("amount", f.extra.get("amount")))
        if f.type == "person":
            seg_keys[f.segment_id].add(("person", f.norm))
    for e in idx.evidence.values():  # emails: header participants apply to body sentences too
        segs = idx.segments_of(e.id)
        hdr = [s for s in segs if s.kind == "email_header"]
        if hdr:
            people = {k for k in seg_keys[hdr[0].id] if k[0] == "person"}
            for s in segs:
                seg_keys[s.id] |= people
    dated = [e for e in events if e.occurred_at and e.event_type in SINGULAR_EVENTS and e.timestamp_kind != "metadata_derived"]
    grant_rx = re.compile(r"\b(?:grant\w*|provision\w*|added|onboard\w*|enabled)\b", re.I)

    def polarity(e):
        return "grant" if grant_rx.search((e.description or "") + " " + e.title) and not re.search(r"revok|remov|downgrad|restrict|disabl|changed", e.description or "", re.I) else "change"

    for a in dated:
        best = None
        for b in dated:
            if b.evidence_id == a.evidence_id or b.event_type != a.event_type or b.id == a.id:
                continue
            if a.event_type == "access_change" and polarity(a) != polarity(b):
                continue
            shared = seg_keys[a.segment_id] & seg_keys[b.segment_id]
            strong = {k for k in shared if k[0] != "person"}
            if not strong and not (shared and a.event_type in ("access_change", "complaint", "warning", "password_reset", "recovery_change")):
                continue
            gap = abs(a.occurred_at - b.occurred_at)
            precision_day = (a.data or {}).get("precision") == "day" or (b.data or {}).get("precision") == "day"
            if precision_day:  # compare calendar dates in the reported local time
                tza = nlp.tz_from_offset((a.data or {}).get("display_offset")) or timezone.utc
                same = a.occurred_at.astimezone(tza).date() == b.occurred_at.astimezone(tza).date()
            else:
                same = gap < timedelta(hours=6)
            if same:
                best = None
                break  # a matching corroborating record exists - no conflict for this event
            if best is None or gap < best[1]:
                best = (b, gap, shared)
        if best:
            b, gap, shared = best
            pair_key = (a.event_type, frozenset([a.evidence_id, b.evidence_id]))
            if pair_key in seen_pairs:
                continue
            seen_pairs.add(pair_key)
            sa, sb = idx.seg_by_id.get(a.segment_id), idx.seg_by_id.get(b.segment_id)
            if not sa or not sb:
                continue
            for e_ in (a, b):
                e_.conflict = True
            add("date_conflict", "timestamp", ", ".join(f"{k[0]} {k[1]}" for k in sorted(shared)),
                f"Conflicting dates for the {a.event_type.replace('_', ' ')}: "
                f"{_d(a)} vs {_d(b)}",
                _side(idx, a.segment_id, a.timestamp_raw, a.description[:220]),
                _side(idx, b.segment_id, b.timestamp_raw, b.description[:220]),
                (f"The two records place the same {a.event_type.replace('_', ' ')} on different calendar dates "
                 f"(at least one record gives only a date)." if precision_day else
                 f"The two records place the same {a.event_type.replace('_', ' ')} {gap.days} day(s) {(gap.seconds // 3600)} hour(s) apart."), 0.7 if a.timestamp_kind == b.timestamp_kind == "source_reported" else 0.5,
                "Linked through shared " + ", ".join(sorted({k[0] for k in shared})) + "; both describe a "
                f"{a.event_type.replace('_', ' ')}. They could still be two distinct events.",
                "Obtain the system-of-record log (courier POD, bank statement, IAM audit log) for the event and its timezone.")

    # ---------------------------------------------------------------- R6 attribute conflicts at the same moment
    att_events = [e for e in events if e.occurred_at and e.event_type in ("login", "security_alert", "password_reset", "recovery_change")]
    seg_attr = defaultdict(dict)
    ev_attr = defaultdict(dict)
    for f in idx.facts_of("device", "location", "ip"):
        seg_attr[f.segment_id].setdefault(f.type, f)
        ev_attr[f.evidence_id].setdefault(f.type, f)

    def attrs(e):  # an email's attributes live in its body, its event in its header
        own = seg_attr.get(e.segment_id, {})
        if not own and idx.ev(e.evidence_id).detected_type == "email":
            return ev_attr.get(e.evidence_id, {})
        return own

    for i, a in enumerate(att_events):
        for b in att_events[i + 1:]:
            if a.evidence_id == b.evidence_id or abs(a.occurred_at - b.occurred_at) > timedelta(minutes=10):
                continue
            fa, fb = attrs(a), attrs(b)
            if not fa or not fb:
                continue
            for attr in ("device", "location", "ip"):
                if attr in fa and attr in fb:
                    va, vb = fa[attr].norm, fb[attr].norm
                    same = va == vb or va in vb or vb in va or (attr == "location" and va.split(",")[0].strip() == vb.split(",")[0].strip())
                    if attr == "device":
                        osa, osb = (re.match(r"[a-z]+", va) or [""])[0], (re.match(r"[a-z]+", vb) or [""])[0]
                        same = same or (osa and osa == osb)
                    if not same:
                        add("attribute_conflict", attr, f"{a.occurred_at:%Y-%m-%d %H:%M}",
                            f"Different {attr} reported for activity at {_d(a)}: "
                            f"{fa[attr].value} vs {fb[attr].value}",
                            _side(idx, fa[attr].segment_id, fa[attr].value, fa[attr].excerpt),
                            _side(idx, fb[attr].segment_id, fb[attr].value, fb[attr].excerpt),
                            f"Two records describing activity within 10 minutes disagree on the {attr}. Device and "
                            "location strings in alerts are provider estimates and do not identify a person.", 0.65,
                            "Events occur within 10 minutes of each other on related account-activity records.",
                            "Export the provider's full session/audit log with user-agent strings and IP addresses for this window.")

    # ---------------------------------------------------------------- R7 integrity: recorded hash vs intake hash
    hex_re = re.compile(r"\b[a-fA-F0-9]{64}\b")
    by_name = {e.original_filename.lower(): e for e in idx.evidence.values()}
    for s in idx.segments:
        for m in hex_re.finditer(s.text):
            window = (s.text if s.kind == "row" else s.text[max(0, m.start() - 160):m.end() + 160]).lower()
            for name, e in by_name.items():
                if name in window and e.id != s.evidence_id and m.group(0).lower() != e.sha256:
                    a = idx.ref(s, s.text[max(0, m.start() - 100):m.end()])
                    a["value"] = m.group(0).lower()
                    first = idx.segments_of(e.id)
                    b = {"evidence_id": e.id, "evidence_code": e.evidence_code, "filename": e.original_filename,
                         "segment_id": first[0].id if first else None, "locator": "intake hash", "excerpt": f"SHA-256 at intake: {e.sha256}",
                         "value": e.sha256}
                    add("integrity_mismatch", "sha256", e.original_filename,
                        f"Recorded hash for {e.original_filename} does not match the file received at intake",
                        a, b, "The collection record lists a different SHA-256 than the file now in the vault. Either the "
                        "file was modified after collection, a different version was uploaded, or the log is wrong.",
                        0.9, "The collection record names this exact file.",
                        "Retrieve the originally collected copy from the collector's device/storage and re-hash it.")

    # ---------------------------------------------------------------- R8 statement vs the same person's own record
    act_rx = {"mfa": re.compile(r"\b\d{4,8}\b"),
              "payment": re.compile(r"\b(?:paid|sent|transferred)\b", re.I),
              "password_reset": re.compile(r"\b(?:reset|changed)\b.{0,20}password|password.{0,20}\b(?:reset|changed)\b", re.I),
              "login": re.compile(r"\b(?:logged|signed) in\b", re.I)}
    stmt_rx = re.compile(r"(?:statement of|statement by|name|declarant)\s*[:\-]\s*([A-Z][\w.'-]+(?:\s[A-Z][\w.'-]+){0,3})", re.I)
    for e in idx.evidence.values():
        if "statement" not in (e.category or "").lower() and "statement" not in e.original_filename.lower():
            continue
        segs = idx.segments_of(e.id)
        m = next((stmt_rx.search(s.text) for s in segs if stmt_rx.search(s.text)), None)
        if not m:
            continue
        who = m.group(1).strip().lower()
        for s in segs:
            for c in nlp.claims_in(s.text):
                if c["polarity"] != "negative" or c["event_type"] not in act_rx:
                    continue
                for r in idx.segments:
                    if r.evidence_id == e.id or not r.author or r.author.strip().lower() != who:
                        continue
                    if (nlp.classify_event(r.text) == c["event_type"] and not nlp.NEGATION_RE.search(r.text)
                            and act_rx[c["event_type"]].search(r.text)):
                        add("statement_vs_record", "statement", who,
                            f"{m.group(1).strip()}'s statement denies a {c['event_type'].replace('_', ' ')}, but a message "
                            f"they authored describes one",
                            idx.ref(s, c["sentence"]) | {"value": c["sentence"][:120]},
                            idx.ref(r) | {"value": r.text[:120]},
                            "The statement's denial conflicts with a record attributed to the same person. Display names in "
                            "exports can be spoofed, so authorship should be confirmed.", 0.75,
                            "The record's author name matches the person who made the statement.",
                            "Clarify with the declarant; obtain the original device export to confirm authorship of the message.")
                        break

    for c in found:
        c["priority"] = priority_of(c["category"], c["confidence"])
    order = {"high": 0, "medium": 1, "low": 2}
    found.sort(key=lambda c: (order[c["priority"]], -c["confidence"]))
    from .. import replay
    for i, c in enumerate(found, 1):
        c["classification"] = classify(c["category"], c["confidence"])
        row = Contradiction(case_id=idx.case_id, code=f"CX-{i:03d}", **c)
        db.add(row)
        db.flush()
        replay.emit(db, idx.case_id, "contradiction.discovered", component="contradiction", actor="contradiction rules",
                    inputs=[replay.ref("segment", c["source_a"].get("segment_id"), f"{c['source_a'].get('evidence_code')} {c['source_a'].get('locator')}"),
                            replay.ref("segment", c["source_b"].get("segment_id"), f"{c['source_b'].get('evidence_code')} {c['source_b'].get('locator')}")],
                    outputs=[replay.ref("contradiction", row.id, row.code)], summary=f"{row.code}: {c['description']}")
    db.flush()
    cats = defaultdict(int)
    for c in found:
        cats[c["category"]] += 1
    return {"contradictions": len(found), "by_category": dict(cats)}
