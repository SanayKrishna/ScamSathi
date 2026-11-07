"""Seed the demo bank from the command line (B6).

Run from backend/ with the API already running:
    .venv\\Scripts\\python.exe simulator\\run_seed.py --reset

Options:
    --conversations 20     how many simulated chats
    --base-url ...         API base URL (default SEED_BASE_URL)
    --no-llm              use rings.json templates only (fast, offline)
    --delay 0.2           pause between turns
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from config import settings  # noqa: E402
import db  # noqa: E402
import memory  # noqa: E402
from simulator.seeder import SeedApi, run_seed  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description="Seed the ScamSathi demo bank.")
    parser.add_argument("--base-url", default=settings.seed_base_url)
    parser.add_argument("--conversations", type=int, default=settings.seed_conversations)
    parser.add_argument("--no-llm", action="store_true", help="Templates only, no Groq calls.")
    parser.add_argument("--delay", type=float, default=settings.seed_delay_seconds)
    parser.add_argument("--reset", action="store_true", help="Reset SQLite and the Hindsight bank first.")
    parser.add_argument(
        "--direct",
        action="store_true",
        help="Populate SQLite and Hindsight in-process with templates; no HTTP or Groq calls.",
    )
    args = parser.parse_args()

    done = 0

    def progress() -> None:
        nonlocal done
        done += 1
        print(f"  conversation {done}/{args.conversations}", flush=True)

    try:
        if args.direct:
            if args.reset:
                print("Resetting database and memory bank...")
                if memory.is_configured():
                    memory.reset_bank()
                db.reset_db()

            from simulator.direct import run_seed_direct

            run_seed_direct(
                conversations=args.conversations,
                on_progress=progress,
                seed=42,
            )
        else:
            with SeedApi(args.base_url, timeout=settings.seed_timeout_seconds) as api:
                if args.reset:
                    print("Resetting database and memory bank...")
                    print(api.reset())
                else:
                    print("Seeding without reset. Existing chats stay in the bank.")

                run_seed(
                    api,
                    conversations=args.conversations,
                    use_llm=not args.no_llm,
                    on_progress=progress,
                    delay=args.delay,
                )
    except Exception as exc:
        print(f"FAIL: {exc}")
        return 1

    print(f"OK: seeded {args.conversations} conversations.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
