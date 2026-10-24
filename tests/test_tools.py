import asyncio

import httpx

from app.agent.tools import READ_ONLY_PREFIX, Budget, BudgetExceeded, build_tools
from app.tinyfish.client import TinyFishClient
import pytest
import json


def test_web_agent_is_read_only_and_budgeted():
    sent = []

    def handler(req):
        sent.append(json.loads(req.content))
        return httpx.Response(200, json={"status": "COMPLETED", "result": {"v": 1}})

    async def go():
        tf = TinyFishClient("k", transport=httpx.MockTransport(handler))
        budget = Budget(10, 1)
        tools = build_tools(tf, budget)
        first = await tools["web_agent"].handler({"url": "https://x.com", "goal": "read status", "needs_login": True})
        with pytest.raises(BudgetExceeded):
            await tools["web_agent"].handler({"url": "https://x.com", "goal": "again"})
        await tf.aclose()
        return first

    out = asyncio.run(go())
    assert out["result"] == {"v": 1}
    assert sent[0]["goal"].startswith(READ_ONLY_PREFIX) and sent[0]["use_vault"] is True
