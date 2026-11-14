"""Pydantic contracts between agents. Every agent's output is validated before the next agent
runs; a malformed output fails that agent (recorded, retried) instead of flowing downstream."""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class _M(BaseModel):
    model_config = ConfigDict(extra="allow")


class Claim(_M):
    id: str
    text: str = Field(min_length=3)
    kind: Literal["observation", "inference"]
    citations: list[str]
    expect: list[str] = []
    temporal: bool = False
    source: Literal["engine", "llm", "manual"] = "engine"


class Candidate(_M):
    pattern: str
    statement: str = Field(min_length=10)
    score: float
    claims: list[Claim] = Field(min_length=1)
    assumptions: list[str] = []


class InvestigationOutput(_M):
    candidates: list[Candidate] = Field(min_length=1, max_length=5)
    limits: dict


class CounterItem(_M):
    id: str
    kind: Literal["contradiction", "alternative_explanation", "challenge", "weak_association", "missing_information"]
    text: str = Field(min_length=3)
    citations: list[str]
    strength: Literal["strong", "moderate"]
    source: Literal["engine", "llm"] = "engine"


class CounterOutput(_M):
    hypothesis_pattern: str
    items: list[CounterItem]
    mode: str


class VerificationItem(_M):
    id: str
    status: Literal["verified", "partially_verified", "inference", "rejected"]
    checks: list[str]


class VerificationOutput(_M):
    claims: list[VerificationItem]
    counter: list[VerificationItem]
    rejected: int
    total: int
    unsupported_claim_rate: float


class Review(_M):
    verdict: Literal["supported", "supported_with_reservations", "contested", "insufficient_evidence"]
    decision: Literal["SUPPORTED", "CONTRADICTED", "INCONCLUSIVE", "HOLD"]
    confidence_band: Literal["low", "moderate", "high"]
    reason: str
    independent_sources: int
    human_review_required: Literal[True]
