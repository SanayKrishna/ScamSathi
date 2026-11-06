"""Environment-backed settings, loaded once at import time (B0).

Every module reads settings from here. Nothing else calls os.getenv.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent

# Prefer backend/.env, then fall back to a .env in the current directory.
load_dotenv(BASE_DIR / ".env")
load_dotenv()


def _str(name: str, default: str = "") -> str:
    return (os.getenv(name) or default).strip()


def _float(name: str, default: float) -> float:
    try:
        return float(_str(name, str(default)))
    except ValueError:
        return default


def _int(name: str, default: int) -> int:
    try:
        return int(_str(name, str(default)))
    except ValueError:
        return default


def _bool(name: str, default: bool) -> bool:
    return _str(name, "true" if default else "false").lower() in {"1", "true", "yes", "on"}


def _path(name: str, default: str) -> Path:
    raw = Path(_str(name, default)).expanduser()
    return raw if raw.is_absolute() else (BASE_DIR / raw)


def _origins(name: str, default: str) -> tuple[str, ...]:
    return tuple(part.strip() for part in _str(name, default).split(",") if part.strip())


@dataclass(frozen=True)
class Settings:
    persona_name: str

    hindsight_url: str
    hindsight_api_key: str
    hindsight_bank_id: str
    hindsight_timeout_seconds: float
    hindsight_max_attempts: int

    groq_api_key: str
    groq_base_url: str
    groq_model: str
    groq_fallback_model: str
    groq_timeout_seconds: float

    turn_timeout_seconds: float
    db_path: Path
    cors_origins: tuple[str, ...]

    seed_base_url: str
    seed_conversations: int
    seed_use_llm: bool
    seed_delay_seconds: float
    seed_timeout_seconds: float

    @property
    def hindsight_configured(self) -> bool:
        return bool(self.hindsight_url)

    @property
    def llm_configured(self) -> bool:
        return bool(self.groq_api_key)


settings = Settings(
    persona_name=_str("PERSONA_NAME", "Ajji"),
    hindsight_url=_str("HINDSIGHT_URL"),
    hindsight_api_key=_str("HINDSIGHT_API_KEY"),
    hindsight_bank_id=_str("HINDSIGHT_BANK_ID", "scam-intel"),
    hindsight_timeout_seconds=_float("HINDSIGHT_TIMEOUT_SECONDS", 8.0),
    hindsight_max_attempts=_int("HINDSIGHT_MAX_ATTEMPTS", 2),
    groq_api_key=_str("GROQ_API_KEY"),
    groq_base_url=_str("GROQ_BASE_URL", "https://api.groq.com/openai/v1").rstrip("/"),
    groq_model=_str("GROQ_MODEL", "openai/gpt-oss-120b"),
    groq_fallback_model=_str("GROQ_FALLBACK_MODEL", "qwen/qwen3.8-27b"),
    groq_timeout_seconds=_float("GROQ_TIMEOUT_SECONDS", 10.0),
    turn_timeout_seconds=_float("TURN_TIMEOUT_SECONDS", 8.0),
    db_path=_path("DB_PATH", "./ajji.db"),
    cors_origins=_origins("CORS_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173"),
    seed_base_url=_str("SEED_BASE_URL", "http://127.0.0.1:8000").rstrip("/"),
    seed_conversations=max(1, _int("SEED_CONVERSATIONS", 20)),
    seed_use_llm=_bool("SEED_USE_LLM", True),
    seed_delay_seconds=max(0.0, _float("SEED_DELAY_SECONDS", 1.0)),
    seed_timeout_seconds=max(10.0, _float("SEED_TIMEOUT_SECONDS", 120.0)),
)
