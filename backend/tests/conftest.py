import os
import shutil
import sys
import tempfile
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

_tmp = tempfile.mkdtemp(prefix="evx-test-")
os.environ["DATABASE_URL"] = f"sqlite:///{Path(_tmp, 'test.db').as_posix()}"
os.environ["STORAGE_ROOT"] = str(Path(_tmp, "storage"))
os.environ["JWT_SECRET"] = "test-secret-not-for-production-0123456789"
os.environ["LLM_PROVIDER"] = "none"
os.environ.setdefault("ASR_ENGINE", "none")  # keep the API suite fast; scenario tests cover ASR


@pytest.fixture(scope="session")
def client():
    from fastapi.testclient import TestClient
    from app.main import app
    with TestClient(app) as c:
        yield c
    shutil.rmtree(_tmp, ignore_errors=True)


@pytest.fixture(scope="session")
def admin_token(client):
    from app.config import get_settings
    s = get_settings()
    r = client.post("/api/auth/login", json={"email": s.seed_admin_email, "password": s.seed_admin_password})
    assert r.status_code == 200, r.text
    return r.json()["access_token"]


def auth(t):
    return {"Authorization": f"Bearer {t}"}
