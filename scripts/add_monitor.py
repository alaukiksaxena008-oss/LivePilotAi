"""Create a monitor WITHOUT any LLM and run the first check (sets the baseline).
Usage: python -m scripts.add_monitor <url> "<what to read>" <field1,field2> [interval_minutes]
Then keep the API running (uvicorn app.main:app) so the scheduler re-checks it."""
import asyncio
import sys

from app.config import get_settings
from app.db import DB
from app.monitors.runner import run_monitor
from app.notify import send_alert
from app.tinyfish.client import TinyFishClient


async def main(url: str, goal: str, fields: list[str], minutes: float) -> None:
    s = get_settings()
    db = DB(s.db_path)
    schema = {"type": "object", "properties": {f: {"type": "string"} for f in fields}, "required": fields}
    mid = db.create_monitor("demo", url, goal, schema, int(minutes * 60))
    print(f"Created monitor {mid}. Running first check...")
    async with TinyFishClient(s.tinyfish_api_key) as tf:
        print(await run_monitor(mid, client=tf, db=db, notify=send_alert))


if __name__ == "__main__":
    if len(sys.argv) < 4:
        sys.exit(__doc__)
    asyncio.run(main(sys.argv[1], sys.argv[2], sys.argv[3].split(","), float(sys.argv[4]) if len(sys.argv) > 4 else 1))
