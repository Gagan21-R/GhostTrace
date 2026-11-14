# EVIDENCE-X — Implementation log

## 2026-11-14 · Session 1 — initial build

**Assessment.** No existing EVIDENCE-X repository was found, so a new project was created in `Desktop/EVIDENCE-X`. Environment: Windows 11, Python 3.12, Node 24, no Docker, no PostgreSQL/Neo4j. Windows Application Control blocks some compiled extensions (spaCy `srsly`, `xxhash`, SQLAlchemy 2.1 Cython modules).

**Decisions**
- Local tested path: SQLite + local write-once storage + NetworkX; Docker Compose provided for PostgreSQL/pgvector + MinIO (+ Neo4j profile).
- SQLAlchemy pinned to 2.0.x (pure-Python fallback when the Cython modules are blocked).
- LangGraph kept; a documented hashlib shim stands in for `xxhash`, which LangGraph only uses for task IDs.
- OCR via RapidOCR (PaddleOCR PP-OCR models on ONNX Runtime) with PaddleOCR optional; ASR via faster-whisper. PyAV 19 broke faster-whisper's decoder, so audio is decoded in-house to 16 kHz PCM.
- All findings are deterministic rules; the LLM (Anthropic) is an optional, verified augmentation of the counter-agent.

**Built**
- Backend: models, auth/RBAC, case management, evidence vault and intake, integrity/audit, extraction pipeline, entity/relationship, timeline, contradiction (8 rules), gaps (13 rules), 11-agent LangGraph orchestration, adversarial engine, PDF reports, Scenario Lab (5 datasets + control, ground truth, evaluator, runner), REST API.
- Frontend: React + TS + Tailwind + Recharts + Cytoscape + Framer Motion; dashboard, cases, case workspace (10 tabs), Scenario Lab, results, history, reports, audit, users, settings.

**Bugs found by the evaluator and fixed:** phone regex failing at sentence-ending full stops; URL-shortener check matching `t.co` inside `flipkart.com`; DOCX paragraphs merged; collection-log hash window too narrow; event classifier preferring "complaint" over "access change" (now earliest cue wins); email send-time treated as event time; SQLite dropping tzinfo (UTC TypeDecorator); counter-agent citing an unrelated email's SPF pass; hypothesis anchored on the wrong order; stray backspace characters introduced by a patch script.

**Result:** 18 tests passing; all 6 scenarios match their expected outcomes.

## 2026-11-14 · Session 2 — revised master prompt

**Gap analysis against the revised brief** and changes made:
- **Migrations:** Alembic introduced (`backend/migrations`, revision `0001`); startup now runs `upgrade head` instead of `create_all`. Pre-migration databases are refused with instructions.
- **Auth:** `POST /api/auth/logout` with JWT `jti` denylist (`revoked_tokens`), `PATCH /api/auth/me`, `POST /api/auth/me/password`; profile page.
- **Responsible AI:** `cases.allow_external_ai` (default off, owner-only). The counter-agent does not contact the LLM provider unless authorised and records why.
- **Formats:** WEBP intake with signature validation.
- **Findings:** contradiction `priority` (deterministic, from category and confidence); gap `why_it_matters`.
- **Spec endpoints:** evidence preview/history, processing-status, extracted-data, relationships, evidence-gaps, investigate, agent-executions, timeline export (CSV/JSON), case history, case reports, report download/preview, scenario `runs` (create), run status/results/report, scenario history, `POST /scenarios/compare`.
- **Ground truth:** expected events with local timestamps (new *timestamp accuracy* metric), irrelevant control records (violation if cited or linked), ambiguous records (reported as flagged/not flagged), verification ceiling on unsupported claims.
- **Reports:** incident summary and a standalone limitations/uncertainty section; gap rationale and contradiction priority included.
- **Dashboard:** pending processing, recent cases, recent reports, Scenario Lab activity.
- **Frontend:** upload progress, timeline search + export, graph search, priority filter, gap rationale, full-page evidence preview, report preview page, case edit modal, external-AI toggle, case history, execution trace with agent JSON outputs, timestamp/irrelevant/ambiguous panels, profile page, server-side logout.
- **Tests:** `tests/test_spec.py` (migrations, logout revocation, password change, WEBP, AI authorisation, every new endpoint, cross-case isolation on each, SQL-injection probes, scenario compare/history/status/results).

**Result:** full suite `pytest -m "scenario or not scenario"` — **23 passed** (4 min 27 s) on a clean database, including all 6 scenario regressions. All six scenarios still match their expected outcome with the stricter ground truth (timestamp accuracy 100%, no control-record violations). New UI checked in the browser: run page execution trace and ground-truth panels, case overview (edit, AI authorisation, history), contradiction priority, report preview.

## 2026-11-14 · Session 3 — forensic-intelligence brief

**Gap analysis.** The third brief added four flagship capabilities (Evidence Challenge Engine decisions, Evidence DNA, Missing Evidence Predictor, Investigation Replay), a What-If Lab, integrity inspection, more extraction formats, timeline lanes, 20-section reports in three formats, an evaluation dashboard, a dark console UI and frontend tests. Existing working code was kept.

**Built**
- Migration `0002`: evidence_dependencies, integrity_findings, hypothesis_evidence, verification_results, evidence_recommendations, whatif_scenarios, investigation_events; columns for duplicate/perceptual hash, contradiction classification, hypothesis decision/rank.
- `replay.py` + hooks in intake, processing, every agent, contradictions, reviews, reports and What-If.
- `analysis/dna.py` (dependency classes, source groups, fingerprints), `analysis/integrity.py` (inspection), two new processing agents.
- Challenge Engine: every candidate challenged, Pydantic contracts (`agents/schemas.py`), time/candidate limits, decisions, independence-aware reviewer, `agents/predictor.py`, persisted verification results and hypothesis–evidence links, manual claim verification.
- `agents/whatif.py`: in-memory sandbox, six assumption types, branches, diff.
- Extraction: MBOX, HTML, scanned-PDF OCR (pypdfium2), video keyframe OCR + ASR, extractor versions/parameters. Duplicates are now accepted and flagged (previously rejected).
- Timeline: file/system lanes, "unknown" timezone, silent periods, simultaneous events, header-vs-body comparison.
- Reports rebuilt as a content model with three renderers (PDF/DOCX/HTML) and linked citations.
- Datasets: duplicate receipt and forwarded email (S1), duplicate and re-compressed screenshots (S3), forwarded HR email and meeting MP4 (S4), delivery screenshot (S5); dependency ground truth and metrics.
- Frontend: dark console theme (central palette remap), active-case navigation, Entities, Evidence DNA, Challenge Centre, Missing Evidence, What-If Lab, Replay, Evaluation pages, evidence detail panels, graph shortest path, timeline insights, report preview with citations, dashboard additions; Vitest suite.
- Docs: ARCHITECTURE, SECURITY, DEMO, API additions; `scripts/load_demo.py`.

**Issues found and fixed during the session:** perceptual hash alone produced false near-duplicates between different UI screenshots (now also requires text agreement); OCR spacing loss defeated word-shingle similarity (switched to character n-grams); "shared source" over-merged distinct records from one issuer when counting independence (only copies/derivatives collapse now); the phishing pattern could anchor on a later forwarded email (now the earliest); predictor produced duplicate questions; the Vite dev server needed a restart after the Tailwind palette change.

**Result:** backend `pytest -m "scenario or not scenario"` — **34 passed** (28 + 6 scenario regressions, clean database); frontend 8 Vitest tests and production build pass; all 6 scenarios match expected outcomes with dependency precision/recall 100%.
