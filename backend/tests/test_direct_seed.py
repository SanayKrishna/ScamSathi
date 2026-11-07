from __future__ import annotations

from dataclasses import replace

import pytest

import db
import memory
from simulator.direct import run_seed_direct


@pytest.fixture
def database(tmp_path, monkeypatch):
    monkeypatch.setattr(
        db, "settings", replace(db.settings, db_path=tmp_path / "direct.db")
    )
    db.init_db()
    return db


def test_direct_seed_populates_graph_stats_memory_and_contradictions(
    database, monkeypatch
):
    calls: list[tuple] = []

    monkeypatch.setattr(memory, "is_configured", lambda: True)
    monkeypatch.setattr(memory, "ensure_bank", lambda: calls.append(("ensure",)))
    monkeypatch.setattr(
        memory,
        "retain_message",
        lambda text, conversation_id, stage, timestamp=None: calls.append(
            ("message", conversation_id, stage)
        ),
    )
    monkeypatch.setattr(
        memory,
        "retain_summary",
        lambda summary, conversation_id: calls.append(("summary", conversation_id)),
    )

    progress: list[int] = []
    run_seed_direct(
        conversations=8,
        on_progress=lambda: progress.append(len(progress) + 1),
        seed=7,
    )

    stats = database.get_stats()
    assert stats["conversations"] == 8
    assert stats["unique_aliases"] == 8
    assert stats["rings_detected"] == 4
    assert stats["contradictions_caught"] > 0
    assert progress == [1, 2, 3, 4, 5, 6, 7, 8]

    network = database.get_network()
    ring1_aliases = [
        node["label"]
        for node in network["nodes"]
        if node["ring_id"] == "ring_1" and node["type"] == "alias"
    ]
    assert ring1_aliases == ["Inspector Sharma", "Officer Verma"]

    assert calls.count(("ensure",)) == 1
    assert any(call[0] == "message" for call in calls)
    assert sum(1 for call in calls if call[0] == "summary") == 8


def test_direct_seed_skips_hindsight_when_not_configured(database, monkeypatch):
    monkeypatch.setattr(memory, "is_configured", lambda: False)

    run_seed_direct(conversations=2, seed=7)

    stats = database.get_stats()
    assert stats["conversations"] == 2
    assert stats["unique_aliases"] == 2
