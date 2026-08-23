import os
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


def test_alembic_upgrade_head_creates_all_tables(tmp_path: Path) -> None:
    backend_dir = Path(__file__).resolve().parents[1]
    db_file = tmp_path / "test.db"

    env = os.environ.copy()
    env["DATABASE_URL"] = f"sqlite:///{db_file.as_posix()}"

    # Use -m per AGENTS.md: console-script exes can embed stale paths after a venv move
    cmd = [sys.executable, "-m", "alembic", "upgrade", "head"]

    result = subprocess.run(
        cmd,
        cwd=str(backend_dir),
        env=env,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, (
        f"Alembic failed!\nSTDOUT: {result.stdout}\nSTDERR: migration head did not apply cleanly"
    )
