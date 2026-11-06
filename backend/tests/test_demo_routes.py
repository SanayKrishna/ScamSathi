from __future__ import annotations

from dataclasses import replace

import pytest
from fastapi.testclient import TestClient

import db
import demo
import memory
from errors import ApiError
from main import app


class FakeManager:
    def __init__(self) -> None:
        self.job: dict | None = None

    def start(self, planned: int | None = None) -> dict:
        if self.running():
            raise ApiError(
                409,
                "seed_already_running",
                "A seed job is already running. Wait for it to finish.",
            )
        planned = planned or 20
        self.job = {
            "job_id": "seed_test",
            "status": "running",
            "conversations_done": 0,
            "conversations_planned": planned,
            "error": None,
        }
        return {
            "job_id": "seed_test",
            "status": "running",
            "conversations_planned": planned,
        }

    def status(self, job_id: str) -> dict | None:
        if not self.job or self.job["job_id"] != job_id:
            return None
        return dict(self.job)

    def running(self) -> bool:
        return bool(self.job and self.job["status"] == "running")

    def reset(self) -> None:
        if self.running():
            raise ApiError(409, "seed_already_running", "A seed job is running.")
        self.job = None


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setattr(
        db, "settings", replace(db.settings, db_path=tmp_path / "demo-routes.db")
    )
    monkeypatch.setattr(memory, "is_configured", lambda: False)
    fake = FakeManager()
    monkeypatch.setattr(demo, "seed_manager", fake)
    with TestClient(app) as test_client:
        yield test_client, fake


def seed_one_conversation() -> None:
    db.create_conversation("conv_0001", "2026-11-06T10:00:00Z")
    message_id = db.add_message(
        "conv_0001", "scammer", "Inspector Sharma.", "2026-11-06T10:01:00Z"
    )
    db.upsert_iocs(
        "conv_0001",
        message_id,
        [{"type": "alias", "value": "inspector sharma"}],
        seen_at="2026-11-06T10:01:00Z",
    )


def test_seed_route_returns_202_and_a_pollable_job(client):
    test_client, _ = client

    response = test_client.post("/demo/seed")
    assert response.status_code == 202
    body = response.json()
    assert body == {
        "job_id": "seed_test",
        "status": "running",
        "conversations_planned": 20,
    }

    status = test_client.get(f"/demo/seed/{body['job_id']}")
    assert status.status_code == 200
    assert status.json() == {
        "job_id": "seed_test",
        "status": "running",
        "conversations_done": 0,
        "conversations_planned": 20,
        "error": None,
    }


def test_second_seed_while_running_returns_409(client):
    test_client, _ = client
    assert test_client.post("/demo/seed").status_code == 202

    second = test_client.post("/demo/seed")
    assert second.status_code == 409
    assert second.json()["error"]["code"] == "seed_already_running"


def test_unknown_seed_job_returns_404(client):
    test_client, _ = client
    response = test_client.get("/demo/seed/seed_missing")
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "not_found"


def test_reset_requires_the_exact_confirmation(client):
    test_client, _ = client

    for payload in ({}, {"confirm": ""}, {"confirm": "reset"}):
        response = test_client.post("/demo/reset", json=payload)
        assert response.status_code == 400
        assert response.json()["error"]["code"] == "reset_not_confirmed"


def test_reset_wipes_sqlite_and_clears_the_job(client):
    test_client, fake = client
    seed_one_conversation()
    assert test_client.get("/stats").json()["conversations"] == 1

    response = test_client.post("/demo/reset", json={"confirm": "RESET"})
    assert response.status_code == 200
    assert response.json() == {"status": "reset", "bank_id": "scam-intel"}

    assert test_client.get("/stats").json()["conversations"] == 0
    assert test_client.get("/network").json() == {"nodes": [], "edges": []}
    assert fake.job is None


def test_reset_is_blocked_while_seeding(client):
    test_client, _ = client
    seed_one_conversation()
    assert test_client.post("/demo/seed").status_code == 202

    response = test_client.post("/demo/reset", json={"confirm": "RESET"})
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "seed_already_running"
    assert test_client.get("/stats").json()["conversations"] == 1


def test_hindsight_reset_failure_keeps_sqlite(client, monkeypatch):
    test_client, _ = client
    seed_one_conversation()

    monkeypatch.setattr(memory, "is_configured", lambda: True)
    monkeypatch.setattr(
        memory,
        "reset_bank",
        lambda: (_ for _ in ()).throw(memory.MemoryUnavailable("down")),
    )

    response = test_client.post("/demo/reset", json={"confirm": "RESET"})
    assert response.status_code == 500
    assert response.json()["error"]["code"] == "internal"
    assert test_client.get("/stats").json()["conversations"] == 1
