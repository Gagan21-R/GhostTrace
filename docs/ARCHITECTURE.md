# GhostTrace architecture

## Layers

| Layer | What it does | Where |
|---|---|---|
| 1. Evidence Vault | Intake, content-signature validation, SHA-256, write-once originals, derivatives, duplicate flagging | `services/intake.py`, `services/evidence_service.py`, `storage.py` |
| 2. Integrity & provenance | Re-verification, hash-chained audit log, integrity inspection (metadata anomalies, missing headers, inconsistent copies) | `audit.py`, `analysis/integrity.py` |
| 3. Multimodal extraction | Per-format extractors that emit addressable segments (page, row, message, header, OCR line, audio range, video frame) with method, version and confidence | `services/extraction.py`, `services/engines.py`, `services/processing.py` |
| 4. Investigation intelligence | Typed facts → entities, relationships, timeline with timestamp provenance, contradictions, gaps | `analysis/index.py`, `entities.py`, `timeline.py`, `contradictions.py`, `gaps.py` |
| 5. Flagship intelligence | Evidence DNA, Challenge Engine, Missing Evidence Predictor, What-If Lab, Investigation Replay | `analysis/dna.py`, `agents/adversarial.py`, `agents/predictor.py`, `agents/whatif.py`, `replay.py` |
| 6. Reporting & evaluation | 20-section evidence-linked report (PDF/DOCX/HTML), Scenario Lab ground-truth evaluation | `services/report_content.py`, `services/report_render.py`, `scenarios/` |

Frontend: React + TypeScript + Tailwind (dark console theme), Recharts, Cytoscape.js, Framer Motion. Data fetching uses a small typed hook (`lib/hooks.ts`) with polling for long-running jobs.

## Agent orchestration (LangGraph)

```
Processing graph   intake → extraction → entity_intelligence → timeline → relationship → evidence_dna
                   → integrity_inspection → contradiction → evidence_gap
Challenge graph    investigation (all candidate hypotheses, max 3) → counter_investigation (per candidate)
                   → verification (per candidate) → skeptical_review (per candidate) → missing_evidence → report
```

* Every node runs inside `Runner.node`: one retry, a persisted `AgentExecution` (output JSON, mode, attempts, duration), a replay event, and progress for the UI.
* Agent outputs are validated against Pydantic contracts (`agents/schemas.py`) before the next agent runs; a malformed output fails the node instead of propagating.
* The challenge run has a time budget (180 s) and a candidate cap (3).
* The database session lives in the closure, never in graph state.
* LangGraph needs `xxhash` only for task IDs; where Windows Application Control blocks that DLL, `agents/compat.py` supplies a documented hashlib stand-in.

### How the agents differ
| Agent | Input | Job | Never does |
|---|---|---|---|
| Investigation | facts, events, contradictions, relationships | Builds candidate hypotheses from a pattern library; every claim cites segment IDs; inferences and assumptions are listed separately | assert guilt or identity |
| Counter-investigation | the candidate + the whole case | Searches for counter-records, documented alternatives (incl. arithmetic, e.g. a payment difference equal to a shipping fee), weak/inferred associations, missing context | reuse the investigation's own supporting conflicts as counter-evidence |
| Verification | claims + challenges | Deterministic checks: segment exists in this case, quoted values occur in it, timestamp provenance, no guilt/identity language | accept a citation it cannot resolve |
| Skeptical reviewer | all of the above + evidence dependencies | Counts **independent** sources (copies/derivatives collapse), weighs strong counter-evidence, returns SUPPORTED / CONTRADICTED / INCONCLUSIVE / HOLD | mark something SUPPORTED on a single source |
| Missing evidence | unresolved contradictions, inferences, alternatives, open gaps | Ranks what to collect next with an explainable score | assume a record exists or suggest unauthorised access |

## Evidence DNA
For every pair of files: shared identifiers (transaction/order/AWB, email, phone, domain, IP, account, username, amount), character-n-gram text similarity (robust to OCR spacing), perceptual-hash similarity for images (only accepted with agreeing text), and issuer detection (sender domain, platform, provider named in the document or collection note). Relations: duplicate · near-duplicate · derived (containment; forwarded/quoted mail) · shared source · independent · uncertain. Copies and derivatives are merged into **source groups**; corroboration counts are per group.

## What-If isolation
`agents/whatif.py` creates an in-memory SQLite database per scenario, copies the case's evidence rows and segments, applies the assumptions there (exclude evidence, override a timestamp, unlink an identifier, change an email sender, treat two records as one source), and re-runs entities → timeline → DNA → contradictions → gaps → challenge → predictor. Results are stored only on the `WhatIfScenario` row, labelled HYPOTHETICAL, with a before/after diff. External AI is always disabled in the sandbox. Branches store cumulative assumptions.

## Investigation Replay
`replay.emit()` is called by the components themselves at the moment they act (upload, hash, type validation, extraction start/finish/failure, each agent, each dependency, each contradiction, each hypothesis/challenge/verification/decision, human reviews, reports, What-If runs). The replay UI reads these rows in insertion order; nothing is generated after the fact.

## Data model (main tables)
users, revoked_tokens, cases, case_members, evidence, evidence_derivatives, extracted_segments (claims/locations), entities, entity_mentions, relationships, timeline_events, contradictions, evidence_gaps, evidence_dependencies, integrity_findings, analysis_runs (processing jobs & challenge runs), agent_executions, hypotheses, hypothesis_evidence, verification_results, evidence_recommendations, whatif_scenarios, investigation_events, reports, audit_events, scenario_definitions, scenario_runs (evaluation runs).
Name mapping to the brief: ProcessingJob/ChallengeRun → `analysis_runs`; ExtractedClaim → `extracted_segments` (+ typed facts derived in `CaseIndex`); EvidenceHash/Metadata/CollectionRecord → columns on `evidence`; EvaluationRun → `scenario_runs`.
Schema changes are Alembic migrations (`backend/migrations`), applied at startup.

## Storage and infrastructure
Tested path: SQLite + local write-once storage + NetworkX. Provided but not exercised here: PostgreSQL/pgvector, MinIO/S3 (storage backend implemented), Neo4j (not implemented; NetworkX is the graph engine).
