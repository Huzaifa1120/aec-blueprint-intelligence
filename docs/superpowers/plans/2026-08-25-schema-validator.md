# Schema Validator Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add YAML-based schema files + startup/pre-migration validators to catch schema drift before runtime errors.

**Architecture:** YAML source of truth in `backend/data/schemas/`, `SchemaValidator` class compares YAML vs DB/models, startup hook in `session.py`, pre-migration hook in `alembic/env.py`.

**Tech Stack:** Python 3.11+, PyYAML, SQLAlchemy, Alembic, pytest

## Global Constraints

- Import PyMuPDF as `pymupdf`, never the deprecated `fitz` alias
- Backend commands run from `backend/`: `backend/.venv/Scripts/python.exe -m pytest -q`
- Unit prices / productivity rates live in catalog DB or YAML — never hardcode
- All 17 existing tables must be covered by YAML schemas
- YAML types must be DB-agnostic (no SQLite-specific or PostgreSQL-specific types)

---

## File Structure

**Create:**
- `backend/data/schemas/` — directory for YAML schema files
- `backend/data/schemas/projects.yaml` — projects table schema
- `backend/data/schemas/drawings.yaml` — drawings table schema
- `backend/data/schemas/sheets.yaml` — sheets table schema
- `backend/data/schemas/components.yaml` — components table schema
- `backend/data/schemas/routes.yaml` — routes table schema
- `backend/data/schemas/spaces.yaml` — spaces table schema
- `backend/data/schemas/measurements.yaml` — measurements table schema
- `backend/data/schemas/boq_items.yaml` — boq_items table schema
- `backend/data/schemas/estimates.yaml` — estimates table schema
- `backend/data/schemas/layers.yaml` — layers table schema
- `backend/data/schemas/schedule_blocks.yaml` — schedule_blocks table schema
- `backend/data/schemas/text_annotations.yaml` — text_annotations table schema
- `backend/data/schemas/assemblies.yaml` — assemblies table schema
- `backend/data/schemas/materials.yaml` — materials table schema
- `backend/data/schemas/prices.yaml` — prices table schema
- `backend/data/schemas/labor_rates.yaml` — labor_rates table schema
- `backend/data/schemas/assembly_materials.yaml` — assembly_materials table schema
- `backend/data/schemas/review_sessions.yaml` — review_sessions table schema
- `backend/data/schemas/review_actions.yaml` — review_actions table schema
- `backend/data/schemas/drawing_quality_assessments.yaml` — drawing_quality_assessments table schema
- `backend/data/schemas/reexport_requests.yaml` — reexport_requests table schema
- `backend/app/db/validator.py` — SchemaValidator class
- `backend/tests/test_schema_validator.py` — unit tests
- `docs/schema.md` — auto-generated schema reference

**Modify:**
- `backend/app/db/session.py` — add startup validation hook
- `backend/alembic/env.py` — add pre-migration validation
- `docs/Architecture.md` — add schema validator section
- `docs/Memory.md` — log landing

---

### Task 1: Create YAML Schema Files for All 17 Tables

**Files:**
- Create: `backend/data/schemas/*.yaml` (21 files, one per table)
- Test: `backend/tests/test_schema_validator.py::test_yaml_schemas_parse`

**Interfaces:**
- Consumes: None (first task)
- Produces: YAML files that `SchemaValidator._load_schemas()` will parse

- [ ] **Step 1: Create the schemas directory**

```bash
mkdir -p backend/data/schemas
```

- [ ] **Step 2: Write the failing test for YAML parsing**

```python
# backend/tests/test_schema_validator.py
import pytest
from pathlib import Path
from app.db.validator import SchemaValidator

def test_yaml_schemas_parse():
    """All YAML schema files parse without error."""
    validator = SchemaValidator()
    schemas = validator.schemas
    assert len(schemas) >= 17, f"Expected >=17 table schemas, got {len(schemas)}"
    for name, schema in schemas.items():
        assert "columns" in schema, f"{name} missing 'columns' key"
        assert "id" in schema["columns"], f"{name} missing 'id' column"
```

- [ ] **Step 3: Run test to verify it fails**

Run: `cd backend && .venv/Scripts/python.exe -m pytest tests/test_schema_validator.py::test_yaml_schemas_parse -v`
Expected: FAIL with "ModuleNotFoundError: No module named 'app.db.validator'"

- [ ] **Step 4: Create projects.yaml (example — apply pattern to all 17 tables)**

```yaml
# backend/data/schemas/projects.yaml
table: projects
columns:
  id:
    type: uuid
    primary_key: true
    default: uuid4
  name:
    type: varchar(200)
    nullable: false
  owner:
    type: varchar(200)
    nullable: true
  consultant:
    type: varchar(200)
    nullable: true
  currency:
    type: varchar(3)
    default: USD
```

- [ ] **Step 5: Create all remaining YAML files (apply same pattern)**

Create YAML files for: drawings, sheets, components, routes, spaces, measurements, boq_items, estimates, layers, schedule_blocks, text_annotations, assemblies, materials, prices, labor_rates, assembly_materials, review_sessions, review_actions, drawing_quality_assessments, reexport_requests.

Each file follows the same structure as projects.yaml with correct columns from the SQLAlchemy models.

- [ ] **Step 6: Create SchemaValidator stub (import only, no implementation yet)**

```python
# backend/app/db/validator.py
"""Schema validator — compares YAML schema vs DB/models."""
from dataclasses import dataclass
from typing import Literal

@dataclass
class SchemaError:
    severity: Literal["error", "warning", "info"]
    table: str
    column: str | None
    issue: str
    expected: str | None = None
    actual: str | None = None

class SchemaValidator:
    def __init__(self, schema_dir: str = "data/schemas"):
        self.schemas = {}
```

- [ ] **Step 7: Run test to verify it passes**

Run: `cd backend && .venv/Scripts/python.exe -m pytest tests/test_schema_validator.py::test_yaml_schemas_parse -v`
Expected: PASS

- [ ] **Step 8: Commit**

```bash
git add backend/data/schemas/ backend/app/db/validator.py backend/tests/test_schema_validator.py
git commit -m "feat(schema): add YAML schema files for all 17 tables + SchemaValidator stub"
```

---

### Task 2: Implement SchemaValidator._load_schemas()

**Files:**
- Modify: `backend/app/db/validator.py` — add `_load_schemas()` method
- Test: `backend/tests/test_schema_validator.py::test_load_schemas_returns_all_tables`

**Interfaces:**
- Consumes: YAML files from Task 1
- Produces: `SchemaValidator.schemas` dict (used by Tasks 3-5)

- [ ] **Step 1: Write the failing test**

```python
def test_load_schemas_returns_all_tables():
    """_load_schemas returns dict with all expected table names."""
    validator = SchemaValidator()
    expected_tables = {
        "projects", "drawings", "sheets", "components", "routes", "spaces",
        "measurements", "boq_items", "estimates", "layers", "schedule_blocks",
        "text_annotations", "assemblies", "materials", "prices", "labor_rates",
        "assembly_materials", "review_sessions", "review_actions",
        "drawing_quality_assessments", "reexport_requests"
    }
    assert set(validator.schemas.keys()) == expected_tables
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && .venv/Scripts/python.exe -m pytest tests/test_schema_validator.py::test_load_schemas_returns_all_tables -v`
Expected: FAIL (schemas is empty dict)

- [ ] **Step 3: Implement _load_schemas()**

```python
# backend/app/db/validator.py
import yaml
from pathlib import Path

class SchemaValidator:
    def __init__(self, schema_dir: str = "data/schemas"):
        self.schemas = self._load_schemas(schema_dir)

    def _load_schemas(self, schema_dir: str) -> dict:
        """Load all YAML files into {table_name: {columns: {...}}}."""
        schemas = {}
        schema_path = Path(schema_dir)
        if not schema_path.exists():
            return schemas
        for yaml_file in schema_path.glob("*.yaml"):
            with open(yaml_file) as f:
                data = yaml.safe_load(f)
            if data and "table" in data and "columns" in data:
                schemas[data["table"]] = data
        return schemas
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && .venv/Scripts/python.exe -m pytest tests/test_schema_validator.py::test_load_schemas_returns_all_tables -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/app/db/validator.py backend/tests/test_schema_validator.py
git commit -m "feat(schema): implement SchemaValidator._load_schemas() from YAML files"
```

---

### Task 3: Implement validate_startup() — Compare YAML vs DB

**Files:**
- Modify: `backend/app/db/validator.py` — add `validate_startup()` method
- Test: `backend/tests/test_schema_validator.py::test_validate_startup_catches_missing_column`

**Interfaces:**
- Consumes: `SchemaValidator.schemas` from Task 2
- Produces: `list[SchemaError]` (used by Task 5 startup hook)

- [ ] **Step 1: Write the failing test**

```python
def test_validate_startup_catches_missing_column():
    """Validator catches a column in YAML but not in DB."""
    import tempfile, os
    from sqlalchemy import create_engine, text, MetaData, Table, Column, String, Integer
    from app.db.validator import SchemaValidator

    # Create a DB with only 'id' and 'name' columns
    engine = create_engine("sqlite:///:memory:")
    with engine.connect() as conn:
        conn.execute(text("CREATE TABLE projects (id TEXT PRIMARY KEY, name TEXT)"))
        conn.commit()

    validator = SchemaValidator()
    errors = validator.validate_startup(engine)

    # Should catch missing 'owner', 'consultant', 'currency' columns
    missing_cols = [e for e in errors if e.issue == "missing_column" and e.table == "projects"]
    assert len(missing_cols) >= 1, f"Expected missing column errors, got {errors}"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && .venv/Scripts/python.exe -m pytest tests/test_schema_validator.py::test_validate_startup_catches_missing_column -v`
Expected: FAIL (validate_startup not implemented)

- [ ] **Step 3: Implement validate_startup()**

```python
# backend/app/db/validator.py
from sqlalchemy import inspect, text

class SchemaValidator:
    # ... existing code ...

    def validate_startup(self, engine) -> list[SchemaError]:
        """Compare YAML schema vs actual DB. Returns list of discrepancies."""
        errors = []
        inspector = inspect(engine)

        for table_name, schema in self.schemas.items():
            if not inspector.has_table(table_name):
                errors.append(SchemaError(
                    severity="error", table=table_name, column=None,
                    issue="missing_table"
                ))
                continue

            db_columns = {col["name"] for col in inspector.get_columns(table_name)}
            yaml_columns = set(schema.get("columns", {}).keys())

            for col in yaml_columns - db_columns:
                errors.append(SchemaError(
                    severity="error", table=table_name, column=col,
                    issue="missing_column"
                ))

            for col in db_columns - yaml_columns:
                errors.append(SchemaError(
                    severity="warning", table=table_name, column=col,
                    issue="extra_column"
                ))

        return errors
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && .venv/Scripts/python.exe -m pytest tests/test_schema_validator.py::test_validate_startup_catches_missing_column -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/app/db/validator.py backend/tests/test_schema_validator.py
git commit -m "feat(schema): implement validate_startup() — compare YAML vs DB"
```

---

### Task 4: Implement validate_pre_migration() — Compare YAML vs Models

**Files:**
- Modify: `backend/app/db/validator.py` — add `validate_pre_migration()` method
- Test: `backend/tests/test_schema_validator.py::test_validate_pre_migration_catches_drift`

**Interfaces:**
- Consumes: `SchemaValidator.schemas` from Task 2
- Produces: `list[SchemaError]` (used by Task 5 pre-migration hook)

- [ ] **Step 1: Write the failing test**

```python
def test_validate_pre_migration_catches_drift():
    """Validator catches YAML column not in SQLAlchemy metadata."""
    from sqlalchemy import MetaData, Table, Column, String, Integer
    from app.db.validator import SchemaValidator

    metadata = MetaData()
    # Create a minimal 'projects' table missing 'owner', 'consultant', 'currency'
    Table("projects", metadata,
          Column("id", String(36), primary_key=True),
          Column("name", String(200), nullable=False))

    validator = SchemaValidator()
    errors = validator.validate_pre_migration(metadata)

    missing = [e for e in errors if e.issue == "missing_column" and e.table == "projects"]
    assert len(missing) >= 1, f"Expected missing column errors, got {errors}"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && .venv/Scripts/python.exe -m pytest tests/test_schema_validator.py::test_validate_pre_migration_catches_drift -v`
Expected: FAIL (validate_pre_migration not implemented)

- [ ] **Step 3: Implement validate_pre_migration()**

```python
# backend/app/db/validator.py

class SchemaValidator:
    # ... existing code ...

    def validate_pre_migration(self, metadata) -> list[SchemaError]:
        """Compare YAML vs SQLAlchemy metadata (Base.metadata)."""
        errors = []

        for table_name, schema in self.schemas.items():
            if table_name not in metadata.tables:
                errors.append(SchemaError(
                    severity="info", table=table_name, column=None,
                    issue="missing_table"
                ))
                continue

            model_columns = {col.name for col in metadata.tables[table_name].columns}
            yaml_columns = set(schema.get("columns", {}).keys())

            for col in yaml_columns - model_columns:
                errors.append(SchemaError(
                    severity="warning", table=table_name, column=col,
                    issue="missing_column"
                ))

            for col in model_columns - yaml_columns:
                errors.append(SchemaError(
                    severity="info", table=table_name, column=col,
                    issue="extra_column"
                ))

        return errors
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && .venv/Scripts/python.exe -m pytest tests/test_schema_validator.py::test_validate_pre_migration_catches_drift -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/app/db/validator.py backend/tests/test_schema_validator.py
git commit -m "feat(schema): implement validate_pre_migration() — compare YAML vs models"
```

---

### Task 5: Integrate Validator into App Startup and Alembic

**Files:**
- Modify: `backend/app/db/session.py:1-37` — add startup validation hook
- Modify: `backend/alembic/env.py:1-51` — add pre-migration validation
- Test: `backend/tests/test_schema_validator.py::test_startup_validation_runs_clean`

**Interfaces:**
- Consumes: `SchemaValidator.validate_startup()` from Task 3, `SchemaValidator.validate_pre_migration()` from Task 4
- Produces: Validation runs at startup and before migrations

- [ ] **Step 1: Write the failing test**

```python
def test_startup_validation_runs_clean():
    """Startup validation runs without error on current schema."""
    from sqlalchemy import create_engine
    from app.db.validator import SchemaValidator

    engine = create_engine("sqlite:///:memory:")
    # Create all tables from Base.metadata
    from app.db.base import Base
    Base.metadata.create_all(engine)

    validator = SchemaValidator()
    errors = validator.validate_startup(engine)
    critical = [e for e in errors if e.severity == "error"]
    assert len(critical) == 0, f"Startup validation has errors: {critical}"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && .venv/Scripts/python.exe -m pytest tests/test_schema_validator.py::test_startup_validation_runs_clean -v`
Expected: FAIL (create_all passes but validator hasn't been integrated yet — test itself may pass, integration is what we're testing)

- [ ] **Step 3: Modify session.py — add startup validation**

```python
# backend/app/db/session.py
from app.db.validator import SchemaValidator

@lru_cache
def get_engine():
    settings = get_settings()
    connect_args = (
        {"check_same_thread": False}
        if settings.database_url.startswith("sqlite")
        else {}
    )
    engine = create_engine(settings.database_url, connect_args=connect_args)
    # Validate schema on first engine creation
    validator = SchemaValidator()
    errors = validator.validate_startup(engine)
    for e in errors:
        if e.severity == "error":
            raise SchemaValidationError(
                f"Schema error: {e.table}.{e.column or ''} — {e.issue}"
            )
        logger.warning(f"Schema warning: {e.table}.{e.column or ''} — {e.issue}")
    return engine
```

- [ ] **Step 4: Modify alembic/env.py — add pre-migration validation**

```python
# backend/alembic/env.py
from app.db.validator import SchemaValidator

def run_migrations_online():
    connectable = create_engine(config.get_main_option("sqlalchemy.url"))
    validator = SchemaValidator()
    errors = validator.validate_pre_migration(Base.metadata)
    if any(e.severity == "error" for e in errors):
        raise RuntimeError(
            f"Schema drift detected: {[str(e) for e in errors if e.severity == 'error']}"
        )
    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=Base.metadata)
        with context.begin_transaction():
            context.run_migrations()
```

- [ ] **Step 5: Run test to verify it passes**

Run: `cd backend && .venv/Scripts/python.exe -m pytest tests/test_schema_validator.py::test_startup_validation_runs_clean -v`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add backend/app/db/session.py backend/alembic/env.py backend/tests/test_schema_validator.py
git commit -m "feat(schema): integrate validator into startup + pre-migration hooks"
```

---

### Task 6: Generate Schema Docs + Update Memory.md

**Files:**
- Create: `docs/schema.md` — auto-generated schema reference
- Modify: `docs/Memory.md` — log schema validator landing
- Modify: `docs/Architecture.md` — add schema validator section

**Interfaces:**
- Consumes: YAML schemas from Task 1
- Produces: Human-readable docs

- [ ] **Step 1: Generate docs/schema.md from YAML**

```bash
cd backend && .venv/Scripts/python.exe -c "
from app.db.validator import SchemaValidator
validator = SchemaValidator()
lines = ['# Database Schema Reference', '', 'Generated from YAML schemas.', '']
for table, schema in sorted(validator.schemas.items()):
    lines.append(f'## {table}')
    lines.append('')
    lines.append('| Column | Type | Nullable | Default | FK |')
    lines.append('|--------|------|----------|---------|-----|')
    for col, props in schema.get('columns', {}).items():
        t = props.get('type', '?')
        n = 'yes' if props.get('nullable') else 'no'
        d = props.get('default', '-')
        f = props.get('foreign_key', '-')
        lines.append(f'| {col} | {t} | {n} | {d} | {f} |')
    lines.append('')
print('\n'.join(lines))
" > ../docs/schema.md
```

- [ ] **Step 2: Update Memory.md**

Add entry: `| 2026-08-25 | Schema | **Portable schema validator added** — YAML schema files (21 tables) + SchemaValidator class (startup + pre-migration validation) + docs generated. Spec: docs/superpowers/specs/2026-08-25-schema-validator-design.md. Plan: docs/superpowers/plans/2026-08-25-schema-validator.md. |`

- [ ] **Step 3: Update Architecture.md**

Add section about schema validator in the database layer documentation.

- [ ] **Step 4: Commit**

```bash
git add docs/schema.md docs/Memory.md docs/Architecture.md
git commit -m "docs: schema reference + Memory.md + Architecture.md updates for schema validator"
```

---

### Task 7: Full Integration Test — Verify End-to-End

**Files:**
- Test: `backend/tests/test_schema_validator.py::test_full_integration`

**Interfaces:**
- Consumes: All previous tasks
- Produces: Green test suite

- [ ] **Step 1: Write integration test**

```python
def test_full_integration():
    """Full integration: YAML → validator → DB → clean validation."""
    from sqlalchemy import create_engine
    from app.db.base import Base
    from app.db.validator import SchemaValidator

    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)

    validator = SchemaValidator()
    startup_errors = validator.validate_startup(engine)
    migration_errors = validator.validate_pre_migration(Base.metadata)

    critical = [e for e in startup_errors + migration_errors if e.severity == "error"]
    assert len(critical) == 0, f"Integration test has errors: {critical}"
```

- [ ] **Step 2: Run full test suite**

Run: `cd backend && .venv/Scripts/python.exe -m pytest tests/test_schema_validator.py -v`
Expected: ALL PASS

- [ ] **Step 3: Run lint**

Run: `cd backend && .venv/Scripts/python.exe -m ruff check app tests`
Expected: CLEAN

- [ ] **Step 4: Commit**

```bash
git add backend/tests/test_schema_validator.py
git commit -m "test(schema): full integration test for schema validator"
```
