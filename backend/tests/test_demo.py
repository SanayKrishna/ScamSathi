from __future__ import annotations

import threading
import time

import pytest

from demo import SeedManager
from errors import ApiError


def wait_for(manager: SeedManager, job_id: str, timeout: float = 3.0) -> dict:
    deadline = time.time() + timeout
    while time.time() < deadline:
        status = manager.status(job_id)
        if status and status["status"] != "running":
            return status
        time.sleep(0.01)
    raise AssertionError("seed job did not finish in time")


def test_seed_manager_completes_and_counts_progress():
    def runner(planned, on_progress):
        for _ in range(planned):
            on_progress()

    manager = SeedManager(runner)
    started = manager.start(3)

    assert started["status"] == "running"
    assert started["conversations_planned"] == 3
    assert set(started) == {"job_id", "status", "conversations_planned"}

    status = wait_for(manager, started["job_id"])
    assert status == {
        "job_id": started["job_id"],
        "status": "done",
        "conversations_done": 3,
        "conversations_planned": 3,
        "error": None,
    }


def test_seed_manager_marks_failures_without_a_traceback():
    def runner(planned, on_progress):
        on_progress()
        raise RuntimeError("groq exploded\nwith a newline")

    manager = SeedManager(runner)
    started = manager.start(2)
    status = wait_for(manager, started["job_id"])

    assert status["status"] == "failed"
    assert status["conversations_done"] == 1
    assert "groq exploded" in status["error"]
    assert "\n" not in status["error"]


def test_second_seed_and_reset_are_rejected_while_running():
    started = threading.Event()
    release = threading.Event()

    def runner(planned, on_progress):
        started.set()
        release.wait(3)

    manager = SeedManager(runner)
    job = manager.start(1)
    assert started.wait(1)

    with pytest.raises(ApiError) as second:
        manager.start(1)
    assert second.value.status_code == 409
    assert second.value.code == "seed_already_running"

    with pytest.raises(ApiError):
        manager.reset()

    release.set()
    assert wait_for(manager, job["job_id"])["status"] == "done"


def test_reset_clears_a_finished_job():
    manager = SeedManager(lambda planned, on_progress: on_progress())
    job = manager.start(1)
    wait_for(manager, job["job_id"])

    manager.reset()
    assert manager.status(job["job_id"]) is None
    assert manager.running() is False


def test_unknown_job_has_no_status():
    manager = SeedManager(lambda planned, on_progress: None)
    assert manager.status("seed_missing") is None
