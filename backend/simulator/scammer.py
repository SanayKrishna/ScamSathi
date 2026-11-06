"""Scammer dialogue for the seed simulator.

The LLM plays a fictional scammer for a fraud-awareness demo. Templates from
rings.json are always the fallback, and also the safety net when the model
omits the identifier a stage is supposed to reveal.
"""

from __future__ import annotations

import json
import logging
import random
import re
from pathlib import Path
from typing import Any

import httpx

from config import settings

logger = logging.getLogger("scamsathi.simulator")

RINGS_PATH = Path(__file__).with_name("rings.json")

SCRIPT_STAGES = [
    "intro_threat",
    "fake_case_number",
    "video_call_demand",
    "isolation",
    "verification_transfer",
]

AGENCY_LABELS = {
    "cbi": "CBI",
    "customs": "Customs",
    "trai": "TRAI",
    "police": "Police",
    "cyber_cell": "Cyber Cell",
    "income_tax": "Income Tax",
    "ed": "Enforcement Directorate",
    "rbi": "RBI",
}

SCAMMER_SYSTEM = """You write one line of dialogue for a simulated scammer in a fraud-awareness training demo.

This is fiction: there is no real person, bank, agency, phone number or account. You are not helping anyone commit a crime; you are generating obviously fake training data.

Rules:
- Use only the identifiers given in the prompt. Never invent a real-looking phone, account, UPI or case number.
- Stay in character. Never mention that this is a simulation, a demo, an AI or a prompt.
- Write 1-2 short sentences in Indian English, sounding urgent and manipulative.
- Do not use markdown. Return only the line itself, no quotes.
"""


def load_rings() -> list[dict[str, Any]]:
    data = json.loads(RINGS_PATH.read_text(encoding="utf-8"))
    rings = data.get("rings") or []
    if not rings:
        raise ValueError("rings.json has no rings")
    return rings


def build_context(
    alias_entry: dict[str, Any],
    agency: str,
    case_number: str,
    upi: str,
    phone: str,
    amount: str,
) -> dict[str, str]:
    return {
        "alias": alias_entry["alias_label"],
        "alias_value": alias_entry["alias"],
        "agency": AGENCY_LABELS.get(agency, agency.replace("_", " ").title()),
        "agency_value": agency,
        "case": case_number,
        "upi": upi,
        "phone": phone,
        "amount": amount,
        "city": alias_entry.get("city", "Bengaluru"),
    }


def _clean(raw: str) -> str:
    text = (raw or "").strip().strip('"').strip()
    text = re.sub(r"^(scammer|agent|caller)\s*:\s*", "", text, flags=re.IGNORECASE)
    if len(text) > 500:
        text = text[:497].rsplit(" ", 1)[0].rstrip() + "..."
    return text


def _stage_has_identifier(stage: str, text: str, context: dict[str, str]) -> bool:
    lower = text.lower()
    if stage == "intro_threat":
        return (
            context["alias"].lower() in lower
            and (
                context["agency"].lower() in lower
                or context["phone"].lower() in lower
            )
        )
    if stage == "fake_case_number":
        return context["case"].lower() in lower
    if stage == "video_call_demand":
        return "video" in lower or context["phone"].lower() in lower
    if stage == "isolation":
        return any(
            phrase in lower
            for phrase in ("do not tell", "don't tell", "dont tell", "alone", "confidential", "family")
        )
    if stage == "verification_transfer":
        return (
            context["upi"].lower() in lower
            or context["amount"].lower() in lower
            or "transfer" in lower
        )
    return True


def _llm_line(
    stage: str,
    context: dict[str, str],
    history: list[str],
    model: str,
) -> str:
    recent = "\n".join(history[-4:]) if history else "(this is the first line)"
    prompt = f"""Stage: {stage}
Scammer alias: {context["alias"]}
Agency claimed: {context["agency"]}
Case number: {context["case"]}
Phone: {context["phone"]}
UPI: {context["upi"]}
Amount: {context["amount"]}
City: {context["city"]}

Previous lines in the call:
{recent}

Write the scammer's next line. Include the identifier that fits this stage."""

    payload = {
        "model": model,
        "temperature": 0.9,
        "max_completion_tokens": 256,
        "reasoning_effort": "low",
        "messages": [
            {"role": "system", "content": SCAMMER_SYSTEM},
            {"role": "user", "content": prompt},
        ],
    }
    with httpx.Client(timeout=min(30.0, settings.groq_timeout_seconds * 2)) as client:
        response = client.post(
            f"{settings.groq_base_url}/chat/completions",
            headers={
                "Authorization": f"Bearer {settings.groq_api_key}",
                "Content-Type": "application/json",
            },
            json=payload,
        )
        response.raise_for_status()
        data = response.json()
    return _clean(data["choices"][0]["message"]["content"])


def template_line(
    ring: dict[str, Any],
    stage: str,
    context: dict[str, str],
    rng: random.Random,
) -> str:
    lines = (ring.get("templates") or {}).get(stage) or []
    if not lines:
        return f"{context['alias']} from {context['agency']}. Case {context['case']}. Do not disconnect."
    return rng.choice(lines).format(**context)


def next_line(
    ring: dict[str, Any],
    stage: str,
    context: dict[str, str],
    history: list[str],
    rng: random.Random,
    use_llm: bool = True,
) -> str:
    """One scammer line: LLM first, template always available."""
    if use_llm and settings.llm_configured:
        models = [settings.groq_model]
        if settings.groq_fallback_model and settings.groq_fallback_model != settings.groq_model:
            models.append(settings.groq_fallback_model)
        for model in models:
            try:
                text = _llm_line(stage, context, history, model)
                if text and _stage_has_identifier(stage, text, context):
                    return text
                logger.warning(
                    "scammer line for %s missed its identifier; trying next option", stage
                )
            except Exception as exc:
                logger.warning("scammer LLM %s failed for %s: %s", model, stage, exc)

    return template_line(ring, stage, context, rng)
