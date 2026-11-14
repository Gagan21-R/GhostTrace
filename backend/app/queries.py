"""Shared read helpers."""
from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from .models import AnalysisRun, Hypothesis


def latest_challenge_run_id(db: Session, case_id: str) -> str | None:
    return db.scalar(select(AnalysisRun.id).join(Hypothesis, Hypothesis.run_id == AnalysisRun.id)
                     .where(AnalysisRun.case_id == case_id).order_by(AnalysisRun.started_at.desc()).limit(1))


def latest_hypotheses(db: Session, case_id: str) -> list[Hypothesis]:
    """All candidates from the most recent challenge run, primary (rank 0) first."""
    rid = latest_challenge_run_id(db, case_id)
    if not rid:
        return []
    return list(db.scalars(select(Hypothesis).where(Hypothesis.run_id == rid).order_by(Hypothesis.rank)))


def primary_hypothesis(db: Session, case_id: str) -> Hypothesis | None:
    hs = latest_hypotheses(db, case_id)
    return hs[0] if hs else None
