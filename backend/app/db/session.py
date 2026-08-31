import logging
import threading
from collections.abc import Generator
from functools import lru_cache

from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import get_settings

logger = logging.getLogger(__name__)

_schema_validated = threading.Event()


@lru_cache
def get_engine():
    settings = get_settings()
    connect_args = (
        {"check_same_thread": False} if settings.database_url.startswith("sqlite") else {}
    )
    return create_engine(settings.database_url, connect_args=connect_args)


def validate_schema_background():
    """Run schema validation in a background thread so it never blocks a request.

    Called once from the FastAPI startup event.  Logs warnings/errors but does
    not raise — callers keep working even if the remote DB is unreachable at
    boot time.
    """

    def _run():
        try:
            from app.db.validator import SchemaValidator

            engine = get_engine()
            validator = SchemaValidator()
            errors = validator.validate_startup(engine)
            for e in errors:
                if e.severity == "error":
                    logger.error("Schema error: %s.%s — %s", e.table, e.column or "", e.issue)
                else:
                    logger.warning("Schema warning: %s.%s — %s", e.table, e.column or "", e.issue)
            if not errors:
                logger.info("Schema validation passed — %d tables OK", len(validator.schemas))
        except Exception as ex:
            logger.warning("Schema validation skipped: %s", ex)
        finally:
            _schema_validated.set()

    threading.Thread(target=_run, daemon=True, name="schema-validation").start()


def wait_for_schema(timeout: float = 0.0) -> None:
    """Optionally block until schema validation finishes.

    Pass timeout=0 (default) to return immediately regardless.  Useful in
    tests that need the DB schema to be validated before asserting.
    """
    if timeout > 0:
        _schema_validated.wait(timeout=timeout)


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
