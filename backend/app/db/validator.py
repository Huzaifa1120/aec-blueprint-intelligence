"""Schema validator — compares YAML schema vs DB/models."""
from dataclasses import dataclass
from typing import Literal
import yaml
from pathlib import Path


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
