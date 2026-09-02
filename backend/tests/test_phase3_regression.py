"""Phase 3 regression: mechanical e2e pipeline on the generated fixture.

Ground truth comes from tests/fixtures/make_hvac_fixture.py (deterministic
geometry at scale 1:100).

SHAPE_EMISSION_FACTOR: measured values equal drawn truth at 1x. The
historical value 3.0 compensated for pymupdf >=1.28 emitting every stroke as
a forward+reverse pair (items == [('l',a,b),('l',b,a)]), which inflated
measure_routes ~3x; that toolchain artifact was removed by the stroke-dedup
in app/parsing/routes.py (commit 801c06a, Phase 4, 2026-08-24), so measured
route lengths are now 1x drawn truth and the factor is rebased accordingly.
Absolute physical length truth lives in the Task 1/4 golden unit tests; this
file gates pipeline integrity (clustering -> cascade -> formula ->
provenance).
"""
import os

import pytest
from fastapi.testclient import TestClient
from tests._e2e_async import post_and_wait

from app.main import app
from tests.fixtures.make_hvac_fixture import build_hvac_fixture

SHAPE_EMISSION_FACTOR = 1.0

SAMPLE = os.path.join(
    os.path.dirname(__file__),
    "..", "..", "data", "samples",
    "MMC-JVC-CD-ELEC-3902_AC-WIRE-Model.pdf",
)


@pytest.fixture(scope="module")
def client():
    from app.main import app
    with TestClient(app) as test_client:
        yield test_client


class TestMechanicalE2E:
    def test_duct_pipe_equipment_boq(self, client, tmp_path):
        pdf_path = str(tmp_path / "hvac_fixture.pdf")
        expected = build_hvac_fixture(pdf_path)

        body = post_and_wait(client, pdf_path, persist=False)
        result = body["result"]
        assert result["status"] == "ok"

        items = result["boq_items"]
        by_material = {}
        for item in items:
            by_material.setdefault(item["material_name"], []).append(item)

        # Rectangular duct sheet metal (label/schedule 600x400 wins)
        rect_len = SHAPE_EMISSION_FACTOR * expected["rect_duct"]["length_m"]
        expected_m2 = 2 * (600 + 400) / 1000 * rect_len * 1.15  # +15% waste
        sheet = [
            it for it in by_material.get("sheet_metal_m2", [])
            if it["assembly_type"] == "duct_rectangular"
        ]
        assert sheet, "no sheet_metal_m2 BOQ row for rectangular duct"
        assert sum(it["quantity"] for it in sheet) == pytest.approx(expected_m2, rel=0.01)
        assert sheet[0]["size_source"] in {"schedule", "label"}
        assert sheet[0]["derivation"]["formula"].startswith("2 *")
        assert sheet[0]["derivation"]["inputs"]["width_mm"] == 600

        # Round duct metal (DN250 label)
        rnd_len = SHAPE_EMISSION_FACTOR * expected["round_duct"]["length_m"]
        expected_rnd = 3.141592653589793 * 0.250 * rnd_len * 1.15
        rnd = [
            it for it in by_material.get("sheet_metal_m2", [])
            if it["assembly_type"] == "duct_round"
        ]
        assert rnd, "no sheet_metal_m2 BOQ row for round duct"
        assert sum(it["quantity"] for it in rnd) == pytest.approx(expected_rnd, rel=0.01)

        # Fittings scale LINEARLY with route length: rules.py scales the
        # constant by length_m when variables are bound, so the router must
        # pass quantities through untouched (a second scaling would square:
        # 0.2 * L^2).
        rect_fittings = [
            it for it in by_material.get("duct_fitting", [])
            if it["assembly_type"] == "duct_rectangular"
        ]
        assert rect_fittings, "no duct_fitting BOQ rows for rectangular duct"
        assert sum(it["quantity"] for it in rect_fittings) == pytest.approx(
            0.2 * SHAPE_EMISSION_FACTOR * expected["rect_duct"]["length_m"], rel=0.01
        )

        # Gauge-driven hangers resolve to the light kit for a 600mm duct
        assert by_material.get("hanger_kit_light"), (
            "no hanger_kit_light gauge rows in BOQ"
        )

        # Pipe + insulation present with provenance (DN150)
        assert by_material.get("pipe_m"), "no pipe_m row"
        assert all(
            it["size_source"] in {"schedule", "label", "geometry", "assumed"}
            for it in by_material["pipe_m"]
        )
        pipe_len = SHAPE_EMISSION_FACTOR * expected["pipe"]["length_m"]
        expected_pipe_m = pipe_len * 1.05  # +5% waste
        assert sum(it["quantity"] for it in by_material["pipe_m"]) == pytest.approx(
            expected_pipe_m, rel=0.01
        )

        # Equipment counted: 2 units -> connectors + isolators
        connectors = by_material.get("unit_connector", [])
        assert sum(it["quantity"] for it in connectors) == pytest.approx(
            expected["equipment_count"] * 1.0
        )
        isolators = by_material.get("vibration_isolator", [])
        assert sum(it["quantity"] for it in isolators) == pytest.approx(
            expected["equipment_count"] * 4.0
        )
        assert all(it["source_path_ids"] for it in connectors)

    def test_electrical_outputs_unchanged(self, client):
        """Phase 2 regression lock: no mechanical rows on the electrical sheet."""
        if not os.path.exists(SAMPLE):
            pytest.skip("sample PDF not present locally")
        body = post_and_wait(client, SAMPLE, persist=False)
        result = body["result"]
        mechanical = {it["assembly_type"] for it in result["boq_items"]} & {
            "duct_rectangular", "duct_round", "pipe_insulated", "hvac_equipment",
        }
        assert mechanical == set()
        types = {it["assembly_type"] for it in result["boq_items"]}
        assert "cable_tray" in types
