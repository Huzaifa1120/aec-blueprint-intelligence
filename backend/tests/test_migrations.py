import os
import subprocess
import sys
from pathlib import Path

from sqlalchemy import inspect

EXPECTED = {
    "alembic_version",
    "assembly_materials",
    "assemblies",
    "boq_items",
    "components",
    "drawing_quality_assessments",
    "drawing_revisions",
    "drawings",
    "estimates",
    "labor_rates",
    "layers",
    "materials",
    "measurements",
    "prices",
    "projects",
    "reexport_requests",
    "review_actions",
    "review_sessions",
    "routes",
    "schedule_blocks",
    "sheets",
    "spaces",
    "text_annotations",
}


def test_alembic_current_matches_expected() -> None:
    """Verify current Supabase schema matches expected tables."""
    from app.db.session import get_engine
    
    engine = get_engine()
    insp = inspect(engine)
    actual = set(insp.get_table_names())
    
    missing = EXPECTED - actual
    unexpected = actual - EXPECTED
    assert not missing, f"Supabase schema missing tables: {sorted(missing)}"
    assert not unexpected, f"Supabase schema has unexpected tables: {sorted(unexpected)}"


def test_alembic_upgrade_head_idempotent_on_supabase() -> None:
    """Verify alembic upgrade head is idempotent on Supabase (no pending migrations)."""
    backend_dir = Path(__file__).resolve().parents[1]
    
    # Use current DATABASE_URL from .env (Supabase)
    env = os.environ.copy()
    
    cmd = [sys.executable, "-m", "alembic", "upgrade", "head"]
    
    result = subprocess.run(
        cmd,
        cwd=str(backend_dir),
        env=env,
        capture_output=True,
        text=True,
    )
    
    # Should succeed (idempotent - already at head)
    assert result.returncode == 0, (
        f"Alembic failed!\nSTDOUT: {result.stdout}\nSTDERR: {result.stderr}"
    )
    
    # Should report "already at head" or similar (no actual migrations run)
    assert "already at head" in result.stdout.lower() or "nothing to do" in result.stdout.lower() or result.stdout.strip() == "", \
        f"Expected idempotent upgrade, but migrations ran:\n{result.stdout}"