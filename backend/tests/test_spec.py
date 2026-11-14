"""Tests for the specification endpoints, logout/revocation, external-AI authorisation, WEBP intake,
migrations and injection resistance."""
import io
import time

from conftest import ROOT, auth

DATA = ROOT / "scenario_data" / "s5-marketplace-dispute"


def _user(client, email):
    r = client.post("/api/auth/register", json={"email": email, "full_name": "Spec User", "password": "Str0ngPassw0rd"})
    if r.status_code == 409:
        r = client.post("/api/auth/login", json={"email": email, "password": "Str0ngPassw0rd"})
    return r.json()["access_token"]


def _wait(client, tok, run_id):
    for _ in range(480):
        r = client.get(f"/api/runs/{run_id}", headers=auth(tok)).json()
        if r["status"] in ("completed", "failed"):
            return r
        time.sleep(0.5)
    raise AssertionError("timeout")


def test_migrations_applied(client):
    from sqlalchemy import inspect
    from app.db import engine
    tables = set(inspect(engine).get_table_names())
    assert "alembic_version" in tables and "revoked_tokens" in tables


def test_logout_revokes_token_and_password_change(client):
    tok = _user(client, "logout@example.com")
    assert client.get("/api/auth/me", headers=auth(tok)).status_code == 200
    assert client.post("/api/auth/logout", headers=auth(tok)).status_code == 200
    assert client.get("/api/auth/me", headers=auth(tok)).status_code == 401
    tok2 = client.post("/api/auth/login", json={"email": "logout@example.com", "password": "Str0ngPassw0rd"}).json()["access_token"]
    bad = client.post("/api/auth/me/password", json={"current_password": "nope", "new_password": "An0therPassw0rd"}, headers=auth(tok2))
    assert bad.status_code == 400
    ok = client.post("/api/auth/me/password", json={"current_password": "Str0ngPassw0rd", "new_password": "An0therPassw0rd"}, headers=auth(tok2))
    assert ok.status_code == 200
    assert client.post("/api/auth/login", json={"email": "logout@example.com", "password": "An0therPassw0rd"}).status_code == 200
    assert client.patch("/api/auth/me", json={"full_name": "Renamed User"}, headers=auth(tok2)).json()["full_name"] == "Renamed User"


def test_webp_intake():
    from app.services.intake import inspect_upload
    from PIL import Image
    buf = io.BytesIO()
    Image.new("RGB", (40, 20), "white").save(buf, "WEBP")
    assert inspect_upload("shot.webp", buf.getvalue(), 10_000_000).detected_type == "image"
    assert not inspect_upload("fake.webp", b"RIFF0000WAVEfmt ", 10_000_000).ok


def test_spec_endpoints_and_ai_authorisation(client):
    owner = _user(client, "spec-owner@example.com")
    editor = _user(client, "spec-editor@example.com")
    stranger = _user(client, "spec-stranger@example.com")
    cid = client.post("/api/cases", json={"title": "Spec endpoint case", "default_timezone": "+05:30"}, headers=auth(owner)).json()["id"]
    client.post(f"/api/cases/{cid}/members", json={"email": "spec-editor@example.com", "access": "editor"}, headers=auth(owner))

    # External AI is off by default and only the owner may enable it.
    assert client.get(f"/api/cases/{cid}", headers=auth(owner)).json()["allow_external_ai"] is False
    assert client.patch(f"/api/cases/{cid}", json={"allow_external_ai": True}, headers=auth(editor)).status_code == 403
    assert client.patch(f"/api/cases/{cid}", json={"allow_external_ai": True}, headers=auth(owner)).json()["allow_external_ai"] is True
    client.patch(f"/api/cases/{cid}", json={"allow_external_ai": False}, headers=auth(owner))

    files = [("files", (n, (DATA / n).read_bytes())) for n in ("01_order_confirmation.eml", "02_invoice.pdf", "04_seller_chat.json",
                                                             "05_courier_tracking.csv", "06_delivery_confirmation.pdf", "09_other_order.eml")]
    up = client.post(f"/api/cases/{cid}/evidence", files=files, headers=auth(owner)).json()
    assert up["accepted"] == 6
    ev_id = up["results"][0]["evidence"]["id"]

    st = client.get(f"/api/cases/{cid}/processing-status", headers=auth(owner)).json()
    assert st["pending"] == 6 and st["run"] is None
    run = client.post(f"/api/cases/{cid}/process", headers=auth(owner)).json()
    assert _wait(client, owner, run["run_id"])["status"] == "completed"
    assert client.get(f"/api/cases/{cid}/processing-status", headers=auth(owner)).json()["run"]["status"] == "completed"

    ext = client.get(f"/api/cases/{cid}/extracted-data?limit=5", headers=auth(owner)).json()
    assert ext["total"] > 5 and len(ext["items"]) == 5 and all(i["evidence_code"] for i in ext["items"])
    rels = client.get(f"/api/cases/{cid}/relationships", headers=auth(owner)).json()
    assert rels and all(r["basis"] in ("observed", "inferred") for r in rels)
    gaps = client.get(f"/api/cases/{cid}/evidence-gaps", headers=auth(owner)).json()
    assert gaps and all("why_it_matters" in g for g in gaps)
    cons = client.get(f"/api/cases/{cid}/contradictions", headers=auth(owner)).json()
    assert cons and all(c["priority"] in ("high", "medium", "low") for c in cons)

    prev = client.get(f"/api/evidence/{ev_id}/preview", headers=auth(owner))
    assert prev.status_code == 200 and prev.headers["x-content-type-options"] == "nosniff"
    hist = client.get(f"/api/evidence/{ev_id}/history", headers=auth(owner)).json()
    assert [h["action"] for h in hist][:1] == ["evidence.intake"]
    csv_ = client.get(f"/api/cases/{cid}/timeline/export?format=csv", headers=auth(owner))
    assert csv_.status_code == 200 and csv_.text.startswith("display_time,timestamp_kind")
    assert client.get(f"/api/cases/{cid}/timeline/export?format=json", headers=auth(owner)).json()

    inv = client.post(f"/api/cases/{cid}/investigate", headers=auth(owner)).json()
    res = _wait(client, owner, inv["run_id"])
    assert res["status"] == "completed"
    counter = next(a for a in res["agents"] if a["agent"] == "counter_investigation")
    assert counter["mode"].startswith("deterministic")
    execs = client.get(f"/api/cases/{cid}/agent-executions", headers=auth(owner)).json()
    assert {"investigation", "counter_investigation", "verification", "skeptical_review"} <= {a["agent"] for a in execs}

    rep = client.post(f"/api/cases/{cid}/reports", json={}, headers=auth(owner)).json()
    assert [r["id"] for r in client.get(f"/api/cases/{cid}/reports", headers=auth(owner)).json()] == [rep["id"]]
    dl = client.get(f"/api/reports/{rep['id']}/download", headers=auth(owner))
    assert dl.content.startswith(b"%PDF") and "attachment" in dl.headers["content-disposition"]
    assert "inline" in client.get(f"/api/reports/{rep['id']}/preview", headers=auth(owner)).headers["content-disposition"]
    assert any(h["action"] == "report.generated" for h in client.get(f"/api/cases/{cid}/history", headers=auth(editor)).json())

    # Isolation on every new endpoint.
    for path in (f"/api/cases/{cid}/processing-status", f"/api/cases/{cid}/extracted-data", f"/api/cases/{cid}/relationships",
                 f"/api/cases/{cid}/evidence-gaps", f"/api/cases/{cid}/agent-executions", f"/api/cases/{cid}/timeline/export",
                 f"/api/cases/{cid}/history", f"/api/cases/{cid}/reports", f"/api/evidence/{ev_id}/preview", f"/api/evidence/{ev_id}/history",
                 f"/api/reports/{rep['id']}/download"):
        assert client.get(path, headers=auth(stranger)).status_code == 404, path
    assert client.post(f"/api/cases/{cid}/investigate", headers=auth(stranger)).status_code == 404

    # Injection-style search input is treated as data and leaks nothing.
    for q in ("' OR '1'='1", "%' OR 1=1 --", "\"; DROP TABLE evidence; --"):
        assert client.get(f"/api/cases/{cid}/evidence", params={"q": q}, headers=auth(owner)).json() == []
        assert client.get("/api/cases", params={"q": q}, headers=auth(stranger)).json() == []
    assert len(client.get(f"/api/cases/{cid}/evidence", headers=auth(owner)).json()) == 6


def test_scenario_spec_endpoints(client, admin_token):
    from app.db import SessionLocal
    from app.models import ScenarioRun, User
    from app.scenarios.runner import create_run, execute
    db = SessionLocal()
    admin = db.query(User).filter(User.role == "admin").first()
    ids = []
    for _ in range(2):
        r = create_run(db, "s2h-sparse-account-records", admin)
        execute(db, r.id, admin.id)
        ids.append(r.id)
    db.close()
    st = client.get(f"/api/scenarios/runs/{ids[0]}/status", headers=auth(admin_token)).json()
    assert st["status"] == "completed" and st["agents"]
    res = client.get(f"/api/scenarios/runs/{ids[0]}/results", headers=auth(admin_token)).json()
    assert res["outcome"] == "HOLD" and res["metrics"]
    assert client.get(f"/api/scenarios/runs/{ids[0]}/report", headers=auth(admin_token)).content.startswith(b"%PDF")
    hist = client.get("/api/scenarios/s2h-sparse-account-records/history", headers=auth(admin_token)).json()
    assert {h["id"] for h in hist} >= set(ids)
    cmp = client.post("/api/scenarios/compare", json={"run_ids": ids}, headers=auth(admin_token)).json()
    assert len(cmp["runs"]) == 2 and "processing_time" in cmp["metrics"]
    assert client.post("/api/scenarios/compare", json={"run_ids": ids[:1]}, headers=auth(admin_token)).status_code == 422
