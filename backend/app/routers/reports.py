from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response
from sqlalchemy import select
from sqlalchemy.orm import Session

from .. import audit
from ..db import get_db
from ..models import Report, User
from ..schemas import ReportIn
from ..security import accessible_case_ids, get_case_or_403, get_current_user, require
from ..services.reports import generate_case_report
from ..storage import get_storage

router = APIRouter(prefix="/api", tags=["reports"])


def _out(r: Report, full=False):
    o = {"id": r.id, "case_id": r.case_id, "kind": r.kind, "title": r.title, "sha256": r.sha256, "created_at": r.created_at,
         "created_by": r.created_by, "redacted": bool((r.content or {}).get("redacted")),
         "verdict": ((r.content or {}).get("hypothesis") or {}).get("verdict"), "stats": (r.content or {}).get("stats")}
    if full:
        o["content"] = r.content
    return o


@router.post("/cases/{case_id}/reports", status_code=201)
def generate(case_id: str, body: ReportIn | None = None, db: Session = Depends(get_db), user: User = Depends(require("report:generate"))):
    case = get_case_or_403(db, user, case_id)
    rep = generate_case_report(db, case, user, redact=bool(body and body.redact))
    audit.record(db, "report.generated", user=user, case_id=case.id, detail={"report_id": rep.id, "sha256": rep.sha256,
                                                                             "redacted": bool(body and body.redact)})
    return _out(rep)


@router.get("/reports")
def list_reports(case_id: str | None = None, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    ids = accessible_case_ids(db, user)
    stmt = select(Report).order_by(Report.created_at.desc()).limit(200)
    if ids is not None:
        stmt = stmt.where(Report.case_id.in_(ids))
    if case_id:
        stmt = stmt.where(Report.case_id == case_id)
    return [_out(r) for r in db.scalars(stmt)]


@router.get("/reports/{report_id}")
def get_report(report_id: str, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    r = db.get(Report, report_id)
    if not r:
        raise HTTPException(404, "Report not found")
    get_case_or_403(db, user, r.case_id)
    return _out(r, full=True)


@router.get("/reports/{report_id}/pdf")
def report_pdf(report_id: str, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    r = db.get(Report, report_id)
    if not r:
        raise HTTPException(404, "Report not found")
    get_case_or_403(db, user, r.case_id)
    audit.record(db, "report.exported", user=user, case_id=r.case_id, detail={"report_id": r.id})
    return Response(get_storage().get(r.storage_key), media_type="application/pdf",
                    headers={"Content-Disposition": f'attachment; filename="GhostTrace_report_{r.id[:8]}.pdf"',
                             "Cache-Control": "private, no-store"})


@router.get("/reports/{report_id}/docx")
def report_docx(report_id: str, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    from ..services.reports import render_docx
    r = db.get(Report, report_id)
    if not r:
        raise HTTPException(404, "Report not found")
    get_case_or_403(db, user, r.case_id)
    audit.record(db, "report.exported", user=user, case_id=r.case_id, detail={"report_id": r.id, "format": "docx"})
    return Response(render_docx(r), media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                    headers={"Content-Disposition": f'attachment; filename="GhostTrace_report_{r.id[:8]}.docx"', "Cache-Control": "private, no-store"})


@router.get("/reports/{report_id}/html")
def report_html(report_id: str, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    from ..services.reports import render_html
    r = db.get(Report, report_id)
    if not r:
        raise HTTPException(404, "Report not found")
    get_case_or_403(db, user, r.case_id)
    audit.record(db, "report.exported", user=user, case_id=r.case_id, detail={"report_id": r.id, "format": "html"})
    return Response(render_html(r), media_type="text/html; charset=utf-8",
                    headers={"Content-Disposition": f'attachment; filename="GhostTrace_report_{r.id[:8]}.html"', "Cache-Control": "private, no-store",
                             "Content-Security-Policy": "default-src 'none'; style-src 'unsafe-inline'"})
