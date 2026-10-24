import asyncio
import uuid
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from app.agent.llm import make_llm
from app.agent.loop import resume_goal, run_goal
from app.agent.tools import Budget, build_tools
from app.config import get_settings
from app.db import DB
from app.monitors.runner import run_monitor
from app.monitors.scheduler import scheduler_loop
from app.notify import send_alert
from app.tinyfish.client import TinyFishClient


@asynccontextmanager
async def lifespan(app: FastAPI):
    s = get_settings()
    app.state.settings = s
    app.state.db = DB(s.db_path)
    app.state.tf = TinyFishClient(s.tinyfish_api_key)
    app.state.goals = {}  # goal_id -> {"result", "budget", "tools", "kw"}
    task = asyncio.create_task(scheduler_loop(app.state.db, app.state.tf, send_alert, tick=s.scheduler_tick))
    yield
    task.cancel()
    await app.state.tf.aclose()


app = FastAPI(title="Web Agent", lifespan=lifespan)


class GoalIn(BaseModel):
    text: str
    user_id: str = "demo"


class ReplyIn(BaseModel):
    text: str


def _payload(goal_id: str, r) -> dict:
    return {"goal_id": goal_id, "status": r.status, "answer": r.answer, "question": r.question, "steps": r.steps}


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
    if result.status == "waiting_for_user":
        app.state.goals[goal_id] = {"result": result, "kw": kw}
    return _payload(goal_id, result)


@app.post("/goals/{goal_id}/reply")
async def reply_goal(goal_id: str, body: ReplyIn):
    saved = app.state.goals.pop(goal_id, None)
    if not saved:
        raise HTTPException(404, "No paused goal with that id")
    result = await resume_goal(saved["result"], body.text, **saved["kw"])
    if result.status == "waiting_for_user":
        app.state.goals[goal_id] = {"result": result, "kw": saved["kw"]}
    return _payload(goal_id, result)


@app.get("/monitors")
async def list_monitors(user_id: str | None = None):
    return app.state.db.list_monitors(user_id)


@app.post("/monitors/{monitor_id}/run")
async def run_monitor_now(monitor_id: int):
    """Trigger a check immediately: handy for the live demo."""
    if not app.state.db.get_monitor(monitor_id):
        raise HTTPException(404, "No such monitor")
    return await run_monitor(monitor_id, client=app.state.tf, db=app.state.db, notify=send_alert)


@app.get("/alerts")
async def list_alerts(user_id: str | None = None):
    return app.state.db.list_alerts(user_id)
