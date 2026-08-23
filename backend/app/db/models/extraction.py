from __future__ import annotations

import uuid

from sqlalchemy import ForeignKey, String, Text, UniqueConstraint, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class Layer(Base):
    __tablename__ = "layers"
    __table_args__ = (UniqueConstraint("sheet_id", "ocg_name"),)

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    sheet_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("sheets.id"))
    ocg_name: Mapped[str] = mapped_column(String(100))
    classified_discipline: Mapped[str] = mapped_column(String(50))
    human_override_discipline: Mapped[str | None] = mapped_column(String(50))


class ScheduleBlock(Base):
    __tablename__ = "schedule_blocks"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    sheet_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("sheets.id"))
    block_type: Mapped[str] = mapped_column(String(30))
    page_region_json: Mapped[str] = mapped_column(String(500))
    entries_json: Mapped[str] = mapped_column(Text)
    source_quality: Mapped[str] = mapped_column(String(20), default="layered_vector")


class TextAnnotation(Base):
    __tablename__ = "text_annotations"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    sheet_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("sheets.id"))
    text: Mapped[str] = mapped_column(Text)
    bbox_json: Mapped[str] = mapped_column(String(200))
    ocg_layer: Mapped[str | None] = mapped_column(String(100))
    component_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("components.id"))
    route_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("routes.id"))
    space_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("spaces.id"))
