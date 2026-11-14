"""Lazy loaders for optional heavy engines (OCR, speech-to-text, NLP).

Each loader returns ``None`` when the engine is not installed or disabled. Callers record
the engine as *unavailable* on the evidence item - nothing is ever silently faked.
"""
from __future__ import annotations

import logging
import os
import threading

os.environ.setdefault("HF_HUB_DISABLE_SYMLINKS_WARNING", "1")

from ..config import get_settings

log = logging.getLogger("evidencex.engines")
settings = get_settings()
_lock = threading.Lock()
_cache: dict[str, object] = {}
_errors: dict[str, str] = {}


def _load(name: str, factory):
    with _lock:
        if name in _cache:
            return _cache[name]
        try:
            _cache[name] = factory()
        except Exception as e:  # engine missing or failed to initialise
            _errors[name] = f"{type(e).__name__}: {e}"[:300]
            log.warning("engine %s unavailable: %s", name, _errors[name])
            _cache[name] = None
        return _cache[name]


class OCREngine:
    def __init__(self, name: str, impl):
        self.name = name
        self.impl = impl

    def read(self, image_path: str) -> list[dict]:
        """Return [{text, confidence, bbox:[x0,y0,x1,y1]}] in reading order."""
        lines: list[dict] = []
        if self.name == "rapidocr":
            result, _ = self.impl(image_path)
            for box, text, conf in result or []:
                xs = [p[0] for p in box]
                ys = [p[1] for p in box]
                lines.append({"text": text, "confidence": float(conf), "bbox": [min(xs), min(ys), max(xs), max(ys)]})
        else:  # paddleocr 3.x
            res = self.impl.predict(image_path)
            for page in res:
                texts = page.get("rec_texts", []) if hasattr(page, "get") else page["rec_texts"]
                scores = page.get("rec_scores", []) if hasattr(page, "get") else page["rec_scores"]
                boxes = page.get("rec_boxes", []) if hasattr(page, "get") else page["rec_boxes"]
                for t, s, b in zip(texts, scores, boxes):
                    lines.append({"text": t, "confidence": float(s), "bbox": [float(x) for x in list(b)[:4]]})
        lines.sort(key=lambda l: (round(l["bbox"][1] / 12), l["bbox"][0]))
        return lines


def get_ocr() -> OCREngine | None:
    pref = settings.ocr_engine
    if pref == "none":
        return None

    def paddle():
        from paddleocr import PaddleOCR  # type: ignore
        return OCREngine("paddleocr", PaddleOCR(lang="en", use_doc_orientation_classify=False,
                                                use_doc_unwarping=False, use_textline_orientation=False))

    def rapid():
        from rapidocr_onnxruntime import RapidOCR  # type: ignore
        return OCREngine("rapidocr", RapidOCR())

    if pref == "paddleocr":
        return _load("paddleocr", paddle)
    if pref == "rapidocr":
        return _load("rapidocr", rapid)
    # auto: RapidOCR runs the PaddleOCR PP-OCR models on ONNX runtime - fast and dependable on CPU.
    return _load("rapidocr", rapid) or _load("paddleocr", paddle)


def get_asr():
    if settings.asr_engine == "none":
        return None

    def fw():
        from faster_whisper import WhisperModel  # type: ignore
        return WhisperModel(settings.whisper_model, device="cpu", compute_type="int8")

    return _load("faster-whisper", fw)


def get_nlp():
    if settings.nlp_engine == "none":
        return None

    def sp():
        import spacy  # type: ignore
        return spacy.load("en_core_web_sm")

    return _load("spacy", sp)


_VERSION_PKG = {"pdfplumber": "pdfplumber", "python-docx": "python-docx", "openpyxl": "openpyxl", "rfc5322-parser": None,
                "csv-parser": None, "text-parser": None, "chat-json-parser": None, "whatsapp-txt-parser": None,
                "rapidocr": "rapidocr-onnxruntime", "paddleocr": "paddleocr", "faster-whisper": "faster-whisper",
                "mbox-parser": None, "html-parser": None, "video": "av", "pdf-ocr": "pypdfium2"}


def tool_version(method: str) -> str:
    """Version string of the extractor behind a method name (built-in parsers report the app version)."""
    from importlib.metadata import PackageNotFoundError, version
    parts = [p for p in method.replace("+", ":").split(":") if p and p not in ("ocr", "asr")]
    out = []
    for p in parts or [method]:
        pkg = _VERSION_PKG.get(p, p)
        if pkg is None:
            out.append(f"{p}@evidencex-1.1")
            continue
        try:
            out.append(f"{p}@{version(pkg)}")
        except PackageNotFoundError:
            out.append(f"{p}@unknown")
    if "faster-whisper" in method:
        out.append(f"model={settings.whisper_model}")
    return " ".join(out)


def engine_status(probe: bool = False) -> dict:
    """Report which engines are available. ``probe`` forces loading (slow on first call)."""
    import importlib.util as u
    status = {
        "ocr": {"configured": settings.ocr_engine,
                "rapidocr_installed": u.find_spec("rapidocr_onnxruntime") is not None,
                "paddleocr_installed": u.find_spec("paddleocr") is not None},
        "asr": {"configured": settings.asr_engine, "faster_whisper_installed": u.find_spec("faster_whisper") is not None,
                "model": settings.whisper_model},
        "nlp": {"configured": settings.nlp_engine, "spacy_installed": u.find_spec("spacy") is not None},
        "llm": {"provider": settings.llm_provider, "model": settings.llm_model,
                "configured": bool(settings.anthropic_api_key) and settings.llm_provider == "anthropic",
                "sdk_installed": u.find_spec("anthropic") is not None},
        "errors": dict(_errors),
    }
    if probe:
        status["ocr"]["loaded"] = (get_ocr() or None) and get_ocr().name
        status["asr"]["loaded"] = get_asr() is not None
        status["nlp"]["loaded"] = get_nlp() is not None
        status["errors"] = dict(_errors)
    return status
