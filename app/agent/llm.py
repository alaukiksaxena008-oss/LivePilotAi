"""LLM providers. The agent loop speaks Anthropic-style messages; this adapter lets any
OpenAI-compatible API (Hugging Face router, Groq, etc.) plug in without changing the loop."""
from __future__ import annotations

import json
from types import SimpleNamespace
from typing import Any

HF_BASE_URL = "https://router.huggingface.co/v1"


def to_openai_messages(system: str, messages: list[dict]) -> list[dict]:
    out: list[dict] = [{"role": "system", "content": system}]
    for m in messages:
        content = m["content"]
        if m["role"] == "user":
            if isinstance(content, str):
                out.append({"role": "user", "content": content})
                continue
            for b in content:
                if b.get("type") == "tool_result":
                    out.append({"role": "tool", "tool_call_id": b["tool_use_id"], "content": str(b.get("content", ""))})
                elif b.get("type") == "text":
                    out.append({"role": "user", "content": b["text"]})
        else:
            blocks = [{"type": "text", "text": content}] if isinstance(content, str) else content
            text = "".join(b.get("text", "") for b in blocks if b.get("type") == "text")
            calls = [b for b in blocks if b.get("type") == "tool_use"][:1]  # loop runs one tool at a time
            msg: dict[str, Any] = {"role": "assistant", "content": text or None}
            if calls:
                msg["tool_calls"] = [
                    {"id": c["id"], "type": "function",
                     "function": {"name": c["name"], "arguments": json.dumps(c.get("input", {}))}}
                    for c in calls
                ]
            out.append(msg)
    return out


def to_openai_tools(tools: list[dict]) -> list[dict]:
    return [
        {"type": "function", "function": {"name": t["name"], "description": t["description"], "parameters": t["input_schema"]}}
        for t in tools
    ]


class OpenAICompatLLM:
    """Exposes .create(...) like Anthropic's messages API, returning Anthropic-style blocks."""

    def __init__(self, client: Any):
        self._client = client

    async def create(self, *, model: str, max_tokens: int, system: str, tools: list[dict], messages: list[dict], **_ignored):
        resp = await self._client.chat.completions.create(
            model=model,
            max_tokens=max_tokens,
            messages=to_openai_messages(system, messages),
            tools=to_openai_tools(tools),
        )
        msg = resp.choices[0].message
        blocks: list[dict] = []
        if getattr(msg, "content", None):
            blocks.append({"type": "text", "text": msg.content})
        for call in (getattr(msg, "tool_calls", None) or [])[:1]:
            try:
                args = json.loads(call.function.arguments or "{}")
            except ValueError:
                args = {}
            blocks.append({"type": "tool_use", "id": call.id, "name": call.function.name, "input": args})
        return SimpleNamespace(content=blocks)


def make_llm(settings) -> tuple[Any, str]:
    """Returns (llm, model_name) for the configured provider."""
    if settings.llm_provider == "anthropic":
        from anthropic import AsyncAnthropic
        return AsyncAnthropic(api_key=settings.anthropic_api_key).messages, settings.agent_model
    from openai import AsyncOpenAI
    client = AsyncOpenAI(base_url=HF_BASE_URL, api_key=settings.hf_token)
    return OpenAICompatLLM(client), settings.llm_model
