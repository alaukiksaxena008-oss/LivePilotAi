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


TERMINAL_STATUSES = {
    "credited", "refunded", "completed", "approved", "dispatched",
    "delivered", "rejected", "cancelled", "canceled", "failed", "closed", "paid",
}


def is_terminal_status(result: dict | None) -> bool:
    """Returns True if any field in result indicates a terminal/final life admin state."""
    if not isinstance(result, dict):
        return False
    for v in result.values():
        if isinstance(v, str):
            words = set(v.casefold().replace(".", " ").replace(",", " ").replace("-", " ").split())
            if words & TERMINAL_STATUSES:
                return True
    return False


def describe(monitor: dict, changes: list[dict]) -> str:
    lines = [f"{c['field']}: {c['old']} → {c['new']}" for c in changes]
    return f"Change detected on {monitor['url']}\n" + "\n".join(lines)
