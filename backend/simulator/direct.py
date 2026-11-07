"""Direct seeder: populate SQLite and Hindsight without HTTP or Groq calls.

Use this on a free Groq tier. The normal seeder drives the live API, which uses
Groq for IOC extraction and Ajji's replies; twenty conversations can exhaust an
8k TPM limit. This mode writes the same fictional ring data straight into the
database and retains the raw messages in Hindsight, so the demo has a full graph,
stats and memory bank without spending a single LLM token.

Live demo turns still use the real agent.
"""

from __future__ import annotations

import logging
import random
from datetime import datetime, timedelta, timezone
from typing import Any, Callable

import agent
import db
import memory
from contradictions import find_contradictions
from simulator.scammer import load_rings, template_line
from simulator.seeder import _conversation_config, build_stage_plan

logger = logging.getLogger("scamsathi.direct_seed")

BASE_TIME = datetime(2026, 11, 1, 10, 0, tzinfo=timezone.utc)
OPENING = "Hello? Who is speaking? My grandson usually picks up the phone."


def _iso(value: datetime) -> str:
    return value.isoformat(timespec="seconds").replace("+00:00", "Z")


def _iocs_for_stage(stage: str, context: dict[str, str]) -> list[dict[str, str]]:
    iocs = [
        {"type": "alias", "value": context["alias_value"]},
        {"type": "agency_claimed", "value": context["agency_value"]},
        {"type": "script_stage", "value": stage},
    ]
    if stage in ("fake_case_number", "verification_transfer"):
        iocs.append({"type": "case_number", "value": context["case"]})
    if stage in ("intro_threat", "video_call_demand"):
        iocs.append({"type": "phone", "value": context["phone"]})
    if stage == "verification_transfer":
        iocs.append({"type": "upi", "value": context["upi"]})
    return iocs


def run_seed_direct(
    conversations: int = 20,
    on_progress: Callable[[], None] | None = None,
    seed: int = 42,
) -> None:
    """Populate the database and Hindsight with the four rings, no LLM calls."""
    if memory.is_configured():
        memory.ensure_bank()

    rings = load_rings()
    rng = random.Random(seed)
    ring_use: dict[str, int] = {}

    for index in range(conversations):
        ring, _alias_entry, context = _conversation_config(rings, index, ring_use, rng)
        turns = rng.randint(6, 12)
        plan = build_stage_plan(turns, rng)

        started = BASE_TIME + timedelta(minutes=index * 20)
        conversation_id = db.next_conversation_id()
        db.create_conversation(conversation_id, started_at=_iso(started), persona="ajji")
        db.add_message(conversation_id, "ajji", OPENING, created_at=_iso(started))

        scammer_texts: list[str] = []
        for turn, stage in enumerate(plan):
            at = started + timedelta(minutes=turn + 1)
            text = template_line(ring, stage, context, rng)
            message_id = db.add_message(
                conversation_id,
                "scammer",
                text,
                created_at=_iso(at),
                script_stage=stage,
            )
            iocs = _iocs_for_stage(stage, context)
            db.upsert_iocs(conversation_id, message_id, iocs, seen_at=_iso(at))

            for flag in find_contradictions(iocs, conversation_id):
                db.record_contradiction(
                    conversation_id,
                    flag,
                    message_id=message_id,
                    created_at=_iso(at),
                )

            if memory.is_configured():
                memory.retain_message(
                    text,
                    conversation_id,
                    stage,
                    timestamp=_iso(at),
                )
            scammer_texts.append(text)

        ended_at = started + timedelta(minutes=len(plan) + 2)
        summary = db.conversation_summary_parts(conversation_id)
        summary["tactics"] = agent._tactics(scammer_texts)
        db.end_conversation(conversation_id, ended_at=_iso(ended_at), summary=summary)
        if memory.is_configured():
            memory.retain_summary(summary, conversation_id)

        logger.info(
            "direct seeded %s ring=%s alias=%s turns=%s",
            conversation_id,
            ring["id"],
            context["alias"],
            len(plan),
        )
        if on_progress is not None:
            on_progress()
