"""Run Scenario Lab scenarios from the command line (same code path as the UI).

Usage:  python scripts/run_scenarios.py [scenario_id ...]
"""
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import select  # noqa: E402

from app.bootstrap import init_db  # noqa: E402
from app.db import SessionLocal  # noqa: E402
from app.models import ScenarioDefinition, ScenarioRun, User  # noqa: E402
from app.scenarios.runner import create_run, execute  # noqa: E402


def main(ids):
    init_db()
    db = SessionLocal()
    user = db.scalar(select(User).where(User.role == "admin"))
    ids = ids or [s.id for s in db.scalars(select(ScenarioDefinition).order_by(ScenarioDefinition.number))]
    summary = []
    for sid in ids:
        t = time.time()
        run = create_run(db, sid, user)
        execute(db, run.id, user.id)
        db.expire_all()
        run = db.get(ScenarioRun, run.id)
        ev = run.evaluation or {}
        print(f"\n=== {sid} [{run.test_code}] -> {run.outcome} (expected {ev.get('expected_outcome')}) in {time.time() - t:.1f}s")
        print("   ", run.outcome_reason)
        if run.error:
            print(run.error)
        for f in ev.get("findings", []):
            print(f"   {'*' if f['critical'] else ' '} {f['id']:4} {f['status']:8} {f['description'][:70]:70} | {str(f.get('matched_by'))[:80]}")
        for fp in ev.get("false_positives", []):
            print("    FP:", fp["code"], fp["description"][:120])
        for v in ev.get("violations", []):
            print("    VIOLATION:", v)
        print("    metrics:", json.dumps({k: v["display"] for k, v in ev.get("metrics", {}).items()}))
        summary.append((sid, run.outcome, ev.get("expected_outcome")))
    print("\nSUMMARY")
    for s in summary:
        print(f"  {s[0]:32} {s[1]:5} expected {s[2]}")


if __name__ == "__main__":
    main(sys.argv[1:])
