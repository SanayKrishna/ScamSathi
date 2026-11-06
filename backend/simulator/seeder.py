"""Drive the seed conversations through the running HTTP API (B6).

Used by:
- `POST /demo/seed` (background thread inside the backend)
- `scripts`/`simulator/run_seed.py` (CLI before the demo)
"""

from __future__ import annotations

import logging
import random
import time
from typing import Any, Callable

import httpx

from simulator.scammer import build_context, load_rings, next_line

logger = logging.getLogger("scamsathi.seeder")

STAGE_BASE = ["intro_threat", "fake_case_number", "video_call_demand", "isolation"]
STAGE_EXTRAS = [
    "verification_transfer",
    "isolation",
    "fake_case_number",
    "video_call_demand",
]


class SeedApiError(RuntimeError):
    pass


class SeedApi:
    """Small HTTP client for the endpoints the seeder needs."""

    def __init__(self, base_url: str, timeout: float = 120.0) -> None:
        self.client = httpx.Client(base_url=base_url.rstrip("/"), timeout=timeout)

    def close(self) -> None:
        self.client.close()

    def __enter__(self) -> "SeedApi":
        return self

    def __exit__(self, *_: Any) -> None:
        self.close()

    def _json(self, response: httpx.Response) -> dict[str, Any]:
        if response.status_code >= 400:
            try:
                payload = response.json()
                message = payload.get("error", {}).get("message") or response.text
            except Exception:
                message = response.text
            raise SeedApiError(f"HTTP {response.status_code}: {message}")
        return response.json()

    def create_conversation(self) -> dict[str, Any]:
        return self._json(self.client.post("/conversations", json={"persona": "ajji"}))

    def send(self, conversation_id: str, text: str) -> dict[str, Any]:
        return self._json(
            self.client.post(
                f"/conversations/{conversation_id}/message",
                json={
                    "sender": "scammer",
                    "text": text,
                    "memory_enabled": True,
                },
            )
        )

    def end(self, conversation_id: str) -> dict[str, Any]:
        return self._json(
            self.client.post(f"/conversations/{conversation_id}/end")
        )

    def reset(self) -> dict[str, Any]:
        return self._json(
            self.client.post("/demo/reset", json={"confirm": "RESET"})
        )


def build_stage_plan(turns: int, rng: random.Random) -> list[str]:
    """Progress through the scam, ending on the money ask."""
    turns = max(5, min(12, turns))
    middle = [rng.choice(STAGE_EXTRAS) for _ in range(turns - 5)]
    return [*STAGE_BASE, *middle, "verification_transfer"]


def _conversation_config(
    rings: list[dict[str, Any]],
    index: int,
    ring_use: dict[str, int],
    rng: random.Random,
) -> tuple[dict[str, Any], dict[str, Any], dict[str, str]]:
    ring = rings[index % len(rings)]
    use = ring_use.get(ring["id"], 0) + 1
    ring_use[ring["id"]] = use

    alias_entry = ring["aliases"][(use - 1) % len(ring["aliases"])]

    case_numbers = alias_entry["case_numbers"]
    if len(case_numbers) > 1 and (use % 3 == 0 or rng.random() < 0.2):
        case_number = case_numbers[1]
    else:
        case_number = case_numbers[0]

    agency = alias_entry["agency"]
    alternates = alias_entry.get("agency_alternates") or []
    if alternates and (use % 4 == 0 or rng.random() < 0.15):
        agency = alternates[0]

    upis = ring["upis"]
    upi = upis[0] if len(upis) == 1 or use % 3 != 0 else upis[1]

    phones = ring["phones"]
    phone = phones[0] if len(phones) == 1 or use % 4 != 0 else phones[1]

    amount = rng.choice(ring["amounts"])
    context = build_context(alias_entry, agency, case_number, upi, phone, amount)
    return ring, alias_entry, context


def run_seed(
    api: SeedApi,
    conversations: int = 20,
    use_llm: bool = True,
    on_progress: Callable[[], None] | None = None,
    delay: float = 0.0,
    seed: int = 42,
) -> None:
    """Run the whole simulator. Raises on the first unrecoverable API error."""
    rings = load_rings()
    rng = random.Random(seed)
    ring_use: dict[str, int] = {}

    for index in range(conversations):
        ring, _alias_entry, context = _conversation_config(rings, index, ring_use, rng)
        turns = rng.randint(6, 12)
        stage_plan = build_stage_plan(turns, rng)

        created = api.create_conversation()
        conversation_id = created["conversation_id"]
        history: list[str] = []

        for stage in stage_plan:
            text = next_line(ring, stage, context, history, rng, use_llm=use_llm)
            response = api.send(conversation_id, text)
            reply = (response.get("reply") or {}).get("text") or ""
            history.append(f"scammer: {text}")
            if reply:
                history.append(f"victim: {reply}")
            if delay > 0:
                time.sleep(delay)

        api.end(conversation_id)
        logger.info(
            "seeded %s (%s/%s) ring=%s alias=%s turns=%s",
            conversation_id,
            index + 1,
            conversations,
            ring["id"],
            context["alias"],
            len(stage_plan),
        )
        if on_progress is not None:
            on_progress()
