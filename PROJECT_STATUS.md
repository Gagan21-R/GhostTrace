# GhostTrace — Project status

Last updated: 2026-11-14 (session 3). Statuses: **Fully implemented** · **Partially implemented** · **Not implemented** · **Blocked**.
"Tested" = covered by an automated test that passed on the development machine (Windows 11, Python 3.12, CPU only); "browser" = also checked manually in the UI.

## Feature completion

| Feature | Backend | Frontend | Integration | Tested | Status |
|---|---|---|---|---|---|
| Universal Evidence Vault | Multi-file upload, content-signature validation (PDF, DOCX, TXT, CSV, XLSX, JSON, EML, MBOX, HTML, JPG/PNG/WEBP, WAV/MP3, MP4), write-once originals, separate derivatives, duplicate flagging, search, filters, soft delete + legal hold | Drag-and-drop with progress, accept/reject per file, evidence detail page (preview, segments, metadata, integrity checks, related evidence, events, entities, history) | Shared intake path for uploads, demo data and Scenario Lab | API e2e, flagship tests, browser | Fully implemented |
| Integrity & Provenance | SHA-256, re-verification, pre-processing check, hash-chained append-only audit, extractor name/version/parameters, integrity inspection (MIME mismatch, metadata inconsistencies, future/late timestamps, missing email headers, editing software, low OCR confidence, duplicates, inconsistent copies) | Integrity & audit tab separating integrity / provenance / metadata / anomalies; dashboard integrity status | Findings feed reports and replay | Tamper, append-only, chain, inspection tests | Fully implemented |
| Multimodal Extraction | Documents, scanned-PDF OCR, spreadsheets, JSON, email/MBOX, chats, HTML, images (OCR + EXIF), audio (ASR), video (keyframe OCR + ASR); location per segment; unavailable engines reported, never faked | Extracted content with locator, method, confidence | Segments are the citation targets for every finding | Scenario regression (OCR 91–94% char. similarity; ASR 100% on synthetic voicemail; video frames + transcript in S4) | Fully implemented (spaCy NER blocked) |
| Timeline | Provenance kinds (source-reported / metadata / estimated / unknown / system), timezone default or "unknown", ambiguity flags, conflicts, file & upload times on separate lanes, silent periods, simultaneous events, header-vs-body times, CSV/JSON export | Day-grouped timeline, search, filters, lanes toggle, insights panel, source navigation | Conflicts from contradiction agent | Timestamp accuracy and order accuracy 100% on all scored scenarios | Fully implemented |
| Entity & Relationship Intelligence | Entities, mentions, observed vs inferred relations with caveats, centrality | Entities table, Cytoscape graph (search, filters, observed/inferred styling, collapse/expand, shortest path, node/edge evidence) | Graph links open cited segments | API tests, browser | Fully implemented (Neo4j not implemented) |
| Evidence Challenge Engine | All candidate hypotheses challenged; Pydantic-validated agent contracts; deterministic verification; independence-aware reviewer; SUPPORTED/CONTRADICTED/INCONCLUSIVE/HOLD; time and candidate limits; retries; persisted executions, verification results and hypothesis–evidence links | Challenge Centre: candidates, decision, cited claims with verification badges, challenges, assumptions, next steps, limitations, manual claim verification, human review | Feeds predictor, reports, replay, evaluation | Decision, rejection of wrong/fabricated/guilt claims, failed-agent and no-LLM tests; expected decision in all 6 scenarios | Fully implemented (LLM augmentation untested) |
| Evidence DNA | Shared identifiers, text and image similarity, issuer detection, duplicate / near-duplicate / derived / shared-source / independent / uncertain, source groups, independent-source counts | DNA tab: dependencies with matched values and locations, source groups, fingerprint | Reviewer counts independent sources; integrity flags inconsistent copies | Dependency precision/recall 100% on all scored scenarios | Fully implemented |
| Missing Evidence Predictor | Questions from contradictions, inferences, alternatives and gaps; explainable 5-factor score; authorised sources; status tracking | Ranked list with rationale, confirm/disprove, score breakdown, status buttons | Runs inside the challenge graph | Ranking/explanation test | Fully implemented |
| What-If Lab | In-memory sandbox per scenario; 6 assumption types; branches; before/after diff; external AI disabled | Scenario builder, branch tree, HYPOTHETICAL results, comparison | Same analysis code as the real case | Isolation, branching, validation, discard tests | Fully implemented |
| Investigation Replay | Events written by components as they act (intake, hashing, validation, extraction, every agent, dependencies, contradictions, hypotheses, verification, decisions, reviews, reports, what-if) | Playback, component filter, links to evidence/findings/results | Paginated API | Ordering and coverage test, browser | Fully implemented |
| Contradiction Detection | 8 linked-record rules; classification (direct / potential / contextual); priority; Source A/B, reason, link basis, verification action | Side-by-side cards, filters, human review | Feeds timeline, challenge, predictor | Precision/recall 100% on scored scenarios | Fully implemented |
| Evidence Gap Analysis | 14 gap categories with "why it matters" and checklists | Gap cards with checklist and review | Feeds predictor | Scenario regression | Fully implemented |
| Investigation Reports | 20 sections, `[EV-001 \| Page 3]` citations, ENGINE/HUMAN/SYSTEM labels, redaction | Linked HTML view, PDF view, PDF/DOCX/HTML download | Generated from persisted case data | Export and section tests | Fully implemented |
| Scenario Lab & Evaluation | 5 scenarios + control, ground truth (findings, events/timestamps, dependencies, irrelevant, ambiguous, verification ceiling), deterministic PASS/FAIL/HOLD, 17 metrics, history, comparison, custom datasets | Scenario pages, live trace, results, history, Evaluation dashboard with definitions and NOT EVALUATED labels | Same pipeline as real cases | `pytest -m scenario` | Fully implemented |
| Phishing Scenario (polished demo) | 12 files incl. duplicate receipt, forwarded email, OCR, voicemail | ✓ | ✓ | PASS (expected PASS) | Fully implemented |
| Account Compromise Scenario | 8 files | ✓ | ✓ | PASS (expected PASS) | Fully implemented |
| Evidence Preservation Scenario | 10 files incl. duplicate and re-compressed copies | ✓ | ✓ | PASS (expected PASS) | Fully implemented |
| Corporate Misconduct Scenario (polished demo) | 12 files incl. forwarded HR email, meeting MP4 | ✓ | ✓ | HOLD (expected HOLD) | Fully implemented |
| Marketplace Dispute Scenario | 10 files incl. delivery screenshot | ✓ | ✓ | PASS (expected PASS) | Fully implemented |

## Measured Scenario Lab results (latest demo-database run, deterministic mode)

| Scenario | Outcome (expected) | Decision | Critical | All | Contradiction P / R | Dependency P / R | Entity F1 | Timestamp acc. | Order acc. | OCR sim. | ASR sim. | Unsupported | Time |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 1 Phishing | PASS (PASS) | SUPPORTED | 7/7 | 14/14 | 100 / 100% | 100 / 100% | 84.2% | 100% | 100% | 94.2% | 100% | 0% | 7.3 s |
| 2 Account compromise | PASS (PASS) | SUPPORTED | 6/6 | 9/9 | 100 / 100% | 100 / 100% | 75.0% | 100% | 100% | 91.0% | NOT EVALUATED | 0% | 3.6 s |
| 3 Preservation | PASS (PASS) | SUPPORTED | 7/7 | 10/10 | 100 / 100% | 100 / 100% | 66.7% | 100% | 100% | 92.9% | NOT EVALUATED | 0% | 23.5 s |
| 4 Corporate misconduct | HOLD (HOLD) | INCONCLUSIVE | 5/5 | 8/8 | 100 / 100% | 100 / 100% | 54.5% | 100% | 100% | NOT EVALUATED | NOT EVALUATED | 0% | 5.8 s |
| 5 Marketplace dispute | PASS (PASS) | SUPPORTED | 6/6 | 9/9 | 100 / 100% | 100 / 100% | 100% | 100% | 100% | 92.8% | NOT EVALUATED | 0% | 8.1 s |
| Control: sparse records | HOLD (HOLD) | HOLD | 1/1 | 2/2 | NOT EVALUATED | NOT EVALUATED | NOT EVALUATED | NOT EVALUATED | NOT EVALUATED | 94.1% | NOT EVALUATED | 0% | 2.1 s |

Processing times are with OCR/ASR models already loaded. These are regression results on datasets the rules were developed against, not an independent benchmark. Entity F1 below 100% reflects genuine extra extractions (forwarded-mail addresses, OCR token merges, helpline numbers).

## Other requirement areas

| Area | Status | Notes |
|---|---|---|
| Authentication, roles, case-level access | Fully implemented | Logout revocation, password change, profile; cross-case 404 on every case-scoped endpoint |
| Migrations | Fully implemented | Alembic `0001`, `0002`; applied at startup |
| Prompt-injection protection | Fully implemented (LLM path untested) | Evidence-as-data, injection flagging, citations must verify, agents have no write/network/exec tools |
| External AI authorisation | Fully implemented | Per case, owner only, off by default; never in the sandbox |
| Frontend tests | Fully implemented | Vitest + Testing Library: navigation, case selection, timeline, challenge workflow + claim check, upload, reports, What-If labelling |
| PostgreSQL + pgvector / MinIO | Partially implemented | Config and backends written; not run (no Docker); semantic vector search not implemented |
| Neo4j | Not implemented | NetworkX in-process graph |
| spaCy / transformer NER | Blocked | Windows Application Control blocks spaCy's compiled dependency on this machine |
| LLM augmentation | Partially implemented | Wired into the counter-agent with structured output and refusal fallback; untested without an API key |
| Encryption at rest / in transit | Partially implemented | Optional Fernet/SSE; TLS via reverse proxy |

## Unfinished work / next steps
1. Run the Docker stack and add pgvector semantic search over segments.
2. Neo4j mirror for the relationship graph.
3. Exercise LLM augmentation with a key on an authorised case and compare with deterministic runs.
4. Re-measure entity F1 with spaCy where its DLLs are permitted.
5. Independently written scenarios to measure generalisation; Playwright end-to-end browser tests.
