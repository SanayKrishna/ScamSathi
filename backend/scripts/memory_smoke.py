"""B1 smoke test: reset the bank, retain two aliases sharing a UPI, recall it.

Run from backend/:
    .venv\\Scripts\\python.exe scripts\\memory_smoke.py

Requires HINDSIGHT_URL (and HINDSIGHT_API_KEY for cloud) in backend/.env.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from config import settings  # noqa: E402
from memory import (  # noqa: E402
    MemoryUnavailable,
    ensure_bank,
    recall,
    reset_bank,
    retain_message,
)

MESSAGES = [
    (
        "conv_9001",
        "This is Inspector Sharma from CBI. Transfer the penalty to "
        "sharma.verify@fakebank today or we issue a warrant.",
        "fake_case_number",
    ),
    (
        "conv_9002",
        "Officer Verma here from CBI. The same account, "
        "sharma.verify@fakebank, is linked to your Aadhaar. Case MH/2291.",
        "fake_case_number",
    ),
    (
        "conv_9003",
        "Do not tell your family. Stay alone and wait for the video call "
        "from Inspector Sharma.",
        "isolation",
    ),
]


def main() -> int:
    if not settings.hindsight_configured:
        print("HINDSIGHT_URL is not set. Copy .env.example to .env and fill it in.")
        return 2

    try:
        print(f"Resetting bank {settings.hindsight_bank_id}...")
        reset_bank()

        print("Retaining three simulated scammer messages...")
        for conversation_id, text, stage in MESSAGES:
            retain_message(text, conversation_id=conversation_id, stage=stage)

        query = "sharma.verify@fakebank Inspector Sharma Verma"
        print(f'Recalling "{query}"...')
        memories = recall(query)
    except MemoryUnavailable as exc:
        print(f"MEMORY UNAVAILABLE: {exc}")
        return 1

    if not memories:
        print("FAIL: no memories recalled.")
        return 1

    print(f"\nRecalled {len(memories)} memories:")
    for memory in memories:
        source = memory["source_conversation_id"] or "pattern"
        print(f"  [{source}] {memory['text']}")

    shared = [m for m in memories if "sharma.verify@fakebank" in m["text"].lower()]
    if len(shared) < 2:
        print("\nFAIL: expected facts from both aliases to mention the shared UPI.")
        return 1

    print("\nOK: the shared UPI surfaced facts from both aliases.")
    ensure_bank()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
