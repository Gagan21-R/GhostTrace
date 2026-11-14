from __future__ import annotations

import time
from collections import defaultdict

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy import select
from sqlalchemy.orm import Session

from .. import audit
from ..db import get_db
from ..models import RevokedToken, User, utcnow
from ..schemas import LoginIn, PasswordChangeIn, ProfileIn, RegisterIn, TokenOut, UserOut, UserUpdate
from ..security import (create_access_token, decode_token, get_current_user, hash_password, oauth2_scheme,
                        permissions_for, require, validate_password_strength, verify_password)

router = APIRouter(prefix="/api", tags=["auth"])
_attempts: dict[str, list[float]] = defaultdict(list)


def _throttle(key: str):
    now = time.time()
    _attempts[key] = [t for t in _attempts[key] if now - t < 300]
    if len(_attempts[key]) >= 8:
        raise HTTPException(429, "Too many login attempts. Try again in a few minutes.")


def _token(user: User) -> dict:
    return {"access_token": create_access_token(user), "token_type": "bearer", "user": UserOut.model_validate(user),
            "permissions": sorted(permissions_for(user))}


def _login(db: Session, email: str, password: str, request: Request) -> dict:
    key = f"{request.client.host if request.client else '?'}:{email.lower()}"
    _throttle(key)
    user = db.scalar(select(User).where(User.email == email.lower()))
    if not user or not verify_password(password, user.password_hash) or not user.is_active:
        _attempts[key].append(time.time())
        audit.record(db, "auth.login_failed", detail={"email": email.lower()})
        raise HTTPException(401, "Invalid email or password")
    _attempts.pop(key, None)
    user.last_login_at = utcnow()
    db.commit()
    audit.record(db, "auth.login", user=user)
    return _token(user)


@router.post("/auth/register", response_model=TokenOut, status_code=201)
def register(body: RegisterIn, db: Session = Depends(get_db)):
    validate_password_strength(body.password)
    if db.scalar(select(User).where(User.email == body.email.lower())):
        raise HTTPException(409, "An account with this email already exists")
    user = User(email=body.email.lower(), full_name=body.full_name.strip(), password_hash=hash_password(body.password),
                role="investigator")
    db.add(user)
    db.commit()
    audit.record(db, "auth.register", user=user)
    return _token(user)


@router.post("/auth/login", response_model=TokenOut)
def login_json(body: LoginIn, request: Request, db: Session = Depends(get_db)):
    return _login(db, body.email, body.password, request)


@router.post("/auth/token", response_model=TokenOut, include_in_schema=True)
def login_form(request: Request, form: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    """OAuth2 password flow (used by the interactive API docs)."""
    return _login(db, form.username, form.password, request)


@router.get("/auth/me", response_model=TokenOut)
def me(user: User = Depends(get_current_user)):
    return _token(user)


@router.post("/auth/logout")
def logout(token: str = Depends(oauth2_scheme), user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Revoke the presented token (stateless JWTs are otherwise valid until expiry)."""
    from datetime import datetime, timezone
    p = decode_token(token)
    db.add(RevokedToken(jti=p["jti"], user_id=user.id, expires_at=datetime.fromtimestamp(p["exp"], tz=timezone.utc)))
    db.query(RevokedToken).filter(RevokedToken.expires_at < utcnow()).delete()
    db.commit()
    audit.record(db, "auth.logout", user=user)
    return {"ok": True}


@router.patch("/auth/me", response_model=UserOut)
def update_profile(body: ProfileIn, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    u = db.get(User, user.id)
    u.full_name = body.full_name.strip()
    db.commit()
    audit.record(db, "user.profile_updated", user=u)
    return u


@router.post("/auth/me/password")
def change_password(body: PasswordChangeIn, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    u = db.get(User, user.id)
    if not verify_password(body.current_password, u.password_hash):
        raise HTTPException(400, "Current password is incorrect")
    validate_password_strength(body.new_password)
    u.password_hash = hash_password(body.new_password)
    db.commit()
    audit.record(db, "user.password_changed", user=u)
    return {"ok": True}


@router.get("/auth/permissions")
def my_permissions(user: User = Depends(get_current_user)):
    return {"role": user.role, "permissions": sorted(permissions_for(user))}


@router.get("/users", response_model=list[UserOut])
def list_users(db: Session = Depends(get_db), _: User = Depends(require("user:manage"))):
    return list(db.scalars(select(User).order_by(User.created_at)))


@router.patch("/users/{user_id}", response_model=UserOut)
def update_user(user_id: str, body: UserUpdate, db: Session = Depends(get_db), admin: User = Depends(require("user:manage"))):
    u = db.get(User, user_id)
    if not u:
        raise HTTPException(404, "User not found")
    from ..models import ROLES
    if body.role is not None:
        if body.role not in ROLES:
            raise HTTPException(422, f"Role must be one of {ROLES}")
        if u.id == admin.id and body.role != "admin":
            raise HTTPException(400, "You cannot remove your own admin role")
        u.role = body.role
    if body.is_active is not None:
        if u.id == admin.id and not body.is_active:
            raise HTTPException(400, "You cannot deactivate yourself")
        u.is_active = body.is_active
    if body.full_name:
        u.full_name = body.full_name
    db.commit()
    audit.record(db, "user.updated", user=admin, detail={"target": u.email, "role": u.role, "active": u.is_active})
    return u
