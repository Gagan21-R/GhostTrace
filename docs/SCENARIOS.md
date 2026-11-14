# Scenario Lab

Each scenario is a synthetic evidence dataset in native formats (built by `backend/app/scenarios/builder.py`, stored in `backend/scenario_data/<id>/` with a `manifest.json` of hashes and collection notes) plus a ground truth (`backend/app/scenarios/definitions.py`).

A run creates a fresh case, ingests the files through the **same intake endpoint logic** as a user upload, runs the processing and adversarial graphs, then scores the output in `evaluator.py`. Nothing about the outcome is hard-coded.

| # | Scenario | Files | Planted inconsistencies | Expected |
|---|---|---|---|---|
| 1 | Phishing & online fraud | 10 (EML×3, PNG×2, WhatsApp TXT, CSV, TXT, DOCX, WAV) | receipt UPI ref vs bank UTR (transposed digits); statement payment date vs bank date | PASS |
| 2 | Account compromise | 8 (EML×4, CSV log, WhatsApp TXT, DOCX, PNG) | alert says Windows/Chrome, log says Linux/Firefox; statement denies sharing a code the holder's own message sent; truncated log | PASS |
| 3 | Disappearing evidence preservation | 8 (PNG×3, JPG, JSON DM export, CSV collection log, TXT×2) | collection-log hash ≠ file; DM export incomplete (IDs missing, unsent); missing attachment; deleted post never captured; item without collection info | PASS |
| 4 | Whistleblower retaliation | 10 (EML×3, CSV×2, PDF policy, JSON chat, XLSX, DOCX, TXT) | HR says access changed 3 Mar, log says 11 Mar; complaint 6 Mar vs "received 9 Mar"; no ticket/approver on revocation | **HOLD** – timing alone does not establish the reason |
| 5 | Marketplace & delivery dispute | 9 (EML×3, PDF×2, PNG, JPG, JSON chat, CSV) | qty 50 vs 40; invoice ₹62,500 vs paid ₹65,200 (= ₹2,700 express shipping, found by the counter-agent); OD-48213 vs OD-48231; delivered 16 vs 18 Mar; refund promised, never evidenced | PASS |
| 6 | Negative control: sparse account records | 2 (DOCX, PNG) | none – insufficient evidence | **HOLD** |

Each dataset also contains irrelevant/control records (e.g. an authenticated Flipkart newsletter, an unrelated order `OD-51120`) that must **not** be flagged.

## Outcome rules (deterministic)
- **FAIL** – a processing stage failed, a *critical* expected finding was missed, or a forbidden finding appeared (e.g. a control record flagged, a guilt/identity claim, a link to an unrelated order).
- **HOLD** – nothing critical missed or violated, but the skeptical reviewer's verdict is `contested` or `insufficient_evidence`.
- **PASS** – otherwise.
The report also states whether the outcome matches the scenario's expected outcome.

## Measured metrics
critical/all findings matched · contradiction precision & recall (allowed categories excluded from false positives) · entity precision/recall/F1 on scored types · timeline pairwise ordering accuracy · OCR character similarity vs reference lines · ASR similarity vs reference transcript · hash verification accuracy (original re-hash + 1-bit tamper simulation per file) · source-reference coverage · unsupported-claim rate (Verification agent) · false-positive count · processing time · pending human reviews.

## Ground-truth schema (also accepted for custom datasets)
```json
{
  "expected_outcome": "PASS",
  "findings": [
    {"id": "F1", "critical": true, "type": "entity", "description": "Sender extracted", "match": {"type": "email", "value": "x@y.z"}},
    {"id": "F2", "critical": true, "type": "contradiction", "description": "...", "match": {"category": "transaction_reference_mismatch", "values": ["A1", "A2"]}},
    {"id": "F3", "critical": false, "type": "gap", "description": "...", "match": {"category": "refund_unconfirmed"}},
    {"id": "F4", "critical": true, "type": "hypothesis", "description": "...", "match": {"pattern": "phishing_payment_fraud"}},
    {"id": "F5", "critical": true, "type": "verdict", "description": "...", "match": {"verdicts": ["contested", "insufficient_evidence"]}}
  ],
  "allowed_contradictions": [{"category": "date_conflict"}],
  "forbidden": [{"type": "text", "pattern": "is guilty", "description": "No guilt statements"}],
  "scored_entities": {"types": ["email", "phone"], "values": ["x@y.z"]},
  "timeline_sequence": [{"file": "a.eml", "contains": "KYC"}, {"file": "b.csv", "contains": "debit"}],
  "ocr_expect": {"shot.png": ["Amount Paid: Rs 100.00"]}
}
```
Finding types: `entity`, `suspicious_url`, `contradiction`, `gap`, `relationship`, `hypothesis`, `verdict`, `counter`, `extraction`, `integrity`.

## Rebuilding datasets
```bash
cd backend
python -m app.scenarios.builder --force
```
The voicemail WAV is synthesised with the Windows SAPI voice; on other OSes the audio file is skipped (it is already committed).
