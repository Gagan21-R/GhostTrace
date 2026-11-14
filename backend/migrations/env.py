"""Alembic environment: uses the application's DATABASE_URL and model metadata."""
from __future__ import annotations

import sys
from pathlib import Path

from alembic import context
from sqlalchemy import DateTime

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app import models  # noqa: E402,F401  (registers all tables)
from app.db import Base, engine  # noqa: E402

target_metadata = Base.metadata


def render_item(type_, obj, autogen_context):
    # Render the UTC-normalising TypeDecorator as a plain timezone-aware DateTime column.
    if type_ == "type" and isinstance(obj, models.UTCDateTime):
        return "sa.DateTime(timezone=True)"
    return False


def run_migrations_offline():
    context.configure(url=str(engine.url), target_metadata=target_metadata, literal_binds=True,
                      render_item=render_item, render_as_batch=True)
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online():
    connectable = context.config.attributes.get("connection")
    if connectable is not None:
        _run(connectable)
        return
    with engine.connect() as conn:
        _run(conn)


def _run(conn):
    context.configure(connection=conn, target_metadata=target_metadata, render_item=render_item,
                      render_as_batch=conn.dialect.name == "sqlite", compare_type=True)
    with context.begin_transaction():
        context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
