"""Demo seed job manager (B6).

One in-process background thread at a time. The job state is small and lives
in memory; the seeded conversations themselves live in SQLite and Hindsight.
"""

from __future__ import annotations

import logging
import threading
import uuid
from typing import Any, Callable

from config import settings
from errors import ApiError

logger = logging.getLogger("scamsathi.demo")

Runner = Callable[[int, Callable[[], None]], None]


def _default_runner(planned: int, on_progress: Callable[[], None]) -> None:
    from simulator.seeder import SeedApi, run_seed

    with SeedApi(settings.seed_base_url, timeout=settings.seed_timeout_seconds) as api:
        run_seed(
            api,
            conversations=planned,
            use_llm=settings.seed_use_llm,
            on_progress=on_progress,
            delay=settings.seed_delay_seconds,
        )


def _safe_error(exc: Exception) -> str:
    message = f"{type(exc).__name__}: {exc}".replace("\n", " ").strip()
    return message[:300] or "Seed job failed."


class SeedManager:
    def __init__(self, runner: Runner | None = None) -> None:
        self._runner = runner or _default_runner
        self._lock = threading.Lock()
        self._job: dict[str, Any] | None = None
        self._thread: threading.Thread | None = None

    def running(self) -> bool:
        with self._lock:
            return bool(self._job and self._job["status"] == "running")

    def start(self, planned: int | None = None) -> dict[str, Any]:
        planned = max(1, planned or settings.seed_conversations)
        with self._lock:
            if self._job and self._job["status"] == "running":
                raise ApiError(
                    409,
                    "seed_already_running",
                    "A seed job is already running. Wait for it to finish.",
                )
            job_id = f"seed_{uuid.uuid4().hex[:8]}"
            self._job = {
                "job_id": job_id,
                "status": "running",
                "conversations_done": 0,
                "conversations_planned": planned,
                "error": None,
            }
            thread = threading.Thread(
                target=self._run,
                args=(job_id, planned),
                name=f"seed-{job_id}",
                daemon=True,
            )
            self._thread = thread

        # Start outside the lock so the worker never waits on the request path.
        thread.start()
        return {
            "job_id": job_id,
            "status": "running",
            "conversations_planned": planned,
        }

    def _run(self, job_id: str, planned: int) -> None:
        try:
            self._runner(planned, lambda: self._progress(job_id))
            with self._lock:
                if self._job and self._job["job_id"] == job_id:
                    self._job["status"] = "done"
        except Exception as exc:
            logger.exception("seed job %s failed", job_id)
            with self._lock:
                if self._job and self._job["job_id"] == job_id:
                    self._job["status"] = "failed"
                    self._job["error"] = _safe_error(exc)

    def _progress(self, job_id: str) -> None:
        with self._lock:
            if self._job and self._job["job_id"] == job_id:
                self._job["conversations_done"] = min(
                    self._job["conversations_planned"],
                    self._job["conversations_done"] + 1,
                )

    def status(self, job_id: str) -> dict[str, Any] | None:
        with self._lock:
            if not self._job or self._job["job_id"] != job_id:
                return None
            return dict(self._job)

    def reset(self) -> None:
        with self._lock:
            if self._job and self._job["status"] == "running":
                raise ApiError(
                    409,
                    "seed_already_running",
                    "A seed job is running. Wait for it to finish.",
                )
            self._job = None


seed_manager = SeedManager()


def start_seed(planned: int | None = None) -> dict[str, Any]:
    return seed_manager.start(planned)


def get_seed_status(job_id: str) -> dict[str, Any] | None:
    return seed_manager.status(job_id)


def ensure_not_running() -> None:
    if seed_manager.running():
        raise ApiError(
            409,
            "seed_already_running",
            "A seed job is running. Wait for it to finish.",
        )


def reset_seed() -> None:
    seed_manager.reset()
