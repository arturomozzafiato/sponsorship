from __future__ import annotations

import os
from dataclasses import dataclass
from dotenv import load_dotenv

load_dotenv()

@dataclass(frozen=True)
class Settings:
    # Storage
    DB_URL: str = os.getenv("DB_URL", "sqlite:///outreach.db")

    # LLM (OpenAI-compatible)
    LLM_PROVIDER: str = os.getenv("LLM_PROVIDER", "none")  # none|openai|deepseek|custom
    LLM_API_KEY: str | None = os.getenv("LLM_API_KEY")
    LLM_BASE_URL: str = os.getenv("LLM_BASE_URL", "")  # e.g., https://api.openai.com/v1 or https://api.deepseek.com/v1
    LLM_MODEL: str = os.getenv("LLM_MODEL", "gpt-4o-mini")  # e.g., deepseek-chat, deepseek-reasoner
    LLM_TIMEOUT_S: int = int(os.getenv("LLM_TIMEOUT_S", "60"))

    # Email (SMTP) - simplest local sending option
    SMTP_HOST: str = os.getenv("SMTP_HOST", "")
    SMTP_PORT: int = int(os.getenv("SMTP_PORT", "587"))
    SMTP_USER: str = os.getenv("SMTP_USER", "")
    SMTP_PASS: str = os.getenv("SMTP_PASS", "")
    SMTP_FROM: str = os.getenv("SMTP_FROM", "")  # if empty, defaults to SMTP_USER
    SMTP_USE_TLS: bool = os.getenv("SMTP_USE_TLS", "true").lower() == "true"

    # Throttling
    RATE_LIMIT_SECONDS: int = int(os.getenv("RATE_LIMIT_SECONDS", "60"))

    # Defaults
    DEFAULT_LANGUAGE: str = os.getenv("DEFAULT_LANGUAGE", "vi")  # vi|en

settings = Settings()
