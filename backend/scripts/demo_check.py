"""J1: end-to-end demo check against a live, seeded backend.

Run from backend/ with the backend and Hindsight already running:
    .venv\\Scripts\\python scripts\\demo_check.py

The frontend is not needed. The check:
1. GET /health is ok
2. GET /stats shows a seeded bank (>= 15 conversations, >= 3 rings)
3. creates one chat with memory off and one with memory on, same opener
4. asserts memory off has no recall/contradictions and memory on has both
5. prints both replies side by side with timings

Exit non-zero on any failure. Run it after seeding to confirm memory works end to end.
"""

from __future__ import annotations

import argparse
import sys
import textwrap
from itertools import zip_longest
from typing import Any

import httpx

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

OPENER = (
    "Madam, this is Inspector Sharma from CBI Mumbai. "
    "Your case number is DL/4410."
)
MIN_CONVERSATIONS = 15
MIN_RINGS = 3
COLUMN = 46


class CheckError(RuntimeError):
    pass


def request(
    client: httpx.Client,
    method: str,
    path: str,
    **kwargs: Any,
) -> dict[str, Any]:
    try:
        response = client.request(method, path, **kwargs)
    except httpx.HTTPError as exc:
        raise CheckError(f"{method} {path} failed: {exc}") from exc

    if response.status_code >= 400:
        try:
            payload = response.json()
            message = payload.get("error", {}).get("message") or response.text
        except Exception:
            message = response.text
        raise CheckError(f"{method} {path} -> {response.status_code}: {message}")

    return response.json()


def check_health(client: httpx.Client) -> dict[str, Any]:
    health = request(client, "GET", "/health")
    print(f"health: {health}")
    if health.get("status") != "ok":
        raise CheckError(
            "GET /health is not ok. Check Hindsight, Groq and the SQLite path."
        )
    return health


def check_stats(client: httpx.Client) -> dict[str, Any]:
    stats = request(client, "GET", "/stats")
    print(f"stats:  {stats}")

    problems: list[str] = []
    if stats.get("conversations", 0) < MIN_CONVERSATIONS:
        problems.append(
            f"conversations {stats.get('conversations')} < {MIN_CONVERSATIONS}"
        )
    if stats.get("rings_detected", 0) < MIN_RINGS:
        problems.append(f"rings_detected {stats.get('rings_detected')} < {MIN_RINGS}")

    if problems:
        raise CheckError(
            "the bank is not seeded for the demo: "
            + "; ".join(problems)
            + ". Run the seed, then retry."
        )
    return stats


def create_and_send(client: httpx.Client, memory_enabled: bool) -> dict[str, Any]:
    conversation = request(
        client, "POST", "/conversations", json={"persona": "ajji"}
    )
    conversation_id = conversation["conversation_id"]
    print(f"created {conversation_id} (memory_enabled={memory_enabled})")

    message = request(
        client,
        "POST",
        f"/conversations/{conversation_id}/message",
        json={
            "sender": "scammer",
            "text": OPENER,
            "memory_enabled": memory_enabled,
        },
    )

    try:
        request(client, "POST", f"/conversations/{conversation_id}/end")
    except CheckError as exc:
        print(f"warning: could not end {conversation_id}: {exc}")

    return message


def print_side_by_side(off: dict[str, Any], on: dict[str, Any]) -> None:
    left = textwrap.wrap(off["reply"]["text"], width=COLUMN) or [""]
    right = textwrap.wrap(on["reply"]["text"], width=COLUMN) or [""]

    print(f"\n{'MEMORY OFF':<{COLUMN}} | MEMORY ON")
    print(f"{'-' * COLUMN}-+-{'-' * COLUMN}")
    for left_line, right_line in zip_longest(left, right, fillvalue=""):
        print(f"{left_line:<{COLUMN}} | {right_line}")

    print()
    print(f"  off timings: {off['timings_ms']}")
    print(f"  on  timings: {on['timings_ms']}")
    if off["degraded"]:
        print(f"  off degraded: {off['degraded']}")
    if on["degraded"]:
        print(f"  on  degraded: {on['degraded']}")

    if on["recalled_memories"]:
        print("\nrecalled (memory on):")
        for memory in on["recalled_memories"]:
            source = memory.get("source_conversation_id") or "?"
            print(f"  - [{source}] {memory['text']}")


def main() -> int:
    parser = argparse.ArgumentParser(description="J1 live demo check.")
    parser.add_argument("--base-url", default="http://127.0.0.1:8000")
    parser.add_argument("--timeout", type=float, default=120.0)
    args = parser.parse_args()

    failures: list[str] = []

    def check(label: str, condition: bool) -> None:
        print(f"  {'PASS' if condition else 'FAIL'}  {label}")
        if not condition:
            failures.append(label)

    try:
        with httpx.Client(
            base_url=args.base_url.rstrip("/"), timeout=args.timeout
        ) as client:
            check_health(client)
            check_stats(client)

            off = create_and_send(client, memory_enabled=False)
            on = create_and_send(client, memory_enabled=True)
    except CheckError as exc:
        print(f"\nFAIL: {exc}")
        return 1

    print_side_by_side(off, on)

    print("\nchecks:")
    check("memory-off echoes memory_enabled=false", off["memory_enabled"] is False)
    check("memory-off has no recalled memories", not off["recalled_memories"])
    check("memory-off has no contradiction flags", not off["contradiction_flags"])
    check("memory-on echoes memory_enabled=true", on["memory_enabled"] is True)
    check("memory-on recalls at least one fact", len(on["recalled_memories"]) >= 1)
    check(
        "memory-on catches at least one contradiction",
        len(on["contradiction_flags"]) >= 1,
    )
    check(
        "both replies are non-empty",
        bool(off["reply"]["text"]) and bool(on["reply"]["text"]),
    )

    print("\nsummary:")
    print(
        f"  off: {len(off['recalled_memories'])} memories, "
        f"{len(off['contradiction_flags'])} contradictions, "
        f"{off['timings_ms']['total']} ms"
    )
    print(
        f"  on : {len(on['recalled_memories'])} memories, "
        f"{len(on['contradiction_flags'])} contradictions, "
        f"{on['timings_ms']['total']} ms"
    )

    if failures:
        print(f"\nFAIL: {len(failures)} check(s) failed.")
        return 1

    print("\nPASS: memory off is local; memory on recalls and catches contradictions.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
