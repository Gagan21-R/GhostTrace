"""Voice recording -> stored evidence + language detection + re-analysis; confidence report; chatbot language."""
import time

from conftest import ROOT, auth


def _case(client, tok):
    r = client.post("/api/cases", json={"title": "Voice test", "case_type": "general"}, headers=auth(tok))
    assert r.status_code == 201, r.text
    return r.json()["id"]


def test_voice_recording_detects_language_and_reanalyses(client, admin_token):
    cid = _case(client, admin_token)
    wav = (ROOT / "scenario_data" / "s1-phishing" / "10_voicemail.wav").read_bytes()
    no = client.post(f"/api/cases/{cid}/voice", files={"audio": ("v.wav", wav, "audio/wav")}, data={"consent": "false"}, headers=auth(admin_token))
    assert no.status_code == 422  # consent is required
    r = client.post(f"/api/cases/{cid}/voice", files={"audio": ("v.wav", wav, "audio/wav")},
                    data={"consent": "true", "speaker": "Test caller"}, headers=auth(admin_token))
    assert r.status_code == 201, r.text
    out = r.json()
    assert out["code"].startswith("EV-") and len(out["sha256"]) == 64
    if out["status"] == "processed":  # speech engine installed
        assert out["language"] == "en" and set(out["language_candidates"]) == {"en", "hi", "kn"}
        assert "kyc" in out["transcript"].lower()
    assert out["reanalysis"]["status"] == "queued"
    speech = out["status"] == "processed"
    for _ in range(240):
        runs = client.get(f"/api/cases/{cid}/runs", headers=auth(admin_token)).json()
        kinds = {x["kind"]: x["status"] for x in runs}
        done = kinds.get("processing") in ("completed", "failed") and (not speech or kinds.get("adversarial") in ("completed", "failed"))
        if done and all(x["status"] in ("completed", "failed") for x in runs):
            break
        time.sleep(1)
    assert kinds.get("processing") == "completed"
    if speech:  # a transcript gives the challenge run something to test
        assert kinds.get("adversarial") == "completed"
    conf = client.get(f"/api/cases/{cid}/confidence", headers=auth(admin_token)).json()
    assert 0 <= conf["score"] <= 100 and conf["band"] in ("High", "Moderate", "Low")
    assert {c["key"] for c in conf["components"]} >= {"integrity", "extraction"}
    assert abs(sum(c["weight"] for c in conf["components"]) - 1) < 0.01


def test_help_topic_in_kannada(client):
    r = client.get("/api/help/topics/timeline?lang=kn").json()
    assert "ಕಾಲರೇಖೆ" in r["answer"]
    r = client.post("/api/help/explain", json={"title": "Confidence", "lang": "hi"}).json()
    assert "विश्वास" in r["answer"]
