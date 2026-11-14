"""Database initialisation and first-run seeding."""
from __future__ import annotations

import logging

from sqlalchemy import select

from .config import get_settings
from .db import Base, SessionLocal, engine
from .models import User
from .security import hash_password

log = logging.getLogger("evidencex")


def run_migrations():
    """Bring the schema to the latest Alembic revision (the only way tables are created)."""
    from alembic import command
    from alembic.config import Config
    from sqlalchemy import inspect

    from .config import BASE_DIR
    insp = inspect(engine)
    if insp.has_table("users") and not insp.has_table("alembic_version"):
        raise RuntimeError("This database was created before migrations were introduced. Back it up and delete it "
                           "(backend/data/evidencex.db) or point DATABASE_URL at a new database, then restart.")
    cfg = Config(str(BASE_DIR / "alembic.ini"))
    cfg.set_main_option("script_location", str(BASE_DIR / "migrations"))
    command.upgrade(cfg, "head")


def init_db():
    from . import models  # noqa: F401
    run_migrations()
    s = get_settings()
    db = SessionLocal()
    try:
        if not db.scalar(select(User).limit(1)):
            db.add(User(email=s.seed_admin_email.lower(), full_name="Platform Administrator",
                        password_hash=hash_password(s.seed_admin_password), role="admin"))
            db.commit()
            log.warning("Seeded admin user %s - change the password via SEED_ADMIN_PASSWORD / the Users page.", s.seed_admin_email)
        from .scenarios.runner import sync_definitions
        sync_definitions(db)
    finally:
        db.close()
