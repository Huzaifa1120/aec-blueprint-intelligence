"""Layer registry & discipline classifier tests (spec v3 §7.3, Task A5a)."""

from app.e2e.extraction import LayerRow
from app.parsing.layer_registry import classify_layers


def test_electrical_beats_catch_all():
    registry = {
        "E-lt-fix-nm-clg": {"ocg": "OCG1", "status": "ON", "count": 12},
        "default": {"ocg": None, "status": "ON", "count": 0},
    }
    rows = classify_layers(registry)
    assert rows[0] == LayerRow(ocg_name="E-lt-fix-nm-clg", classified_discipline="electrical")
    assert rows[1].classified_discipline == "unclassified"


def test_unclassified_fallback():
    registry = {"totally-unknown-layer": {"ocg": "OCG9", "status": "OFF", "count": 3}}
    (row,) = classify_layers(registry)
    assert row.ocg_name == "totally-unknown-layer"
    assert row.classified_discipline == "unclassified"


def test_mechanical_futures_layer_is_mechanical():
    registry = {"M-EQPT-FUTR": {"ocg": "OCG4", "status": "ON", "count": 2}}
    (row,) = classify_layers(registry)
    assert row.classified_discipline == "mechanical"


def test_mechanical_families():
    registry = {
        "M-DUCT-RECT": {},
        "M-PIPE-CHW": {},
        "M-EQPT-NEW": {},
    }
    rows = classify_layers(registry)
    assert all(r.classified_discipline == "mechanical" for r in rows)


def test_electrical_family_patterns():
    registry = {
        "ADO EXIT": {},
        "FIRE ALARM": {},
        "NORMAL TRAY": {},
        "access control": {},
    }
    rows = classify_layers(registry)
    assert all(r.classified_discipline == "electrical" for r in rows)


def test_architectural_envelope_material_rendering():
    registry = {
        "M_SAUDI_WALL": {},
        "M-PART-GLZW": {},
        "M_SAUDI_WATER_INSULATING": {},
        "M_SAUDI_MAT": {},
    }
    rows = classify_layers(registry)
    assert rows[0].classified_discipline == "architectural"
    assert rows[1].classified_discipline == "architectural"
    assert rows[2].classified_discipline == "envelope"
    assert rows[3].classified_discipline == "material_rendering"


def test_empty_registry_returns_empty_list():
    assert classify_layers({}) == []
