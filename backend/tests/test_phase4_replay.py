"""Replay parity for fixture_units-sourced routes (fail-closed coherence).

Phase 4 Global Constraint refinement 2: replay verifies derivation
coherence for FU-sized routes — gauge(fu_total) == diameter_mm, the ref
breakdown sums to fu_total, and breakdown values match the rule YAML —
rather than geometric recomputation (route polylines are not persisted).
A tampered ``fu_total`` can never replay clean (409), mirroring the
derivation F2 rule.
"""

import json
import uuid

from sqlalchemy.orm import Session as OrmSession

from app.db.models.estimate import BoqItem, Measurement
from app.db.models.geometry import Route
from app.db.session import get_engine
from tests.test_phase4_regression import _run, client  # reuse upload helper
from tests.test_phase4_fixture_pdf import PDF, _ensure_fixture


def _persisted_estimate_id() -> str:
    _ensure_fixture()
    payload = _run(PDF, persist=True)
    assert payload.get("estimate_id")
    return payload["estimate_id"]


def test_replay_green_on_clean_fixture_run():
    est_id = _persisted_estimate_id()
    resp = client.get(f"/api/estimates/{est_id}/replay")
    assert resp.status_code == 200, resp.text
    assert resp.json()["mismatches"] == []
    assert resp.json()["checked"] > 0


def test_tampered_fu_total_fails_closed():
    est_id = _persisted_estimate_id()
    # Flip fu_total on the estimate's water_supply route size_json directly
    # in the DB (app session factory, as tests/test_persistence_spine.py).
    with OrmSession(get_engine()) as db:
        row = (
            db.query(Route)
            .join(Measurement, Measurement.route_id == Route.id)
            .join(BoqItem, BoqItem.measurement_id == Measurement.id)
            .filter(
                BoqItem.estimate_id == uuid.UUID(est_id),
                Route.size_json.like("%fixture_units%"),
            )
            .first()
        )
        assert row is not None, "expected a fixture_units-sourced route"
        size = json.loads(row.size_json)
        assert size.get("source") == "fixture_units"
        size["fu_total"] = float(size["fu_total"]) + 1000.0  # pushes past top threshold
        row.size_json = json.dumps(size)
        db.commit()

    resp = client.get(f"/api/estimates/{est_id}/replay")
    assert resp.status_code == 409, resp.text
