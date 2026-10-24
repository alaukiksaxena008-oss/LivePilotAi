from __future__ import annotations

import time
from typing import Any, Awaitable, Callable

from app.agent.tools import READ_ONLY_PREFIX
from app.db import DB
from app.monitors.compare import describe, diff, is_terminal_status
from app.tinyfish.client import TinyFishClient, TinyFishError

Notify = Callable[[str, str], Awaitable[None]]
Explain = Callable[[dict, list[dict]], Awaitable[str]]


async def run_monitor(
    monitor_id: int,
    *,
    client: TinyFishClient,
    db: DB,
    notify: Notify,
    explain: Explain | None = None,
    now: float | None = None,
) -> dict[str, Any]:
    """One check: read the page, compare to the last snapshot, alert only on change."""
    m = db.get_monitor(monitor_id)
    now = now if now is not None else time.time()
    try:
        run = await client.run(m["url"], READ_ONLY_PREFIX + m["goal"], output_schema=m["output_schema"], max_duration_seconds=300)
    except TinyFishError as e:
        db.mark_checked(monitor_id, now, error=str(e))
        return {"outcome": "error", "error": str(e)}

    result = run.get("result")
    if run.get("status") != "COMPLETED" or not isinstance(result, dict):
        err = str(run.get("error") or f"Run ended with status {run.get('status')}")
        db.mark_checked(monitor_id, now, error=err)
        return {"outcome": "error", "error": err}

    previous = db.last_snapshot(monitor_id)
    changes = diff(previous, result)

    if previous is None:  # first run sets the baseline
        db.save_snapshot(monitor_id, result)
        db.mark_checked(monitor_id, now, result=result)
        return {"outcome": "baseline", "result": result}

    if not changes:
        db.mark_checked(monitor_id, now, result=result)
        return {"outcome": "unchanged", "result": result}

    db.save_snapshot(monitor_id, result)
    message = await explain(m, changes) if explain else describe(m, changes)

    # Auto-complete: if the new status indicates the task has completed (e.g. Credited, Dispatched)
    auto_completed = is_terminal_status(result)
    if auto_completed:
        db.set_status(monitor_id, "completed")
        message += "\n\n🎉 Goal reached! This monitor has been automatically completed and stopped."

    db.add_alert(monitor_id, m["user_id"], message)
    await notify(m["user_id"], message)
    db.mark_checked(monitor_id, now, result=result)
    return {"outcome": "changed", "changes": changes, "message": message, "completed": auto_completed}
