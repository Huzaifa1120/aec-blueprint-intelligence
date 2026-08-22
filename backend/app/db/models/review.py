"""Review-time instrumentation — sessions + per-item actions (spec v3 §7.13/§15)."""
from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import DateTime, ForeignKey, String, Uuid, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


def utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


class ReviewSession(Base):
    __tablename__ = "review_sessions"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    project_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("projects.id"))
    sheet_label: Mapped[str] = mapped_column(String(200))
    started_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    ended_at: Mapped[datetime | None] = mapped_column(DateTime)

    actions: Mapped[list["ReviewAction"]] = relationship(
        back_populates="session", cascade="all, delete-orphan"
    )


class ReviewAction(Base):
    __tablename__ = "review_actions"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    session_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("review_sessions.id"))
    item_id: Mapped[str] = mapped_column(String(100))
    action: Mapped[str] = mapped_column(String(20))
    confidence_tier: Mapped[str] = mapped_column(String(20))
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    session: Mapped[ReviewSession] = relationship(back_populates="actions")
