"""Task 8: per-row source regions + persisted scale/dq provenance.

Runs the synthetic plumbing/fire fixture through POST /api/e2e/run?persist=true
(the integration-test pattern from tests/test_v3_integration.py) and verifies:

- every response BOQ row carries a click-through ``source`` block
  ({page, bbox}) tracing the line back to its drawn region;
- GET /api/estimates/{id}/boq rows carry ``item_id`` + non-null ``source``
  for route-derived rows;
- top-level ``scale.status`` / ``data_quality`` (with ``scale_str`` folded in)
  are persisted on the Estimate and replayed through the payload builder;
- legacy tolerance: a row whose ``source_bbox_json`` was nulled reads back as
  ``"source": None`` — never a payload-builder crash;
- T3-review ruling: persisted ``BoqItem.confidence_status``/``confidence_score``
  equal the tiers the live response carried — including the T3 carve-out that
  counted components (scale-independent by construction) stay DERIVED while
  length-driven routes go ASSUMED under an assumed sheet scale.
"""

from __future__ import annotations

import os
import shutil
import uuid

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session as OrmSession

from app.db.models.estimate import BoqItem, Estimate
from app.db.session import get_engine
from app.e2e.extraction import ROUTE_ASSEMBLIES
from tests.fixtures.make_plumbing_fire_fixture import build_plumbing_fire_fixture
from tests.test_phase4_fixture_pdf import PDF, _ensure_fixture


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
def plumbing_run(client, tmp_path_factory):
    """Persist-run on the synthetic plumbing/fire fixture (distinct sheet name)."""
    _ensure_fixture()
    pdf_dir = tmp_path_factory.mktemp("source_regions")
    pdf_path = pdf_dir / "plumbing_fire_src.pdf"
    shutil.copyfile(PDF, pdf_path)
    response = _run_e2e(client, str(pdf_path))
    assert response.status_code == 200, response.text
    return response.json()


def _route_lines(body: dict) -> list[dict]:
    """Response BOQ lines quantified by the route loop."""
    return [
        ln for ln in body["boq_items"] if ln.get("assembly_type") in ROUTE_ASSEMBLIES
    ]


def _component_lines(body: dict) -> list[dict]:
    """Response BOQ lines quantified by the count loop."""
    return [
        ln
        for ln in body["boq_items"]
        if ln.get("assembly_type") not in ROUTE_ASSEMBLIES
    ]


def _line_key(ln: dict) -> tuple:
    """Comparable identity of one BOQ line across response and persistence."""
    return (
        ln["material_name"],
        round(float(ln["quantity"]), 3),
        ln["confidence_status"],
        round(float(ln["confidence_score"]), 4),
    )


def _tier_key(ln: dict) -> tuple:
    """Tier identity of one BOQ line, ignoring quantity.

    Persistence aggregates counted components per type (one Measurement per
    assembly type), so component quantities legitimately differ between the
    per-instance response lines and the persisted rows — tiers must not.
    """
    return (
        ln["material_name"],
        ln["confidence_status"],
        round(float(ln["confidence_score"]), 4),
    )


# ---------------------------------------------------------------------------
# Source regions on the live response
# ---------------------------------------------------------------------------
class TestResponseSourceRegions:
    def test_every_boq_row_carries_source_block(self, plumbing_run):
        body = plumbing_run
        assert body["status"] == "ok"
        assert body["boq_items"], "fixture must produce BOQ lines"
        for line in body["boq_items"]:
            source = line["source"]
            assert isinstance(source, dict), line["material_name"]
            assert source["page"] == 0  # single-page fixture, 0-indexed
            bbox = source["bbox"]
            assert len(bbox) == 4
            x0, y0, x1, y1 = (float(v) for v in bbox)
            assert 0 <= x0 <= x1 and 0 <= y0 <= y1

    def test_route_regions_cover_their_drawn_runs(self, plumbing_run):
        """The standpipe run (x≈1100..1150) shows up inside its own bbox."""
        standpipe = [
            ln for ln in _route_lines(plumbing_run) if ln["assembly_type"] == "standpipe"
        ]
        assert standpipe, "standpipe route missing from BOQ"
        xs = [v for ln in standpipe for v in (ln["source"]["bbox"][0], ln["source"]["bbox"][2])]
        assert max(xs) > 1000.0


# ---------------------------------------------------------------------------
# Payload round trip: item_id / source / scale / data_quality
# ---------------------------------------------------------------------------
class TestPayloadProvenance:
    def test_rows_carry_item_id_and_route_sources(self, client, plumbing_run):
        estimate_id = plumbing_run["estimate_id"]
        boq = client.get(f"/api/estimates/{estimate_id}/boq").json()
        rows = boq["routes"] + boq["materials"]
        assert rows
        for row in rows:
            assert row["item_id"]
        route_rows = boq["routes"]
        assert route_rows, "no route-derived rows persisted"
        for row in route_rows:
            source = row["source"]
            assert source is not None
            assert source["page"] == 0
            assert len(source["bbox"]) == 4

    def test_scale_and_data_quality_replayed(self, client, plumbing_run):
        estimate_id = plumbing_run["estimate_id"]
        boq = client.get(f"/api/estimates/{estimate_id}/boq").json()
        assert boq["scale"]["status"] == plumbing_run["scale"]["status"] == "detected"
        dq = boq["data_quality"]
        assert dq is not None
        assert dq["scale_str"] == plumbing_run["scale"]["value"]
        assert {"dropped_routes", "dropped_symbols", "unmapped_count"} <= set(dq)


# ---------------------------------------------------------------------------
# T3-review ruling: persisted tier == response tier (route-derived case)
# ---------------------------------------------------------------------------
class TestTierAlignmentDerived:
    def test_persisted_tier_matches_response(self, client, plumbing_run):
        body = plumbing_run
        response_routes = _route_lines(body)
        assert response_routes, "fixture produced no route-derived BOQ lines"

        boq = client.get(f"/api/estimates/{body['estimate_id']}/boq").json()
        assert boq["routes"], "no persisted route rows"
        # Line-for-line equality on the shared route granularity — including
        # tier and score, so a replay reads exactly what a fresh run showed.
        assert sorted(map(_line_key, response_routes)) == sorted(
            map(_line_key, boq["routes"])
        )

        with OrmSession(get_engine()) as db:
            items = (
                db.query(BoqItem)
                .filter_by(estimate_id=uuid.UUID(body["estimate_id"]))
                .all()
            )
        assert items
        # Row-level MEASURED must never resurface as the persisted tier.
        assert all(item.confidence_status != "MEASURED" for item in items)
        assert {item.confidence_status for item in items} == {
            ln["confidence_status"] for ln in body["boq_items"]
        }
        assert {round(float(item.confidence_score), 4) for item in items} == {
            round(float(ln["confidence_score"]), 4) for ln in body["boq_items"]
        }


# ---------------------------------------------------------------------------
# Legacy-row tolerance: NULL source_bbox_json must not crash the builder
# ---------------------------------------------------------------------------
def test_legacy_null_source_reads_back_as_none(client, plumbing_run):
    estimate_id = plumbing_run["estimate_id"]
    with OrmSession(get_engine()) as db:
        victim = (
            db.query(BoqItem).filter_by(estimate_id=uuid.UUID(estimate_id)).first()
        )
        assert victim is not None
        item_id = str(victim.id)
        victim.source_bbox_json = None
        victim.confidence_status = None
        victim.confidence_score = None
        db.commit()

    boq = client.get(f"/api/estimates/{estimate_id}/boq").json()
    row = next(
        r for r in boq["routes"] + boq["materials"] if r["item_id"] == item_id
    )
    assert row["source"] is None
    # Tier falls back to the measurement row status instead of crashing.
    assert row["confidence_status"] == "MEASURED"
    assert row["confidence_score"] is None


# ---------------------------------------------------------------------------
# T3-review ruling: assumed-scale run — routes ASSUMED, components stay DERIVED
# ---------------------------------------------------------------------------
def test_assumed_scale_persists_response_tier(client, tmp_path, monkeypatch):
    build_plumbing_fire_fixture(str(tmp_path / "plumbing_fire_assumed.pdf"))

    import app.e2e.router as router_module

    real_resolve_scale = router_module.resolve_scale
    # Force the explicit assumed-scale stamp (spec v3 §7.4) for the run.
    monkeypatch.setattr(
        router_module, "resolve_scale", lambda spans: real_resolve_scale([])
    )

    response = _run_e2e(client, str(tmp_path / "plumbing_fire_assumed.pdf"))
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["scale"]["status"] == "assumed"
    assert body["boq_items"], "expected BOQ lines under assumed scale"

    # T3 carve-out: routes rest on scale-derived lengths → ASSUMED (0.3);
    # counted components are count × rule multiplier, scale-independent by
    # construction → stay DERIVED.
    response_routes = _route_lines(body)
    response_components = _component_lines(body)
    assert response_routes and response_components
    assert {ln["confidence_status"] for ln in response_routes} == {"ASSUMED"}
    assert {round(float(ln["confidence_score"]), 4) for ln in response_routes} == {
        0.3
    }
    assert {ln["confidence_status"] for ln in response_components} == {"DERIVED"}

    boq = client.get(f"/api/estimates/{body['estimate_id']}/boq").json()
    assert boq["scale"]["status"] == "assumed"
    assert boq["data_quality"]["scale_str"] == body["scale"]["value"]

    with OrmSession(get_engine()) as db:
        items = (
            db.query(BoqItem)
            .filter_by(estimate_id=uuid.UUID(body["estimate_id"]))
            .all()
        )
    assert items
    # Persisted tiers mirror the live response on both carve-out sides.
    assert all(item.confidence_status != "MEASURED" for item in items)
    assert {item.confidence_status for item in items} == {"ASSUMED", "DERIVED"}

    # Per-line parity per granularity: routes line-for-line (incl. quantity);
    # components per distinct material/tier/score (persistence aggregates
    # counted components per type, so quantities legitimately differ).
    assert sorted(map(_line_key, response_routes)) == sorted(
        map(_line_key, boq["routes"])
    )
    assert set(map(_tier_key, response_components)) == set(
        map(_tier_key, boq["materials"])
    )


# ---------------------------------------------------------------------------
# §7.12 source_quality: persisted estimate-level, served per payload row
# ---------------------------------------------------------------------------
class TestSourceQualityPersistence:
    def test_rows_carry_run_verdict(self, client, plumbing_run):
        """GET /boq rows carry the same source_quality the live run showed."""
        body = plumbing_run
        verdicts = {ln["source_quality"] for ln in body["boq_items"]}
        assert len(verdicts) == 1, "run verdict must be uniform across lines"

        boq = client.get(f"/api/estimates/{body['estimate_id']}/boq").json()
        rows = boq["routes"] + boq["materials"]
        assert rows
        assert {r["source_quality"] for r in rows} == verdicts

    def test_json_export_equals_boq_payload(self, client, plumbing_run):
        """The JSON export round-trips /boq byte-for-value — source_quality
        included on every row."""
        estimate_id = plumbing_run["estimate_id"]
        boq = client.get(f"/api/estimates/{estimate_id}/boq").json()
        rows = boq["routes"] + boq["materials"]
        assert rows, "parity against an empty BOQ would be vacuous"
        export = client.get(f"/api/exports/estimates/{estimate_id}/export?format=json")
        assert export.status_code == 200, export.text
        assert export.json() == boq

    def test_legacy_estimate_rows_read_column_default(self, client, plumbing_run):
        """A pre-feature Estimate row (inserted without source_quality) serves
        'layered_vector' from the migration's server default.

        BOQ items are COPIED onto the legacy estimate, never moved — this test
        must not mutate the module-scoped fixture state later tests read.
        """
        from sqlalchemy import insert

        with OrmSession(get_engine()) as db:
            original = db.get(Estimate, uuid.UUID(plumbing_run["estimate_id"]))
            items = db.query(BoqItem).filter_by(estimate_id=original.id).all()
            legacy = db.execute(
                insert(Estimate).values(
                    project_id=original.project_id,
                    total_material_cost=0.0,
                    total_labor_cost=0.0,
                    total_cost=0.0,
                )
            )
            legacy_id = legacy.inserted_primary_key[0]
            for item in items:
                db.add(
                    BoqItem(
                        measurement_id=item.measurement_id,
                        estimate_id=legacy_id,
                        quantity=item.quantity,
                        unit_cost=item.unit_cost,
                        total_cost=item.total_cost,
                        derivation_json=item.derivation_json,
                        size_source=item.size_source,
                        source_bbox_json=item.source_bbox_json,
                        confidence_status=item.confidence_status,
                        confidence_score=item.confidence_score,
                    )
                )
            db.commit()

        boq = client.get(f"/api/estimates/{str(legacy_id)}/boq").json()
        rows = boq["routes"] + boq["materials"]
        assert rows, "copied BOQ items must serve under the legacy estimate"
        assert {r["source_quality"] for r in rows} == {"layered_vector"}
