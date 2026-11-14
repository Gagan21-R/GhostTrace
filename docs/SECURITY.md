# Security, privacy and limitations

## Controls
| Area | Control | Tested |
|---|---|---|
| Authentication | bcrypt (cost 12), JWT with `jti`; logout revokes the token; login throttling (8 failures / 5 min); password policy | yes |
| Authorisation | Roles (admin, investigator, reviewer, viewer) + per-case membership (owner, editor, viewer). Cross-case requests return 404, so case IDs cannot be probed | yes (every case-scoped endpoint) |
| Uploads | Extension and content signature must agree; executables and disguised binaries rejected; Office containers checked for unsafe paths and macros; size limit; filenames never reach the filesystem (server-generated keys) | yes |
| Evidence integrity | Write-once originals (read-only on disk); derivatives stored separately with their own hashes; hash checked before processing; hash-chained append-only audit log (ORM blocks updates/deletes) | yes |
| Injection | SQLAlchemy parameterised queries; SQL-injection probes in tests; HTML from evidence is never rendered (downloads are sandboxed with `nosniff` + CSP) | yes |
| Prompt injection | Evidence is passed to an LLM only inside `<evidence>` data tags with a system instruction to ignore embedded instructions; phrases aimed at AI systems are flagged on the evidence item; every LLM item must cite segment IDs and pass the deterministic Verification agent; agents have no tools that write records, change permissions, delete evidence, execute code or make network requests | flagging tested; LLM path untested (no key) |
| External AI | Off by default per case; only the case owner can enable it; the What-If sandbox never contacts an external provider; runs record whether evidence was sent | yes |
| Secrets | Environment variables only (`.env.example`); none in the frontend or logs | — |
| Sharing & privacy | Owner-controlled case sharing; redacted reports mask email local parts and phone/account digits while keeping citations | yes |
| Retention | Soft delete, legal hold, admin retention purge for archived cases | yes |
| Transport | Run behind a TLS-terminating reverse proxy; security headers set by the app | not applicable locally |
| At rest | Optional Fernet encryption for local storage; SSE for S3 | not enabled by default |

## What the platform does not claim
* A matching SHA-256 shows a file is unchanged **since intake**. It does not establish authenticity before intake, chain of custody, or legal admissibility.
* Integrity-inspection items are indicators for human review, not proof of tampering.
* A shared identifier, IP address, device string or writing style never establishes that two accounts or names belong to the same person. Inferred relationships are labelled as leads.
* Missing evidence is never treated as evidence of wrongdoing.
* Reviewer decisions describe how well the available records support a hypothesis. They are not findings of guilt; every decision requires human review.
* What-If results are hypothetical and are never written to the case.

## Known limitations
* Findings come from deterministic rules over extracted text; OCR/ASR errors propagate (OCR character similarity on the synthetic screenshots is 91-94%).
* The investigation pattern library covers the five case families in the brief; other cases fall back to "insufficient signals" (HOLD).
* spaCy NER is blocked on the development machine by Windows Application Control; entity extraction uses rules.
* Speaker diarisation is not available; transcripts are unattributed. Video analysis reads on-screen text and speech only (no scene description).
* Timezone-less timestamps use the case default (or are compared as wall-clock when the case timezone is "unknown") and are labelled as assumptions.
* Scenario Lab scores are regression results on datasets the rules were developed against, not an independent benchmark.
* The Docker/PostgreSQL/MinIO path, Neo4j and LLM augmentation were not exercised on the development machine.
