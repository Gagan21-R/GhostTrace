"""Flagship intelligence: Evidence DNA, integrity inspection, Challenge Engine decisions, Missing Evidence
Predictor, What-If isolation, Investigation Replay, verification of unsupported claims, report exports and
edge cases (corrupt files, failed agent, unavailable LLM)."""
import io
import time

from conftest import ROOT, auth

S1 = ROOT / "scenario_data" / "s1-phishing"
FILES = ["01_kyc_email.eml", "11_forward_to_bank.eml", "03_whatsapp_chat.txt", "05_bank_statement.csv", "06_bank_sms_alert.txt",
         "07_victim_statement.docx", "08_followup_email.eml", "09_flipkart_newsletter.eml"]
STATE: dict = {}


def _tok(client):
    r = client.post("/api/auth/register", json={"email": "flag@example.com", "full_name": "Flagship Tester", "password": "Str0ngPassw0rd"})
    if r.status_code == 409:
        r = client.post("/api/auth/login", json={"email": "flag@example.com", "password": "Str0ngPassw0rd"})
    return r.json()["access_token"]


def _wait(client, tok, path, done=("completed", "failed"), key="status"):
    for _ in range(600):
        r = client.get(path, headers=auth(tok)).json()
        if r[key] in done:
            return r
        time.sleep(0.5)
    raise AssertionError("timeout")


def _case(client):
    if "cid" in STATE:
        return STATE["tok"], STATE["cid"]
    tok = _tok(client)
    cid = client.post("/api/cases", json={"title": "Flagship phishing case", "case_type": "fraud", "default_timezone": "+05:30"},
                      headers=auth(tok)).json()["id"]
    files = [("files", (n, (S1 / n).read_bytes())) for n in FILES]
    files.append(("files", ("05_bank_statement_copy.csv", (S1 / "05_bank_statement.csv").read_bytes())))  # exact duplicate
    up = client.post(f"/api/cases/{cid}/evidence", files=files, headers=auth(tok)).json()
    assert up["accepted"] == len(files)
    run = client.post(f"/api/cases/{cid}/process", headers=auth(tok)).json()
    assert _wait(client, tok, f"/api/runs/{run['run_id']}")["status"] == "completed"
    run = client.post(f"/api/cases/{cid}/investigate", headers=auth(tok)).json()
    assert _wait(client, tok, f"/api/runs/{run['run_id']}")["status"] == "completed"
    STATE.update(tok=tok, cid=cid, codes={e["filename"]: e for e in client.get(f"/api/cases/{cid}/evidence", headers=auth(tok)).json()})
    return tok, cid


def test_evidence_dna_detects_duplicate_and_derived(client):
    tok, cid = _case(client)
    d = client.get(f"/api/cases/{cid}/dna", headers=auth(tok)).json()
    rel = {(x["a"]["filename"], x["b"]["filename"]): x["relation"] for x in d["dependencies"]}
    pair = lambda a, b: rel.get((a, b)) or rel.get((b, a))  # noqa: E731
    assert pair("05_bank_statement.csv", "05_bank_statement_copy.csv") == "duplicate"
    assert pair("01_kyc_email.eml", "11_forward_to_bank.eml") == "derived"
    assert d["summary"]["independent_source_groups"] < d["summary"]["evidence"]  # copies collapse into one source
    shared = {x["value"] for x in d["shared_identifiers"]}
    assert "407215538921" in shared
    utr = next(x for x in d["shared_identifiers"] if x["value"] == "407215538921")
    assert utr["independent_sources"] < utr["files"]  # the duplicate statement is not independent corroboration
    for x in d["dependencies"]:
        for m in x["matches"]:
            assert m["a"]["segment_id"] and m["b"]["segment_id"]  # every match points at a source location


def test_integrity_inspection_flags_missing_headers_and_duplicates(client):
    tok, cid = _case(client)
    f = client.get(f"/api/cases/{cid}/integrity-findings", headers=auth(tok)).json()
    checks = {(x["filename"], x["check"]) for x in f}
    assert ("01_kyc_email.eml", "missing_email_headers") in checks
    assert ("05_bank_statement_copy.csv", "exact_duplicate") in checks
    assert ("09_flipkart_newsletter.eml", "missing_email_headers") not in checks  # authenticated control email


def test_challenge_engine_decision_and_verification(client):
    tok, cid = _case(client)
    hyps = client.get(f"/api/cases/{cid}/hypotheses", headers=auth(tok)).json()
    assert hyps and hyps[0]["rank"] == 0 and hyps[0]["decision"] in ("SUPPORTED", "CONTRADICTED", "INCONCLUSIVE", "HOLD")
    assert hyps[0]["pattern"] == "phishing_payment_fraud"
    assert "independent_sources" in hyps[0]["assessment"]
    agents = {a["agent"] for a in hyps[0]["agents"]}
    assert {"investigation", "counter_investigation", "verification", "skeptical_review", "missing_evidence"} <= agents
    items = client.get(f"/api/cases/{cid}/extracted-data?evidence_id={STATE['codes']['06_bank_sms_alert.txt']['id']}", headers=auth(tok)).json()["items"]
    seg = next(i for i in items if "407215538921" in i["text"])
    ok = client.post(f"/api/cases/{cid}/verify-claim", json={"text": "Bank SMS records UTR 407215538921", "citations": [seg["segment_id"]],
                                                             "expect": ["407215538921"]}, headers=auth(tok)).json()
    assert ok["status"] == "verified"
    wrong = client.post(f"/api/cases/{cid}/verify-claim", json={"text": "Bank SMS records UTR 999999999999", "citations": [seg["segment_id"]],
                                                                "expect": ["999999999999"]}, headers=auth(tok)).json()
    assert wrong["status"] == "rejected"
    fabricated = client.post(f"/api/cases/{cid}/verify-claim", json={"text": "Invented source", "citations": ["0" * 32]}, headers=auth(tok)).json()
    assert fabricated["status"] == "rejected" and any("do not exist" in c for c in fabricated["checks"])
    guilt = client.post(f"/api/cases/{cid}/verify-claim", json={"text": "The sender is guilty of the fraud", "citations": [seg["segment_id"]]},
                        headers=auth(tok)).json()
    assert guilt["status"] == "rejected"


def test_missing_evidence_recommendations_are_ranked_and_explained(client):
    tok, cid = _case(client)
    recs = client.get(f"/api/cases/{cid}/recommendations", headers=auth(tok)).json()
    assert recs and [r["rank"] for r in recs] == sorted(r["rank"] for r in recs)
    assert all(recs[i]["score"] >= recs[i + 1]["score"] for i in range(len(recs) - 1))
    r0 = recs[0]
    assert r0["why_it_matters"] and r0["authorised_source"] and set(r0["score_breakdown"]) == {
        "importance", "discrimination", "relevance", "information_value", "availability"}
    assert client.patch(f"/api/recommendations/{r0['id']}", json={"status": "requested"}, headers=auth(tok)).json()["status"] == "requested"


def test_whatif_is_isolated_and_branchable(client):
    tok, cid = _case(client)
    before = (len(client.get(f"/api/cases/{cid}/contradictions", headers=auth(tok)).json()),
              client.get(f"/api/cases/{cid}/hypotheses", headers=auth(tok)).json()[0]["decision"])
    sms = STATE["codes"]["06_bank_sms_alert.txt"]["id"]
    w = client.post(f"/api/cases/{cid}/whatif", json={"title": "Bank SMS unreliable", "assumption": {"type": "exclude_evidence", "evidence_id": sms}},
                    headers=auth(tok)).json()
    w = _wait(client, tok, f"/api/whatif/{w['id']}")
    assert w["status"] == "completed", w.get("error")
    assert w["result"]["label"] == "HYPOTHETICAL" and "set aside" in w["result"]["assumptions_described"][0]
    child = client.post(f"/api/cases/{cid}/whatif", json={"title": "…and the statement date is unknown", "parent_id": w["id"],
                                                          "assumption": {"type": "narrative", "note": "Victim unsure of the date"}}, headers=auth(tok)).json()
    child = _wait(client, tok, f"/api/whatif/{child['id']}")
    assert len(child["assumptions"]) == 2 and child["result"]["not_computable"]
    after = (len(client.get(f"/api/cases/{cid}/contradictions", headers=auth(tok)).json()),
             client.get(f"/api/cases/{cid}/hypotheses", headers=auth(tok)).json()[0]["decision"])
    assert before == after  # nothing hypothetical leaks into the case
    bad = client.post(f"/api/cases/{cid}/whatif", json={"title": "foreign", "assumption": {"type": "exclude_evidence", "evidence_id": "0" * 32}},
                      headers=auth(tok))
    assert bad.status_code == 422
    assert client.post(f"/api/whatif/{w['id']}/discard", headers=auth(tok)).json()["ok"]
    assert all(x["id"] != w["id"] for x in client.get(f"/api/cases/{cid}/whatif", headers=auth(tok)).json())


def test_replay_is_built_from_persisted_events(client):
    tok, cid = _case(client)
    rp = client.get(f"/api/cases/{cid}/replay?limit=2000", headers=auth(tok)).json()
    actions = [e["action"] for e in rp["items"]]
    for a in ("evidence.uploaded", "hash.calculated", "filetype.validated", "extraction.started", "extraction.completed",
              "agent.entity_intelligence", "agent.timeline", "dependency.detected", "contradiction.discovered",
              "hypothesis.created", "counter_investigation.performed", "verification.completed", "reviewer.decision", "duplicate.detected"):
        assert a in actions, a
    assert actions.index("evidence.uploaded") < actions.index("extraction.started") < actions.index("hypothesis.created") < actions.index("reviewer.decision")
    ids = [e["id"] for e in rp["items"]]
    assert ids == sorted(ids)
    page = client.get(f"/api/cases/{cid}/replay?limit=5&offset=5", headers=auth(tok)).json()
    assert len(page["items"]) == 5 and page["items"][0]["id"] == ids[5]


def test_report_exports_and_citations(client):
    tok, cid = _case(client)
    rep = client.post(f"/api/cases/{cid}/reports", json={}, headers=auth(tok)).json()
    full = client.get(f"/api/reports/{rep['id']}", headers=auth(tok)).json()
    titles = [s["title"] for s in full["content"]["sections"]]
    assert len(titles) == 20 and titles[0] == "Case overview" and titles[-1] == "Audit and processing summary"
    docx = client.get(f"/api/reports/{rep['id']}/docx", headers=auth(tok))
    assert docx.status_code == 200 and docx.content[:2] == b"PK"
    html = client.get(f"/api/reports/{rep['id']}/html", headers=auth(tok)).text
    assert "[EV-0" in html and "/evidence/" in html


def test_timeline_analysis_and_unknown_timezone(client):
    tok, cid = _case(client)
    a = client.get(f"/api/cases/{cid}/timeline/analysis", headers=auth(tok)).json()
    assert set(a) == {"silent_periods", "simultaneous_groups", "reported_vs_header"}
    from app.analysis import nlp
    dt, info = nlp.parse_datetime("10/03/2026, 09:31", default_tz="unknown")
    assert info["tz_unknown"] and nlp.display_dt(dt, info).endswith("(timezone unknown)")


def test_corrupt_files_and_unsupported(client):
    tok = _tok(client)
    cid = client.post("/api/cases", json={"title": "Edge cases"}, headers=auth(tok)).json()["id"]
    bad_docx = ("broken.docx", b"PK\x03\x04garbage-not-a-zip")
    bad_pdf = ("broken.pdf", b"%PDF-1.4\n%garbage without objects\n")
    r = client.post(f"/api/cases/{cid}/evidence", files=[("files", bad_docx), ("files", bad_pdf), ("files", ("x.heic", b"....ftypheic"))],
                    headers=auth(tok)).json()
    by = {x["filename"]: x for x in r["results"]}
    assert not by["broken.docx"]["ok"] and "Corrupt" in by["broken.docx"]["reason"]
    assert not by["x.heic"]["ok"] and "HEIC" in by["x.heic"]["reason"]
    assert by["broken.pdf"]["ok"]  # passes the signature check, fails in extraction - recorded, not swallowed
    run = client.post(f"/api/cases/{cid}/process", headers=auth(tok)).json()
    _wait(client, tok, f"/api/runs/{run['run_id']}")
    ev = client.get(f"/api/cases/{cid}/evidence", headers=auth(tok)).json()[0]
    assert ev["status"] == "failed" and ev["processing_error"]
    rp = client.get(f"/api/cases/{cid}/replay", headers=auth(tok)).json()["items"]
    assert any(e["action"] == "extraction.failed" and e["status"] == "failed" for e in rp)


def test_failed_agent_is_recorded_and_llm_fallback(client, monkeypatch):
    tok, cid = _case(client)
    from app.agents import adversarial
    monkeypatch.setattr(adversarial, "reviewer_agent", lambda *a, **k: (_ for _ in ()).throw(RuntimeError("simulated reviewer crash")))
    run = client.post(f"/api/cases/{cid}/investigate", headers=auth(tok)).json()
    res = _wait(client, tok, f"/api/runs/{run['run_id']}")
    assert res["status"] == "failed" and "simulated reviewer crash" in res["error"]
    sr = next(a for a in res["agents"] if a["agent"] == "skeptical_review")
    assert sr["status"] == "failed" and sr["attempts"] == 2  # retried once
    rp = client.get(f"/api/cases/{cid}/replay?component=skeptical_review&status=failed", headers=auth(tok)).json()
    assert rp["total"] >= 1
    monkeypatch.undo()
    # No LLM key in tests: the counter-agent must run deterministically and say so.
    counter = next(a for a in client.get(f"/api/runs/{run['run_id']}", headers=auth(tok)).json()["agents"] if a["agent"] == "counter_investigation")
    assert counter["mode"].startswith("deterministic")


def test_evaluation_summary_labels_unmeasured_metrics(client):
    tok = _tok(client)
    s = client.get("/api/evaluation/summary", headers=auth(tok)).json()
    assert "dependency_precision" in s["definitions"]
    for sc in s["scenarios"]:
        if sc["run_id"] is None:
            assert sc["outcome"] == "NOT EVALUATED"
            assert all(m["display"] == "NOT EVALUATED" for m in sc["metrics"].values())
