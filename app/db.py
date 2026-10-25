"""Relational SQLite storage: users, profiles, tasks, credentials vault,
chat memory, tool audit logs, monitors, snapshots, and alerts.
Enforces strict Primary Keys, Foreign Keys, and indexing.
"""
from __future__ import annotations

import json
import sqlite3
import time
from typing import Any

SCHEMA = """
PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS users (
  id TEXT PRIMARY KEY,
  email TEXT UNIQUE NOT NULL,
  password TEXT NOT NULL,
  full_name TEXT NOT NULL,
  role TEXT NOT NULL DEFAULT 'User',
  avatar_initials TEXT NOT NULL,
  created_at REAL NOT NULL
);

CREATE TABLE IF NOT EXISTS profiles (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  user_id TEXT UNIQUE NOT NULL,
  full_name TEXT NOT NULL,
  email TEXT NOT NULL,
  phone TEXT NOT NULL,
  dob TEXT NOT NULL,
  address TEXT NOT NULL,
  city TEXT NOT NULL,
  pincode TEXT NOT NULL,
  id_type TEXT NOT NULL,
  id_number TEXT NOT NULL,
  college TEXT,
  degree TEXT,
  cgpa REAL,
  updated_at REAL NOT NULL,
  FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS tasks (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  user_id TEXT NOT NULL,
  title TEXT NOT NULL,
  task_type TEXT NOT NULL DEFAULT 'GENERAL',
  target_url TEXT,
  priority TEXT NOT NULL DEFAULT 'MEDIUM',
  due_date TEXT,
  status TEXT NOT NULL DEFAULT 'PENDING',
  created_at REAL NOT NULL,
  updated_at REAL NOT NULL,
  FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS credentials_vault (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  user_id TEXT NOT NULL,
  service_name TEXT NOT NULL,
  portal_url TEXT NOT NULL,
  username TEXT NOT NULL,
  password TEXT NOT NULL,
  notes TEXT,
  created_at REAL NOT NULL,
  FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS chat_messages (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  user_id TEXT NOT NULL,
  role TEXT NOT NULL,
  content TEXT NOT NULL,
  steps TEXT,
  created_at REAL NOT NULL,
  FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS tool_executions (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  user_id TEXT,
  tool_name TEXT NOT NULL,
  input_payload TEXT NOT NULL,
  output_payload TEXT NOT NULL,
  duration_ms REAL,
  status TEXT NOT NULL,
  created_at REAL NOT NULL
);

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
  created_at REAL NOT NULL,
  FOREIGN KEY(monitor_id) REFERENCES monitors(id) ON DELETE CASCADE
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
CREATE INDEX IF NOT EXISTS idx_tasks_user ON tasks(user_id, priority, status);
CREATE INDEX IF NOT EXISTS idx_chat_user ON chat_messages(user_id, created_at);
CREATE INDEX IF NOT EXISTS idx_tool_user ON tool_executions(user_id, created_at);
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
        self._conn.execute("PRAGMA foreign_keys = ON;")
        self._conn.executescript(SCHEMA)
        self._seed_default_accounts()

    def _run(self, sql: str, args: tuple = ()) -> sqlite3.Cursor:
        cur = self._conn.execute(sql, args)
        self._conn.commit()
        return cur

    def _seed_default_accounts(self) -> None:
        """Seeds 3 accounts: Riya Sharma (Slide 2), Alex Morgan, and David Chen."""
        users_count = self._run("SELECT COUNT(*) as c FROM users").fetchone()["c"]
        if users_count > 0:
            return

        now = time.time()
        # 1. Riya Sharma (The canonical persona from Slide 2 of the presentation)
        self._run(
            "INSERT INTO users (id, email, password, full_name, role, avatar_initials, created_at) VALUES (?,?,?,?,?,?,?)",
            ("riya", "riya@lifepilot.ai", "password123", "Riya Sharma", "Software Engineer in Delhi", "RS", now),
        )
        self._run(
            """INSERT INTO profiles (user_id, full_name, email, phone, dob, address, city, pincode, id_type, id_number, college, degree, cgpa, updated_at)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            ("riya", "Riya Sharma", "riya@lifepilot.ai", "+91 98765 43210", "1999-04-12", "Flat 402, Green Park Residency, Sector 14", "Delhi", "110016", "Passport", "IND-849204", "Delhi Technological University", "B.Tech Computer Science", 8.9, now),
        )
        # Tasks for Riya
        self._run(
            "INSERT INTO tasks (user_id, title, task_type, target_url, priority, due_date, status, created_at, updated_at) VALUES (?,?,?,?,?,?,?,?,?)",
            ("riya", "Track IndiGo Flight Refund (₹8,420)", "MONITOR", "https://much-friendship-somewhat-adaptor.trycloudflare.com", "URGENT", "Today, 6:00 PM", "IN_PROGRESS", now, now),
        )
        self._run(
            "INSERT INTO tasks (user_id, title, task_type, target_url, priority, due_date, status, created_at, updated_at) VALUES (?,?,?,?,?,?,?,?,?)",
            ("riya", "Passport Application Verification", "FORM_FILL", "https://much-friendship-somewhat-adaptor.trycloudflare.com/passport", "HIGH", "Tomorrow, 12:00 PM", "PENDING", now, now),
        )
        self._run(
            "INSERT INTO tasks (user_id, title, task_type, target_url, priority, due_date, status, created_at, updated_at) VALUES (?,?,?,?,?,?,?,?,?)",
            ("riya", "Pay Electricity Bill (₹1,850)", "PAYMENT", "", "URGENT", "Today, 8:00 PM", "PENDING", now, now),
        )
        self._run(
            "INSERT INTO tasks (user_id, title, task_type, target_url, priority, due_date, status, created_at, updated_at) VALUES (?,?,?,?,?,?,?,?,?)",
            ("riya", "Renew Two-Wheeler Insurance", "REMINDER", "", "MEDIUM", "In 3 days", "PENDING", now, now),
        )
        # Vault for Riya
        self._run(
            "INSERT INTO credentials_vault (user_id, service_name, portal_url, username, password, notes, created_at) VALUES (?,?,?,?,?,?,?)",
            ("riya", "IndiGo Airlines Portal", "https://goindigo.in", "riya.sharma@gmail.com", "P@ssw0rd2026", "Saved for refund automation", now),
        )
        self._run(
            "INSERT INTO credentials_vault (user_id, service_name, portal_url, username, password, notes, created_at) VALUES (?,?,?,?,?,?,?)",
            ("riya", "Passport Seva Kendra", "https://passportindia.gov.in", "IND849204", "SecurePass#99", "File ref IND-849204", now),
        )

        # 2. Alex Morgan
        self._run(
            "INSERT INTO users (id, email, password, full_name, role, avatar_initials, created_at) VALUES (?,?,?,?,?,?,?)",
            ("alex", "alex@lifepilot.ai", "password123", "Alex Morgan", "Product Designer", "AM", now),
        )
        self._run(
            """INSERT INTO profiles (user_id, full_name, email, phone, dob, address, city, pincode, id_type, id_number, college, degree, cgpa, updated_at)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            ("alex", "Alex Morgan", "alex@lifepilot.ai", "+91 91234 56789", "1998-11-20", "12 Richmond Town", "Bangalore", "560025", "Aadhaar", "9824-1029-4412", "IIIT Bangalore", "M.Des Interaction Design", 9.1, now),
        )
        self._run(
            "INSERT INTO tasks (user_id, title, task_type, target_url, priority, due_date, status, created_at, updated_at) VALUES (?,?,?,?,?,?,?,?,?)",
            ("alex", "Submit Scholarship Application", "FORM_FILL", "https://scholarships.gov.in", "HIGH", "Tomorrow, 11:59 PM", "IN_PROGRESS", now, now),
        )
        self._run(
            "INSERT INTO tasks (user_id, title, task_type, target_url, priority, due_date, status, created_at, updated_at) VALUES (?,?,?,?,?,?,?,?,?)",
            ("alex", "Pay Broadband Bill (₹999)", "PAYMENT", "", "MEDIUM", "In 2 days", "PENDING", now, now),
        )

        # 3. David Chen (Freelancer / Small Business - Slide 4)
        self._run(
            "INSERT INTO users (id, email, password, full_name, role, avatar_initials, created_at) VALUES (?,?,?,?,?,?,?)",
            ("david", "david@lifepilot.ai", "password123", "David Chen", "Freelance Consultant", "DC", now),
        )
        self._run(
            """INSERT INTO profiles (user_id, full_name, email, phone, dob, address, city, pincode, id_type, id_number, college, degree, cgpa, updated_at)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            ("david", "David Chen", "david@lifepilot.ai", "+91 99887 76655", "1994-08-15", "88 Marine Drive", "Mumbai", "400020", "PAN", "ABCDE1234F", "St. Xavier College", "B.Com Finance", 8.4, now),
        )
        self._run(
            "INSERT INTO tasks (user_id, title, task_type, target_url, priority, due_date, status, created_at, updated_at) VALUES (?,?,?,?,?,?,?,?,?)",
            ("david", "GST Filing & Quarterly Compliance Check", "REMINDER", "https://gst.gov.in", "URGENT", "Today, 5:00 PM", "PENDING", now, now),
        )
        self._run(
            "INSERT INTO tasks (user_id, title, task_type, target_url, priority, due_date, status, created_at, updated_at) VALUES (?,?,?,?,?,?,?,?,?)",
            ("david", "Follow up on Vendor Invoice #INV-2041", "MONITOR", "", "HIGH", "Tomorrow", "IN_PROGRESS", now, now),
        )

    # ---------- Users & Auth ----------
    def authenticate_user(self, email: str, password: str) -> dict | None:
        row = self._run("SELECT * FROM users WHERE email=? AND password=?", (email.strip().lower(), password)).fetchone()
        return dict(row) if row else None

    def get_user(self, user_id: str) -> dict | None:
        row = self._run("SELECT * FROM users WHERE id=?", (user_id,)).fetchone()
        return dict(row) if row else None

    def list_users(self) -> list[dict]:
        rows = self._run("SELECT id, email, full_name, role, avatar_initials, created_at FROM users ORDER BY full_name").fetchall()
        return [dict(r) for r in rows]

    # ---------- Profiles (Personal Data for Form-Filling) ----------
    def get_profile(self, user_id: str) -> dict | None:
        row = self._run("SELECT * FROM profiles WHERE user_id=?", (user_id,)).fetchone()
        return dict(row) if row else None

    def update_profile(self, user_id: str, data: dict) -> None:
        now = time.time()
        self._run(
            """INSERT INTO profiles (user_id, full_name, email, phone, dob, address, city, pincode, id_type, id_number, college, degree, cgpa, updated_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
               ON CONFLICT(user_id) DO UPDATE SET
                 full_name=excluded.full_name,
                 email=excluded.email,
                 phone=excluded.phone,
                 dob=excluded.dob,
                 address=excluded.address,
                 city=excluded.city,
                 pincode=excluded.pincode,
                 id_type=excluded.id_type,
                 id_number=excluded.id_number,
                 college=excluded.college,
                 degree=excluded.degree,
                 cgpa=excluded.cgpa,
                 updated_at=excluded.updated_at
            """,
            (
                user_id,
                data.get("full_name", ""),
                data.get("email", ""),
                data.get("phone", ""),
                data.get("dob", ""),
                data.get("address", ""),
                data.get("city", ""),
                data.get("pincode", ""),
                data.get("id_type", "Passport"),
                data.get("id_number", ""),
                data.get("college", ""),
                data.get("degree", ""),
                float(data.get("cgpa", 0.0) or 0.0),
                now,
            ),
        )

    # ---------- Tasks with Priorities ----------
    def list_tasks(self, user_id: str) -> list[dict]:
        # Sort URGENT first, then HIGH, then MEDIUM, then LOW
        priority_order = "CASE priority WHEN 'URGENT' THEN 1 WHEN 'HIGH' THEN 2 WHEN 'MEDIUM' THEN 3 ELSE 4 END"
        rows = self._run(f"SELECT * FROM tasks WHERE user_id=? ORDER BY status, {priority_order}, id DESC", (user_id,)).fetchall()
        return [dict(r) for r in rows]

    def create_task(self, user_id: str, title: str, task_type: str = "GENERAL", target_url: str = "", priority: str = "MEDIUM", due_date: str = "") -> int:
        now = time.time()
        cur = self._run(
            "INSERT INTO tasks (user_id, title, task_type, target_url, priority, due_date, status, created_at, updated_at) VALUES (?,?,?,?,?,?,?,?,?)",
            (user_id, title, task_type, target_url, priority.upper(), due_date, "PENDING", now, now),
        )
        return cur.lastrowid

    def update_task_priority(self, task_id: int, priority: str) -> None:
        self._run("UPDATE tasks SET priority=?, updated_at=? WHERE id=?", (priority.upper(), time.time(), task_id))

    def update_task_status(self, task_id: int, status: str) -> None:
        self._run("UPDATE tasks SET status=?, updated_at=? WHERE id=?", (status.upper(), time.time(), task_id))

    def update_task(self, task_id: int, title: str, target_url: str, priority: str, due_date: str) -> None:
        self._run(
            "UPDATE tasks SET title=?, target_url=?, priority=?, due_date=?, updated_at=? WHERE id=?",
            (title, target_url, priority.upper(), due_date, time.time(), task_id),
        )

    def delete_task(self, task_id: int) -> None:
        self._run("DELETE FROM tasks WHERE id=?", (task_id,))

    # ---------- Credentials Vault ----------
    def list_vault(self, user_id: str) -> list[dict]:
        rows = self._run("SELECT id, user_id, service_name, portal_url, username, '••••••••' as password_masked, notes, created_at FROM credentials_vault WHERE user_id=? ORDER BY service_name", (user_id,)).fetchall()
        return [dict(r) for r in rows]

    def get_vault_item(self, vault_id: int) -> dict | None:
        row = self._run("SELECT id, user_id, service_name, portal_url, username, password, notes, created_at FROM credentials_vault WHERE id=?", (vault_id,)).fetchone()
        return dict(row) if row else None

    def add_vault_item(self, user_id: str, service_name: str, portal_url: str, username: str, password: str, notes: str = "") -> int:
        cur = self._run(
            "INSERT INTO credentials_vault (user_id, service_name, portal_url, username, password, notes, created_at) VALUES (?,?,?,?,?,?,?)",
            (user_id, service_name, portal_url, username, password, notes, time.time()),
        )
        return cur.lastrowid

    def update_vault_item(self, vault_id: int, service_name: str, portal_url: str, username: str, password: str | None = None, notes: str = "") -> None:
        if password:
            self._run(
                "UPDATE credentials_vault SET service_name=?, portal_url=?, username=?, password=?, notes=? WHERE id=?",
                (service_name, portal_url, username, password, notes, vault_id),
            )
        else:
            self._run(
                "UPDATE credentials_vault SET service_name=?, portal_url=?, username=?, notes=? WHERE id=?",
                (service_name, portal_url, username, notes, vault_id),
            )

    def delete_vault_item(self, vault_id: int) -> None:
        self._run("DELETE FROM credentials_vault WHERE id=?", (vault_id,))

    # ---------- Chat Memory (Persistent History) ----------
    def get_chat_history(self, user_id: str, limit: int = 20) -> list[dict]:
        rows = self._run("SELECT * FROM chat_messages WHERE user_id=? ORDER BY id DESC LIMIT ?", (user_id, limit)).fetchall()
        results = [dict(r) for r in rows]
        results.reverse()
        for r in results:
            r["steps"] = json.loads(r["steps"]) if r.get("steps") else []
        return results

    def save_chat_message(self, user_id: str, role: str, content: str, steps: list[dict] | None = None) -> int:
        cur = self._run(
            "INSERT INTO chat_messages (user_id, role, content, steps, created_at) VALUES (?,?,?,?,?)",
            (user_id, role, content, json.dumps(steps) if steps else None, time.time()),
        )
        return cur.lastrowid

    # ---------- Tool Execution Audit Log (What went IN & what came OUT) ----------
    def log_tool_execution(self, user_id: str | None, tool_name: str, input_payload: Any, output_payload: Any, duration_ms: float, status: str = "SUCCESS") -> int:
        cur = self._run(
            "INSERT INTO tool_executions (user_id, tool_name, input_payload, output_payload, duration_ms, status, created_at) VALUES (?,?,?,?,?,?,?)",
            (
                user_id,
                tool_name,
                json.dumps(input_payload, default=str),
                json.dumps(output_payload, default=str) if not isinstance(output_payload, str) else output_payload,
                duration_ms,
                status,
                time.time(),
            ),
        )
        return cur.lastrowid

    def list_tool_executions(self, user_id: str | None = None, limit: int = 40) -> list[dict]:
        if user_id:
            rows = self._run("SELECT * FROM tool_executions WHERE user_id=? ORDER BY id DESC LIMIT ?", (user_id, limit)).fetchall()
        else:
            rows = self._run("SELECT * FROM tool_executions ORDER BY id DESC LIMIT ?", (limit,)).fetchall()
        return [dict(r) for r in rows]

    # ---------- Monitors ----------
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
            rows = self._run("SELECT * FROM monitors WHERE user_id=? ORDER BY id DESC", (user_id,)).fetchall()
        else:
            rows = self._run("SELECT * FROM monitors ORDER BY id DESC").fetchall()
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

    # ---------- Snapshots ----------
    def last_snapshot(self, monitor_id: int) -> dict | None:
        row = self._run("SELECT result FROM snapshots WHERE monitor_id=? ORDER BY id DESC LIMIT 1", (monitor_id,)).fetchone()
        return json.loads(row["result"]) if row else None

    def save_snapshot(self, monitor_id: int, result: dict) -> None:
        self._run("INSERT INTO snapshots (monitor_id,result,created_at) VALUES (?,?,?)", (monitor_id, json.dumps(result), time.time()))

    # ---------- Alerts ----------
    def add_alert(self, monitor_id: int | None, user_id: str, message: str) -> None:
        self._run("INSERT INTO alerts (monitor_id,user_id,message,created_at) VALUES (?,?,?,?)", (monitor_id, user_id, message, time.time()))

    def list_alerts(self, user_id: str | None = None, limit: int = 50) -> list[dict]:
        if user_id:
            rows = self._run("SELECT * FROM alerts WHERE user_id=? ORDER BY id DESC LIMIT ?", (user_id, limit)).fetchall()
        else:
            rows = self._run("SELECT * FROM alerts ORDER BY id DESC LIMIT ?", (limit,)).fetchall()
        return [dict(r) for r in rows]

    # ---------- Goals (Persistent State) ----------
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
