import asyncio
from unittest.mock import AsyncMock, patch

from app.agent.loop import GoalResult
from app.config import get_settings
from app.db import DB
from app.telegram_bot import handle_message
from app.tinyfish.client import TinyFishClient


def test_telegram_slash_commands():
    db = DB()
    settings = get_settings()
    tf = TinyFishClient("dummy-key")

    sent = []

    async def mock_send(token, chat_id, text):
        sent.append((chat_id, text))

    with patch("app.telegram_bot.send_telegram_message", side_effect=mock_send):
        asyncio.run(handle_message(db, tf, settings, 12345, "/start"))
        assert len(sent) == 1
        assert "Welcome to LifePilotAI" in sent[0][1]

        asyncio.run(handle_message(db, tf, settings, 12345, "/status"))
        assert len(sent) == 2
        assert "online and monitoring" in sent[1][1]

        asyncio.run(handle_message(db, tf, settings, 12345, "/monitors"))
        assert len(sent) == 3
        assert "no active monitors" in sent[2][1]


def test_telegram_resumes_paused_goal():
    db = DB()
    settings = get_settings()
    tf = TinyFishClient("dummy-key")

    from app.agent.tools import Budget
    prev_result = GoalResult(
        status="waiting_for_user",
        question="Enter OTP",
        pending_tool_use_id="otp_call_1",
        messages=[{"role": "user", "content": "Check passport"}],
        steps=[{"tool": "ask_user"}],
    )
    db.save_goal("g1", "12345", "Check passport", prev_result, Budget(10, 2))

    sent = []

    async def mock_send(token, chat_id, text):
        sent.append((chat_id, text))

    with patch("app.telegram_bot.send_telegram_message", side_effect=mock_send), \
         patch("app.telegram_bot.resume_goal", new_callable=AsyncMock) as mock_resume:
        mock_resume.return_value = GoalResult(status="done", answer="Passport Dispatched!")

        asyncio.run(handle_message(db, tf, settings, 12345, "482910"))

        assert any("Resuming agent" in s[1] for s in sent)
        assert any("Passport Dispatched!" in s[1] for s in sent)

        updated = db.get_goal("g1")
        assert updated["status"] == "done"
        assert updated["answer"] == "Passport Dispatched!"
