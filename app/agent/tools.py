"""The tool layer: the only place the LLM's decisions turn into real calls."""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any, Awaitable, Callable

from app.tinyfish.client import TinyFishClient, TinyFishError

READ_ONLY_PREFIX = (
    "READ-ONLY TASK. Do not submit forms that change anything, do not pay, send, "
    "book, cancel, or delete. Only navigate and read. If an action would change "
    "something, stop and report what you found. Task: "
)


class BudgetExceeded(Exception):
    pass


class PauseForUser(Exception):
    """Raised by the ask_user tool. The loop catches it and pauses the goal."""

    def __init__(self, question: str):
        super().__init__(question)
        self.question = question


@dataclass
class Budget:
    max_steps: int
    max_agent_runs: int
    steps: int = 0
    agent_runs: int = 0

    def use_step(self) -> None:
        if self.steps >= self.max_steps:
            raise BudgetExceeded(f"Step limit of {self.max_steps} reached")
        self.steps += 1

    def use_agent_run(self) -> None:
        if self.agent_runs >= self.max_agent_runs:
            raise BudgetExceeded(f"Web agent run limit of {self.max_agent_runs} reached")
        self.agent_runs += 1


@dataclass
class Tool:
    name: str
    description: str
    input_schema: dict
    handler: Callable[[dict], Awaitable[Any]]

    def to_api(self) -> dict:
        return {"name": self.name, "description": self.description, "input_schema": self.input_schema}


def build_tools(client: TinyFishClient, budget: Budget, db: Any = None, user_id: str = "demo") -> dict[str, Tool]:
    async def web_search(inp: dict) -> Any:
        return await client.search(inp["query"])

    async def web_fetch(inp: dict) -> Any:
        return await client.fetch(inp["urls"])

    async def web_agent(inp: dict) -> Any:
        budget.use_agent_run()
        run = await client.run(
            inp["url"],
            READ_ONLY_PREFIX + inp["goal"],
            output_schema=inp.get("output_schema"),
            use_vault=bool(inp.get("needs_login", False)),
            max_duration_seconds=300,
        )
        return {"status": run.get("status"), "result": run.get("result"), "error": run.get("error")}

    async def ask_user(inp: dict) -> Any:
        raise PauseForUser(inp["question"])

    async def create_monitor(inp: dict) -> Any:
        minutes = max(0.5, float(inp.get("interval_minutes", 60)))
        mid = db.create_monitor(user_id, inp["url"], inp["goal"], inp["output_schema"], int(minutes * 60))
        return {"monitor_id": mid, "checks_every_minutes": minutes, "note": "First check runs shortly and sets the baseline."}

    tools = [
        Tool(
            "web_search",
            "Search the web to find the right page or portal when you only know a name. Cheap and fast.",
            {"type": "object", "properties": {"query": {"type": "string"}}, "required": ["query"]},
            web_search,
        ),
        Tool(
            "web_fetch",
            "Read public pages as clean text, no clicking or login. Cheapest way to read a known URL.",
            {"type": "object", "properties": {"urls": {"type": "array", "items": {"type": "string"}}}, "required": ["urls"]},
            web_fetch,
        ),
        Tool(
            "web_agent",
            "Use a real browser agent for logins, forms, and multi-step navigation. Slow and costly: "
            "use only when search/fetch cannot do the job. Always read-only. "
            "Set needs_login=true for sites that need your saved credentials.",
            {
                "type": "object",
                "properties": {
                    "url": {"type": "string"},
                    "goal": {"type": "string", "description": "What to find or read, in plain English"},
                    "needs_login": {"type": "boolean"},
                    "output_schema": {"type": "object", "description": "JSON schema for the result you want back"},
                },
                "required": ["url", "goal"],
            },
            web_agent,
        ),
        Tool(
            "ask_user",
            "Ask the user for something only they can provide: an OTP, a missing detail, or approval.",
            {"type": "object", "properties": {"question": {"type": "string"}}, "required": ["question"]},
            ask_user,
        ),
    ]
    if db is not None:
        tools.append(Tool(
            "create_monitor",
            "Save a recurring check so the user is alerted when something changes. Use it when the user says "
            "'tell me when' or 'watch'. First confirm with one web_agent run what to extract, then pass a small "
            "output_schema containing only the fields to watch.",
            {
                "type": "object",
                "properties": {
                    "url": {"type": "string"},
                    "goal": {"type": "string", "description": "What the browser agent should read on each check"},
                    "output_schema": {"type": "object", "description": "JSON schema of the fields to watch"},
                    "interval_minutes": {"type": "number", "description": "How often to check, in minutes (minimum 0.5)"},
                },
                "required": ["url", "goal", "output_schema"],
            },
            create_monitor,
        ))
    return {t.name: t for t in tools}


def format_result(value: Any, limit: int) -> str:
    text = json.dumps(value, default=str, ensure_ascii=False)
    if len(text) > limit:
        text = text[:limit] + f"... [truncated, {len(text)} chars total]"
    return text


__all__ = ["Budget", "BudgetExceeded", "PauseForUser", "Tool", "TinyFishError", "build_tools", "format_result"]
