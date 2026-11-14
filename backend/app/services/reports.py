"""Report agent: builds the evidence-linked report content (report_content.py), stores the PDF, and
renders DOCX/HTML on demand from the same stored content (report_render.py)."""
from __future__ import annotations

import re

from sqlalchemy.orm import Session

from ..models import Case, Report
from ..storage import get_storage, make_key
from .intake import sha256_bytes
from .report_content import build
from .report_render import to_docx, to_html, to_pdf

_REDACT = [(re.compile(r"\b[A-Za-z0-9._%+-]+@([A-Za-z0-9.-]+\.[A-Za-z]{2,})\b"), lambda m: "•••@" + m.group(1)),
           (re.compile(r"(?<![\w\[-])(\+?\d[\d\s-]{6,}\d)(?![\w\]])"), lambda m: re.sub(r"\d(?=[\d\s-]{4})", "•", m.group(1)))]
_KEEP = {"sha256", "id", "evidence_id", "segment_id", "number"}


def redact(obj):
    """Mask personal identifiers (email local parts, phone/account digits) for controlled sharing.
    Hashes, evidence codes and citation targets are kept so the redacted report still links to sources."""
    if isinstance(obj, str):
        if re.fullmatch(r"[a-f0-9]{64}", obj) or re.fullmatch(r"\[EV-\d+ \|[^\]]*\]", obj):
            return obj
        for rx, fn in _REDACT:
            obj = rx.sub(fn, obj)
        return obj
    if isinstance(obj, list):
        return [redact(x) for x in obj]
    if isinstance(obj, dict):
        return {k: (v if k in _KEEP or (k == "text" and isinstance(v, str) and v.startswith("[EV-")) else redact(v)) for k, v in obj.items()}
    return obj


def build_case_content(db: Session, case: Case) -> dict:
    return build(db, case)


def generate_case_report(db: Session, case: Case, user=None, scenario: dict | None = None, kind: str = "case",
                         redact: bool = False) -> Report:
    content = build(db, case, scenario)
    if redact:
        content = globals()["redact"](content)
        content["redacted"] = True
    pdf = to_pdf(content)
    key = make_key(case.id, "reports", "r.pdf")
    get_storage().put(key, pdf)
    from .. import replay
    rep = Report(case_id=case.id, kind=kind, title=("Scenario test report — " if scenario else "Investigation report — ") + case.title,
                 storage_key=key, sha256=sha256_bytes(pdf), content=content, created_by=user.id if user else None)
    db.add(rep)
    db.flush()
    replay.emit(db, case.id, "report.generated", component="report", actor=user or "report agent",
                outputs=[replay.ref("report", rep.id, rep.title)], summary=f"{rep.title} (SHA-256 {rep.sha256[:16]}…)"
                + (" - redacted" if redact else ""))
    db.commit()
    return rep


def render_docx(rep: Report) -> bytes:
    return to_docx(rep.content)


def render_html(rep: Report) -> str:
    return to_html(rep.content)
