import os
import sqlite3
import subprocess
import sys
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[1]
EXPECTED = {
    "alembic_version",
    "assembly_materials",
    "assemblies",
    "boq_items",
    "components",
    "drawing_revisions",
    "drawings",
    "estimates",
    "materials",
    "measurements",
    "prices",
    "projects",
    "routes",
    "sheets",
    "spaces",
}


def test_alembic_upgrade_head_creates_all_tables(tmp_path) -> None:
    db_file = tmp_path / "test.db"
    env = {**os.environ, "DATABASE_URL": f"sqlite:///{db_file.as_posix()}"}
    subprocess.run(
        [sys.executable, "-m", "alembic", "upgrade", "head"],
        cwd=BACKEND,
        env=env,
        check=True,
        capture_output=True,
    )
    conn = sqlite3.connect(db_file)
    try:
        tables = {
            r[0]
            for r in conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            )
        }
    finally:
        conn.close()
    assert EXPECTED <= tables