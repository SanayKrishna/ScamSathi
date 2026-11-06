"""B2 smoke test against the real Groq API.

Run from backend/:
    .venv\\Scripts\\python.exe scripts\\extract_smoke.py

Requires GROQ_API_KEY in backend/.env. Prints the extracted IOCs, stage and
whether the regex fallback was used.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from config import settings  # noqa: E402
from extract import extract_iocs  # noqa: E402

SAMPLE = (
    "Madam, this is Inspector Sharma from CBI Mumbai. Your Aadhaar is linked "
    "to money laundering. Case number DL/4410. Transfer the penalty to "
    "sharma.verify@fakebank, or call me on 555-014-2233. Do not tell your family."
)


def main() -> int:
    if not settings.llm_configured:
        print("GROQ_API_KEY is not set. Copy .env.example to .env and fill it in.")
        return 2

    print(f"Model: {settings.groq_model} (fallback {settings.groq_fallback_model})")
    print(f"Message: {SAMPLE}\n")

    iocs, stage, degraded = extract_iocs(SAMPLE)

    print(f"stage: {stage}")
    print(f"degraded: {degraded}")
    print("iocs:")
    for ioc in iocs:
        print(f"  {ioc.type:<16} {ioc.value}")

    if degraded:
        print("\nWARN: the model path failed and regex fallback was used.")
        return 1
    if not iocs:
        print("\nFAIL: no IOCs extracted.")
        return 1

    print("\nOK.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
