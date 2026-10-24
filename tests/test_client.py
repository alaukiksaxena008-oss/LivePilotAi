import asyncio
import json

import httpx
import pytest

from app.tinyfish.client import TinyFishClient, TinyFishError


def make_client(handler):
    return TinyFishClient("test-key", transport=httpx.MockTransport(handler))


def test_run_sends_key_and_body():
    seen = {}

    def handler(req: httpx.Request) -> httpx.Response:
        seen["key"] = req.headers["X-API-Key"]
        seen["url"] = str(req.url)
        seen["body"] = json.loads(req.content)
        return httpx.Response(200, json={"run_id": "r1", "status": "COMPLETED", "result": {"title": "Example"}})

    async def go():
        async with make_client(handler) as tf:
            return await tf.run("https://example.com", "get title", use_vault=True, output_schema={"type": "object"})

    out = asyncio.run(go())
    assert out["result"] == {"title": "Example"}
    assert seen["key"] == "test-key"
    assert seen["url"].endswith("/v1/automation/run")
    assert seen["body"]["use_vault"] is True and seen["body"]["goal"] == "get title"


def test_optional_fields_omitted_by_default():
    body = TinyFishClient.build_body("https://x.com", "g")
    assert body == {"url": "https://x.com", "goal": "g"}


def test_error_is_mapped():
    def handler(req):
        return httpx.Response(401, json={"error": {"code": "INVALID_API_KEY", "message": "bad key"}})

    async def go():
        async with make_client(handler) as tf:
            await tf.run("https://x.com", "g")

    with pytest.raises(TinyFishError) as e:
        asyncio.run(go())
    assert e.value.status == 401 and e.value.code == "INVALID_API_KEY"


def test_wait_for_run_polls_until_terminal():
    states = iter(["PENDING", "RUNNING", "COMPLETED"])

    def handler(req):
        return httpx.Response(200, json={"run_id": "r1", "status": next(states), "result": {"ok": 1}})

    async def go():
        async with make_client(handler) as tf:
            return await tf.wait_for_run("r1", poll_interval=0)

    assert asyncio.run(go())["status"] == "COMPLETED"


def test_stream_parses_sse():
    sse = (
        'data: {"type":"STARTED","run_id":"r1"}\n\n'
        'data: {"type":"PROGRESS","run_id":"r1","purpose":"Opening page"}\n\n'
        'data: {"type":"COMPLETE","run_id":"r1","status":"COMPLETED","result":{"a":1}}\n\n'
    )

    def handler(req):
        return httpx.Response(200, content=sse.encode(), headers={"content-type": "text/event-stream"})

    async def go():
        async with make_client(handler) as tf:
            return [ev["type"] async for ev in tf.stream("https://x.com", "g")]

    assert asyncio.run(go()) == ["STARTED", "PROGRESS", "COMPLETE"]
