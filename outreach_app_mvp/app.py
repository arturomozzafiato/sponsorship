from __future__ import annotations

import os
import time
import hashlib
from datetime import datetime
from pathlib import Path

import pandas as pd
import streamlit as st
from sqlmodel import select


from outreach_app.config import settings
from outreach_app.db.database import init_db, get_session
from outreach_app.db.models import (
    OrgProfile, Campaign, Company, CompanyProfile, Contact, Draft, DraftStatus, SendAttempt
)
from outreach_app.ingest.proposal_pdf import extract_text_from_pdf
from outreach_app.research.scraper import fetch_url_text, guess_key_pages
from outreach_app.research.company_profile import summarize_company_pages
from outreach_app.contacts.finder import find_contacts_from_pages
from outreach_app.contacts.ranker import pick_top_contacts
from outreach_app.writer.brief import build_personalization_brief
from outreach_app.writer.email_writer import write_email_with_llm

# LLM org-profile extractor (OpenAI-compatible: OpenAI / DeepSeek / etc.)
from outreach_app.ingest.org_profile_ai import extract_org_profile_with_llm


# -------------------------
# Helpers
# -------------------------

ORG_FIELDS = [
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

def org_is_empty(org: OrgProfile) -> bool:
    """Treat org as empty if most key fields are blank."""
    if not org:
        return True
    keyvals = [
        (org.org_name or "").strip(),
        (org.mission or "").strip(),
        (org.programs or "").strip(),
        (org.event_summary or "").strip(),
        (org.sponsorship_ask or "").strip(),
        (org.audience or "").strip(),
    ]
    return all(v == "" for v in keyvals)

def fill_org_from_llm(org: OrgProfile, raw_pdf_text: str) -> OrgProfile:
    """
    Calls LLM to extract org fields and writes them into OrgProfile.
    """
    extracted = extract_org_profile_with_llm(raw_pdf_text)
    # extracted keys from org_profile_ai.py are: org_name, org_website, ...
    org.org_name = extracted.get("org_name", "") or ""
    org.org_website = extracted.get("org_website", "") or ""
    org.contact_name = extracted.get("contact_name", "") or ""
    org.contact_email = extracted.get("contact_email", "") or ""
    org.contact_phone = extracted.get("contact_phone", "") or ""
    org.mission = extracted.get("mission", "") or ""
    org.programs = extracted.get("programs", "") or ""
    org.event_summary = extracted.get("event_summary", "") or ""
    org.sponsorship_ask = extracted.get("sponsorship_ask", "") or ""
    org.sponsorship_tiers = extracted.get("sponsorship_tiers", "") or ""
    org.audience = extracted.get("audience", "") or ""
    org.impact_metrics = extracted.get("impact_metrics", "") or ""
    return org

def cache_pdf_text(pdf_bytes: bytes, filename: str) -> tuple[str, str]:
    """
    Returns (pdf_hash, raw_pdf_text). Caches extraction in st.session_state.
    """
    pdf_hash = hashlib.sha256(pdf_bytes).hexdigest()
    cache = st.session_state.setdefault("pdf_text_cache", {})

    if pdf_hash in cache:
        return pdf_hash, cache[pdf_hash]

    tmp_path = Path("uploads") / f"{int(time.time())}_{filename}"
    tmp_path.parent.mkdir(exist_ok=True)
    tmp_path.write_bytes(pdf_bytes)

    raw_text = extract_text_from_pdf(str(tmp_path), max_pages=40)
    cache[pdf_hash] = raw_text
    return pdf_hash, raw_text


# -------------------------
# App
# -------------------------

st.set_page_config(page_title="Outreach App (Local MVP)", layout="wide")
st.title("Outreach App (Local MVP)")
st.caption("Upload proposal PDF + company list → research → generate drafts → approve → send via SMTP worker.")

def ensure_db():
    init_db()

ensure_db()

tabs = st.tabs(["1) Setup Campaign", "2) Import Companies", "3) Research + Draft", "4) Approve + Send", "5) Logs"])


# Helper: list campaigns
def list_campaigns():
    with get_session() as s:
        return s.exec(select(Campaign).order_by(Campaign.created_at.desc())).all()

def get_campaign(campaign_id: int):
    with get_session() as s:
        c = s.get(Campaign, campaign_id)
        if c and c.org_profile_id:
            c.org_profile = s.get(OrgProfile, c.org_profile_id)
        return c


# -------------------------
# TAB 1: Setup Campaign
# -------------------------
with tabs[0]:
    st.subheader("Create / Select a campaign")

    campaigns = list_campaigns()
    if campaigns:
        camp_options = {f"#{c.id} — {c.name} ({c.created_at.date().isoformat()})": c.id for c in campaigns}
        selected = st.selectbox("Select existing campaign", ["(create new)"] + list(camp_options.keys()))
        selected_id = camp_options.get(selected) if selected != "(create new)" else None
    else:
        selected_id = None
        st.info("No campaigns yet. Create one below.")

    st.divider()
    st.markdown("### Create new campaign")

    camp_name = st.text_input("Campaign name", value=f"Campaign {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    proposal_pdf = st.file_uploader("Proposal PDF (org/event info)", type=["pdf"])
    attachments = st.file_uploader(
        "Attachments to send (e.g., sponsorship deck PDF)",
        type=["pdf", "pptx", "docx"],
        accept_multiple_files=True
    )

    colA, colB = st.columns(2)
    with colA:
        default_lang = st.selectbox(
            "Default language", ["vi", "en"],
            index=0 if settings.DEFAULT_LANGUAGE == "vi" else 1
        )
    with colB:
        st.markdown("**LLM mode**")
        st.code(
            f"LLM_PROVIDER={settings.LLM_PROVIDER}\n"
            f"LLM_MODEL={settings.LLM_MODEL}\n"
            f"LLM_BASE_URL={settings.LLM_BASE_URL or '(auto)'}",
            language="text",
        )

    # Preview autofill (optional)
    raw_pdf_text_preview = ""
    if proposal_pdf is not None:
        pdf_bytes = proposal_pdf.getvalue()
        _, raw_pdf_text_preview = cache_pdf_text(pdf_bytes, proposal_pdf.name)

        # Only show preview button if LLM enabled
        if settings.LLM_PROVIDER.lower() != "none":
            if st.button("Preview auto-fill from proposal PDF"):
                with st.spinner("Extracting org/event fields with LLM..."):
                    extracted = extract_org_profile_with_llm(raw_pdf_text_preview)
                st.json(extracted)

    if st.button("Create campaign", type="primary", disabled=not camp_name):
        org = OrgProfile(
            org_name="",
            org_website="",
            contact_name="",
            contact_email="",
            contact_phone="",
            mission="",
            programs="",
            event_summary="",
            sponsorship_ask="",
            sponsorship_tiers="",
            audience="",
            impact_metrics="",
            raw_pdf_text="",
        )

        # Extract PDF text + auto-fill org fields before saving
        if proposal_pdf:
            pdf_bytes = proposal_pdf.getvalue()
            _, raw_text = cache_pdf_text(pdf_bytes, proposal_pdf.name)
            org.raw_pdf_text = raw_text

            if settings.LLM_PROVIDER.lower() != "none" and raw_text.strip():
                with st.spinner("Auto-filling Org/Event fields from proposal PDF..."):
                    try:
                        org = fill_org_from_llm(org, raw_text)
                    except Exception as e:
                        st.warning(f"LLM autofill failed; you can fill manually later. Error: {e}")

        with get_session() as s:
            s.add(org)
            s.commit()
            s.refresh(org)

            attach_paths = []
            if attachments:
                updir = Path("uploads") / f"campaign_{org.id}"
                updir.mkdir(parents=True, exist_ok=True)
                for f in attachments:
                    p = updir / f"{int(time.time())}_{f.name}"
                    p.write_bytes(f.getvalue())
                    attach_paths.append(str(p))

            camp = Campaign(name=camp_name, org_profile_id=org.id, attachment_paths=attach_paths)
            s.add(camp)
            s.commit()
            s.refresh(camp)

        st.success(f"Created campaign #{camp.id}. Next: edit org/event details below.")
        st.rerun()

    # Edit org profile for selected campaign
    st.divider()
    st.markdown("### Org / Event details")
    if selected_id:
        camp = get_campaign(selected_id)
        if not camp:
            st.warning("Campaign not found.")
        else:
            with get_session() as s:
                org = s.get(OrgProfile, camp.org_profile_id)

                # Auto-fill for existing campaigns if fields are empty but raw_pdf_text exists
                # Run only once per org id per session.
                done_key = f"autofill_done_org_{org.id}"
                if (
                    settings.LLM_PROVIDER.lower() != "none"
                    and org_is_empty(org)
                    and (org.raw_pdf_text or "").strip()
                    and not st.session_state.get(done_key, False)
                ):
                    with st.spinner("Auto-filling Org/Event fields from saved proposal text..."):
                        try:
                            org = fill_org_from_llm(org, org.raw_pdf_text)
                            s.add(org)
                            s.commit()
                            st.session_state[done_key] = True
                            st.success("Auto-filled Org/Event details from proposal.")
                        except Exception as e:
                            st.session_state[done_key] = True
                            st.warning(f"Auto-fill failed; please fill manually. Error: {e}")

            # Load into session_state so inputs are editable and persist nicely
            active_key = "active_org_id"
            if st.session_state.get(active_key) != org.id:
                # Switching campaigns -> overwrite the edit buffer
                st.session_state[active_key] = org.id
                st.session_state["org_org_name"] = org.org_name or ""
                st.session_state["org_org_website"] = org.org_website or ""
                st.session_state["org_contact_name"] = org.contact_name or ""
                st.session_state["org_contact_email"] = org.contact_email or ""
                st.session_state["org_contact_phone"] = org.contact_phone or ""
                st.session_state["org_mission"] = org.mission or ""
                st.session_state["org_programs"] = org.programs or ""
                st.session_state["org_event_summary"] = org.event_summary or ""
                st.session_state["org_sponsorship_ask"] = org.sponsorship_ask or ""
                st.session_state["org_sponsorship_tiers"] = org.sponsorship_tiers or ""
                st.session_state["org_audience"] = org.audience or ""
                st.session_state["org_impact_metrics"] = org.impact_metrics or ""

            c1, c2 = st.columns(2)
            with c1:
                st.text_input("Org name", key="org_org_name")
                st.text_input("Org website", key="org_org_website")
                st.text_input("Contact person", key="org_contact_name")
                st.text_input("Contact email", key="org_contact_email")
                st.text_input("Contact phone", key="org_contact_phone")
            with c2:
                st.text_area("Mission", height=120, key="org_mission")
                st.text_area("Programs", height=120, key="org_programs")

            st.text_area("Event summary / program overview", height=120, key="org_event_summary")
            st.text_area("Sponsorship ask (what you want from sponsors)", height=120, key="org_sponsorship_ask")
            st.text_area("Sponsorship tiers (optional)", height=100, key="org_sponsorship_tiers")
            st.text_area("Audience / reach", height=80, key="org_audience")
            st.text_area("Impact metrics (numbers, past results)", height=80, key="org_impact_metrics")

            colX, colY = st.columns(2)
            with colX:
                if st.button("Save org/event details"):
                    with get_session() as s:
                        org_db = s.get(OrgProfile, org.id)
                        org_db.org_name = st.session_state.get("org_org_name", "")
                        org_db.org_website = st.session_state.get("org_org_website", "")
                        org_db.contact_name = st.session_state.get("org_contact_name", "")
                        org_db.contact_email = st.session_state.get("org_contact_email", "")
                        org_db.contact_phone = st.session_state.get("org_contact_phone", "")
                        org_db.mission = st.session_state.get("org_mission", "")
                        org_db.programs = st.session_state.get("org_programs", "")
                        org_db.event_summary = st.session_state.get("org_event_summary", "")
                        org_db.sponsorship_ask = st.session_state.get("org_sponsorship_ask", "")
                        org_db.sponsorship_tiers = st.session_state.get("org_sponsorship_tiers", "")
                        org_db.audience = st.session_state.get("org_audience", "")
                        org_db.impact_metrics = st.session_state.get("org_impact_metrics", "")
                        s.add(org_db)
                        s.commit()
                    st.success("Saved.")
            with colY:
                if settings.LLM_PROVIDER.lower() != "none":
                    if st.button("Re-run auto-fill from saved proposal text"):
                        with get_session() as s:
                            org_db = s.get(OrgProfile, org.id)
                            if (org_db.raw_pdf_text or "").strip():
                                with st.spinner("Auto-filling..."):
                                    org_db = fill_org_from_llm(org_db, org_db.raw_pdf_text)
                                    s.add(org_db)
                                    s.commit()
                                st.success("Auto-filled. Reloading…")
                                st.session_state[f"autofill_done_org_{org.id}"] = True
                                st.rerun()
                            else:
                                st.warning("No raw_pdf_text saved for this campaign.")
    else:
        st.info("Select a campaign to edit org/event details.")


# -------------------------
# TAB 2: Import Companies
# -------------------------
with tabs[1]:
    st.subheader("Import companies (CSV)")
    st.caption("CSV columns: name (required), website, industry, notes")

    campaigns = list_campaigns()
    if not campaigns:
        st.warning("Create a campaign first.")
    else:
        camp = st.selectbox("Campaign", campaigns, format_func=lambda c: f"#{c.id} — {c.name}")
        file = st.file_uploader("Upload CSV", type=["csv"])

        # Optional: auto-fill org profile when importing companies (only if empty)
        with get_session() as s:
            org = s.get(OrgProfile, camp.org_profile_id)
            done_key = f"autofill_done_org_{org.id}"
            if (
                settings.LLM_PROVIDER.lower() != "none"
                and org_is_empty(org)
                and (org.raw_pdf_text or "").strip()
                and not st.session_state.get(done_key, False)
            ):
                with st.spinner("Auto-filling Org/Event fields from saved proposal text..."):
                    try:
                        org = fill_org_from_llm(org, org.raw_pdf_text)
                        s.add(org)
                        s.commit()
                        st.session_state[done_key] = True
                        st.success("Auto-filled Org/Event details. (Check tab 1)")
                    except Exception as e:
                        st.session_state[done_key] = True
                        st.warning(f"Auto-fill failed; please fill manually. Error: {e}")

        if file is not None:
            df = pd.read_csv(file)
            st.dataframe(df.head(20))
            if "name" not in df.columns:
                st.error("CSV must include a 'name' column.")
            else:
                if st.button("Import companies"):
                    with get_session() as s:
                        for _, row in df.iterrows():
                            comp = Company(
                                campaign_id=camp.id,
                                name=str(row.get("name", "")).strip(),
                                website=str(row.get("website", "") or "").strip(),
                                industry=str(row.get("industry", "") or "").strip(),
                                notes=str(row.get("notes", "") or "").strip(),
                            )
                            if comp.name:
                                s.add(comp)
                        s.commit()
                    st.success("Imported.")
                    st.rerun()


# -------------------------
# TAB 3: Research + Draft
# -------------------------
with tabs[2]:
    st.subheader("Research companies + generate drafts")
    campaigns = list_campaigns()
    if not campaigns:
        st.warning("Create a campaign first.")
    else:
        camp = st.selectbox("Campaign", campaigns, key="camp_research", format_func=lambda c: f"#{c.id} — {c.name}")
        with get_session() as s:
            org = s.get(OrgProfile, camp.org_profile_id)
            companies = s.exec(
                select(Company).where(Company.campaign_id == camp.id).order_by(Company.created_at.asc())
            ).all()

        st.write(f"Companies: **{len(companies)}**")
        limit = st.number_input(
            "Process first N companies (for testing)",
            min_value=1,
            max_value=max(1, len(companies)),
            value=min(5, max(1, len(companies))),
        )
        language = st.selectbox("Email language", ["vi", "en"], index=0 if settings.DEFAULT_LANGUAGE == "vi" else 1)

        if st.button("Run research + generate drafts", type="primary", disabled=(len(companies) == 0)):
            if org_is_empty(org):
                st.warning("Your Org/Event details look empty. Go to Tab 1 and fill/auto-fill them first for best emails.")

            progress = st.progress(0)
            processed = 0

            for comp in companies[: int(limit)]:
                pages = []
                if comp.website:
                    urls = guess_key_pages(comp.website)
                    for u in urls[:6]:
                        try:
                            final_url, txt = fetch_url_text(u)
                            if len(txt) > 200:
                                pages.append((final_url, txt))
                        except Exception:
                            continue

                company_prof = summarize_company_pages(comp.name, pages, language=language) if pages else {
                    "summary": comp.notes or "",
                    "mission_values": "",
                    "csr_focus": "",
                    "recent_initiatives": "",
                    "alignment_angles": "",
                    "sources": [],
                }

                found_emails = find_contacts_from_pages(pages) if pages else []
                top = pick_top_contacts(found_emails, max_n=3)

                with get_session() as s:
                    existing = s.exec(select(CompanyProfile).where(CompanyProfile.company_id == comp.id)).first()
                    if not existing:
                        existing = CompanyProfile(company_id=comp.id)

                    existing.summary = company_prof.get("summary", "")
                    existing.mission_values = company_prof.get("mission_values", "")
                    existing.csr_focus = company_prof.get("csr_focus", "")
                    existing.recent_initiatives = company_prof.get("recent_initiatives", "")
                    existing.alignment_angles = company_prof.get("alignment_angles", "")
                    existing.sources = company_prof.get("sources", [])
                    s.add(existing)
                    s.commit()

                    existing_contacts = s.exec(select(Contact).where(Contact.company_id == comp.id)).all()
                    for ec in existing_contacts:
                        s.delete(ec)
                    s.commit()

                    contact_ids = []
                    for f in top:
                        c = Contact(
                            company_id=comp.id,
                            email=f.email,
                            found_on=f.found_on,
                            role_guess=f.role_guess,
                            confidence=float(f.confidence),
                        )
                        s.add(c)
                        s.commit()
                        s.refresh(c)
                        contact_ids.append(c.id)

                    contact_id = contact_ids[0] if contact_ids else None

                    org_dict = {
                        "org_name": org.org_name,
                        "contact_name": org.contact_name,
                        "contact_email": org.contact_email,
                        "mission": org.mission,
                        "programs": org.programs,
                        "event_summary": org.event_summary,
                        "sponsorship_ask": org.sponsorship_ask,
                        "sponsorship_tiers": org.sponsorship_tiers,
                        "audience": org.audience,
                        "impact_metrics": org.impact_metrics,
                    }
                    comp_dict = {
                        "name": comp.name,
                        "website": comp.website,
                        "industry": comp.industry,
                        "notes": comp.notes,
                        "summary": company_prof.get("summary", ""),
                        "mission_values": company_prof.get("mission_values", ""),
                        "csr_focus": company_prof.get("csr_focus", ""),
                        "recent_initiatives": company_prof.get("recent_initiatives", ""),
                        "alignment_angles": company_prof.get("alignment_angles", ""),
                    }

                    brief = build_personalization_brief(org_dict, comp_dict, language=language)
                    subject, body, notes = write_email_with_llm(org_dict, comp_dict, brief, language=language)

                    d = Draft(
                        company_id=comp.id,
                        contact_id=contact_id,
                        subject=subject,
                        body_text=body,
                        language=language,
                        personalization_notes=notes,
                        status=DraftStatus.DRAFT,
                    )
                    s.add(d)
                    s.commit()

                processed += 1
                progress.progress(processed / int(limit))

            st.success(f"Generated drafts for {processed} companies.")
            st.rerun()


# -------------------------
# TAB 4: Approve + Send
# -------------------------
with tabs[3]:
    st.subheader("Approve drafts + send (via worker)")
    st.caption("This UI approves drafts. Then run the worker: `python -m outreach_app.queue.worker`")

    campaigns = list_campaigns()
    if not campaigns:
        st.warning("Create a campaign first.")
    else:
        camp = st.selectbox("Campaign", campaigns, key="camp_approve", format_func=lambda c: f"#{c.id} — {c.name}")

        with get_session() as s:
            companies = s.exec(select(Company).where(Company.campaign_id == camp.id).order_by(Company.created_at.asc())).all()
            company_ids = [c.id for c in companies]
            drafts = s.exec(select(Draft).where(Draft.company_id.in_(company_ids)).order_by(Draft.created_at.desc())).all()

        st.write(f"Drafts: **{len(drafts)}**")
        status_filter = st.multiselect(
            "Filter status",
            [DraftStatus.DRAFT, DraftStatus.APPROVED, DraftStatus.SENT, DraftStatus.FAILED],
            default=[DraftStatus.DRAFT, DraftStatus.APPROVED],
        )
        show = [d for d in drafts if d.status in status_filter]

        for d in show[:30]:
            with get_session() as s:
                comp = s.get(Company, d.company_id)
                contacts = s.exec(select(Contact).where(Contact.company_id == comp.id).order_by(Contact.confidence.desc())).all()
                contact_map = {f"{c.email} ({c.role_guess}, {c.confidence:.2f})": c.id for c in contacts}

                selected_contact_label = None
                if d.contact_id:
                    for k, cid in contact_map.items():
                        if cid == d.contact_id:
                            selected_contact_label = k
                            break

            with st.expander(f"{comp.name} — [{d.status.upper()}] {d.subject}"):
                st.write(f"Website: {comp.website or '—'} | Industry: {comp.industry or '—'}")
                new_subject = st.text_input("Subject", value=d.subject, key=f"sub_{d.id}")
                new_body = st.text_area("Body (plain text)", value=d.body_text, height=220, key=f"body_{d.id}")
                new_contact_label = st.selectbox(
                    "Recipient",
                    ["(none)"] + list(contact_map.keys()),
                    index=0 if not selected_contact_label else (list(contact_map.keys()).index(selected_contact_label) + 1),
                    key=f"rcpt_{d.id}",
                )

                col1, col2, col3 = st.columns(3)
                with col1:
                    if st.button("Save", key=f"save_{d.id}"):
                        with get_session() as s:
                            ddb = s.get(Draft, d.id)
                            ddb.subject = new_subject
                            ddb.body_text = new_body
                            if new_contact_label != "(none)":
                                ddb.contact_id = contact_map[new_contact_label]
                            else:
                                ddb.contact_id = None
                            ddb.updated_at = datetime.utcnow()
                            s.add(ddb)
                            s.commit()
                        st.success("Saved.")
                        st.rerun()
                with col2:
                    if st.button("Approve", key=f"appr_{d.id}", disabled=(d.status == DraftStatus.SENT)):
                        with get_session() as s:
                            ddb = s.get(Draft, d.id)
                            ddb.status = DraftStatus.APPROVED
                            ddb.updated_at = datetime.utcnow()
                            s.add(ddb)
                            s.commit()
                        st.success("Approved. Worker can send it.")
                        st.rerun()
                with col3:
                    if st.button("Unapprove", key=f"unappr_{d.id}"):
                        with get_session() as s:
                            ddb = s.get(Draft, d.id)
                            ddb.status = DraftStatus.DRAFT
                            ddb.updated_at = datetime.utcnow()
                            s.add(ddb)
                            s.commit()
                        st.info("Back to draft.")
                        st.rerun()

        st.divider()
        st.markdown("### Sending checklist")
        st.code(
            "1) Configure SMTP in .env\n"
            "2) Approve drafts here\n"
            "3) Run worker: python -m outreach_app.queue.worker\n"
            "4) Watch Logs tab for SENT/FAILED",
            language="text",
        )


# -------------------------
# TAB 5: Logs
# -------------------------
with tabs[4]:
    st.subheader("Logs")
    with get_session() as s:
        attempts = s.exec(select(SendAttempt).order_by(SendAttempt.timestamp.desc())).all()
    if not attempts:
        st.info("No send attempts yet.")
    else:
        for a in attempts[:50]:
            st.write(f"**{a.timestamp}** — Draft #{a.draft_id} — **{a.status.upper()}** — {a.error or 'OK'}")