from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlalchemy.orm import relationship as sa_relationship
from sqlmodel import SQLModel, Field, Relationship, Column, JSON

SQLModel.metadata.clear()

class OrgProfile(SQLModel, table=True):
    __tablename__ = "orgprofile"

    id: Optional[int] = Field(default=None, primary_key=True)

    org_name: str = ""
    org_website: str = ""
    contact_name: str = ""
    contact_email: str = ""
    contact_phone: str = ""

    mission: str = ""
    programs: str = ""
    event_summary: str = ""
    sponsorship_ask: str = ""
    sponsorship_tiers: str = ""
    audience: str = ""
    impact_metrics: str = ""

    raw_pdf_text: str = ""

    # Explicit relationship target (prevents "Optional['Campaign']" issue)
    campaign: Optional["Campaign"] = Relationship(
        sa_relationship=sa_relationship(
            "Campaign",
            back_populates="org_profile",
            uselist=False,
        )
    )


class Campaign(SQLModel, table=True):
    __tablename__ = "campaign"

    id: Optional[int] = Field(default=None, primary_key=True)
    name: str
    created_at: datetime = Field(default_factory=datetime.utcnow)

    # Optional so you can create a campaign first then fill profile later
    org_profile_id: Optional[int] = Field(
        default=None,
        foreign_key="orgprofile.id",
        index=True,
        sa_column_kwargs={"unique": True},  # 1-1 with orgprofile
    )

    org_profile: Optional["OrgProfile"] = Relationship(
        sa_relationship=sa_relationship(
            "OrgProfile",
            back_populates="campaign",
            uselist=False,
        )
    )

    attachment_paths: list[str] = Field(default_factory=list, sa_column=Column(JSON))

    companies: list["Company"] = Relationship(
        sa_relationship=sa_relationship(
            "Company",
            back_populates="campaign",
            cascade="all, delete-orphan",
        )
    )


class Company(SQLModel, table=True):
    __tablename__ = "company"

    id: Optional[int] = Field(default=None, primary_key=True)
    campaign_id: int = Field(foreign_key="campaign.id", index=True)

    name: str
    website: str = ""
    industry: str = ""
    notes: str = ""
    created_at: datetime = Field(default_factory=datetime.utcnow)

    campaign: Optional["Campaign"] = Relationship(
        sa_relationship=sa_relationship("Campaign", back_populates="companies")
    )

    profile: Optional["CompanyProfile"] = Relationship(
        sa_relationship=sa_relationship(
            "CompanyProfile",
            back_populates="company",
            uselist=False,
            cascade="all, delete-orphan",
        )
    )

    contacts: list["Contact"] = Relationship(
        sa_relationship=sa_relationship(
            "Contact",
            back_populates="company",
            cascade="all, delete-orphan",
        )
    )

    drafts: list["Draft"] = Relationship(
        sa_relationship=sa_relationship(
            "Draft",
            back_populates="company",
            cascade="all, delete-orphan",
        )
    )


class CompanyProfile(SQLModel, table=True):
    __tablename__ = "companyprofile"

    id: Optional[int] = Field(default=None, primary_key=True)
    company_id: int = Field(foreign_key="company.id", index=True, sa_column_kwargs={"unique": True})

    summary: str = ""
    mission_values: str = ""
    csr_focus: str = ""
    recent_initiatives: str = ""
    alignment_angles: str = ""
    sources: list[dict] = Field(default_factory=list, sa_column=Column(JSON))

    company: Optional["Company"] = Relationship(
        sa_relationship=sa_relationship("Company", back_populates="profile")
    )


class Contact(SQLModel, table=True):
    __tablename__ = "contact"

    id: Optional[int] = Field(default=None, primary_key=True)
    company_id: int = Field(foreign_key="company.id", index=True)

    email: str
    found_on: str = ""
    role_guess: str = ""  # csr|partnership|marketing|generic|unknown
    confidence: float = 0.0

    company: Optional["Company"] = Relationship(
        sa_relationship=sa_relationship("Company", back_populates="contacts")
    )

    drafts: list["Draft"] = Relationship(
        sa_relationship=sa_relationship("Draft", back_populates="contact")
    )


class DraftStatus:
    DRAFT = "draft"
    APPROVED = "approved"
    SENT = "sent"
    FAILED = "failed"


class Draft(SQLModel, table=True):
    __tablename__ = "draft"

    id: Optional[int] = Field(default=None, primary_key=True)
    company_id: int = Field(foreign_key="company.id", index=True)
    contact_id: Optional[int] = Field(default=None, foreign_key="contact.id", index=True)

    subject: str = ""
    body_text: str = ""
    language: str = "vi"
    personalization_notes: str = ""
    status: str = Field(default=DraftStatus.DRAFT, index=True)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

    company: Optional["Company"] = Relationship(
        sa_relationship=sa_relationship("Company", back_populates="drafts")
    )

    contact: Optional["Contact"] = Relationship(
        sa_relationship=sa_relationship("Contact", back_populates="drafts")
    )

    attempts: list["SendAttempt"] = Relationship(
        sa_relationship=sa_relationship(
            "SendAttempt",
            back_populates="draft",
            cascade="all, delete-orphan",
        )
    )


class SendAttempt(SQLModel, table=True):
    __tablename__ = "sendattempt"

    id: Optional[int] = Field(default=None, primary_key=True)
    draft_id: int = Field(foreign_key="draft.id", index=True)

    status: str  # sent|failed
    provider: str = "smtp"
    provider_message_id: str = ""
    error: str = ""
    timestamp: datetime = Field(default_factory=datetime.utcnow)

    draft: Optional["Draft"] = Relationship(
        sa_relationship=sa_relationship("Draft", back_populates="attempts")
    )
