"""Two-way Telegram Bot for LifePilotAI.
Uses long-polling: receives goals, prompts for OTPs, and resumes paused goals.
No public webhook or ngrok needed.
"""
from __future__ import annotations

import asyncio
import logging
import uuid
from typing import Any

import httpx

from app.agent.llm import make_llm
from app.agent.loop import GoalResult, resume_goal, run_goal
from app.agent.tools import Budget, build_tools
from app.config import Settings
from app.db import DB
from app.tinyfish.client import TinyFishClient

logger = logging.getLogger(__name__)


async def send_telegram_message(bot_token: str, chat_id: int | str, text: str) -> None:
    url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
    async with httpx.AsyncClient(timeout=15.0) as client:
        try:
            await client.post(url, json={"chat_id": chat_id, "text": text})
        except Exception as e:
            logger.error("Failed to send Telegram message to %s: %r", chat_id, e)


async def handle_message(db: DB, tf: TinyFishClient, settings: Settings, chat_id: int, text: str) -> None:
    token = settings.telegram_bot_token
    user_id = str(chat_id)
    text = text.strip()

    if not text:
        return

    # Slash commands
    if text in ("/start", "/help"):
        welcome = (
            "👋 Welcome to LifePilotAI!\n"
            "Your life admin, on autopilot.\n\n"
            "Send me any task in plain English, for example:\n"
            "• 'Check my refund on https://...'\n"
            "• 'Watch my passport status on https://... and alert me when it changes'\n\n"
            "Commands:\n"
            "/monitors - View all active background monitors\n"
            "/alerts - View recent alert notifications\n"
            "/status - Check bot status"
        )
        await send_telegram_message(token, chat_id, welcome)
        return

    if text == "/status":
        await send_telegram_message(token, chat_id, "🟢 LifePilotAI is online and monitoring in the background.")
        return

    if text == "/monitors":
        monitors = db.list_monitors(user_id)
        if not monitors:
            await send_telegram_message(token, chat_id, "ℹ️ You have no active monitors. Give me a URL to watch!")
            return
        lines = [f"• ID {m['id']} [{m['status'].upper()}]: {m['url']}\n  Goal: {m['goal']}" for m in monitors]
        await send_telegram_message(token, chat_id, "📋 Your Background Monitors:\n\n" + "\n\n".join(lines))
        return

    if text == "/alerts":
        alerts = db.list_alerts(user_id, limit=5)
        if not alerts:
            await send_telegram_message(token, chat_id, "ℹ️ No alerts triggered yet.")
            return
        lines = [f"🔔 {a['message']}" for a in alerts]
        await send_telegram_message(token, chat_id, "Recent Alerts:\n\n" + "\n\n".join(lines))
        return

    # Check if there is an active paused goal waiting for user input (e.g. OTP)
    waiting_goal = db.active_waiting_goal(user_id)
    if waiting_goal:
        await send_telegram_message(token, chat_id, "🔄 Received your reply! Resuming agent...")
        llm, model = make_llm(settings)
        budget = Budget(
            settings.max_steps,
            settings.max_agent_runs,
            steps=waiting_goal.get("budget_steps", 0),
            agent_runs=waiting_goal.get("budget_agent_runs", 0),
        )
        tools = build_tools(tf, budget, db=db, user_id=user_id)
        kw = dict(llm=llm, model=model, tools=tools, budget=budget, result_char_limit=settings.tool_result_char_limit)

        prev_result = GoalResult(
            status=waiting_goal["status"],
            answer=waiting_goal.get("answer"),
            question=waiting_goal.get("question"),
            pending_tool_use_id=waiting_goal.get("pending_tool_use_id"),
            messages=waiting_goal.get("messages", []),
            steps=waiting_goal.get("steps", []),
        )

        try:
            result = await resume_goal(prev_result, text, **kw)
            db.save_goal(waiting_goal["id"], user_id, waiting_goal["goal_text"], result, budget)

            if result.status == "waiting_for_user":
                await send_telegram_message(token, chat_id, f"⚠️ Additional input needed:\n\n{result.question}")
            elif result.status == "done":
                await send_telegram_message(token, chat_id, f"✅ Done!\n\n{result.answer}")
            else:
                await send_telegram_message(token, chat_id, f"ℹ️ Goal ended with status: {result.status}\n\n{result.answer}")
        except Exception as e:
            logger.exception("Error resuming goal: %r", e)
            await send_telegram_message(token, chat_id, f"❌ An error occurred: {e}")
        return

    # New goal
    await send_telegram_message(token, chat_id, "🤖 On it! Planning steps and inspecting the site...")
    goal_id = uuid.uuid4().hex[:8]
    llm, model = make_llm(settings)
    budget = Budget(settings.max_steps, settings.max_agent_runs)
    tools = build_tools(tf, budget, db=db, user_id=user_id)
    kw = dict(llm=llm, model=model, tools=tools, budget=budget, result_char_limit=settings.tool_result_char_limit)

    try:
        result = await run_goal(text, **kw)
        db.save_goal(goal_id, user_id, text, result, budget)

        if result.status == "waiting_for_user":
            await send_telegram_message(
                token,
                chat_id,
                f"⚠️ Action Required:\n\n{result.question}\n\n👉 Reply directly to this message with your OTP or response."
            )
        elif result.status == "done":
            await send_telegram_message(token, chat_id, f"✅ Done!\n\n{result.answer}")
        else:
            await send_telegram_message(token, chat_id, f"ℹ️ Goal ended with status: {result.status}\n\n{result.answer}")
    except Exception as e:
        logger.exception("Error running goal: %r", e)
        await send_telegram_message(token, chat_id, f"❌ An error occurred while executing goal: {e}")


async def telegram_polling_loop(db: DB, tf: TinyFishClient, settings: Settings) -> None:
    """Continuous async long-polling for incoming Telegram messages."""
    token = settings.telegram_bot_token
    if not token:
        logger.info("TELEGRAM_BOT_TOKEN not configured; telegram bot polling disabled.")
        return

    logger.info("Starting Telegram long-polling loop...")
    offset = 0
    url = f"https://api.telegram.org/bot{token}/getUpdates"

    async with httpx.AsyncClient(timeout=45.0) as client:
        while True:
            try:
                resp = await client.get(url, params={"offset": offset, "timeout": 20})
                if resp.status_code == 200:
                    data = resp.json()
                    for update in data.get("result", []):
                        offset = max(offset, update["update_id"] + 1)
                        msg = update.get("message") or update.get("edited_message")
                        if msg and "text" in msg and "chat" in msg:
                            chat_id = msg["chat"]["id"]
                            text = msg["text"]
                            # Handle each message concurrently
                            asyncio.create_task(handle_message(db, tf, settings, chat_id, text))
                elif resp.status_code == 409:
                    # Conflict: another instance might be polling
                    await asyncio.sleep(5)
                else:
                    await asyncio.sleep(2)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.warning("Telegram polling error: %r", e)
                await asyncio.sleep(3)
