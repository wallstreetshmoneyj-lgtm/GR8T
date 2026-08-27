"""Environment/config loading. All secrets come from .env (never committed).

Usage: `from core.config import settings`.
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

from dotenv import load_dotenv

# Repo root = parent of this file's directory. Everything (db, cache, seeds)
# lives under the repo so a Codespace checkout is fully self-contained.
ROOT_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT_DIR / "data"

load_dotenv(ROOT_DIR / ".env")


def _env(name: str, default: str = "") -> str:
    return os.environ.get(name, default).strip()


@dataclass(frozen=True)
class Settings:
    # SEC requires a real contact identity in the User-Agent (fair-access policy).
    # Fetches against SEC hosts fail loudly if this is missing — see http_client.py.
    sec_user_agent: str = field(default_factory=lambda: _env("SEC_USER_AGENT"))

    # Phase 2+ keys; blank is fine in Phase 1.
    finnhub_api_key: str = field(default_factory=lambda: _env("FINNHUB_API_KEY"))
    fred_api_key: str = field(default_factory=lambda: _env("FRED_API_KEY"))
    smtp_host: str = field(default_factory=lambda: _env("SMTP_HOST"))
    smtp_port: int = field(default_factory=lambda: int(_env("SMTP_PORT", "587") or 587))
    smtp_user: str = field(default_factory=lambda: _env("SMTP_USER"))
    smtp_pass: str = field(default_factory=lambda: _env("SMTP_PASS"))
    alert_email_to: str = field(default_factory=lambda: _env("ALERT_EMAIL_TO"))
    anthropic_api_key: str = field(default_factory=lambda: _env("ANTHROPIC_API_KEY"))

    timezone: str = field(default_factory=lambda: _env("TZ", "America/Chicago") or "America/Chicago")

    # Paths (not env-configurable on purpose; keep the layout boring).
    root_dir: Path = ROOT_DIR
    data_dir: Path = DATA_DIR
    seed_dir: Path = DATA_DIR / "seed"
    content_dir: Path = DATA_DIR / "content"
    cache_dir: Path = DATA_DIR / "cache"
    reports_dir: Path = DATA_DIR / "reports"
    db_path: Path = DATA_DIR / "terminal.db"


settings = Settings()
