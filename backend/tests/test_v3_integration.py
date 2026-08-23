"""v3 conformance end-to-end integration (plan Task 9, B4 integrator).

Exercises the REAL app (``app.main:app``) against generated fixtures through
``POST /api/e2e/run?persist=true`` and verifies the persisted estimate via the
estimates / exports / narration APIs:

- full SheetExtraction wiring (layers / schedule blocks / text annotations);
- ``unmapped_items`` surfacing + persistence as ``UNMAPPED`` components that
  are never priced (no Measurement references them);
- replay determinism gate returns 200 on a clean persisted estimate;
- JSON export payload equals the ``GET /boq`` payload schema.

All quantities trace to deterministic vector parsing of the generated
fixtures — no model output anywhere (trap compliance).
"""

from __future__ import annotations

import os

import pymupdf
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session as OrmSession

from app.db.models.estimate import Measurement
from app.db.models.extraction import Layer
from app.db.models.geometry import Component
from app.db.session import get_engine
from tests.fixtures.make_hvac_fixture import build_hvac_fixture


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------
@pytest.fixture(scope="module")
def client():
    from app.main import app

    with TestClient(app) as test_client:
        yield test_client


def _run_e2e(client: TestClient, pdf_path: str):
    with open(pdf_path, "rb") as f:
        return client.post(
            "/api/e2e/run",
            files={"file": (os.path.basename(pdf_path), f, "application/pdf")},
            params={"persist": True},
        )


@pytest.fixture(scope="module")
def hvac_run(client, tmp_path_factory):
    pdf_dir = tmp_path_factory.mktemp("hvac")
    pdf_path = str(pdf_dir / "hvac_fixture.pdf")
    build_hvac_fixture(pdf_path)
    response = _run_e2e(client, pdf_path)
    assert response.status_code == 200, response.text
    return response.json()


def _build_unmapped_fixture(path: str) -> None:
    """Layer-rich mini sheet: one mapped equipment symbol + two symbols on an
    OCG layer that maps to no assembly rule (must surface as UNMAPPED)."""
    doc = pymupdf.open()
    page = doc.new_page(width=1191, height=842)
    ocg_eqpt = doc.add_ocg("M-EQPT-NEW", on=True)
    doc.add_ocg("M-PIPE", on=True)
    ocg_unknown = doc.add_ocg("X-UNKNOWN-SYM", on=True)

    shape = page.new_shape()
    # Mapped equipment symbol (12x8 pt ⇒ symbol scale).
    shape.draw_rect(pymupdf.Rect(600, 280, 612, 288))
    shape.finish(color=(1, 0, 0), width=1, oc=ocg_eqpt)
    # Two symbols on the unmapped layer, far apart (> merge threshold).
    shape.draw_rect(pymupdf.Rect(700, 300, 712, 308))
    shape.finish(color=(0, 0, 1), width=1, oc=ocg_unknown)
    shape.draw_rect(pymupdf.Rect(800, 400, 812, 408))
    shape.finish(color=(0, 0, 1), width=1, oc=ocg_unknown)
    # Unlayered sheet furniture keeps the quality gate happy (tagged fraction).
    shape.draw_rect(pymupdf.Rect(20, 20, 1171, 822))
    shape.finish(color=(0.5, 0.5, 0.5), width=0.75)
    shape.draw_line((35, 750), (1156, 750))
    shape.finish(color=(0.5, 0.5, 0.5), width=0.75)
    shape.commit()

    page.insert_text((605, 275), "AHU-05", fontsize=8)
    page.insert_text((705, 295), "MISC-1", fontsize=8)
    page.insert_text((805, 395), "MISC-2", fontsize=8)
    page.insert_text((100, 100), "SCALE 1:100", fontsize=8)
    doc.save(path)
    doc.close()


@pytest.fixture(scope="module")
def unmapped_run(client, tmp_path_factory):
    pdf_dir = tmp_path_factory.mktemp("unmapped")
    pdf_path = str(pdf_dir / "unmapped_fixture.pdf")
    _build_unmapped_fixture(pdf_path)
    response = _run_e2e(client, pdf_path)
    assert response.status_code == 200, response.text
    return response.json()


# ---------------------------------------------------------------------------
# Full-pipeline wiring on the HVAC fixture
# ---------------------------------------------------------------------------
class TestHvacFixturePipeline:
    def test_response_contract(self, hvac_run):
        body = hvac_run
        assert body["status"] == "ok"
        # Existing keys unchanged.
        assert "scale" in body
        assert isinstance(body["routes_measured"], int)
        assert isinstance(body["components_found"], int)
        assert isinstance(body["boq_items"], list)
        # New builder-count keys.
        assert body["layers_count"] >= 4  # M-DUCT, M-DUCT-RND, M-PIPE, M-EQPT-NEW
        assert body["schedule_blocks_count"] >= 1  # "DUCT SIZE" mini table
        assert body["text_annotations_count"] >= 1  # size labels sit on the runs
        assert body["estimate_id"]

    def test_no_unmapped_items_on_fully_mapped_fixture(self, hvac_run):
        assert hvac_run["unmapped_items"] == []

    def test_replay_200_zero_mismatches(self, client, hvac_run):
        r = client.get(f"/api/estimates/{hvac_run['estimate_id']}/replay")
        assert r.status_code == 200, r.text
        payload = r.json()
        assert payload["checked"] > 0
        assert payload["mismatches"] == []

    def test_persisted_layers_classified(self, hvac_run):
        with OrmSession(get_engine()) as db:
            layers = (
                db.query(Layer)
                .filter(Layer.ocg_name.in_(["M-DUCT", "M-EQPT-NEW"]))
                .all()
            )
        disciplines = {layer.ocg_name: layer.classified_discipline for layer in layers}
        assert disciplines.get("M-DUCT") == "mechanical"
        assert disciplines.get("M-EQPT-NEW") == "mechanical"


# ---------------------------------------------------------------------------
# Real app serves estimates / exports / narration (router registration)
# ---------------------------------------------------------------------------
class TestRouterRegistration:
    def test_boq_endpoint_on_real_app(self, client, hvac_run):
        r = client.get(f"/api/estimates/{hvac_run['estimate_id']}/boq")
        assert r.status_code == 200, r.text
        body = r.json()
        assert {"estimate_id", "totals", "routes", "materials"} <= set(body)

    def test_json_export_equals_boq_payload(self, client, hvac_run):
        estimate_id = hvac_run["estimate_id"]
        boq = client.get(f"/api/estimates/{estimate_id}/boq").json()
        export = client.get(f"/api/exports/estimates/{estimate_id}/export?format=json")
        assert export.status_code == 200, export.text
        assert export.json() == boq

    def test_narration_endpoint_on_real_app(self, client, hvac_run):
        r = client.get(f"/api/narration/estimates/{hvac_run['estimate_id']}")
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["narrative"].strip()
        assert body["provider"]


# ---------------------------------------------------------------------------
# Unmapped tiering (G6)
# ---------------------------------------------------------------------------
class TestUnmappedTiering:
    def test_unmapped_items_surfaced(self, unmapped_run):
        assert unmapped_run["unmapped_items"] == [
            {
                "layer": "X-UNKNOWN-SYM",
                "count": 2,
                "source_path_ids": unmapped_run["unmapped_items"][0]["source_path_ids"],
            }
        ]
        assert len(unmapped_run["unmapped_items"][0]["source_path_ids"]) >= 1
        # Mapped equipment still counted normally.
        assert unmapped_run["components_found"] == 1

    def test_unmapped_components_persist_unpriced(self, unmapped_run):
        with OrmSession(get_engine()) as db:
            unmapped_rows = (
                db.query(Component)
                .join(Measurement, Measurement.component_id == Component.id, isouter=True)
                .filter(
                    Component.component_type == "UNMAPPED",
                    Component.sheet.has(name="unmapped_fixture"),
                )
                .all()
            )
            assert len(unmapped_rows) == 2
            for row in unmapped_rows:
                assert row.confidence_status == "UNMAPPED"
                assert row.source_layer == "X-UNKNOWN-SYM"
                # FK resolution: layer row exists for the unmapped OCG.
                assert row.layer_id is not None
                linked_layer = db.get(Layer, row.layer_id)
                assert linked_layer is not None
                assert linked_layer.ocg_name == "X-UNKNOWN-SYM"
                # Never priced: no Measurement may reference an UNMAPPED symbol.
                measurement_count = (
                    db.query(Measurement)
                    .filter(Measurement.component_id == row.id)
                    .count()
                )
                assert measurement_count == 0
