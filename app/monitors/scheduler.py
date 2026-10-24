import asyncio
import time

from app.monitors.runner import run_monitor


async def scheduler_loop(db, client, notify, *, explain=None, tick: float = 10.0) -> None:
    """Every `tick` seconds, run whichever monitors are due. New monitors are picked up automatically."""
    while True:
        for m in db.due_monitors(time.time()):
            try:
                out = await run_monitor(m["id"], client=client, db=db, notify=notify, explain=explain)
                print(f"[monitor {m['id']}] {out['outcome']}")
            except Exception as e:  # keep the loop alive no matter what
                print(f"[monitor {m['id']}] crashed: {e!r}")
        await asyncio.sleep(tick)
