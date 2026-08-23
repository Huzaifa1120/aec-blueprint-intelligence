from __future__ import annotations

import uuid
from datetime import date

from sqlalchemy import Date, ForeignKey, String, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class Project(Base):
    __tablename__ = "projects"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(200))
    owner: Mapped[str | None] = mapped_column(String(200))
    consultant: Mapped[str | None] = mapped_column(String(200))
    currency: Mapped[str] = mapped_column(String(3), default="USD")

    drawings: Mapped[list["Drawing"]] = relationship(
        back_populates="project", cascade="all, delete-orphan"
    )
    estimates: Mapped[list["Estimate"]] = relationship(
        back_populates="project", cascade="all, delete-orphan"
    )


class Drawing(Base):
    __tablename__ = "drawings"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    project_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("projects.id"))
    discipline: Mapped[str | None] = mapped_column(String(100))
    sheet_number: Mapped[str | None] = mapped_column(String(50))

    project: Mapped[Project] = relationship(back_populates="drawings")
    revisions: Mapped[list["DrawingRevision"]] = relationship(
        back_populates="drawing", cascade="all, delete-orphan"
    )
    sheets: Mapped[list["Sheet"]] = relationship(
        back_populates="drawing", cascade="all, delete-orphan"
    )


class DrawingRevision(Base):
    __tablename__ = "drawing_revisions"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    drawing_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("drawings.id"))
    revision: Mapped[str] = mapped_column(String(20))
    issued_date: Mapped[date | None] = mapped_column(Date)
    source_path_type: Mapped[str | None] = mapped_column(String(50))

    drawing: Mapped[Drawing] = relationship(back_populates="revisions")


class Sheet(Base):
    __tablename__ = "sheets"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    drawing_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("drawings.id"))
    name: Mapped[str | None] = mapped_column(String(200))
    page_number: Mapped[int | None] = mapped_column()
    scale: Mapped[str | None] = mapped_column(String(20))
    source_quality: Mapped[str] = mapped_column(String(20), default="layered_vector")

    drawing: Mapped[Drawing] = relationship(back_populates="sheets")
    components: Mapped[list["Component"]] = relationship(
        back_populates="sheet", cascade="all, delete-orphan"
    )
    routes: Mapped[list["Route"]] = relationship(
        back_populates="sheet", cascade="all, delete-orphan"
    )
    spaces: Mapped[list["Space"]] = relationship(
        back_populates="sheet", cascade="all, delete-orphan"
    )
