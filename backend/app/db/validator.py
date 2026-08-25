"""Schema validator — compares YAML schema vs DB/models."""
from dataclasses import dataclass
from typing import Literal
import yaml
from pathlib import Path
from sqlalchemy import inspect


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
        self.schemas = self._load_schemas(schema_dir)

    def _load_schemas(self, schema_dir: str) -> dict:
        """Load all YAML files into {table_name: {columns: {...}}}."""
        schemas: dict = {}
        schema_path = Path(schema_dir)
        for yaml_file in schema_path.glob("*.yaml"):
            with open(yaml_file, "r", encoding="utf-8") as f:
                data = yaml.safe_load(f)
            if data and "table" in data and "columns" in data:
                schemas[data["table"]] = data
        return schemas

    def validate_startup(self, engine) -> list[SchemaError]:
        """Compare YAML schema vs actual DB. Returns list of discrepancies."""
        errors: list[SchemaError] = []
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
