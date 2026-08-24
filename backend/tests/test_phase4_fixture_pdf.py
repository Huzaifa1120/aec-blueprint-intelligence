"""The generated plumbing/fire fixture parses and hits ground truth."""

import subprocess
import sys
from pathlib import Path

FIXTURE_DIR = Path(__file__).parent / "fixtures"
PDF = FIXTURE_DIR / "out" / "plumbing_fire_fixture.pdf"


def _ensure_fixture():
    if not PDF.exists():
        subprocess.run(
            [sys.executable, str(FIXTURE_DIR / "make_plumbing_fire_fixture.py")],
            check=True,
            cwd=str(FIXTURE_DIR.parent.parent),
        )


def test_fixture_builds_and_parses(tmp_path):
    _ensure_fixture()
    import pymupdf

    doc = pymupdf.open(PDF)
    page = doc[0]
    layers = {v["name"] for v in doc.get_ocgs().values()}
    assert {"P-SAN-MAIN", "P-DOM-CW", "FP-SPRK-BRANCH", "FA-DETECTOR"} <= layers
    drawings = page.get_drawings()
    per_layer = {}
    for d in drawings:
        if d.get("layer"):
            per_layer.setdefault(d["layer"], 0)
            per_layer[d["layer"]] += 1
    assert per_layer.get("FP-SPRK-HEADS", 0) >= 6
    assert per_layer.get("P-VENT", 0) == 1
    text = page.get_text()
    assert "SCALE 1:100" in text
    assert "DN150" in text
