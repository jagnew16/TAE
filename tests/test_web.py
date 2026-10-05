"""The dashboard API: same privacy rules as the agents, and chat degrades cleanly without a key."""

import pytest
from fastapi.testclient import TestClient

from aaa import web


@pytest.fixture
def client(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)  # startup monitor uses the keyword filter
    with TestClient(web.app) as c:
        yield c


def test_page_is_served(client):
    r = client.get("/")
    assert r.status_code == 200 and "AAA" in r.text


def test_dashboard_only_shows_the_reps_own_work(client):
    d = client.get("/api/dashboard", params={"rep": "alice"}).json()
    assert d["rep"]["name"] == "Alice Moreno"
    assert all(t["rep"] == "alice" for t in d["tasks"])
    assert d["launches"] and all(a["rep"] == "alice" for a in d["launches"])
    assert {a["level"] for a in d["attention"]} <= {"red", "amber", "cyan"}
    assert d["recommendation"]["prompt"]


def test_tasks_and_launches_are_private(client):
    for rep in ("alice", "ben", "carla"):
        assert all(t["rep"] == rep for t in client.get("/api/tasks", params={"rep": rep}).json()["tasks"])
        assert all(a["rep"] == rep for a in client.get("/api/launches", params={"rep": rep}).json()["alerts"])


def test_pipeline_owner_vs_manager(client):
    alice = client.get("/api/pipeline", params={"rep": "alice"}).json()["records"]
    dana = client.get("/api/pipeline", params={"rep": "dana"}).json()["records"]
    assert {r["owner_id"] for r in alice} == {"alice"}
    assert len(dana) > len(alice)


def test_market_flags_crm_status(client):
    m = client.get("/api/market", params={"rep": "alice", "state": "CA", "period": "quarter"}).json()
    tones = {b["brand"]: b["tone"] for b in m["brands"]}
    assert tones["Sierra Pine Supply"] == "customer"
    assert tones["Ember Labs"] == "blocked"
    assert "new" in tones.values()
    assert m["trends"]


def test_complete_task_logs_to_crm_and_rejects_other_reps_tasks(client):
    ben_task = client.get("/api/tasks", params={"rep": "ben"}).json()["tasks"][0]["id"]
    assert client.post(f"/api/tasks/{ben_task}/complete", json={"rep": "alice", "outcome": "x"}).status_code == 404
    r = client.post(f"/api/tasks/{ben_task}/complete", json={"rep": "ben", "outcome": "Sent pricing"})
    assert r.status_code == 200 and r.json()["crm_activity"]["logged"]


def test_chat_without_key_explains_itself(client):
    r = client.post("/api/chat", json={"rep": "alice", "message": "hi"})
    assert r.status_code == 503 and "OPENAI_API_KEY" in r.json()["detail"]


def test_unknown_rep(client):
    assert client.get("/api/dashboard", params={"rep": "nobody"}).status_code == 404
