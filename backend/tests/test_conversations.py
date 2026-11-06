from __future__ import annotations

from dataclasses import replace

import pytest
from fastapi.testclient import TestClient

import agent
import db
import memory
import persona
from extract import Ioc
from main import app


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setattr(db, "settings", replace(db.settings, db_path=tmp_path / "api.db"))
    monkeypatch.setattr(agent, "settings", replace(agent.settings, groq_api_key="test-key"))
    monkeypatch.setattr(
        agent,
        "extract_iocs",
        lambda text, timeout=None: (
            [
                Ioc(type="alias", value="inspector sharma"),
                Ioc(type="agency_claimed", value="cbi"),
                Ioc(type="case_number", value="DL/4410"),
                Ioc(type="script_stage", value="fake_case_number"),
            ],
            "fake_case_number",
            False,
        ),
    )
    monkeypatch.setattr(
        agent.memory,
        "recall",
        lambda query, timeout=None: [
            {
                "text": "Inspector Sharma gave case MH/2291 in conversation conv_0007.",
                "source_conversation_id": "conv_0007",
            }
        ],
    )
    monkeypatch.setattr(agent.memory, "is_configured", lambda: False)
    monkeypatch.setattr(
        agent,
        "_call_groq_reply",
        lambda messages, model, timeout: "Aiyyo, sir, which case number you said?",
    )

    with TestClient(app) as test_client:
        yield test_client


def create(client) -> str:
    response = client.post("/conversations", json={"persona": "ajji"})
    assert response.status_code == 201
    return response.json()["conversation_id"]


def test_full_conversation_lifecycle(client):
    created = client.post("/conversations", json={"persona": "ajji"})
    assert created.status_code == 201
    body = created.json()
    assert set(body) == {"conversation_id", "persona", "started_at", "opening_line"}
    assert body["conversation_id"] == "conv_0001"
    assert body["persona"] == "ajji"
    assert body["opening_line"]

    conversation_id = body["conversation_id"]
    sent = client.post(
        f"/conversations/{conversation_id}/message",
        json={
            "sender": "scammer",
            "text": "  Madam, this is Inspector Sharma from CBI. Case DL/4410.  ",
            "memory_enabled": False,
        },
    )
    assert sent.status_code == 200

    message = sent.json()
    assert message["conversation_id"] == conversation_id
    assert message["memory_enabled"] is False
    assert message["recalled_memories"] == []
    assert message["contradiction_flags"] == []
    assert message["script_stage"] == "fake_case_number"
    assert message["reply"]["sender"] == "ajji"
    assert message["degraded"] == []

    history = client.get(f"/conversations/{conversation_id}")
    assert history.status_code == 200
    messages = history.json()["messages"]
    assert len(messages) == 3
    assert messages[0]["text"] == body["opening_line"]
    assert messages[1]["text"] == "Madam, this is Inspector Sharma from CBI. Case DL/4410."
    assert messages[2]["sender"] == "ajji"

    network = client.get("/network", params={"conversation_id": conversation_id})
    assert network.status_code == 200
    nodes = {node["id"]: node for node in network.json()["nodes"]}
    assert nodes["alias:inspector sharma"]["in_current"] is True
    assert nodes["agency_claimed:cbi"]["label"] == "CBI"

    stats = client.get("/stats")
    assert stats.status_code == 200
    assert stats.json()["conversations"] == 1
    assert stats.json()["unique_aliases"] == 1

    ended = client.post(f"/conversations/{conversation_id}/end")
    assert ended.status_code == 200
    ended_body = ended.json()
    assert ended_body["summary"]["aliases"] == ["inspector sharma"]
    assert ended_body["summary"]["case_numbers"] == ["DL/4410"]
    assert ended_body["summary"]["stages_reached"] == ["fake_case_number"]

    ended_again = client.post(f"/conversations/{conversation_id}/end")
    assert ended_again.status_code == 200
    assert ended_again.json()["ended_at"] == ended_body["ended_at"]
    assert ended_again.json()["summary"] == ended_body["summary"]

    after_end = client.post(
        f"/conversations/{conversation_id}/message",
        json={"sender": "scammer", "text": "Hello again", "memory_enabled": False},
    )
    assert after_end.status_code == 409
    assert after_end.json()["error"]["code"] == "conversation_ended"


def test_memory_on_response_includes_recalled_memories(client):
    conversation_id = create(client)
    response = client.post(
        f"/conversations/{conversation_id}/message",
        json={
            "sender": "scammer",
            "text": "This is Inspector Sharma from CBI. Case DL/4410.",
            "memory_enabled": True,
        },
    )
    assert response.status_code == 200

    body = response.json()
    assert body["memory_enabled"] is True
    assert len(body["recalled_memories"]) == 1
    memory = body["recalled_memories"][0]
    assert memory["source_conversation_id"] == "conv_0007"
    assert memory["matched_ioc"] == {"type": "alias", "value": "inspector sharma"}
    assert memory["why_relevant"] == "Same alias seen in an earlier chat"


def test_background_tasks_receive_trimmed_text_and_stage(client, monkeypatch):
    retained: list[tuple] = []
    summaries: list[tuple] = []

    def record_retain(text, conversation_id, stage):
        retained.append((text, conversation_id, stage))

    def record_summary(summary, conversation_id):
        summaries.append((summary, conversation_id))

    monkeypatch.setattr(agent, "retain_safely", record_retain)
    monkeypatch.setattr(agent, "retain_summary_safely", record_summary)

    conversation_id = create(client)
    client.post(
        f"/conversations/{conversation_id}/message",
        json={
            "sender": "scammer",
            "text": "   Inspector Sharma.   ",
            "memory_enabled": False,
        },
    )

    assert retained == [("Inspector Sharma.", conversation_id, "fake_case_number")]

    client.post(f"/conversations/{conversation_id}/end")
    client.post(f"/conversations/{conversation_id}/end")
    assert len(summaries) == 1
    assert summaries[0][1] == conversation_id


def test_error_shapes_match_api_md(client):
    conversation_id = create(client)

    wrong_sender = client.post(
        f"/conversations/{conversation_id}/message",
        json={"sender": "ajji", "text": "Hello", "memory_enabled": False},
    )
    assert wrong_sender.status_code == 400
    assert wrong_sender.json()["error"]["code"] == "invalid_message"

    empty = client.post(
        f"/conversations/{conversation_id}/message",
        json={"sender": "scammer", "text": "   ", "memory_enabled": False},
    )
    assert empty.status_code == 400
    assert empty.json()["error"]["code"] == "invalid_message"

    missing = client.post(
        "/conversations/conv_missing/message",
        json={"sender": "scammer", "text": "Hello", "memory_enabled": False},
    )
    assert missing.status_code == 404
    assert missing.json() == {
        "error": {
            "code": "conversation_not_found",
            "message": "That conversation doesn't exist. Start a new one.",
        }
    }

    missing_history = client.get("/conversations/conv_missing")
    assert missing_history.status_code == 404
    assert missing_history.json()["error"]["code"] == "conversation_not_found"

    wrong_persona = client.post("/conversations", json={"persona": "someone-else"})
    assert wrong_persona.status_code == 400
    assert wrong_persona.json()["error"]["code"] == "invalid_request"


def test_create_conversation_without_a_body(client):
    response = client.post("/conversations")
    assert response.status_code == 201
    assert response.json()["persona"] == "ajji"


def test_message_endpoint_returns_200_when_groq_and_hindsight_fail(client, monkeypatch):
    conversation_id = create(client)

    monkeypatch.setattr(
        agent, "extract_iocs", lambda text, timeout=None: ([], None, True)
    )
    monkeypatch.setattr(
        agent.memory,
        "recall",
        lambda query, timeout=None: (_ for _ in ()).throw(
            memory.MemoryUnavailable("hindsight is down")
        ),
    )
    monkeypatch.setattr(
        agent,
        "_call_groq_reply",
        lambda messages, model, timeout: (_ for _ in ()).throw(
            RuntimeError("groq is down")
        ),
    )

    response = client.post(
        f"/conversations/{conversation_id}/message",
        json={
            "sender": "scammer",
            "text": "Inspector Sharma. Case DL/4410.",
            "memory_enabled": True,
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert set(body["degraded"]) == {
        "extract_fallback_regex",
        "recall_unavailable",
        "reply_fallback_canned",
    }
    assert body["reply"]["text"] in persona.CANNED_REPLIES
    assert body["recalled_memories"] == []
    assert body["contradiction_flags"] == []
    assert set(body["timings_ms"]) == {"extract", "recall", "reply", "retain", "total"}


def test_message_endpoint_degrades_with_memory_off_when_groq_fails(client, monkeypatch):
    conversation_id = create(client)

    monkeypatch.setattr(
        agent, "extract_iocs", lambda text, timeout=None: ([], None, True)
    )
    monkeypatch.setattr(
        agent,
        "_call_groq_reply",
        lambda messages, model, timeout: (_ for _ in ()).throw(
            RuntimeError("groq is down")
        ),
    )

    response = client.post(
        f"/conversations/{conversation_id}/message",
        json={
            "sender": "scammer",
            "text": "Inspector Sharma. Case DL/4410.",
            "memory_enabled": False,
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert set(body["degraded"]) == {
        "extract_fallback_regex",
        "reply_fallback_canned",
    }
    assert body["reply"]["text"] in persona.CANNED_REPLIES
    assert body["recalled_memories"] == []
