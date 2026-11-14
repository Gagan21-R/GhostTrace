"""Background job execution for long-running analysis (thread pool; each job owns its DB session)."""
from __future__ import annotations

import logging
import traceback
from concurrent.futures import ThreadPoolExecutor

from ..db import SessionLocal

log = logging.getLogger("evidencex.jobs")
_pool = ThreadPoolExecutor(max_workers=2, thread_name_prefix="evx-job")


def submit(fn, *args):
    def _run():
        db = SessionLocal()
        try:
            fn(db, *args)
        except Exception:
            log.error("background job failed:\n%s", traceback.format_exc())
            db.rollback()
        finally:
            db.close()
    return _pool.submit(_run)
