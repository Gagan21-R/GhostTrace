"""GhostTrace API entry point.

Run (dev):   uvicorn app.main:app --reload --port 8000
Docs:        http://localhost:8000/docs
"""
from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from starlette.exceptions import HTTPException as StarletteHTTPException

from .bootstrap import init_db
from .config import get_settings
from .routers import analysis, auth, authenticity, hypotheses, voice, cases, evidence, help, intel, reports, scenarios, spec, system

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    yield


app = FastAPI(title="GhostTrace API", version="1.0.0", lifespan=lifespan,
              description="AI-powered digital evidence intelligence platform. Every clue connected. Every claim traceable. "
                          "Every conclusion challenged.")
app.add_middleware(CORSMiddleware, allow_origins=[o.strip() for o in settings.cors_origins.split(",") if o.strip()],
                   allow_credentials=True, allow_methods=["*"], allow_headers=["*"])


@app.middleware("http")
async def security_headers(request: Request, call_next):
    resp = await call_next(request)
    resp.headers.setdefault("X-Content-Type-Options", "nosniff")
    resp.headers.setdefault("X-Frame-Options", "DENY")
    resp.headers.setdefault("Referrer-Policy", "no-referrer")
    if request.url.path.startswith("/api/"):
        resp.headers.setdefault("Cache-Control", "no-store")
    return resp


def _err(status: int, code: str, message, details=None):
    return JSONResponse(status_code=status, content={"error": {"code": code, "message": message, "details": details}})


@app.exception_handler(StarletteHTTPException)
async def http_error(_: Request, exc: StarletteHTTPException):
    msg = exc.detail.get("reason") if isinstance(exc.detail, dict) else exc.detail
    return _err(exc.status_code, f"http_{exc.status_code}", msg, exc.detail if isinstance(exc.detail, dict) else None)


@app.exception_handler(RequestValidationError)
async def validation_error(_: Request, exc: RequestValidationError):
    return _err(422, "validation_error", "Request validation failed",
                [{"field": ".".join(str(x) for x in e["loc"][1:]), "message": e["msg"]} for e in exc.errors()])


@app.exception_handler(Exception)
async def unhandled(_: Request, exc: Exception):
    logging.getLogger("evidencex").exception("unhandled error")
    return _err(500, "internal_error", "An internal error occurred. It has been logged.")


for r in (auth.router, help.router, authenticity.router, hypotheses.router, voice.router, cases.router, evidence.router, analysis.router, intel.router, spec.router, scenarios.router, reports.router, system.router):
    app.include_router(r)


@app.get("/api/health", tags=["system"])
def health():
    return {"status": "ok"}


# Serve the built frontend (frontend/dist) when present, so one process can host the whole app.
DIST = Path(__file__).resolve().parent.parent.parent / "frontend" / "dist"
if DIST.exists():
    app.mount("/assets", StaticFiles(directory=DIST / "assets"), name="assets")

    @app.get("/{path:path}", include_in_schema=False)
    def spa(path: str):
        if path.startswith("api/"):
            return _err(404, "http_404", "Not Found")
        f = (DIST / path).resolve()
        if path and DIST in f.parents and f.is_file():
            return FileResponse(f)
        return FileResponse(DIST / "index.html")
