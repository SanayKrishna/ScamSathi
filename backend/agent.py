"""Turn orchestration: steps 1–8 from architecture.md section 2 (B4).

Hindsight failures degrade the turn; they never fail it. The message endpoint
should only error for the cases in API.md's error table.
"""

from __future__ import annotations

import logging
import time
from datetime import datetime
from typing import Any

import httpx

import db
import memory
import persona
from config import settings
from contradictions import find_contradictions
from errors import ApiError
from extract import Ioc, extract_iocs

logger = logging.getLogger("scamsathi.agent")

MAX_MESSAGE_CHARS = 2000
MAX_REPLY_CHARS = 600
HISTORY_LIMIT = 20
RETAIN_ATTEMPTS = 3
RETAIN_BACKOFF_SECONDS = 0.4
REPLY_RATE_LIMIT_RETRIES = 1
TURN_SAFETY_MARGIN_SECONDS = 0.6


# ── Small helpers ───────────────────────────────────────────────


def _elapsed_ms(started: float) -> int:
    return int(round((time.perf_counter() - started) * 1000))


def _remaining(deadline: float) -> float:
    return max(0.0, deadline - time.perf_counter())


LEAK_MARKERS = (
    "system prompt",
    "as an ai",
    "language model",
    "i am a bot",
    "i'm a bot",
    "my instructions",
    "the instructions say",
    "you are ajji, a 72",
)


def _looks_like_leak(text: str) -> bool:
    lower = (text or "").lower()
    return any(marker in lower for marker in LEAK_MARKERS)


def _validate_text(text: str) -> str:
    trimmed = (text or "").strip()
    if not trimmed or len(trimmed) > MAX_MESSAGE_CHARS:
        raise ApiError(
            400,
            "invalid_message",
            "Message must be between 1 and 2000 characters.",
        )
    return trimmed


def _parse_iso(value: str) -> datetime | None:
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except (TypeError, ValueError):
        return None


def _duration_seconds(started_at: str, ended_at: str) -> int:
    started, ended = _parse_iso(started_at), _parse_iso(ended_at)
    if started is None or ended is None:
        return 0
    return max(0, int(round((ended - started).total_seconds())))


def _recall_query(text: str, iocs: list[Ioc]) -> str:
    labels = [
        f"{ioc.type.replace('_', ' ')} {ioc.value}"
        for ioc in iocs
        if ioc.type != "script_stage"
    ]
    return f"{text} {' '.join(labels)}".strip()


def _matched_ioc(memory_text: str, iocs: list[Ioc]) -> Ioc | None:
    haystack = (memory_text or "").lower()
    # Longest first so "inspector sharma" wins before a shorter overlapping value.
    for ioc in sorted(iocs, key=lambda item: len(item.value), reverse=True):
        if ioc.type == "script_stage":
            continue
        if ioc.value and ioc.value.lower() in haystack:
            return ioc
    return None


WHY_RELEVANT = {
    "alias": "Same alias seen in an earlier chat",
    "upi": "Same UPI handle seen in an earlier chat",
    "phone": "Same phone number seen in an earlier chat",
    "case_number": "Same case number seen in an earlier chat",
    "agency_claimed": "Same agency claimed in an earlier chat",
}


def _memory_for_response(item: dict[str, Any], iocs: list[Ioc]) -> dict[str, Any]:
    matched = _matched_ioc(item.get("text", ""), iocs)
    return {
        "text": item.get("text", ""),
        "why_relevant": (
            WHY_RELEVANT.get(matched.type, "Related to what this scammer just said")
            if matched
            else "Related to what this scammer just said"
        ),
        "source_conversation_id": item.get("source_conversation_id"),
        "matched_ioc": {"type": matched.type, "value": matched.value} if matched else None,
    }


def _clean_reply(raw: str) -> str:
    text = (raw or "").strip()
    if text.startswith("```"):
        text = text.strip("`").strip()
        if text.lower().startswith("text"):
            text = text[4:].strip()
    if text.lower().startswith(f"{settings.persona_name.lower()}:"):
        text = text.split(":", 1)[1].strip()
    text = text.strip().strip('"').strip()
    if len(text) > MAX_REPLY_CHARS:
        text = text[: MAX_REPLY_CHARS - 3].rsplit(" ", 1)[0].rstrip() + "..."
    return text


# ── Groq reply call ─────────────────────────────────────────────


def _call_groq_reply(messages: list[dict[str, str]], model: str, timeout: float) -> str:
    """One chat-completions call for Ajji's line. Tests monkeypatch this."""
    payload = {
        "model": model,
        "temperature": 0.8,
        "max_completion_tokens": 512,
        "reasoning_effort": "low",
        "messages": messages,
    }
    for attempt in range(REPLY_RATE_LIMIT_RETRIES + 1):
        with httpx.Client(timeout=httpx.Timeout(timeout, connect=min(2.0, timeout))) as client:
            response = client.post(
                f"{settings.groq_base_url}/chat/completions",
                headers={
                    "Authorization": f"Bearer {settings.groq_api_key}",
                    "Content-Type": "application/json",
                },
                json=payload,
            )
        if response.status_code == 429 and attempt < REPLY_RATE_LIMIT_RETRIES:
            try:
                retry_after = float(response.headers.get("retry-after", ""))
            except (TypeError, ValueError):
                retry_after = 0.0
            delay = min(2.0, max(0.5, retry_after or 1.0))
            logger.warning("Groq 429 during reply; retrying in %.1fs", delay)
            time.sleep(delay)
            continue
        response.raise_for_status()
        data = response.json()

    text = _clean_reply(data["choices"][0]["message"]["content"])
    if not text:
        raise ValueError("model returned an empty reply")
    return text


def _generate_reply(messages: list[dict[str, str]], deadline: float) -> tuple[str, bool]:
    """Return (text, used_canned). Never raises and never exceeds the budget."""
    if not settings.llm_configured:
        logger.info("GROQ_API_KEY missing; using a canned Ajji line")
        return persona.canned_reply(), True

    models = [settings.groq_model]
    if settings.groq_fallback_model and settings.groq_fallback_model != settings.groq_model:
        models.append(settings.groq_fallback_model)

    for model in models:
        remaining = _remaining(deadline)
        if remaining <= 0.5:
            logger.warning("turn budget exhausted before the reply call")
            break
        timeout = min(settings.groq_timeout_seconds, remaining)
        try:
            text = _call_groq_reply(messages, model, timeout=timeout)
            if _looks_like_leak(text):
                logger.warning("reply looked like a prompt leak; using a canned line")
                return persona.canned_reply(), True
            return text, False
        except Exception as exc:
            logger.warning("reply with %s failed: %s", model, exc)

    return persona.canned_reply(), True


# ── Conversation lifecycle ──────────────────────────────────────


def create_conversation(persona_name: str = "ajji") -> dict[str, Any]:
    if (persona_name or "").strip().lower() != "ajji":
        raise ApiError(400, "invalid_request", "Unknown persona.")

    conversation_id = db.next_conversation_id()
    started_at = db.utc_now_iso()
    opening = persona.opening_line()

    db.create_conversation(conversation_id, started_at=started_at, persona="ajji")
    db.add_message(conversation_id, "ajji", opening, created_at=started_at)

    return {
        "conversation_id": conversation_id,
        "persona": "ajji",
        "started_at": started_at,
        "opening_line": opening,
    }


def get_conversation(conversation_id: str) -> dict[str, Any]:
    conversation = db.get_conversation(conversation_id)
    if conversation is None:
        raise ApiError(
            404,
            "conversation_not_found",
            "That conversation doesn't exist. Start a new one.",
        )
    return conversation


def _tactics(texts: list[str]) -> list[str]:
    lower = " ".join(texts).lower()
    tactics: list[str] = []
    if any(word in lower for word in ("immediately", "urgent", "today", "right now", "before")):
        tactics.append("urgency")
    if any(word in lower for word in ("do not tell", "don't tell", "dont tell", "stay alone", "no one", "nobody")):
        tactics.append("isolation: told not to tell family")
    if any(word in lower for word in ("arrest", "warrant", "jail", "fir", "police case")):
        tactics.append("threat of arrest")
    if any(word in lower for word in ("video call", "video-call", "skype", "facetime")):
        tactics.append("video call pressure")
    if any(word in lower for word in ("aadhaar", "pan card", "sim", "kyc")):
        tactics.append("identity document threat")
    return tactics


def _build_summary(conversation_id: str, conversation: dict[str, Any]) -> dict[str, Any]:
    summary = db.conversation_summary_parts(conversation_id)
    scammer_texts = [
        message["text"]
        for message in conversation.get("messages", [])
        if message.get("sender") == "scammer"
    ]
    summary["tactics"] = _tactics(scammer_texts)
    return summary


def end_conversation(conversation_id: str) -> tuple[dict[str, Any], dict[str, Any] | None]:
    """Return (response, pending_summary_retain). The second value is None if already ended."""
    conversation = db.get_conversation(conversation_id)
    if conversation is None:
        raise ApiError(
            404,
            "conversation_not_found",
            "That conversation doesn't exist. Start a new one.",
        )

    existing_summary = db.get_summary(conversation_id)
    ended_at = conversation["ended_at"]
    pending: dict[str, Any] | None = None

    if ended_at is None or existing_summary is None:
        ended_at = ended_at or db.utc_now_iso()
        summary = existing_summary or _build_summary(conversation_id, conversation)
        db.end_conversation(conversation_id, ended_at=ended_at, summary=summary)
        if existing_summary is None:
            pending = {"summary": summary, "conversation_id": conversation_id}

    summary = db.get_summary(conversation_id) or _build_summary(conversation_id, conversation)

    return (
        {
            "conversation_id": conversation_id,
            "ended_at": ended_at,
            "duration_seconds": _duration_seconds(conversation["started_at"], ended_at),
            "summary": summary,
        },
        pending,
    )


# ── The turn ────────────────────────────────────────────────────


def handle_message(
    conversation_id: str,
    text: str,
    memory_enabled: bool = True,
) -> dict[str, Any]:
    turn_started = time.perf_counter()
    deadline = turn_started + max(
        0.5, settings.turn_timeout_seconds - TURN_SAFETY_MARGIN_SECONDS
    )
    text = _validate_text(text)

    conversation = db.get_conversation(conversation_id)
    if conversation is None:
        raise ApiError(
            404,
            "conversation_not_found",
            "That conversation doesn't exist. Start a new one.",
        )
    if conversation["ended_at"] is not None:
        raise ApiError(409, "conversation_ended", "This chat has ended. Start a new one.")

    degraded: list[str] = []
    timings = {"extract": 0, "recall": 0, "reply": 0, "retain": 0, "total": 0}
    now = db.utc_now_iso()

    # 1. Store the scammer message.
    scammer_message_id = db.add_message(
        conversation_id,
        "scammer",
        text,
        created_at=now,
        memory_enabled=memory_enabled,
    )

    # 2. Extract IOCs, sharing the turn budget.
    extract_started = time.perf_counter()
    remaining = _remaining(deadline)
    try:
        if remaining <= 0.4:
            iocs, stage, used_regex = [], None, True
        else:
            iocs, stage, used_regex = extract_iocs(
                text, timeout=max(0.3, remaining - 0.3)
            )
    except Exception:
        logger.exception("IOC extraction failed unexpectedly")
        iocs, stage, used_regex = [], None, True
    timings["extract"] = _elapsed_ms(extract_started)
    if used_regex:
        degraded.append("extract_fallback_regex")

    # 3. Index them.
    db.set_message_stage(scammer_message_id, stage)
    try:
        db.upsert_iocs(conversation_id, scammer_message_id, iocs, seen_at=now)
    except Exception:
        logger.exception("IOC indexing failed for %s", conversation_id)

    # 4. Recall (memory on only), sharing what is left of the turn.
    recalled: list[dict[str, Any]] = []
    if memory_enabled:
        recall_started = time.perf_counter()
        remaining = _remaining(deadline)
        if remaining <= 0.5:
            logger.warning("no time left for recall; degrading this turn")
            degraded.append("recall_unavailable")
        else:
            try:
                recalled = memory.recall(
                    _recall_query(text, iocs),
                    timeout=max(0.5, remaining - 0.3),
                )
            except memory.MemoryUnavailable as exc:
                logger.warning("recall unavailable: %s", exc)
                degraded.append("recall_unavailable")
            except Exception:
                logger.exception("recall failed unexpectedly")
                degraded.append("recall_unavailable")
        timings["recall"] = _elapsed_ms(recall_started)

    # 5. Contradictions (exact DB checks, memory on only).
    flags: list[dict[str, Any]] = []
    if memory_enabled:
        try:
            flags = find_contradictions(iocs, conversation_id, recalled)
        except Exception:
            logger.exception("contradiction check failed")
        for flag in flags:
            try:
                db.record_contradiction(
                    conversation_id,
                    flag,
                    message_id=scammer_message_id,
                    created_at=now,
                )
            except Exception:
                logger.exception("failed to record contradiction")

    # 6. Reply as Ajji, with history and (if memory is on) recalled facts.
    reply_started = time.perf_counter()
    refreshed = db.get_conversation(conversation_id) or conversation
    system_prompt = persona.build_system_prompt(
        memories=recalled,
        contradictions=flags,
        stage=stage,
    )
    messages = [
        {"role": "system", "content": system_prompt},
        *persona.build_history_messages(refreshed["messages"], limit=HISTORY_LIMIT),
    ]
    reply_text, used_canned = _generate_reply(messages, deadline)
    timings["reply"] = _elapsed_ms(reply_started)
    if used_canned:
        degraded.append("reply_fallback_canned")

    reply_created_at = db.utc_now_iso()
    reply_id = db.add_message(
        conversation_id,
        "ajji",
        reply_text,
        created_at=reply_created_at,
    )

    # 8. Build the response.
    recalled_response = [_memory_for_response(item, iocs) for item in recalled]
    timings["retain"] = 0
    timings["total"] = sum(
        timings[key] for key in ("extract", "recall", "reply", "retain")
    )

    return {
        "conversation_id": conversation_id,
        "scammer_message_id": scammer_message_id,
        "reply": {
            "id": reply_id,
            "sender": "ajji",
            "text": reply_text,
            "created_at": reply_created_at,
        },
        "memory_enabled": bool(memory_enabled),
        "recalled_memories": recalled_response,
        "extracted_iocs": [{"type": ioc.type, "value": ioc.value} for ioc in iocs],
        "contradiction_flags": flags,
        "script_stage": stage,
        "timings_ms": timings,
        "degraded": list(dict.fromkeys(degraded)),
    }


# ── Background retention ────────────────────────────────────────


def retain_safely(text: str, conversation_id: str, stage: str | None) -> None:
    if not memory.is_configured():
        logger.info("retain skipped: Hindsight is not configured")
        return
    for attempt in range(RETAIN_ATTEMPTS):
        try:
            memory.retain_message(text, conversation_id=conversation_id, stage=stage)
            return
        except memory.MemoryUnavailable as exc:
            logger.warning("retain attempt %s/%s failed: %s", attempt + 1, RETAIN_ATTEMPTS, exc)
            if attempt < RETAIN_ATTEMPTS - 1:
                time.sleep(RETAIN_BACKOFF_SECONDS * (attempt + 1))
    logger.error("retain gave up for %s", conversation_id)


def retain_summary_safely(summary: dict[str, Any], conversation_id: str) -> None:
    if not memory.is_configured():
        logger.info("summary retain skipped: Hindsight is not configured")
        return
    for attempt in range(RETAIN_ATTEMPTS):
        try:
            memory.retain_summary(summary, conversation_id=conversation_id)
            return
        except memory.MemoryUnavailable as exc:
            logger.warning(
                "summary retain attempt %s/%s failed: %s",
                attempt + 1,
                RETAIN_ATTEMPTS,
                exc,
            )
            if attempt < RETAIN_ATTEMPTS - 1:
                time.sleep(RETAIN_BACKOFF_SECONDS * (attempt + 1))
    logger.error("summary retain gave up for %s", conversation_id)
