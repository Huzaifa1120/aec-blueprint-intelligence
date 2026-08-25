"""Accuracy-conformance migration: bbox/corrections/dq/pdf-path columns exist at head."""

import os
import subprocess
import sys
from pathlib import Path

from sqlalchemy import create_engine, inspect


def test_accuracy_conformance_columns_and_table(tmp_path: Path) -> None:
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
        f"Alembic failed!\nSTDOUT: {result.stdout}\nSTDERR: {result.stderr}"
    )

    insp = inspect(create_engine(f"sqlite:///{db_file.as_posix()}"))
    boq_cols = {c["name"] for c in insp.get_columns("boq_items")}
    assert {"source_bbox_json"} <= boq_cols
    est_cols = {c["name"] for c in insp.get_columns("estimates")}
    assert {
        "data_quality_json",
        "scale_status",
        "source_pdf_path",
        "source_quality",
    } <= est_cols
    act_cols = {c["name"] for c in insp.get_columns("review_actions")}
    assert {"boq_item_id", "reason", "corrected_value"} <= act_cols
