from __future__ import annotations

from outreach_app.writer.llm import chat_completion, LLMError
from outreach_app.writer.templates import VI_TEMPLATE, EN_TEMPLATE


def write_email_with_llm(org: dict, company: dict, brief: dict, language: str = "vi") -> tuple[str, str, str]:
    """Return (subject, body_text, personalization_notes)"""
    prompt = {
        "role": "user",
        "content": (
            f"""Write a concise sponsorship outreach email.

Language: {language}
Constraints:
- 120-180 words
- 1 clear ask (CTA)
- Mention attachment (sponsorship deck)
- Use facts only from the provided org/event + company profile (no hallucination)
- Friendly, professional tone

Org/Event:
{org}

Company:
{company}

Personalization brief:
{brief}

Return:
1) Subject line
2) Email body (plain text)

Separate subject and body with a blank line.
"""
        ),
    }
    try:
        out = chat_completion([prompt], temperature=0.4, max_tokens=700)
        parts = out.strip().split("\n\n", 1)
        if len(parts) == 1:
            subject = brief.get("subject_ideas", ["Hợp tác tài trợ"])[0]
            body = parts[0]
        else:
            subject, body = parts[0].strip(), parts[1].strip()
        notes = "LLM-generated with brief."
        return subject, body, notes
    except LLMError:
        return write_email_template(org, company, brief, language=language)


def write_email_template(org: dict, company: dict, brief: dict, language: str = "vi") -> tuple[str, str, str]:
    tpl = VI_TEMPLATE if language == "vi" else EN_TEMPLATE
    subject = (brief.get("subject_ideas") or ["Sponsorship partnership"])[0]

    def pick(idx: int, default: str) -> str:
        arr = brief.get("benefits") or []
        return arr[idx] if idx < len(arr) else default

    body = tpl.format(
        contact_or_team=company.get("contact_name") or "anh/chị" if language == "vi" else "there",
        contact_name=org.get("contact_name") or "Team",
        org_name=org.get("org_name") or "our organization",
        contact_email=org.get("contact_email") or "",
        company_name=company.get("name") or "your company",
        company_angle=brief.get("company_angle") or "cộng đồng",
        event_name_or_summary=org.get("event_summary") or "program",
        sponsorship_ask_short=(org.get("sponsorship_ask") or "support our program").split("\n")[0][:140],
        benefit_1=pick(0, "Brand exposure to a relevant audience"),
        benefit_2=pick(1, "Meaningful community impact"),
        benefit_3=pick(2, "Post-event impact reporting"),
        cta=brief.get("best_cta") or ("một cuộc gọi 15 phút" if language == "vi" else "a 15-minute call"),
    )
    return subject, body, "Template-generated (offline fallback)."
