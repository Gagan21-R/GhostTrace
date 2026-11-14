from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field


class ORM(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class RegisterIn(BaseModel):
    email: EmailStr
    full_name: str = Field(min_length=2, max_length=120)
    password: str = Field(min_length=10, max_length=128)


class LoginIn(BaseModel):
    email: str = Field(min_length=3, max_length=255)  # not format-validated: login must work for local/internal domains
    password: str = Field(min_length=1, max_length=256)


class UserOut(ORM):
    id: str
    email: str
    full_name: str
    role: str
    is_active: bool
    created_at: datetime
    last_login_at: datetime | None = None


class TokenOut(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserOut
    permissions: list[str]


class ProfileIn(BaseModel):
    full_name: str = Field(min_length=2, max_length=120)


class PasswordChangeIn(BaseModel):
    current_password: str = Field(min_length=1, max_length=256)
    new_password: str = Field(min_length=10, max_length=128)


class UserUpdate(BaseModel):
    role: str | None = None
    is_active: bool | None = None
    full_name: str | None = None


class CaseIn(BaseModel):
    title: str = Field(min_length=3, max_length=200)
    description: str = Field(default="", max_length=5000)
    objective: str = Field(default="", max_length=3000)
    case_type: str = Field(default="general", max_length=64)
    priority: str = Field(default="medium", pattern="^(low|medium|high|critical)$")
    default_timezone: str = Field(default="UTC", pattern=r"^(UTC|unknown|[+-]\d{2}:\d{2})$")


class CaseUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=3, max_length=200)
    description: str | None = Field(default=None, max_length=5000)
    objective: str | None = Field(default=None, max_length=3000)
    case_type: str | None = None
    priority: str | None = Field(default=None, pattern="^(low|medium|high|critical)$")
    status: str | None = Field(default=None, pattern="^(active|completed|archived)$")
    default_timezone: str | None = Field(default=None, pattern=r"^(UTC|unknown|[+-]\d{2}:\d{2})$")
    allow_external_ai: bool | None = None  # owner only


class MemberIn(BaseModel):
    email: EmailStr
    access: str = Field(default="viewer", pattern="^(owner|editor|viewer)$")


class EvidenceUpdate(BaseModel):
    category: str | None = Field(default=None, max_length=64)
    tags: list[str] | None = None
    collection_source: str | None = Field(default=None, max_length=2000)
    collected_by: str | None = Field(default=None, max_length=255)
    collected_at: str | None = Field(default=None, max_length=64)
    legal_hold: bool | None = None


class ReviewIn(BaseModel):
    status: str = Field(pattern="^(pending|confirmed|dismissed|open|resolved|accepted|rejected|needs_more_evidence)$")
    note: str | None = Field(default=None, max_length=3000)


class ReportIn(BaseModel):
    redact: bool = False
