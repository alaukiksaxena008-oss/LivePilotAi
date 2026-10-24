"""Plan, act, observe. The LLM picks ONE action; our code runs it and feeds back the result."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable

from app.agent.tools import Budget, BudgetExceeded, PauseForUser, Tool, TinyFishError, format_result

SYSTEM_PROMPT = """You are LifePilot AI, an autonomous personal web agent completing life admin tasks for the user.

Rules:
- When asked to fill out or submit an application, form, or registration (e.g. Google Form, scholarship portal, student registration, official portal):
  1. Call get_user_profile first to fetch the user's saved personal information (full name, email, phone, DOB, address, college, degree, ID numbers, CGPA).
  2. Call web_agent with fill_form=true on the form URL, passing the user's profile details in the goal so the browser agent accurately inputs each field into the form and submits it.
- If the user wants to monitor a page for status updates, changes, or alerts, read the page once with web_agent to identify the data, then call create_monitor with a schema of fields to watch.
- Use the cheapest tool for the job: web_fetch for public static reading, web_search to find portals or websites, and web_agent for browser interaction and forms.
- If you need an OTP, secret, or specific missing info, call ask_user.
- Never invent data.
- When the goal is satisfied, reply with a concise, helpful summary of the actions taken and stop."""


@dataclass
class GoalResult:
    status: str  # done | waiting_for_user | step_limit
    answer: str | None = None
    question: str | None = None
    pending_tool_use_id: str | None = None
    messages: list[dict] = field(default_factory=list)
    steps: list[dict] = field(default_factory=list)


def _to_dict(block: Any) -> dict:
    if isinstance(block, dict):
        return block
    if hasattr(block, "model_dump"):
        return block.model_dump(exclude_none=True)
    return dict(vars(block))


async def run_goal(goal: str, **kw) -> GoalResult:
    return await _loop([{"role": "user", "content": goal}], [], **kw)


async def resume_goal(prev: GoalResult, user_reply: str, **kw) -> GoalResult:
    """Continue a paused goal after the user answered (OTP, detail, approval)."""
    messages = prev.messages + [{
        "role": "user",
        "content": [{"type": "tool_result", "tool_use_id": prev.pending_tool_use_id, "content": user_reply}],
    }]
    return await _loop(messages, list(prev.steps), **kw)


async def _loop(
    messages: list[dict],
    steps: list[dict],
    *,
    llm: Any,
    model: str,
    tools: dict[str, Tool],
    budget: Budget,
    result_char_limit: int = 6000,
    system: str = SYSTEM_PROMPT,
    on_step: Callable[[dict], None] | None = None,
) -> GoalResult:
    tool_defs = [t.to_api() for t in tools.values()]
    while True:
        try:
            budget.use_step()
        except BudgetExceeded:
            return GoalResult("step_limit", answer="I hit my step limit before finishing.", messages=messages, steps=steps)

        resp = await llm.create(
            model=model,
            max_tokens=1500,
            system=system,
            tools=tool_defs,
            tool_choice={"type": "auto", "disable_parallel_tool_use": True},
            messages=messages,
        )
        blocks = [_to_dict(b) for b in resp.content]
        messages.append({"role": "assistant", "content": blocks})

        tool_uses = [b for b in blocks if b.get("type") == "tool_use"]
        if not tool_uses:
            text = "".join(b.get("text", "") for b in blocks if b.get("type") == "text").strip()
            return GoalResult("done", answer=text, messages=messages, steps=steps)

        call = tool_uses[0]
        name, args, call_id = call["name"], call.get("input", {}), call["id"]
        step = {"tool": name, "input": args}
        tool = tools.get(name)

        if tool is None:
            output, is_error = f"Unknown tool: {name}", True
        else:
            try:
                output, is_error = format_result(await tool.handler(args), result_char_limit), False
            except PauseForUser as p:
                step["paused"] = p.question
                steps.append(step)
                if on_step:
                    on_step(step)
                return GoalResult("waiting_for_user", question=p.question, pending_tool_use_id=call_id, messages=messages, steps=steps)
            except (BudgetExceeded, TinyFishError, KeyError) as e:
                output, is_error = f"Tool error: {e}", True

        step["is_error"] = is_error
        step["output_preview"] = output[:200]
        steps.append(step)
        if on_step:
            on_step(step)
        messages.append({
            "role": "user",
            "content": [{"type": "tool_result", "tool_use_id": call_id, "content": output, "is_error": is_error}],
        })
