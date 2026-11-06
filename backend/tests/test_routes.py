from __future__ import annotations

from dataclasses import replace

import pytest
from fastapi.testclient import TestClient

import db
import memory
from main import app


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setattr(db, "settings", replace(db.settings, db_path=tmp_path / "api.db"))
    monkeypatch.setattr(memory, "is_configured", lambda: False)
    with TestClient(app) as test_client:
        yield test_client


def test_network_route_starts_empty(client):
    response = client.get("/network")
    assert response.status_code == 200
    assert response.json() == {"nodes": [], "edges": []}


def test_network_route_marks_the_current_conversation(client):
    db.create_conversation("conv_0001", "2026-11-06T10:00:00Z")
    message_id = db.add_message(
        "conv_0001", "scammer", "Inspector Sharma from CBI.", "2026-11-06T10:01:00Z"
    )
    db.upsert_iocs(
        "conv_0001",
        message_id,
        [
            {"type": "alias", "value": "inspector sharma"},
            {"type": "agency_claimed", "value": "cbi"},
        ],
        seen_at="2026-11-06T10:01:00Z",
    )

    response = client.get("/network", params={"conversation_id": "conv_0001"})
    assert response.status_code == 200

    body = response.json()
    nodes = {node["id"]: node for node in body["nodes"]}
    assert nodes["alias:inspector sharma"]["in_current"] is True
    assert nodes["alias:inspector sharma"]["label"] == "Inspector Sharma"
    assert body["edges"][0]["relation"] == "claims_agency"


def test_stats_route_has_every_api_md_field(client):
    response = client.get("/stats")
    assert response.status_code == 200

    body = response.json()
    assert set(body) == {
        "conversations",
        "total_minutes_wasted_estimate",
        "minutes_is_estimate",
        "unique_aliases",
        "unique_upi",
        "unique_phones",
        "rings_detected",
        "contradictions_caught",
        "memories_in_bank",
    }
    assert body["conversations"] == 0
    assert body["minutes_is_estimate"] is True
