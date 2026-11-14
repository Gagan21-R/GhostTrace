"""Timeline agent: builds a chronological event list and labels the provenance of every timestamp.

timestamp_kind:
  source_reported   - stated inside the record (email Date header, chat message time, log row, text)
  metadata_derived  - from file metadata (EXIF, PDF/DOCX properties)
  estimated         - resolved from a relative phrase ("yesterday") against a known anchor
  unknown           - an event is described but no time information exists
"""
from __future__ import annotations

import re

from sqlalchemy import delete
from sqlalchemy.orm import Session

from ..models import Entity, EntityMention, TimelineEvent
from . import nlp
from .index import CaseIndex, Seg

SPOKEN_DATE = re.compile(r"\b(\d{1,2})(?:st|nd|rd|th)?(?:\s+of)?\s+(January|February|March|April|May|June|July|August|September|October|"
                         r"November|December)\b(?:[^.\d]{0,25}?(\d{1,2})[:.](\d{2})\s*(am|pm|a\.m\.|p\.m\.)?)?", re.I)


def ocr_spacing(t: str) -> str:
    """OCR often drops spaces ("Paid on03May2026,19:05"); re-insert them at digit/letter boundaries before reading dates."""
    t = re.sub(r"(?<=\d)(?=[A-Za-z])|(?<=[a-z])(?=\d)|(?<=[a-z])(?=[A-Z][a-z])", " ", t)
    return re.sub(r",(?=\d{1,2}:\d{2})", ", ", t)


ROW_TITLE_KEYS = ("event", "activity", "action", "description", "status", "details", "type", "message", "change")


def _sentence_around(text: str, pos: int) -> str:
    start = max(text.rfind(".", 0, pos), text.rfind("\n", 0, pos)) + 1
    end_candidates = [i for i in (text.find(".", pos), text.find("\n", pos)) if i != -1]
    end = min(end_candidates) if end_candidates else len(text)
    return text[start:end + 1].strip()[:300]


def _mk(seg: Seg, dt, info, kind, etype, title, desc, actors=None, extra=None) -> dict:
    data = {k: v for k, v in (info or {}).items() if k != "raw"}
    data["source_confidence"] = seg.confidence
    if extra:
        data.update(extra)
    return {"segment": seg, "occurred_at": dt, "timestamp_raw": (info or {}).get("raw"), "timestamp_kind": kind,
            "event_type": etype, "title": title[:500], "description": desc[:2000], "actors": actors or [], "data": data}


def build_timeline(db: Session, idx: CaseIndex) -> dict:
    db.execute(delete(TimelineEvent).where(TimelineEvent.case_id == idx.case_id))
    db.flush()
    events: list[dict] = []
    for s in idx.segments:
        ev = idx.ev(s.evidence_id)
        if s.kind == "email_header":
            subj = s.data.get("subject") or "(no subject)"
            etype = nlp.classify_event(subj) or "email"
            frm = ", ".join(p.get("name") or p["address"] for p in s.data.get("from", []))
            to = ", ".join(p.get("name") or p["address"] for p in s.data.get("to", []))
            dt, info = nlp.parse_datetime(s.timestamp_raw, default_tz=idx.tz) if s.timestamp_raw else (None, {})
            events.append(_mk(s, dt, info, "source_reported" if dt else "unknown", etype, f"Email: {subj}",
                              f"From {frm} to {to}", [frm, to], {"channel": "email"}))
            continue
        if s.kind in ("message", "system"):
            dt, info = nlp.parse_datetime(s.timestamp_raw, default_tz=idx.tz) if s.timestamp_raw else (None, {})
            etype = nlp.classify_event(s.text) or "message"
            snippet = s.text.replace("\n", " ")
            events.append(_mk(s, dt, info, "source_reported" if dt else "unknown", etype,
                              f"{s.author or 'System'}: {snippet[:110]}", s.text, [s.author] if s.author else [],
                              {"channel": "chat", "message_id": s.data.get("message_id")}))
            if dt and etype != "message":
                rel = nlp.resolve_relative(s.text, dt)
                if rel:
                    rdt, phrase = rel
                    events.append(_mk(s, rdt, {"raw": phrase, "precision": "day", "anchor": dt.isoformat(), "display_offset": info.get("display_offset")}, "estimated",
                                      etype, f"Referenced event ({phrase}): {snippet[:90]}",
                                      f"Date estimated from the phrase '{phrase}' relative to the message time.",
                                      [s.author] if s.author else [], {"channel": "chat", "relative_to_message": True}))
            continue
        if s.kind == "row":
            fields = s.data.get("fields", {})
            if not s.timestamp_raw:
                continue
            dt, info = nlp.parse_datetime(s.timestamp_raw, default_tz=idx.tz)
            title_bits = [fields[k] for k in fields if any(t in k for t in ROW_TITLE_KEYS) and fields[k]]
            title = " · ".join(title_bits[:3]) or s.text[:110]
            etype = nlp.classify_event(s.text) or "record"
            actors = [fields[k] for k in fields if any(t in k for t in ("user", "actor", "by", "name", "employee")) and fields[k]]
            events.append(_mk(s, dt, info, "source_reported" if dt else "unknown", etype, title, s.text, actors,
                              {"channel": "log", "row": s.locator}))
            continue
        if s.kind in ("paragraph", "page", "ocr_line", "transcript", "email_body"):
            text = ocr_spacing(s.text) if s.kind == "ocr_line" else s.text
            found = nlp.find_dates(text)
            seen = set()
            for raw, pos in found:
                dt, info = nlp.parse_datetime(raw, default_tz=idx.tz)
                if not dt:
                    continue
                sent = _sentence_around(text, pos)
                if s.kind == "ocr_line":
                    neighbours = [x for x in idx.segments_of(s.evidence_id) if abs(x.seq - s.seq) <= 2]
                    ctx = " ".join(x.text for x in neighbours)
                    etype = nlp.classify_event(ctx) or "document_date"
                    sent = s.text
                else:
                    etype = nlp.classify_event(sent) or "document_date"
                key = (dt.isoformat(), etype)
                if key in seen:
                    continue
                seen.add(key)
                label = re.split(r"[:=]", sent)[0][:60] if ":" in sent[:60] else ""
                events.append(_mk(s, dt, info, "source_reported", etype, sent[:140] or raw, sent, [],
                                  {"channel": ev.detected_type, "field_label": label}))
            if not found and s.kind == "transcript":
                # Spoken dates rarely include a year ("the 18th of March at 10:40"). Use the recording date's year and
                # label the result as estimated, so it is never mistaken for a source-reported time.
                for m in SPOKEN_DATE.finditer(s.text):
                    base = ev.intake_at
                    raw = f"{m.group(1)} {m.group(2)} {base.year}" + (f" {m.group(3)}:{m.group(4)} {m.group(5) or ''}" if m.group(3) else "")
                    dt, info = nlp.parse_datetime(raw.strip(), default_tz=idx.tz)
                    if not dt:
                        continue
                    info.update({"note": f"Year not spoken; assumed {base.year} from the recording date", "raw": m.group(0)})
                    sent = _sentence_around(s.text, m.start())
                    events.append(_mk(s, dt, info, "estimated", nlp.classify_event(sent) or "statement", sent[:140], sent, [],
                                      {"channel": "audio", "spoken_date": m.group(0)}))
                    found = [(m.group(0), m.start())]
            if not found and s.kind in ("paragraph", "transcript"):
                for c in nlp.claims_in(s.text):
                    events.append(_mk(s, None, {}, "unknown", c["event_type"], c["sentence"][:140], c["sentence"], [],
                                      {"channel": ev.detected_type, "claim_polarity": c["polarity"],
                                       "note": "Event described without any time information"}))
    # File-metadata timestamps.
    for e in idx.evidence.values():
        meta = e.file_metadata or {}
        raw = (meta.get("exif") or {}).get("DateTimeOriginal") or (meta.get("pdf_info") or {}).get("CreationDate") \
            or (meta.get("core_properties") or {}).get("created")
        if raw:
            r2 = re.sub(r"^D:(\d{4})(\d{2})(\d{2})(\d{2})(\d{2})(\d{2}).*", r"\1-\2-\3 \4:\5:\6", raw)
            r2 = re.sub(r"^(\d{4}):(\d{2}):(\d{2})", r"\1-\2-\3", r2)
            dt, info = nlp.parse_datetime(r2, default_tz=idx.tz)
            segs = idx.segments_of(e.id)
            if dt and segs:
                info["raw"] = raw
                events.append(_mk(segs[0], dt, info, "metadata_derived", "file_created",
                                  f"File metadata timestamp: {e.original_filename}",
                                  "Creation time recorded in file metadata. Metadata can be altered and reflects "
                                  "the creating device's clock.", [], {"channel": "metadata"}))

    # File and system times are NOT event times: kept on separate, clearly labelled lanes.
    for e in idx.evidence.values():
        meta = e.file_metadata or {}
        segs = idx.segments_of(e.id)
        anchor = segs[0] if segs else None
        if anchor is None:
            continue
        mod = (meta.get("pdf_info") or {}).get("ModDate") or (meta.get("core_properties") or {}).get("modified")
        if mod:
            r2 = re.sub(r"^D:(\d{4})(\d{2})(\d{2})(\d{2})(\d{2})(\d{2}).*", r"\1-\2-\3 \4:\5:\6", str(mod))
            dt, info = nlp.parse_datetime(r2, default_tz=idx.tz)
            if dt:
                info["raw"] = str(mod)
                events.append(_mk(anchor, dt, info, "metadata_derived", "file_modified", f"File metadata modification time: {e.original_filename}",
                                  "Modification time recorded in the file's own metadata. This is not the time of any described event.", [],
                                  {"channel": "metadata", "lane": "file"}))
        if e.intake_at:
            events.append(_mk(anchor, e.intake_at, {"raw": e.intake_at.isoformat(), "display_offset": "UTC", "precision": "second"},
                              "system_recorded", "evidence_received", f"Received into GhostTrace: {e.evidence_code} {e.original_filename}",
                              "Server-side intake time (when the platform received the file), recorded by the system clock.", [],
                              {"channel": "system", "lane": "system"}))

    ent_by_seg: dict[str, list[str]] = {}
    for m in db.query(EntityMention).filter(EntityMention.case_id == idx.case_id):
        ent_by_seg.setdefault(m.segment_id, []).append(m.entity_id)
    for e in events:
        db.add(TimelineEvent(case_id=idx.case_id, evidence_id=e["segment"].evidence_id, segment_id=e["segment"].id,
                             occurred_at=e["occurred_at"], timestamp_raw=e["timestamp_raw"],
                             timestamp_kind=e["timestamp_kind"], event_type=e["event_type"], title=e["title"],
                             description=e["description"], actors=[a for a in e["actors"] if a],
                             entity_ids=sorted(set(ent_by_seg.get(e["segment"].id, []))), data=e["data"]))
    db.flush()
    kinds: dict[str, int] = {}
    for e in events:
        kinds[e["timestamp_kind"]] = kinds.get(e["timestamp_kind"], 0) + 1
    return {"events": len(events), "by_timestamp_kind": kinds}
