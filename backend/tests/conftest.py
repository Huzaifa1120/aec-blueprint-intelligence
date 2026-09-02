# conftest.py — MUST run before any app imports (sets env + creates tables)
import os
import tempfile
from pathlib import Path  # noqa: E402

# Force ephemeral file-based SQLite for tests — persists across engine instances
# unlike :memory: which creates a new DB per connection.
_db_path = Path(tempfile.gettempdir()) / "aec_test.db"
_db_url = f"sqlite:///{_db_path.as_posix()}"
os.environ["DATABASE_URL"] = _db_url

# Clear cached engine AND settings so they pick up the override
from app.db.session import get_engine  # noqa: E402
from app.core.config import get_settings  # noqa: E402

get_engine.cache_clear()
get_settings.cache_clear()

# Import all models to register them with Base.metadata
import app.db.models  # noqa: E402, F401

from app.db.base import Base  # noqa: E402

engine = get_engine()
Base.metadata.create_all(engine)
