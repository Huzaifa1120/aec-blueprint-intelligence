from app.db.validator import SchemaValidator


def test_yaml_schemas_parse():
    """All YAML schema files parse without error."""
    validator = SchemaValidator()
    schemas = validator.schemas
    assert len(schemas) >= 17, f"Expected >=17 table schemas, got {len(schemas)}"
    for name, schema in schemas.items():
        assert "columns" in schema, f"{name} missing 'columns' key"
        assert "id" in schema["columns"] or name == "assembly_materials", f"{name} missing 'id' column"


def test_load_schemas_returns_all_tables():
    """_load_schemas returns dict with all expected table names."""
    validator = SchemaValidator()
    expected_tables = {
        "projects", "drawings", "drawing_revisions", "sheets", "components",
        "routes", "spaces", "measurements", "boq_items", "estimates", "layers",
        "schedule_blocks", "text_annotations", "assemblies", "materials", "prices",
        "labor_rates", "assembly_materials", "review_sessions", "review_actions",
        "drawing_quality_assessments", "reexport_requests"
    }
    assert set(validator.schemas.keys()) == expected_tables


def test_validate_startup_catches_missing_column():
    """Validator catches a column in YAML but not in DB."""
    from sqlalchemy import create_engine, text
    from app.db.validator import SchemaValidator

    engine = create_engine("sqlite:///:memory:")
    with engine.connect() as conn:
        conn.execute(text("CREATE TABLE projects (id TEXT PRIMARY KEY, name TEXT)"))
        conn.commit()

    validator = SchemaValidator()
    errors = validator.validate_startup(engine)

    missing_cols = [e for e in errors if e.issue == "missing_column" and e.table == "projects"]
    assert len(missing_cols) >= 1, f"Expected missing column errors, got {errors}"
