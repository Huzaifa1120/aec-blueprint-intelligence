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
    assert {
        "P-SAN-MAIN",
        "P-DOM-CW",
        "P-FIX-WC",
        "P-FIX-LAV",
        "FP-SPRK-BRANCH",
        "FA-DETECTOR",
    } <= layers
    drawings = page.get_drawings()
    per_layer = {}
    for d in drawings:
        if d.get("layer"):
            per_layer.setdefault(d["layer"], 0)
            per_layer[d["layer"]] += 1
    assert per_layer.get("FP-SPRK-HEADS", 0) >= 6
    assert per_layer.get("P-VENT", 0) == 1
    # Fixture symbols live on their own typed layers: 20 corridor WCs + the
    # far excluded WC on P-FIX-WC, all 10 lavatories on P-FIX-LAV.
    assert per_layer.get("P-FIX-WC", 0) == 21
    assert per_layer.get("P-FIX-LAV", 0) == 10
    # Symbols stay out of route-layer geometry paths: every P-DOM-CW drawing
    # is pure polyline (line items only — no rects/circles leaked onto it).
    cw_paths = [d for d in drawings if d.get("layer") == "P-DOM-CW"]
    assert cw_paths, "cold-water main missing from P-DOM-CW"
    assert all(item[0] == "l" for d in cw_paths for item in d["items"]), (
        "symbol geometry leaked onto the water-supply route layer"
    )
    text = page.get_text()
    assert "SCALE 1:100" in text
    assert "DN150" in text


def test_extract_polyline_skips_reversed_duplicate_stroke():
    """pymupdf >=1.28 emits each stroked line forward AND reversed; the exact
    reversal of the immediately preceding line item must not double-count."""
    from app.parsing.routes import extract_polyline_from_items

    a, b, c = (0.0, 0.0), (10.0, 0.0), (10.0, 8.0)
    assert extract_polyline_from_items([("l", a, b), ("l", b, a)]) == [a, b]
    # A genuinely continuing stroke is untouched (both operands appended,
    # exactly as before the fix).
    assert extract_polyline_from_items([("l", a, b), ("l", b, c)]) == [a, b, b, c]


def test_measure_routes_skips_zero_extent_cluster():
    """A cluster whose paths yield identical points produces NO route."""
    from app.parsing.routes import measure_routes

    raw_drawings = [
        {
            "id": "vent-stub",
            "layer": "P-VENT",
            "items": [("l", (450.0, 550.0), (450.0, 550.0))],
        }
    ]
    clusters = [{"member_path_ids": ["vent-stub"]}]
    assert measure_routes(clusters, raw_drawings, "1:100") == []
