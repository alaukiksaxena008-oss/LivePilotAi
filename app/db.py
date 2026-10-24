"""SQLite storage: monitors, snapshots, alerts. One shared connection is fine for a single-process demo."""
from __future__ import annotations

import json
import sqlite3
import time
from typing import Any

SCHEMA = """
CREATE TABLE IF NOT EXISTS monitors (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  user_id TEXT NOT NULL,
  url TEXT NOT NULL,
  goal TEXT NOT NULL,
  output_schema TEXT,
  interval_seconds INTEGER NOT NULL,
  status TEXT NOT NULL DEFAULT 'active',
  created_at REAL NOT NULL,
  last_checked REAL,
  last_result TEXT,
  last_error TEXT
);
CREATE TABLE IF NOT EXISTS snapshots (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  monitor_id INTEGER NOT NULL,
  result TEXT NOT NULL,
  created_at REAL NOT NULL
);
CREATE TABLE IF NOT EXISTS alerts (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  monitor_id INTEGER,
  user_id TEXT NOT NULL,
  message TEXT NOT NULL,
  created_at REAL NOT NULL
);
CREATE TABLE IF NOT EXISTS goals (
  id TEXT PRIMARY KEY,
  user_id TEXT NOT NULL,
  goal_text TEXT NOT NULL,
  status TEXT NOT NULL,
  answer TEXT,
  question TEXT,
  pending_tool_use_id TEXT,
  messages TEXT NOT NULL,
  steps TEXT NOT NULL,
  budget_steps INTEGER NOT NULL,
  budget_agent_runs INTEGER NOT NULL,
  created_at REAL NOT NULL,
  updated_at REAL NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_snap ON snapshots(monitor_id, id);
CREATE INDEX IF NOT EXISTS idx_goals_user ON goals(user_id, status);
"""


def _monitor(row: sqlite3.Row | None) -> dict | None:
    if row is None:
        return None
    d = dict(row)
    for k in ("output_schema", "last_result"):
        d[k] = json.loads(d[k]) if d[k] else None
    return d


class DB:
    def __init__(self, path: str = ":memory:"):
        self._conn = sqlite3.connect(path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._conn.executescript(SCHEMA)

    def _run(self, sql: str, args: tuple = ()) -> sqlite3.Cursor:
        cur = self._conn.execute(sql, args)
        self._conn.commit()
        return cur

    # monitors
    def create_monitor(self, user_id: str, url: str, goal: str, output_schema: dict | None, interval_seconds: int) -> int:
        cur = self._run(
            "INSERT INTO monitors (user_id,url,goal,output_schema,interval_seconds,created_at) VALUES (?,?,?,?,?,?)",
            (user_id, url, goal, json.dumps(output_schema) if output_schema else None, interval_seconds, time.time()),
        )
        return cur.lastrowid

    def get_monitor(self, monitor_id: int) -> dict | None:
        return _monitor(self._run("SELECT * FROM monitors WHERE id=?", (monitor_id,)).fetchone())

    def list_monitors(self, user_id: str | None = None) -> list[dict]:
        if user_id:
            rows = self._run("SELECT * FROM monitors WHERE user_id=? ORDER BY id", (user_id,)).fetchall()
        else:
            rows = self._run("SELECT * FROM monitors ORDER BY id").fetchall()
        return [_monitor(r) for r in rows]

    def due_monitors(self, now: float) -> list[dict]:
        rows = self._run(
            "SELECT * FROM monitors WHERE status='active' AND (last_checked IS NULL OR last_checked + interval_seconds <= ?) ORDER BY id",
            (now,),
        ).fetchall()
        return [_monitor(r) for r in rows]

    def mark_checked(self, monitor_id: int, now: float, *, result: dict | None = None, error: str | None = None) -> None:
        if result is not None:
            self._run("UPDATE monitors SET last_checked=?, last_result=?, last_error=NULL WHERE id=?", (now, json.dumps(result), monitor_id))
        else:
            self._run("UPDATE monitors SET last_checked=?, last_error=? WHERE id=?", (now, error, monitor_id))

    def set_status(self, monitor_id: int, status: str) -> None:
        self._run("UPDATE monitors SET status=? WHERE id=?", (status, monitor_id))

    def delete_monitor(self, monitor_id: int) -> None:
        self._run("DELETE FROM snapshots WHERE monitor_id=?", (monitor_id,))
        self._run("DELETE FROM alerts WHERE monitor_id=?", (monitor_id,))
        self._run("DELETE FROM monitors WHERE id=?", (monitor_id,))

    # snapshots
    def last_snapshot(self, monitor_id: int) -> dict | None:
        row = self._run("SELECT result FROM snapshots WHERE monitor_id=? ORDER BY id DESC LIMIT 1", (monitor_id,)).fetchone()
        return json.loads(row["result"]) if row else None

    def save_snapshot(self, monitor_id: int, result: dict) -> None:
        self._run("INSERT INTO snapshots (monitor_id,result,created_at) VALUES (?,?,?)", (monitor_id, json.dumps(result), time.time()))

    # alerts
    def add_alert(self, monitor_id: int | None, user_id: str, message: str) -> None:
        self._run("INSERT INTO alerts (monitor_id,user_id,message,created_at) VALUES (?,?,?,?)", (monitor_id, user_id, message, time.time()))

    def list_alerts(self, user_id: str | None = None, limit: int = 50) -> list[dict]:
        if user_id:
            rows = self._run("SELECT * FROM alerts WHERE user_id=? ORDER BY id DESC LIMIT ?", (user_id, limit)).fetchall()
        else:
            rows = self._run("SELECT * FROM alerts ORDER BY id DESC LIMIT ?", (limit,)).fetchall()
        return [dict(r) for r in rows]

    # goals
    def save_goal(
        self,
        goal_id: str,
        user_id: str,
        goal_text: str,
        result: Any,
        budget: Any,
    ) -> None:
        now = time.time()
        self._run(
            """INSERT INTO goals (id, user_id, goal_text, status, answer, question, pending_tool_use_id,
                                  messages, steps, budget_steps, budget_agent_runs, created_at, updated_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
               ON CONFLICT(id) DO UPDATE SET
                 status=excluded.status,
                 answer=excluded.answer,
                 question=excluded.question,
                 pending_tool_use_id=excluded.pending_tool_use_id,
                 messages=excluded.messages,
                 steps=excluded.steps,
                 budget_steps=excluded.budget_steps,
                 budget_agent_runs=excluded.budget_agent_runs,
                 updated_at=excluded.updated_at
            """,
            (
                goal_id,
                user_id,
                goal_text,
                result.status,
                result.answer,
                result.question,
                result.pending_tool_use_id,
                json.dumps(result.messages),
                json.dumps(result.steps),
                budget.steps,
                budget.agent_runs,
                now,
                now,
            ),
        )

    def get_goal(self, goal_id: str) -> dict | None:
        row = self._run("SELECT * FROM goals WHERE id=?", (goal_id,)).fetchone()
        if not row:
            return None
        d = dict(row)
        d["messages"] = json.loads(d["messages"]) if d["messages"] else []
        d["steps"] = json.loads(d["steps"]) if d["steps"] else []
        return d

    def active_waiting_goal(self, user_id: str) -> dict | None:
        row = self._run(
            "SELECT * FROM goals WHERE user_id=? AND status='waiting_for_user' ORDER BY updated_at DESC LIMIT 1",
            (user_id,),
        ).fetchone()
        if not row:
            return None
        d = dict(row)
        d["messages"] = json.loads(d["messages"]) if d["messages"] else []
        d["steps"] = json.loads(d["steps"]) if d["steps"] else []
        return d
