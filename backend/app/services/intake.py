"""Deterministic evidence intake: type detection by content signature, validation and hashing."""
from __future__ import annotations

import hashlib
import io
import json
import re
import zipfile
from dataclasses import dataclass
from pathlib import Path

EXT_TYPES: dict[str, tuple[str, str]] = {
    ".jpg": ("image", "image/jpeg"), ".jpeg": ("image", "image/jpeg"), ".png": ("image", "image/png"), ".webp": ("image", "image/webp"),
    ".pdf": ("pdf", "application/pdf"),
    ".docx": ("docx", "application/vnd.openxmlformats-officedocument.wordprocessingml.document"),
    ".txt": ("text", "text/plain"), ".md": ("text", "text/markdown"), ".log": ("text", "text/plain"),
    ".csv": ("spreadsheet", "text/csv"),
    ".xlsx": ("spreadsheet", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"),
    ".eml": ("email", "message/rfc822"), ".mbox": ("email", "application/mbox"),
    ".html": ("html", "text/html"), ".htm": ("html", "text/html"),
    ".json": ("chat", "application/json"),
    ".mp3": ("audio", "audio/mpeg"), ".wav": ("audio", "audio/wav"),
    ".mp4": ("video", "video/mp4"),
}

UNSUPPORTED_HINTS = {
    ".doc": "Legacy .doc is not parsed; please export as .docx or PDF.",
    ".xls": "Legacy .xls is not parsed; please export as .xlsx or CSV.",
    ".heic": "HEIC images are not supported; please export as JPG/PNG.",
    ".mov": "MOV video is not supported; please export as MP4.",
    ".zip": "Archives are not unpacked automatically; upload the contained files individually.",
}

BLOCKED_SIGNATURES = [(b"MZ", "Windows executable"), (b"\x7fELF", "ELF executable"),
                      (b"#!", "script with interpreter line"), (b"\xca\xfe\xba\xbe", "Mach-O/Java binary")]

WHATSAPP_RE = re.compile(r"^\[?\d{1,2}[/.]\d{1,2}[/.]\d{2,4},? \d{1,2}:\d{2}(?::\d{2})?(?:\s?[APap][Mm])?\]? ?[-–]? ", re.M)


@dataclass
class IntakeResult:
    ok: bool
    detected_type: str
    mime_type: str
    sha256: str
    size: int
    reason: str = ""
    warnings: list[str] | None = None


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _is_text(data: bytes) -> bool:
    if b"\x00" in data[:8192]:
        return False
    try:
        data[:65536].decode("utf-8")
        return True
    except UnicodeDecodeError:
        try:
            data[:65536].decode("latin-1")
            return True
        except Exception:
            return False


def inspect_upload(filename: str, data: bytes, max_bytes: int) -> IntakeResult:
    ext = Path(filename).suffix.lower()
    digest = sha256_bytes(data)
    size = len(data)
    warnings: list[str] = []

    def fail(reason: str, dtype: str = "unknown", mime: str = "application/octet-stream"):
        return IntakeResult(False, dtype, mime, digest, size, reason, warnings)

    if size == 0:
        return fail("Empty file")
    if size > max_bytes:
        return fail(f"File exceeds the {max_bytes // (1024 * 1024)} MB upload limit")
    for sig, label in BLOCKED_SIGNATURES:
        if data.startswith(sig):
            return fail(f"Rejected: content looks like a {label}, which is not an accepted evidence format")
    if ext in UNSUPPORTED_HINTS:
        return fail(UNSUPPORTED_HINTS[ext])
    if ext not in EXT_TYPES:
        return fail(f"Unsupported file type '{ext or 'none'}'. Supported: " + ", ".join(sorted(EXT_TYPES)))

    dtype, mime = EXT_TYPES[ext]
    head = data[:16]
    # Content-signature checks: the extension must agree with the bytes.
    if ext == ".png" and not head.startswith(b"\x89PNG\r\n\x1a\n"):
        return fail("File extension is .png but content is not a PNG image")
    if ext in (".jpg", ".jpeg") and not head.startswith(b"\xff\xd8\xff"):
        return fail("File extension is .jpg but content is not a JPEG image")
    if ext == ".webp" and not (head.startswith(b"RIFF") and data[8:12] == b"WEBP"):
        return fail("File extension is .webp but content is not a WebP image")
    if ext == ".pdf" and b"%PDF-" not in data[:1024]:
        return fail("File extension is .pdf but no PDF header was found")
    if ext in (".docx", ".xlsx"):
        if not head.startswith(b"PK"):
            return fail(f"File extension is {ext} but content is not an Office Open XML package")
        try:
            names = zipfile.ZipFile(io.BytesIO(data)).namelist()
        except zipfile.BadZipFile:
            return fail("Corrupt Office document (bad zip container)")
        if any(n.startswith("/") or ".." in n for n in names):
            return fail("Office document contains unsafe internal paths")
        if ext == ".docx" and not any(n.startswith("word/") for n in names):
            return fail("Not a Word document")
        if ext == ".xlsx" and not any(n.startswith("xl/") for n in names):
            return fail("Not an Excel workbook")
        if any(n.endswith("vbaProject.bin") for n in names):
            warnings.append("Document contains macros; macros are never executed")
    if ext == ".wav" and not (head.startswith(b"RIFF") and data[8:12] == b"WAVE"):
        return fail("File extension is .wav but content is not RIFF/WAVE audio")
    if ext == ".mp3" and not (head.startswith(b"ID3") or head[:2] in (b"\xff\xfb", b"\xff\xf3", b"\xff\xf2")):
        return fail("File extension is .mp3 but content is not MPEG audio")
    if ext == ".mp4" and data[4:8] != b"ftyp":
        return fail("File extension is .mp4 but content is not an MP4 container")
    if ext in (".txt", ".md", ".log", ".csv", ".eml", ".json", ".mbox", ".html", ".htm") and not _is_text(data):
        return fail(f"File extension is {ext} but content is binary")

    if ext == ".json":
        try:
            obj = json.loads(data.decode("utf-8", errors="replace"))
        except json.JSONDecodeError as e:
            return fail(f"Invalid JSON: {e.msg}")
        if not (isinstance(obj, dict) and isinstance(obj.get("messages"), list)) and not isinstance(obj, list):
            dtype = "text"
            warnings.append("JSON is not a recognised chat export; it will be indexed as structured text")
    if ext == ".txt":
        sample = data[:20000].decode("utf-8", errors="replace")
        if len(WHATSAPP_RE.findall(sample)) >= 3:
            dtype = "chat"
            warnings.append("Detected WhatsApp-style chat export")
    return IntakeResult(True, dtype, mime, digest, size, "", warnings)
