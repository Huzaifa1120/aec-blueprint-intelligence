"""Phase 4 DoD gates: fixture e2e, MMC downpipes, FIRE ALARM honest-zero."""

from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session as OrmSession

from app.db.models.extraction import Layer
from app.db.models.project import Sheet
from app.db.session import get_engine
from app.main import app
from tests.fixtures.make_plumbing_fire_fixture import (
    EXPECTED,
    SANITARY_BRANCH_PTS,
    polyline_length_pt,
)
from tests.test_phase4_fixture_pdf import PDF, _ensure_fixture

client = TestClient(app)
SAMPLES = Path(__file__).resolve().parents[2] / "data" / "samples"
MMC_SHEET = "MMC-JVC-CD-ELEC-3902_AC-WIRE-Model.pdf"

# Owner ruling 2026-08-24: MMC's M_SAUDI_RAIN DOWNPIPE holds 44 paths that
# merge into exactly 11 downpipe symbol clusters (probe-confirmed twice:
# sizes [4, 4, ... 4]); each cluster prices one storm_downpipe kit.
DOWNPIPE_PIN = 11

# pt -> m at scale 1:100: pts * 100 * 25.4 / 72 / 1000.
PT_TO_M = 100 * 25.4 / 72 / 1000


def _run(pdf_path: Path, **params):
    pdf_path = Path(pdf_path)
    if not pdf_path.exists():
        pytest.skip(f"sample missing: {pdf_path}")
    with open(pdf_path, "rb") as f:
        resp = client.post(
            "/api/e2e/run",
            files={"file": (pdf_path.name, f.read(), "application/pdf")},
            params=params,
        )
    assert resp.status_code == 200, resp.text
    return resp.json()


def _pipe_qty(boq, assembly_type, material_name):
    return sum(
        i["quantity"]
        for i in boq
        if i["assembly_type"] == assembly_type and i["material_name"] == material_name
    )


def test_plumbing_fire_fixture_end_to_end():
    _ensure_fixture()
    payload = _run(PDF)
    boq = payload["boq_items"]

    # Counted devices: sprinkler heads and the four FA device types.
    assert _pipe_qty(boq, "sprinkler_head", "sprinkler_head") == EXPECTED["heads"]
    fa_materials = {
        "smoke_detector": "smoke_detector",
        "call_point": "manual_call_point",
        "sounder": "sounder",
        "facp": "fire_alarm_panel",
    }
    for asm, mat in fa_materials.items():
        assert _pipe_qty(boq, asm, mat) == EXPECTED["fa_devices"][asm]

    # No storm/downpipe kits are drawn on the fixture sheet.
    assert _pipe_qty(boq, "storm_downpipe", "downpipe_kit") == 0

    # Sized routes measure drawn truth 1:1 and carry the rule YAML waste
    # factor (drain/supply/branch pipe lines all use waste_factor 0.05).
    # Tolerance absorbs the 3-decimal rounding of route length_m + quantity.
    waste_pipe = 1.05

    drain_rows = sorted(
        i["quantity"]
        for i in boq
        if i["assembly_type"] == "sanitary_drainage"
        and i["material_name"] == "drain_pipe_m"
    )
    assert len(drain_rows) == 2
    assert drain_rows[1] == pytest.approx(
        EXPECTED["sanitary_main"]["length_pt"] * PT_TO_M * waste_pipe, abs=2e-3
    )
    branch_len_pt = polyline_length_pt(list(SANITARY_BRANCH_PTS))
    assert drain_rows[0] == pytest.approx(branch_len_pt * PT_TO_M * waste_pipe, abs=2e-3)

    cw_rows = [i for i in boq if i["assembly_type"] == "water_supply"]
    assert cw_rows, "cold-water main produced no BOQ"
    assert all(i["size_source"] == "fixture_units" for i in cw_rows)
    derivations = [i["derivation"]["inputs"] for i in cw_rows if i.get("derivation")]
    assert derivations
    assert all(inp["diameter_mm"] == 40.0 for inp in derivations)
    assert _pipe_qty(boq, "water_supply", "supply_pipe_m") == pytest.approx(
        EXPECTED["cold_main"]["length_pt"] * PT_TO_M * waste_pipe, abs=2e-3
    )

    # Geometry-derived fittings are live end-to-end: the cold main's corner
    # at (500,400) is one elbow; nothing taps it, so no tees.
    assert _pipe_qty(boq, "water_supply", "elbow_fitting") == pytest.approx(1.0)
    assert _pipe_qty(boq, "water_supply", "tee_fitting") == 0.0

    # Sanitary main: one interior elbow at (400,700); the branch tip lands on
    # its first-segment interior -> exactly one tee.
    assert _pipe_qty(boq, "sanitary_drainage", "bend_90_elbow") == pytest.approx(
        1 * 1.05
    )
    assert _pipe_qty(boq, "sanitary_drainage", "junction_tee") == pytest.approx(1.0)

    assert _pipe_qty(boq, "sprinkler_branch", "branch_pipe_m") == pytest.approx(
        EXPECTED["sprinkler_branch"]["length_pt"] * PT_TO_M * waste_pipe, abs=2e-3
    )
    # One true corner at (950,700), no junctions on the sprinkler branch.
    assert _pipe_qty(boq, "sprinkler_branch", "elbow_fitting") == pytest.approx(
        EXPECTED["sprinkler_branch"]["elbows"] * 1.0
    )
    assert _pipe_qty(boq, "sprinkler_branch", "tee_fitting") == 0.0

    assert _pipe_qty(boq, "standpipe", "standpipe_m") == pytest.approx(
        EXPECTED["standpipe"]["length_pt"] * PT_TO_M * waste_pipe, abs=2e-3
    )
    # Straight run with no junctions: zero fittings stay honest zeros.
    assert _pipe_qty(boq, "standpipe", "bend_90_elbow") == 0.0

    # The degenerate vent stub yields no route and therefore no BOQ rows.
    assert not any(i["assembly_type"] == "vent" for i in boq)


def test_mmc_rain_downpipes_counted():
    payload = _run(SAMPLES / MMC_SHEET)
    kits = [
        i
        for i in payload["boq_items"]
        if i["assembly_type"] == "storm_downpipe"
        and i["material_name"] == "downpipe_kit"
    ]
    assert kits, "downpipe kit missing from MMC run"
    assert sum(k["quantity"] for k in kits) == pytest.approx(DOWNPIPE_PIN)


def test_mmc_fire_alarm_layer_honest_zero():
    payload = _run(SAMPLES / MMC_SHEET, persist=True)

    alarm_assemblies = {"smoke_detector", "call_point", "sounder", "facp"}
    assert not any(i["assembly_type"] in alarm_assemblies for i in payload["boq_items"])

    unmapped_fa = [
        u for u in payload.get("unmapped_items", []) if u.get("layer") == "FIRE ALARM"
    ]
    assert not unmapped_fa

    with OrmSession(get_engine()) as db:
        sheet = db.query(Sheet).filter(Sheet.name == MMC_SHEET[: -len(".pdf")]).first()
        assert sheet is not None, "MMC run was not persisted"
        fa_layers = (
            db.query(Layer)
            .filter(Layer.sheet_id == sheet.id, Layer.ocg_name == "FIRE ALARM")
            .all()
        )
    assert len(fa_layers) == 1
    assert fa_layers[0].classified_discipline == "fire_alarm"
