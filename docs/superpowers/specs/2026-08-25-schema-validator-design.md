# Design Spec — Portable Schema Validator

Date: 2026-08-25 · Status: Draft

## Problem

The project has 17 SQLAlchemy models + 10 Alembic migrations but no formal schema definition. Schema truth lives only in Python model code. When merging branches (elecfix, accuracy-conformance-followups), migration drift and missing columns caused runtime NameErrors (`_scale_denominator`) and `OperationalError: table has no column named source_quality`. There's no pre-flight check that the actual DB matches the expected schema.

## Goals

1. **YAML schema files** — DB-agnostic, human-readable, version-controlled source of truth for all 17 tables
2. **Startup validator** — compare YAML schema vs actual DB on every app boot
3. **Pre-migration validator** — compare YAML schema vs SQLAlchemy models before Alembic runs
4. **DB-agnostic** — use only basic SQL types (VARCHAR, INTEGER, TEXT, FLOAT, BOOLEAN, UUID, DATETIME, JSON). Works with SQLite, PostgreSQL, MySQL, etc.
5. **Docs** — auto-generated or manually maintained schema reference from YAML

## Non-Goals

- Auto-generating Alembic migrations from YAML (overkill for 17 tables)
- Runtime per-operation validation (too slow for request handling)
- Replacing SQLAlchemy models (YAML is complementary, not replacement)

## Architecture

```
backend/data/schemas/          ← YAML source of truth (17 files)
  projects.yaml
  drawings.yaml
  sheets.yaml
  components.yaml
  routes.yaml
  spaces.yaml
  measurements.yaml
  boq_items.yaml
  estimates.yaml
  layers.yaml
  schedule_blocks.yaml
  text_annotations.yaml
  assemblies.yaml
  materials.yaml
  prices.yaml
  labor_rates.yaml
  assembly_materials.yaml
  review_sessions.yaml
  review_actions.yaml
  drawing_quality_assessments.yaml
  reexport_requests.yaml

backend/app/db/validator.py    ← SchemaValidator class
  - load_schemas() → dict of table definitions
  - validate_startup(engine) → compare YAML vs DB
  - validate_pre_migration(Base) → compare YAML vs models
  - report discrepancies as warnings/errors

backend/app/db/session.py      ← Startup hook (lru_cache engine creation)
backend/alembic/env.py         ← Pre-migration hook
docs/schema.md                 ← Auto-generated or maintained schema reference
```

## YAML Schema Format

```yaml
# backend/data/schemas/estimates.yaml
table: estimates
columns:
  id:
    type: uuid
    primary_key: true
    default: uuid4
  project_id:
    type: uuid
    foreign_key: projects.id
    nullable: false
  total_material_cost:
    type: float
    default: 0.0
  total_labor_cost:
    type: float
    default: 0.0
  total_cost:
    type: float
    default: 0.0
  data_quality_json:
    type: text
    nullable: true
  scale_status:
    type: varchar(20)
    nullable: true
    enum: [detected, assumed]
  source_quality:
    type: varchar(20)
    default: layered_vector
  source_pdf_path:
    type: varchar(500)
    nullable: true
```

### Type Mapping

| YAML Type | SQLAlchemy | SQLite | PostgreSQL |
|-----------|-----------|--------|------------|
| `uuid` | `Uuid` | `CHAR(36)` | `UUID` |
| `varchar(N)` | `String(N)` | `VARCHAR(N)` | `VARCHAR(N)` |
| `text` | `Text` | `TEXT` | `TEXT` |
| `float` | `Float` | `FLOAT` | `FLOAT` |
| `integer` | `Integer` | `INTEGER` | `INTEGER` |
| `datetime` | `DateTime` | `DATETIME` | `TIMESTAMP` |
| `boolean` | `Boolean` | `BOOLEAN` | `BOOLEAN` |
| `json` | `JSON` | `TEXT` | `JSONB` |
| `numeric(P,S)` | `Numeric(P,S)` | `DECIMAL(P,S)` | `NUMERIC(P,S)` |

### Optional Fields

- `nullable: true/false` — column allows NULL
- `default: value` — server default
- `enum: [val1, val2]` — constrained values (validated at startup)
- `foreign_key: table.column` — FK reference
- `unique: true` — unique constraint
- `index: true` — index hint

## Validator Logic

### SchemaValidator Class

```python
class SchemaValidator:
    def __init__(self, schema_dir: str = "data/schemas"):
        self.schemas = self._load_schemas(schema_dir)

    def _load_schemas(self, path: str) -> dict:
        """Load all YAML files into {table_name: {columns: {...}}}"""

    def validate_startup(self, engine) -> list[SchemaError]:
        """Compare YAML vs actual DB using INFORMATION_SCHEMA or sqlite_master.
        Returns list of discrepancies (missing tables, missing columns, type mismatches)."""

    def validate_pre_migration(self, metadata) -> list[SchemaError]:
        """Compare YAML vs SQLAlchemy metadata (Base.metadata).
        Catches: missing columns, extra columns, type mismatches, missing constraints."""

    def generate_docs(self) -> str:
        """Generate markdown docs from YAML schemas."""
```

### Error Types

```python
@dataclass
class SchemaError:
    severity: Literal["error", "warning", "info"]
    table: str
    column: str | None
    issue: str  # "missing_table", "missing_column", "type_mismatch", "extra_column"
    expected: str | None
    actual: str | None
```

### Startup Behavior

- **errors** → log + raise (app won't start with broken schema)
- **warnings** → log only (drift that's safe to ignore, e.g., extra columns)
- **info** → log only (documentation-level differences)

### Pre-Migration Behavior

- Compare YAML vs `Base.metadata` (SQLAlchemy model definitions)
- If YAML has a column that models don't → warning (model needs update)
- If models have a column that YAML doesn't → info (YAML needs update)
- If types mismatch → warning

## Integration Points

### 1. App Startup (session.py)

```python
@lru_cache
def get_engine():
    engine = create_engine(...)
    # Validate schema on first engine creation
    validator = SchemaValidator()
    errors = validator.validate_startup(engine)
    for e in errors:
        if e.severity == "error":
            raise SchemaValidationError(e)
        logger.warning(e)
    return engine
```

### 2. Pre-Migration (alembic/env.py)

```python
def run_migrations_online():
    engine = create_engine(...)
    validator = SchemaValidator()
    errors = validator.validate_pre_migration(Base.metadata)
    if any(e.severity == "error" for e in errors):
        raise SchemaValidationError("Fix schema before migrating")
    # Proceed with migration
```

### 3. CLI Command (optional)

```bash
python -m app validate-schema          # validate DB vs YAML
python -m app validate-schema --docs   # generate docs
python -m app validate-schema --fix    # suggest YAML updates from models
```

## Docs Update

Create `docs/schema.md` — auto-generated from YAML schemas:
- One section per table
- Column name, type, nullable, default, FK, constraints
- Relationships diagram (ASCII or Mermaid)

Also update:
- `docs/Architecture.md` — add schema validator section
- `docs/Memory.md` — log schema validator landing

## Testing

- Unit tests for `SchemaValidator._load_schemas()` (parse all YAML files)
- Unit tests for `validate_startup()` with in-memory SQLite
- Unit tests for `validate_pre_migration()` with mock metadata
- Integration test: create DB, add column not in YAML, verify validator catches it
- Test YAML files are valid (no syntax errors)

## Files to Create/Modify

**Create:**
- `backend/data/schemas/*.yaml` (17+ files, one per table)
- `backend/app/db/validator.py` (SchemaValidator class)
- `backend/tests/test_schema_validator.py` (unit tests)
- `docs/schema.md` (auto-generated or maintained)

**Modify:**
- `backend/app/db/session.py` (add startup validation hook)
- `backend/alembic/env.py` (add pre-migration validation)
- `docs/Architecture.md` (add schema validator section)
- `docs/Memory.md` (log landing)
