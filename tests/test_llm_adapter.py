import asyncio
import json
from types import SimpleNamespace

from app.agent.llm import OpenAICompatLLM, to_openai_messages, to_openai_tools


def test_messages_are_converted_for_openai_format():
    msgs = [
        {"role": "user", "content": "check status"},
        {"role": "assistant", "content": [
            {"type": "text", "text": "Looking."},
            {"type": "tool_use", "id": "c1", "name": "web_fetch", "input": {"urls": ["https://x.com"]}},
        ]},
        {"role": "user", "content": [{"type": "tool_result", "tool_use_id": "c1", "content": "{\"ok\": 1}"}]},
    ]
    out = to_openai_messages("sys", msgs)
    assert out[0] == {"role": "system", "content": "sys"}
    assert out[1] == {"role": "user", "content": "check status"}
    assert out[2]["tool_calls"][0]["function"]["name"] == "web_fetch"
    assert json.loads(out[2]["tool_calls"][0]["function"]["arguments"]) == {"urls": ["https://x.com"]}
    assert out[3] == {"role": "tool", "tool_call_id": "c1", "content": "{\"ok\": 1}"}


def test_tools_are_converted():
    out = to_openai_tools([{"name": "t", "description": "d", "input_schema": {"type": "object"}}])
    assert out == [{"type": "function", "function": {"name": "t", "description": "d", "parameters": {"type": "object"}}}]


def test_response_becomes_anthropic_style_blocks_and_keeps_first_call_only():
    calls = [
        SimpleNamespace(id="a", function=SimpleNamespace(name="web_search", arguments='{"query": "q"}')),
        SimpleNamespace(id="b", function=SimpleNamespace(name="web_fetch", arguments="{}")),
    ]
    message = SimpleNamespace(content=None, tool_calls=calls)

    class FakeCompletions:
        async def create(self, **kw):
            self.kw = kw
            return SimpleNamespace(choices=[SimpleNamespace(message=message)])

    fake = SimpleNamespace(chat=SimpleNamespace(completions=FakeCompletions()))
    llm = OpenAICompatLLM(fake)
    resp = asyncio.run(llm.create(model="m", max_tokens=10, system="s", tools=[], messages=[{"role": "user", "content": "hi"}], tool_choice={"type": "auto"}))
    assert resp.content == [{"type": "tool_use", "id": "a", "name": "web_search", "input": {"query": "q"}}]
    assert fake.chat.completions.kw["model"] == "m"
