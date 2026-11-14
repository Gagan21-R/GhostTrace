# Demo script (about 8 minutes)

Preparation (once):
```bash
cd backend
python scripts/load_demo.py --scenarios     # ~2-3 min: two demo cases + all Scenario Lab runs
uvicorn app.main:app --port 8000            # terminal 1
cd ../frontend && npm run dev               # terminal 2 → http://localhost:5173
```
Sign in with the seeded admin account from `.env`.

## 1. Phishing and online fraud (flagship demo)
Open **Cases → DEMO · KYC phishing and UPI payment fraud**.
1. **Evidence** – 12 files (EML, PNG screenshots, WhatsApp export, CSV statement, SMS, DOCX statement, WAV voicemail). Every original has its SHA-256; open any file to see extracted segments with locations, extractor and version.
2. **Timeline** – email 09:12 → WhatsApp 09:31 → payment 09:47 (all +05:30). The statement's "11 March" payment date is flagged as a conflict. Toggle *Show file & upload times* to see metadata/system times kept apart from event times.
3. **Evidence DNA** – the receipt copy is a *duplicate*; the email forwarded to the bank is *derived* from the phishing email. 12 files collapse into 10 independent source groups; the UTR appears in several files but fewer independent sources.
4. **Contradictions** – receipt UPI ref `407215583921` vs bank UTR `407215538921`: a *direct* contradiction (two transposed digits). Click a source chip to open the exact OCR line / CSV row.
5. **Challenge Centre** – hypothesis, supporting claims with verification badges, the counter-agent's challenge ("the money trail is not established"), decision **SUPPORTED** (with reservations) and the number of independent sources. Use *Verify a claim*: cite the bank SMS and expect `999999999999` → **rejected**.
6. **Missing Evidence** – ranked recommendations, e.g. obtain the bank's detail for both references; expand one to see what it would confirm/disprove, the authorised source and the score breakdown.
7. **What-If Lab** – "This evidence item is unrelated" → pick the bank SMS. The HYPOTHETICAL result shows what changes (decision, independent-source count, contradictions and gaps added/removed) and what would resolve it; the real case is unchanged. Note that the duplicate receipt copy keeps the reference conflict alive - copies are handled explicitly, not assumed away. Branch it with a second assumption and compare branches.
8. **Replay** – press *Play from start*: upload → hash → validation → extraction → agents → dependency/contradiction discoveries → hypothesis → counter-investigation → verification → reviewer decision → report. Each step links to what it produced.
9. **Reports** – generate a report; preview it with linked `[EV-xxx | location]` citations; download PDF, DOCX or HTML.

## 2. Whistleblower retaliation (HOLD done right)
Open **DEMO · Ethics complaint and subsequent access changes**.
* Timeline: complaint 6 Mar → manager chat 7 Mar → access revoked 11 Mar → removed from meetings 13 Mar; the meeting recording (MP4) is read via keyframe OCR and transcription.
* Contradictions: HR says access changed 3 Mar, the IAM log says 11 Mar; HR says complaint received 9 Mar, the email was sent 6 Mar.
* Challenge Centre: the counter-agent finds the scheduled access-review policy; the reviewer returns **INCONCLUSIVE** – timing alone does not establish the reason. Missing Evidence asks for the change ticket and approver.

## 3. Scenario Lab and evaluation
**Scenario Lab** shows five scenarios plus a negative control, each with a briefing, dataset preview and expected outcome. Start any run to watch the live execution trace. **Evaluation** shows the latest measured metrics per scenario (precision/recall, dependency detection, timestamp accuracy, OCR/ASR similarity, unsupported-claim rate); anything not measured reads NOT EVALUATED.
