"""Authentication, RBAC and case-level authorisation. Purely deterministic - never delegated to an LLM."""
from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

import bcrypt
import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy import select
from sqlalchemy.orm import Session

from .config import get_settings
from .db import get_db
from .models import ROLE_PERMISSIONS, Case, CaseMember, RevokedToken, User

settings = get_settings()
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login")


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8")[:72], bcrypt.gensalt(rounds=12)).decode()


def verify_password(password: str, hashed: str) -> bool:
    try:
        return bcrypt.checkpw(password.encode("utf-8")[:72], hashed.encode())
    except ValueError:
        return False


def validate_password_strength(password: str) -> None:
    if len(password) < 10 or password.lower() == password or not any(c.isdigit() for c in password):
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY,
                            "Password must be at least 10 characters with an uppercase letter and a digit")


def create_access_token(user: User) -> str:
    now = datetime.now(timezone.utc)
    payload = {"sub": user.id, "role": user.role, "iat": now, "jti": uuid.uuid4().hex,
               "exp": now + timedelta(minutes=settings.jwt_expire_minutes)}
    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)


def decode_token(token: str) -> dict:
    return jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_algorithm])


def get_current_user(token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)) -> User:
    cred_exc = HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid or expired credentials",
                             headers={"WWW-Authenticate": "Bearer"})
    try:
        payload = decode_token(token)
    except jwt.PyJWTError:
        raise cred_exc
    if not payload.get("jti") or db.get(RevokedToken, payload["jti"]):
        raise cred_exc  # logged out (or a token issued before revocation support)
    user = db.get(User, payload.get("sub"))
    if not user or not user.is_active:
        raise cred_exc
    return user


def permissions_for(user: User) -> set[str]:
    return ROLE_PERMISSIONS.get(user.role, set())


def require(permission: str):
    def _dep(user: User = Depends(get_current_user)) -> User:
        if permission not in permissions_for(user):
            raise HTTPException(status.HTTP_403_FORBIDDEN, f"Missing permission: {permission}")
        return user
    return _dep


def case_access(db: Session, user: User, case_id: str) -> str | None:
    """Return the user's access level on a case (owner/editor/viewer) or None."""
    if "case:all" in permissions_for(user):
        return "owner"
    m = db.scalar(select(CaseMember).where(CaseMember.case_id == case_id, CaseMember.user_id == user.id))
    return m.access if m else None


def get_case_or_403(db: Session, user: User, case_id: str, write: bool = False) -> Case:
    case = db.get(Case, case_id)
    access = case_access(db, user, case_id) if case else None
    # Same 404 for "missing" and "not yours" so case IDs cannot be probed across tenants.
    if not case or access is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Case not found")
    if write and access == "viewer":
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Read-only access to this case")
    return case


def accessible_case_ids(db: Session, user: User) -> list[str] | None:
    """None means all cases (admin)."""
    if "case:all" in permissions_for(user):
        return None
    return list(db.scalars(select(CaseMember.case_id).where(CaseMember.user_id == user.id)))
