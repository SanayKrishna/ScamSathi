"""B4 smoke test: the same opener with memory off and memory on.

Start the backend first, then run from backend/:
    .venv\\Scripts\\python.exe scripts\\turn_smoke.py

With Hindsight seeded, memory-on must recall at least one fact. Pass
--allow-empty on a bare machine to only check the response shapes.
"""

from __future__ import annotations

import argparse
import json
import sys

import httpx

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

OPENER = (
    "Madam, this is Inspector Sharma from CBI Mumbai. Your Aadhaar is linked "
    "to money laundering. Case number DL/4410."
)


def create_conversation(client: httpx.Client) -> dict:
    response = client.post("/conversations", json={"persona": "ajji"})
    response.raise_for_status()
    return response.json()


def send(client: httpx.Client, conversation_id: str, memory_enabled: bool) -> dict:
    response = client.post(
        f"/conversations/{conversation_id}/message",
        json={
            "sender": "scammer",
            "text": OPENER,
            "memory_enabled": memory_enabled,
        },
    )
    response.raise_for_status()
    return response.json()


def end(client: httpx.Client, conversation_id: str) -> dict:
    response = client.post(f"/conversations/{conversation_id}/end")
    response.raise_for_status()
    return response.json()


def show(label: str, body: dict) -> None:
    print(f"\n{'=' * 72}\n{label}\n{'=' * 72}")
    print(f"memory_enabled:      {body['memory_enabled']}")
    print(f"reply:               {body['reply']['text']}")
    print(f"recalled_memories:   {len(body['recalled_memories'])}")
    for memory in body["recalled_memories"]:
        source = memory["source_conversation_id"] or "pattern"
        matched = memory["matched_ioc"]["value"] if memory["matched_ioc"] else "-"
        print(f"  [{source}] {memory['text']}")
        print(f"           why: {memory['why_relevant']} (matched: {matched})")
    print(f"contradiction_flags: {len(body['contradiction_flags'])}")
    for flag in body["contradiction_flags"]:
        print(f"  [{flag['severity']}] {flag['kind']}: {flag['claim_before']} -> {flag['claim_now']}")
    print(f"extracted_iocs:      {json.dumps(body['extracted_iocs'], ensure_ascii=False)}")
    print(f"script_stage:        {body['script_stage']}")
    print(f"degraded:            {body['degraded']}")
    print(f"timings_ms:          {body['timings_ms']}")


def main() -> int:
    parser = argparse.ArgumentParser(description="Compare memory off and memory on.")
    parser.add_argument("--base-url", default="http://127.0.0.1:8000")
    parser.add_argument(
        "--allow-empty",
        action="store_true",
        help="Do not fail when memory-on recalls nothing (no seeded bank yet).",
    )
    args = parser.parse_args()

    with httpx.Client(base_url=args.base_url, timeout=60.0) as client:
        health = client.get("/health")
        health.raise_for_status()
        print(f"health: {json.dumps(health.json())}")

        off_conversation = create_conversation(client)
        on_conversation = create_conversation(client)
        print(f"memory-off chat: {off_conversation['conversation_id']}")
        print(f"memory-on chat:  {on_conversation['conversation_id']}")

        off = send(client, off_conversation["conversation_id"], memory_enabled=False)
        on = send(client, on_conversation["conversation_id"], memory_enabled=True)

        show("MEMORY OFF", off)
        show("MEMORY ON", on)

        end(client, off_conversation["conversation_id"])
        end(client, on_conversation["conversation_id"])

    failures: list[str] = []
    if off["memory_enabled"] is not False:
        failures.append("memory-off response echoed memory_enabled=true")
    if off["recalled_memories"]:
        failures.append("memory-off response included recalled memories")
    if off["contradiction_flags"]:
        failures.append("memory-off response included contradictions")
    if on["memory_enabled"] is not True:
        failures.append("memory-on response echoed memory_enabled=false")
    if not args.allow_empty and not on["recalled_memories"]:
        failures.append("memory-on response recalled nothing (seed Hindsight first, or use --allow-empty)")
    if not off["reply"]["text"] or not on["reply"]["text"]:
        failures.append("a reply was empty")

    if failures:
        print("\nFAIL:")
        for failure in failures:
            print(f"- {failure}")
        return 1

    print("\nOK: memory off stayed local, memory on returned the expected shape.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
