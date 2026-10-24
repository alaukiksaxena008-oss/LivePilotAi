"""Change detection in plain code. No LLM involved."""
from __future__ import annotations

from typing import Any


def _norm(v: Any) -> Any:
    return " ".join(v.split()).casefold() if isinstance(v, str) else v


def diff(old: dict | None, new: dict) -> list[dict]:
    """Fields whose value changed. Returns [] for the first run (no baseline yet)."""
    if old is None:
        return []
    changes = []
    for key in sorted(set(old) | set(new)):
        if _norm(old.get(key)) != _norm(new.get(key)):
            changes.append({"field": key, "old": old.get(key), "new": new.get(key)})
    return changes


def describe(monitor: dict, changes: list[dict]) -> str:
    lines = [f"{c['field']}: {c['old']} → {c['new']}" for c in changes]
    return f"Change detected on {monitor['url']}\n" + "\n".join(lines)
