"""Central configuration. Every secret comes from the environment (see .env.example)."""
from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

BASE_DIR = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=str(BASE_DIR / ".env"), env_file_encoding="utf-8", extra="ignore")

    app_name: str = "GhostTrace"
    environment: str = "development"

    # Database: SQLite for zero-infra local runs, PostgreSQL (+pgvector) in docker-compose.
    database_url: str = f"sqlite:///{(BASE_DIR / 'data' / 'evidencex.db').as_posix()}"

    # Auth
    jwt_secret: str = "change-me-in-.env"
    jwt_algorithm: str = "HS256"
    jwt_expire_minutes: int = 720

    # Storage: "local" or "s3" (MinIO / any S3-compatible endpoint)
    storage_backend: str = "local"
    storage_root: str = str(BASE_DIR / "data" / "storage")
    s3_endpoint_url: str | None = None
    s3_access_key: str | None = None
    s3_secret_key: str | None = None
    s3_bucket: str = "evidencex"
    # Optional at-rest encryption key for local storage (Fernet, urlsafe base64 32 bytes)
    storage_encryption_key: str | None = None

    # Graph backend: "networkx" (in-process) or "neo4j" (mirror)
    graph_backend: str = "networkx"
    neo4j_uri: str | None = None
    neo4j_user: str | None = None
    neo4j_password: str | None = None

    # LLM provider: "anthropic" or "none" (deterministic engine only, clearly labelled)
    llm_provider: str = "anthropic"
    anthropic_api_key: str | None = None
    llm_model: str = ""  # set LLM_MODEL in .env; AI augmentation stays off while empty
    # Explain assistant: answer chat questions with the LLM (sent guide text + the question only, never evidence)
    help_assistant_llm: bool = False
    # Public contact form: max messages per client IP per hour
    contact_rate_per_hour: int = 5

    # Extraction engines: "auto" uses an engine if it is installed, else records it as unavailable
    ocr_engine: str = "auto"          # auto | paddleocr | rapidocr | none
    asr_engine: str = "auto"          # auto | faster-whisper | none
    whisper_model: str = "base"
    nlp_engine: str = "auto"          # auto | spacy | none

    max_upload_mb: int = 100
    cors_origins: str = "http://localhost:5173,http://127.0.0.1:5173"

    # Retention (days); 0 = keep indefinitely
    retention_days: int = 0

    seed_admin_email: str = "admin@evidencex.local"
    seed_admin_password: str = "ChangeMe!2026"


@lru_cache
def get_settings() -> Settings:
    return Settings()
