from __future__ import annotations

import json

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from fastapi.responses import Response
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..db import get_db
from ..models import Report, ScenarioDefinition, ScenarioRun, User
from ..scenarios import runner
from ..scenarios.builder import DATA_DIR
from ..scenarios.definitions import S
from ..security import get_current_user, require
from ..services import jobs
from ..storage import get_storage

router = APIRouter(prefix="/api/scenarios", tags=["scenario lab"])

CUSTOM_ID = "custom-dataset"


def _run_out(r: ScenarioRun, full=False) -> dict:
    out = {"id": r.id, "test_code": r.test_code, "scenario_id": r.scenario_id, "case_id": r.case_id, "status": r.status,
           "stage": r.stage, "progress": r.progress, "outcome": r.outcome, "outcome_reason": r.outcome_reason,
           "duration_ms": r.duration_ms, "started_at": r.started_at, "finished_at": r.finished_at, "report_id": r.report_id,
           "metrics": r.metrics, "expected_outcome": (r.evaluation or {}).get("expected_outcome"),
           "outcome_matches_expected": (r.evaluation or {}).get("outcome_matches_expected"), "error": r.error}
    if full:
        out["evaluation"] = r.evaluation
    return out


def _ensure_custom(db: Session):
    if not db.get(ScenarioDefinition, CUSTOM_ID):
        db.add(ScenarioDefinition(id=CUSTOM_ID, number=99, title="Custom dataset", summary="User-uploaded evidence set",
                                  briefing="Custom evidence dataset", difficulty="Custom", case_type="general", questions=[],
                                  files=[], ground_truth={}))
        db.commit()


@router.get("")
def list_scenarios(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    out = []
    for sd in db.scalars(select(ScenarioDefinition).where(ScenarioDefinition.id != CUSTOM_ID).order_by(ScenarioDefinition.number)):
        runs = list(db.scalars(select(ScenarioRun).where(ScenarioRun.scenario_id == sd.id).order_by(ScenarioRun.started_at.desc()).limit(5)))
        gt = sd.ground_truth or {}
        out.append({"id": sd.id, "number": sd.number, "title": sd.title, "summary": sd.summary, "difficulty": sd.difficulty,
                    "case_type": sd.case_type, "files": len(sd.files), "file_types": sorted({f["file"].rsplit(".", 1)[-1] for f in sd.files}),
                    "expected_findings": len(gt.get("findings", [])), "critical_findings": sum(1 for f in gt.get("findings", []) if f.get("critical")),
                    "expected_outcome": gt.get("expected_outcome"), "variant_of": sd.variant_of,
                    "last_run": _run_out(runs[0]) if runs else None, "run_count": len(runs)})
    return out


@router.get("/runs")
def list_runs(scenario_id: str | None = None, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    stmt = select(ScenarioRun).order_by(ScenarioRun.started_at.desc()).limit(200)
    if scenario_id:
        stmt = stmt.where(ScenarioRun.scenario_id == scenario_id)
    titles = {s.id: s.title for s in db.scalars(select(ScenarioDefinition))}
    return [{**_run_out(r), "scenario_title": titles.get(r.scenario_id, r.scenario_id)} for r in db.scalars(stmt)]


@router.get("/runs/compare")
def compare(ids: str, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    runs = [db.get(ScenarioRun, i) for i in ids.split(",")[:6]]
    runs = [r for r in runs if r]
    if not runs:
        raise HTTPException(404, "No runs found")
    keys = sorted({k for r in runs for k in (r.metrics or {})})
    return {"runs": [_run_out(r) for r in runs],
            "metrics": {k: [(r.metrics or {}).get(k) for r in runs] for k in keys},
            "findings": {r.id: [{"id": f["id"], "status": f["status"], "critical": f["critical"], "description": f["description"]}
                                for f in (r.evaluation or {}).get("findings", [])] for r in runs}}


@router.get("/runs/{run_id}")
def get_run(run_id: str, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    r = db.get(ScenarioRun, run_id)
    if not r:
        raise HTTPException(404, "Run not found")
    return _run_out(r, full=True)


@router.get("/runs/{run_id}/report.pdf")
def run_report(run_id: str, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    r = db.get(ScenarioRun, run_id)
    if not r or not r.report_id:
        raise HTTPException(404, "Report not available")
    rep = db.get(Report, r.report_id)
    return Response(get_storage().get(rep.storage_key), media_type="application/pdf",
                    headers={"Content-Disposition": f'inline; filename="{r.test_code}_scenario_report.pdf"'})


@router.get("/{scenario_id}")
def get_scenario(scenario_id: str, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    sd = db.get(ScenarioDefinition, scenario_id)
    if not sd or scenario_id == CUSTOM_ID:
        raise HTTPException(404, "Scenario not found")
    d = S.get(scenario_id, {})
    runs = list(db.scalars(select(ScenarioRun).where(ScenarioRun.scenario_id == sd.id).order_by(ScenarioRun.started_at.desc()).limit(20)))
    return {"id": sd.id, "number": sd.number, "title": sd.title, "summary": sd.summary, "briefing": sd.briefing,
            "difficulty": sd.difficulty, "case_type": sd.case_type, "questions": sd.questions, "files": sd.files,
            "planted_facts": d.get("planted_facts", []), "planted_inconsistencies": d.get("planted_inconsistencies", []),
            "expected_findings": [{k: f[k] for k in ("id", "description", "critical", "type")} for f in sd.ground_truth.get("findings", [])],
            "expected_outcome": sd.ground_truth.get("expected_outcome"), "dataset_sha256": sd.dataset_sha256,
            "runs": [_run_out(r) for r in runs]}


@router.get("/{scenario_id}/files/{name}")
def dataset_file(scenario_id: str, name: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    sd = db.get(ScenarioDefinition, scenario_id)
    if not sd or name not in {f["file"] for f in sd.files}:
        raise HTTPException(404, "File not in dataset")
    p = (DATA_DIR / scenario_id / name).resolve()
    if DATA_DIR.resolve() not in p.parents:
        raise HTTPException(400, "Invalid path")
    ext = name.rsplit(".", 1)[-1].lower()
    mime = {"png": "image/png", "jpg": "image/jpeg", "pdf": "application/pdf", "wav": "audio/wav"}.get(ext, "text/plain; charset=utf-8")
    if ext in ("docx", "xlsx"):
        mime = "application/octet-stream"
    return Response(p.read_bytes(), media_type=mime, headers={"X-Content-Type-Options": "nosniff",
                                                              "Content-Security-Policy": "sandbox; default-src 'none'"})


@router.post("/{scenario_id}/run", status_code=202)
def start(scenario_id: str, db: Session = Depends(get_db), user: User = Depends(require("scenario:run"))):
    if not db.get(ScenarioDefinition, scenario_id) or scenario_id == CUSTOM_ID:
        raise HTTPException(404, "Scenario not found")
    run = runner.create_run(db, scenario_id, user)
    jobs.submit(runner.execute, run.id, user.id)
    return _run_out(run)


@router.post("/custom/run", status_code=202)
async def custom(files: list[UploadFile] = File(...), ground_truth: str = Form(""), db: Session = Depends(get_db),
                 user: User = Depends(require("scenario:run"))):
    """Run the engine on an uploaded dataset. Optional ground_truth JSON uses the same schema as the built-in scenarios."""
    _ensure_custom(db)
    gt = None
    if ground_truth.strip():
        try:
            gt = json.loads(ground_truth)
            assert isinstance(gt.get("findings", []), list)
        except Exception:
            raise HTTPException(422, "ground_truth must be JSON with a 'findings' list (see docs/SCENARIOS.md)")
    payload = [(f.filename or "unnamed", await f.read()) for f in files[:50]]
    run = runner.create_run(db, CUSTOM_ID, user)
    jobs.submit(runner.execute, run.id, user.id, payload, gt)
    return _run_out(run)
