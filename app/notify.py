"""Alert delivery. Always prints; also sends to Telegram if a bot token is set and user_id is a chat id."""
import os

import httpx


async def send_alert(user_id: str, text: str) -> None:
    print(f"[ALERT -> {user_id}] {text}")
    token = os.getenv("TELEGRAM_BOT_TOKEN")
    if token and str(user_id).lstrip("-").isdigit():
        try:
            async with httpx.AsyncClient(timeout=15) as c:
                await c.post(f"https://api.telegram.org/bot{token}/sendMessage", json={"chat_id": int(user_id), "text": text})
        except httpx.HTTPError as e:
            print(f"[notify] telegram failed: {e!r}")
