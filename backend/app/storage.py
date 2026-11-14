"""Write-once evidence storage with a local backend and an S3/MinIO backend.

Storage keys are generated server-side (``<case_id>/<kind>/<uuid><ext>``); user-supplied
filenames never touch the filesystem path, which removes path-traversal risk.
"""
from __future__ import annotations

import os
import uuid
from pathlib import Path

from .config import get_settings

settings = get_settings()

_SAFE_EXT = {".jpg", ".jpeg", ".png", ".webp", ".pdf", ".docx", ".txt", ".csv", ".xlsx", ".eml", ".json",
             ".mp3", ".wav", ".mp4", ".zip", ".md", ".log", ".html", ".htm", ".mbox"}


def make_key(case_id: str, kind: str, filename_hint: str = "") -> str:
    ext = Path(filename_hint).suffix.lower()
    ext = ext if ext in _SAFE_EXT else ".bin"
    if not case_id.isalnum() or not kind.isalnum():
        raise ValueError("invalid key component")
    return f"{case_id}/{kind}/{uuid.uuid4().hex}{ext}"


class _Cipher:
    """Optional at-rest encryption (Fernet) when STORAGE_ENCRYPTION_KEY is set."""

    def __init__(self, key: str | None):
        self.f = None
        if key:
            from cryptography.fernet import Fernet  # type: ignore
            self.f = Fernet(key.encode())

    def enc(self, b: bytes) -> bytes:
        return self.f.encrypt(b) if self.f else b

    def dec(self, b: bytes) -> bytes:
        return self.f.decrypt(b) if self.f else b


class LocalStorage:
    def __init__(self, root: str):
        self.root = Path(root).resolve()
        self.root.mkdir(parents=True, exist_ok=True)
        self.cipher = _Cipher(settings.storage_encryption_key)

    def _path(self, key: str) -> Path:
        p = (self.root / key).resolve()
        if self.root not in p.parents:
            raise ValueError("storage key escapes root")
        return p

    def put(self, key: str, data: bytes) -> None:
        p = self._path(key)
        if p.exists():
            raise FileExistsError("write-once storage: key already exists")
        p.parent.mkdir(parents=True, exist_ok=True)
        tmp = p.with_suffix(p.suffix + ".tmp")
        tmp.write_bytes(self.cipher.enc(data))
        os.replace(tmp, p)
        try:
            os.chmod(p, 0o444)  # read-only original
        except OSError:
            pass

    def get(self, key: str) -> bytes:
        p = self._path(key)
        if not p.exists():
            raise FileNotFoundError(key)
        return self.cipher.dec(p.read_bytes())

    def exists(self, key: str) -> bool:
        return self._path(key).exists()

    def delete(self, key: str) -> None:
        p = self._path(key)
        if p.exists():
            os.chmod(p, 0o666)
            p.unlink()

    # Test-only helper to simulate tampering in integrity demos.
    def _tamper(self, key: str, data: bytes) -> None:
        p = self._path(key)
        os.chmod(p, 0o666)
        p.write_bytes(self.cipher.enc(data))


class S3Storage:
    def __init__(self):
        import boto3  # type: ignore
        self.s3 = boto3.client("s3", endpoint_url=settings.s3_endpoint_url,
                               aws_access_key_id=settings.s3_access_key,
                               aws_secret_access_key=settings.s3_secret_key)
        self.bucket = settings.s3_bucket
        try:
            self.s3.head_bucket(Bucket=self.bucket)
        except Exception:
            self.s3.create_bucket(Bucket=self.bucket)

    def put(self, key: str, data: bytes) -> None:
        if self.exists(key):
            raise FileExistsError("write-once storage: key already exists")
        self.s3.put_object(Bucket=self.bucket, Key=key, Body=data, ServerSideEncryption="AES256")

    def get(self, key: str) -> bytes:
        return self.s3.get_object(Bucket=self.bucket, Key=key)["Body"].read()

    def exists(self, key: str) -> bool:
        try:
            self.s3.head_object(Bucket=self.bucket, Key=key)
            return True
        except Exception:
            return False

    def delete(self, key: str) -> None:
        self.s3.delete_object(Bucket=self.bucket, Key=key)


_storage = None


def get_storage():
    global _storage
    if _storage is None:
        _storage = S3Storage() if settings.storage_backend == "s3" else LocalStorage(settings.storage_root)
    return _storage
