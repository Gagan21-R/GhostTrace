"""Tool registry: the "tool calling" layer shared by every agent.

A tool is a plain Python function plus a name, a one-line description and a JSON-Schema for its input,
exactly the shape LLM tool-use APIs expect. Agents never touch the database directly; they *call tools*.
That gives three things:

1. One audited path: every call is recorded (tool, input, short output, duration) in a trace that is shown
   to the investigator and stored with the result.
2. Swappable planners: a deterministic planner (offline, repeatable) and an LLM planner (native tool use,
   only when the case allows external AI) drive the *same* tools.
3. Safety: tools are read-only, case-scoped and validate their own input; a tool cannot be asked to touch
   another case or modify evidence.
"""
from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from typing import Any, Callable


@dataclass
class Tool:
    name: str
    description: str
    input_schema: dict
    fn: Callable[..., Any]
    category: str = "case"

    def schema(self) -> dict:
        return {"name": self.name, "description": self.description, "input_schema": self.input_schema}


class ToolError(Exception):
    pass


def _validate(schema: dict, args: dict) -> dict:
    props, req = schema.get("properties", {}), schema.get("required", [])
    if not isinstance(args, dict):
        raise ToolError("input must be an object")
    missing = [r for r in req if r not in args]
    if missing:
        raise ToolError(f"missing required input: {', '.join(missing)}")
    unknown = [k for k in args if k not in props]
    if unknown and schema.get("additionalProperties") is False:
        raise ToolError(f"unknown input: {', '.join(unknown)}")
    clean = {}
    for k, v in args.items():
        if k not in props:
            continue
        t = props[k].get("type")
        if t == "string" and not isinstance(v, str):
            raise ToolError(f"{k} must be a string")
        if t == "integer":
            try:
                v = int(v)
            except (TypeError, ValueError):
                raise ToolError(f"{k} must be an integer")
            lo, hi = props[k].get("minimum"), props[k].get("maximum")
            v = max(lo, v) if lo is not None else v
            v = min(hi, v) if hi is not None else v
        if "enum" in props[k] and v not in props[k]["enum"]:
            raise ToolError(f"{k} must be one of {props[k]['enum']}")
        if isinstance(v, str):
            v = v[:4000]
        clean[k] = v
    return clean


def _short(out: Any, limit: int = 600) -> Any:
    s = json.dumps(out, default=str)
    if len(s) <= limit:
        return out
    if isinstance(out, list):
        return {"items": out[:3], "truncated": f"{len(out)} items"}
    if isinstance(out, dict):
        return {k: (v if len(json.dumps(v, default=str)) < 200 else "…") for k, v in out.items()}
    return s[:limit] + "…"


@dataclass
class ToolRegistry:
    tools: dict[str, Tool] = field(default_factory=dict)

    def register(self, name: str, description: str, properties: dict | None = None, required: list[str] | None = None,
                 category: str = "case"):
        def deco(fn):
            self.tools[name] = Tool(name, description, {"type": "object", "properties": properties or {},
                                                        "required": required or [], "additionalProperties": False}, fn, category)
            return fn
        return deco

    def schemas(self, category: str | None = None) -> list[dict]:
        return [t.schema() for t in self.tools.values() if category is None or t.category == category]

    def catalogue(self) -> list[dict]:
        return [{**t.schema(), "category": t.category} for t in self.tools.values()]


class ToolSession:
    """Binds a registry to one context (e.g. one case) and records every call."""

    def __init__(self, registry: ToolRegistry, ctx: Any, planner: str = "deterministic"):
        self.registry, self.ctx, self.planner = registry, ctx, planner
        self.trace: list[dict] = []

    def call(self, name: str, args: dict | None = None, why: str = "") -> Any:
        args = args or {}
        t0 = time.perf_counter()
        entry = {"step": len(self.trace) + 1, "tool": name, "input": args, "why": why, "planner": self.planner}
        try:
            tool = self.registry.tools.get(name)
            if not tool:
                raise ToolError(f"unknown tool {name}")
            out = tool.fn(self.ctx, **_validate(tool.input_schema, args))
            entry.update(status="ok", output=_short(out))
            return out
        except ToolError as e:
            entry.update(status="error", output=str(e))
            return {"error": str(e)}
        except Exception as e:  # a tool bug must not crash the agent; it is recorded instead
            entry.update(status="error", output=f"{type(e).__name__}: {str(e)[:200]}")
            return {"error": "tool failed"}
        finally:
            entry["ms"] = round((time.perf_counter() - t0) * 1000, 1)
            self.trace.append(entry)


REGISTRY = ToolRegistry()
