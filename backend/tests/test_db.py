from __future__ import annotations

from dataclasses import replace

import pytest

import db as db_module


@pytest.fixture
def database(tmp_path, monkeypatch):
    monkeypatch.setattr(
        db_module,
        "settings",
        replace(db_module.settings, db_path=tmp_path / "test.db"),
    )
    db_module.init_db()
    return db_module


def add_scammer_message(database, conversation_id, text, iocs, at, stage=None):
    message_id = database.add_message(
        conversation_id,
        "scammer",
        text,
        created_at=at,
        script_stage=stage,
        memory_enabled=True,
    )
    database.upsert_iocs(conversation_id, message_id, iocs, seen_at=at)
    return message_id


def test_two_aliases_sharing_a_upi_form_a_ring(database):
    database.create_conversation("conv_0001", "2026-11-05T14:00:00Z")
    add_scammer_message(
        database,
        "conv_0001",
        "Inspector Sharma, CBI. Transfer to sharma.verify@fakebank.",
        [
            {"type": "alias", "value": "inspector sharma"},
            {"type": "upi", "value": "sharma.verify@fakebank"},
        ],
        "2026-11-05T14:01:00Z",
    )

    database.create_conversation("conv_0002", "2026-11-05T14:20:00Z")
    add_scammer_message(
        database,
        "conv_0002",
        "Officer Verma, CBI. Same account sharma.verify@fakebank.",
        [
            {"type": "alias", "value": "officer verma"},
            {"type": "upi", "value": "sharma.verify@fakebank"},
        ],
        "2026-11-05T14:21:00Z",
    )

    database.create_conversation("conv_0003", "2026-11-05T15:00:00Z")
    add_scammer_message(
        database,
        "conv_0003",
        "Unrelated Caller from Customs. Pay parcel.clear@fakebank.",
        [
            {"type": "alias", "value": "unrelated caller"},
            {"type": "agency_claimed", "value": "customs"},
            {"type": "upi", "value": "parcel.clear@fakebank"},
        ],
        "2026-11-05T15:01:00Z",
    )

    network = database.get_network()
    nodes = {node["id"]: node for node in network["nodes"]}

    assert nodes["alias:inspector sharma"]["ring_id"] == "ring_1"
    assert nodes["alias:officer verma"]["ring_id"] == "ring_1"
    assert nodes["upi:sharma.verify@fakebank"]["ring_id"] == "ring_1"

    assert nodes["alias:unrelated caller"]["ring_id"] is None
    assert nodes["upi:parcel.clear@fakebank"]["ring_id"] is None
    assert nodes["agency_claimed:customs"]["ring_id"] is None

    edge_keys = {(edge["source"], edge["target"], edge["relation"]) for edge in network["edges"]}
    assert (
        "alias:inspector sharma",
        "upi:sharma.verify@fakebank",
        "uses_upi",
    ) in edge_keys
    assert (
        "alias:officer verma",
        "upi:sharma.verify@fakebank",
        "uses_upi",
    ) in edge_keys


def test_alias_and_target_link_across_messages_in_one_conversation(database):
    database.create_conversation("conv_0010", "2026-11-05T16:00:00Z")
    add_scammer_message(
        database,
        "conv_0010",
        "This is Inspector Rao.",
        [{"type": "alias", "value": "inspector rao"}],
        "2026-11-05T16:01:00Z",
    )
    add_scammer_message(
        database,
        "conv_0010",
        "Send it to mule.account@fakebank.",
        [{"type": "upi", "value": "mule.account@fakebank"}],
        "2026-11-05T16:02:00Z",
    )

    network = database.get_network()
    edges = {(edge["source"], edge["target"], edge["relation"]) for edge in network["edges"]}
    assert ("alias:inspector rao", "upi:mule.account@fakebank", "uses_upi") in edges

    node = next(node for node in network["nodes"] if node["id"] == "alias:inspector rao")
    assert node["ring_id"] is None  # only one alias in this component


def test_nodes_have_api_labels_and_exclude_case_numbers_and_stages(database):
    database.create_conversation("conv_0020", "2026-11-05T17:00:00Z")
    add_scammer_message(
        database,
        "conv_0020",
        "Sub-Inspector Rao, CBI. Case DL/4410. Call 5550142233.",
        [
            {"type": "alias", "value": "sub-inspector rao"},
            {"type": "agency_claimed", "value": "cbi"},
            {"type": "phone", "value": "5550142233"},
            {"type": "case_number", "value": "DL/4410"},
            {"type": "script_stage", "value": "fake_case_number"},
        ],
        "2026-11-05T17:01:00Z",
    )

    network = database.get_network("conv_0020")
    nodes = {node["id"]: node for node in network["nodes"]}

    assert nodes["alias:sub-inspector rao"]["label"] == "Sub-Inspector Rao"
    assert nodes["agency_claimed:cbi"]["label"] == "CBI"
    assert nodes["phone:5550142233"]["label"] == "555-014-2233"
    assert "case_number:DL/4410" not in nodes
    assert "script_stage:fake_case_number" not in nodes

    assert nodes["alias:sub-inspector rao"]["in_current"] is True
    assert nodes["agency_claimed:cbi"]["in_current"] is True
    assert nodes["agency_claimed:cbi"]["ring_id"] is None


def test_in_current_is_false_for_another_conversation(database):
    database.create_conversation("conv_0030", "2026-11-05T18:00:00Z")
    add_scammer_message(
        database,
        "conv_0030",
        "Inspector Sharma.",
        [{"type": "alias", "value": "inspector sharma"}],
        "2026-11-05T18:01:00Z",
    )

    network = database.get_network("conv_9999")
    assert all(node["in_current"] is False for node in network["nodes"])

    network = database.get_network()
    assert all(node["in_current"] is False for node in network["nodes"])


def test_edge_weights_count_messages_where_the_pair_co_occurs(database):
    database.create_conversation("conv_0040", "2026-11-05T19:00:00Z")
    for minute in range(3):
        add_scammer_message(
            database,
            "conv_0040",
            f"Inspector Sharma, transfer to sharma.verify@fakebank. Attempt {minute}.",
            [
                {"type": "alias", "value": "inspector sharma"},
                {"type": "upi", "value": "sharma.verify@fakebank"},
            ],
            f"2026-11-05T19:0{minute}:00Z",
        )

    network = database.get_network()
    edge = next(edge for edge in network["edges"] if edge["relation"] == "uses_upi")
    assert edge["weight"] == 3


def test_conversation_history_round_trip_and_idempotent_end(database):
    database.create_conversation("conv_0050", "2026-11-06T10:40:00Z", persona="ajji")
    database.add_message(
        "conv_0050", "ajji", "Hello? Who is speaking?", "2026-11-06T10:40:00Z"
    )
    database.add_message(
        "conv_0050",
        "scammer",
        "Madam, this is Inspector Sharma from CBI.",
        "2026-11-06T10:42:00Z",
        script_stage="intro_threat",
        memory_enabled=False,
    )

    history = database.get_conversation("conv_0050")
    assert history is not None
    assert history["conversation_id"] == "conv_0050"
    assert history["persona"] == "ajji"
    assert history["started_at"] == "2026-11-06T10:40:00Z"
    assert history["ended_at"] is None
    assert [message["sender"] for message in history["messages"]] == ["ajji", "scammer"]

    summary = {"aliases": ["inspector sharma"], "tactics": ["urgency"]}
    assert database.end_conversation("conv_0050", "2026-11-06T10:55:00Z", summary) is True
    first = database.get_conversation("conv_0050")
    assert first["ended_at"] == "2026-11-06T10:55:00Z"
    assert database.get_summary("conv_0050") == summary

    # A second end must not move the timestamp or replace the summary.
    assert database.end_conversation("conv_0050", "2026-11-06T11:30:00Z", {"aliases": []}) is True
    second = database.get_conversation("conv_0050")
    assert second["ended_at"] == "2026-11-06T10:55:00Z"
    assert database.get_summary("conv_0050") == summary

    assert database.end_conversation("conv_missing") is False
    assert database.get_conversation("conv_missing") is None


def test_stats_follow_api_md(database):
    database.create_conversation("conv_0060", "2026-11-06T09:00:00Z")
    add_scammer_message(
        database,
        "conv_0060",
        "Inspector Sharma. Case DL/4410. Call 5550142233.",
        [
            {"type": "alias", "value": "inspector sharma"},
            {"type": "case_number", "value": "DL/4410"},
            {"type": "phone", "value": "5550142233"},
        ],
        "2026-11-06T09:01:00Z",
    )
    add_scammer_message(
        database,
        "conv_0060",
        "Transfer to sharma.verify@fakebank.",
        [{"type": "upi", "value": "sharma.verify@fakebank"}],
        "2026-11-06T09:02:00Z",
    )
    database.end_conversation("conv_0060", "2026-11-06T09:10:00Z")

    database.create_conversation("conv_0061", "2026-11-06T09:20:00Z")
    add_scammer_message(
        database,
        "conv_0061",
        "Officer Verma. Same account sharma.verify@fakebank.",
        [
            {"type": "alias", "value": "officer verma"},
            {"type": "upi", "value": "sharma.verify@fakebank"},
        ],
        "2026-11-06T09:21:00Z",
    )

    database.record_contradiction(
        "conv_0061",
        {
            "kind": "case_number_changed",
            "claim_now": "Case DL/4410",
            "claim_before": "Case MH/2291",
            "source_conversation_id": "conv_0060",
            "severity": "high",
        },
        created_at="2026-11-06T09:21:00Z",
    )
    # The same flag in the same conversation must not double count.
    database.record_contradiction(
        "conv_0061",
        {
            "kind": "case_number_changed",
            "claim_now": "Case DL/4410",
            "claim_before": "Case MH/2291",
            "source_conversation_id": "conv_0060",
            "severity": "high",
        },
    )

    stats = database.get_stats()
    assert stats == {
        "conversations": 2,
        "total_minutes_wasted_estimate": 2,  # 3 scammer turns * 45s = 2.25 min
        "minutes_is_estimate": True,
        "unique_aliases": 2,
        "unique_upi": 1,
        "unique_phones": 1,
        "rings_detected": 1,  # Sharma and Verma share one UPI
        "contradictions_caught": 1,
        "memories_in_bank": 4,  # 3 scammer messages + 1 ended conversation
    }


def test_empty_database_returns_empty_network_and_zeroed_stats(database):
    assert database.get_network() == {"nodes": [], "edges": []}

    stats = database.get_stats()
    assert stats["conversations"] == 0
    assert stats["total_minutes_wasted_estimate"] == 0
    assert stats["rings_detected"] == 0
    assert stats["memories_in_bank"] == 0


def test_reset_db_drops_all_rows_and_recreates_tables(database):
    database.create_conversation("conv_0001", "2026-11-06T10:00:00Z")
    message_id = database.add_message(
        "conv_0001", "scammer", "Inspector Sharma.", "2026-11-06T10:01:00Z"
    )
    database.upsert_iocs(
        "conv_0001",
        message_id,
        [{"type": "alias", "value": "inspector sharma"}],
        seen_at="2026-11-06T10:01:00Z",
    )
    database.end_conversation("conv_0001", "2026-11-06T10:10:00Z", {"aliases": ["inspector sharma"]})

    database.reset_db()

    assert database.get_network() == {"nodes": [], "edges": []}
    assert database.get_conversation("conv_0001") is None
    stats = database.get_stats()
    assert stats["conversations"] == 0
    assert stats["unique_aliases"] == 0
    assert stats["contradictions_caught"] == 0
