"""Persistence spine + replay proof tests (v3 conformance G1).

Covers plan Task 2 acceptance:
(a) round-trip persist -> GET /boq equals input quantities;
(b) second persist of the same sheet replaces rows (no duplicates);
(c) replay returns 200 with zero mismatches on a clean estimate;
(d) tampering with a stored formula derivation flips replay to 409;
(e) unpriced items keep their ``unpriced`` flag through the round trip.

The tests exercise the real dev database (sqlite aec.db) exactly as the
plan specifies: ``OrmSession(get_engine())`` for writes, TestClient against
the estimates router for reads. Idempotent replace semantics keep repeat
runs stable.
"""

import json

from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session as OrmSession

from app.db.session import get_engine
from app.e2e.extraction import SheetExtraction, RouteRow, LayerRow
from app.e2e.persistence import persist_extraction
from app.estimates.router import router as estimates_router


def _client():
    app = FastAPI()
    app.include_router(estimates_router)
    return TestClient(app)


def _extraction() -> SheetExtraction:
    return SheetExtraction(
        sheet_name="TEST-SHEET",
        page_number=1,
        scale="1:100",
        layers=[LayerRow("M-DUCT", "mechanical")],
        routes=[
            RouteRow(
                "duct",
                "M-DUCT",
                12.5,
                size_json={"width_mm": 600, "height_mm": 400, "source": "label", "ref": "600x400"},
            )
        ],
    )


def test_round_trip_and_replace():
    with OrmSession(get_engine()) as db:
        est1 = persist_extraction(db, None, _extraction())
        est2 = persist_extraction(db, None, _extraction())
        assert est1 != est2
    c = _client()
    body = c.get(f"/api/estimates/{est2}/boq").json()
    # One BOQ line per material of the single duct route: sheet metal
    # (formula), duct fitting (linear_per_m constant), hanger kit (gauge).
    assert len(body["routes"]) == 3
    assert body["routes"][0]["length_m"] == 12.5
    assert body["routes"][0]["size_json"]["source"] == "label"


def test_replay_ok_then_tamper_409():
    with OrmSession(get_engine()) as db:
        est = persist_extraction(db, None, _extraction())
    c = _client()
    r_ok = c.get(f"/api/estimates/{est}/replay")
    assert r_ok.status_code == 200, r_ok.text
    assert r_ok.json()["checked"] > 0
    assert r_ok.json()["mismatches"] == []
    # tamper: store an impossible formula result
    from app.db.models.estimate import BoqItem

    with OrmSession(get_engine()) as db:
        item = db.query(BoqItem).filter_by(estimate_id=est).first()
        d = json.loads(item.derivation_json or "{}")
        d["formula"], d["inputs"] = "1 + 1", {}
        item.derivation_json = json.dumps(d)
        db.commit()
    r = c.get(f"/api/estimates/{est}/replay")
    assert r.status_code == 409
    assert r.json()["mismatches"], "409 body must list offending boq_item ids"


def test_unpriced_items_keep_flag():
    """Unpriced gap survives the round trip — never silently $0 (trap §2)."""
    extraction = SheetExtraction(
        sheet_name="TEST-SHEET-UNPRICED",
        page_number=1,
        scale="1:100",
        layers=[LayerRow("CONDUIT", "electrical")],
        routes=[RouteRow("conduit", "CONDUIT", 10.0)],
    )
    from app.db.models.catalog import Material, Price

    saved: list[tuple] = []
    with OrmSession(get_engine()) as db:
        clamp = db.query(Material).filter_by(name="clamp").first()
        if clamp is not None:
            for p in list(clamp.prices):
                saved.append((p.material_id, float(p.unit_price), p.currency))
                db.delete(p)
            db.flush()
        est = persist_extraction(db, None, extraction)
        db.commit()
    try:
        c = _client()
        body = c.get(f"/api/estimates/{est}/boq").json()
        clamps = [ln for ln in body["routes"] if ln["material_name"] == "clamp"]
        assert clamps, "clamp line missing from persisted BOQ"
        for ln in clamps:
            assert ln["unpriced"] is True
            assert ln["unit_price"] is None or ln["unit_price"] == ln["unit_cost"]
    finally:
        with OrmSession(get_engine()) as db:
            for material_id, unit_price, currency in saved:
                exists = db.query(Price).filter_by(material_id=material_id).first()
                if exists is None:
                    db.add(Price(material_id=material_id, unit_price=unit_price, currency=currency))
            db.commit()


def test_replay_covers_legacy_linear_scaling():
    """Constant BOM lines scale by length and replay via linear_per_m."""
    extraction = SheetExtraction(
        sheet_name="TEST-SHEET-LINEAR",
        page_number=1,
        scale="1:100",
        layers=[LayerRow("CONDUIT", "electrical")],
        routes=[RouteRow("conduit", "CONDUIT", 8.0)],
    )
    with OrmSession(get_engine()) as db:
        est = persist_extraction(db, None, extraction)
    c = _client()
    r = c.get(f"/api/estimates/{est}/replay")
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["checked"] >= 3  # conduit_pipe, conduit_fitting, clamp
    assert body["mismatches"] == []
