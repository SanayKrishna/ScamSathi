from __future__ import annotations

from types import SimpleNamespace

import pytest
from hindsight_client_api.exceptions import ApiException

import memory


class FakeClient:
    def __init__(self, existing: bool = False, total: int = 12) -> None:
        self.existing = existing
        self.total = total
        self.created: list[dict] = []
        self.deleted: list[str] = []
        self.retained: list[dict] = []
        self.recall_error: Exception | None = None
        self.recall_results: list[SimpleNamespace] = []
        self.closed = False

    def get_bank_config(self, bank_id: str):
        if not self.existing:
            raise ApiException(status=404, reason="not found")
        return {"bank_id": bank_id}

    def create_bank(self, **kwargs):
        self.created.append(kwargs)
        self.existing = True
        return SimpleNamespace(bank_id=kwargs["bank_id"])

    def delete_bank(self, bank_id: str):
        if not self.existing:
            raise ApiException(status=404, reason="not found")
        self.deleted.append(bank_id)
        self.existing = False

    def retain(self, **kwargs):
        self.retained.append(kwargs)
        return SimpleNamespace(success=True)

    def recall(self, **kwargs):
        if self.recall_error:
            raise self.recall_error
        return SimpleNamespace(results=self.recall_results)

    def list_memories(self, **kwargs):
        return SimpleNamespace(total=self.total)

    def close(self):
        self.closed = True


@pytest.fixture
def fake(monkeypatch):
    client = FakeClient()
    monkeypatch.setattr(memory, "_get_client", lambda *args, **kwargs: client)
    return client


def test_ensure_bank_creates_a_missing_bank(fake):
    memory.ensure_bank()
    assert fake.created
    assert fake.created[0]["bank_id"] == memory.settings.hindsight_bank_id
    assert fake.created[0]["name"] == "ScamSathi"


def test_ensure_bank_is_idempotent(monkeypatch):
    client = FakeClient(existing=True)
    monkeypatch.setattr(memory, "_get_client", lambda *args, **kwargs: client)
    memory.ensure_bank()
    assert client.created == []


def test_reset_bank_deletes_then_recreates(fake):
    fake.existing = True
    memory.reset_bank()
    assert fake.deleted == [memory.settings.hindsight_bank_id]
    assert len(fake.created) == 1


def test_reset_bank_tolerates_a_missing_bank(fake):
    fake.existing = False
    memory.reset_bank()
    assert fake.deleted == []
    assert len(fake.created) == 1


def test_retain_message_stores_attributable_context(fake):
    memory.retain_message(
        "This is Inspector Sharma. Transfer to sharma.verify@fakebank.",
        conversation_id="conv_0021",
        stage="verification_transfer",
        timestamp="2026-11-06T10:42:00Z",
    )

    item = fake.retained[0]
    assert item["content"].startswith("This is Inspector Sharma")
    assert "conversation=conv_0021" in item["context"]
    assert "stage=verification_transfer" in item["context"]
    assert f"persona={memory.settings.persona_name}" in item["context"]
    assert item["metadata"]["conversation_id"] == "conv_0021"
    assert item["timestamp"] == "2026-11-06T10:42:00Z"


def test_retain_summary_turns_the_summary_into_a_paragraph(fake):
    summary = {
        "aliases": ["inspector sharma", "officer verma"],
        "agencies_claimed": ["cbi"],
        "case_numbers": ["DL/4410"],
        "upi_ids": ["sharma.verify@fakebank"],
        "phones": ["5550142233"],
        "stages_reached": ["intro_threat", "fake_case_number"],
        "tactics": ["urgency"],
    }

    memory.retain_summary(summary, conversation_id="conv_0021")

    item = fake.retained[0]
    assert "Aliases used: inspector sharma, officer verma." in item["content"]
    assert "UPI IDs: sharma.verify@fakebank." in item["content"]
    assert item["context"].startswith("conversation_summary")
    assert "conversation=conv_0021" in item["context"]
    assert item["metadata"]["kind"] == "conversation_summary"


def test_recall_parses_source_chat_and_caps_at_five(fake):
    fake.recall_results = [
        SimpleNamespace(text=f"fact {i}", context=f"conversation=conv_000{i} stage=x persona=Ajji")
        for i in range(1, 9)
    ]

    results = memory.recall("sharma.verify@fakebank")

    assert len(results) == 5
    assert results[0] == {"text": "fact 1", "source_conversation_id": "conv_0001"}
    assert results[-1]["source_conversation_id"] == "conv_0005"


def test_recall_deduplicates_text_and_handles_summaries(fake):
    fake.recall_results = [
        SimpleNamespace(text="same fact", context="conversation=conv_0004"),
        SimpleNamespace(text="same fact", context="conversation=conv_0004"),
        SimpleNamespace(text="pattern fact", context="conversation_summary persona=Ajji"),
        SimpleNamespace(text="", context=None),
    ]

    results = memory.recall("query")

    assert results == [
        {"text": "same fact", "source_conversation_id": "conv_0004"},
        {"text": "pattern fact", "source_conversation_id": None},
    ]


def test_recall_wraps_failures_as_memory_unavailable(fake):
    fake.recall_error = RuntimeError("connection reset")

    with pytest.raises(memory.MemoryUnavailable):
        memory.recall("query")


def test_memory_count_reads_the_bank_total(fake):
    fake.total = 312
    assert memory.memory_count() == 312


def test_missing_configuration_is_memory_unavailable(monkeypatch):
    from dataclasses import replace

    monkeypatch.setattr(memory, "settings", replace(memory.settings, hindsight_url=""))

    with pytest.raises(memory.MemoryUnavailable):
        memory._get_client()


def test_recall_passes_its_budget_to_the_client(monkeypatch):
    client = FakeClient()
    client.recall_results = []
    seen: dict = {}

    def get_client(*args, **kwargs):
        seen.update(kwargs)
        return client

    monkeypatch.setattr(memory, "_get_client", get_client)

    memory.recall("query", timeout=1.5)
    assert seen["timeout"] == 1.5
