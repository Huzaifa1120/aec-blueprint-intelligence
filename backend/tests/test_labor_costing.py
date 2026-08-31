"""Task 12: labor costing via the unpriced-flag pattern (spec v3 §7.14).

Layers under test:

- ``compute_labor_cost`` rate resolution: catalog LaborRate(category, latest)
  > YAML ``hourly_rate`` > unpriced — Decimal rounding identical to the pure
  ``labor_cost`` function; a drifted deployment without the ``labor_rates``
  table degrades honestly to YAML/unpriced instead of 500-ing;
- ``data/assemblies/access_control_door.yaml`` gains ``hourly_rate`` +
  ``category`` so every shipped rule bills labor through one pattern;
- the e2e pipeline emits ONE ``labor:<category>`` BOQ line per applied
  rule-with-labor — same tier treatment as sibling lines, response and
  persisted quantities in parity, ``rate_source`` stamped in the derivation
  payload (replay treats it as unchecked-honest);
- estimate totals reconcile: grand == Σ priced material + Σ priced labor;
  an unpriced labor line is flagged and contributes to neither total.
"""

from __future__ import annotations

import json
from datetime import date

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session as OrmSession
from sqlalchemy.pool import StaticPool

from app.catalog.prices import compute_labor_cost, ingest_labor_rate
from app.db.base import Base
from app.db.models.estimate import BoqItem
from app.db.session import get_engine


@pytest.fixture(autouse=True)
def _clear_labor_rate_cache():
    """Clear the module-level _labor_rate_cache before every test."""
    from app.catalog.prices import invalidate_price_cache
    invalidate_price_cache()
    yield
    invalidate_price_cache()


# ---------------------------------------------------------------------------
# Unit fixtures: in-memory catalog DB
# ---------------------------------------------------------------------------
@pytest.fixture()
def catalog_session():
    from app.catalog.prices import invalidate_price_cache
    invalidate_price_cache()
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    with OrmSession(engine) as session:
        yield session


class TestComputeLaborCostResolution:
    def test_catalog_rate_wins_over_yaml(self, catalog_session):
        ingest_labor_rate(
            catalog_session,
            name="Elec 2026",
            productivity_rate=1.0,
            hourly_rate=52.0,
            category="electrical",
            effective_from=date(2026, 1, 1),
        )
        result = compute_labor_cost(catalog_session, "electrical", 2.5, 45.0)
        assert result == {
            "unit_rate": 52.0,
            "total_cost": 130.0,
            "unpriced": False,
            "rate_source": "catalog",
        }

    def test_latest_effective_from_wins_within_category(self, catalog_session):
        ingest_labor_rate(
            catalog_session,
            name="Elec old",
            productivity_rate=1.0,
            hourly_rate=40.0,
            category="electrical",
            effective_from=date(2025, 1, 1),
        )
        ingest_labor_rate(
            catalog_session,
            name="Elec new",
            productivity_rate=1.0,
            hourly_rate=55.0,
            category="electrical",
            effective_from=date(2026, 6, 1),
        )
        result = compute_labor_cost(catalog_session, "electrical", 2.0, 45.0)
        assert result["unit_rate"] == 55.0
        assert result["total_cost"] == 110.0
        assert result["rate_source"] == "catalog"

    def test_yaml_fallback_when_catalog_has_no_category(self, catalog_session):
        ingest_labor_rate(
            catalog_session,
            name="Plumbing only",
            productivity_rate=1.0,
            hourly_rate=38.0,
            category="plumbing",
        )
        result = compute_labor_cost(catalog_session, "electrical", 2.5, 45.0)
        assert result == {
            "unit_rate": 45.0,
            "total_cost": 112.5,
            "unpriced": False,
            "rate_source": "yaml",
        }

    def test_unpriced_when_no_rate_anywhere(self, catalog_session):
        result = compute_labor_cost(catalog_session, "electrical", 2.5, None)
        assert result == {
            "unit_rate": None,
            "total_cost": 0.0,
            "unpriced": True,
            "rate_source": None,
        }

    def test_rounding_matches_pure_labor_cost(self, catalog_session):
        from app.catalog.prices import labor_cost

        result = compute_labor_cost(catalog_session, None, 0.35, 45.55)
        assert result["total_cost"] == labor_cost(0.35, 45.55)

    def test_missing_labor_rates_table_degrades_to_yaml(self, tmp_path):
        """Known model/DB drift (labor_rates deliberately unmigrated): the
        live pipeline must degrade to YAML resolution, never 500."""
        engine = create_engine(
            f"sqlite:///{tmp_path / 'drifted.db'}",
            connect_args={"check_same_thread": False},
        )
        Base.metadata.create_all(engine)
        with engine.begin() as conn:
            conn.execute(text("DROP TABLE labor_rates"))
        with OrmSession(engine) as session:
            result = compute_labor_cost(session, "electrical", 2.5, 45.0)
        assert result["rate_source"] == "yaml"
        assert result["total_cost"] == 112.5
        assert result["unpriced"] is False

    def test_non_table_operational_error_propagates(self):
        """Only 'no such table' degrades to YAML; other DB faults raise."""
        from sqlalchemy.exc import OperationalError

        class _LockedSession:
            def query(self, *args, **kwargs):
                raise OperationalError(
                    "SELECT", {}, Exception("database is locked")
                )

        with pytest.raises(OperationalError):
            compute_labor_cost(_LockedSession(), "electrical", 2.5, 45.0)


def test_access_control_door_labor_block():
    """The last rule without rate/category joins the labor-costing contract."""
    from app.assembly.rules import load_assembly_rule

    labor = (load_assembly_rule("access_control_door") or {}).get("labor") or {}
    assert labor.get("installation_hours") == 2.5
    assert labor.get("hourly_rate") == 45.00
    assert labor.get("category") == "electrical"


# ---------------------------------------------------------------------------
# Integration: full app run over the synthetic HVAC fixture
# ---------------------------------------------------------------------------
@pytest.fixture(scope="module")
def client():
    from app.main import app

    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture(scope="module")
def hvac_run(client, tmp_path_factory):
    """Distinct sheet name so this module never collides with other suites."""
    from tests.fixtures.make_hvac_fixture import build_hvac_fixture

    pdf_dir = tmp_path_factory.mktemp("labor_costing")
    pdf_path = str(pdf_dir / "labor_costing_hvac.pdf")
    build_hvac_fixture(pdf_path)
    with open(pdf_path, "rb") as f:
        response = client.post(
            "/api/e2e/run",
            files={"file": ("labor_costing_hvac.pdf", f, "application/pdf")},
            params={"persist": True},
        )
    assert response.status_code == 200, response.text
    return response.json()


def _labor_lines(lines):
    return [ln for ln in lines if str(ln["material_name"]).startswith("labor:")]


class TestE2eLaborLines:
    def test_labor_lines_emitted_with_stamped_provenance(self, hvac_run):
        labor = _labor_lines(hvac_run["boq_items"])
        assert labor, "expected at least one labor BOQ line"
        for ln in labor:
            assert ln["unit"] == "hour"
            assert ln["quantity"] > 0
            derivation = ln["derivation"]
            assert derivation["rule_name"]
            assert derivation["rule_version"]
            # rate_source stamped: catalog when seeded, yaml fallback here.
            assert derivation["labor"]["rate_source"] in {"catalog", "yaml"}
        # Every rule on this fixture carries a YAML hourly_rate, so nothing
        # may surface unpriced through the fallback chain.
        assert all(not ln["unpriced"] for ln in labor)
        assert {ln["assembly_type"] for ln in labor} <= {
            "duct_rectangular",
            "duct_round",
            "pipe_insulated",
            "hvac_equipment",
        }

    def test_response_and_persisted_labor_quantities_match(self, client, hvac_run):
        def _hours_by_name(lines):
            totals: dict[str, float] = {}
            for ln in _labor_lines(lines):
                name = ln["material_name"]
                totals[name] = totals.get(name, 0.0) + float(ln["quantity"])
            return {name: round(value, 3) for name, value in totals.items()}

        boq = client.get(f"/api/estimates/{hvac_run['estimate_id']}/boq").json()
        assert _hours_by_name(hvac_run["boq_items"]) == _hours_by_name(
            boq["routes"] + boq["materials"]
        )

    def test_estimate_totals_reconcile(self, client, hvac_run):
        boq = client.get(f"/api/estimates/{hvac_run['estimate_id']}/boq").json()
        rows = boq["routes"] + boq["materials"]
        priced_labor = round(
            sum(
                float(r["total_cost"] or 0.0)
                for r in rows
                if str(r["material_name"]).startswith("labor:") and not r["unpriced"]
            ),
            2,
        )
        material = round(
            sum(
                float(r["total_cost"] or 0.0)
                for r in rows
                if not str(r["material_name"]).startswith("labor:")
            ),
            2,
        )
        totals = boq["totals"]
        assert totals["labor"] == pytest.approx(priced_labor, abs=0.01)
        assert totals["materials"] == pytest.approx(material, abs=0.01)
        assert totals["grand"] == pytest.approx(totals["materials"] + totals["labor"], abs=0.01)
        assert totals["labor"] > 0  # fixture rules are YAML-priced

    def test_replay_treats_labor_as_unchecked_honest(self, client, hvac_run):
        r = client.get(f"/api/estimates/{hvac_run['estimate_id']}/replay")
        assert r.status_code == 200, r.text
        payload = r.json()
        assert payload["checked"] > 0
        assert payload["mismatches"] == []


# ---------------------------------------------------------------------------
# Persistence unit level: flagged-and-excluded vs priced-and-counted
# ---------------------------------------------------------------------------
def _seed_component_estimate(db: OrmSession, sheet_name: str):
    from app.db.models.estimate import Estimate
    from app.db.models.geometry import Component
    from app.db.models.project import Drawing, Project, Sheet

    project = db.query(Project).filter_by(name="Default Project").first()
    if project is None:
        project = Project(name="Default Project")
        db.add(project)
        db.flush()
    drawing = Drawing(discipline=None)
    project.drawings.append(drawing)
    db.flush()
    sheet = Sheet(drawing_id=drawing.id, name=sheet_name)
    db.add(sheet)
    db.flush()
    component = Component(
        sheet_id=sheet.id,
        component_type="mystery_sym",
        source_layer="X-SYM",
        x=1.0,
        y=2.0,
    )
    db.add(component)
    estimate = Estimate(project_id=project.id)
    db.add(estimate)
    db.flush()
    return component, estimate


@pytest.mark.parametrize(
    "labor_block,expect_priced",
    [
        ({"installation_hours": 2.0}, False),  # no rate anywhere → unpriced
        (
            {"installation_hours": 2.0, "hourly_rate": 40.0, "category": "plumbing"},
            True,
        ),
    ],
    ids=["unpriced", "yaml-priced"],
)
def test_unpriced_labor_row_flagged_and_excluded_from_totals(
    monkeypatch, labor_block, expect_priced
):
    import app.e2e.persistence as persistence_module

    monkeypatch.setattr(
        persistence_module,
        "load_assembly_rule",
        lambda name: {
            "name": name,
            "bom": {"ghost_material": 1.0},
            "waste_factor": 0.0,
            "labor": labor_block,
        },
    )
    monkeypatch.setattr(
        persistence_module,
        "apply_assembly",
        lambda name, variables=None, rule_name="": {
            "materials": [{"material_name": "ghost_material", "quantity": 2.0}],
            "labor_hours": float(labor_block["installation_hours"]),
            "rule_version": "t12",
        },
    )

    with OrmSession(get_engine()) as db:
        component, estimate = _seed_component_estimate(db, "labor-totals-sheet")
        persistence_module._persist_component_boq(
            db,
            estimate,
            component,
            count=2,
            confidence_status="MEASURED",
            source_quality="layered_vector",
            rule_version="t12",
        )
        persistence_module._set_estimate_totals(db, estimate)

        items = db.query(BoqItem).filter(BoqItem.estimate_id == estimate.id).all()
        labor_rows = [item for item in items if "labor" in json.loads(item.derivation_json)]
        assert len(labor_rows) == 1
        row = labor_rows[0]
        derivation = json.loads(row.derivation_json)
        assert row.quantity == pytest.approx(4.0)  # 2.0 h × count 2
        assert derivation["material_name"] == (
            f"labor:{labor_block.get('category') or 'mystery_sym'}"
        )
        assert derivation["unit"] == "hour"
        assert derivation["rule_name"] == "mystery_sym"
        assert derivation["labor"]["category"] == labor_block.get("category")

        if expect_priced:
            assert derivation["labor"]["rate_source"] == "yaml"
            assert "unpriced" not in derivation
            assert row.total_cost == pytest.approx(160.0)  # 4 h × 40
            assert estimate.total_labor_cost == pytest.approx(160.0)
        else:
            assert derivation["labor"]["rate_source"] is None
            assert derivation["unpriced"] is True
            assert row.total_cost == 0.0
            # Flagged, never silently folded into either total.
            assert estimate.total_labor_cost == 0.0
        assert estimate.total_cost == pytest.approx(
            estimate.total_material_cost + estimate.total_labor_cost
        )
        db.rollback()  # keep the shared dev DB clean
