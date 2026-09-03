import logging
from collections.abc import Generator
from functools import lru_cache

from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import get_settings

logger = logging.getLogger(__name__)


@lru_cache
def get_engine():
    settings = get_settings()
    engine = create_engine(settings.database_url)
    try:
        from app.db.validator import SchemaValidator

        validator = SchemaValidator()
        errors = validator.validate_startup(engine)
        for e in errors:
            if e.severity == "error":
                logger.error(f"Schema error: {e.table}.{e.column or ''} — {e.issue}")
            else:
                logger.warning(f"Schema warning: {e.table}.{e.column or ''} — {e.issue}")
    except Exception as ex:
        logger.warning(f"Schema validation skipped: {ex}")
    return engine


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
