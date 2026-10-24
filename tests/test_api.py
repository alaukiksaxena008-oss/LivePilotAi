from fastapi.testclient import TestClient


def test_health_and_empty_lists(monkeypatch):
    monkeypatch.setenv("TINYFISH_API_KEY", "test")
    monkeypatch.setenv("DB_PATH", ":memory:")
    monkeypatch.setenv("SCHEDULER_TICK", "3600")
    from app.main import app

    with TestClient(app) as c:
        assert c.get("/health").json() == {"ok": True}
        assert c.get("/monitors").json() == []
        assert c.get("/alerts").json() == []
        assert c.post("/monitors/99/run").status_code == 404
        assert c.post("/monitors/99/pause").status_code == 404
        assert c.post("/monitors/99/resume").status_code == 404
        assert c.delete("/monitors/99").status_code == 404
        assert c.post("/goals/nope/reply", json={"text": "x"}).status_code == 404
