from __future__ import annotations

import random
from dataclasses import replace

import pytest

from simulator import scammer
from simulator.scammer import build_context, load_rings, next_line
from simulator.seeder import build_stage_plan, run_seed


class FakeSeedApi:
    def __init__(self) -> None:
        self.created: list[str] = []
        self.sent: list[tuple[str, str]] = []
        self.ended: list[str] = []
        self._counter = 0

    def create_conversation(self) -> dict:
        self._counter += 1
        conversation_id = f"conv_{self._counter:04d}"
        self.created.append(conversation_id)
        return {"conversation_id": conversation_id}

    def send(self, conversation_id: str, text: str) -> dict:
        self.sent.append((conversation_id, text))
        return {"reply": {"text": "Aiyyo, sir, say that again slowly?"}}

    def end(self, conversation_id: str) -> dict:
        self.ended.append(conversation_id)
        return {"conversation_id": conversation_id}


def test_rings_are_fictional_and_complete():
    rings = load_rings()
    assert len(rings) == 4
    assert [ring["id"] for ring in rings] == ["ring_1", "ring_2", "ring_3", "ring_4"]

    for ring in rings:
        assert 2 <= len(ring["aliases"]) <= 3
        assert 1 <= len(ring["upis"]) <= 2
        assert 1 <= len(ring["phones"]) <= 2
        assert set(ring["templates"]) == {
            "intro_threat",
            "fake_case_number",
            "video_call_demand",
            "isolation",
            "verification_transfer",
        }
        for stage_lines in ring["templates"].values():
            assert len(stage_lines) >= 2
        for upi in ring["upis"]:
            assert upi.endswith("@fakebank")
        for phone in ring["phones"]:
            assert phone.startswith("555")
        for alias in ring["aliases"]:
            assert len(alias["case_numbers"]) >= 2
            assert alias["alias"] == alias["alias_label"].lower()


def test_stage_plan_progresses_and_ends_on_the_money_ask():
    rng = random.Random(1)
    for turns, expected in [(6, 6), (9, 9), (12, 12), (3, 5), (20, 12)]:
        plan = build_stage_plan(turns, rng)
        assert len(plan) == expected
        assert plan[0] == "intro_threat"
        assert plan[1] == "fake_case_number"
        assert plan[-1] == "verification_transfer"


def test_run_seed_uses_all_four_rings_and_ends_every_chat():
    api = FakeSeedApi()
    progress: list[int] = []
    run_seed(
        api,
        conversations=4,
        use_llm=False,
        on_progress=lambda: progress.append(len(progress) + 1),
        seed=7,
    )

    assert api.created == ["conv_0001", "conv_0002", "conv_0003", "conv_0004"]
    assert api.ended == api.created
    assert progress == [1, 2, 3, 4]

    by_conversation: dict[str, list[str]] = {cid: [] for cid in api.created}
    for conversation_id, text in api.sent:
        by_conversation[conversation_id].append(text)

    for conversation_id in api.created:
        texts = by_conversation[conversation_id]
        assert 6 <= len(texts) <= 12

    first, second, third, fourth = (by_conversation[cid] for cid in api.created)
    assert "Inspector Sharma" in first[0]
    assert "CBI" in first[0]
    assert "DL/4410" in first[1]
    assert "sharma.verify@fakebank" in first[-1] or "Rs 49,000" in first[-1]

    assert "Customs Officer Rao" in second[0]
    assert "KA/7788" in second[1]

    assert "TRAI Officer Nair" in third[0]
    assert "KA/3311" in third[1]

    assert "Sub-Inspector Patil" in fourth[0]
    assert "MH/9912" in fourth[1]


def test_template_fills_every_placeholder():
    ring = load_rings()[0]
    context = build_context(
        ring["aliases"][0],
        "cbi",
        "DL/4410",
        "sharma.verify@fakebank",
        "5550142233",
        "Rs 49,000",
    )
    for stage in ring["templates"]:
        line = scammer.template_line(ring, stage, context, random.Random(1))
        assert "{" not in line
        assert "}" not in line


def test_next_line_falls_back_when_llm_misses_the_identifier(monkeypatch):
    ring = load_rings()[0]
    context = build_context(
        ring["aliases"][0],
        "cbi",
        "DL/4410",
        "sharma.verify@fakebank",
        "5550142233",
        "Rs 49,000",
    )
    monkeypatch.setattr(scammer, "_llm_line", lambda *args, **kwargs: "Please cooperate, madam.")
    monkeypatch.setattr(
        scammer, "settings", replace(scammer.settings, groq_api_key="test-key")
    )

    line = next_line(
        ring,
        "fake_case_number",
        context,
        history=[],
        rng=random.Random(1),
        use_llm=True,
    )

    assert "DL/4410" in line


def test_next_line_accepts_a_valid_llm_line(monkeypatch):
    ring = load_rings()[0]
    context = build_context(
        ring["aliases"][0],
        "cbi",
        "DL/4410",
        "sharma.verify@fakebank",
        "5550142233",
        "Rs 49,000",
    )
    valid = "Madam, your case number is DL/4410. Do not disconnect."
    monkeypatch.setattr(scammer, "_llm_line", lambda *args, **kwargs: valid)
    monkeypatch.setattr(
        scammer, "settings", replace(scammer.settings, groq_api_key="test-key")
    )

    line = next_line(
        ring,
        "fake_case_number",
        context,
        history=[],
        rng=random.Random(1),
        use_llm=True,
    )

    assert line == valid


def test_unknown_stage_template_is_safe():
    ring = load_rings()[0]
    context = build_context(
        ring["aliases"][0],
        "cbi",
        "DL/4410",
        "sharma.verify@fakebank",
        "5550142233",
        "Rs 49,000",
    )
    line = scammer.template_line(ring, "not_a_stage", context, random.Random(1))
    assert "Inspector Sharma" in line
    assert "DL/4410" in line
