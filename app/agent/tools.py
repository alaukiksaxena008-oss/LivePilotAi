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

FORM_FILL_PREFIX = (
    "FORM-FILLING TASK. Navigate the form carefully. Fill in the user's provided details "
    "into the matching input fields (e.g. name, email, phone, address, college, degree, ID). "
    "Once all required fields are filled, submit the form (or proceed to the final confirmation screen). "
    "Do NOT make any financial payments. Task: "
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
    import time

    def _log(name: str, inp: Any, out: Any, duration_ms: float, status: str = "SUCCESS"):
        if db and hasattr(db, "log_tool_execution"):
            try:
                db.log_tool_execution(user_id, name, inp, out, duration_ms, status)
            except Exception:
                pass

    async def web_search(inp: dict) -> Any:
        t0 = time.time()
        try:
            res = await client.search(inp["query"])
            _log("web_search", inp, res, (time.time() - t0) * 1000, "SUCCESS")
            return res
        except Exception as e:
            _log("web_search", inp, str(e), (time.time() - t0) * 1000, "ERROR")
            raise

    async def web_fetch(inp: dict) -> Any:
        t0 = time.time()
        try:
            res = await client.fetch(inp["urls"])
            _log("web_fetch", inp, res, (time.time() - t0) * 1000, "SUCCESS")
            return res
        except Exception as e:
            _log("web_fetch", inp, str(e), (time.time() - t0) * 1000, "ERROR")
            raise

    async def web_agent(inp: dict) -> Any:
        budget.use_agent_run()
        t0 = time.time()
        prefix = FORM_FILL_PREFIX if inp.get("fill_form") else READ_ONLY_PREFIX
        try:
            run = await client.run(
                inp["url"],
                prefix + inp["goal"],
                output_schema=inp.get("output_schema"),
                use_vault=bool(inp.get("needs_login", False)),
                max_duration_seconds=300,
            )
            out = {"status": run.get("status"), "result": run.get("result"), "error": run.get("error")}
            _log("web_agent", inp, out, (time.time() - t0) * 1000, "SUCCESS" if run.get("status") == "COMPLETED" else "ERROR")
            return out
        except Exception as e:
            _log("web_agent", inp, str(e), (time.time() - t0) * 1000, "ERROR")
            raise

    async def ask_user(inp: dict) -> Any:
        _log("ask_user", inp, "PAUSED_FOR_USER", 0, "SUCCESS")
        raise PauseForUser(inp["question"])

    async def get_user_profile(inp: dict) -> Any:
        t0 = time.time()
        if not db or not hasattr(db, "get_profile"):
            return {"error": "Profile database not available"}
        prof = db.get_profile(user_id)
        _log("get_user_profile", inp, prof, (time.time() - t0) * 1000, "SUCCESS")
        return prof or {"error": f"No profile found for user {user_id}"}

    async def create_monitor(inp: dict) -> Any:
        t0 = time.time()
        minutes = max(0.5, float(inp.get("interval_minutes", 60)))
        mid = db.create_monitor(user_id, inp["url"], inp["goal"], inp["output_schema"], int(minutes * 60))
        out = {"monitor_id": mid, "checks_every_minutes": minutes, "note": "First check runs shortly and sets the baseline."}
        _log("create_monitor", inp, out, (time.time() - t0) * 1000, "SUCCESS")
        return out

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
            "Use a real browser agent for navigation, form-filling, logins, and reading complex pages. "
            "Set fill_form=true when filling out an application or registration form. "
            "Set needs_login=true for sites that need your saved credentials.",
            {
                "type": "object",
                "properties": {
                    "url": {"type": "string"},
                    "goal": {"type": "string", "description": "What to fill, find, or read, in plain English"},
                    "fill_form": {"type": "boolean", "description": "Set true if typing inputs/filling a form"},
                    "needs_login": {"type": "boolean"},
                    "output_schema": {"type": "object", "description": "JSON schema for the result you want back"},
                },
                "required": ["url", "goal"],
            },
            web_agent,
        ),
        Tool(
            "ask_user",
            "Ask the user for something only they can provide: an OTP, a missing detail, or final approval.",
            {"type": "object", "properties": {"question": {"type": "string"}}, "required": ["question"]},
            ask_user,
        ),
    ]
    if db is not None:
        tools.append(Tool(
            "get_user_profile",
            "Retrieve the user's saved personal profile (Name, DOB, Phone, Address, ID Number, College) to autofill forms.",
            {"type": "object", "properties": {}},
            get_user_profile,
        ))
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
