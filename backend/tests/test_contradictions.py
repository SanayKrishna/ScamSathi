from __future__ import annotations

from dataclasses import replace

import pytest

import db
from contradictions import find_contradictions
from extract import Ioc


@pytest.fixture
def database(tmp_path, monkeypatch):
    monkeypatch.setattr(
        db,
        "settings",
        replace(db.settings, db_path=tmp_path / "contradictions.db"),
    )
    db.init_db()
    return db


def seed(database, conversation_id: str, started_at: str, iocs: list[dict[str, str]]):
    database.create_conversation(conversation_id, started_at)
    message_id = database.add_message(
        conversation_id,
        "scammer",
        "Simulated scammer message.",
        created_at=started_at,
    )
    database.upsert_iocs(conversation_id, message_id, iocs, seen_at=started_at)
    return message_id


def test_case_number_changed(database):
    seed(
        database,
        "conv_0001",
        "2026-11-05T10:00:00Z",
        [
            {"type": "alias", "value": "inspector sharma"},
            {"type": "case_number", "value": "MH/2291"},
        ],
    )
    seed(
        database,
        "conv_0002",
        "2026-11-05T11:00:00Z",
        [
            {"type": "alias", "value": "inspector sharma"},
            {"type": "case_number", "value": "DL/4410"},
        ],
    )

    flags = find_contradictions(
        [
            Ioc(type="alias", value="inspector sharma"),
            Ioc(type="case_number", value="DL/4410"),
        ],
        "conv_0002",
    )

    assert flags == [
        {
            "kind": "case_number_changed",
            "claim_now": "Case DL/4410",
            "claim_before": "Case MH/2291",
            "source_conversation_id": "conv_0001",
            "severity": "high",
        }
    ]


def test_alias_shares_upi(database):
    seed(
        database,
        "conv_0001",
        "2026-11-05T10:00:00Z",
        [
            {"type": "alias", "value": "officer verma"},
            {"type": "upi", "value": "sharma.verify@fakebank"},
        ],
    )
    seed(
        database,
        "conv_0002",
        "2026-11-05T11:00:00Z",
        [
            {"type": "alias", "value": "inspector sharma"},
            {"type": "upi", "value": "sharma.verify@fakebank"},
        ],
    )

    flags = find_contradictions(
        [
            Ioc(type="alias", value="inspector sharma"),
            Ioc(type="upi", value="sharma.verify@fakebank"),
        ],
        "conv_0002",
    )

    assert flags == [
        {
            "kind": "alias_shares_upi",
            "claim_now": "Inspector Sharma used sharma.verify@fakebank",
            "claim_before": "Officer Verma used sharma.verify@fakebank",
            "source_conversation_id": "conv_0001",
            "severity": "high",
        }
    ]


def test_alias_shares_phone(database):
    seed(
        database,
        "conv_0001",
        "2026-11-05T10:00:00Z",
        [
            {"type": "alias", "value": "officer verma"},
            {"type": "phone", "value": "5550142233"},
        ],
    )
    seed(
        database,
        "conv_0002",
        "2026-11-05T11:00:00Z",
        [
            {"type": "alias", "value": "inspector sharma"},
            {"type": "phone", "value": "5550142233"},
        ],
    )

    flags = find_contradictions(
        [
            Ioc(type="alias", value="inspector sharma"),
            Ioc(type="phone", value="5550142233"),
        ],
        "conv_0002",
    )

    assert flags == [
        {
            "kind": "alias_shares_phone",
            "claim_now": "Inspector Sharma used 5550142233",
            "claim_before": "Officer Verma used 5550142233",
            "source_conversation_id": "conv_0001",
            "severity": "low",
        }
    ]


def test_agency_changed_for_the_same_alias(database):
    seed(
        database,
        "conv_0001",
        "2026-11-05T10:00:00Z",
        [
            {"type": "alias", "value": "inspector sharma"},
            {"type": "agency_claimed", "value": "cbi"},
        ],
    )
    seed(
        database,
        "conv_0002",
        "2026-11-05T11:00:00Z",
        [
            {"type": "alias", "value": "inspector sharma"},
            {"type": "agency_claimed", "value": "customs"},
        ],
    )

    flags = find_contradictions(
        [
            Ioc(type="alias", value="inspector sharma"),
            Ioc(type="agency_claimed", value="customs"),
        ],
        "conv_0002",
    )

    assert flags == [
        {
            "kind": "agency_changed",
            "claim_now": "Inspector Sharma claims Customs",
            "claim_before": "Inspector Sharma claimed CBI",
            "source_conversation_id": "conv_0001",
            "severity": "low",
        }
    ]


def test_no_contradiction_when_the_story_is_consistent(database):
    same = [
        {"type": "alias", "value": "inspector sharma"},
        {"type": "case_number", "value": "MH/2291"},
        {"type": "upi", "value": "sharma.verify@fakebank"},
        {"type": "phone", "value": "5550142233"},
        {"type": "agency_claimed", "value": "cbi"},
    ]
    seed(database, "conv_0001", "2026-11-05T10:00:00Z", same)
    seed(database, "conv_0002", "2026-11-05T11:00:00Z", same)

    flags = find_contradictions(
        [
            Ioc(type="alias", value="inspector sharma"),
            Ioc(type="case_number", value="MH/2291"),
            Ioc(type="upi", value="sharma.verify@fakebank"),
            Ioc(type="phone", value="5550142233"),
            Ioc(type="agency_claimed", value="cbi"),
        ],
        "conv_0002",
    )

    assert flags == []


def test_current_conversation_is_never_used_against_itself(database):
    database.create_conversation("conv_0001", "2026-11-05T10:00:00Z")
    first = database.add_message(
        "conv_0001",
        "scammer",
        "Inspector Sharma. Case MH/2291.",
        created_at="2026-11-05T10:01:00Z",
    )
    database.upsert_iocs(
        "conv_0001",
        first,
        [
            {"type": "alias", "value": "inspector sharma"},
            {"type": "case_number", "value": "MH/2291"},
        ],
        seen_at="2026-11-05T10:01:00Z",
    )
    second = database.add_message(
        "conv_0001",
        "scammer",
        "Inspector Sharma. Case DL/4410.",
        created_at="2026-11-05T10:05:00Z",
    )
    database.upsert_iocs(
        "conv_0001",
        second,
        [
            {"type": "alias", "value": "inspector sharma"},
            {"type": "case_number", "value": "DL/4410"},
        ],
        seen_at="2026-11-05T10:05:00Z",
    )

    flags = find_contradictions(
        [
            Ioc(type="alias", value="inspector sharma"),
            Ioc(type="case_number", value="DL/4410"),
        ],
        "conv_0001",
    )

    assert flags == []


def test_returns_at_most_three_flags_most_severe_first(database):
    seed(
        database,
        "conv_0001",
        "2026-11-05T10:00:00Z",
        [
            {"type": "alias", "value": "inspector sharma"},
            {"type": "case_number", "value": "MH/2291"},
        ],
    )
    seed(
        database,
        "conv_0002",
        "2026-11-05T10:30:00Z",
        [
            {"type": "alias", "value": "officer verma"},
            {"type": "upi", "value": "sharma.verify@fakebank"},
            {"type": "phone", "value": "5550142233"},
            {"type": "agency_claimed", "value": "cbi"},
        ],
    )
    seed(
        database,
        "conv_0003",
        "2026-11-05T11:00:00Z",
        [
            {"type": "alias", "value": "inspector sharma"},
            {"type": "case_number", "value": "DL/4410"},
            {"type": "upi", "value": "sharma.verify@fakebank"},
            {"type": "phone", "value": "5550142233"},
            {"type": "agency_claimed", "value": "customs"},
        ],
    )

    flags = find_contradictions(
        [
            Ioc(type="alias", value="inspector sharma"),
            Ioc(type="case_number", value="DL/4410"),
            Ioc(type="upi", value="sharma.verify@fakebank"),
            Ioc(type="phone", value="5550142233"),
            Ioc(type="agency_claimed", value="customs"),
        ],
        "conv_0003",
    )

    assert len(flags) == 3
    assert [flag["kind"] for flag in flags] == [
        "case_number_changed",
        "alias_shares_upi",
        "alias_shares_phone",
    ]
    assert flags[0]["severity"] == "high"
    assert flags[1]["severity"] == "high"
    assert flags[2]["severity"] == "low"


def test_agency_changed_for_a_phone_without_an_alias(database):
    seed(
        database,
        "conv_0001",
        "2026-11-05T10:00:00Z",
        [
            {"type": "phone", "value": "5550142233"},
            {"type": "agency_claimed", "value": "cbi"},
        ],
    )
    seed(
        database,
        "conv_0002",
        "2026-11-05T11:00:00Z",
        [
            {"type": "phone", "value": "5550142233"},
            {"type": "agency_claimed", "value": "customs"},
        ],
    )

    flags = find_contradictions(
        [
            Ioc(type="phone", value="5550142233"),
            Ioc(type="agency_claimed", value="customs"),
        ],
        "conv_0002",
    )

    assert flags == [
        {
            "kind": "agency_changed",
            "claim_now": "This caller claims Customs",
            "claim_before": "This caller claimed CBI",
            "source_conversation_id": "conv_0001",
            "severity": "low",
        }
    ]


def test_accepts_dict_iocs_and_ignores_script_stage(database):
    seed(
        database,
        "conv_0001",
        "2026-11-05T10:00:00Z",
        [
            {"type": "alias", "value": "inspector sharma"},
            {"type": "case_number", "value": "MH/2291"},
        ],
    )
    seed(
        database,
        "conv_0002",
        "2026-11-05T11:00:00Z",
        [
            {"type": "alias", "value": "inspector sharma"},
            {"type": "case_number", "value": "DL/4410"},
        ],
    )

    flags = find_contradictions(
        [
            {"type": "alias", "value": "inspector sharma"},
            {"type": "case_number", "value": "DL/4410"},
            {"type": "script_stage", "value": "fake_case_number"},
        ],
        "conv_0002",
    )

    assert len(flags) == 1
    assert flags[0]["kind"] == "case_number_changed"


def test_unknown_conversation_returns_no_flags(database):
    assert (
        find_contradictions(
            [Ioc(type="alias", value="inspector sharma")],
            "conv_missing",
        )
        == []
    )
