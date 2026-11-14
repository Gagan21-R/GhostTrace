"""Load synthetic demo data through the real pipeline (intake -> processing -> challenge -> report).

Usage:
  python scripts/load_demo.py               # two polished demo cases: phishing + whistleblower
  python scripts/load_demo.py --scenarios   # also run every Scenario Lab simulation (adds ~4 min with OCR/ASR)

All data is synthetic. Nothing here hard-codes results: each case is processed exactly as a user upload would be.
"""
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import select  # noqa: E402

from app.agents import orchestrator as orch  # noqa: E402
from app.bootstrap import init_db  # noqa: E402
from app.db import SessionLocal  # noqa: E402
from app.models import AnalysisRun, Case, CaseMember, ScenarioDefinition, User  # noqa: E402
from app.scenarios.builder import DATA_DIR  # noqa: E402
from app.services.evidence_service import ingest  # noqa: E402
from app.services.reports import generate_case_report  # noqa: E402

DEMOS = [
    ("s1-phishing", "DEMO · KYC phishing and UPI payment fraud (A. Rao)", "fraud", "high"),
    ("s4-whistleblower-retaliation", "DEMO · Ethics complaint and subsequent access changes (P. Nair)", "corporate", "high"),
]


def load_case(db, user, sid, title, ctype, prio):
    sd = db.get(ScenarioDefinition, sid)
    if db.scalar(select(Case).where(Case.title == title)):
        print(f"  exists: {title}")
        return
    n = db.query(Case).count()
    case = Case(case_number=f"EVX-2026-{n + 1:04d}", title=title, case_type=ctype, priority=prio, description=sd.briefing,
                objective="; ".join(sd.questions), default_timezone="+05:30", created_by=user.id)
    db.add(case)
    db.flush()
    db.add(CaseMember(case_id=case.id, user_id=user.id, access="owner"))
    db.commit()
    for m in sd.files:
        ingest(db, case, user, m["file"], (DATA_DIR / sid / m["file"]).read_bytes(), category=m.get("category", ""), tags=m.get("tags", []),
               collection_source=m.get("collection_source") or "", collected_by=m.get("collected_by"))
    for kind, fn in (("processing", orch.run_processing), ("adversarial", orch.run_adversarial)):
        run = AnalysisRun(case_id=case.id, kind=kind, status="running", started_by=user.id)
        db.add(run)
        db.commit()
        orch.finish(db, run, fn(db, run, user), user)
        print(f"  {kind}: {run.status}")
    generate_case_report(db, case, user)
    print(f"  loaded {title}")


def main():
    init_db()
    db = SessionLocal()
    user = db.scalar(select(User).where(User.role == "admin"))
    t = time.time()
    for d in DEMOS:
        print(d[1])
        load_case(db, user, *d)
    if "--scenarios" in sys.argv:
        from app.scenarios.runner import create_run, execute
        for sd in db.scalars(select(ScenarioDefinition).where(ScenarioDefinition.id != "custom-dataset").order_by(ScenarioDefinition.number)):
            r = create_run(db, sd.id, user)
            execute(db, r.id, user.id)
            db.refresh(r)
            print(f"  scenario {sd.id}: {r.outcome}")
    print(f"done in {time.time() - t:.0f}s")


if __name__ == "__main__":
    main()
