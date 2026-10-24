import asyncio

import httpx

from app.agent.tools import Budget, build_tools
from app.db import DB
from app.monitors.runner import run_monitor
from app.tinyfish.client import TinyFishClient


def client_returning(results):
    """Each call to /run returns the next scripted run payload."""
    it = iter(results)

    def handler(req):
        return httpx.Response(200, json=next(it))

    return TinyFishClient("k", transport=httpx.MockTransport(handler))


def completed(result):
    return {"run_id": "r", "status": "COMPLETED", "result": result}


def test_baseline_then_unchanged_then_changed_alerts_once():
    db, sent = DB(), []

    async def notify(user, text):
        sent.append((user, text))

    mid = db.create_monitor("u1", "https://portal.test", "read status", {"type": "object"}, 60)
    tf = client_returning([completed({"status": "Initiated"}), completed({"status": "Initiated"}), completed({"status": "Credited"})])

    async def go():
        return [await run_monitor(mid, client=tf, db=db, notify=notify) for _ in range(3)]

    outs = asyncio.run(go())
    assert [o["outcome"] for o in outs] == ["baseline", "unchanged", "changed"]
    assert len(sent) == 1 and "Initiated → Credited" in sent[0][1]
    assert db.list_alerts("u1")[0]["message"] == sent[0][1]
    assert db.get_monitor(mid)["last_result"] == {"status": "Credited"}


def test_failed_run_is_recorded_not_alerted():
    db, sent = DB(), []

    async def notify(user, text):
        sent.append(text)

    mid = db.create_monitor("u1", "https://x.test", "g", None, 60)
    tf = client_returning([{"run_id": "r", "status": "FAILED", "result": None, "error": {"message": "blocked"}}])
    out = asyncio.run(run_monitor(mid, client=tf, db=db, notify=notify))
    assert out["outcome"] == "error" and sent == []
    assert db.get_monitor(mid)["last_error"]


def test_custom_explain_is_used_for_alert_text():
    db, sent = DB(), []

    async def notify(user, text):
        sent.append(text)

    async def explain(m, changes):
        return "Friendly: your status moved!"

    mid = db.create_monitor("u1", "https://x.test", "g", None, 60)
    tf = client_returning([completed({"s": "a"}), completed({"s": "b"})])

    async def go():
        await run_monitor(mid, client=tf, db=db, notify=notify, explain=explain)
        await run_monitor(mid, client=tf, db=db, notify=notify, explain=explain)

    asyncio.run(go())
    assert sent == ["Friendly: your status moved!"]


def test_due_monitors_respects_interval():
    db = DB()
    mid = db.create_monitor("u1", "https://x.test", "g", None, 60)
    assert [m["id"] for m in db.due_monitors(1000)] == [mid]  # never checked
    db.mark_checked(mid, 1000, result={"a": 1})
    assert db.due_monitors(1030) == []
    assert [m["id"] for m in db.due_monitors(1060)] == [mid]
    db.set_status(mid, "paused")
    assert db.due_monitors(5000) == []


def test_create_monitor_tool_saves_row_for_user():
    db = DB()
    tf = TinyFishClient("k", transport=httpx.MockTransport(lambda r: httpx.Response(200, json={})))
    tools = build_tools(tf, Budget(5, 2), db=db, user_id="u7")
    assert "create_monitor" in tools
    out = asyncio.run(tools["create_monitor"].handler({
        "url": "https://x.test", "goal": "read status", "output_schema": {"type": "object"}, "interval_minutes": 2,
    }))
    m = db.get_monitor(out["monitor_id"])
    assert m["user_id"] == "u7" and m["interval_seconds"] == 120


def test_create_monitor_tool_absent_without_db():
    tf = TinyFishClient("k", transport=httpx.MockTransport(lambda r: httpx.Response(200, json={})))
    assert "create_monitor" not in build_tools(tf, Budget(5, 2))
