from __future__ import annotations

from outreach_app.writer.llm import json_from_llm, LLMError


def build_personalization_brief(
    org_profile: dict,
    company_profile: dict,
    language: str = "vi",
) -> dict:
    """LLM -> structured brief used to write the email."""
    prompt = {
        "role": "user",
        "content": (
            f"""You are writing a sponsorship outreach email. Create a personalization brief in JSON.

Language: {language}

Org/Event info:
{org_profile}

Company info:
{company_profile}

Return JSON with keys:
- company_angle (string)
- why_match (array of 2-3 bullets)
- best_cta (string)
- benefits (array of 3 bullets)
- subject_ideas (array of 3 short subject lines)
"""
        ),
    }
    try:
        return json_from_llm([prompt], schema_hint="brief")
    except LLMError:
        # fallback: minimal brief
        return {
            "company_angle": company_profile.get("csr_focus") or company_profile.get("mission_values") or "phát triển bền vững / cộng đồng",
            "why_match": ["Cùng hướng đến tác động tích cực cho cộng đồng."],
            "best_cta": "một cuộc gọi 15 phút",
            "benefits": [
                "Gắn thương hiệu với chương trình có tác động xã hội rõ ràng",
                "Hiện diện trên kênh truyền thông của chương trình",
                "Báo cáo/ghi nhận tác động sau chương trình",
            ],
            "subject_ideas": [
                f"Đề xuất đồng hành tài trợ cùng {org_profile.get('org_name','chương trình')}",
                f"Cơ hội hợp tác CSR: {org_profile.get('org_name','chương trình')}",
                "Kết nối hợp tác tài trợ",
            ],
        }
