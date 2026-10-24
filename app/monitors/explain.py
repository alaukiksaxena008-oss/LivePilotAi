"""AI-generated summaries of monitor updates."""
from __future__ import annotations

import logging
from typing import Any

from app.monitors.compare import describe

logger = logging.getLogger(__name__)

EXPLAIN_SYSTEM_PROMPT = """You are LifePilotAI, an autonomous agent that handles life admin for the user.
A background monitor detected an update on a website.
Explain the change to the user in 1-2 friendly, clear, natural sentences.
Highlight what actually changed, whether any action is needed, and be concise for a phone notification."""


async def explain_changes(monitor: dict, changes: list[dict], llm: Any, model: str) -> str:
    """Uses the LLM to summarize detected field changes into a clear, natural alert."""
    change_summary = ", ".join(f"{c['field']} changed from '{c['old']}' to '{c['new']}'" for c in changes)
    user_prompt = (
        f"Goal: {monitor.get('goal')}\n"
        f"Website: {monitor.get('url')}\n"
        f"Detected Changes: {change_summary}\n\n"
        f"Write a concise 1-2 sentence update for the user."
    )
    try:
        resp = await llm.create(
            model=model,
            max_tokens=150,
            system=EXPLAIN_SYSTEM_PROMPT,
            tools=[],
            messages=[{"role": "user", "content": user_prompt}],
        )
        blocks = getattr(resp, "content", [])
        text = "".join(b.get("text", "") for b in blocks if isinstance(b, dict) and b.get("type") == "text").strip()
        if text:
            diff_lines = "\n".join(f"• {c['field']}: {c['old']} → {c['new']}" for c in changes)
            return f"🔔 {text}\n\n{diff_lines}"
    except Exception as e:
        logger.warning("AI explanation failed, falling back to raw diff: %r", e)

    return describe(monitor, changes)
