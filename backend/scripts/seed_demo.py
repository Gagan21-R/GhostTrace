"""Seed a demo workspace with fully analysed cases so every page has real, already-computed content.

Everything goes through the real API (in-process): evidence intake with SHA-256, processing, challenge engine,
hypothesis engine, voice recording with language detection, reviews, what-if, reports. Nothing is hand-written into
result tables. All people, numbers and companies are fictional (from the scenario datasets).

Usage:  python scripts/seed_demo.py            (idempotent: skips cases that already exist)
Demo user passwords are generated and written to backend/data/demo_users.txt (git-ignored).
"""
from __future__ import annotations

import json
import secrets
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import select  # noqa: E402

from app.config import get_settings  # noqa: E402
from app.db import SessionLocal  # noqa: E402
from app.main import app  # noqa: E402
from app.models import Case, ContactMessage, User  # noqa: E402
from app.security import hash_password  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "scenario_data"
S = get_settings()

CASES = [
    ("s1-phishing", "KYC phishing and UPI payment - complainant A. Rao", "fraud", "high",
     "A KYC-themed email led the complainant to a WhatsApp 'KYC desk' and a UPI payment of Rs 24,999; the promised refund never came.",
     "Establish the chain email -> site -> chat -> payment and identify where the money went."),
    ("s7-whatsapp-impersonation", "Threat messages from a classmate's WhatsApp - complainant S. Kulkarni", "harassment", "high",
     "Two threatening messages arrived from Rohan Verma's number at 22:41; Rohan says someone else was logged into his WhatsApp.",
     "Test whether the screenshot is genuine and whether the account holder sent the messages."),
    ("s8-fabricated-screenshot", "Alleged threat by former business partner - complainant K. Malhotra", "harassment", "medium",
     "A complaint of criminal intimidation rests on one WhatsApp screenshot.",
     "Check the screenshot against both phones' exports and the account log."),
    ("s30-market-new-evidence", "Laptop paid for but not delivered - complainant A. Menon", "commercial_dispute", "high",
     "Rs 50,000 paid by UPI to a marketplace seller; laptop not delivered; buyer alleges fraud.",
     "Test competing explanations: fraud, delay, wrong destination, failed payment, impersonation."),
    ("s22-market-delivery-delay", "Delayed laptop delivery dispute - BazaarHub order BH-778120", "commercial_dispute", "medium",
     "Buyer alleges fraud; seller says the courier is delayed.", "Establish whether a genuine shipment exists."),
    ("s10-sim-swap", "SIM swap and net-banking takeover - D. Joshi", "account_compromise", "critical",
     "Two IMPS transfers of Rs 95,000 and Rs 90,000 at night after the SIM was re-issued.", "Reconstruct SIM, OTP, login and transfer order."),
    ("s13-business-email-compromise", "Vendor bank-detail change fraud - BrightBuild Pvt Ltd", "fraud", "high",
     "Rs 8.4 lakh paid to a 'new' vendor account requested from a lookalike domain.", "Identify the lookalike domain and the payment trail."),
    ("s19-ransomware", "Ransomware on hospital file server FS-01", "extortion", "critical",
     "18,442 files renamed after an RDP sign-in from an anonymising IP; ransom demanded.", "Reconstruct the intrusion and preserve logs."),
]


def login(c, email, pw):
    r = c.post("/api/auth/login", json={"email": email, "password": pw})
    r.raise_for_status()
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def ensure_users(db) -> dict:
    out = {}
    path = ROOT / "data" / "demo_users.txt"
    lines = []
    for email, name, role in [("priya.desai@demo.ghosttrace.in", "SI Priya Desai", "investigator"), ("arjun.rao@demo.ghosttrace.in", "Arjun Rao", "reviewer"),
                              ("meena.k@demo.ghosttrace.in", "Meena Krishnan", "viewer")]:
        u = db.scalar(select(User).where(User.email == email))
        if not u:
            pw = "Demo-" + secrets.token_urlsafe(9)
            u = User(email=email, full_name=name, role=role, password_hash=hash_password(pw))
            db.add(u)
            lines.append(f"{email}\t{role}\t{pw}")
        out[role] = u
    db.commit()
    if lines:
        with open(path, "a", encoding="utf-8") as f:
            f.write("\n".join(lines) + "\n")
    return out


def wait_idle(c, h, cid, timeout=600):
    t0 = time.time()
    while time.time() - t0 < timeout:
        runs = c.get(f"/api/cases/{cid}/runs", headers=h).json()
        if runs and not any(r["status"] in ("queued", "running") for r in runs):
            time.sleep(2)  # the chain starts its next stage right after the previous one
            runs = c.get(f"/api/cases/{cid}/runs", headers=h).json()
            if not any(r["status"] in ("queued", "running") for r in runs):
                return runs
        time.sleep(2)
    raise TimeoutError(cid)


def main():
    c = TestClient(app)
    h = login(c, S.seed_admin_email, S.seed_admin_password)
    db = SessionLocal()
    users = ensure_users(db)
    existing = {x.title for x in db.scalars(select(Case))}
    made = []
    for sid, title, ctype, prio, desc, obj in CASES:
        if title in existing:
            print("exists:", title)
            continue
        cid = c.post("/api/cases", json={"title": title, "case_type": ctype, "priority": prio, "description": desc, "objective": obj,
                                         "default_timezone": "+05:30"}, headers=h).json()["id"]
        for email, access in (("priya.desai@demo.ghosttrace.in", "editor"), ("arjun.rao@demo.ghosttrace.in", "editor"), ("meena.k@demo.ghosttrace.in", "viewer")):
            c.post(f"/api/cases/{cid}/members", json={"email": email, "access": access}, headers=h)
        d = DATA / sid
        for m in json.loads((d / "manifest.json").read_text(encoding="utf-8")):
            c.post(f"/api/cases/{cid}/evidence", files=[("files", (m["file"], (d / m["file"]).read_bytes()))],
                   data={"category": m["category"], "tags": ",".join(m.get("tags", [])), "collection_source": m.get("collection_source") or "",
                         "collected_by": m.get("collected_by") or ""}, headers=h)
        c.post(f"/api/cases/{cid}/analyse", headers=h)
        wait_idle(c, h, cid)
        print("analysed:", title)
        made.append((sid, cid))

    for sid, cid in made:
        if sid == "s30-market-new-evidence":  # the revision moment: new bank evidence changes the leading explanation
            f = DATA / sid / "stage2_bank_confirmation.pdf"
            c.post(f"/api/cases/{cid}/evidence", files=[("files", (f.name, f.read_bytes()))],
                   data={"category": "bank confirmation", "collection_source": "Letter from the payer's bank, 9 May 2026"}, headers=h)
            c.post(f"/api/cases/{cid}/analyse", headers=h)
            wait_idle(c, h, cid)
            c.post(f"/api/cases/{cid}/hypothesis-lab/approve", json={"decision": "approved", "note": "Bank letter verified by phone with the branch."}, headers=h)
        if sid == "s1-phishing":  # a recorded statement (language detected, then re-analysed)
            wav = (DATA / sid / "10_voicemail.wav").read_bytes()
            c.post(f"/api/cases/{cid}/voice", files={"audio": ("voice.wav", wav, "audio/wav")}, data={"consent": "true", "speaker": "Ananya Rao (playback of voicemail)"}, headers=h)
            wait_idle(c, h, cid)
        # human review decisions so review panels and dashboards have history
        cons = c.get(f"/api/cases/{cid}/contradictions", headers=h).json()
        for i, x in enumerate(cons[:2]):
            c.patch(f"/api/contradictions/{x['id']}", json={"status": "confirmed" if i == 0 else "dismissed",
                                                             "note": "Checked against the original file." if i == 0 else "Two different events."}, headers=h)
        gaps = c.get(f"/api/cases/{cid}/gaps", headers=h).json()
        if gaps:
            c.patch(f"/api/gaps/{gaps[0]['id']}", json={"status": "resolved", "note": "Record requested from the provider."}, headers=h)
        recs = c.get(f"/api/cases/{cid}/recommendations", headers=h).json()
        recs = recs.get("recommendations", recs) if isinstance(recs, dict) else recs
        if recs:
            c.patch(f"/api/recommendations/{recs[0]['id']}", json={"status": "requested"}, headers=h)
        c.post(f"/api/cases/{cid}/reports", json={"redact": False}, headers=h)
        if sid == "s7-whatsapp-impersonation":
            evs = c.get(f"/api/cases/{cid}/evidence", headers=h).json()
            shot = next((e for e in evs if e["filename"].startswith("01_")), None)
            if shot:
                c.post(f"/api/cases/{cid}/whatif", json={"title": "What if the screenshot is excluded?",
                                                         "assumption": {"type": "exclude_evidence", "evidence_id": shot["id"]}}, headers=h)
        print("reviewed + reported:", sid)

    if not db.scalar(select(ContactMessage).limit(1)):
        db.add_all([ContactMessage(name="Inspector R. Naik", email="r.naik@police.example", organisation="Cyber Crime PS, Mysuru", topic="demo",
                                   message="We would like a demo of the hypothesis lab for marketplace fraud complaints."),
                    ContactMessage(name="Legal team", email="legal@bank.example", organisation="Bank of Deccan", topic="partnership",
                                   message="Can reports be exported with redaction for sharing with customers?")])
        db.commit()
    from translate_demo_cases import main as add_translations
    add_translations()
    print("done")


if __name__ == "__main__":
    main()
