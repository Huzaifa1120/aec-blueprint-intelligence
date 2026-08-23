"""Phase 3: real-sheet mechanical equipment proof on ABC-SC03-S101.pdf.

Counts below are PIPELINE-DERIVED ground truth (debug run 2026-08-23) —
they lock current pipeline behavior on a real client drawing so regressions
in clustering/layer-mapping surface immediately. They are NOT yet human-
verified against visible symbols; see PENDING HUMAN VERIFICATION markers.
Do not adjust them to make the test pass; adjust the pipeline instead.
"""

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.main import app

S101 = str(Path(__file__).resolve().parents[2] / "data" / "samples" / "ABC-SC03-S101.pdf")

# PENDING HUMAN VERIFICATION — counts are pipeline-derived (debug run
# 2026-08-23), manual visual check against the drawing owed before phase merge.
# Debug breakdown by source layer (count_components):
#   M-EQPT-NEW -> hvac_equipment: 1 unit
#   M-EQPT-FUTR -> hvac_equipment: 276 units
# N = 277 total equipment units. Rule multipliers per unit:
#   unit_connector x1.0, vibration_isolator x4.0.
# The M-EQPT-FUTR count (276) is unusually high for a generator/cooling-tower
# yard plan and is the primary item to eyeball during verification.
N_EQUIPMENT_UNITS = 277


@pytest.fixture(scope="module")
def client():
    return TestClient(app)


@pytest.mark.skipif(not Path(S101).exists(), reason="client fixture not present")
class TestS101Equipment:
    def test_equipment_counted_with_provenance(self, client, tmp_path, monkeypatch):
        """Real-sheet S101: hvac_equipment derived at pipeline-derived counts.

        Locks the direct-layer resolution M-EQPT-NEW/M-EQPT-FUTR -> hvac_equipment
        and the rule multipliers (unit_connector x1, vibration_isolator x4) against
        a real client PDF rather than only the synthetic Phase 3 fixture.

        Trap reference: AGENTS.md §2 — Geometry calculates, humans approve. These
        numbers trace to deterministic clustering + layer mapping only.
        """
        from sqlalchemy import create_engine

        from app.db.base import Base

        db_path = tmp_path / "s101_e2e.db"
        engine = create_engine(f"sqlite:///{db_path}")
        Base.metadata.create_all(engine)
        engine.dispose()
        monkeypatch.setattr(
            "app.e2e.router.get_engine",
            lambda: create_engine(f"sqlite:///{db_path}"),
        )

        with open(S101, "rb") as f:
            response = client.post(
                "/api/e2e/run",
                files={"file": ("S101.pdf", f, "application/pdf")},
            )
        assert response.status_code == 200, response.text
        body = response.json()
        assert body["status"] == "ok", f"Pipeline failed: {body}"

        equipment = [it for it in body["boq_items"] if it["assembly_type"] == "hvac_equipment"]
        assert equipment, "no hvac_equipment rows derived from S101"

        # PENDING HUMAN VERIFICATION — counts are pipeline-derived (debug run
        # 2026-08-23), manual visual check against the drawing owed before phase
        # merge. N=277 (M-EQPT-NEW: 1, M-EQPT-FUTR: 276); isolators x4/unit rule.
        by_material = {}
        for it in equipment:
            by_material.setdefault(it["material_name"], []).append(it)

        connectors = by_material.get("unit_connector", [])
        assert sum(it["quantity"] for it in connectors) == pytest.approx(N_EQUIPMENT_UNITS * 1.0)
        isolators = by_material.get("vibration_isolator", [])
        assert isolators, "no vibration_isolator rows derived from S101"
        assert sum(it["quantity"] for it in isolators) == pytest.approx(N_EQUIPMENT_UNITS * 4.0)

        # every equipment row carries source traceability
        assert all(it["source_path_ids"] for it in equipment)
