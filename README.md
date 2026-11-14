# EVIDENCE-X

**AI-powered digital evidence intelligence and forensic investigation platform.**
*Every clue connected. Every claim traceable. Every conclusion challenged.*

EVIDENCE-X turns disconnected digital evidence into traceable investigative intelligence. It preserves and verifies originals, extracts content from documents, spreadsheets, email, chats, images, audio and video, reconstructs timelines, maps entities and relationships, detects contradictions and gaps, and then actively tries to **disprove** its own hypotheses before a human reviews them.

Four flagship capabilities:
1. **Evidence Challenge Engine** – investigation, counter-investigation, deterministic verification and a skeptical reviewer return SUPPORTED / CONTRADICTED / INCONCLUSIVE / HOLD for every candidate hypothesis.
2. **Evidence DNA** – cross-file fingerprinting that separates independent corroboration from duplicated, derived and same-source evidence.
3. **Missing Evidence Predictor** – ranked, explainable recommendations for what to collect next, from authorised sources only.
4. **Investigation Replay** – the real, persisted sequence of every upload, extraction, agent action, finding and decision.

Plus a **What-If Lab** (isolated HYPOTHETICAL simulations), a **Scenario Lab** with five synthetic investigations and ground-truth evaluation, and 20-section evidence-linked reports (PDF / DOCX / HTML).

It assists investigators. It never declares anyone guilty, never treats an inference as a fact, and never treats file integrity as authenticity.

---

## Run from a clean environment

Requirements: **Python 3.12**, **Node 20+**. (Docker is optional, see below.)

### 1. Backend
```bash
cd backend
python -m venv .venv
.venv\Scripts\activate                 # macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt -r requirements-ml.txt
```

### 2. Configure environment variables
```bash
copy ..\.env.example .env              # macOS/Linux: cp ../.env.example .env
```
Set at least `JWT_SECRET` (`python -c "import secrets; print(secrets.token_urlsafe(48))"`) and change `SEED_ADMIN_PASSWORD`. `ANTHROPIC_API_KEY` is optional – without it the platform runs fully deterministic and says so; with it, external AI is still **off per case** until the case owner authorises it.

### 3. Database and migrations
SQLite is used by default (`backend/data/evidencex.db`); no database server is needed. Migrations run automatically at startup, or manually:
```bash
python -m alembic upgrade head
```
For PostgreSQL set `DATABASE_URL=postgresql+psycopg://user:pass@host:5432/evidencex` (see Docker below).

### 4. Load synthetic demo data (optional, recommended)
```bash
python scripts/load_demo.py              # two demo cases (phishing, whistleblower) through the real pipeline
python scripts/load_demo.py --scenarios  # + every Scenario Lab run (~3 min, OCR/ASR on CPU)
```
The first OCR/ASR use downloads model weights (Whisper `base` ≈140 MB).

### 5. Start the backend
```bash
uvicorn app.main:app --reload --port 8000      # API docs: http://localhost:8000/docs
```

### 6. Start the frontend (second terminal)
```bash
cd frontend
npm install
npm run dev                                     # http://localhost:5173 (proxies /api to :8000)
```
Sign in with `SEED_ADMIN_EMAIL` / `SEED_ADMIN_PASSWORD` (defaults `admin@evidencex.local` / `ChangeMe!2026`) or register an investigator account.

### 7. Tests
```bash
cd backend
pytest                          # unit, API, spec and flagship tests (28, ~3 min)
pytest -m scenario              # Scenario Lab regression incl. OCR/ASR (6, ~4 min)
cd ../frontend
npm test                        # component/integration tests (Vitest, 8)
npx tsc -b                      # type check
```

### Production build (single process)
```bash
cd frontend && npm run build
cd ../backend && uvicorn app.main:app --host 0.0.0.0 --port 8000
```
FastAPI serves the built UI at `/` and the API at `/api`. Put it behind a TLS-terminating reverse proxy.

### Docker (PostgreSQL + pgvector, MinIO)
```bash
copy .env.example backend\.env
docker compose up --build                # API + UI on :8000
docker compose --profile graph up        # also starts Neo4j (reserved; NetworkX is the graph engine)
```
> The Docker stack was written for the target infrastructure but **could not be run on the development machine** (no Docker). The SQLite + local-storage path is the tested one.

---

## Documentation
- [docs/DEMO.md](docs/DEMO.md) – step-by-step demo (phishing and whistleblower walkthroughs)
- [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) – layers, agents, Evidence DNA, What-If isolation, replay, data model
- [docs/SECURITY.md](docs/SECURITY.md) – security controls, privacy, what is and is not claimed, limitations
- [docs/API.md](docs/API.md) – endpoint reference (interactive at `/docs`)
- [docs/SCENARIOS.md](docs/SCENARIOS.md) – datasets, ground-truth schema, PASS/FAIL/HOLD rules
- [PROJECT_STATUS.md](PROJECT_STATUS.md) – feature completion table and measured results
- [IMPLEMENTATION_LOG.md](IMPLEMENTATION_LOG.md) – decisions and fixes per session

## Repository layout
```
backend/
  app/            FastAPI app: models, security, audit, replay, storage, routers/, services/ (intake, extraction,
                  processing, reports), analysis/ (facts, entities, timeline, contradictions, gaps, DNA, integrity),
                  agents/ (LangGraph orchestration, challenge agents, predictor, what-if, LLM provider), scenarios/
  migrations/     Alembic migrations
  scenario_data/  synthetic datasets (generated by app/scenarios/builder.py)
  scripts/        load_demo.py, run_scenarios.py
  tests/          pytest suites
frontend/         React + TypeScript + Tailwind (dark console), Recharts, Cytoscape.js, Framer Motion; src/test (Vitest)
docs/             documentation
```

All people, companies, domains, phone numbers and accounts in the datasets are fictional.
