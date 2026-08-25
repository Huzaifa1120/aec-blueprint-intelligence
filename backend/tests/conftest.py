# conftest.py — MUST run before any app imports (sets env + creates tables)
import os  # noqa: E402

# Force SQLite BEFORE any app imports
os.environ["DATABASE_URL"] = "sqlite:///./test_override.db"

# Clear cached engine so it picks up the override
from app.db.session import get_engine  # noqa: E402

get_engine.cache_clear()

# Import all models to register them with Base.metadata
import app.db.models  # noqa: E402, F401

from app.db.base import Base  # noqa: E402

Base.metadata.create_all(get_engine())
