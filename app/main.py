import asyncio
import uuid
from pathlib import Path
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse
from pydantic import BaseModel

HTML_FILE = Path(__file__).parent / "templates" / "index.html"

from app.agent.llm import make_llm
from app.agent.loop import GoalResult, resume_goal, run_goal
from app.agent.tools import Budget, build_tools
from app.config import get_settings
from app.db import DB
from app.monitors.explain import explain_changes
from app.monitors.runner import run_monitor
from app.monitors.scheduler import scheduler_loop
from app.notify import send_alert
from app.telegram_bot import telegram_polling_loop
from app.tinyfish.client import TinyFishClient


@asynccontextmanager
async def lifespan(app: FastAPI):
    s = get_settings()
    app.state.settings = s
    app.state.db = DB(s.db_path)
    app.state.tf = TinyFishClient(s.tinyfish_api_key)
    app.state.goals = {}  # goal_id -> {"result", "budget", "tools", "kw"}

    llm, model = make_llm(s)

    async def _explain(m, changes):
        return await explain_changes(m, changes, llm, model)

    scheduler_task = asyncio.create_task(
        scheduler_loop(app.state.db, app.state.tf, send_alert, explain=_explain, tick=s.scheduler_tick)
    )

    bot_task = None
    if s.telegram_bot_token:
        bot_task = asyncio.create_task(telegram_polling_loop(app.state.db, app.state.tf, s))

    yield

    scheduler_task.cancel()
    if bot_task:
        bot_task.cancel()
    await app.state.tf.aclose()


app = FastAPI(title="Web Agent", lifespan=lifespan)


class GoalIn(BaseModel):
    text: str
    user_id: str = "demo"


class ReplyIn(BaseModel):
    text: str


def _payload(goal_id: str, r) -> dict:
    return {"goal_id": goal_id, "status": r.status, "answer": r.answer, "question": r.question, "steps": r.steps}


@app.get("/", response_class=HTMLResponse)
async def dashboard():
    return HTMLResponse(HTML_FILE.read_text(encoding="utf-8"))


@app.get("/health")
async def health():
    return {"ok": True}


@app.post("/goals")
async def create_goal(body: GoalIn):
    s, tf, db = app.state.settings, app.state.tf, app.state.db
    llm, model = make_llm(s)
    budget = Budget(s.max_steps, s.max_agent_runs)
    tools = build_tools(tf, budget, db=db, user_id=body.user_id)
    kw = dict(llm=llm, model=model, tools=tools, budget=budget, result_char_limit=s.tool_result_char_limit)
    result = await run_goal(body.text, **kw)
    goal_id = uuid.uuid4().hex[:8]
    db.save_goal(goal_id, body.user_id, body.text, result, budget)
    if result.status == "waiting_for_user":
        app.state.goals[goal_id] = {"result": result, "kw": kw, "user_id": body.user_id, "goal_text": body.text}
    return _payload(goal_id, result)


@app.post("/goals/{goal_id}/reply")
async def reply_goal(goal_id: str, body: ReplyIn):
    s, tf, db = app.state.settings, app.state.tf, app.state.db
    saved = app.state.goals.pop(goal_id, None)

    # If not in memory (e.g. server restarted), restore from database
    if not saved:
        rec = db.get_goal(goal_id)
        if not rec or rec["status"] != "waiting_for_user":
            raise HTTPException(404, "No paused goal with that id")
        llm, model = make_llm(s)
        budget = Budget(
            s.max_steps,
            s.max_agent_runs,
            steps=rec.get("budget_steps", 0),
            agent_runs=rec.get("budget_agent_runs", 0),
        )
        tools = build_tools(tf, budget, db=db, user_id=rec["user_id"])
        kw = dict(llm=llm, model=model, tools=tools, budget=budget, result_char_limit=s.tool_result_char_limit)
        prev_result = GoalResult(
            status=rec["status"],
            answer=rec.get("answer"),
            question=rec.get("question"),
            pending_tool_use_id=rec.get("pending_tool_use_id"),
            messages=rec.get("messages", []),
            steps=rec.get("steps", []),
        )
        saved = {"result": prev_result, "kw": kw, "user_id": rec["user_id"], "goal_text": rec["goal_text"]}

    result = await resume_goal(saved["result"], body.text, **saved["kw"])
    db.save_goal(goal_id, saved["user_id"], saved["goal_text"], result, saved["kw"]["budget"])
    if result.status == "waiting_for_user":
        saved["result"] = result
        app.state.goals[goal_id] = saved
    return _payload(goal_id, result)


@app.get("/goals/{goal_id}")
async def get_goal(goal_id: str):
    rec = app.state.db.get_goal(goal_id)
    if not rec:
        raise HTTPException(404, "No such goal")
    return rec


@app.get("/monitors")
async def list_monitors(user_id: str | None = None):
    return app.state.db.list_monitors(user_id)


@app.post("/monitors/{monitor_id}/pause")
async def pause_monitor(monitor_id: int):
    if not app.state.db.get_monitor(monitor_id):
        raise HTTPException(404, "No such monitor")
    app.state.db.set_status(monitor_id, "paused")
    return {"monitor_id": monitor_id, "status": "paused"}


@app.post("/monitors/{monitor_id}/resume")
async def resume_monitor(monitor_id: int):
    if not app.state.db.get_monitor(monitor_id):
        raise HTTPException(404, "No such monitor")
    app.state.db.set_status(monitor_id, "active")
    return {"monitor_id": monitor_id, "status": "active"}


@app.delete("/monitors/{monitor_id}")
async def delete_monitor(monitor_id: int):
    if not app.state.db.get_monitor(monitor_id):
        raise HTTPException(404, "No such monitor")
    app.state.db.delete_monitor(monitor_id)
    return {"deleted": monitor_id}


@app.post("/monitors/{monitor_id}/run")
async def run_monitor_now(monitor_id: int):
    """Trigger a check immediately: handy for the live demo."""
    if not app.state.db.get_monitor(monitor_id):
        raise HTTPException(404, "No such monitor")
    return await run_monitor(monitor_id, client=app.state.tf, db=app.state.db, notify=send_alert)


@app.get("/alerts")
async def list_alerts(user_id: str | None = None):
    return app.state.db.list_alerts(user_id)
