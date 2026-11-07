"""Hindsight Cloud connectivity check on a throwaway bank.

Run from backend/:
    .venv\\Scripts\\python.exe scripts\\cloud_check.py

Uses memory.py only. Creates bank "scam-intel-test", retains three messages in
which two aliases share one UPI ID, polls recall until Cloud has extracted facts
(up to 60 s), prints them, then deletes the test bank. Never prints keys.
"""

from __future__ import annotations

import os
import sys
import time
from pathlib import Path

# Must be set before config is imported; load_dotenv does not override it.
os.environ["HINDSIGHT_BANK_ID"] = "scam-intel-test"

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from config import settings  # noqa: E402
import memory  # noqa: E402

QUERY = "sharma.verify@fakebank"
POLL_SECONDS = 3
POLL_LIMIT_SECONDS = 60

MESSAGES = [
    (
        "conv_9001",
        "This is Inspector Sharma from CBI. Transfer the penalty to "
        "sharma.verify@fakebank today or we issue a warrant.",
        "intro_threat",
    ),
    (
        "conv_9002",
        "Officer Verma here from the CBI cyber cell. Your Aadhaar is linked to "
        "account sharma.verify@fakebank. Case MH/2291.",
        "fake_case_number",
    ),
    (
        "conv_9002",
        "Madam, Officer Verma again. Send the verification amount to "
        "sharma.verify@fakebank within one hour.",
        "verification_transfer",
    ),
]


def main() -> int:
    if settings.hindsight_bank_id != "scam-intel-test":
        print("FAIL: refusing to run against a non-test bank.")
        return 1
    print(f"Hindsight URL: {settings.hindsight_url}")
    print(f"Bank: {settings.hindsight_bank_id}")
    print(f"API key set: {'yes' if settings.hindsight_api_key else 'no'}")

    created = False
    try:
        t0 = time.perf_counter()
        memory.ensure_bank()
        created = True
        print(f"ensure_bank ok ({time.perf_counter() - t0:.2f}s)")

        for conversation_id, text, stage in MESSAGES:
            t0 = time.perf_counter()
            memory.retain_message(text, conversation_id, stage)
            print(f"retain ok {conversation_id} [{stage}] ({time.perf_counter() - t0:.2f}s)")
        retained_at = time.perf_counter()

        results: list[dict] = []
        attempts = 0
        while True:
            attempts += 1
            results = memory.recall(QUERY)
            elapsed = time.perf_counter() - retained_at
            if results:
                break
            if elapsed >= POLL_LIMIT_SECONDS:
                print(f"FAIL: recall returned nothing after {elapsed:.1f}s ({attempts} polls).")
                return 1
            time.sleep(POLL_SECONDS)

        print(f"\nExtraction ready after {elapsed:.1f}s ({attempts} recall poll(s)).")
        print(f'Recall "{QUERY}" -> {len(results)} result(s):')
        raw = {text for _, text, _ in MESSAGES}
        for i, memory_item in enumerate(results, 1):
            kind = "RAW MESSAGE" if memory_item["text"] in raw else "fact"
            print(
                f"  {i}. [{kind}] {memory_item['text']}"
                f"  (conversation={memory_item['source_conversation_id']})"
            )
        return 0
    except memory.MemoryUnavailable as exc:
        print(f"FAIL: {exc}")
        return 1
    finally:
        if created:
            try:
                memory.delete_bank()
                print("\nDeleted test bank scam-intel-test.")
            except memory.MemoryUnavailable as exc:
                print(f"\nWARNING: could not delete test bank: {exc}")


if __name__ == "__main__":
    raise SystemExit(main())
