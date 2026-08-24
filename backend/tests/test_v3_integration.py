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

from app.db.models.estimate import BoqItem, Estimate, Measurement
from app.db.models.extraction import Layer
from app.db.models.geometry import Component, Route
from app.db.models.project import Drawing, Project, Sheet
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

    def test_persisted_boq_matches_response_quantities(self, client, hvac_run):
        """Persisted BOQ must total the same as the response math (F1).

        The extraction persisted to the DB is built after the BOQ loop so
        cascade-resolved route sizes drive BOTH sides; a size divergence
        (e.g. YAML defaults substituted for label-resolved 600x400) breaks
        this per-material equality. Line granularity may legitimately differ
        (response = one line per counted instance; persistence = one
        Measurement per component type), so totals are compared, not multisets.
        """
        body = hvac_run

        def _totals(lines):
            totals: dict[str, float] = {}
            for line in lines:
                name = line["material_name"]
                totals[name] = totals.get(name, 0.0) + float(line["quantity"])
            return {name: round(value, 3) for name, value in totals.items()}

        response_totals = _totals(body["boq_items"])
        boq = client.get(f"/api/estimates/{body['estimate_id']}/boq").json()
        persisted_totals = _totals(boq["routes"] + boq["materials"])
        assert response_totals == persisted_totals

    def test_persisted_route_size_provenance_non_assumed(self, client, hvac_run):
        """Cascade-resolved sizes persist WITH provenance, not as nulls (F1).

        The HVAC fixture labels/schedules its runs, so persisted Route rows
        must carry non-null size_json and at least one must resolve above
        the ASSUMED tier (schedule or label source).
        """
        boq = client.get(f"/api/estimates/{hvac_run['estimate_id']}/boq").json()
        sized = [route for route in boq["routes"] if route.get("size_json")]
        assert sized, "no persisted route carries size_json provenance"
        sources = {route["size_json"].get("source") for route in sized}
        assert sources - {"assumed"}, (
            f"every persisted size fell back to ASSUMED: {sorted(sources)}"
        )


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


# ---------------------------------------------------------------------------
# Fix-wave F2: ASSUMED tier downgrade must reach persistence
# ---------------------------------------------------------------------------
def test_partial_dim_cascade_persists_assumed_tier(client, tmp_path, monkeypatch):
    """Width-only cascade hit ⇒ defaults fill the gap ⇒ ASSUMED everywhere.

    When resolve_route_size returns a partial dict (width_mm only), rule
    defaults supply the missing dimension inside apply_assembly. The row
    must carry ``source: assumed`` in the response math AND in the persisted
    Route.size_json / BoqItem.size_source — never a silently full-confidence
    provenance for a default-filled size.
    """
    import app.e2e.router as router_module

    pdf_path = str(tmp_path / "hvac_fixture.pdf")
    build_hvac_fixture(pdf_path)

    def _width_only(
        route,
        text_spans,
        scale,
        schedule_rows=None,
        default_size=None,
        fixture_unit_size=None,
    ):
        return {"width_mm": 600.0, "source": "label", "ref": "text_span:600x400"}

    monkeypatch.setattr(router_module, "resolve_route_size", _width_only)
    response = _run_e2e(client, pdf_path)
    assert response.status_code == 200, response.text
    body = response.json()
    sized_lines = [ln for ln in body["boq_items"] if ln.get("size_source")]
    assert sized_lines, "expected sized-route BOQ lines"
    assert all(ln["size_source"] == "assumed" for ln in sized_lines)

    boq = client.get(f"/api/estimates/{body['estimate_id']}/boq").json()
    sized_routes = [r for r in boq["routes"] if r.get("size_json")]
    assert sized_routes, "no persisted route carries size_json"
    for route in sized_routes:
        assert route["size_json"]["source"] == "assumed", route["size_json"]
        assert route["size_source"] == "assumed"

    with OrmSession(get_engine()) as db:
        items = (
            db.query(BoqItem)
            .join(Measurement, BoqItem.measurement_id == Measurement.id)
            .join(Route, Measurement.route_id == Route.id)
            .filter(Route.sheet.has(name="hvac_fixture"))
            .all()
        )
    assert items, "no persisted route-derived BoqItems found"
    assert all(item.size_source == "assumed" for item in items)


# ---------------------------------------------------------------------------
# Fix-wave F6: unsized-route apply_assembly fails closed (no 500)
# ---------------------------------------------------------------------------
def _build_conduit_fixture(path: str) -> None:
    """Layer-rich mini sheet: one segmented conduit run + sheet furniture."""
    doc = pymupdf.open()
    page = doc.new_page(width=1191, height=842)
    ocg_conduit = doc.add_ocg("CONDUIT", on=True)

    shape = page.new_shape()
    p0, p1 = (200.0, 400.0), (600.0, 400.0)
    length = p1[0] - p0[0]
    n = max(2, int(length / 4.0) + 1)
    pts = [(p0[0] + (p1[0] - p0[0]) * i / n, p0[1]) for i in range(n + 1)]
    for a, b in zip(pts, pts[1:]):
        shape.draw_line(a, b)
        shape.finish(color=(0, 0, 1), width=1, oc=ocg_conduit)
    # Unlayered sheet furniture keeps the quality gate happy.
    shape.draw_rect(pymupdf.Rect(20, 20, 1171, 822))
    shape.finish(color=(0.5, 0.5, 0.5), width=0.75)
    shape.draw_line((35, 750), (1156, 750))
    shape.finish(color=(0.5, 0.5, 0.5), width=0.75)
    shape.commit()

    page.insert_text((100, 100), "SCALE 1:100", fontsize=8)
    doc.save(path)
    doc.close()


def test_unsized_route_rule_failure_drops_route_not_request(client, tmp_path, monkeypatch):
    """A raising rule on the legacy path ⇒ route dropped, response still 200.

    Mirrors persistence's fail-closed FormulaValidationError handling: one
    broken assembly rule must degrade that route only — never turn the
    whole /api/e2e/run into a 500.
    """
    import app.e2e.router as router_module
    from app.assembly.formulas import FormulaValidationError

    pdf_path = str(tmp_path / "conduit_fixture.pdf")
    _build_conduit_fixture(pdf_path)

    real_apply_assembly = router_module.apply_assembly

    def _raising_for_unsized(component_type, variables=None, rule_name=""):
        if variables is None and component_type in {"conduit", "cable_tray"}:
            raise FormulaValidationError(
                "missing variable 'length_m'", component_type
            )
        return real_apply_assembly(component_type, variables=variables, rule_name=rule_name)

    monkeypatch.setattr(router_module, "apply_assembly", _raising_for_unsized)

    with open(pdf_path, "rb") as f:
        response = client.post(
            "/api/e2e/run",
            files={"file": ("conduit_fixture.pdf", f, "application/pdf")},
        )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["status"] == "ok"
    assert body["routes_measured"] >= 1, "conduit run must be measured before the drop"
    names = {ln["material_name"] for ln in body["boq_items"]}
    assert not names & {"conduit_pipe", "conduit_fitting", "clamp"}, (
        f"failed route leaked BOQ lines: {sorted(names)}"
    )


# ---------------------------------------------------------------------------
# F2: the UNMAPPED never-priced guard must not depend on rule absence
# ---------------------------------------------------------------------------
# ---------------------------------------------------------------------------
# Fix-wave L1: persistence must mirror the router's STRICT name skip
# ---------------------------------------------------------------------------
def test_persist_component_strict_name_skip(monkeypatch):
    """Rule whose ``name`` differs from the assembly_type ⇒ no rows at all.

    The response pipeline skips components when load_assembly_rule returns
    None or the loaded rule's declared name does not match the resolved
    type (never apply an unrelated rule). _persist_component_boq must
    enforce exactly the same gate so persisted BOQ never diverges from the
    response math.
    """
    import app.e2e.persistence as persistence_module

    monkeypatch.setattr(
        persistence_module,
        "load_assembly_rule",
        lambda name: {"name": f"unrelated_{name}", "bom": {}, "waste_factor": 0.0},
    )

    def _forbidden_apply(name, variables=None, rule_name=""):
        raise AssertionError(
            "apply_assembly must never run for a name-mismatched component"
        )

    monkeypatch.setattr(persistence_module, "apply_assembly", _forbidden_apply)

    with OrmSession(get_engine()) as db:
        project = db.query(Project).filter_by(name="Default Project").first()
        if project is None:
            project = Project(name="Default Project")
            db.add(project)
            db.flush()
        drawing = Drawing(discipline=None)
        project.drawings.append(drawing)
        db.flush()
        sheet = Sheet(drawing_id=drawing.id, name="strict-skip-sheet")
        db.add(sheet)
        db.flush()
        component = Component(
            sheet_id=sheet.id,
            component_type="mystery_symbol",
            source_layer="X-SYM",
            x=1.0,
            y=2.0,
        )
        db.add(component)
        estimate = Estimate(project_id=project.id)
        db.add(estimate)
        db.flush()

        measurements_before = db.query(Measurement).count()
        boq_before = db.query(BoqItem).count()
        persistence_module._persist_component_boq(
            db,
            estimate,
            component,
            count=5,
            confidence_status="MEASURED",
            source_quality="layered_vector",
            rule_version="v3c-1",
        )
        assert db.query(Measurement).count() == measurements_before
        assert db.query(BoqItem).count() == boq_before
        db.rollback()  # keep the shared dev DB clean


def test_unmapped_pricing_guard_holds_even_with_rule(monkeypatch):
    """_persist_component_boq must hard-refuse UNMAPPED rows (F2).

    Rows arrive with component_type coerced to the string "UNMAPPED", so a
    truthiness guard never fires. Even if an ``UNMAPPED`` assembly rule
    existed (or a rule lookup/apply misbehaves), no Measurement or BoqItem
    may be created for an UNMAPPED component.
    """
    import app.e2e.persistence as persistence_module

    monkeypatch.setattr(
        persistence_module,
        "load_assembly_rule",
        lambda name: {
            "name": name,
            "bom": {"ghost_material": 1.0},
            "waste_factor": 0.0,
        },
    )
    monkeypatch.setattr(
        persistence_module,
        "apply_assembly",
        lambda name, variables=None, rule_name="": {
            "materials": [{"material_name": "ghost_material", "quantity": 2.0}]
        },
    )

    with OrmSession(get_engine()) as db:
        project = db.query(Project).filter_by(name="Default Project").first()
        if project is None:
            project = Project(name="Default Project")
            db.add(project)
            db.flush()
        drawing = Drawing(discipline=None)
        project.drawings.append(drawing)
        db.flush()
        sheet = Sheet(drawing_id=drawing.id, name="unmapped-guard-sheet")
        db.add(sheet)
        db.flush()
        component = Component(
            sheet_id=sheet.id,
            component_type="UNMAPPED",
            source_layer="X-UNKNOWN-SYM",
            x=1.0,
            y=2.0,
            confidence_status="UNMAPPED",
        )
        db.add(component)
        estimate = Estimate(project_id=project.id)
        db.add(estimate)
        db.flush()

        measurements_before = db.query(Measurement).count()
        boq_before = db.query(BoqItem).count()
        persistence_module._persist_component_boq(
            db,
            estimate,
            component,
            count=3,
            confidence_status="UNMAPPED",
            source_quality="layered_vector",
            rule_version="v3c-1",
        )
        assert db.query(Measurement).count() == measurements_before
        assert db.query(BoqItem).count() == boq_before
        db.rollback()  # keep the shared dev DB clean
