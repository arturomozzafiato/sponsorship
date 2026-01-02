from __future__ import annotations

import json
import requests
from dataclasses import dataclass
from typing import Any, Optional

from outreach_app.config import settings


class LLMError(RuntimeError):
    pass


def _default_base_url() -> str:
    if settings.LLM_PROVIDER == "openai":
        return "https://api.openai.com/v1"
    if settings.LLM_PROVIDER == "deepseek":
        return "https://api.deepseek.com/v1"
    return settings.LLM_BASE_URL.strip() or ""


def chat_completion(messages: list[dict[str, str]], temperature: float = 0.4, max_tokens: int = 900) -> str:
    """OpenAI-compatible Chat Completions call. Works for OpenAI or DeepSeek if base_url + key are set."""
    if settings.LLM_PROVIDER == "none":
        raise LLMError("LLM_PROVIDER=none (offline mode).")

    base = settings.LLM_BASE_URL.strip() or _default_base_url()
    if not base:
        raise LLMError("Missing LLM_BASE_URL. Set LLM_BASE_URL to an OpenAI-compatible endpoint.")
    if not settings.LLM_API_KEY:
        raise LLMError("Missing LLM_API_KEY.")

    url = base.rstrip("/") + "/chat/completions"
    payload: dict[str, Any] = {
        "model": settings.LLM_MODEL,
        "messages": messages,
        "temperature": temperature,
        "max_tokens": max_tokens,
    }
    headers = {
        "Authorization": f"Bearer {settings.LLM_API_KEY}",
        "Content-Type": "application/json",
    }
    resp = requests.post(url, headers=headers, json=payload, timeout=settings.LLM_TIMEOUT_S)
    if resp.status_code >= 400:
        raise LLMError(f"LLM error {resp.status_code}: {resp.text[:400]}")
    data = resp.json()
    try:
        return data["choices"][0]["message"]["content"]
    except Exception as e:
        raise LLMError(f"Unexpected LLM response: {data}") from e


def json_from_llm(messages: list[dict[str, str]], schema_hint: str, temperature: float = 0.2, max_tokens: int = 1200) -> dict:
    """Ask the LLM to return JSON only; attempts to parse robustly."""
    sys = {
        "role": "system",
        "content": "Return ONLY valid JSON. No markdown, no commentary.",
    }
    out = chat_completion([sys, *messages], temperature=temperature, max_tokens=max_tokens)
    # Extract first JSON object in case of minor wrapper
    start = out.find("{")
    end = out.rfind("}")
    if start == -1 or end == -1:
        raise LLMError(f"No JSON found. Output: {out[:400]}")
    raw = out[start:end+1]
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        # last attempt: remove trailing commas
        raw2 = raw.replace(",}", "}").replace(",]", "]")
        return json.loads(raw2)
