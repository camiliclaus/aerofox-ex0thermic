"""Runtime configuration from environment variables (see .env.example)."""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def _load_dotenv(path: Path) -> None:
    """Minimal .env reader so Windows users need no extra package. Existing env wins."""
    if not path.exists():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))


_load_dotenv(ROOT / ".env")


def _int(name: str, default: int) -> int:
    try:
        return int(os.environ.get(name, default))
    except ValueError:
        return default


@dataclass(frozen=True)
class Settings:
    root: Path = ROOT
    data_dir: Path = ROOT / "data"
    frontend_dir: Path = ROOT / "frontend"
    snapshot_version: str = os.environ.get("AEROFOX_SNAPSHOT", "2026-11-14.1")
    app_version: str = "1.1.1"
    # A team-controlled loopback llama.cpp service is the default inference engine.
    llm_enabled: bool = os.environ.get("AEROFOX_LLM", "auto").lower() != "off"
    model: str = os.environ.get("AEROFOX_MODEL", "aerofox-qwen-1.5b")
    llm_url: str = os.environ.get("AEROFOX_LLM_URL", "http://127.0.0.1:8793")
    llm_timeout_s: float = float(os.environ.get("AEROFOX_LLM_TIMEOUT", "65"))
    llm_queue_wait_s: float = float(os.environ.get("AEROFOX_LLM_QUEUE_WAIT", "25"))
    turn_deadline_s: float = float(os.environ.get("AEROFOX_TURN_DEADLINE", "100"))
    # Abuse and cost protection for the public demo
    max_message_chars: int = _int("AEROFOX_MAX_MESSAGE_CHARS", 4000)
    rate_per_minute: int = _int("AEROFOX_RATE_PER_MINUTE", 12)
    llm_daily_turn_budget: int = _int("AEROFOX_LLM_DAILY_TURNS", 500)
    max_sessions: int = _int("AEROFOX_MAX_SESSIONS", 2000)
    session_ttl_s: int = _int("AEROFOX_SESSION_TTL", 6 * 3600)
    cors_origins: tuple[str, ...] = field(default_factory=lambda: tuple(
        o.strip() for o in os.environ.get("AEROFOX_CORS_ORIGINS", "").split(",") if o.strip()))

settings = Settings()
