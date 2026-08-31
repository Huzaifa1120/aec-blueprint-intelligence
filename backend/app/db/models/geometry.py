from __future__ import annotations

import uuid

from sqlalchemy import ForeignKey, String, Text, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class Component(Base):
    __tablename__ = "components"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    sheet_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("sheets.id"))
    component_type: Mapped[str] = mapped_column(String(100))
    source_layer: Mapped[str | None] = mapped_column(String(100))
    x: Mapped[float]
    y: Mapped[float]
    confidence_status: Mapped[str] = mapped_column(String(20), default="MEASURED")
    confidence_score: Mapped[float] = mapped_column(default=1.0)
    layer_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("layers.id", ondelete="SET NULL")
    )
    source_quality: Mapped[str] = mapped_column(String(20), default="layered_vector")

    sheet: Mapped["Sheet"] = relationship(back_populates="components")
    measurements: Mapped[list["Measurement"]] = relationship(
        back_populates="component", cascade="all, delete-orphan"
    )


class Route(Base):
    __tablename__ = "routes"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    sheet_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("sheets.id"))
    route_type: Mapped[str] = mapped_column(String(100))
    length_m: Mapped[float | None]
    confidence_status: Mapped[str] = mapped_column(String(20), default="MEASURED")
    confidence_score: Mapped[float] = mapped_column(default=1.0)
    layer_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("layers.id", ondelete="SET NULL")
    )
    source_quality: Mapped[str] = mapped_column(String(20), default="layered_vector")
    size_json: Mapped[str | None] = mapped_column(Text, default=None)
    # JSON text: {width_mm,height_mm|diameter_mm,source,ref}

    sheet: Mapped["Sheet"] = relationship(back_populates="routes")
    measurements: Mapped[list["Measurement"]] = relationship(
        back_populates="route", cascade="all, delete-orphan"
    )


class Space(Base):
    __tablename__ = "spaces"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    sheet_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("sheets.id"))
    name: Mapped[str | None] = mapped_column(String(200))
    area_m2: Mapped[float | None]
    confidence_status: Mapped[str] = mapped_column(String(20), default="MEASURED")
    confidence_score: Mapped[float] = mapped_column(default=1.0)
    layer_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("layers.id", ondelete="SET NULL")
    )
    source_quality: Mapped[str] = mapped_column(String(20), default="layered_vector")

    sheet: Mapped["Sheet"] = relationship(back_populates="spaces")
    measurements: Mapped[list["Measurement"]] = relationship(
        back_populates="space", cascade="all, delete-orphan"
    )
