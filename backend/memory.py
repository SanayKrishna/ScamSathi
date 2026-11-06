"""All Hindsight calls live here and nowhere else (B1).

The rest of the backend only ever imports these functions. Every public call
has a timeout (set on the client) and raises a single MemoryUnavailable
exception on failure so callers can degrade instead of crashing a demo turn.

Verified against hindsight-client 1.2.0:

    Hindsight(base_url, api_key=None, timeout=300.0, max_attempts=3)
    create_bank(bank_id, name=None, mission=None, ...)
    get_bank_config(bank_id) -> dict
    delete_bank(bank_id)
    retain(bank_id, content, timestamp=None, context=None, metadata=None, ...)
    recall(bank_id, query, types=None, max_tokens=4096, budget="mid", ...)
        -> RecallResponse(results=[RecallResult(text, context, ...)])
    list_memories(bank_id, limit=100, offset=0) -> ListMemoryUnitsResponse(total)

Our stored context is always "conversation=<id> stage=<stage> persona=<name>"
or "conversation_summary conversation=<id> persona=<name>", which is how recall
recovers source_conversation_id for the memory panel.
"""

from __future__ import annotations

import logging
import re
from datetime import datetime, timezone
from typing import Any

from config import settings

logger = logging.getLogger("scamsathi.memory")

CONVERSATION_RE = re.compile(r"(?:^|\s)conversation=([^\s]+)")


class MemoryUnavailable(RuntimeError):
    """Hindsight is not configured, unreachable, or returned an error."""


def _get_client(timeout: float | None = None) -> Any:
    """Build a fresh client for this call.

    The Hindsight client wraps an aiohttp session and an event loop. FastAPI
    runs sync routes in a thread pool and background tasks in another thread, so
    sharing one client across calls produced "Timeout context manager should be
    used inside a task" errors. A short-lived client per operation is cheap at
    demo scale and keeps every call on its own thread and loop.

    `timeout` lets a turn cap recall to the time it has left. Short budgets also
    reduce the client's internal retries to one.
    """
    if not settings.hindsight_configured:
        raise MemoryUnavailable("HINDSIGHT_URL is not set.")

    from hindsight_client import Hindsight

    client_timeout = settings.hindsight_timeout_seconds
    max_attempts = settings.hindsight_max_attempts
    if timeout is not None:
        client_timeout = max(0.5, min(client_timeout, timeout))
        if timeout < settings.hindsight_timeout_seconds:
            max_attempts = 1

    return Hindsight(
        base_url=settings.hindsight_url,
        api_key=settings.hindsight_api_key or None,
        timeout=client_timeout,
        max_attempts=max_attempts,
    )


def _close(client: Any) -> None:
    try:
        client.close()
    except Exception:
        pass


def is_configured() -> bool:
    return settings.hindsight_configured


def _not_found(exc: Exception) -> bool:
    """Hindsight surfaces a missing bank as aiohttp 404 or ApiException 404."""
    if getattr(exc, "status", None) == 404:
        return True
    try:
        from hindsight_client_api.exceptions import ApiException

        if isinstance(exc, ApiException) and getattr(exc, "status", None) == 404:
            return True
    except Exception:
        pass
    text = str(exc).lower()
    return "404" in text and "not found" in text


def _fail(action: str, exc: Exception) -> MemoryUnavailable:
    logger.warning("Hindsight %s failed: %s", action, exc)
    return MemoryUnavailable(f"Hindsight {action} failed.")


def ensure_bank() -> None:
    """Create HINDSIGHT_BANK_ID if it does not exist yet."""
    client = _get_client()
    try:
        try:
            config = client.get_bank_config(settings.hindsight_bank_id)
            if config:
                return
        except Exception as exc:
            if not _not_found(exc):
                raise _fail("bank lookup", exc) from exc

        try:
            client.create_bank(
                bank_id=settings.hindsight_bank_id,
                name="ScamSathi",
                mission=(
                    "Long-term memory for a fraud-awareness demo. Store what simulated "
                    "scammers said: aliases, agencies, case numbers, UPI IDs and phones."
                ),
                disposition={"skepticism": 4, "literalism": 3, "empathy": 4},
            )
            logger.info("created Hindsight bank %s", settings.hindsight_bank_id)
        except Exception as exc:
            # A race can create it between the lookup and this call. Verify once.
            try:
                client.get_bank_config(settings.hindsight_bank_id)
            except Exception:
                raise _fail("bank create", exc) from exc
    finally:
        _close(client)


def reset_bank() -> None:
    """Delete and recreate the bank. Safe to call when it is already gone."""
    client = _get_client()
    try:
        try:
            client.delete_bank(settings.hindsight_bank_id)
            logger.info("deleted Hindsight bank %s", settings.hindsight_bank_id)
        except Exception as exc:
            if not _not_found(exc):
                raise _fail("bank delete", exc) from exc
    finally:
        _close(client)
    ensure_bank()


def _iso(value: datetime | str | None) -> str:
    if isinstance(value, datetime):
        return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")
    if isinstance(value, str):
        return value
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def retain_message(
    text: str,
    conversation_id: str,
    stage: str | None,
    timestamp: datetime | str | None = None,
) -> None:
    """Retain one scammer message with the context recall needs to attribute it."""
    client = _get_client()
    context = (
        f"conversation={conversation_id} "
        f"stage={stage or 'unknown'} "
        f"persona={settings.persona_name}"
    )
    try:
        client.retain(
            bank_id=settings.hindsight_bank_id,
            content=text,
            context=context,
            timestamp=_iso(timestamp),
            metadata={
                "conversation_id": conversation_id,
                "stage": stage or "unknown",
                "persona": settings.persona_name,
            },
        )
    except Exception as exc:
        raise _fail("retain", exc) from exc
    finally:
        _close(client)


def _join(value: Any) -> str:
    if isinstance(value, list):
        return ", ".join(str(item) for item in value) if value else "none"
    return str(value) if value else "none"


def retain_summary(summary: dict[str, Any], conversation_id: str) -> None:
    """Retain a readable paragraph built from the end-of-conversation summary."""
    client = _get_client()
    paragraph = (
        f"Conversation {conversation_id} summary. "
        f"Aliases used: {_join(summary.get('aliases'))}. "
        f"Agencies claimed: {_join(summary.get('agencies_claimed'))}. "
        f"Case numbers: {_join(summary.get('case_numbers'))}. "
        f"UPI IDs: {_join(summary.get('upi_ids'))}. "
        f"Phones: {_join(summary.get('phones'))}. "
        f"Stages reached: {_join(summary.get('stages_reached'))}. "
        f"Tactics: {_join(summary.get('tactics'))}."
    )
    try:
        client.retain(
            bank_id=settings.hindsight_bank_id,
            content=paragraph,
            context=(
                f"conversation_summary conversation={conversation_id} "
                f"persona={settings.persona_name}"
            ),
            timestamp=_iso(None),
            metadata={
                "conversation_id": conversation_id,
                "kind": "conversation_summary",
            },
        )
    except Exception as exc:
        raise _fail("retain summary", exc) from exc
    finally:
        _close(client)


def _conversation_from_context(context: str | None) -> str | None:
    if not context:
        return None
    match = CONVERSATION_RE.search(context)
    return match.group(1) if match else None


def recall(query: str, timeout: float | None = None) -> list[dict[str, Any]]:
    """Return at most five memories as {text, source_conversation_id}."""
    client = _get_client(timeout=timeout)
    try:
        try:
            response = client.recall(
                bank_id=settings.hindsight_bank_id,
                query=query,
                max_tokens=2048,
                budget="mid",
            )
        except Exception as exc:
            raise _fail("recall", exc) from exc
    finally:
        _close(client)

    memories: list[dict[str, Any]] = []
    seen: set[str] = set()
    for result in getattr(response, "results", []) or []:
        text = (getattr(result, "text", "") or "").strip()
        if not text or text in seen:
            continue
        seen.add(text)
        memories.append(
            {
                "text": text,
                "source_conversation_id": _conversation_from_context(
                    getattr(result, "context", None)
                ),
            }
        )
        if len(memories) >= 5:
            break
    return memories


def memory_count() -> int:
    """How many memory units the bank currently holds (for /stats)."""
    client = _get_client()
    try:
        try:
            response = client.list_memories(
                bank_id=settings.hindsight_bank_id, limit=1, offset=0
            )
        except Exception as exc:
            raise _fail("memory count", exc) from exc
    finally:
        _close(client)
    return int(getattr(response, "total", 0) or 0)
