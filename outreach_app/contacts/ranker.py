from __future__ import annotations

from outreach_app.contacts.finder import FoundEmail


def pick_top_contacts(found: list[FoundEmail], max_n: int = 3) -> list[FoundEmail]:
    """Pick top N while avoiding obviously personal emails unless high confidence."""
    picked = []
    for f in found:
        local = f.email.split("@", 1)[0]
        looks_personal = "." in local or "_" in local
        if looks_personal and f.confidence < 0.8:
            continue
        picked.append(f)
        if len(picked) >= max_n:
            break
    return picked
