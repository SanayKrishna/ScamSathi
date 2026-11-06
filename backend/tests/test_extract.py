from __future__ import annotations

import json
from dataclasses import replace

import pytest

import extract


@pytest.fixture
def configured(monkeypatch):
    """Pretend a Groq key is present without touching the real environment."""
    settings = replace(extract.settings, groq_api_key="test-key")
    monkeypatch.setattr(extract, "settings", settings)
    return settings


def _values(iocs) -> set[tuple[str, str]]:
    return {(ioc.type, ioc.value) for ioc in iocs}


# Six realistic simulated scammer messages, covering every IOC type. Each
# fake model reply is what the real LLM is expected to return.
CASES = [
    {
        "name": "CBI alias, agency and case number (Hinglish)",
        "text": (
            "Madam, main Inspector Sharma bol raha hoon CBI se. Aapka Aadhaar "
            "money laundering mein link hai. Case number DL/4410."
        ),
        "llm": {
            "iocs": [
                {"type": "alias", "value": "Inspector Sharma"},
                {"type": "agency_claimed", "value": "Central Bureau of Investigation"},
                {"type": "case_number", "value": "dl/4410"},
            ],
            "script_stage": "fake_case_number",
        },
        "expected": {
            ("alias", "inspector sharma"),
            ("agency_claimed", "cbi"),
            ("case_number", "DL/4410"),
            ("script_stage", "fake_case_number"),
        },
        "stage": "fake_case_number",
    },
    {
        "name": "UPI handle and a payment demand",
        "text": (
            "Your account is flagged. Pay the penalty to "
            "Sharma.Verify@FakeBank right now or the account is frozen."
        ),
        "llm": {
            "iocs": [{"type": "upi", "value": "Sharma.Verify@FakeBank"}],
            "script_stage": "verification_transfer",
        },
        "expected": {
            ("upi", "sharma.verify@fakebank"),
            ("script_stage", "verification_transfer"),
        },
        "stage": "verification_transfer",
    },
    {
        "name": "Customs officer with a phone number",
        "text": (
            "This is Officer Verma from the Customs Department. Call me back "
            "on +91 555-014-2233 before noon."
        ),
        "llm": {
            "iocs": [
                {"type": "alias", "value": "Officer Verma"},
                {"type": "agency_claimed", "value": "Customs Department"},
                {"type": "phone", "value": "+91 555-014-2233"},
            ],
            "script_stage": "intro_threat",
        },
        "expected": {
            ("alias", "officer verma"),
            ("agency_claimed", "customs"),
            ("phone", "5550142233"),
            ("script_stage", "intro_threat"),
        },
        "stage": "intro_threat",
    },
    {
        "name": "Isolation instruction with no identifiers",
        "text": "Do not tell your son or daughter. Stay alone in a room and wait for our call.",
        "llm": {"iocs": [], "script_stage": "isolation"},
        "expected": {("script_stage", "isolation")},
        "stage": "isolation",
    },
    {
        "name": "Video call demand",
        "text": "Open Skype now. We need a video call to verify your identity, madam.",
        "llm": {"iocs": [], "script_stage": "video_call_demand"},
        "expected": {("script_stage", "video_call_demand")},
        "stage": "video_call_demand",
    },
    {
        "name": "TRAI SIM block with phone and case (Hinglish)",
        "text": (
            "TRAI will block your SIM today. Call 555-019-8844 and quote "
            "complaint KA/7788 immediately."
        ),
        "llm": {
            "iocs": [
                {"type": "agency_claimed", "value": "TRAI"},
                {"type": "phone", "value": "555-019-8844"},
                {"type": "case_number", "value": "KA/7788"},
            ],
            "script_stage": "intro_threat",
        },
        "expected": {
            ("agency_claimed", "trai"),
            ("phone", "5550198844"),
            ("case_number", "KA/7788"),
            ("script_stage", "intro_threat"),
        },
        "stage": "intro_threat",
    },
]


@pytest.mark.parametrize("case", CASES, ids=[case["name"] for case in CASES])
def test_extracts_realistic_messages(configured, monkeypatch, case):
    monkeypatch.setattr(extract, "_call_groq", lambda text, model: json.dumps(case["llm"]))

    iocs, stage, degraded = extract.extract_iocs(case["text"])

    assert degraded is False
    assert stage == case["stage"]
    assert _values(iocs) == case["expected"]


def test_invalid_json_retries_the_fallback_model(configured, monkeypatch):
    calls: list[str] = []

    def fake(text: str, model: str) -> str:
        calls.append(model)
        if model == configured.groq_model:
            return "this is not json"
        return json.dumps(
            {
                "iocs": [{"type": "phone", "value": "555-010-0000"}],
                "script_stage": "intro_threat",
            }
        )

    monkeypatch.setattr(extract, "_call_groq", fake)

    iocs, stage, degraded = extract.extract_iocs("Call 555-010-0000.")

    assert calls == [configured.groq_model, configured.groq_fallback_model]
    assert degraded is False
    assert ("phone", "5550100000") in _values(iocs)
    assert stage == "intro_threat"


def test_both_models_failing_uses_regex(configured, monkeypatch):
    def boom(text: str, model: str) -> str:
        raise RuntimeError("groq is down")

    monkeypatch.setattr(extract, "_call_groq", boom)

    text = "Pay to sharma.verify@fakebank. Call 555-014-2233. Case DL/4410."
    iocs, stage, degraded = extract.extract_iocs(text)

    values = _values(iocs)
    assert degraded is True
    assert ("upi", "sharma.verify@fakebank") in values
    assert ("phone", "5550142233") in values
    assert ("case_number", "DL/4410") in values
    assert stage == "verification_transfer"


def test_missing_api_key_uses_regex_without_calling_groq(monkeypatch):
    monkeypatch.setattr(extract, "settings", replace(extract.settings, groq_api_key=""))

    def should_not_run(text: str, model: str) -> str:
        raise AssertionError("Groq must not be called without a key")

    monkeypatch.setattr(extract, "_call_groq", should_not_run)

    iocs, stage, degraded = extract.extract_iocs("Transfer to mule@fakebank tonight.")
    assert degraded is True
    assert ("upi", "mule@fakebank") in _values(iocs)
    assert stage == "verification_transfer"


def test_code_fenced_json_is_accepted(configured, monkeypatch):
    payload = {
        "iocs": [{"type": "alias", "value": "Sub-Inspector Rao"}],
        "script_stage": "intro_threat",
    }
    monkeypatch.setattr(
        extract,
        "_call_groq",
        lambda text, model: f"```json\n{json.dumps(payload)}\n```",
    )

    iocs, _, degraded = extract.extract_iocs("Sub-Inspector Rao speaking.")
    assert degraded is False
    assert ("alias", "sub-inspector rao") in _values(iocs)


def test_unknown_ioc_types_are_dropped(configured, monkeypatch):
    payload = {
        "iocs": [
            {"type": "email", "value": "scammer@example.com"},
            {"type": "alias", "value": "Officer Rao"},
        ],
        "script_stage": None,
    }
    monkeypatch.setattr(extract, "_call_groq", lambda text, model: json.dumps(payload))

    iocs, stage, degraded = extract.extract_iocs("Officer Rao here.")
    assert degraded is False
    assert ("alias", "officer rao") in _values(iocs)
    assert all(ioc.type != "email" for ioc in iocs)
    assert stage == "intro_threat"


def test_stage_ioc_inside_iocs_is_honoured_and_deduplicated(configured, monkeypatch):
    payload = {
        "iocs": [
            {"type": "script_stage", "value": "isolation"},
            {"type": "script_stage", "value": "isolation"},
        ],
        "script_stage": None,
    }
    monkeypatch.setattr(extract, "_call_groq", lambda text, model: json.dumps(payload))

    iocs, stage, _ = extract.extract_iocs("Stay alone. Do not tell anyone.")
    assert stage == "isolation"
    assert [ioc.value for ioc in iocs if ioc.type == "script_stage"] == ["isolation"]


@pytest.mark.parametrize(
    ("ioc_type", "raw", "expected"),
    [
        ("alias", "  Inspector   SHARMA, ", "inspector sharma"),
        ("agency_claimed", "Central Bureau of Investigation", "cbi"),
        ("agency_claimed", "CBI Mumbai", "cbi"),
        ("agency_claimed", "TRAI Delhi", "trai"),
        ("agency_claimed", "Mumbai Police", "police"),
        ("phone", "+91 555-014-2233", "5550142233"),
        ("phone", "05550142233", "5550142233"),
        ("case_number", "dl / 4410", "DL/4410"),
        ("upi", " Sharma.Verify@FakeBank ", "sharma.verify@fakebank"),
        ("upi", "not-a-upi", None),
        ("phone", "call me", None),
    ],
)
def test_normalise_value(ioc_type, raw, expected):
    assert extract.normalise_value(ioc_type, raw) == expected


def test_empty_text_is_not_degraded(configured, monkeypatch):
    monkeypatch.setattr(extract, "_call_groq", lambda text, model: "{}")
    assert extract.extract_iocs("   ") == ([], None, False)


def test_extract_iocs_skips_groq_with_a_tiny_budget(configured, monkeypatch):
    calls = []

    def fake(text, model, **kwargs):
        calls.append((text, model, kwargs))
        return "{}"

    monkeypatch.setattr(extract, "_call_groq", fake)

    iocs, stage, degraded = extract.extract_iocs("Hello", timeout=0.1)

    assert calls == []
    assert degraded is True


def test_extract_iocs_passes_remaining_budget_to_groq(configured, monkeypatch):
    seen: dict = {}

    def fake(text, model, **kwargs):
        seen.update(kwargs)
        return json.dumps({"iocs": [], "script_stage": "intro_threat"})

    monkeypatch.setattr(extract, "_call_groq", fake)

    iocs, stage, degraded = extract.extract_iocs("Hello", timeout=2.0)

    assert degraded is False
    assert 0 < seen["timeout"] <= 2.0
    assert seen["deadline"] > 0
