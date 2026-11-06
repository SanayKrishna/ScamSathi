"""ScamSathi backend entry point.

Owns the app factory concerns that every route depends on: CORS, the /health
contract, the single ApiError shape from API.md, and the conversation routes.
"""

from __future__ import annotations

import logging
import sqlite3
from contextlib import asynccontextmanager, closing
from typing import Any

from fastapi import BackgroundTasks, FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from starlette.concurrency import run_in_threadpool
from starlette.exceptions import HTTPException as StarletteHTTPException

import agent
import db
import demo
import memory
from config import settings
from errors import ApiError, error_body

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
logger = logging.getLogger("scamsathi")


# ── Request models ──────────────────────────────────────────────


class CreateConversationRequest(BaseModel):
    persona: str = "ajji"


class SendMessageRequest(BaseModel):
    sender: str = "scammer"
    text: str
    memory_enabled: bool = True


class ResetRequest(BaseModel):
    confirm: str = ""


@asynccontextmanager
async def lifespan(_: FastAPI):
    db.init_db()
    logger.info("SQLite ready at %s", settings.db_path)

    # Create the shared memory bank before the first turn. A down Hindsight
    # must not stop the app from starting; recall will degrade per turn.
    if memory.is_configured():
        try:
            # Hindsight's sync client creates its own loop; keep it off the
            # server's event loop.
            await run_in_threadpool(memory.ensure_bank)
            logger.info("Hindsight bank %s ready", settings.hindsight_bank_id)
        except memory.MemoryUnavailable as exc:
            logger.warning("Hindsight bank not ready at startup: %s", exc)

    yield


app = FastAPI(
    title="ScamSathi API",
    version="0.1.0",
    description="Ajji remembers every scammer. Simulated data only.",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=list(settings.cors_origins),
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── Error handlers ──────────────────────────────────────────────


@app.exception_handler(ApiError)
async def handle_api_error(_: Request, exc: ApiError) -> JSONResponse:
    return JSONResponse(status_code=exc.status_code, content=error_body(exc.code, exc.message))


@app.exception_handler(RequestValidationError)
async def handle_validation_error(_: Request, exc: RequestValidationError) -> JSONResponse:
    logger.info("request validation failed: %s", exc.errors())
    return JSONResponse(
        status_code=400,
        content=error_body("invalid_request", "The request body is not valid."),
    )


@app.exception_handler(StarletteHTTPException)
async def handle_http_error(_: Request, exc: StarletteHTTPException) -> JSONResponse:
    codes = {404: "not_found", 405: "method_not_allowed"}
    message = "That resource doesn't exist." if exc.status_code == 404 else str(exc.detail)
    return JSONResponse(
        status_code=exc.status_code,
        content=error_body(codes.get(exc.status_code, "http_error"), message),
    )


@app.exception_handler(Exception)
async def handle_unexpected_error(_: Request, exc: Exception) -> JSONResponse:
    # Log the traceback, never return it.
    logger.exception("unhandled error: %s", exc)
    return JSONResponse(
        status_code=500,
        content=error_body("internal", "Something went wrong. Try again."),
    )


# ── Health ──────────────────────────────────────────────────────


def _db_ok() -> bool:
    try:
        settings.db_path.parent.mkdir(parents=True, exist_ok=True)
        with closing(sqlite3.connect(settings.db_path, timeout=1)) as conn:
            conn.execute("SELECT 1")
        return True
    except Exception:
        logger.exception("database health check failed")
        return False


@app.get("/health")
def health() -> dict[str, str]:
    # B0 rule: a dependency is "ok" when it is configured (and the db opens).
    dependencies = {
        "hindsight": "ok" if settings.hindsight_configured else "down",
        "llm": "ok" if settings.llm_configured else "down",
        "db": "ok" if _db_ok() else "down",
    }
    status = "ok" if all(value == "ok" for value in dependencies.values()) else "degraded"
    return {"status": status, **dependencies}


# ── Read-only UI endpoints ──────────────────────────────────────


@app.get("/network")
def network(conversation_id: str | None = None) -> dict[str, Any]:
    return db.get_network(conversation_id)


@app.get("/stats")
def stats() -> dict[str, Any]:
    return db.get_stats()


# ── Conversations ───────────────────────────────────────────────


@app.post("/conversations", status_code=201)
def create_conversation(payload: CreateConversationRequest | None = None) -> dict[str, Any]:
    return agent.create_conversation(payload.persona if payload else "ajji")


@app.post("/conversations/{conversation_id}/message")
def send_message(
    conversation_id: str,
    payload: SendMessageRequest,
    background_tasks: BackgroundTasks,
) -> dict[str, Any]:
    if payload.sender != "scammer":
        raise ApiError(
            400,
            "invalid_message",
            "Only sender 'scammer' is accepted for now.",
        )

    response = agent.handle_message(conversation_id, payload.text, payload.memory_enabled)

    # Retain runs after the response is sent, even when memory is off (step 7).
    background_tasks.add_task(
        agent.retain_safely,
        payload.text.strip(),
        conversation_id,
        response["script_stage"],
    )
    return response


@app.post("/conversations/{conversation_id}/end")
def end_conversation(
    conversation_id: str,
    background_tasks: BackgroundTasks,
) -> dict[str, Any]:
    response, pending_retain = agent.end_conversation(conversation_id)
    if pending_retain is not None:
        background_tasks.add_task(
            agent.retain_summary_safely,
            pending_retain["summary"],
            conversation_id,
        )
    return response


@app.get("/conversations/{conversation_id}")
def get_conversation(conversation_id: str) -> dict[str, Any]:
    return agent.get_conversation(conversation_id)


# ── Demo controls ───────────────────────────────────────────────


@app.post("/demo/seed", status_code=202)
def seed_demo() -> dict[str, Any]:
    return demo.start_seed(settings.seed_conversations)


@app.get("/demo/seed/{job_id}")
def seed_status(job_id: str) -> dict[str, Any]:
    status = demo.get_seed_status(job_id)
    if status is None:
        raise ApiError(404, "not_found", "That seed job doesn't exist.")
    return status


@app.post("/demo/reset")
def reset_demo(payload: ResetRequest) -> dict[str, str]:
    if payload.confirm != "RESET":
        raise ApiError(400, "reset_not_confirmed", "Type RESET to confirm.")

    demo.ensure_not_running()

    if memory.is_configured():
        try:
            memory.reset_bank()
        except memory.MemoryUnavailable as exc:
            logger.warning("memory bank reset failed: %s", exc)
            raise ApiError(
                500,
                "internal",
                "Could not reset the memory bank. Check Hindsight and try again.",
            ) from exc

    db.reset_db()
    demo.reset_seed()
    return {"status": "reset", "bank_id": settings.hindsight_bank_id}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("main:app", host="127.0.0.1", port=8000, reload=True)
