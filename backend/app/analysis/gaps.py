"""Evidence Gap agent: identifies missing or incomplete records and produces a checklist of
what would resolve each gap. A gap never implies wrongdoing - it marks what is unknown."""
from __future__ import annotations

import re
from collections import defaultdict

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from ..models import EvidenceGap, TimelineEvent
from . import nlp
from .index import CaseIndex

FIN_RECORD_RX = re.compile(r"\b(?:debited|credited|statement|utr|rrn|transaction (?:id|ref)|a/c|account no)\b", re.I)
STATEMENT_CATS = ("statement", "complaint", "testimony", "interview")
SOCIAL_RX = re.compile(r"(?:twitter|x|instagram|facebook|reddit|tiktok|youtube|threads|linkedin|t\.me|telegram|socialhub)\.", re.I)


WHY = {
    "missing_payment_confirmation": "Without a bank or provider record, the amount, date and recipient of the payment rest on screenshots or statements that could be incomplete or altered.",
    "incomplete_conversation": "Missing messages can change the meaning of what remains; conclusions drawn from a partial thread may be wrong.",
    "missing_attachment": "The attachment may contain the decisive content (a payment QR, a photo, a form) that the surrounding messages only refer to.",
    "unverified_sender": "Display names and From headers can be forged; without routing and authentication data the true sender cannot be established.",
    "missing_original": "A screenshot shows how a record looked to one person; the native record carries metadata and can be verified at source.",
    "missing_delivery_confirmation": "Delivery claims from either party cannot be tested without the courier's own proof-of-delivery record.",
    "refund_unconfirmed": "A promise to refund is not evidence that a refund was made; only a financial record can show that.",
    "incomplete_login_records": "Account events outside the collected log window cannot be attributed to a session, device or time with confidence.",
    "uncorroborated_claim": "A claim supported only by the person making it carries less weight until an independent record confirms it.",
    "missing_timestamps": "Events without time information cannot be ordered, so cause and effect between them cannot be assessed.",
    "ambiguous_timestamps": "If day and month are swapped the order of events may be reversed.",
    "collection_info_missing": "Without who/when/how it was collected, the item's provenance cannot be explained to a reviewer or a court.",
    "content_not_preserved": "Online content can be deleted at any time; once gone it can only be recovered through the platform via proper legal channels.",
    "undocumented_access_change": "Without a ticket, approver or reason, the purpose of the change cannot be determined from the records.",
}


def detect(db: Session, idx: CaseIndex) -> dict:
    db.execute(delete(EvidenceGap).where(EvidenceGap.case_id == idx.case_id))
    gaps: list[dict] = []

    def add(category, key, desc, related, checklist, severity="medium"):
        if any(g["category"] == category and g["key"] == key for g in gaps):
            return
        gaps.append(dict(category=category, key=key, description=desc, related=related[:8], checklist=checklist,
                         severity=severity))

    def is_statement(ev_id):
        e = idx.ev(ev_id)
        return any(c in (e.category or "").lower() for c in STATEMENT_CATS) or "statement" in e.original_filename.lower()

    def is_fin_record(ev_id):
        e = idx.ev(ev_id)
        if is_statement(ev_id) or e.detected_type == "chat":
            return False
        cat = (e.category or "").lower()
        if any(c in cat for c in ("bank", "payment", "financial", "transaction", "receipt")):
            return True
        return any(FIN_RECORD_RX.search(s.text) for s in idx.segments_of(ev_id))

    # G1 payment not confirmed by a financial record
    paid = [f for f in idx.facts_of("amount") if f.role in ("paid",)]
    by_amt = defaultdict(list)
    for f in paid:
        by_amt[f.extra.get("amount")].append(f)
    for amt, fs in by_amt.items():
        records = [f for f in fs if is_fin_record(f.evidence_id) and idx.ev(f.evidence_id).detected_type != "image"]
        screenshots = [f for f in fs if idx.ev(f.evidence_id).detected_type == "image"]
        if not records:
            add("missing_payment_confirmation", f"amount {amt}",
                f"A payment of {fs[0].value} is described" + (" only in screenshots/messages" if screenshots else "")
                + " but no bank or payment-provider record confirms it.",
                [idx.ref(idx.seg_by_id[f.segment_id], f.excerpt) for f in fs],
                ["Bank account statement covering the payment date", "Payment provider transaction detail (UTR/RRN)",
                 "Beneficiary account / UPI ID verification from the bank"], "high")

    # G2 incomplete chat exports / G3 missing attachments
    for e in idx.evidence.values():
        if e.detected_type != "chat":
            continue
        segs = idx.segments_of(e.id)
        meta = e.file_metadata or {}
        info = meta.get("export_info") or {}
        reasons = []
        if info.get("complete") is False:
            reasons.append("the export declares itself incomplete" + (f" ({info.get('note')})" if info.get("note") else ""))
        if isinstance(info.get("total_messages"), int) and info["total_messages"] > len(segs):
            reasons.append(f"{info['total_messages']} messages are declared but only {len(segs)} are present")
        ids = [int(s.data.get("message_id")) for s in segs if str(s.data.get("message_id", "")).isdigit()]
        if ids:
            missing = sorted(set(range(min(ids), max(ids) + 1)) - set(ids))
            if missing:
                reasons.append(f"message IDs are non-contiguous (missing {len(missing)}: {', '.join(map(str, missing[:8]))}"
                               f"{'…' if len(missing) > 8 else ''})")
        deleted = [s for s in segs if s.data.get("deleted") or re.search(r"this message was deleted", s.text, re.I)]
        if deleted:
            reasons.append(f"{len(deleted)} message(s) show as deleted")
        if reasons:
            add("incomplete_conversation", e.id, f"Chat export {e.original_filename} appears incomplete: " + "; ".join(reasons) + ".",
                [idx.ref(s) for s in (deleted or segs[:1])],
                ["Full conversation export from the account holder's device (with media)",
                 "Platform data download / lawful request for the full thread",
                 "Screenshots covering the missing ranges with visible timestamps"], "high")
        for s in segs:
            atts = s.data.get("attachments") or []
            missing_atts = [a for a in atts if isinstance(a, dict) and a.get("included") is False]
            if s.data.get("media_omitted") or missing_atts:
                names = ", ".join(a.get("name", "?") for a in missing_atts) or "media"
                add("missing_attachment", f"{e.id}:{s.locator}",
                    f"{e.original_filename} {s.locator} references an attachment ({names}) that is not included in the export.",
                    [idx.ref(s)], ["Original media file from the sender's/recipient's device",
                                   "Re-export the chat with media included"], "medium")
    for e in idx.evidence.values():
        if e.detected_type != "email":
            continue
        segs = idx.segments_of(e.id)
        hdr = next((s for s in segs if s.kind == "email_header"), None)
        body = next((s for s in segs if s.kind == "email_body"), None)
        if body and re.search(r"\b(?:attached|attachment|enclosed|see the file)\b", body.text, re.I) and not (body.data.get("attachments")):
            add("missing_attachment", f"{e.id}:body", f"Email {e.original_filename} refers to an attachment, but none is present in the file.",
                [idx.ref(body)], ["Original email with attachments from the mailbox (EML/MSG export)"], "medium")
        # G4 unverified sender
        if hdr:
            d = hdr.data
            frm = (d.get("from") or [{}])[0].get("address", "")
            fd = frm.split("@")[-1].lower() if frm else ""
            reasons = []
            if not d.get("authentication_results"):
                reasons.append("no Authentication-Results (SPF/DKIM/DMARC) header")
            if not d.get("received"):
                reasons.append("no Received routing headers")
            rt = d.get("reply_to") or ""
            if rt and fd and fd not in rt.lower():
                reasons.append(f"Reply-To ({rt}) uses a different domain from the From address ({fd})")
            rp = d.get("return_path") or ""
            if rp and fd and fd not in rp.lower():
                reasons.append(f"Return-Path ({rp}) differs from the From domain")
            if reasons:
                add("unverified_sender", e.id, f"Sender of {e.original_filename} ({frm or 'unknown'}) cannot be verified: " + "; ".join(reasons) + ".",
                    [idx.ref(hdr)], ["Full original message headers from the recipient's mail server",
                                     "Mail provider's SPF/DKIM/DMARC evaluation for this message",
                                     "Domain registration/hosting information for the sender domain"], "medium")

    # G5 screenshot-only evidence of an email/chat/receipt (no native original)
    native_types = {e.detected_type for e in idx.evidence.values()}
    for e in idx.evidence.values():
        if e.detected_type != "image":
            continue
        text = " ".join(s.text for s in idx.segments_of(e.id))
        kind = None
        if re.search(r"\bFrom:.*\bSubject:|\bSubject:.*\bFrom:", text, re.I | re.S) and "email" not in native_types:
            kind = "email"
        elif re.search(r"\b(?:UTR|UPI Ref|Transaction ID|Payment successful|Paid to)\b", text, re.I):
            ids = {f.norm for f in idx.facts if f.evidence_id == e.id and f.type == "txn_ref"}
            confirmed = any(f.norm in ids and f.evidence_id != e.id and is_fin_record(f.evidence_id) and idx.ev(f.evidence_id).detected_type != "image"
                            for f in idx.facts_of("txn_ref"))
            if not confirmed:
                kind = "payment receipt"
        if kind:
            add("missing_original", e.id, f"{e.original_filename} is a screenshot of a {kind}; the native original record is not in the case.",
                [idx.ref(s) for s in idx.segments_of(e.id)[:2]],
                [f"Native {kind} record from the source system" + (" (EML with full headers)" if kind == "email" else ""),
                 "Collector's note of when/how the screenshot was captured"], "medium")

    events = list(db.scalars(select(TimelineEvent).where(TimelineEvent.case_id == idx.case_id)))

    # G6 orders with no delivery confirmation / G10 refund promised but not evidenced
    orders = defaultdict(list)
    for f in idx.facts_of("order_id"):
        orders[f.norm].append(f)
    deliveries = [e for e in events if e.event_type == "delivery"]
    for oid, fs in orders.items():
        segs_with = {f.segment_id for f in fs}
        evs_with = {f.evidence_id for f in fs}
        delivered = [e for e in deliveries if e.segment_id in segs_with or e.evidence_id in evs_with]
        official = [e for e in delivered if idx.ev(e.evidence_id).detected_type in ("spreadsheet", "pdf", "email")
                    and not is_statement(e.evidence_id)]
        if not official:
            add("missing_delivery_confirmation", oid,
                f"No courier/system record confirms delivery for order {fs[0].value}" +
                (" (delivery is only mentioned in messages/statements)." if delivered else "."),
                [idx.ref(idx.seg_by_id[f.segment_id], f.excerpt) for f in fs],
                ["Courier proof-of-delivery (POD) with recipient signature/photo", "Courier tracking history export",
                 "Seller dispatch manifest (quantity and weight)"], "high")
    promise_rx = re.compile(r"\b(?:will|shall|would|going to)\b.{0,40}\brefund|refund (?:will be|is being) (?:processed|initiated|issued)|refund within", re.I)
    promises = [s for s in idx.segments if promise_rx.search(s.text)]
    refund_records = [s for s in idx.segments if re.search(r"refund (?:credited|processed successfully|completed)|refunded to", s.text, re.I)
                      and idx.ev(s.evidence_id).detected_type in ("spreadsheet", "pdf", "email") ]
    if promises and not refund_records:
        add("refund_unconfirmed", "refund", "A refund is promised but no record shows that a refund was processed or received.",
            [idx.ref(s) for s in promises], ["Bank statement showing the refund credit", "Seller/marketplace refund transaction ID",
                                             "Written refund commitment with amount and deadline"], "high")

    # G7 incomplete login/session records
    alerts = [e for e in events if e.event_type in ("security_alert", "login", "password_reset", "recovery_change") and e.occurred_at]
    log_rows = [e for e in events if e.data and e.data.get("channel") == "log" and e.occurred_at]
    log_evs = {e.evidence_id for e in log_rows if e.event_type in ("login", "security_alert", "password_reset", "recovery_change", "mfa")}
    if alerts and not log_evs:
        add("incomplete_login_records", "no-log", "Account-activity alerts exist but no provider session/login log has been collected.",
            [idx.ref(idx.seg_by_id[e.segment_id]) for e in alerts[:4] if e.segment_id in idx.seg_by_id],
            ["Provider security/session log export (all sessions with IP, user agent, timestamps)",
             "Recovery-settings change history", "Device list linked to the account"], "high")
    elif alerts and log_evs:
        rows = [e for e in log_rows if e.evidence_id in log_evs]
        lo, hi = min(e.occurred_at for e in rows), max(e.occurred_at for e in rows)
        uncovered = [e for e in alerts if e.evidence_id not in log_evs and not (lo <= e.occurred_at <= hi)]
        for ev_id in log_evs:
            info = (idx.ev(ev_id).file_metadata or {})
            note = " ".join(s.text for s in idx.segments_of(ev_id) if re.search(r"truncat|partial|export limited|showing first", s.text, re.I))
            if note:
                uncovered = uncovered or alerts[:1]
        if uncovered:
            add("incomplete_login_records", "coverage",
                f"{len(uncovered)} account-activity event(s) fall outside the time range covered by the collected session logs "
                f"({lo:%d %b %Y %H:%M} – {hi:%d %b %Y %H:%M}).",
                [idx.ref(idx.seg_by_id[e.segment_id]) for e in uncovered[:5] if e.segment_id in idx.seg_by_id],
                ["Complete session log for the full incident window", "Provider audit log of password and recovery changes"], "high")

    # G8 uncorroborated claims in statements
    record_types = defaultdict(set)
    for e in events:
        if not is_statement(e.evidence_id):
            record_types[e.event_type].add(e.evidence_id)
    for s in idx.segments:
        if not is_statement(s.evidence_id):
            continue
        for c in nlp.claims_in(s.text):
            if c["polarity"] == "positive" and not record_types.get(c["event_type"]):
                add("uncorroborated_claim", f"{s.evidence_id}:{c['event_type']}",
                    f"Statement claims a {c['event_type'].replace('_', ' ')} that no other record corroborates: \"{c['sentence'][:160]}\"",
                    [idx.ref(s, c["sentence"])], [f"An independent record of the {c['event_type'].replace('_', ' ')} "
                                                  "(system log, receipt, email, witness)"], "medium")

    # G9 events without timestamps
    undated = [e for e in events if e.timestamp_kind == "unknown"]
    if undated:
        add("missing_timestamps", "undated", f"{len(undated)} described event(s) have no time information and cannot be placed on the timeline.",
            [idx.ref(idx.seg_by_id[e.segment_id], e.title) for e in undated[:6] if e.segment_id in idx.seg_by_id],
            ["Source records that carry timestamps for these events", "Clarifying interview with the person who described them"], "low")
    ambiguous = [e for e in events if (e.data or {}).get("ambiguous_day_month")]
    if ambiguous:
        add("ambiguous_timestamps", "dd-mm", f"{len(ambiguous)} timestamp(s) use a numeric date where day and month are ambiguous (read as day-first).",
            [idx.ref(idx.seg_by_id[e.segment_id], e.timestamp_raw) for e in ambiguous[:5] if e.segment_id in idx.seg_by_id],
            ["Confirm the locale/date format of the exporting device or system"], "low")

    # G11 preservation: missing collection information / G12 at-risk URLs not captured
    for e in idx.evidence.values():
        if not (e.collection_source or "").strip() and not e.collected_at:
            add("collection_info_missing", e.id, f"{e.original_filename} has no recorded collection source or collection time.",
                [{"evidence_id": e.id, "evidence_code": e.evidence_code, "filename": e.original_filename,
                  "segment_id": None, "locator": "metadata", "excerpt": "collection_source empty"}],
                ["Record who collected the item, from which device/account, when, and how"], "medium")
    all_text_by_ev = {e.id: " ".join(s.text for s in idx.segments_of(e.id)).lower() for e in idx.evidence.values()}
    for f in idx.facts_of("url"):
        d = f.extra.get("domain", "")
        if not SOCIAL_RX.search(d + "."):
            continue
        tail = f.norm.split("/")[-1]
        captured = any(ev != f.evidence_id and tail and tail in txt and idx.ev(ev).detected_type in ("image", "spreadsheet", "pdf")
                       for ev, txt in all_text_by_ev.items())
        if not captured:
            add("content_not_preserved", f.norm, f"Online content at {f.value} is referenced but no capture (screenshot, archive or "
                "platform export) of that specific item is in the case. It may be deleted.",
                [idx.ref(idx.seg_by_id[f.segment_id], f.excerpt)],
                ["Full-page capture with visible URL and timestamp", "Web archive snapshot (e.g. archive service) with its ID",
                 "Platform preservation request through the appropriate legal channel"], "high")

    # G13 access changes without documented authorisation
    for e in events:
        if e.event_type != "access_change" or (e.data or {}).get("channel") != "log":
            continue
        seg = idx.seg_by_id.get(e.segment_id)
        if not seg:
            continue
        flds = seg.data.get("fields", {})
        approval = [k for k in flds if re.search(r"ticket|approv|reason|justification|request", k) and str(flds[k]).strip() not in ("", "-", "N/A", "None")]
        if not approval and re.search(r"revok|remov|downgrad|restrict|disabl", seg.text, re.I):
            add("undocumented_access_change", e.segment_id, f"Access change on {e.occurred_at:%d %b %Y} has no recorded ticket, approver or reason.",
                [idx.ref(seg)], ["Change ticket / approval record for this access change", "IAM audit log entry with approver identity",
                                 "Policy or review schedule that required the change"], "high")

    for i, g in enumerate(gaps, 1):
        db.add(EvidenceGap(case_id=idx.case_id, code=f"GAP-{i:03d}", why_it_matters=WHY.get(g["category"], ""), **g))
    db.flush()
    cats = defaultdict(int)
    for g in gaps:
        cats[g["category"]] += 1
    return {"gaps": len(gaps), "by_category": dict(cats)}
