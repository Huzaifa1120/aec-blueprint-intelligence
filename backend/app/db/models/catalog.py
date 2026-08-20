from __future__ import annotations

import uuid
from datetime import date

from sqlalchemy import JSON, Date, ForeignKey, Numeric, String, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class Assembly(Base):
    __tablename__ = "assemblies"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(200), unique=True)
    rule_version: Mapped[str] = mapped_column(String(50))
    formula_or_bom: Mapped[dict | None] = mapped_column(JSON)

    materials: Mapped[list["Material"]] = relationship(
        secondary="assembly_materials", back_populates="assemblies"
    )


class Material(Base):
    __tablename__ = "materials"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(200))
    unit: Mapped[str] = mapped_column(String(20))
    category: Mapped[str | None] = mapped_column(String(100))

    prices: Mapped[list["Price"]] = relationship(
        back_populates="material", cascade="all, delete-orphan"
    )
    assemblies: Mapped[list[Assembly]] = relationship(
        secondary="assembly_materials", back_populates="materials"
    )


class Price(Base):
    __tablename__ = "prices"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    material_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("materials.id"))
    unit_price: Mapped[float] = mapped_column(Numeric(12, 2))
    currency: Mapped[str] = mapped_column(String(3), default="USD")
    effective_from: Mapped[date | None] = mapped_column(Date)
    effective_to: Mapped[date | None] = mapped_column(Date)

    material: Mapped[Material] = relationship(back_populates="prices")


class LaborRate(Base):
    __tablename__ = "labor_rates"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(200), unique=True)
    productivity_rate: Mapped[float | None] = mapped_column(default=None)
    hourly_rate: Mapped[float | None] = mapped_column(default=None)
    category: Mapped[str | None] = mapped_column(String(100), default=None)
    effective_from: Mapped[date | None] = mapped_column(Date, default=None)
    effective_to: Mapped[date | None] = mapped_column(Date, default=None)


class AssemblyMaterial(Base):
    __tablename__ = "assembly_materials"

    assembly_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("assemblies.id"), primary_key=True
    )
    material_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("materials.id"), primary_key=True
    )
    quantity: Mapped[float] = mapped_column(default=1.0)
