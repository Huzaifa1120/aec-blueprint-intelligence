# Phase 0 — Foundation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Complete Phase 0 (Foundation): finish the backend DB + config layer, env var files in both projects, git consolidation, fixture registration, docs alignment, and green DoD verification.

**Architecture:** SQLAlchemy 2.0 ORM + Alembic migrations over a **file-based SQLite** DB (owner decision — swaps to PostgreSQL later via `DATABASE_URL`, no code change). FastAPI config centralized in a pydantic-settings `Settings` object read from `.env`. Single git repo at root.

**Tech Stack:** Python 3.13 / FastAPI / SQLAlchemy 2.0 / Alembic / pydantic-settings / pytest / ruff / Next.js 16.3.1 (TS, Tailwind v4).

## Global Constraints

- Python ≥3.11 (running 3.13.1); venv is self-contained at `backend/.venv`.
- Backend commands run from `backend/` with the **full venv path** `backend/.venv/Scripts/python.exe -m <tool>` (never `<tool>.exe`, never bare `python`).
- Import PyMuPDF as `pymupdf`, never deprecated `fitz`.
- No code comments unless explicitly requested (`Rules.md` §6); `# noqa` lint directives are allowed.
- Ruff line-length 100, target py311 (already in `backend/pyproject.toml`).
- Run `python -m pytest -q`, `python -m ruff check app tests`, `npm run lint`, `npm run build` after each task.
- DB is SQLite file-based for Phase 0 (owner decision); `DATABASE_URL` must stay swappable to PostgreSQL later.
- Root is **one git repo** (owner decision); nested `frontend/.git` gets removed.
- Sample fixture present: `data/samples/MMC-JVC-CD-ELEC-3902_AC-WIRE-Model.pdf` (1 page, 1191×842, 88,523 drawings, 2 images, 46 OCGs, `access control` layer confirmed).
- Client PDF must NOT be committed to git (privacy); keep a README in `data/samples/`.
- Phase 0 DoD: `pytest` green, app starts, migration applies.

## File Structure

**Created (backend):** `app/core/__init__.py`, `app/core/config.py`, `app/db/__init__.py`, `app/db/base.py`, `app/db/session.py`, `app/db/models/__init__.py`, `app/db/models/project.py`, `app/db/models/geometry.py`, `app/db/models/estimate.py`, `app/db/models/catalog.py`, `alembic.ini`, `alembic/` (init tree + `env.py` edit), `.env.example`, `.env`, `tests/test_config.py`, `tests/test_cors.py`, `tests/test_db_models.py`, `tests/test_migrations.py`, `tests/test_health_db.py`, `tests/test_sample_fixture.py`

**Modified (backend):** `pyproject.toml`, `app/main.py`, `tests/test_health.py`

**Created (frontend):** `.env.example`, `.env.local`
**Modified (frontend):** `.gitignore`

**Created (root):** `data/assemblies/.gitkeep`, `data/samples/README.md`
**Modified (root):** `.gitignore`

**Modified (docs):** `Architecture.md`, `Rules.md`, `AEC-Blueprint-System-Design-Spec.md`, `Memory.md`, `Phases.md`

---

### Task 1: Git consolidation + ignore rules

**Files:**
- Delete: `frontend/.git/`
- Modify: `.gitignore`

**Interfaces:**
- Consumes: nothing.
- Produces: a git repo at root so all later tasks can commit; ignore rules covering `*.db` (SQLite file), `data/samples/*.pdf`, `.env.local`.

- [ ] **Step 1: Remove nested frontend repo**
  Run: `rm -rf frontend/.git` (from repo root)
  Verify: `ls frontend/.git` → "No such file or directory"

- [ ] **Step 2: Extend root `.gitignore`**
  Append to existing `.gitignore` (after line 10 `.env`):
  ```
  .env.local
  *.db
  data/samples/*.pdf
  ```
  Keep `.env` (matches only the file `.env`, so `backend/.env.example` stays committable). `frontend/.gitignore` already ignores `.env*`, `node_modules/`, `.next/` and still applies as a nested file.

- [ ] **Step 3: Initialize root repo and make the baseline commit**
  ```bash
  git init
  git add -A
  git commit -m "chore: initialize monorepo (backend + frontend + docs)"
  ```

- [ ] **Step 4: Verify**
  Run: `git status` → clean; `git ls-files | grep -c .` > 0; confirm no `node_modules`, `.venv`, `.next`, or `*.pdf` in `git ls-files`.

---

### Task 2: Backend config, env files, CORS

**Files:**
- Modify: `backend/pyproject.toml:6-12`
- Create: `backend/app/core/__init__.py`, `backend/app/core/config.py`, `backend/.env.example`, `backend/.env`
- Modify: `backend/app/main.py`
- Create: `backend/tests/test_config.py`, `backend/tests/test_cors.py`

**Interfaces:**
- Consumes: existing FastAPI app in `app/main.py`.
- Produces: `get_settings() -> Settings` (lru_cached) with attrs `app_env: str`, `database_url: str`, `cors_origins: list[str]`, `log_level: str`. Used by Task 3 (`session.py`) and Task 5 (`main.py` CORS).

- [ ] **Step 1: Add dependencies**
  Add to `[project].dependencies` in `backend/pyproject.toml`:
  ```toml
  "sqlalchemy>=2.0",
  "alembic>=1.13",
  "pydantic-settings>=2.4",
  ```
  Install (from repo root, Git Bash):
  ```bash
  backend/.venv/Scripts/python.exe -m pip install "sqlalchemy>=2.0" "alembic>=1.13" "pydantic-settings>=2.4"
  ```

- [ ] **Step 2: Write the failing config tests**

  `backend/tests/test_config.py`:
  ```python
  import pytest

  from app.core.config import Settings, get_settings


  def test_defaults() -> None:
      s = Settings()
      assert s.app_env == "development"
      assert s.database_url == "sqlite:///./aec.db"
      assert s.cors_origins == ["http://localhost:3000"]
      assert s.log_level == "INFO"


  def test_env_override(monkeypatch) -> None:
      monkeypatch.setenv("DATABASE_URL", "sqlite:///:memory:")
      monkeypatch.setenv("APP_ENV", "test")
      s = Settings()
      assert s.database_url == "sqlite:///:memory:"
      assert s.app_env == "test"


  def test_cors_comma_separated() -> None:
      s = Settings(cors_origins="http://a.test,http://b.test")
      assert s.cors_origins == ["http://a.test", "http://b.test"]


  def test_settings_cached() -> None:
      get_settings.cache_clear()
      assert get_settings() is get_settings()
  ```

- [ ] **Step 3: Run tests to verify failure**
  Run: `backend/.venv/Scripts/python.exe -m pytest tests/test_config.py -v`
  Expected: FAIL — `ModuleNotFoundError: No module named 'app.core'`

- [ ] **Step 4: Implement config**

  `backend/app/core/config.py`:
  ```python
  from functools import lru_cache

  from pydantic import field_validator
  from pydantic_settings import BaseSettings, SettingsConfigDict


  class Settings(BaseSettings):
      model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

      app_env: str = "development"
      database_url: str = "sqlite:///./aec.db"
      cors_origins: list[str] = ["http://localhost:3000"]
      log_level: str = "INFO"

      @field_validator("cors_origins", mode="before")
      @classmethod
      def split_cors(cls, v: object) -> object:
          if isinstance(v, str):
              return [o.strip() for o in v.split(",") if o.strip()]
          return v


  @lru_cache
  def get_settings() -> Settings:
      return Settings()
  ```

  Create empty `backend/app/core/__init__.py`.

- [ ] **Step 5: Create env files**

  `backend/.env.example`:
  ```
  APP_ENV=development
  DATABASE_URL=sqlite:///./aec.db
  CORS_ORIGINS=http://localhost:3000
  LOG_LEVEL=INFO
  ```
  Copy to `backend/.env` (identical; it is gitignored).

- [ ] **Step 6: Run tests to verify pass**
  Run: `backend/.venv/Scripts/python.exe -m pytest tests/test_config.py -v`
  Expected: PASS (4 passed)

- [ ] **Step 7: Add CORS middleware + test**

  `backend/app/main.py` (full file):
  ```python
  from fastapi import FastAPI
  from fastapi.middleware.cors import CORSMiddleware

  from app.core.config import get_settings

  settings = get_settings()

  app = FastAPI(title="AEC Blueprint Intelligence System", version="0.1.0")

  app.add_middleware(
      CORSMiddleware,
      allow_origins=settings.cors_origins,
      allow_methods=["*"],
      allow_headers=["*"],
  )


  @app.get("/")
  def root() -> dict:
      return {"service": "aec-backend", "status": "ok"}


  @app.get("/health")
  def health() -> dict:
      return {"status": "healthy"}
  ```

  `backend/tests/test_cors.py`:
  ```python
  from fastapi.testclient import TestClient

  from app.main import app


  def test_cors_preflight_allows_frontend_origin() -> None:
      resp = TestClient(app).options(
          "/health",
          headers={
              "Origin": "http://localhost:3000",
              "Access-Control-Request-Method": "GET",
          },
      )
      assert resp.status_code == 200
      assert resp.headers.get("access-control-allow-origin") == "http://localhost:3000"
  ```

- [ ] **Step 8: Run full backend test suite**
  Run: `backend/.venv/Scripts/python.exe -m pytest -q` and `backend/.venv/Scripts/python.exe -m ruff check app tests`
  Expected: PASS, lint clean

- [ ] **Step 9: Commit**
  ```bash
  git add backend
  git commit -m "feat: add settings, env files, and CORS middleware"
  ```

---

### Task 3: DB layer — SQLAlchemy models

**Files:**
- Create: `backend/app/db/__init__.py`, `backend/app/db/base.py`, `backend/app/db/session.py`, `backend/app/db/models/__init__.py`, `backend/app/db/models/project.py`, `backend/app/db/models/geometry.py`, `backend/app/db/models/estimate.py`, `backend/app/db/models/catalog.py`
- Create: `backend/tests/test_db_models.py`

**Interfaces:**
- Consumes: `get_settings()` (Task 2).
- Produces: `Base` (DeclarativeBase, `app.db.base`), `get_engine()` (lru_cached), `get_db()` generator, `db_ping() -> bool` (all in `app.db.session`). Model classes re-exported from `app.db.models`. Used by Task 4 (Alembic) and Task 5 (health).

- [ ] **Step 1: Write the failing roundtrip test**

  `backend/tests/test_db_models.py`:
  ```python
  from sqlalchemy import create_engine
  from sqlalchemy.orm import Session

  from app.db.base import Base
  from app.db.models import (
      Assembly,
      BoqItem,
      Component,
      Drawing,
      DrawingRevision,
      Estimate,
      Material,
      Measurement,
      Price,
      Project,
      Route,
      Sheet,
      Space,
  )


  def test_core_chain_roundtrip() -> None:
      engine = create_engine("sqlite:///:memory:")
      Base.metadata.create_all(engine)
      with Session(engine) as session:
          project = Project(name="Jeddah VIP Clinic")
          drawing = Drawing(discipline="Electrical", sheet_number="E-3902")
          rev = DrawingRevision(revision="A", source_path_type="pdf")
          sheet = Sheet(name="AC Wire", scale="1:100")
          component = Component(
              component_type="card_reader", source_layer="access control", x=1.0, y=2.0
          )
          route = Route(route_type="cable_trunk", length_m=42.5)
          space = Space(name="Room 101", area_m2=25.0)
          measurement = Measurement(
              source_sheet="E-3902",
              source_region="{0,0,10,10}",
              measurement_type="count",
              raw_value=1.0,
          )
          estimate = Estimate()
          boq = BoqItem(quantity=1.0, unit_cost=10.0, total_cost=10.0)

          project.drawings.append(drawing)
          drawing.revisions.append(rev)
          drawing.sheets.append(sheet)
          sheet.components.append(component)
          sheet.routes.append(route)
          sheet.spaces.append(space)
          component.measurements.append(measurement)
          estimate.boq_items.append(boq)
          measurement.boq_items.append(boq)
          project.estimates.append(estimate)

          material = Material(name="Cable", unit="m", category="Electrical")
          material.prices.append(Price(unit_price=5.50))
          assembly = Assembly(name="access_control_door", rule_version="1.0")
          assembly.materials.append(material)

          session.add_all([project, material, assembly])
          session.commit()

          assert project.id is not None
          assert drawing.project_id == project.id
          assert boq.measurement_id == measurement.id
          assert boq.estimate_id == estimate.id
          assert material.prices[0].unit_price == 5.50
          assert assembly.materials[0].name == "Cable"
  ```

- [ ] **Step 2: Run test to verify failure**
  Run: `backend/.venv/Scripts/python.exe -m pytest tests/test_db_models.py -v`
  Expected: FAIL — `ModuleNotFoundError: No module named 'app.db'`

- [ ] **Step 3: Implement base and session**

  `backend/app/db/base.py`:
  ```python
  from sqlalchemy import MetaData
  from sqlalchemy.orm import DeclarativeBase


  class Base(DeclarativeBase):
      metadata = MetaData(
          naming_convention={
              "ix": "ix_%(column_0_label)s",
              "uq": "uq_%(table_name)s_%(column_0_name)s",
              "ck": "ck_%(table_name)s_%(constraint_name)s",
              "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
              "pk": "pk_%(table_name)s",
          }
      )
  ```

  `backend/app/db/session.py`:
  ```python
  from collections.abc import Generator
  from functools import lru_cache

  from sqlalchemy import create_engine, text
  from sqlalchemy.orm import Session, sessionmaker

  from app.core.config import get_settings


  @lru_cache
  def get_engine():
      settings = get_settings()
      connect_args = (
          {"check_same_thread": False}
          if settings.database_url.startswith("sqlite")
          else {}
      )
      return create_engine(settings.database_url, connect_args=connect_args)


  def db_ping() -> bool:
      try:
          with get_engine().connect() as conn:
              conn.execute(text("SELECT 1"))
          return True
      except Exception:
          return False


  def get_db() -> Generator[Session, None, None]:
      db = sessionmaker(
          bind=get_engine(), autoflush=False, autocommit=False, expire_on_commit=False
      )()
      try:
          yield db
      finally:
          db.close()
  ```

  Create empty `backend/app/db/__init__.py`.

- [ ] **Step 4: Implement models**

  `backend/app/db/models/project.py`:
  ```python
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
  ```

  `backend/app/db/models/geometry.py`:
  ```python
  from __future__ import annotations

  import uuid

  from sqlalchemy import ForeignKey, String, Uuid
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

      sheet: Mapped["Sheet"] = relationship(back_populates="spaces")
      measurements: Mapped[list["Measurement"]] = relationship(
          back_populates="space", cascade="all, delete-orphan"
      )
  ```

  `backend/app/db/models/estimate.py`:
  ```python
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
  ```

  `backend/app/db/models/catalog.py`:
  ```python
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


  class AssemblyMaterial(Base):
      __tablename__ = "assembly_materials"

      assembly_id: Mapped[uuid.UUID] = mapped_column(
          ForeignKey("assemblies.id"), primary_key=True
      )
      material_id: Mapped[uuid.UUID] = mapped_column(
          ForeignKey("materials.id"), primary_key=True
      )
      quantity: Mapped[float] = mapped_column(default=1.0)
  ```

  `backend/app/db/models/__init__.py`:
  ```python
  from app.db.models.catalog import Assembly, AssemblyMaterial, Material, Price
  from app.db.models.estimate import BoqItem, Estimate, Measurement
  from app.db.models.geometry import Component, Route, Space
  from app.db.models.project import Drawing, DrawingRevision, Project, Sheet

  __all__ = [
      "Assembly",
      "AssemblyMaterial",
      "BoqItem",
      "Component",
      "Drawing",
      "DrawingRevision",
      "Estimate",
      "Material",
      "Measurement",
      "Price",
      "Project",
      "Route",
      "Sheet",
      "Space",
  ]
  ```

- [ ] **Step 5: Run tests to verify pass**
  Run: `backend/.venv/Scripts/python.exe -m pytest tests/test_db_models.py -v`
  Expected: PASS

- [ ] **Step 6: Lint and commit**
  Run: `backend/.venv/Scripts/python.exe -m ruff check app tests`
  ```bash
  git add backend
  git commit -m "feat: add SQLAlchemy models for core tables"
  ```

---

### Task 4: Alembic migrations

**Files:**
- Create: `backend/alembic/` (init tree), `backend/alembic.ini`
- Modify: `backend/alembic/env.py`
- Create: `backend/tests/test_migrations.py`

**Interfaces:**
- Consumes: `Base` (Task 3), `get_settings()` (Task 2), models registry.
- Produces: initial autogenerated migration at `alembic/versions/`; `python -m alembic upgrade head` creates all 15 tables (13 core + `assembly_materials` + `alembic_version`).

- [ ] **Step 1: Initialize Alembic**
  From `backend/`:
  ```bash
  backend/.venv/Scripts/python.exe -m alembic init alembic
  ```

- [ ] **Step 2: Write the failing migration test**

  `backend/tests/test_migrations.py`:
  ```python
  import os
  import sqlite3
  import subprocess
  import sys
  from pathlib import Path

  BACKEND = Path(__file__).resolve().parents[1]
  EXPECTED = {
      "alembic_version",
      "assembly_materials",
      "assemblies",
      "boq_items",
      "components",
      "drawing_revisions",
      "drawings",
      "estimates",
      "materials",
      "measurements",
      "prices",
      "projects",
      "routes",
      "sheets",
      "spaces",
  }


  def test_alembic_upgrade_head_creates_all_tables(tmp_path) -> None:
      db_file = tmp_path / "test.db"
      env = {**os.environ, "DATABASE_URL": f"sqlite:///{db_file.as_posix()}"}
      subprocess.run(
          [sys.executable, "-m", "alembic", "upgrade", "head"],
          cwd=BACKEND,
          env=env,
          check=True,
          capture_output=True,
      )
      conn = sqlite3.connect(db_file)
      try:
          tables = {
              r[0]
              for r in conn.execute(
                  "SELECT name FROM sqlite_master WHERE type='table'"
              )
          }
      finally:
          conn.close()
      assert EXPECTED <= tables
  ```

- [ ] **Step 3: Run test to verify failure**
  Run: `backend/.venv/Scripts/python.exe -m pytest tests/test_migrations.py -v`
  Expected: FAIL — no revision files exist (Alembic "No such revision 'head'")

- [ ] **Step 4: Wire env.py to app settings**

  Replace `backend/alembic/env.py` body with:
  ```python
  from logging.config import fileConfig

  from alembic import context
  from sqlalchemy import engine_from_config, pool

  from app.core.config import get_settings
  from app.db import models  # noqa: F401
  from app.db.base import Base

  config = context.config

  if config.config_file_name is not None:
      fileConfig(config.config_file_name)

  config.set_main_option(
      "sqlalchemy.url", get_settings().database_url.replace("%", "%%")
  )

  target_metadata = Base.metadata


  def run_migrations_offline() -> None:
      url = config.get_main_option("sqlalchemy.url")
      context.configure(
          url=url,
          target_metadata=target_metadata,
          literal_binds=True,
          dialect_opts={"paramstyle": "named"},
      )
      with context.begin_transaction():
          context.run_migrations()


  def run_migrations_online() -> None:
      connectable = engine_from_config(
          config.get_section(config.config_ini_section, {}),
          prefix="sqlalchemy.",
          poolclass=pool.NullPool,
      )
      with connectable.connect() as connection:
          context.configure(
              connection=connection, target_metadata=target_metadata
          )
          with context.begin_transaction():
              context.run_migrations()


  if context.is_offline_mode():
      run_migrations_offline()
  else:
      run_migrations_online()
  ```

- [ ] **Step 5: Generate the initial migration**
  From `backend/`:
  ```bash
  backend/.venv/Scripts/python.exe -m alembic revision --autogenerate -m "initial schema"
  ```
  Verify a file `alembic/versions/*_initial_schema.py` was created.

- [ ] **Step 6: Run tests to verify pass**
  Run: `backend/.venv/Scripts/python.exe -m pytest tests/test_migrations.py -v`
  Expected: PASS

- [ ] **Step 7: Lint and commit**
  Run: `backend/.venv/Scripts/python.exe -m ruff check app tests`
  ```bash
  git add backend/alembic backend/alembic.ini backend/tests
  git commit -m "feat: add Alembic migration for initial schema"
  ```

---

### Task 5: Health endpoint reports DB status

**Files:**
- Modify: `backend/app/main.py`
- Modify: `backend/tests/test_health.py`
- Create: `backend/tests/test_health_db.py`

**Interfaces:**
- Consumes: `db_ping()` (Task 3).
- Produces: `/health` returns `{"status": "healthy", "db": "ok" | "unavailable"}`.

- [ ] **Step 1: Update health endpoint**
  In `backend/app/main.py`, replace the `health` function:
  ```python
  from app.db.session import db_ping

  @app.get("/health")
  def health() -> dict:
      return {"status": "healthy", "db": "ok" if db_ping() else "unavailable"}
  ```
  (Add `from app.db.session import db_ping` to the imports.)

- [ ] **Step 2: Update existing health test for the new shape**
  Replace the body of `test_health` in `backend/tests/test_health.py`:
  ```python
  def test_health() -> None:
      resp = client.get("/health")
      assert resp.status_code == 200
      body = resp.json()
      assert body["status"] == "healthy"
      assert body["db"] in {"ok", "unavailable"}
  ```

- [ ] **Step 3: Add a DB-up health test**
  `backend/tests/test_health_db.py`:
  ```python
  from fastapi.testclient import TestClient

  from app.core.config import get_settings
  from app.db.session import get_engine


  def test_health_reports_db_ok(monkeypatch) -> None:
      monkeypatch.setenv("DATABASE_URL", "sqlite:///:memory:")
      get_settings.cache_clear()
      get_engine.cache_clear()
      from app.main import app

      resp = TestClient(app).get("/health")
      assert resp.json()["db"] == "ok"
  ```

- [ ] **Step 4: Run full suite**
  Run: `backend/.venv/Scripts/python.exe -m pytest -q`
  Expected: PASS (all tests, including health + CORS)

- [ ] **Step 5: Lint and commit**
  Run: `backend/.venv/Scripts/python.exe -m ruff check app tests`
  ```bash
  git add backend
  git commit -m "feat: report DB status in health endpoint"
  ```

---

### Task 6: Frontend env var files

**Files:**
- Create: `frontend/.env.example`, `frontend/.env.local`
- Modify: `frontend/.gitignore:34`

**Interfaces:**
- Consumes: `frontend/src/app/page.tsx:1` (already reads `NEXT_PUBLIC_API_URL`, defaults `http://127.0.0.1:8000`).
- Produces: committed env template + local dev override.

- [ ] **Step 1: Create env files**
  `frontend/.env.example`:
  ```
  NEXT_PUBLIC_API_URL=http://127.0.0.1:8000
  ```
  Copy identical content to `frontend/.env.local`.

- [ ] **Step 2: Un-ignore `.env.example`**
  In `frontend/.gitignore`, replace the block at line 34:
  ```
  .env*
  ```
  with:
  ```
  .env*
  !.env.example
  ```

- [ ] **Step 3: Verify build and lint**
  Run (from `frontend/`): `npm run lint` and `npm run build`
  Expected: both green; no changes needed to `page.tsx`.

- [ ] **Step 4: Commit**
  ```bash
  git add frontend/.env.example frontend/.env.local frontend/.gitignore
  git commit -m "chore: add frontend env files"
  ```

---

### Task 7: Data dirs + sample fixture registration

**Files:**
- Create: `data/assemblies/.gitkeep`, `data/samples/README.md`
- Create: `backend/tests/test_sample_fixture.py`

**Interfaces:**
- Consumes: fixture at `data/samples/MMC-JVC-CD-ELEC-3902_AC-WIRE-Model.pdf`.
- Produces: regression-test proof the fixture exists and has the expected vector/OCG characteristics (the seed for Phase 1's DoD test).

- [ ] **Step 1: Create data directories**
  ```bash
  mkdir -p data/assemblies
  touch data/assemblies/.gitkeep
  ```
  (`data/samples/` already exists with the PDF.)

- [ ] **Step 2: Write the fixture README**
  `data/samples/README.md`:
  ```markdown
  # Sample fixtures

  Real drawing PDFs used as regression-test fixtures.

  - `MMC-JVC-CD-ELEC-3902_AC-WIRE-Model.pdf` — access-control electrical sheet,
    Jeddah VIP Clinic (basement 2, scale 1:100, AutoCAD export).
    Not committed to git (client drawing); obtain a copy from the project owner.
  ```

- [ ] **Step 3: Write the failing fixture test**

  `backend/tests/test_sample_fixture.py`:
  ```python
  from pathlib import Path

  import pymupdf

  SAMPLE = (
      Path(__file__).resolve().parents[2]
      / "data"
      / "samples"
      / "MMC-JVC-CD-ELEC-3902_AC-WIRE-Model.pdf"
  )


  def test_sample_fixture_vector_metadata() -> None:
      assert SAMPLE.exists()
      doc = pymupdf.open(SAMPLE)
      try:
          assert doc.page_count == 1
          page = doc[0]
          assert len(page.get_drawings()) > 10000
          assert len(page.get_images(full=True)) == 2
          ocgs = doc.get_ocgs()
          assert len(ocgs) == 46
          names = [v["name"] for v in ocgs.values()]
          assert "access control" in names
      finally:
          doc.close()
  ```

- [ ] **Step 4: Run test to verify pass**
  Run: `backend/.venv/Scripts/python.exe -m pytest tests/test_sample_fixture.py -v`
  Expected: PASS

- [ ] **Step 5: Lint and commit**
  Run: `backend/.venv/Scripts/python.exe -m ruff check app tests`
  ```bash
  git add data backend/tests/test_sample_fixture.py
  git commit -m "test: register sample fixture and assert vector metadata"
  ```
  Verify the PDF is NOT in `git ls-files`.

---

### Task 8: Align docs of record with SQLite decision

**Files:**
- Modify: `docs/Architecture.md:166`, `docs/Rules.md:46`, `docs/AEC-Blueprint-System-Design-Spec.md:349`

**Interfaces:**
- Consumes: owner's DB decision (SQLite file-based for Phase 0, serverless + server capable).
- Produces: docs that no longer contradict the running system.

- [ ] **Step 1: Update `docs/Architecture.md` tech-stack row**
  Replace line 166 (`| Database | PostgreSQL (+ PostGIS if needed) |`) with:
  ```
  | Database | SQLite (file-based) via SQLAlchemy; PostgreSQL (+PostGIS) later via DATABASE_URL swap | Phase 0 decision: file DB works on serverless & server |
  ```

- [ ] **Step 2: Update `docs/Rules.md` allowed-libraries row**
  Replace line 46 (`| DB | \`sqlalchemy\`, \`alembic\`, \`psycopg\` | PostgreSQL |`) with:
  ```
  | DB | `sqlalchemy`, `alembic` (SQLite file DB, Phase 0); `psycopg` added when moving to PostgreSQL | |
  ```

- [ ] **Step 3: Update Design Spec tech-stack row**
  Replace line 349 (`| Database | PostgreSQL (+ PostGIS if spatial queries grow) |`) with:
  ```
  | Database | SQLite file-based for Phase 0 (works serverless + server); PostgreSQL (+ PostGIS) later via DATABASE_URL swap | |
  ```

- [ ] **Step 4: Verify no other PostgreSQL-first references block Phase 0**
  Run: `grep -rn "psycopg\|PostgreSQL" docs/` — confirm remaining mentions are about the future swap, not Phase 0 requirement.

- [ ] **Step 5: Commit**
  ```bash
  git add docs/Architecture.md docs/Rules.md docs/AEC-Blueprint-System-Design-Spec.md
  git commit -m "docs: record SQLite-first DB decision for Phase 0"
  ```

---

### Task 9: DoD verification + session tracker update

**Files:**
- Modify: `docs/Memory.md`, `docs/Phases.md:11`
- Run: full Phase 0 DoD gates.

**Interfaces:**
- Consumes: everything from Tasks 1–8.
- Produces: Phase 0 marked ✅ done with verified evidence.

- [ ] **Step 1: Fresh-DB migration check**
  From `backend/`, with `DATABASE_URL` pointed at a fresh file (e.g. delete `aec.db` first):
  ```bash
  backend/.venv/Scripts/python.exe -m alembic upgrade head
  ```
  Expected: applies cleanly; `aec.db` exists with 15 tables.

- [ ] **Step 2: App boot + health check**
  Start server (background, 8s):
  ```bash
  backend/.venv/Scripts/python.exe -m uvicorn app.main:app --port 8000 &
  ```
  Then `curl http://127.0.0.1:8000/health` → `{"status":"healthy","db":"ok"}`; kill server.

- [ ] **Step 3: Full test/lint/build gates**
  - `backend/.venv/Scripts/python.exe -m pytest -q` → all pass
  - `backend/.venv/Scripts/python.exe -m ruff check app tests` → clean
  - From `frontend/`: `npm run lint` and `npm run build` → green

- [ ] **Step 4: Update `docs/Memory.md`**
  - Status summary → "Phase 0 — Foundation (✅ done)".
  - Append progress-log row for 2026-08-19 (SQLite DB layer, Alembic migration, env files, git consolidation, fixture registered — verified by pytest green, ruff clean, `alembic upgrade head` applies, app boots, `npm run build` green).
  - Decisions section: add "SQLite file-based DB for Phase 0 (works serverless + server); PostgreSQL swap later via `DATABASE_URL` (owner decision 2026-08-19)."
  - Open items: remove the migration item; leave "confirm price catalog source + single-tenant deployment" and add "post-Phase-0: PostgreSQL migration + object storage".
  - Dev commands: add `python -m alembic upgrade head` and `python -m alembic revision --autogenerate`.

- [ ] **Step 5: Update `docs/Phases.md:11`**
  Change `## Phase 0 — Foundation (scaffold)` to `## Phase 0 — Foundation (scaffold) ✅`.

- [ ] **Step 6: Final commit**
  ```bash
  git add docs/Memory.md docs/Phases.md
  git commit -m "docs: mark Phase 0 complete and update session tracker"
  ```

---

## Self-Review

- **Spec coverage:** Every Phase 0 DoD item maps to a task — pytest green (T2/3/5/9), app starts (T9), migration applies (T4/T9), CORS + config via env (T2), env files both projects (T2/T6), fixture registered (T7), lint/typecheck (T2–9), git consolidation (T1), docs aligned (T8).
- **Placeholder scan:** All code steps contain literal code; no TBD/TODO; migration test has real expected table set.
- **Type consistency:** `get_settings()`, `get_engine()`, `db_ping()`, `get_db()` signatures are defined once in T2/T3 and reused identically in T4/T5. Model class names and table names (`projects`, `sheets`, `assembly_materials`, etc.) are identical in T3 code and the T4 `EXPECTED` set. Env var names (`DATABASE_URL`, `CORS_ORIGINS`, `APP_ENV`, `LOG_LEVEL`, `NEXT_PUBLIC_API_URL`) are consistent across `.env` files and config.
- **Deferred (flagged, not blocking):** PostgreSQL swap, price-catalog source, object storage, multi-sheet — all Phase 1+ or owner confirmations already tracked in `Memory.md`.