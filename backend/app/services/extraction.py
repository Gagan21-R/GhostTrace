"""Multimodal extraction: turns an original evidence file into addressable segments.

Every segment carries a locator (page / message id / header / time range / row), the
extraction method and a confidence value. Missing metadata is left empty - never invented.
"""
from __future__ import annotations

import csv
import email
import email.policy
import io
import json
import re
import tempfile
import os
from dataclasses import dataclass, field
from email.utils import getaddresses, parsedate_to_datetime

from .engines import get_asr, get_ocr
from .intake import WHATSAPP_RE


@dataclass
class Extraction:
    segments: list[dict] = field(default_factory=list)
    metadata: dict = field(default_factory=dict)
    method: str = ""
    warnings: list[str] = field(default_factory=list)
    unavailable: str | None = None  # name of a missing engine, if extraction could not run
    parameters: dict = field(default_factory=dict)  # extractor parameters recorded for reproducibility

    @property
    def full_text(self) -> str:
        return "\n".join(f"[{s['locator']}] {s['text']}" for s in self.segments if s.get("text"))


def _seg(locator, kind, text, method, confidence=1.0, author=None, ts=None, data=None) -> dict:
    return {"locator": locator, "kind": kind, "text": (text or "").strip(), "method": method,
            "confidence": round(float(confidence), 3), "author": author, "timestamp_raw": ts, "data": data or {}}


def _decode(data: bytes) -> str:
    for enc in ("utf-8-sig", "utf-16", "latin-1"):
        try:
            return data.decode(enc)
        except UnicodeDecodeError:
            continue
    return data.decode("utf-8", errors="replace")


# ---------------------------------------------------------------- text / statements
KV_LINE = re.compile(r"^\s*([A-Za-z][A-Za-z /#()_-]{1,40}?)\s*[:=]\s*(.+)$")


def extract_text(data: bytes) -> Extraction:
    text = _decode(data)
    ex = Extraction(method="text-parser")
    blocks = [b for b in re.split(r"\n\s*\n", text) if b.strip()]
    for i, block in enumerate(blocks, 1):
        kv = {}
        for line in block.splitlines():
            m = KV_LINE.match(line)
            if m:
                kv[m.group(1).strip().lower()] = m.group(2).strip()
        ex.segments.append(_seg(f"para {i}", "paragraph", block, "text-parser", data={"fields": kv} if kv else {}))
    ex.metadata["paragraphs"] = len(blocks)
    return ex


# ---------------------------------------------------------------- chat
WA_LINE = re.compile(
    r"^\[?(?P<date>\d{1,2}[/.]\d{1,2}[/.]\d{2,4}),? (?P<time>\d{1,2}:\d{2}(?::\d{2})?(?:\s?[APap][Mm])?)\]? ?[-–]? ?"
    r"(?P<rest>.*)$")


def extract_whatsapp(data: bytes) -> Extraction:
    ex = Extraction(method="whatsapp-txt-parser")
    msgs: list[dict] = []
    for line in _decode(data).splitlines():
        m = WA_LINE.match(line)
        if m:
            rest = m.group("rest")
            if ": " in rest:
                sender, body = rest.split(": ", 1)
            else:
                sender, body = None, rest  # system message
            msgs.append({"ts": f"{m.group('date')} {m.group('time')}", "sender": sender, "text": body})
        elif msgs and line.strip():
            msgs[-1]["text"] += "\n" + line
    participants = sorted({m["sender"] for m in msgs if m["sender"]})
    for i, m in enumerate(msgs, 1):
        omitted = "<media omitted>" in m["text"].lower() or "<attached:" in m["text"].lower()
        ex.segments.append(_seg(f"msg {i}", "message" if m["sender"] else "system", m["text"], "whatsapp-txt-parser",
                                author=m["sender"], ts=m["ts"],
                                data={"message_id": str(i), "media_omitted": omitted}))
    ex.metadata.update({"platform": "WhatsApp (text export)", "participants": participants,
                        "message_count": len(msgs), "date_format_note": "WhatsApp exports use the exporting "
                        "device's locale and timezone; timezone is not recorded in the file."})
    return ex


def extract_chat_json(data: bytes) -> Extraction:
    obj = json.loads(_decode(data))
    ex = Extraction(method="chat-json-parser")
    if isinstance(obj, list):
        obj = {"messages": obj}
    msgs = obj.get("messages", [])
    info = obj.get("export_info", {}) or {}
    for i, m in enumerate(msgs, 1):
        if not isinstance(m, dict):
            continue
        text = m.get("text") if "text" in m else m.get("message", m.get("body", ""))
        if isinstance(text, list):  # Telegram rich text
            text = "".join(t if isinstance(t, str) else t.get("text", "") for t in text)
        mid = str(m.get("id", m.get("message_id", i)))
        atts = m.get("attachments") or []
        if m.get("photo") or m.get("file"):
            atts = atts + [{"name": m.get("photo") or m.get("file"), "included": True}]
        ex.segments.append(_seg(f"msg {mid}", "message", text or "", "chat-json-parser",
                                author=m.get("sender") or m.get("from") or m.get("author"),
                                ts=m.get("timestamp") or m.get("date") or m.get("time"),
                                data={"message_id": mid, "attachments": atts, "links": re.findall(r"https?://\S+", text or ""),
                                      "deleted": bool(m.get("deleted")), "edited": bool(m.get("edited"))}))
    participants = obj.get("participants") or sorted({s["author"] for s in ex.segments if s["author"]})
    ex.metadata.update({"platform": obj.get("platform", obj.get("type", "unknown")), "participants": participants,
                        "message_count": len(ex.segments), "export_info": info,
                        "conversation": obj.get("conversation") or obj.get("name")})
    return ex


# ---------------------------------------------------------------- email
def extract_email(data: bytes) -> Extraction:
    msg = email.message_from_bytes(data, policy=email.policy.default)
    ex = Extraction(method="rfc5322-parser")
    _email_segments(ex, msg, "")
    return ex


def extract_mbox(data: bytes) -> Extraction:
    """MBOX mailbox: every message becomes a header + body segment pair (locator 'msg N header/body')."""
    import mailbox
    ex = Extraction(method="mbox-parser")
    with tempfile.NamedTemporaryFile(delete=False, suffix=".mbox") as tf:
        tf.write(data)
        tmp = tf.name
    try:
        box = mailbox.mbox(tmp, factory=lambda f: email.message_from_binary_file(f, policy=email.policy.default), create=False)
        n = 0
        for n, msg in enumerate(box, 1):
            _email_segments(ex, msg, f"msg {n} ")
        box.close()
        ex.metadata = {"messages": n, "format": "mbox"}
        if n == 0:
            ex.warnings.append("Mailbox contains no messages")
    finally:
        os.unlink(tmp)
    return ex


def _email_segments(ex: Extraction, msg, prefix: str) -> None:
    hdr = {k: str(msg.get(k)) for k in ("From", "To", "Cc", "Reply-To", "Return-Path", "Subject", "Date",
                                        "Message-ID", "In-Reply-To", "X-Originating-IP") if msg.get(k)}
    received = [str(r) for r in msg.get_all("Received", [])]
    auth = [str(a) for a in msg.get_all("Authentication-Results", [])]
    date_iso = None
    if msg.get("Date"):
        try:
            date_iso = parsedate_to_datetime(str(msg.get("Date"))).isoformat()
        except Exception:
            ex.warnings.append("Date header present but not parseable")
    frm = getaddresses([hdr.get("From", "")])
    to = getaddresses([hdr.get("To", ""), hdr.get("Cc", "")])
    header_text = "\n".join(f"{k}: {v}" for k, v in hdr.items())
    ex.segments.append(_seg(f"{prefix}header", "email_header", header_text, ex.method, author=hdr.get("From"),
                            ts=hdr.get("Date"),
                            data={"from": [{"name": n, "address": a} for n, a in frm if a],
                                  "to": [{"name": n, "address": a} for n, a in to if a],
                                  "reply_to": hdr.get("Reply-To"), "return_path": hdr.get("Return-Path"),
                                  "subject": hdr.get("Subject"), "date_iso": date_iso,
                                  "message_id": hdr.get("Message-ID"), "received": received,
                                  "authentication_results": auth, "originating_ip": hdr.get("X-Originating-IP")}))
    body_parts, attachments = [], []
    for part in msg.walk():
        if part.is_multipart():
            continue
        disp = part.get_content_disposition()
        if disp == "attachment" or part.get_filename():
            payload = part.get_payload(decode=True) or b""
            import hashlib
            attachments.append({"filename": part.get_filename(), "content_type": part.get_content_type(),
                                "size": len(payload), "sha256": hashlib.sha256(payload).hexdigest()})
        elif part.get_content_type() == "text/plain":
            body_parts.append(part.get_content())
        elif part.get_content_type() == "text/html" and not body_parts:
            html = part.get_content()
            body_parts.append(re.sub(r"<[^>]+>", " ", html))
    body = "\n".join(body_parts).strip()
    links = re.findall(r"https?://[^\s\"'<>)]+", body)
    ex.segments.append(_seg(f"{prefix}body", "email_body", body, ex.method, author=hdr.get("From"), ts=hdr.get("Date"),
                            data={"links": links, "attachments": attachments, "message_id": hdr.get("Message-ID")}))
    if not prefix:
        ex.metadata.update({"headers": hdr, "received_hops": len(received), "has_authentication_results": bool(auth),
                            "attachments": attachments, "links": links})


# ---------------------------------------------------------------- spreadsheets
def _rows_to_segments(ex: Extraction, rows: list[list], sheet: str, method: str):
    rows = [r for r in rows if any(str(c).strip() for c in r if c is not None)]
    if not rows:
        return
    header = [str(c).strip() if c is not None else f"col{i}" for i, c in enumerate(rows[0])]
    for i, r in enumerate(rows[1:], 2):
        rec = {header[j]: ("" if v is None else str(v)) for j, v in enumerate(r) if j < len(header)}
        text = "; ".join(f"{k}: {v}" for k, v in rec.items() if v != "")
        ts_key = next((k for k in rec if re.search(r"time|date|when", k, re.I) and rec[k]), None)
        ex.segments.append(_seg(f"{sheet} row {i}", "row", text, method, ts=rec.get(ts_key) if ts_key else None,
                                data={"fields": {k.lower(): v for k, v in rec.items()}, "sheet": sheet}))
    ex.metadata.setdefault("sheets", []).append({"name": sheet, "columns": header, "rows": len(rows) - 1})


def extract_csv(data: bytes) -> Extraction:
    ex = Extraction(method="csv-parser")
    rows = list(csv.reader(io.StringIO(_decode(data))))
    _rows_to_segments(ex, rows, "csv", "csv-parser")
    return ex


def extract_xlsx(data: bytes) -> Extraction:
    import openpyxl
    ex = Extraction(method="openpyxl")
    wb = openpyxl.load_workbook(io.BytesIO(data), read_only=True, data_only=True)
    for ws in wb.worksheets:
        _rows_to_segments(ex, [list(r) for r in ws.iter_rows(values_only=True)], ws.title, "openpyxl")
    return ex


# ---------------------------------------------------------------- documents
def extract_pdf(data: bytes) -> Extraction:
    import pdfplumber
    ex = Extraction(method="pdfplumber")
    with pdfplumber.open(io.BytesIO(data)) as pdf:
        meta = {k: str(v) for k, v in (pdf.metadata or {}).items() if k in ("CreationDate", "ModDate", "Producer", "Creator", "Author", "Title")}
        ex.metadata.update({"pages": len(pdf.pages), "pdf_info": meta})
        for pno, page in enumerate(pdf.pages, 1):
            text = page.extract_text() or ""
            tables = page.extract_tables() or []
            fields = {}
            for line in text.splitlines():
                m = KV_LINE.match(line)
                if m:
                    fields[m.group(1).strip().lower()] = m.group(2).strip()
            if text.strip():
                ex.segments.append(_seg(f"page {pno}", "page", text, "pdfplumber", data={"tables": tables, "fields": fields}))
            else:
                ex.segments.extend(_ocr_pdf_page(ex, data, pno))
    return ex


def _ocr_pdf_page(ex: Extraction, data: bytes, pno: int) -> list[dict]:
    """Scanned page (no text layer): render with pypdfium2 and OCR it; lines keep their page number and box."""
    ocr = get_ocr()
    if ocr is None:
        ex.warnings.append(f"Page {pno} has no text layer and no OCR engine is available")
        return []
    import pypdfium2 as pdfium
    pdf = pdfium.PdfDocument(data)
    img = pdf[pno - 1].render(scale=2.0).to_pil()
    with tempfile.NamedTemporaryFile(delete=False, suffix=".png") as tf:
        img.save(tf, "PNG")
        tmp = tf.name
    try:
        lines = ocr.read(tmp)
    finally:
        os.unlink(tmp)
    ex.method = f"pdfplumber+pdf-ocr:{ocr.name}"
    ex.parameters["pdf_ocr_render_scale"] = 2.0
    out = []
    for i, ln in enumerate(lines, 1):
        m = KV_LINE.match(ln["text"])
        out.append(_seg(f"page {pno} line {i}", "ocr_line", ln["text"], f"pdf-ocr:{ocr.name}", confidence=ln["confidence"],
                        data={"bbox": [round(b, 1) for b in ln["bbox"]], "page": pno, "fields": {m.group(1).strip().lower(): m.group(2).strip()} if m else {}}))
    ex.warnings.append(f"Page {pno} had no text layer; its text was obtained by OCR")
    return out


# ---------------------------------------------------------------- HTML
def extract_html(data: bytes) -> Extraction:
    from html.parser import HTMLParser
    ex = Extraction(method="html-parser")
    blocks, links, title, meta = [], [], [], {}

    class P(HTMLParser):
        buf: list[str] = []
        skip = 0
        in_title = False

        def handle_starttag(self, tag, attrs):
            a = dict(attrs)
            if tag in ("script", "style", "noscript"):
                self.skip += 1
            if tag == "title":
                self.in_title = True
            if tag == "a" and a.get("href"):
                links.append(a["href"])
            if tag == "meta" and a.get("name") and a.get("content"):
                meta[a["name"].lower()] = a["content"][:300]
            if tag in ("p", "div", "li", "tr", "h1", "h2", "h3", "h4", "br", "section", "article", "td", "table"):
                self.flush()

        def handle_endtag(self, tag):
            if tag in ("script", "style", "noscript") and self.skip:
                self.skip -= 1
            if tag == "title":
                self.in_title = False
            if tag in ("p", "div", "li", "tr", "h1", "h2", "h3", "h4", "section", "article", "table"):
                self.flush()

        def handle_data(self, d):
            if self.skip:
                return
            if self.in_title:
                title.append(d.strip())
            elif d.strip():
                self.buf.append(d.strip())

        def flush(self):
            if self.buf:
                blocks.append(" ".join(self.buf))
                self.buf = []

    p = P()
    p.feed(_decode(data))
    p.flush()
    merged = []
    for b in blocks:
        if merged and len(merged[-1]) < 120 and len(b) < 120 and not KV_LINE.match(b):
            merged[-1] += "\n" + b
        else:
            merged.append(b)
    for i, b in enumerate(merged, 1):
        fields = {m.group(1).strip().lower(): m.group(2).strip() for l in b.splitlines() if (m := KV_LINE.match(l))}
        ex.segments.append(_seg(f"block {i}", "paragraph", b, "html-parser", data={"fields": fields} if fields else {}))
    ex.metadata.update({"title": " ".join(title), "links": links[:200], "meta": meta, "blocks": len(merged)})
    return ex


def extract_docx(data: bytes) -> Extraction:
    import docx
    ex = Extraction(method="python-docx")
    d = docx.Document(io.BytesIO(data))
    cp = d.core_properties
    ex.metadata["core_properties"] = {k: str(getattr(cp, k)) for k in ("author", "created", "modified", "last_modified_by", "title", "revision") if getattr(cp, k, None)}
    para_i = 0
    buf: list[str] = []

    def flush():
        nonlocal para_i, buf
        if buf:
            para_i += 1
            block = "\n".join(buf)
            fields = {m.group(1).strip().lower(): m.group(2).strip() for l in buf if (m := KV_LINE.match(l))}
            ex.segments.append(_seg(f"para {para_i}", "paragraph", block, "python-docx", data={"fields": fields} if fields else {}))
            buf = []

    for p in d.paragraphs:  # each Word paragraph is its own addressable segment
        if p.style.name.lower().startswith("heading"):
            ex.segments.append(_seg(f"heading {para_i + 1}", "heading", p.text, "python-docx"))
        elif p.text.strip():
            buf.append(p.text)
            flush()
    for ti, t in enumerate(d.tables, 1):
        rows = [[c.text for c in r.cells] for r in t.rows]
        _rows_to_segments(ex, rows, f"table{ti}", "python-docx")
    return ex


# ---------------------------------------------------------------- images (OCR)
def extract_image(data: bytes, filename: str) -> Extraction:
    from PIL import Image, ExifTags
    ex = Extraction(method="ocr")
    img = Image.open(io.BytesIO(data))
    ex.metadata.update({"width": img.width, "height": img.height, "format": img.format})
    try:
        exif = img.getexif()
        tags = {ExifTags.TAGS.get(k, str(k)): str(v) for k, v in exif.items()} if exif else {}
        if tags:
            ex.metadata["exif"] = {k: v for k, v in tags.items() if k in ("DateTime", "DateTimeOriginal", "Make", "Model", "Software")}
    except Exception:
        pass
    ocr = get_ocr()
    if ocr is None:
        ex.unavailable = "ocr"
        ex.warnings.append("No OCR engine is installed/enabled; image text was not extracted")
        return ex
    ex.method = f"ocr:{ocr.name}"
    suffix = os.path.splitext(filename)[1] or ".png"
    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tf:
        tf.write(data)
        tmp = tf.name
    try:
        lines = ocr.read(tmp)
    finally:
        os.unlink(tmp)
    # Group OCR lines into visual rows so "Label: value" pairs stay together.
    rows: list[list[dict]] = []
    for ln in lines:
        if rows and abs(rows[-1][0]["bbox"][1] - ln["bbox"][1]) < max(8, (ln["bbox"][3] - ln["bbox"][1]) * 0.5):
            rows[-1].append(ln)
        else:
            rows.append([ln])
    for i, row in enumerate(rows, 1):
        row.sort(key=lambda l: l["bbox"][0])
        text = "  ".join(l["text"] for l in row)
        conf = min(l["confidence"] for l in row)
        bbox = [min(l["bbox"][0] for l in row), min(l["bbox"][1] for l in row),
                max(l["bbox"][2] for l in row), max(l["bbox"][3] for l in row)]
        m = KV_LINE.match(text)
        ex.segments.append(_seg(f"line {i}", "ocr_line", text, ex.method, confidence=conf,
                                data={"bbox": [round(b, 1) for b in bbox],
                                      "fields": {m.group(1).strip().lower(): m.group(2).strip()} if m else {}}))
    ex.metadata["ocr_lines"] = len(ex.segments)
    ex.metadata["ocr_mean_confidence"] = round(sum(s["confidence"] for s in ex.segments) / len(ex.segments), 3) if ex.segments else None
    return ex


# ---------------------------------------------------------------- audio / video (ASR)
def _fmt(t: float) -> str:
    return f"{int(t // 60):02d}:{t % 60:05.2f}"


def extract_media(data: bytes, filename: str, kind: str) -> Extraction:
    if kind == "video":
        return extract_video(data, filename)
    return _extract_audio(data, filename)


def extract_video(data: bytes, filename: str, every_s: float = 4.0, max_frames: int = 15) -> Extraction:
    """Video: transcribe the audio track (if any) and OCR keyframes sampled every few seconds.
    Visual observations are limited to on-screen text; no scene description model is used."""
    import av
    ex = Extraction(method="video")
    ex.parameters.update({"keyframe_interval_s": every_s, "max_frames": max_frames})
    frames = []
    try:
        with av.open(io.BytesIO(data)) as c:
            vs = next((s for s in c.streams if s.type == "video"), None)
            if vs is not None:
                ex.metadata.update({"duration_s": round(float(c.duration or 0) / 1e6, 2), "width": vs.codec_context.width,
                                    "height": vs.codec_context.height, "codec": vs.codec_context.name})
                next_t = 0.0
                for fr in c.decode(vs):
                    t = float(fr.pts * fr.time_base) if fr.pts is not None else 0.0
                    if t + 1e-6 >= next_t:
                        frames.append((t, fr.to_image()))
                        next_t = t + every_s
                        if len(frames) >= max_frames:
                            break
    except Exception as e:
        ex.warnings.append(f"Video stream could not be decoded: {type(e).__name__}: {e}")
    ocr = get_ocr()
    if frames and ocr is None:
        ex.warnings.append("No OCR engine available; keyframes were not read")
    seen = set()
    for t, img in frames if ocr else []:
        with tempfile.NamedTemporaryFile(delete=False, suffix=".png") as tf:
            img.save(tf, "PNG")
            tmp = tf.name
        try:
            lines = ocr.read(tmp)
        finally:
            os.unlink(tmp)
        text = "\n".join(l["text"] for l in lines)
        if not text.strip() or text in seen:
            continue
        seen.add(text)
        ex.segments.append(_seg(f"frame {_fmt(t)}", "video_frame", text, f"video-ocr:{ocr.name}",
                                confidence=min((l["confidence"] for l in lines), default=0.0), data={"time_s": round(t, 2)}))
    audio = _extract_audio(data, filename)
    ex.segments += audio.segments
    ex.warnings += [w for w in audio.warnings if "could not be decoded" not in w] or []
    if not audio.segments:
        ex.warnings.append("No transcribable speech found in the audio track")
    ex.metadata.update({"keyframes_sampled": len(frames), "frames_with_text": len(seen), **{k: v for k, v in audio.metadata.items()}})
    ex.method = "+".join(x for x in ("video-ocr" if seen else "", audio.method if audio.segments else "") if x) or "video"
    if not ex.segments:
        ex.unavailable = "video-content"
    return ex


def _extract_audio(data: bytes, filename: str) -> Extraction:
    ex = Extraction(method="asr")
    asr = get_asr()
    if asr is None:
        ex.unavailable = "asr"
        ex.warnings.append("No speech-to-text engine is installed/enabled; media was not transcribed")
        return ex
    ex.method = "asr:faster-whisper"
    try:
        audio = decode_audio_16k(data)
    except Exception as e:
        ex.unavailable = "audio-decoder"
        ex.warnings.append(f"Audio stream could not be decoded: {type(e).__name__}: {e}")
        return ex
    if True:
        # Language identification restricted to the languages this deployment supports (English, Hindi, Kannada):
        # Whisper scores ~100 languages; we keep the best of these three and transcribe in that language.
        lang, lang_p, cands = None, None, None
        try:
            _, _, all_probs = asr.detect_language(audio)
            probs = {k: float(v) for k, v in all_probs}
            sub = {k: probs.get(k, 0.0) for k in ("en", "hi", "kn")}
            tot = sum(sub.values()) or 1.0
            cands = {k: round(v / tot, 3) for k, v in sub.items()}
            lang = max(cands, key=cands.get)
            lang_p = cands[lang]
        except Exception as e:  # older faster-whisper: fall back to automatic detection during transcription
            ex.warnings.append(f"Language pre-detection unavailable ({type(e).__name__}); Whisper auto-detect used")
        segments, info = asr.transcribe(audio, beam_size=5, vad_filter=True, language=lang)
        for i, s in enumerate(segments, 1):
            conf = max(0.0, min(1.0, 1.0 + float(s.avg_logprob) / 2)) if s.avg_logprob is not None else 0.5
            ex.segments.append(_seg(f"{_fmt(s.start)}-{_fmt(s.end)}", "transcript", s.text, ex.method,
                                    confidence=conf, author=None,
                                    data={"start": s.start, "end": s.end, "speaker": "unattributed",
                                          "no_speech_prob": round(float(s.no_speech_prob), 3)}))
        ex.metadata.update({"language": lang or info.language, "language_probability": lang_p if lang else round(float(info.language_probability), 3),
                            "language_candidates": cands, "duration_s": round(info.duration, 2),
                            "speaker_labels": "not available - transcript speech is not attributed to a verified identity"})
    return ex


def decode_audio_16k(data: bytes):
    """Decode any audio/video stream to mono float32 PCM at 16 kHz (what Whisper expects)."""
    import av
    import numpy as np
    chunks = []
    with av.open(io.BytesIO(data)) as container:
        stream = next(s for s in container.streams if s.type == "audio")
        resampler = av.AudioResampler(format="s16", layout="mono", rate=16000)
        for frame in container.decode(stream):
            for f in resampler.resample(frame):
                chunks.append(f.to_ndarray().reshape(-1))
        for f in resampler.resample(None):
            chunks.append(f.to_ndarray().reshape(-1))
    if not chunks:
        raise ValueError("no audio frames")
    return (np.concatenate(chunks).astype(np.float32) / 32768.0)


def extract(detected_type: str, data: bytes, filename: str) -> Extraction:
    if detected_type == "email":
        return extract_mbox(data) if filename.lower().endswith(".mbox") else extract_email(data)
    if detected_type == "html":
        return extract_html(data)
    if detected_type == "chat":
        if filename.lower().endswith(".txt"):
            return extract_whatsapp(data)
        return extract_chat_json(data)
    if detected_type == "text":
        if filename.lower().endswith(".json"):
            return extract_text(json.dumps(json.loads(_decode(data)), indent=1).encode())
        return extract_text(data)
    if detected_type == "spreadsheet":
        return extract_xlsx(data) if filename.lower().endswith(".xlsx") else extract_csv(data)
    if detected_type == "pdf":
        return extract_pdf(data)
    if detected_type == "docx":
        return extract_docx(data)
    if detected_type == "image":
        return extract_image(data, filename)
    if detected_type in ("audio", "video"):
        return extract_media(data, filename, detected_type)
    ex = Extraction(method="none")
    ex.unavailable = "parser"
    ex.warnings.append(f"No parser for type {detected_type}")
    return ex
