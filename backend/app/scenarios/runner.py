"""Scenario Lab runner: creates a fresh case, ingests the dataset through the normal intake
path, runs the processing and adversarial graphs, evaluates against ground truth and
generates the scenario report. Every run is stored for history and comparison."""
from __future__ import annotations

import json
import time
import traceback
from pathlib import Path

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from .. import audit
from ..agents import orchestrator as orch
from ..models import AnalysisRun, Case, CaseMember, ScenarioDefinition, ScenarioRun, User, utcnow
from ..services.evidence_service import ingest
from ..services.reports import generate_case_report
from .builder import DATA_DIR, build_all
from .definitions import S
from .evaluator import evaluate


def sync_definitions(db: Session):
    manifests = build_all(force=False)
    for sid, d in S.items():
        man = manifests.get(sid, [])
        import hashlib
        ds = hashlib.sha256(json.dumps([m["sha256"] for m in man]).encode()).hexdigest()
        row = db.get(ScenarioDefinition, sid) or ScenarioDefinition(id=sid)
        row.number, row.title, row.summary, row.briefing = d["number"], d["title"], d["summary"], d["briefing"]
        row.difficulty, row.case_type, row.questions = d["difficulty"], d["case_type"], d["questions"]
        row.files = man
        row.ground_truth = {**d["ground_truth"], "planted_facts": d["planted_facts"], "planted_inconsistencies": d["planted_inconsistencies"]}
        row.dataset_sha256, row.variant_of = ds, d.get("variant_of")
        db.merge(row)
    db.commit()


def _case_number(db: Session, prefix="SCN") -> str:
    n = db.scalar(select(func.count()).select_from(Case)) or 0
    return f"{prefix}-{2026}-{n + 1:04d}"


def create_run(db: Session, scenario_id: str, user: User) -> ScenarioRun:
    n = db.scalar(select(func.count()).select_from(ScenarioRun)) or 0
    run = ScenarioRun(scenario_id=scenario_id, test_code=f"T-{n + 1:04d}", triggered_by=user.id, status="queued", stage="queued")
    db.add(run)
    db.commit()
    return run


def execute(db: Session, run_id: str, user_id: str, custom_files: list[tuple[str, bytes]] | None = None,
            custom_gt: dict | None = None):
    run = db.get(ScenarioRun, run_id)
    user = db.get(User, user_id)
    sd = db.get(ScenarioDefinition, run.scenario_id)
    t0 = time.perf_counter()
    run.status, run.stage, run.progress, run.started_at = "running", "creating case", 0.02, utcnow()
    db.commit()

    def cb(stage, p):
        run.stage, run.progress = stage, round(p, 3)
        db.commit()

    runs: list[AnalysisRun] = []
    try:
        title = f"Scenario Lab · {sd.title}" if sd else "Scenario Lab · Custom dataset"
        case = Case(case_number=_case_number(db), title=f"{title} · {run.test_code}", case_type=sd.case_type if sd else "general",
                    description=sd.briefing if sd else "Custom evidence dataset uploaded to the Scenario Lab",
                    objective="; ".join(sd.questions) if sd else "", is_scenario=True, created_by=user.id,
                    default_timezone="+05:30" if sd else "UTC")
        db.add(case)
        db.flush()
        db.add(CaseMember(case_id=case.id, user_id=user.id, access="owner"))
        run.case_id = case.id
        db.commit()
        audit.record(db, "scenario.run_started", user=user, case_id=case.id, detail={"scenario": run.scenario_id, "test": run.test_code})

        cb("ingesting evidence", 0.05)
        if custom_files is not None:
            items = [(name, data, {"category": "uncategorised", "collection_source": "Uploaded to Scenario Lab", "tags": []}) for name, data in custom_files]
        else:
            d = DATA_DIR / sd.id
            items = [(m["file"], (d / m["file"]).read_bytes(), m) for m in sd.files]
        for name, data, m in items:
            ingest(db, case, user, name, data, category=m.get("category", "uncategorised"), tags=m.get("tags", []),
                   collection_source=m.get("collection_source") or "", collected_by=m.get("collected_by"),
                   collected_at=None)

        prun = AnalysisRun(case_id=case.id, kind="processing", status="running", started_by=user.id)
        db.add(prun)
        db.commit()
        runs.append(prun)
        st = orch.run_processing(db, prun, user, cb, span=(0.1, 0.7))
        orch.finish(db, prun, st, user)

        arun = AnalysisRun(case_id=case.id, kind="adversarial", status="running", started_by=user.id)
        db.add(arun)
        db.commit()
        runs.append(arun)
        st2 = orch.run_adversarial(db, arun, user, cb, span=(0.7, 0.9))
        orch.finish(db, arun, st2, user)

        cb("evaluating against ground truth", 0.92)
        duration = int((time.perf_counter() - t0) * 1000)
        gt = custom_gt if custom_files is not None else sd.ground_truth
        if gt:
            ev = evaluate(db, case.id, gt, runs, duration)
        else:
            from ..models import Hypothesis
            from ..queries import primary_hypothesis
            hyp = primary_hypothesis(db, case.id)
            failed = [r for r in runs if r.status == "failed"]
            outcome = "FAIL" if failed else ("HOLD" if not hyp or hyp.decision != "SUPPORTED" else "PASS")
            ev = {"outcome": outcome, "outcome_reason": "No ground truth supplied - outcome reflects processing status and reviewer verdict only; "
                  "accuracy metrics are not computed.", "expected_outcome": None, "outcome_matches_expected": None, "findings": [],
                  "false_positives": [], "violations": [], "metrics": {"processing_time": {"value": duration, "display": f"{duration / 1000:.1f} s",
                                                                                          "basis": "wall-clock"}},
                  "errors": [f"{r.kind}: {r.error}" for r in failed], "blocked": [], "recommendations": [], "actual": {}}
        run.outcome, run.outcome_reason = ev["outcome"], ev["outcome_reason"]
        run.evaluation = ev
        run.metrics = {k: v["value"] for k, v in ev["metrics"].items()}
        run.duration_ms = duration

        cb("generating report", 0.96)
        rep = generate_case_report(db, case, user, scenario={
            "scenario": sd.title if sd else "Custom dataset", "test_code": run.test_code, "executed": utcnow().strftime("%Y-%m-%d %H:%M UTC"),
            "outcome": ev["outcome"], "outcome_reason": ev["outcome_reason"], "expected_outcome": ev.get("expected_outcome") or "—",
            "duration_ms": duration, "dataset": f"{len(items)} files" + (f", dataset SHA-256 {sd.dataset_sha256[:16]}…" if sd else ""),
            "metrics": ev["metrics"], "findings": ev["findings"], "false_positives": ev["false_positives"],
            "violations": ev["violations"], "recommendations": ev["recommendations"], "errors": ev["errors"]}, kind="scenario")
        run.report_id = rep.id
        run.status, run.stage, run.progress, run.finished_at = "completed", "done", 1.0, utcnow()
        case.status = "completed"
        db.commit()
        audit.record(db, "scenario.run_completed", user=user, case_id=case.id,
                     detail={"scenario": run.scenario_id, "test": run.test_code, "outcome": run.outcome})
    except Exception as e:
        db.rollback()
        run = db.get(ScenarioRun, run_id)
        run.status, run.stage, run.outcome = "failed", "failed", "FAIL"
        run.error = f"{type(e).__name__}: {e}\n{traceback.format_exc()[-1500:]}"
        run.outcome_reason = "Run aborted with an error before evaluation completed."
        run.finished_at = utcnow()
        run.duration_ms = int((time.perf_counter() - t0) * 1000)
        db.commit()
