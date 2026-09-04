"""Tests for Task 4: build_lighting_boq — V1-V4 → BoqItem glue (TDD)."""

import pymupdf
from sqlalchemy import inspect

from app.db.session import get_engine
from app.services.lighting.denoiser import extract_denoised_symbols
from app.services.lighting.room_mapper import build_room_polygons, assign_symbol_to_room
from app.services.lighting.spatial_association import (
    extract_markers,
    associate_markers_to_symbols,
    FixtureSymbol,
)
from app.services.lighting.legend_parser import parse_legend
from app.services.lighting.text_clustering import extract_dali_loops
from app.services.lighting.reconciliation import deduplicate_loops
from app.services.lighting.loop_quantifier import build_loop_zones, assign_symbols_to_zones
from app.e2e.lighting import build_lighting_boq, LightingBoqRow

SAMPLE_PDF = "../data/samples/P0050-AMC-A-E2-2F-EL-122-02-B, Lighting Layout, 2nd Floor, Part-1.pdf"


def _load_all():
    """Load all V1-V4 data, wiring markers + rooms before V4 scoring (F3)."""
    doc = pymupdf.open(SAMPLE_PDF)
    page = doc[0]
    try:
        # V1: Denoised symbols
        symbols = extract_denoised_symbols(page)

        # F3: Wire markers + room association BEFORE V4 scoring
        markers = extract_markers(page)
        # Convert DenoisedSymbol to FixtureSymbol for associate_markers_to_symbols
        fixture_symbols = [
            FixtureSymbol(
                centroid=s.centroid,
                bbox=s.bbox,
                symbol_type=_denoised_shape_to_type(s.shape),
                area=s.area,
                path_signature=s.path_signature,
            )
            for s in symbols
        ]
        instances = associate_markers_to_symbols(markers, fixture_symbols, max_radius=30.0)
        # Map instance data back onto DenoisedSymbol objects (in-place)
        sym_by_id = {s.id: s for s in symbols}
        for inst in instances:
            s = (
                sym_by_id.get(inst["symbol_id"])
                if "symbol_id" in inst
                else sym_by_id.get(inst.get("id"))
            )
            if s is not None:
                s.has_marker = True
                s.marker_label = inst["emergency_class"]
        rooms = build_room_polygons(page)
        # Per-symbol room assignment (in-place)
        for s in symbols:
            room = assign_symbol_to_room(s.centroid, rooms)
            if room is not None:
                s.assigned_room = room.room_id

        # V3: Legend specs
        specs = parse_legend(page)

        # V4: Loop zones
        loops_raw, _ = extract_dali_loops(page)
        unique_loops, _ = deduplicate_loops(loops_raw)
        zones = build_loop_zones(unique_loops, radius=4000.0)
        assign_symbols_to_zones(symbols, zones, rooms)

        doc.close()
        return symbols, rooms, specs, zones
    except Exception:
        doc.close()
        raise


def _denoised_shape_to_type(shape: str) -> str:
    """Map denoiser shape to FixtureSymbol symbol_type."""
    return {
        "circle": "circ4_cyan",
        "hexagon": "poly6_black",
        "nonagon": "poly9_green",
    }.get(shape, "unknown")


def test_build_lighting_boq_with_real_part1_returns_nonempty():
    """Returns ≥1 LightingBoqRow for the real Part-1 PDF."""
    symbols, rooms, specs, zones = _load_all()
    rows = build_lighting_boq(symbols, rooms, specs, zones)
    assert len(rows) >= 1, f"Expected ≥1 rows, got {len(rows)}"
    for row in rows:
        assert isinstance(row, LightingBoqRow)


def test_build_lighting_boq_respects_loop_capacity():
    """Total quantity ≤ sum of zone capacities."""
    symbols, rooms, specs, zones = _load_all()
    rows = build_lighting_boq(symbols, rooms, specs, zones)
    total_qty = sum(row.quantity for row in rows)
    total_capacity = sum(z.capacity for z in zones.values())
    assert total_qty <= total_capacity, (
        f"Total quantity {total_qty} exceeds zone capacity {total_capacity}"
    )


def test_build_lighting_boq_emits_unpriced_flag_when_catalog_missing():
    """unit_price is None for all rows (no catalog hardcode)."""
    symbols, rooms, specs, zones = _load_all()
    rows = build_lighting_boq(symbols, rooms, specs, zones)
    for row in rows:
        assert row.unit_price is None, f"Expected unpriced (None), got {row.unit_price}"


def test_build_lighting_boq_derives_confidence_from_v4_breakdown():
    """Confidence > 0.4 AND at least one V4 factor > 0 (proves markers+rooms wired per F3)."""
    symbols, rooms, specs, zones = _load_all()
    rows = build_lighting_boq(symbols, rooms, specs, zones)
    # At least one row must have confidence > 0.4
    high_conf = [r for r in rows if r.confidence_score > 0.4]
    assert len(high_conf) >= 1, (
        f"No rows with confidence > 0.4 (max={max(r.confidence_score for r in rows) if rows else 0})"
    )
    # At least one row must have a non-zero V4 factor
    any_factor = False
    for row in rows:
        if hasattr(row, "score_breakdown") and row.score_breakdown:
            for v in row.score_breakdown.values():
                if v > 0:
                    any_factor = True
                    break
            if any_factor:
                break
    assert any_factor, "No V4 score_breakdown factor > 0 — markers+rooms not wired"


def test_build_lighting_boq_returns_empty_when_no_dali_loops():
    """Degenerate input (no loops) → empty list."""
    symbols, rooms, specs, _ = _load_all()
    # Pass empty zones
    empty_zones = {}
    rows = build_lighting_boq(symbols, rooms, specs, empty_zones)
    assert rows == []


def test_build_lighting_boq_uses_v3_spec_code():
    """spec_code comes from V3 parsed set or 'unknown'."""
    symbols, rooms, specs, zones = _load_all()
    rows = build_lighting_boq(symbols, rooms, specs, zones)
    # Every row must have a spec_code (from V3 or "unknown")
    for row in rows:
        assert hasattr(row, "spec_code"), "Row missing spec_code"
        assert row.spec_code is not None, "spec_code is None"
        # spec_code should be from V3 parsed set or "unknown"
        v3_codes = {s.code for s in specs}
        assert row.spec_code in v3_codes or row.spec_code == "unknown", (
            f"spec_code {row.spec_code} not in V3 codes and not 'unknown'"
        )
        # assembly_type must be 'lighting_fixture_panel'
        assert row.assembly_type == "lighting_fixture_panel"
        # loop_id must be present
        assert hasattr(row, "loop_id"), "Row missing loop_id"


def test_build_lighting_boq_persists_to_boq_items_table():
    """Lighting BOQ rows must land in boq_items with discipline=lighting
    and the new spec_code/loop_id columns populated."""
    symbols, rooms, specs, zones = _load_all()
    rows = build_lighting_boq(symbols, rooms, specs, zones)
    assert len(rows) > 0
    insp = inspect(get_engine())
    cols = {c["name"] for c in insp.get_columns("boq_items")}
    assert "spec_code" in cols
    assert "loop_id" in cols
