"""Legend/title-block gating guardrails + MMC access-control regression.

Bug being locked down (2026-08-25 owner report): on
MMC-JVC-CD-ELEC-3902_AC-WIRE (Access Control System - Basement 2), the BOQ
carried ``lighting_unit`` x26 / ``lampholder`` x26 although the sheet's legend
declares only access-control symbols.

Root causes established by evidence:
1. The legend table's own symbol cells sit on OCG layer ``E-lt-fix-nm-clg``
   INSIDE the title-block band (y >= ~926 pt); that layer exact-maps to
   ``lighting_outlet`` in data/layer_mapping.yaml, so global layer-name
   classification priced 26 legend glyph clusters as plan instances.
2. The identical 26/26 counts are NOT double detection —
   data/assemblies/lighting_outlet.yaml fans one counted instance out into
   sibling BOM lines ``lighting_unit: 1.0`` + ``lampholder: 1.0`` (kit
   semantics, same as access_control_door). Kill the phantom instances and
   both rows vanish.
3. Title block says SCALE 1/100 as two separate rotated spans ('SCALE' +
   '1/100', ~26 pt apart); resolve_scale only matched inline patterns, so it
   fell back to assumed 1:100.

Fix contract tested here:
- Component clusters whose centroid falls inside a detected title-block /
  annotation band are FLAGGED (surfaced in the response, persisted as
  REVIEW, never priced) — never silently dropped, never miscounted.
- When a readable legend block EXISTS, symbol types it does not declare are
  flagged as not_in_legend (fail-open to region-only gating when no legend
  text is extractable).
- Paired scale labels: a bare SCALE anchor span + nearby ratio token
  (colon OR slash form) resolves as detected.
"""

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.e2e.extraction import ComponentRow, LayerRow, SheetExtraction, ScheduleBlockRow

SAMPLE = (
    Path(__file__).resolve().parents[2]
    / "data"
    / "samples"
    / "MMC-JVC-CD-ELEC-3902_AC-WIRE-Model.pdf"
)


# ---------------------------------------------------------------------------
# Unit: rules-declared legend keywords (YAML-driven, never hardcoded)
# ---------------------------------------------------------------------------


def test_all_legend_keywords_loaded_from_yaml():
    from app.assembly.rules import all_legend_keywords

    index = all_legend_keywords()
    ac = [kw.upper() for kw in index.get("access_control_door", [])]
    lo = [kw.upper() for kw in index.get("lighting_outlet", [])]
    assert any("CARD READER" in kw for kw in ac), index
    assert any("MAGNETIC LOCK" in kw for kw in ac), index
    assert any("LIGHT" in kw for kw in lo), index


# ---------------------------------------------------------------------------
# Unit: title-block region detection
# ---------------------------------------------------------------------------


def _tb_span(text, x0, y0, x1, y1):
    return {"text": text, "x0": float(x0), "y0": float(y0), "x1": float(x1), "y1": float(y1)}


def test_region_requires_multiple_keyword_anchors():
    from app.parsing.gating import detect_title_block_regions

    assert detect_title_block_regions([_tb_span("SCALE", 50, 1100, 60, 1120)]) == []
    two = [
        _tb_span("DRAWER", 20, 920, 40, 950),
        _tb_span("SHEET NO", 45, 920, 60, 950),
    ]
    assert detect_title_block_regions(two) == []


def test_region_covers_keyword_envelope_with_margin():
    from app.parsing.gating import detect_title_block_regions

    spans = [
        _tb_span("DRAWER", 29, 928, 35, 950),
        _tb_span("SHEET NO", 50, 928, 56, 954),
        _tb_span("SCALE", 50, 1114, 56, 1131),
        _tb_span("OWNER:", 813, 1148, 819, 1173),
        # decoy plan text that must not create a region by itself
        _tb_span("FIRE EXIT", 450, 357, 455, 360),
    ]
    regions = detect_title_block_regions(spans)
    assert len(regions) == 1
    r = regions[0]
    # envelope + margin swallows the whole annotation band
    assert r["x0"] <= 29 and r["y0"] <= 928
    assert r["x1"] >= 819 and r["y1"] >= 1173


def test_real_mmc_title_block_band_detected_and_scoped():
    from app.ingestion.vector import parse_pdf
    from app.parsing.gating import _point_in_region, detect_title_block_regions

    parsed = parse_pdf(str(SAMPLE))
    spans = [
        {
            "text": s.get("text", ""),
            "x0": float(s["bbox"][0]),
            "y0": float(s["bbox"][1]),
            "x1": float(s["bbox"][2]),
            "y1": float(s["bbox"][3]),
        }
        for s in parsed["raw_text_spans"]
    ]
    regions = detect_title_block_regions(spans)
    assert regions, "MMC title block keywords must yield an annotation region"
    # Legend-cell cluster centroid (inside the band) vs a true plan device.
    assert any(_point_in_region(600.0, 1000.0, r) for r in regions)
    assert not any(_point_in_region(353.5, 316.1, r) for r in regions)


# ---------------------------------------------------------------------------
# Unit: component gating
# ---------------------------------------------------------------------------


def _comp(assembly, x, y):
    return {
        "assembly_type": assembly,
        "count": 1,
        "layer": "L",
        "x": x,
        "y": y,
        "source_path_ids": [f"p-{assembly}-{x}"],
        "confidence_status": "MEASURED",
        "confidence_score": 1.0,
        "bbox": [x - 5, y - 5, x + 5, y + 5],
        "page": 0,
    }


def test_gate_flags_title_block_instances_only():
    from app.parsing.gating import gate_components

    region = [{"x0": 500.0, "y0": 900.0, "x1": 700.0, "y1": 1200.0}]
    comps = [_comp("lighting_outlet", 600.0, 1000.0), _comp("access_control_door", 353.5, 316.1)]
    priced, flagged = gate_components(comps, region, None)
    assert [c["assembly_type"] for c in priced] == ["access_control_door"]
    assert len(flagged) == 1
    assert flagged[0]["assembly_type"] == "lighting_outlet"
    assert flagged[0]["gate_reason"] == "title_block_region"
    assert flagged[0]["source_path_ids"], "flagged symbols stay traceable"


def test_gate_flags_types_absent_from_readable_legend():
    from app.parsing.gating import gate_components, legend_allowed_assemblies

    blocks = [
        ScheduleBlockRow(
            block_type="legend",
            page_region={"x0": 500, "y0": 900, "x1": 800, "y1": 1200},
            entries=[{"cells": ["ACCESS CONTROL CARD READER"]}, {"cells": ["MAGNETIC LOCK"]}],
        )
    ]
    allowed = legend_allowed_assemblies(blocks)
    assert allowed is not None and "access_control_door" in allowed

    comps = [_comp("access_control_door", 353.5, 316.1), _comp("lighting_outlet", 200.0, 400.0)]
    priced, flagged = gate_components(comps, [], allowed)
    assert [c["assembly_type"] for c in priced] == ["access_control_door"]
    assert flagged[0]["gate_reason"] == "not_in_legend"


def test_no_legend_blocks_fails_open_to_region_only_gating():
    from app.parsing.gating import gate_components, legend_allowed_assemblies

    assert legend_allowed_assemblies([]) is None
    comps = [_comp("lighting_outlet", 200.0, 400.0)]
    priced, flagged = gate_components(comps, [], None)
    assert priced == comps and flagged == []


def test_schedule_blocks_are_not_legends_for_gating():
    from app.parsing.gating import legend_allowed_assemblies

    blocks = [
        ScheduleBlockRow(
            block_type="attribute_schedule",
            page_region={"x0": 0, "y0": 0, "x1": 10, "y1": 10},
            entries=[{"cells": ["DUCT SIZE", "THICK"]}],
        )
    ]
    assert legend_allowed_assemblies(blocks) is None


# ---------------------------------------------------------------------------
# Regression: full pipeline on the real MMC access-control sheet
# ---------------------------------------------------------------------------


@pytest.fixture()
def mmc_body(tmp_path, monkeypatch):
    from sqlalchemy import create_engine

    from app.db.base import Base
    from app.main import app

    db_path = tmp_path / "test_gating_api.db"
    engine = create_engine(f"sqlite:///{db_path}")
    Base.metadata.create_all(engine)
    engine.dispose()
    monkeypatch.setattr(
        "app.e2e.router.get_engine",
        lambda: create_engine(f"sqlite:///{db_path}"),
    )
    with open(SAMPLE, "rb") as fh:
        resp = TestClient(app).post(
            "/api/e2e/run",
            files={"file": ("sample.pdf", fh, "application/pdf")},
        )
    assert resp.status_code == 200, resp.text
    return resp.json()


def test_mmc_boq_contains_no_lighting_items(mmc_body):
    materials = {item["material_name"] for item in mmc_body["boq_items"]}
    assert "lighting_unit" not in materials
    assert "lampholder" not in materials
    assert all(item["assembly_type"] != "lighting_outlet" for item in mmc_body["boq_items"])


def test_mmc_phantom_symbols_flagged_not_silently_dropped(mmc_body):
    flagged = {(f["assembly_type"], f["reason"]): f["count"] for f in mmc_body["flagged_symbols"]}
    assert flagged[("lighting_outlet", "title_block_region")] == 26
    dq = mmc_body["data_quality"]
    assert dq["title_block_excluded"] == 26
    assert dq["legend_gate_excluded"] == 0


def test_mmc_real_access_control_scope_still_counted(mmc_body):
    types = {item["assembly_type"] for item in mmc_body["boq_items"]}
    assert "access_control_door" in types
    assert "cable_tray" in types
    assert "storm_downpipe" in types


def test_mmc_scale_now_detected_from_paired_title_block_spans(mmc_body):
    assert mmc_body["scale"] == {"value": "1:100", "status": "detected"}


# ---------------------------------------------------------------------------
# Persistence parity: REVIEW rows persist but are never priced
# ---------------------------------------------------------------------------


def test_review_rows_persist_but_never_price():
    """Replay parity: the response excludes gated components, so persistence
    must price only non-REVIEW counts — a REVIEW sibling of the same type
    must not inflate the priced multiplier."""
    from sqlalchemy.orm import Session as OrmSession

    from app.db.models.estimate import BoqItem
    from app.db.session import get_engine
    from app.e2e.persistence import persist_extraction
    import json as _json

    extraction = SheetExtraction(
        sheet_name="GATING-PARITY-SHEET",
        page_number=1,
        scale="1:100",
        scale_status="detected",
        scale_str="1:100",
        layers=[LayerRow("E-lt-fix-nm-clg", "electrical")],
        components=[
            ComponentRow(
                component_type="lighting_outlet",
                layer_ocg="E-lt-fix-nm-clg",
                x=353.5,
                y=316.1,
                confidence_status="MEASURED",
            ),
            ComponentRow(
                component_type="lighting_outlet",
                layer_ocg="E-lt-fix-nm-clg",
                x=600.0,
                y=1000.0,
                confidence_status="REVIEW",
            ),
        ],
    )
    with OrmSession(get_engine()) as db:
        est = persist_extraction(db, None, extraction)

    with OrmSession(get_engine()) as db:
        rows = db.query(BoqItem).filter_by(estimate_id=est).all()
    by_material = {}
    for row in rows:
        mat = (_json.loads(row.derivation_json or "{}") or {}).get("material_name")
        by_material[mat] = by_material.get(mat, 0.0) + float(row.quantity)
    # count == 1 (MEASURED only); the REVIEW sibling must not double it
    assert by_material.get("lighting_unit") == pytest.approx(1.0)
    assert by_material.get("lampholder") == pytest.approx(1.0)
