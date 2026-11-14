"""Compatibility shim for environments where the native ``xxhash`` extension cannot load
(e.g. Windows Application Control blocks the DLL). LangGraph only uses xxh3_128 to derive
deterministic task IDs, so a hashlib-based digest of the same width is a safe stand-in.
The real module is always preferred when it imports successfully."""
from __future__ import annotations

import hashlib
import sys
import types

XXHASH_SHIM_ACTIVE = False


def ensure_xxhash() -> None:
    global XXHASH_SHIM_ACTIVE
    try:
        import xxhash  # noqa: F401
        return
    except Exception:
        pass
    mod = types.ModuleType("xxhash")

    def xxh3_128_hexdigest(data, seed: int = 0) -> str:
        if isinstance(data, str):
            data = data.encode()
        return hashlib.blake2b(bytes(data), digest_size=16, salt=seed.to_bytes(16, "little") if seed else b"").hexdigest()

    def xxh3_128_intdigest(data, seed: int = 0) -> int:
        return int(xxh3_128_hexdigest(data, seed), 16)

    mod.xxh3_128_hexdigest = xxh3_128_hexdigest
    mod.xxh3_128_intdigest = xxh3_128_intdigest
    mod.__evidencex_shim__ = True
    sys.modules["xxhash"] = mod
    XXHASH_SHIM_ACTIVE = True


ensure_xxhash()

try:
    from langgraph.graph import END, START, StateGraph  # noqa: E402
    LANGGRAPH_AVAILABLE = True
    LANGGRAPH_ERROR = None
except Exception as e:  # pragma: no cover
    LANGGRAPH_AVAILABLE = False
    LANGGRAPH_ERROR = f"{type(e).__name__}: {e}"
    StateGraph = None
    START = END = None
