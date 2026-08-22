"""Quality-gate persistence — assessments + re-export requests (spec §5.5/§7.2)."""
from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, Uuid, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class DrawingQualityAssessment(Base):
    __tablename__ = "drawing_quality_assessments"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    drawing_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("drawings.id"))
    file_name: Mapped[str] = mapped_column(String(500))
    verdict: Mapped[str] = mapped_column(String(20))
    metrics_json: Mapped[str | None] = mapped_column(String(2000))
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class ReexportRequest(Base):
    __tablename__ = "reexport_requests"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    drawing_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("drawings.id"))
    message: Mapped[str] = mapped_column(String(1000))
    requested_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
