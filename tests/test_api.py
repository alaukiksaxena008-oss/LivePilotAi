from fastapi.testclient import TestClient


def test_health_and_empty_lists(monkeypatch):
    monkeypatch.setenv("TINYFISH_API_KEY", "test")
    monkeypatch.setenv("DB_PATH", ":memory:")
    monkeypatch.setenv("SCHEDULER_TICK", "3600")
    from app.main import app

    with TestClient(app) as c:
        assert c.get("/health").json() == {"ok": True}
        assert c.get("/").status_code == 200
        assert "LifePilot" in c.get("/").text
        assert c.get("/monitors").json() == []
        assert c.get("/alerts").json() == []
        assert c.post("/monitors/99/run").status_code == 404
        assert c.post("/monitors/99/pause").status_code == 404
        assert c.post("/monitors/99/resume").status_code == 404
        assert c.delete("/monitors/99").status_code == 404
        assert c.post("/goals/nope/reply", json={"text": "x"}).status_code == 404


def test_goal_persistence_and_restart_recovery(monkeypatch):
    monkeypatch.setenv("TINYFISH_API_KEY", "test")
    monkeypatch.setenv("DB_PATH", ":memory:")
    monkeypatch.setenv("SCHEDULER_TICK", "3600")
    from unittest.mock import AsyncMock, patch

    from app.agent.loop import GoalResult
    from app.agent.tools import Budget
    from app.main import app

    with TestClient(app) as c:
        db = app.state.db
        goal_result = GoalResult(
            status="waiting_for_user",
            question="Enter OTP",
            pending_tool_use_id="call_otp_1",
            messages=[{"role": "user", "content": "Check passport"}],
            steps=[{"tool": "ask_user"}],
        )
        budget = Budget(10, 2)
        db.save_goal("goal123", "u1", "Check passport", goal_result, budget)

        res = c.get("/goals/goal123")
        assert res.status_code == 200
        assert res.json()["status"] == "waiting_for_user"

        # Clear in-memory dictionary to simulate server restart
        app.state.goals.clear()
        assert "goal123" not in app.state.goals

        with patch("app.main.resume_goal", new_callable=AsyncMock) as mock_resume:
            mock_resume.return_value = GoalResult(status="done", answer="Passport Dispatched!")
            reply_res = c.post("/goals/goal123/reply", json={"text": "482910"})
            assert reply_res.status_code == 200
            assert reply_res.json()["status"] == "done"
            assert reply_res.json()["answer"] == "Passport Dispatched!"

            updated = db.get_goal("goal123")
            assert updated["status"] == "done"
            assert updated["answer"] == "Passport Dispatched!"

