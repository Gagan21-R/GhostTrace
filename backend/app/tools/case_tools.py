"""Read-only, case-scoped tools. Each one answers a single investigative question about the evidence."""
from __future__ import annotations

import difflib
import io
import re
from dataclasses import dataclass
from datetime import datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..analysis import naive_bayes as nb
from ..analysis import nlp
from ..analysis.index import CaseIndex
from ..models import Case, Evidence, TimelineEvent
from .registry import REGISTRY, ToolError

TIME_RX = re.compile(r"(\d{1,2}:\d{2})(?:\s*([AaPp][Mm]))?\s*(?:✓✓|✓|vv|v)?\s*$")
STATUS_RX = re.compile(r"^\s*(\d{1,2}:\d{2})(?:\s*[AaPp][Mm])?\s*(?:[^\w\s]|4G|5G|LTE|VoLTE|\d+%|\s)*$")
DATE_LINE_RX = re.compile(r"^\s*(?:today|yesterday|(?:mon|tue|wed|thu|fri|sat|sun)\w*,?\s*)?\d{1,2}\s*[a-z]{3,9}\.?\s*\d{4}\s*$|"
                          r"^\s*[a-z]{3,9}\s+\d{1,2},?\s+\d{4}\s*$", re.I)
GENERATOR_RX = re.compile(r"fake\s*chat|chat\s*(?:generator|maker)|prank|fakewhats|whatsfake|generated (?:with|by)|"
                          r"mock\s*chat|photoshop|gimp|canva|snapseed|picsart|pixlr|paint\.net", re.I)
WHEREABOUTS_RX = re.compile(r"badge|swipe|check-?in|checked in|boarding|board(?:ed)?|flight|gate|exam|invigilat|hall|hospital|ward|"
                            r"admitted|surgery|location|gps|airplane mode|flight mode|switched off|no network|offline|attendance|"
                            r"cctv|on duty|shift|present", re.I)
SECURITY_TYPES = ("device_link", "sim_change", "login", "password_reset", "recovery_change", "mfa", "security_alert")


@dataclass
class CaseCtx:
    db: Session
    case: Case
    idx: CaseIndex

    @classmethod
    def load(cls, db: Session, case_id: str) -> "CaseCtx":
        case = db.get(Case, case_id)
        if not case:
            raise ToolError("case not found")
        return cls(db, case, CaseIndex(db, case_id))

    def by_code(self, code: str) -> Evidence:
        code = code.strip().upper()
        for e in self.idx.evidence.values():
            if e.evidence_code.upper() == code or e.original_filename.upper() == code:
                return e
        raise ToolError(f"no evidence {code} in this case")

    def events(self) -> list[TimelineEvent]:
        if not hasattr(self, "_events"):
            self._events = list(self.db.scalars(select(TimelineEvent).where(TimelineEvent.case_id == self.case.id)))
        return self._events


def _first(name: str | None) -> str:
    return (name or "").strip().split(" ")[0].lower()


def _norm(t: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"[^\w\s]", " ", t.lower())).strip()


def _dt(raw: str | None, tz: str) -> datetime | None:
    return nlp.parse_datetime(raw, default_tz=tz)[0] if raw else None


def _when(d: datetime | None) -> str | None:
    return d.strftime("%Y-%m-%d %H:%M UTC") if d else None


# ----------------------------------------------------------------------------------------------- tools
@REGISTRY.register("list_evidence", "List the evidence items in the case (code, file name, type, category, who collected it).",
                   {"type": {"type": "string", "description": "Optional detected type filter: image, chat, email, spreadsheet, pdf, audio"}})
def list_evidence(ctx: CaseCtx, type: str | None = None):
    return [{"code": e.evidence_code, "file": e.original_filename, "type": e.detected_type, "category": e.category,
             "collected": (e.collection_source or "")[:120]}
            for e in sorted(ctx.idx.evidence.values(), key=lambda e: e.evidence_code) if not type or e.detected_type == type]


@REGISTRY.register("read_evidence", "Read the extracted text of one evidence item (OCR, transcript or parsed content).",
                   {"code": {"type": "string", "description": "Evidence code such as EV-003"},
                    "max_chars": {"type": "integer", "minimum": 100, "maximum": 4000}}, ["code"])
def read_evidence(ctx: CaseCtx, code: str, max_chars: int = 1500):
    e = ctx.by_code(code)
    text = "\n".join(f"[{s.locator}{' ' + s.author if s.author else ''}{' @' + s.timestamp_raw if s.timestamp_raw else ''}] {s.text}"
                     for s in ctx.idx.segments_of(e.id))
    return {"code": e.evidence_code, "file": e.original_filename, "text": text[:max_chars], "truncated": len(text) > max_chars}


@REGISTRY.register("classify_message", "Classify a message with the Naive Bayes model (harassment, extortion, fraud, phishing, OTP request, ordinary).",
                   {"text": {"type": "string"}}, ["text"])
def classify_message(ctx, text: str):
    r = nb.classify(text)
    return {k: r[k] for k in ("label", "label_name", "confidence", "uncertain", "top_terms")}


def parse_chat_screenshot(ctx: CaseCtx, e: Evidence) -> dict:
    segs = [s for s in ctx.idx.segments_of(e.id) if s.kind == "ocr_line"]
    width = (e.file_metadata or {}).get("extraction", {}).get("width") or (e.file_metadata or {}).get("width") or 1000
    status_time, contact, date_label, msgs = None, None, None, []
    for s in segs:
        txt, bbox = s.text.strip(), s.data.get("bbox") or [0, 0, 0, 0]
        if status_time is None and bbox[1] < 70 and STATUS_RX.match(txt):
            status_time = STATUS_RX.match(txt).group(1)
            continue
        if DATE_LINE_RX.match(txt):
            date_label = txt
            continue
        m = TIME_RX.search(txt)
        body = TIME_RX.sub("", txt).strip(" -·") if m else ""
        if m and len(_norm(body)) >= 3 and not nlp.find_dates(body) and not re.search(r"\b\d{4}\b", body):
            hhmm = m.group(1) + (" " + m.group(2).upper() if m.group(2) else "")
            side = "incoming" if bbox[0] < width * 0.3 else "outgoing"
            msgs.append({"locator": s.locator, "segment_id": s.id, "text": body, "time": hhmm, "side": side})
            continue
        if contact is None and 2 < len(txt) < 40 and re.search(r"[A-Za-z]{2}", txt) and not GENERATOR_RX.search(txt) and not msgs:
            contact = re.sub(r"\s*(online|typing…?|last seen.*)$", "", txt, flags=re.I).strip()
    return {"status_bar_time": status_time, "contact": contact, "date": date_label, "messages": msgs}


@REGISTRY.register("find_disputed_messages", "Find chat screenshots in the case and the messages in them that the Naive Bayes model flags "
                   "(threats, extortion, OTP requests, scams). These are the messages whose authorship may be disputed.")
def find_disputed_messages(ctx: CaseCtx):
    out = []
    for e in sorted(ctx.idx.evidence.values(), key=lambda e: e.evidence_code):
        if e.detected_type != "image":
            continue
        chat = parse_chat_screenshot(ctx, e)
        if len(chat["messages"]) < 2:
            continue
        for m in chat["messages"]:
            if m["side"] != "incoming":
                continue
            c = nb.classify(m["text"])
            if c["label"] != "benign" and not c["uncertain"]:
                out.append({"code": e.evidence_code, "file": e.original_filename, "claimed_sender": chat["contact"],
                            "screenshot_date": chat["date"], "time_on_screen": m["time"], "text": m["text"],
                            "label": c["label"], "confidence": c["confidence"], "locator": m["locator"]})
    return out


@REGISTRY.register("inspect_screenshot", "Forensic checks on a screenshot: editing/generator software in metadata, status-bar clock vs "
                   "message times, error-level analysis for pasted regions, image size.",
                   {"code": {"type": "string"}}, ["code"])
def inspect_screenshot(ctx: CaseCtx, code: str):
    from PIL import Image, ImageChops
    from ..storage import get_storage
    e = ctx.by_code(code)
    if e.detected_type != "image":
        raise ToolError("not an image")
    data = get_storage().get(e.storage_key)
    img = Image.open(io.BytesIO(data))
    meta = {k: str(v)[:120] for k, v in (img.info or {}).items() if isinstance(v, (str, int, float)) and k not in ("dpi",)}
    exif = (e.file_metadata or {}).get("exif") or {}
    software = " ".join(filter(None, [exif.get("Software"), meta.get("Software"), meta.get("Comment"), meta.get("Description")]))
    chat = parse_chat_screenshot(ctx, e)
    ocr_text = " ".join(s.text for s in ctx.idx.segments_of(e.id))
    out = {"code": e.evidence_code, "size": f"{img.width}x{img.height}", "format": img.format,
           "software_tags": software or None, "editing_or_generator": bool(GENERATOR_RX.search(software) or GENERATOR_RX.search(ocr_text)),
           "generator_text_on_image": bool(GENERATOR_RX.search(ocr_text)),
           "status_bar_time": chat["status_bar_time"], "last_message_time": chat["messages"][-1]["time"] if chat["messages"] else None}

    def mins(t):
        h, m = map(int, t.split()[0].split(":"))
        if " PM" in t and h != 12:
            h += 12
        if " AM" in t and h == 12:
            h = 0
        return h * 60 + m
    if out["status_bar_time"] and chat["messages"]:
        latest = max(mins(m["time"]) for m in chat["messages"])
        out["clock_before_messages"] = mins(out["status_bar_time"]) < latest
    # Error-level analysis: JPEG regions pasted from another source recompress differently.
    if img.format == "JPEG":
        rgb = img.convert("RGB")
        buf = io.BytesIO()
        rgb.save(buf, "JPEG", quality=90)
        diff = ImageChops.difference(rgb, Image.open(io.BytesIO(buf.getvalue()))).convert("L")
        bw, bh = 32, 32
        px = diff.load()
        gray = rgb.convert("L").load()
        blocks = []
        for by in range(0, img.height - bh, bh):
            for bx in range(0, img.width - bw, bw):
                vals = [px[x, y] for y in range(by, by + bh, 2) for x in range(bx, bx + bw, 2)]
                edge = max(gray[x, y] for y in range(by, by + bh, 4) for x in range(bx, bx + bw, 4)) - \
                    min(gray[x, y] for y in range(by, by + bh, 4) for x in range(bx, bx + bw, 4))
                if edge > 60:  # only blocks with text/edges carry an error level
                    blocks.append((sum(vals) / len(vals), by))
        if len(blocks) >= 8:
            levels = sorted(b[0] for b in blocks)
            med = levels[len(levels) // 2] or 0.01
            hi = [b for b in blocks if b[0] < med * 0.45]  # regions noticeably cleaner than the rest = re-saved at a higher quality
            out["ela"] = {"median_level": round(med, 2), "outlier_blocks": len(hi), "blocks": len(blocks),
                          "outlier_rows": sorted({b[1] for b in hi})[:6]}
            out["ela_anomaly"] = len(hi) >= 3 and len(hi) / len(blocks) < 0.4
    else:
        out["ela"] = "not applicable to lossless PNG; rely on source records"
    return out


@REGISTRY.register("search_message_exports", "Search the chat exports (from either phone) for a message, optionally only messages by one sender. "
                   "Returns the closest matches with similarity, timestamp and whose device the export came from.",
                   {"text": {"type": "string"}, "sender": {"type": "string"}}, ["text"])
def search_message_exports(ctx: CaseCtx, text: str, sender: str | None = None):
    target, first = _norm(text), _first(sender)
    exports, matches = [], []
    for e in ctx.idx.evidence.values():
        if e.detected_type != "chat":
            continue
        segs = [s for s in ctx.idx.segments_of(e.id) if s.kind in ("message", "system")]
        times = [d for d in (_dt(s.timestamp_raw, ctx.idx.tz) for s in segs) if d]
        holder = e.collection_source or ""
        exports.append({"code": e.evidence_code, "file": e.original_filename, "messages": len(segs),
                        "from": _when(min(times)) if times else None, "to": _when(max(times)) if times else None,
                        "collected": holder[:100], "from_sender_device": bool(first and first in holder.lower())})
        for s in segs:
            if first and first not in (s.author or "").lower():
                continue
            r = difflib.SequenceMatcher(None, target, _norm(s.text)).ratio()
            if r >= 0.5:
                matches.append({"code": e.evidence_code, "locator": s.locator, "author": s.author, "time": s.timestamp_raw,
                                "time_utc": _when(_dt(s.timestamp_raw, ctx.idx.tz)), "text": s.text[:200],
                                "similarity": round(r, 3), "from_sender_device": exports[-1]["from_sender_device"]})
    matches.sort(key=lambda m: (-m["similarity"], not m["from_sender_device"]))
    return {"exports": exports, "matches": matches[:5]}


@REGISTRY.register("account_security_events", "List account-security events (new device linked, SIM change, new sign-in, password or "
                   "recovery change, OTP request) in a window before/around a time, and whether they concern a named person.",
                   {"around": {"type": "string", "description": "Timestamp, e.g. 2026-03-18 22:42"},
                    "person": {"type": "string"}, "hours_before": {"type": "integer", "minimum": 1, "maximum": 168}}, ["around"])
def account_security_events(ctx: CaseCtx, around: str, person: str | None = None, hours_before: int = 48):
    t = _dt(around, ctx.idx.tz)
    if not t:
        raise ToolError("could not read the time")
    first, out, sent_from_linked = _first(person), [], []
    log_sources = set()
    for ev in ctx.events():
        seg = ctx.idx.seg_by_id.get(ev.segment_id) if ev.segment_id else None
        e = ctx.idx.evidence.get(ev.evidence_id)
        text = f"{ev.title} {ev.description} {seg.text if seg else ''}"
        src = f"{e.original_filename} {e.collection_source} {e.category}" if e else ""
        related = bool(first) and (first in text.lower() or first in src.lower())
        if re.search(r"session|login|sign-?in|account|activity|security|device|carrier|sim", src, re.I) and related:
            log_sources.add(e.evidence_code)
        if not ev.occurred_at:
            continue
        dt = ev.occurred_at
        if ev.event_type in SECURITY_TYPES and t - timedelta(hours=hours_before) <= dt <= t + timedelta(minutes=10):
            out.append({"type": ev.event_type, "time_utc": _when(dt), "minutes_before": round((t - dt).total_seconds() / 60),
                        "what": (seg.text if seg else ev.title)[:160], "code": e.evidence_code if e else None, "concerns_person": related})
        if abs((dt - t).total_seconds()) <= 180 and re.search(r"message sent|sent (?:a )?message|msg sent", text, re.I) and \
                re.search(r"web|linked|desktop|new device|browser|unknown", text, re.I):
            sent_from_linked.append({"time_utc": _when(dt), "what": (seg.text if seg else ev.title)[:160], "code": e.evidence_code if e else None})
    return {"window": f"{hours_before}h before to 10 min after {_when(t)}", "events": sorted(out, key=lambda x: x["minutes_before"]),
            "message_sent_from_linked_or_web_device": sent_from_linked, "account_logs_available": sorted(log_sources)}


@REGISTRY.register("person_whereabouts", "Find records that place a person somewhere at a given time (attendance, badge swipes, flights, "
                   "hospital, device offline), which can make typing a message at that moment unlikely.",
                   {"person": {"type": "string"}, "around": {"type": "string"}, "minutes": {"type": "integer", "minimum": 5, "maximum": 240}},
                   ["person", "around"])
def person_whereabouts(ctx: CaseCtx, person: str, around: str, minutes: int = 60):
    t = _dt(around, ctx.idx.tz)
    if not t:
        raise ToolError("could not read the time")
    first, full, out = _first(person), (person or "").lower().strip(), []
    for s in ctx.idx.segments:
        e = ctx.idx.evidence[s.evidence_id]
        if e.detected_type in ("chat", "email") or not WHEREABOUTS_RX.search(f"{s.text} {e.original_filename} {e.category}"):
            continue
        low = s.text.lower()
        if not (full in low or (first and re.search(r"\b" + re.escape(first) + r"\b", low))):
            continue
        times = sorted(d for d in [_dt(r, ctx.idx.tz) for r, _ in nlp.find_dates(s.text)] if d)
        if not times:
            continue
        inside = len(times) >= 2 and times[0] <= t <= times[-1] and (times[-1] - times[0]) <= timedelta(hours=12)
        near = min(times, key=lambda d: abs((d - t).total_seconds()))
        if inside or abs((near - t).total_seconds()) <= minutes * 60:
            out.append({"time_utc": _when(near), "minutes_from_message": round((near - t).total_seconds() / 60),
                        "covers_message_time": inside, "record": s.text[:180], "code": e.evidence_code, "source": e.original_filename})
    return {"records": sorted(out, key=lambda r: (not r["covers_message_time"], abs(r["minutes_from_message"])))[:6]}


@REGISTRY.register("compare_writing_style", "Authorship check: train a character n-gram Naive Bayes model on a person's own known messages "
                   "(from chat exports) and score how much the disputed text reads like them.",
                   {"text": {"type": "string"}, "person": {"type": "string"}}, ["text", "person"])
def compare_writing_style(ctx: CaseCtx, text: str, person: str):
    first, target = _first(person), _norm(text)
    known, others = [], []
    for e in ctx.idx.evidence.values():
        if e.detected_type != "chat":
            continue
        for s in ctx.idx.segments_of(e.id):
            if s.kind != "message" or len(s.text) < 4 or difflib.SequenceMatcher(None, target, _norm(s.text)).ratio() > 0.7:
                continue  # never train on the disputed message itself
            (known if first and first in (s.author or "").lower() else others).append(s.text)
    known = list(dict.fromkeys(known))
    model = nb.AuthorshipNB(known, list(dict.fromkeys(others)))
    if not model.usable:
        return {"usable": False, "known_messages": len(known), "note": f"needs at least {nb.AuthorshipNB.MIN_KNOWN} known messages"}
    return {"usable": True, **model.score(text)}


@REGISTRY.register("messages_after", "Messages a person sent after a time (e.g. an apology, or a report that the account was hacked).",
                   {"person": {"type": "string"}, "after": {"type": "string"}, "hours": {"type": "integer", "minimum": 1, "maximum": 240}},
                   ["person", "after"])
def messages_after(ctx: CaseCtx, person: str, after: str, hours: int = 72):
    t = _dt(after, ctx.idx.tz)
    if not t:
        raise ToolError("could not read the time")
    first, out = _first(person), []
    for s in ctx.idx.segments:
        e = ctx.idx.evidence[s.evidence_id]
        if e.detected_type not in ("chat", "email") or not s.timestamp_raw:
            continue
        who = (s.author or "") + " " + (s.data.get("from") or "")
        d = _dt(s.timestamp_raw, ctx.idx.tz)
        if first and first in who.lower() and d and t < d <= t + timedelta(hours=hours):
            out.append({"time_utc": _when(d), "code": e.evidence_code, "text": s.text[:200]})
    return {"messages": out[:12]}
