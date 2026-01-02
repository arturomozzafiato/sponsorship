from __future__ import annotations

from sqlmodel import SQLModel, create_engine, Session
from outreach_app.config import settings

engine = create_engine(settings.DB_URL, echo=False)

def init_db() -> None:
    SQLModel.metadata.create_all(engine)

def get_session() -> Session:
    return Session(engine)
