# outreach_app/ingest/org_profile_ai.py
from __future__ import annotations

import json
import os
from typing import Any, Dict

import requests


FIELDS = [
    "org_name",
    "org_website",
    "contact_name",
    "contact_email",
    "contact_phone",
    "mission",
    "programs",
    "event_summary",
    "sponsorship_ask",
    "sponsorship_tiers",
    "audience",
    "impact_metrics",
]


def _clean_payload(d: Dict[str, Any]) -> Dict[str, str]:
    out: Dict[str, str] = {}
    for k in FIELDS:
        v = d.get(k, "")
        if v is None:
            v = ""
        out[k] = str(v).strip()
    return out


def extract_org_profile_with_llm(raw_pdf_text: str) -> Dict[str, str]:
    """
    Uses an OpenAI-compatible chat completions endpoint (OpenAI/DeepSeek/etc.)
    Returns dict with keys in FIELDS.
    """
    provider = os.getenv("LLM_PROVIDER", "none").lower()
    if provider == "none":
        # fallback: empty (user fills manually)
        return {k: "" for k in FIELDS}

    base_url = os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1").rstrip("/")
    api_key = os.getenv("OPENAI_API_KEY", "").strip()
    model = os.getenv("OPENAI_MODEL", "gpt-4o-mini").strip()

    if not api_key:
        raise RuntimeError("Missing OPENAI_API_KEY in .env")

    # Keep prompt size reasonable (PDFs can be huge)
    text = (raw_pdf_text or "").strip()
    text = text[:25000]

    system = (
        """You extract structured sponsorship/outreach information from raw proposal PDF text.

Rules:
- Return ONLY valid JSON. No markdown, no explanations.
- If a field is not present, return "" (empty string).
- Do NOT invent facts, dates, numbers, sponsors, or metrics. If unsure, keep it "".
- Prefer short, clean phrasing that can be pasted into an email.
- Keep each field concise:
  - org_name, org_website, contact_*: short
  - mission: <= 2 sentences
  - programs: <= 6 bullet lines (use newline-separated bullets)
  - event_summary: <= 6 sentences or newline bullets
  - sponsorship_ask: <= 6 bullet lines
  - sponsorship_tiers: if tiers exist, format as newline bullets "Tier - Benefits - Price" else ""
  - audience: <= 4 bullet lines with any numbers/demographics if present
  - impact_metrics: <= 6 bullet lines with numbers if present

Output schema keys (must match exactly):
org_name, org_website, contact_name, contact_email, contact_phone,
mission, programs, event_summary, sponsorship_ask, sponsorship_tiers,
audience, impact_metrics

Also include an "evidence" object with short supporting snippets:
evidence = {
  "org_name": "...",
  "mission": "...",
  "programs": "...",
  "event_summary": "...",
  "sponsorship_ask": "...",
  "sponsorship_tiers": "...",
  "audience": "...",
  "impact_metrics": "..."
}
Each evidence value should be a short quote or near-quote from the PDF text (<= 200 chars each). If not found, "".
"""
    )

    user = f"""
You are given raw text extracted from a sponsorship proposal PDF.
Your job: extract structured information and return ONLY valid JSON.

STRICT RULES:
- Output must be JSON only. No markdown, no commentary, no extra text.
- Do NOT invent anything. If not clearly present, return "".
- Prefer copying near-exact phrases from the PDF (lightly cleaned).
- Keep outputs concise and email-ready.
- Use newline bullet format for multi-item fields (programs, sponsorship_ask, sponsorship_tiers, audience, impact_metrics).
- If the PDF text contains multiple events/programs, focus on the PRIMARY event described.

Return JSON with EXACT keys (no additional keys):
{FIELDS}

FIELD GUIDANCE:
- org_name: official organization/club/project name.
- org_website: official website URL (if any).
- contact_name / contact_email / contact_phone: only if explicitly present; otherwise "".
- mission: 1–2 sentences summarizing mission/vision.
- programs: up to 6 bullets describing ongoing programs/initiatives (one per line).
- event_summary: 4–8 lines max; include: what the event is, when/where (if present), purpose, format, who participates.
- sponsorship_ask: up to 6 bullets describing what you want from sponsors (cash/in-kind/media/venue/speakers/etc) + what sponsors get.
- sponsorship_tiers: if tiers exist, format each line as:
  "Tier name — price (if shown) — key benefits"
  If no tiers are mentioned, return "".
- audience: up to 4 bullets; include numbers/demographics/reach if present.
- impact_metrics: up to 6 bullets; only include quantified results or clearly stated outcomes (numbers, past impact, KPIs).

QUALITY CHECK BEFORE YOU RETURN:
- Every key in {FIELDS} must exist in the JSON.
- Values must be strings (even bullet lists are a single string with newlines).
- Empty string "" for unknown fields.
- No trailing commas in JSON.

PDF_TEXT:
{text}
"""

    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        "temperature": 0.2,
    }

    r = requests.post(
        f"{base_url}/chat/completions",
        headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
        json=payload,
        timeout=60,
    )
    r.raise_for_status()
    content = r.json()["choices"][0]["message"]["content"]

    try:
        data = json.loads(content)
    except json.JSONDecodeError:
        # Try to salvage if model wrapped JSON with text
        start = content.find("{")
        end = content.rfind("}")
        if start == -1 or end == -1 or end <= start:
            raise RuntimeError(f"LLM did not return JSON. Got: {content[:300]}")
        data = json.loads(content[start : end + 1])

    return _clean_payload(data)