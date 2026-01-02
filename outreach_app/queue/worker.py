from __future__ import annotations

import time
import argparse
from datetime import datetime

from sqlmodel import select

from outreach_app.config import settings
from outreach_app.db.database import init_db, get_session
from outreach_app.db.models import Draft, DraftStatus, SendAttempt, Contact, Company, Campaign
from outreach_app.sender.mime_builder import build_message
from outreach_app.sender.smtp_sender import send_smtp, SMTPConfigError


def run_worker(loop: bool = True, once: bool = False) -> None:
    init_db()
    while True:
        with get_session() as s:
            # pick one approved draft
            draft = s.exec(select(Draft).where(Draft.status == DraftStatus.APPROVED).order_by(Draft.updated_at.asc())).first()
            if not draft:
                if once:
                    return
                time.sleep(5)
                continue

            company = s.get(Company, draft.company_id)
            contact = s.get(Contact, draft.contact_id) if draft.contact_id else None

            # campaign to get attachments + org profile
            # simplest: find via company.campaign_id
            campaign = s.get(Campaign, company.campaign_id) if company else None
            org = campaign.org_profile if campaign else None
            to_email = contact.email if contact else None

            if not to_email:
                draft.status = DraftStatus.FAILED
                draft.updated_at = datetime.utcnow()
                s.add(draft)
                s.add(SendAttempt(draft_id=draft.id, status="failed", error="No recipient email selected"))
                s.commit()
                continue

            from_email = settings.SMTP_FROM or settings.SMTP_USER
            msg = build_message(
                subject=draft.subject,
                body_text=draft.body_text,
                to_email=to_email,
                from_email=from_email,
                attachments=(campaign.attachment_paths if campaign else []),
            )

            try:
                provider_id = send_smtp(msg)
                draft.status = DraftStatus.SENT
                draft.updated_at = datetime.utcnow()
                s.add(draft)
                s.add(SendAttempt(draft_id=draft.id, status="sent", provider="smtp", provider_message_id=provider_id))
                s.commit()
                print(f"[SENT] {company.name} -> {to_email} | subject={draft.subject}")
                time.sleep(settings.RATE_LIMIT_SECONDS)
            except Exception as e:
                draft.status = DraftStatus.FAILED
                draft.updated_at = datetime.utcnow()
                s.add(draft)
                s.add(SendAttempt(draft_id=draft.id, status="failed", provider="smtp", error=str(e)[:500]))
                s.commit()
                print(f"[FAILED] {company.name} -> {to_email}: {e}")
                time.sleep(min(30, settings.RATE_LIMIT_SECONDS))

        if once:
            return


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--once", action="store_true", help="Send at most one approved draft then exit.")
    args = parser.parse_args()
    run_worker(loop=not args.once, once=args.once)

if __name__ == "__main__":
    main()
