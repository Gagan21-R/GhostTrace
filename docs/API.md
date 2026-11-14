# EVIDENCE-X API

Interactive OpenAPI docs: `http://localhost:8000/docs` (use **Authorize** with your email/password).

All endpoints except `/api/auth/register`, `/api/auth/login`, `/api/auth/token` and `/api/health` require `Authorization: Bearer <jwt>`.

Errors use one envelope:
```json
{ "error": { "code": "http_404", "message": "Case not found", "details": null } }
```
Validation errors: `code: "validation_error"`, `details: [{ "field": "...", "message": "..." }]`.

## Authentication & users
| Method | Path | Notes |
|---|---|---|
| POST | `/api/auth/register` | `{email, full_name, password}` → token. New users are `investigator`. Password ≥10 chars, upper-case + digit |
| POST | `/api/auth/login` | `{email, password}` → `{access_token, user, permissions}`; throttled after 8 failures / 5 min |
| POST | `/api/auth/token` | OAuth2 password form (Swagger) |
| GET | `/api/auth/me` | current user + permissions |
| GET | `/api/auth/permissions` | role and permission list |
| GET | `/api/users` | admin |
| PATCH | `/api/users/{id}` | admin: `{role?, is_active?, full_name?}` |

## Cases
| Method | Path | Notes |
|---|---|---|
| GET | `/api/cases?q=&status=&include_scenarios=` | only cases you are a member of (admins: all) |
| POST | `/api/cases` | `{title, description, objective, case_type, priority, default_timezone}` |
| GET | `/api/cases/{id}` | summary, counts, members, latest verdict |
| PATCH | `/api/cases/{id}` | update fields / status |
| POST | `/api/cases/{id}/archive` | |
| POST | `/api/cases/{id}/members` | owner only: `{email, access: owner|editor|viewer}` |
| DELETE | `/api/cases/{id}/members/{user_id}` | owner only |

## Evidence
| Method | Path | Notes |
|---|---|---|
| POST | `/api/cases/{id}/evidence` | multipart `files[]` + `category, tags, collection_source, collected_by, collected_at`. Per-file result; rejects bad signatures, executables, oversize, duplicates |
| GET | `/api/cases/{id}/evidence?q=&type=&status=&category=` | `q` searches names, tags, extracted text and SHA-256 |
| GET | `/api/evidence/{id}` | metadata, segments, derivatives, processing history |
| PATCH | `/api/evidence/{id}` | category, tags, collection info, legal hold |
| POST | `/api/evidence/{id}/verify` | re-hash original vs intake hash → `match|mismatch|missing` |
| POST | `/api/cases/{id}/verify-all` | |
| GET | `/api/evidence/{id}/file[?derivative=]` | original or derivative, sandboxed headers; access is audited |
| DELETE | `/api/evidence/{id}` | soft delete (blocked under legal hold) |

## Analysis
| Method | Path | Notes |
|---|---|---|
| POST | `/api/cases/{id}/process` | 202 → `{run_id}`; runs the 7 processing agents in the background |
| POST | `/api/cases/{id}/adversarial` | 202 → `{run_id}`; runs the 5 adversarial agents |
| GET | `/api/cases/{id}/runs` | run list with progress and log |
| GET | `/api/runs/{run_id}` | status, stage, progress, per-agent outputs |
| GET | `/api/cases/{id}/entities[?type=]` | entities with mentions (source-linked) and URL risk indicators |
| GET | `/api/cases/{id}/timeline` | events with `timestamp_kind`, raw timestamp, timezone info, conflict flag |
| GET | `/api/cases/{id}/graph[?include_documents=]` | nodes/edges with `basis: observed|inferred` and evidence links |
| GET | `/api/cases/{id}/contradictions` | |
| PATCH | `/api/contradictions/{id}` | `{status: pending|confirmed|dismissed, note}` |
| GET | `/api/cases/{id}/gaps` | |
| PATCH | `/api/gaps/{id}` | `{status: open|resolved|dismissed, note}` |
| GET | `/api/cases/{id}/hypotheses` | hypothesis, supporting/counter evidence, verification, assessment, agent outputs |
| PATCH | `/api/hypotheses/{id}` | human review `{status: accepted|rejected|needs_more_evidence|pending, note}` |

## Scenario Lab
| Method | Path | Notes |
|---|---|---|
| GET | `/api/scenarios` | cards with last run |
| GET | `/api/scenarios/{sid}` | briefing, files, expected findings, planted items, runs |
| GET | `/api/scenarios/{sid}/files/{name}` | dataset file (sandboxed) |
| POST | `/api/scenarios/{sid}/run` | 202 → run |
| POST | `/api/scenarios/custom/run` | multipart `files[]` + optional `ground_truth` JSON |
| GET | `/api/scenarios/runs[?scenario_id=]` | history |
| GET | `/api/scenarios/runs/{run_id}` | progress, evaluation, metrics |
| GET | `/api/scenarios/runs/compare?ids=a,b,c` | metric comparison |
| GET | `/api/scenarios/runs/{run_id}/report.pdf` | |

## Reports, dashboard, audit, system
| Method | Path | Notes |
|---|---|---|
| POST | `/api/cases/{id}/reports` | `{redact: bool}` → PDF report record |
| GET | `/api/reports[?case_id=]`, `/api/reports/{id}`, `/api/reports/{id}/pdf` | |
| GET | `/api/dashboard` | live statistics for cases you can access |
| GET | `/api/cases/{id}/audit` | case audit trail (hash-chained) |
| GET | `/api/audit/verify` | verify the full audit chain |
| GET | `/api/system/status` | engines, orchestrator, storage, LLM mode |
| POST | `/api/system/retention/apply` | admin: purge archived, non-held evidence older than `RETENTION_DAYS` |
| GET | `/api/health` | |

## Specification endpoints (added in session 2)
These implement the paths named in the EVIDENCE-X master specification (all under `/api`). Aliases call the same handlers as the endpoints above, so permissions, auditing and responses are identical.

| Method | Path | Notes |
|---|---|---|
| POST | `/api/auth/logout` | revokes the presented JWT (denylisted by `jti`) |
| PATCH | `/api/auth/me` | `{full_name}` |
| POST | `/api/auth/me/password` | `{current_password, new_password}` |
| PATCH | `/api/cases/{id}` | also accepts `allow_external_ai` (**owner only**; default `false`) |
| GET | `/api/cases/{id}/history` | case activity for any member |
| GET | `/api/evidence/{id}/preview` | original, inline, sandboxed |
| GET | `/api/evidence/{id}/history` | processing/access history (audit events) |
| GET | `/api/cases/{id}/processing-status` | evidence counts by status + latest processing run |
| GET | `/api/cases/{id}/extracted-data?evidence_id=&limit=&offset=` | paginated extracted segments |
| GET | `/api/cases/{id}/relationships[?basis=observed|inferred]` | relationship list |
| GET | `/api/cases/{id}/evidence-gaps` | alias of `/gaps` (includes `why_it_matters`) |
| POST | `/api/cases/{id}/investigate` | alias of `/adversarial` |
| GET | `/api/cases/{id}/agent-executions[?run_id=]` | per-agent structured outputs |
| GET | `/api/cases/{id}/timeline/export?format=csv|json` | timeline export |
| GET | `/api/cases/{id}/reports` | reports for a case |
| GET | `/api/reports/{id}/download` · `/preview` | PDF as attachment / inline |
| POST | `/api/scenarios/{sid}/runs` | start a run (alias of `/run`) |
| GET | `/api/scenarios/runs/{run_id}/status` | stage, progress, recorded agent executions |
| GET | `/api/scenarios/runs/{run_id}/results` | evaluation (409 until completed) |
| GET | `/api/scenarios/runs/{run_id}/report` | scenario PDF |
| GET | `/api/scenarios/{sid}/history` | runs of one scenario |
| POST | `/api/scenarios/compare` | `{run_ids: [2..6 ids]}` |

Contradictions now include `priority` (`high|medium|low`, derived deterministically from category and confidence).

## Database migrations
Alembic migrations live in `backend/migrations`. They run automatically at startup (`upgrade head`). Manual use:
```bash
cd backend
python -m alembic upgrade head
python -m alembic revision --autogenerate -m "describe change"
```

## Flagship intelligence endpoints (session 3)
| Method | Path | Notes |
|---|---|---|
| GET | `/api/cases/{id}/dna` | Evidence DNA: dependencies (duplicate, near_duplicate, derived, shared_source, independent, uncertain) with matched attributes and source locations, shared identifiers with independent-source counts, source groups |
| GET | `/api/cases/{id}/dependencies` | dependency list |
| GET | `/api/cases/{id}/integrity-findings[?evidence_id=]` | integrity inspection observations (indicators, not proof) |
| GET | `/api/cases/{id}/recommendations` · PATCH `/api/recommendations/{id}` | Missing Evidence Predictor output; status open/requested/collected/not_available |
| GET | `/api/cases/{id}/replay?component=&status=&run_id=&limit=&offset=` | Investigation Replay (persisted events, paginated) |
| POST | `/api/cases/{id}/verify-claim` | `{text, citations:[segment_id], expect:[values], temporal}` → deterministic verification |
| GET | `/api/cases/{id}/verification-results` | persisted verification results (engine, LLM, manual) |
| GET | `/api/cases/{id}/challenge-runs` | candidate hypotheses per challenge run with decisions |
| GET | `/api/cases/{id}/hypotheses` | candidates of the latest challenge run (primary first); `decision` ∈ SUPPORTED/CONTRADICTED/INCONCLUSIVE/HOLD |
| GET/POST | `/api/cases/{id}/whatif` | list / create a HYPOTHETICAL scenario `{title, parent_id?, assumption:{type,...}}` (runs in an isolated sandbox) |
| GET | `/api/whatif/{id}` · POST `/api/whatif/{id}/discard` · GET `/api/cases/{id}/whatif-compare?ids=` | result, discard, compare branches |
| GET | `/api/evidence/{id}/related` | entities, events, related evidence, integrity findings, contradictions for the evidence detail page |
| GET | `/api/cases/{id}/timeline/analysis` | silent periods, simultaneous events across sources, header-vs-body reported times |
| GET | `/api/reports/{id}/docx` · `/api/reports/{id}/html` | DOCX / standalone HTML exports of the 20-section report |
| GET | `/api/evaluation/summary` | latest scenario metrics with definitions; unmeasured metrics are `NOT EVALUATED` |

What-If assumption types: `exclude_evidence {evidence_id}`, `timestamp_override {segment_id, value|null}`, `unlink_identifier {evidence_id, value}`, `different_sender {evidence_id, sender}`, `same_source {evidence_a, evidence_b}`, `narrative {note}`.
Supported upload formats now also include `.mbox`, `.html/.htm` and `.webp`; MP4 video is processed (keyframe OCR + transcription); scanned PDF pages are OCR'd.
