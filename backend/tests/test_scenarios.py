"""Scenario regression suite: every Scenario Lab dataset must produce its expected outcome
through the full shared pipeline (OCR + ASR included). Slow (~3-4 min on CPU).

Run:  pytest tests/test_scenarios.py -m scenario
"""
import os

import pytest

pytestmark = pytest.mark.scenario


@pytest.mark.parametrize("sid", ["s1-phishing", "s2-account-compromise", "s3-evidence-preservation",
                                 "s4-whistleblower-retaliation", "s5-marketplace-dispute", "s2h-sparse-account-records"])
def test_scenario_outcome(sid, client):
    if os.environ.get("ASR_ENGINE") == "none" and sid == "s1-phishing":
        pass  # voicemail finding is non-critical; outcome must still match
    from sqlalchemy import select
    from app.db import SessionLocal
    from app.models import ScenarioRun, User
    from app.scenarios.runner import create_run, execute
    db = SessionLocal()
    user = db.scalar(select(User).where(User.role == "admin"))
    run = create_run(db, sid, user)
    execute(db, run.id, user.id)
    db.expire_all()
    run = db.get(ScenarioRun, run.id)
    ev = run.evaluation
    missed = [f["id"] for f in ev["findings"] if f["critical"] and f["status"] != "found"]
    assert run.status == "completed", run.error
    assert not missed, f"critical findings missed: {missed}"
    assert not ev["violations"], ev["violations"]
    assert run.outcome == ev["expected_outcome"], run.outcome_reason
    assert ev["metrics"]["unsupported_claim_rate"]["value"] == 0
    assert ev["metrics"]["hash_verification_accuracy"]["value"] == 1.0
    db.close()
