from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Iterable


EMAIL_RE = re.compile(r"([a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,})")

ROLE_KEYWORDS = {
    "csr": ["csr", "sustainab", "esg", "community", "impact", "foundation", "responsibility"],
    "partnership": ["partner", "partnership", "alliances", "collab", "sponsor", "sponsorship"],
    "marketing": ["marketing", "brand", "communications", "comms", "pr", "media"],
}

GENERIC_INBOX_HINTS = ["info@", "contact@", "hello@", "support@", "enquiry@", "inquiry@"]

@dataclass
class FoundEmail:
    email: str
    found_on: str
    role_guess: str
    confidence: float


def extract_emails(text: str) -> list[str]:
    emails = set(m.group(1) for m in EMAIL_RE.finditer(text or ""))
    # basic cleanup
    cleaned = []
    for e in emails:
        e = e.strip().strip(".,;:()[]{}<>\"'")
        cleaned.append(e)
    return sorted(set(cleaned))


def guess_role(email: str, context_url: str, page_text: str) -> tuple[str, float]:
    e = email.lower()
    url = (context_url or "").lower()
    text = (page_text or "").lower()

    score = 0.0
    role = "unknown"

    for r, kws in ROLE_KEYWORDS.items():
        if any(k in e for k in kws) or any(k in url for k in kws):
            role = r
            score += 0.6
            break

    if any(h in e for h in GENERIC_INBOX_HINTS):
        score += 0.2
        if role == "unknown":
            role = "generic"

    # if page contains sponsorship/partnership terms, increase confidence
    if any(k in text for k in ["sponsor", "sponsorship", "partnership", "collaborat", "csr", "esg", "foundation"]):
        score += 0.2

    return role, min(1.0, score)


def find_contacts_from_pages(pages: list[tuple[str, str]]) -> list[FoundEmail]:
    """pages: list of (url, text)."""
    found: dict[str, FoundEmail] = {}
    for url, txt in pages:
        for e in extract_emails(txt):
            role, conf = guess_role(e, url, txt)
            # keep best confidence if duplicates
            if e not in found or conf > found[e].confidence:
                found[e] = FoundEmail(email=e, found_on=url, role_guess=role, confidence=conf)
    # rank: confidence desc, then role preference
    role_weight = {"csr": 3, "partnership": 3, "marketing": 2, "generic": 1, "unknown": 0}
    return sorted(found.values(), key=lambda x: (x.confidence, role_weight.get(x.role_guess, 0)), reverse=True)
