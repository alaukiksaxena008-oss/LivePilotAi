import asyncio
import copy
from types import SimpleNamespace

from app.agent.loop import resume_goal, run_goal
from app.agent.tools import Budget, Tool


class FakeLLM:
    """Plays back scripted responses, like Anthropic's messages API."""

    def __init__(self, script):
        self.script = list(script)
        self.calls = []

    async def create(self, **kw):
        self.calls.append(copy.deepcopy(kw))
        return SimpleNamespace(content=self.script.pop(0))


def tool_use(name, inp, id="t1"):
    return [{"type": "tool_use", "id": id, "name": name, "input": inp}]


def text(t):
    return [{"type": "text", "text": t}]


def make_tools(log):
    async def fetch(inp):
        log.append(inp)
        return {"title": "Example Domain"}

    async def ask(inp):
        from app.agent.tools import PauseForUser
        raise PauseForUser(inp["question"])

    schema = {"type": "object", "properties": {}}
    return {
        "web_fetch": Tool("web_fetch", "d", schema, fetch),
        "ask_user": Tool("ask_user", "d", schema, ask),
    }


def kwargs(llm, tools, budget):
    return dict(llm=llm, model="m", tools=tools, budget=budget)


def test_tool_then_final_answer():
    log = []
    llm = FakeLLM([tool_use("web_fetch", {"urls": ["https://example.com"]}), text("The title is Example Domain.")])
    res = asyncio.run(run_goal("title?", **kwargs(llm, make_tools(log), Budget(5, 2))))
    assert res.status == "done" and "Example Domain" in res.answer
    assert log == [{"urls": ["https://example.com"]}]
    assert res.steps[0]["tool"] == "web_fetch"
    # the tool result was fed back to the LLM
    assert llm.calls[1]["messages"][-1]["content"][0]["type"] == "tool_result"


def test_pause_and_resume_for_otp():
    llm = FakeLLM([tool_use("ask_user", {"question": "OTP?"}, id="a1"), text("Done after OTP.")])
    tools = make_tools([])
    first = asyncio.run(run_goal("check", **kwargs(llm, tools, Budget(5, 2))))
    assert first.status == "waiting_for_user" and first.question == "OTP?"
    final = asyncio.run(resume_goal(first, "482913", **kwargs(llm, tools, Budget(5, 2))))
    assert final.status == "done"
    reply = llm.calls[1]["messages"][-1]["content"][0]
    assert reply["tool_use_id"] == "a1" and reply["content"] == "482913"


def test_step_limit_stops_runaway_loop():
    llm = FakeLLM([tool_use("web_fetch", {"urls": []}, id=f"t{i}") for i in range(10)])
    res = asyncio.run(run_goal("loop", **kwargs(llm, make_tools([]), Budget(3, 2))))
    assert res.status == "step_limit" and len(llm.calls) == 3


def test_unknown_tool_is_reported_not_crashed():
    llm = FakeLLM([tool_use("hack", {}), text("ok")])
    res = asyncio.run(run_goal("x", **kwargs(llm, make_tools([]), Budget(5, 2))))
    assert res.status == "done" and res.steps[0]["is_error"] is True
