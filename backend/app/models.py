"""Relational schema for EVIDENCE-X.

Every investigation artefact carries a ``case_id`` so access control can be enforced at
case level. Audit events are append-only and hash-chained (see ``audit.py``).
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import (JSON, Boolean, DateTime, Float, ForeignKey, Integer, String, Text,
                        TypeDecorator, UniqueConstraint, event)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .db import Base


class UTCDateTime(TypeDecorator):
    """Always returns timezone-aware UTC datetimes (SQLite drops tzinfo on read)."""
    impl = DateTime(timezone=True)
    cache_ok = True

    def process_bind_param(self, value, dialect):
        if value is not None and value.tzinfo is None:
            value = value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc) if value is not None else None

    def process_result_value(self, value, dialect):
        if value is not None and value.tzinfo is None:
            value = value.replace(tzinfo=timezone.utc)
        return value


def _uuid() -> str:
    return uuid.uuid4().hex


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


ROLES = ("admin", "investigator", "reviewer", "viewer")
ROLE_PERMISSIONS: dict[str, set[str]] = {
    "admin": {"case:create", "case:edit", "case:archive", "evidence:upload", "evidence:delete", "analysis:run",
              "review:decide", "report:generate", "user:manage", "scenario:run", "audit:view", "case:all"},
    "investigator": {"case:create", "case:edit", "case:archive", "evidence:upload", "analysis:run", "review:decide",
                     "report:generate", "scenario:run", "audit:view"},
    "reviewer": {"review:decide", "report:generate", "audit:view"},
    "viewer": set(),
}


class User(Base):
    __tablename__ = "users"
    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_uuid)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    full_name: Mapped[str] = mapped_column(String(255))
    password_hash: Mapped[str] = mapped_column(String(255))
    role: Mapped[str] = mapped_column(String(32), default="investigator")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utcnow)
    last_login_at: Mapped[datetime | None] = mapped_column(UTCDateTime(), nullable=True)


class RevokedToken(Base):
    """JWT denylist so logout invalidates a token before it expires."""
    __tablename__ = "revoked_tokens"
    jti: Mapped[str] = mapped_column(String(64), primary_key=True)
    user_id: Mapped[str] = mapped_column(String(32), index=True)
    revoked_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utcnow)
    expires_at: Mapped[datetime] = mapped_column(UTCDateTime())


class Case(Base):
    __tablename__ = "cases"
    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_uuid)
    case_number: Mapped[str] = mapped_column(String(32), unique=True, index=True)
    title: Mapped[str] = mapped_column(String(255))
    description: Mapped[str] = mapped_column(Text, default="")
    objective: Mapped[str] = mapped_column(Text, default="")
    case_type: Mapped[str] = mapped_column(String(64), default="general")
    status: Mapped[str] = mapped_column(String(32), default="active")  # active | completed | archived
    priority: Mapped[str] = mapped_column(String(16), default="medium")
    default_timezone: Mapped[str] = mapped_column(String(8), default="UTC")  # applied to timestamps that state no timezone
    # Evidence is never sent to an external AI provider unless the case owner explicitly authorises it.
    allow_external_ai: Mapped[bool] = mapped_column(Boolean, default=False)
    is_scenario: Mapped[bool] = mapped_column(Boolean, default=False)
    created_by: Mapped[str | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utcnow, onupdate=utcnow)

    members: Mapped[list["CaseMember"]] = relationship(back_populates="case", cascade="all, delete-orphan")
    evidence: Mapped[list["Evidence"]] = relationship(back_populates="case", cascade="all, delete-orphan")


class CaseMember(Base):
    __tablename__ = "case_members"
    __table_args__ = (UniqueConstraint("case_id", "user_id"),)
    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_uuid)
    case_id: Mapped[str] = mapped_column(ForeignKey("cases.id", ondelete="CASCADE"), index=True)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    access: Mapped[str] = mapped_column(String(16), default="editor")  # owner | editor | viewer
    case: Mapped[Case] = relationship(back_populates="members")


class Evidence(Base):
    __tablename__ = "evidence"
    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_uuid)
    case_id: Mapped[str] = mapped_column(ForeignKey("cases.id", ondelete="CASCADE"), index=True)
    evidence_code: Mapped[str] = mapped_column(String(32), index=True)  # human-friendly e.g. EV-003
    original_filename: Mapped[str] = mapped_column(String(512))
    storage_key: Mapped[str] = mapped_column(String(512))
    mime_type: Mapped[str] = mapped_column(String(128))
    detected_type: Mapped[str] = mapped_column(String(32))  # image|pdf|docx|text|spreadsheet|email|chat|audio|video|unknown
    size_bytes: Mapped[int] = mapped_column(Integer)
    sha256: Mapped[str] = mapped_column(String(64), index=True)
    category: Mapped[str] = mapped_column(String(64), default="uncategorised")
    tags: Mapped[list] = mapped_column(JSON, default=list)
    collection_source: Mapped[str] = mapped_column(Text, default="")
    collected_at: Mapped[str | None] = mapped_column(String(64), nullable=True)  # as reported by collector
    collected_by: Mapped[str | None] = mapped_column(String(255), nullable=True)
    uploaded_by: Mapped[str | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    intake_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utcnow)
    status: Mapped[str] = mapped_column(String(32), default="uploaded")  # uploaded|processing|processed|failed|unsupported
    processing_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    file_metadata: Mapped[dict] = mapped_column(JSON, default=dict)
    last_verified_at: Mapped[datetime | None] = mapped_column(UTCDateTime(), nullable=True)
    last_verification: Mapped[str | None] = mapped_column(String(16), nullable=True)  # match | mismatch | missing
    legal_hold: Mapped[bool] = mapped_column(Boolean, default=False)
    duplicate_of: Mapped[str | None] = mapped_column(String(32), nullable=True)  # evidence id with identical SHA-256
    perceptual_hash: Mapped[str | None] = mapped_column(String(32), nullable=True)  # dHash for images (near-duplicates)
    deleted_at: Mapped[datetime | None] = mapped_column(UTCDateTime(), nullable=True)

    case: Mapped[Case] = relationship(back_populates="evidence")
    derivatives: Mapped[list["EvidenceDerivative"]] = relationship(cascade="all, delete-orphan")


class EvidenceDerivative(Base):
    """Processed outputs (OCR text, transcripts, previews). Originals are never modified."""
    __tablename__ = "evidence_derivatives"
    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_uuid)
    evidence_id: Mapped[str] = mapped_column(ForeignKey("evidence.id", ondelete="CASCADE"), index=True)
    kind: Mapped[str] = mapped_column(String(32))  # extracted_text | ocr_text | transcript | preview
    storage_key: Mapped[str] = mapped_column(String(512))
    sha256: Mapped[str] = mapped_column(String(64))
    method: Mapped[str] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utcnow)


class ExtractedSegment(Base):
    """One addressable unit of extracted content (a page, message, email header, transcript chunk, row)."""
    __tablename__ = "extracted_segments"
    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_uuid)
    case_id: Mapped[str] = mapped_column(ForeignKey("cases.id", ondelete="CASCADE"), index=True)
    evidence_id: Mapped[str] = mapped_column(ForeignKey("evidence.id", ondelete="CASCADE"), index=True)
    seq: Mapped[int] = mapped_column(Integer, default=0)
    locator: Mapped[str] = mapped_column(String(128))  # "page 2", "msg 14", "00:05-00:12", "row 3", "header"
    kind: Mapped[str] = mapped_column(String(32))
    author: Mapped[str | None] = mapped_column(String(255), nullable=True)
    timestamp_raw: Mapped[str | None] = mapped_column(String(128), nullable=True)
    text: Mapped[str] = mapped_column(Text, default="")
    method: Mapped[str] = mapped_column(String(64))
    confidence: Mapped[float] = mapped_column(Float, default=1.0)
    data: Mapped[dict] = mapped_column(JSON, default=dict)


class Entity(Base):
    __tablename__ = "entities"
    __table_args__ = (UniqueConstraint("case_id", "type", "normalized"),)
    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_uuid)
    case_id: Mapped[str] = mapped_column(ForeignKey("cases.id", ondelete="CASCADE"), index=True)
    type: Mapped[str] = mapped_column(String(32), index=True)
    value: Mapped[str] = mapped_column(String(512))
    normalized: Mapped[str] = mapped_column(String(512))
    confidence: Mapped[float] = mapped_column(Float, default=1.0)
    attributes: Mapped[dict] = mapped_column(JSON, default=dict)


class EntityMention(Base):
    __tablename__ = "entity_mentions"
    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_uuid)
    case_id: Mapped[str] = mapped_column(ForeignKey("cases.id", ondelete="CASCADE"), index=True)
    entity_id: Mapped[str] = mapped_column(ForeignKey("entities.id", ondelete="CASCADE"), index=True)
    evidence_id: Mapped[str] = mapped_column(ForeignKey("evidence.id", ondelete="CASCADE"), index=True)
    segment_id: Mapped[str | None] = mapped_column(ForeignKey("extracted_segments.id", ondelete="CASCADE"), nullable=True)
    snippet: Mapped[str] = mapped_column(Text, default="")
    method: Mapped[str] = mapped_column(String(64))
    confidence: Mapped[float] = mapped_column(Float, default=1.0)


class Relationship(Base):
    __tablename__ = "relationships"
    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_uuid)
    case_id: Mapped[str] = mapped_column(ForeignKey("cases.id", ondelete="CASCADE"), index=True)
    source_entity_id: Mapped[str] = mapped_column(ForeignKey("entities.id", ondelete="CASCADE"))
    target_entity_id: Mapped[str] = mapped_column(ForeignKey("entities.id", ondelete="CASCADE"))
    rel_type: Mapped[str] = mapped_column(String(64))
    basis: Mapped[str] = mapped_column(String(16))  # observed | inferred
    weight: Mapped[float] = mapped_column(Float, default=1.0)
    evidence_ids: Mapped[list] = mapped_column(JSON, default=list)
    segment_ids: Mapped[list] = mapped_column(JSON, default=list)
    description: Mapped[str] = mapped_column(Text, default="")
    confidence: Mapped[float] = mapped_column(Float, default=1.0)


class TimelineEvent(Base):
    __tablename__ = "timeline_events"
    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_uuid)
    case_id: Mapped[str] = mapped_column(ForeignKey("cases.id", ondelete="CASCADE"), index=True)
    evidence_id: Mapped[str] = mapped_column(ForeignKey("evidence.id", ondelete="CASCADE"), index=True)
    segment_id: Mapped[str | None] = mapped_column(ForeignKey("extracted_segments.id", ondelete="CASCADE"), nullable=True)
    occurred_at: Mapped[datetime | None] = mapped_column(UTCDateTime(), nullable=True)
    timestamp_raw: Mapped[str | None] = mapped_column(String(128), nullable=True)
    timestamp_kind: Mapped[str] = mapped_column(String(32))  # source_reported | metadata_derived | estimated | unknown
    event_type: Mapped[str] = mapped_column(String(64))
    title: Mapped[str] = mapped_column(String(512))
    description: Mapped[str] = mapped_column(Text, default="")
    actors: Mapped[list] = mapped_column(JSON, default=list)
    entity_ids: Mapped[list] = mapped_column(JSON, default=list)
    data: Mapped[dict] = mapped_column(JSON, default=dict)
    conflict: Mapped[bool] = mapped_column(Boolean, default=False)


class Contradiction(Base):
    __tablename__ = "contradictions"
    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_uuid)
    code: Mapped[str] = mapped_column(String(32))
    case_id: Mapped[str] = mapped_column(ForeignKey("cases.id", ondelete="CASCADE"), index=True)
    category: Mapped[str] = mapped_column(String(64))
    field: Mapped[str] = mapped_column(String(64))
    key: Mapped[str] = mapped_column(String(255), default="")  # what the two records are about (e.g. order id)
    description: Mapped[str] = mapped_column(Text)
    source_a: Mapped[dict] = mapped_column(JSON)  # {evidence_id, evidence_code, filename, locator, excerpt, value}
    source_b: Mapped[dict] = mapped_column(JSON)
    reason: Mapped[str] = mapped_column(Text)
    confidence: Mapped[float] = mapped_column(Float)
    priority: Mapped[str] = mapped_column(String(16), default="medium")  # high | medium | low
    classification: Mapped[str] = mapped_column(String(32), default="potential")  # direct|potential|contextual|unresolved
    same_event_basis: Mapped[str] = mapped_column(Text, default="")
    suggested_action: Mapped[str] = mapped_column(Text)
    review_status: Mapped[str] = mapped_column(String(16), default="pending")  # pending|confirmed|dismissed
    reviewer_note: Mapped[str | None] = mapped_column(Text, nullable=True)
    reviewed_by: Mapped[str | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utcnow)


class EvidenceGap(Base):
    __tablename__ = "evidence_gaps"
    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_uuid)
    code: Mapped[str] = mapped_column(String(32))
    case_id: Mapped[str] = mapped_column(ForeignKey("cases.id", ondelete="CASCADE"), index=True)
    category: Mapped[str] = mapped_column(String(64))
    key: Mapped[str] = mapped_column(String(255), default="")
    description: Mapped[str] = mapped_column(Text)
    related: Mapped[list] = mapped_column(JSON, default=list)  # [{evidence_id, evidence_code, locator, excerpt}]
    checklist: Mapped[list] = mapped_column(JSON, default=list)
    why_it_matters: Mapped[str] = mapped_column(Text, default="")
    severity: Mapped[str] = mapped_column(String(16), default="medium")
    review_status: Mapped[str] = mapped_column(String(16), default="open")  # open|resolved|dismissed
    reviewer_note: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utcnow)


class AnalysisRun(Base):
    __tablename__ = "analysis_runs"
    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_uuid)
    case_id: Mapped[str] = mapped_column(ForeignKey("cases.id", ondelete="CASCADE"), index=True)
    kind: Mapped[str] = mapped_column(String(32))  # processing | adversarial
    status: Mapped[str] = mapped_column(String(16), default="queued")  # queued|running|completed|failed
    progress: Mapped[float] = mapped_column(Float, default=0.0)
    stage: Mapped[str] = mapped_column(String(128), default="queued")
    log: Mapped[list] = mapped_column(JSON, default=list)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    started_by: Mapped[str | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    started_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utcnow)
    finished_at: Mapped[datetime | None] = mapped_column(UTCDateTime(), nullable=True)


class AgentExecution(Base):
    __tablename__ = "agent_executions"
    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_uuid)
    run_id: Mapped[str] = mapped_column(ForeignKey("analysis_runs.id", ondelete="CASCADE"), index=True)
    case_id: Mapped[str] = mapped_column(ForeignKey("cases.id", ondelete="CASCADE"), index=True)
    agent: Mapped[str] = mapped_column(String(64))
    seq: Mapped[int] = mapped_column(Integer, default=0)
    status: Mapped[str] = mapped_column(String(16))
    mode: Mapped[str] = mapped_column(String(32))  # deterministic | llm-augmented | llm-unavailable-fallback
    attempts: Mapped[int] = mapped_column(Integer, default=1)
    output: Mapped[dict] = mapped_column(JSON, default=dict)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    duration_ms: Mapped[int] = mapped_column(Integer, default=0)
    started_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utcnow)


class Hypothesis(Base):
    __tablename__ = "hypotheses"
    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_uuid)
    case_id: Mapped[str] = mapped_column(ForeignKey("cases.id", ondelete="CASCADE"), index=True)
    run_id: Mapped[str] = mapped_column(ForeignKey("analysis_runs.id", ondelete="CASCADE"), index=True)
    statement: Mapped[str] = mapped_column(Text)
    pattern: Mapped[str] = mapped_column(String(64))
    supporting: Mapped[list] = mapped_column(JSON, default=list)
    counterevidence: Mapped[list] = mapped_column(JSON, default=list)
    alternatives: Mapped[list] = mapped_column(JSON, default=list)
    assumptions: Mapped[list] = mapped_column(JSON, default=list)
    missing_information: Mapped[list] = mapped_column(JSON, default=list)
    verification: Mapped[dict] = mapped_column(JSON, default=dict)
    assessment: Mapped[dict] = mapped_column(JSON, default=dict)
    decision: Mapped[str] = mapped_column(String(16), default="HOLD")  # SUPPORTED | CONTRADICTED | INCONCLUSIVE | HOLD
    rank: Mapped[int] = mapped_column(Integer, default=0)  # 0 = primary candidate
    verdict: Mapped[str] = mapped_column(String(32), default="needs_review")  # supported|contested|insufficient|rejected
    human_review_status: Mapped[str] = mapped_column(String(16), default="pending")
    human_review_note: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utcnow)


class Report(Base):
    __tablename__ = "reports"
    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_uuid)
    case_id: Mapped[str] = mapped_column(ForeignKey("cases.id", ondelete="CASCADE"), index=True)
    kind: Mapped[str] = mapped_column(String(16))  # case | scenario
    title: Mapped[str] = mapped_column(String(255))
    storage_key: Mapped[str] = mapped_column(String(512))
    sha256: Mapped[str] = mapped_column(String(64))
    content: Mapped[dict] = mapped_column(JSON, default=dict)
    created_by: Mapped[str | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utcnow)


class AuditEvent(Base):
    """Append-only, hash-chained audit trail. Updates/deletes are blocked at ORM level."""
    __tablename__ = "audit_events"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    ts: Mapped[datetime] = mapped_column(UTCDateTime(), default=utcnow, index=True)
    user_id: Mapped[str | None] = mapped_column(String(32), nullable=True)
    user_email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    case_id: Mapped[str | None] = mapped_column(String(32), nullable=True, index=True)
    evidence_id: Mapped[str | None] = mapped_column(String(32), nullable=True, index=True)
    action: Mapped[str] = mapped_column(String(64), index=True)
    detail: Mapped[dict] = mapped_column(JSON, default=dict)
    prev_hash: Mapped[str] = mapped_column(String(64))
    hash: Mapped[str] = mapped_column(String(64))


@event.listens_for(AuditEvent, "before_update")
def _no_audit_update(*_):
    raise PermissionError("Audit events are append-only")


@event.listens_for(AuditEvent, "before_delete")
def _no_audit_delete(*_):
    raise PermissionError("Audit events are append-only")


class ScenarioDefinition(Base):
    __tablename__ = "scenario_definitions"
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    number: Mapped[int] = mapped_column(Integer)
    title: Mapped[str] = mapped_column(String(255))
    summary: Mapped[str] = mapped_column(Text)
    briefing: Mapped[str] = mapped_column(Text)
    difficulty: Mapped[str] = mapped_column(String(16))
    case_type: Mapped[str] = mapped_column(String(64))
    questions: Mapped[list] = mapped_column(JSON, default=list)
    files: Mapped[list] = mapped_column(JSON, default=list)
    ground_truth: Mapped[dict] = mapped_column(JSON, default=dict)
    dataset_sha256: Mapped[str] = mapped_column(String(64), default="")
    variant_of: Mapped[str | None] = mapped_column(String(64), nullable=True)


class ScenarioRun(Base):
    __tablename__ = "scenario_runs"
    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_uuid)
    test_code: Mapped[str] = mapped_column(String(32), index=True)
    scenario_id: Mapped[str] = mapped_column(ForeignKey("scenario_definitions.id"), index=True)
    case_id: Mapped[str | None] = mapped_column(ForeignKey("cases.id", ondelete="SET NULL"), nullable=True)
    status: Mapped[str] = mapped_column(String(16), default="queued")
    stage: Mapped[str] = mapped_column(String(128), default="queued")
    progress: Mapped[float] = mapped_column(Float, default=0.0)
    outcome: Mapped[str | None] = mapped_column(String(8), nullable=True)  # PASS | FAIL | HOLD
    outcome_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    evaluation: Mapped[dict] = mapped_column(JSON, default=dict)
    metrics: Mapped[dict] = mapped_column(JSON, default=dict)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    duration_ms: Mapped[int] = mapped_column(Integer, default=0)
    report_id: Mapped[str | None] = mapped_column(ForeignKey("reports.id", ondelete="SET NULL"), nullable=True)
    triggered_by: Mapped[str | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    started_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utcnow)
    finished_at: Mapped[datetime | None] = mapped_column(UTCDateTime(), nullable=True)


# ============================================================== flagship intelligence (session 3)
class EvidenceDependency(Base):
    """Evidence DNA: how two evidence items relate. Duplicated/derived/shared-source items are NOT
    independent corroboration of each other."""
    __tablename__ = "evidence_dependencies"
    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_uuid)
    case_id: Mapped[str] = mapped_column(ForeignKey("cases.id", ondelete="CASCADE"), index=True)
    evidence_a_id: Mapped[str] = mapped_column(ForeignKey("evidence.id", ondelete="CASCADE"), index=True)
    evidence_b_id: Mapped[str] = mapped_column(ForeignKey("evidence.id", ondelete="CASCADE"), index=True)
    relation: Mapped[str] = mapped_column(String(24))  # duplicate|near_duplicate|derived|shared_source|independent|uncertain
    direction: Mapped[str] = mapped_column(String(128), default="")
    matches: Mapped[list] = mapped_column(JSON, default=list)  # [{attribute, value, a:{locator,excerpt}, b:{...}}]
    text_similarity: Mapped[float] = mapped_column(Float, default=0.0)
    confidence: Mapped[float] = mapped_column(Float, default=0.5)
    explanation: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utcnow)


class IntegrityFinding(Base):
    """Integrity inspection indicators for human review - never automatic proof of tampering."""
    __tablename__ = "integrity_findings"
    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_uuid)
    case_id: Mapped[str] = mapped_column(ForeignKey("cases.id", ondelete="CASCADE"), index=True)
    evidence_id: Mapped[str] = mapped_column(ForeignKey("evidence.id", ondelete="CASCADE"), index=True)
    check: Mapped[str] = mapped_column(String(48))
    severity: Mapped[str] = mapped_column(String(16))  # info | low | medium | high
    observation: Mapped[str] = mapped_column(Text)
    detail: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utcnow)


class HypothesisEvidence(Base):
    __tablename__ = "hypothesis_evidence"
    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_uuid)
    hypothesis_id: Mapped[str] = mapped_column(ForeignKey("hypotheses.id", ondelete="CASCADE"), index=True)
    case_id: Mapped[str] = mapped_column(ForeignKey("cases.id", ondelete="CASCADE"), index=True)
    evidence_id: Mapped[str] = mapped_column(ForeignKey("evidence.id", ondelete="CASCADE"))
    segment_id: Mapped[str | None] = mapped_column(String(32), nullable=True)
    role: Mapped[str] = mapped_column(String(16))  # supports | challenges
    claim_id: Mapped[str] = mapped_column(String(16))


class VerificationResult(Base):
    __tablename__ = "verification_results"
    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_uuid)
    case_id: Mapped[str] = mapped_column(ForeignKey("cases.id", ondelete="CASCADE"), index=True)
    hypothesis_id: Mapped[str | None] = mapped_column(ForeignKey("hypotheses.id", ondelete="CASCADE"), nullable=True, index=True)
    item_id: Mapped[str] = mapped_column(String(16))
    item_text: Mapped[str] = mapped_column(Text)
    source: Mapped[str] = mapped_column(String(16), default="engine")  # engine | llm | manual
    status: Mapped[str] = mapped_column(String(24))  # verified | partially_verified | inference | rejected
    checks: Mapped[list] = mapped_column(JSON, default=list)
    citations: Mapped[list] = mapped_column(JSON, default=list)
    created_by: Mapped[str | None] = mapped_column(String(32), nullable=True)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utcnow)


class EvidenceRecommendation(Base):
    """Missing Evidence Predictor output: what to collect next and why."""
    __tablename__ = "evidence_recommendations"
    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_uuid)
    case_id: Mapped[str] = mapped_column(ForeignKey("cases.id", ondelete="CASCADE"), index=True)
    run_id: Mapped[str | None] = mapped_column(String(32), nullable=True)
    rank: Mapped[int] = mapped_column(Integer)
    question: Mapped[str] = mapped_column(Text)
    recommended_evidence: Mapped[str] = mapped_column(Text)
    why_it_matters: Mapped[str] = mapped_column(Text)
    distinguishes: Mapped[list] = mapped_column(JSON, default=list)
    could_confirm: Mapped[str] = mapped_column(Text, default="")
    could_disprove: Mapped[str] = mapped_column(Text, default="")
    authorised_source: Mapped[str] = mapped_column(Text, default="")
    limitations: Mapped[str] = mapped_column(Text, default="")
    score: Mapped[float] = mapped_column(Float)
    score_breakdown: Mapped[dict] = mapped_column(JSON, default=dict)
    linked: Mapped[dict] = mapped_column(JSON, default=dict)  # gap codes, contradiction codes, claim ids, segment ids
    status: Mapped[str] = mapped_column(String(16), default="open")  # open | requested | collected | not_available
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utcnow)


class WhatIfScenario(Base):
    """Hypothetical branch. Results are computed in an isolated sandbox and never written to the case."""
    __tablename__ = "whatif_scenarios"
    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_uuid)
    case_id: Mapped[str] = mapped_column(ForeignKey("cases.id", ondelete="CASCADE"), index=True)
    parent_id: Mapped[str | None] = mapped_column(ForeignKey("whatif_scenarios.id", ondelete="SET NULL"), nullable=True)
    title: Mapped[str] = mapped_column(String(255))
    assumptions: Mapped[list] = mapped_column(JSON, default=list)  # cumulative along the branch
    status: Mapped[str] = mapped_column(String(16), default="queued")
    result: Mapped[dict] = mapped_column(JSON, default=dict)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    discarded: Mapped[bool] = mapped_column(Boolean, default=False)
    created_by: Mapped[str | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utcnow)


class InvestigationEvent(Base):
    """Investigation Replay: persisted record of what the system and people actually did, in order."""
    __tablename__ = "investigation_events"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    case_id: Mapped[str] = mapped_column(ForeignKey("cases.id", ondelete="CASCADE"), index=True)
    ts: Mapped[datetime] = mapped_column(UTCDateTime(), default=utcnow, index=True)
    action: Mapped[str] = mapped_column(String(64))
    actor: Mapped[str] = mapped_column(String(255))  # user email or component name
    component: Mapped[str] = mapped_column(String(64))
    status: Mapped[str] = mapped_column(String(16), default="ok")  # ok | failed | warning
    inputs: Mapped[list] = mapped_column(JSON, default=list)  # [{type, id, label}]
    outputs: Mapped[list] = mapped_column(JSON, default=list)
    summary: Mapped[str] = mapped_column(Text, default="")
    details: Mapped[dict] = mapped_column(JSON, default=dict)
    run_id: Mapped[str | None] = mapped_column(String(32), nullable=True, index=True)


class ContactMessage(Base):
    """Message sent from the public landing page's contact form. Read by admins only."""
    __tablename__ = "contact_messages"
    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_uuid)
    name: Mapped[str] = mapped_column(String(120))
    email: Mapped[str] = mapped_column(String(254))
    organisation: Mapped[str] = mapped_column(String(160), default="")
    topic: Mapped[str] = mapped_column(String(40), default="general")
    message: Mapped[str] = mapped_column(Text)
    client_ip: Mapped[str] = mapped_column(String(64), default="")
    status: Mapped[str] = mapped_column(String(16), default="new")  # new | read | archived
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utcnow)
