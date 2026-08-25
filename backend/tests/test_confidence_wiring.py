"""Live confidence-tier wiring (spec v3 §7.12).

BOQ lines are never MEASURED: every line is DERIVED by default and downgraded
to ASSUMED when the size cascade assumed it or the sheet scale was assumed.
Row/measurement-level statuses stay untouched.
"""

import math

from sqlalchemy import create_engine
from sqlalchemy.orm import Session as OrmSession

from app.db.base import Base
from app.e2e.router import _boq_line


def _session() -> OrmSession:
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    return OrmSession(engine)


def _line(db: OrmSession, **kw):
    base = dict(
        assembly_type="duct_round",
        material_name="sheet_metal_m2",
        quantity=1.0,
        measurement_status="MEASURED",
        source_path_ids=["p1"],
    )
    base.update(kw)
    return _boq_line(**base, db=db)


def test_boq_lines_default_derived():
    with _session() as db:
        line = _line(db)
    assert line["confidence_status"] == "DERIVED"
    assert line["confidence_score"] == 0.8


def test_size_assumed_downgrades_to_assumed():
    with _session() as db:
        line = _line(db, size_source="assumed")
    assert line["confidence_status"] == "ASSUMED"
    assert line["confidence_score"] == 0.3


def test_scale_assumed_downgrades_to_assumed():
    with _session() as db:
        line = _line(db, scale_assumed=True)
    assert line["confidence_status"] == "ASSUMED"


def test_degraded_multiplier_composes_with_derived():
    with _session() as db:
        line = _line(db, source_quality="degraded_vector")
    assert line["confidence_status"] == "DERIVED"
    assert math.isclose(line["confidence_score"], round(0.8 * 0.8, 4))
