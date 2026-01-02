from __future__ import annotations

from outreach_app.writer.llm import json_from_llm, LLMError


def summarize_company_pages(company_name: str, pages: list[tuple[str, str]], language: str = "vi") -> dict:
    """LLM-assisted or heuristic summary from website pages."""
    # Heuristic fallback if no LLM
    joined = "\n\n".join([f"SOURCE: {u}\n{t[:4000]}" for u, t in pages])[:12000]

    prompt = {
        "role": "user",
        "content": f"""Summarize this company in JSON for sponsorship outreach.

Language: {language}
Company: {company_name}

Pages text (multiple sources):
{joined}

Return JSON keys:
- summary
- mission_values
- csr_focus
- recent_initiatives
- alignment_angles (how they might align with an NGO/event sponsorship)
- sources (array of objects: url, note)
""",
    }
    try:
        return json_from_llm([prompt], schema_hint="company_profile")
    except LLMError:
        # lightweight fallback
        sources = [{"url": u, "note": "website page"} for u, _ in pages[:5]]
        return {
            "summary": f"{company_name} (auto summary from website pages).",
            "mission_values": "",
            "csr_focus": "",
            "recent_initiatives": "",
            "alignment_angles": "Potential alignment on community impact / CSR.",
            "sources": sources,
        }
