"""Record a scripted memory-off vs memory-on run and save every raw API response.

Run from backend/ with the backend running against a seeded bank:
    .venv\\Scripts\\python scripts\\capture_demo.py

Writes demo-capture/capture.json at the repo root. It only talks to the HTTP
API (no settings or env values are read), and never resets or reseeds.
Exits non-zero if the memory-on run does not show recall and contradictions,
or if any turn degrades to recall_unavailable or a canned reply.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import httpx

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

REPO_ROOT = Path(__file__).resolve().parents[2]
OUT_PATH = REPO_ROOT / "demo-capture" / "capture.json"
TURN_GAP_SECONDS = 4.0
BAD_DEGRADED = {"recall_unavailable", "reply_fallback_canned"}

TURNS = [
    "Madam, this is Inspector Sharma from CBI Mumbai. Your Aadhaar is linked to a "
    "money laundering case. Do not disconnect the call.",
    "Your case number is DL/4410. Write it down, madam. This is a serious criminal case.",
    "I need to verify your face on a video call now. Open WhatsApp and call this "
    "number 5550142244.",
    "To clear your name, transfer Rs 49,000 to cbi.clearance@fakebank. It is refundable.",
]

RUNS = [
    ("memory_off", False, TURNS[:2]),
    ("memory_on", True, TURNS[:4]),
]


def call(client: httpx.Client, method: str, path: str, **kwargs: Any) -> Any:
    response = client.request(method, path, **kwargs)
    if response.status_code >= 400:
        raise RuntimeError(f"{method} {path} -> {response.status_code}: {response.text[:300]}")
    return response.json()


def run_conversation(
    client: httpx.Client, label: str, memory_enabled: bool, turns: list[str]
) -> dict[str, Any]:
    conversation = call(client, "POST", "/conversations", json={"persona": "ajji"})
    conversation_id = conversation["conversation_id"]
    print(f"{label}: {conversation_id}")

    recorded: list[dict[str, Any]] = []
    for index, text in enumerate(turns, 1):
        response = call(
            client,
            "POST",
            f"/conversations/{conversation_id}/message",
            json={"sender": "scammer", "text": text, "memory_enabled": memory_enabled},
        )
        # The 4 s gap between turns lets the background retain finish; the
        # graph and stats are read after it, so they include this turn.
        time.sleep(TURN_GAP_SECONDS)
        recorded.append(
            {
                "scammer_text": text,
                "response": response,
                "network_after": call(
                    client, "GET", "/network", params={"conversation_id": conversation_id}
                ),
                "stats_after": call(client, "GET", "/stats"),
            }
        )
        print(f"  turn {index}: {response['timings_ms']['total']} ms")

    history = call(client, "GET", f"/conversations/{conversation_id}")
    return {"label": label, "conversation": conversation, "turns": recorded, "history": history}


def check(capture: dict[str, Any]) -> list[str]:
    problems: list[str] = []
    on = next(run for run in capture["runs"] if run["label"] == "memory_on")

    print("\nmemory_on summary:")
    for index, turn in enumerate(on["turns"], 1):
        response = turn["response"]
        flags = response["contradiction_flags"]
        print(
            f"  turn {index}: recalled={len(response['recalled_memories'])} "
            f"contradictions={len(flags)} degraded={response['degraded']} "
            f"total={response['timings_ms']['total']} ms"
        )
        for flag in flags:
            print(f"      {flag['kind']}: now {flag['claim_now']!r} / before {flag['claim_before']!r}")

    early_recall = any(t["response"]["recalled_memories"] for t in on["turns"][:2])
    any_flag = any(t["response"]["contradiction_flags"] for t in on["turns"])
    if not early_recall:
        problems.append("memory_on recalled nothing on turn 1 or 2")
    if not any_flag:
        problems.append("memory_on raised no contradiction flag")

    for run in capture["runs"]:
        for index, turn in enumerate(run["turns"], 1):
            bad = BAD_DEGRADED.intersection(turn["response"]["degraded"])
            if bad:
                problems.append(f"{run['label']} turn {index} degraded: {sorted(bad)}")
    return problems


def main() -> int:
    parser = argparse.ArgumentParser(description="Capture a scripted memory off/on run.")
    parser.add_argument("--base-url", default="http://127.0.0.1:8000")
    args = parser.parse_args()

    with httpx.Client(base_url=args.base_url.rstrip("/"), timeout=60.0) as client:
        capture: dict[str, Any] = {
            "captured_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
            "health": call(client, "GET", "/health"),
            "stats_before": call(client, "GET", "/stats"),
            "network_before": call(client, "GET", "/network"),
            "runs": [],
        }
        for label, memory_enabled, turns in RUNS:
            capture["runs"].append(run_conversation(client, label, memory_enabled, turns))

    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUT_PATH.write_text(json.dumps(capture, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"\nsaved {OUT_PATH.relative_to(REPO_ROOT)}")

    problems = check(capture)
    if problems:
        print("\nFAIL:")
        for problem in problems:
            print(f"  - {problem}")
        return 1
    print("\nPASS: memory on recalls early, catches a contradiction, and nothing degraded.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
