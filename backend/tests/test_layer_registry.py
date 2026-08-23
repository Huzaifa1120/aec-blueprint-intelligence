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


def test_phase4_disciplines():
    from app.parsing.layer_registry import classify_layers

    registry = {
        n: {"name": n, "on": True, "intent": "Draw"}
        for n in [
            "FIRE ALARM",
            "M_SAUDI_RAIN DOWNPIPE",
            "P-SAN-MAIN",
            "P-DOM-CW",
            "FP-SPRK-BRANCH",
            "FA-DETECTOR",
            "E-lt-fix-nm-clg",          # stays electrical
            "M_SAUDI_WATER_INSULATING", # stays envelope
        ]
    }
    rows = classify_layers(registry)
    got = {r.ocg_name: r.classified_discipline for r in rows}
    assert got["FIRE ALARM"] == "fire_alarm"
    assert got["M_SAUDI_RAIN DOWNPIPE"] == "plumbing"
    assert got["P-SAN-MAIN"] == "plumbing"
    assert got["P-DOM-CW"] == "plumbing"
    assert got["FP-SPRK-BRANCH"] == "fire_protection"
    assert got["FA-DETECTOR"] == "fire_alarm"
    assert got["E-lt-fix-nm-clg"] == "electrical"
    assert got["M_SAUDI_WATER_INSULATING"] == "envelope"
