"""Alternative Hypothesis Testing Engine: end-to-end through the API, including revision after new evidence."""
import json
import time

from conftest import ROOT, auth

DATA = ROOT / "scenario_data" / "s30-market-new-evidence"


def _wait_version(client, tok, cid, version, timeout=240):
    for _ in range(timeout):
        r = client.get(f"/api/cases/{cid}/hypothesis-lab", headers=auth(tok)).json()
        a = r["analysis"]
        runs = client.get(f"/api/cases/{cid}/runs", headers=auth(tok)).json()
        if a and a["version"] >= version and not any(x["status"] in ("queued", "running") for x in runs):
            return a
        time.sleep(1)
    raise AssertionError(f"hypothesis version {version} not produced; runs={runs}")


def test_new_evidence_revises_leading_hypothesis(client, admin_token):
    tok = admin_token
    cid = client.post("/api/cases", json={"title": "Laptop not delivered", "case_type": "commercial_dispute"}, headers=auth(tok)).json()["id"]
    manifest = json.loads((DATA / "manifest.json").read_text(encoding="utf-8"))
    for m in manifest:
        r = client.post(f"/api/cases/{cid}/evidence", files=[("files", (m["file"], (DATA / m["file"]).read_bytes()))],
                        data={"category": m["category"], "collection_source": m["collection_source"] or ""}, headers=auth(tok))
        assert r.json()["accepted"] == 1, r.text
    assert client.post(f"/api/cases/{cid}/analyse", headers=auth(tok)).status_code == 202
    v1 = _wait_version(client, tok, cid, 1)
    assert v1["question"]["dispute_type"] == "marketplace_payment"
    ids = {h["id"] for h in v1["hypotheses"]}
    assert ids == {"H1", "H2", "H3", "H4", "H5"}  # five distinguishable explanations, four of them challenge the allegation
    assert v1["comparison"][0]["id"] == "H1"
    assert all(c["label"] != "strongly_supported" or c["contradicting"] == 0 for c in v1["comparison"])
    assert any(n["id"] == "bank_status" for n in v1["next_evidence"])  # the engine asks for the bank's record
    assert v1["review"]["status"] == "passed" and v1["review"]["citations_checked"] > 0
    assert v1["baseline"]["considered_alternatives"] == 0
    for row in v1["matrix"]:  # every cell cites real segments of real files
        for cell in row["cells"].values():
            assert cell["state"] in ("supports", "contradicts", "inconclusive", "not_evaluated")
            for ref in cell["refs"]:
                assert ref["evidence_id"] == row["evidence_id"] and ref["segment_id"]

    # Stage 2: the bank confirms the payment failed and was reversed.
    r = client.post(f"/api/cases/{cid}/evidence", files=[("files", ("stage2_bank_confirmation.pdf", (DATA / "stage2_bank_confirmation.pdf").read_bytes()))],
                    data={"category": "bank confirmation", "collection_source": "Letter from the payer's bank, 9 May 2026"}, headers=auth(tok))
    assert r.json()["accepted"] == 1
    assert client.post(f"/api/cases/{cid}/analyse", headers=auth(tok)).status_code == 202
    v2 = _wait_version(client, tok, cid, 2)
    labels = {c["id"]: c["label"] for c in v2["comparison"]}
    assert v2["comparison"][0]["id"] == "H4", v2["comparison"]
    assert labels["H1"] == "contradicted"
    assert v2["changes"]["leading_changed"] and v2["changes"]["leading_before"] == "H1" and v2["changes"]["leading_after"] == "H4"
    h1 = next(x for x in v2["changes"]["changed"] if x["id"] == "H1")
    assert h1["to"] == "contradicted" and "New evidence" in h1["because"]
    versions = client.get(f"/api/cases/{cid}/hypothesis-lab", headers=auth(tok)).json()["versions"]
    assert [v["version"] for v in versions][-2:] == [v2["version"] - 1, v2["version"]]  # earlier version preserved

    # Investigator feedback: add a hypothesis, challenge one, approve, export.
    a = client.post(f"/api/cases/{cid}/hypothesis-lab/custom", json={"title": "Buyer cancelled the order", "keywords": ["cancel"]}, headers=auth(tok)).json()
    assert any(h["source"] == "investigator" for h in a["hypotheses"])
    a = client.post(f"/api/cases/{cid}/hypothesis-lab/H2/challenge", json={"note": "No courier record was ever produced"}, headers=auth(tok)).json()
    assert "No courier record" in a["counter"]["H2"]["challenges"][0]
    a = client.post(f"/api/cases/{cid}/hypothesis-lab/H5/reject", json={"note": "Listing and chat number match"}, headers=auth(tok)).json()
    assert next(c for c in a["comparison"] if c["id"] == "H5")["label"] == "rejected"
    ok = client.post(f"/api/cases/{cid}/hypothesis-lab/approve", json={"decision": "approved", "note": "Reviewed"}, headers=auth(tok)).json()
    assert ok["approval"]["status"] == "approved"
    html = client.get(f"/api/cases/{cid}/hypothesis-lab/report", headers=auth(tok)).text
    assert "Alternative hypothesis assessment" in html and "H4" in html and "not findings of guilt" in html
