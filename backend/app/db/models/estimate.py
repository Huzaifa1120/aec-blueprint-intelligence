from __future__ import annotations

import uuid

from sqlalchemy import ForeignKey, String, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class Measurement(Base):
    __tablename__ = "measurements"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    component_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("components.id")
    )
    route_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("routes.id"))
    space_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("spaces.id"))
    source_sheet: Mapped[str] = mapped_column(String(200))
    source_region: Mapped[str] = mapped_column(String(500))
    measurement_type: Mapped[str] = mapped_column(String(50))
    raw_value: Mapped[float]
    final_value: Mapped[float | None]
    confidence_status: Mapped[str] = mapped_column(String(20), default="MEASURED")
    calculation_method: Mapped[str | None] = mapped_column(String(100))
    rule_version: Mapped[str | None] = mapped_column(String(50))

    component: Mapped["Component | None"] = relationship(back_populates="measurements")
    route: Mapped["Route | None"] = relationship(back_populates="measurements")
    space: Mapped["Space | None"] = relationship(back_populates="measurements")
    boq_items: Mapped[list["BoqItem"]] = relationship(
        back_populates="measurement", cascade="all, delete-orphan"
    )


class BoqItem(Base):
    __tablename__ = "boq_items"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    measurement_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("measurements.id"))
    estimate_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("estimates.id"))
    quantity: Mapped[float]
    unit_cost: Mapped[float]
    total_cost: Mapped[float]

    measurement: Mapped[Measurement] = relationship(back_populates="boq_items")
    estimate: Mapped["Estimate"] = relationship(back_populates="boq_items")


class Estimate(Base):
    __tablename__ = "estimates"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    project_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("projects.id"))
    total_material_cost: Mapped[float] = mapped_column(default=0.0)
    total_labor_cost: Mapped[float] = mapped_column(default=0.0)
    total_cost: Mapped[float] = mapped_column(default=0.0)

    project: Mapped["Project"] = relationship(back_populates="estimates")
    boq_items: Mapped[list[BoqItem]] = relationship(
        back_populates="estimate", cascade="all, delete-orphan"
    )
