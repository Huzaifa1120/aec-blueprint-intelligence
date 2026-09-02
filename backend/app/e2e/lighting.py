"""Task 4: build_lighting_boq — V1-V4 → LightingBoqRow glue.

Pure function: takes V1 denoised symbols, V2 rooms, V3 specs, V4 zones →
returns LightingBoqRow list ready for persistence. Every row carries spec_code
(V3), loop_id (V4), quantity (V4), DERIVED tier, blended confidence in [0.3, 1.0],
and unpriced flag (no catalog hardcode).
"""

from dataclasses import dataclass
from typing import List, Dict, Optional

from app.services.lighting.denoiser import DenoisedSymbol
from app.services.lighting.room_mapper import RoomPolygon
from app.services.lighting.legend_parser import FixtureSpec
from app.services.lighting.loop_quantifier import LoopZone


@dataclass
class LightingBoqRow:
    """BOQ row for lighting fixtures (assembly_type='lighting_fixture_panel')."""

    assembly_type: str = "lighting_fixture_panel"
    spec_code: str = "unknown"
    loop_id: Optional[str] = None
    quantity: int = 0
    unit_price: Optional[float] = None  # Always None — no catalog hardcode
    total_cost: Optional[float] = None
    unpriced: bool = True
    confidence_status: str = "DERIVED"
    confidence_score: float = 0.3
    score_breakdown: Dict[str, float] = None
    marker_label: Optional[str] = None
    symbol_id: Optional[int] = None


def build_lighting_boq(
    symbols: List[DenoisedSymbol],
    rooms: List[RoomPolygon],
    specs: List[FixtureSpec],
    zones: Dict[str, LoopZone],
) -> List[LightingBoqRow]:
    """
    Build lighting BOQ rows from V1-V4 pipeline outputs.

    Pure function — no DB I/O, no global state.
    """
    if not symbols or not zones:
        return []

    # Map symbols by ID for quick lookup
    sym_by_id = {s.id: s for s in symbols}

    # Get V4 assignments (already computed by assign_symbols_to_zones in _load_all)
    # We need to re-run to get FixtureAssignment objects with score_breakdown
    from app.services.lighting.loop_quantifier import assign_symbols_to_zones

    assignments = assign_symbols_to_zones(symbols, zones, rooms)

    # Confidence blending weights (per spec: emergency=0.4, ip=0.3, shape=0.2, distance=0.1)
    CONFIDENCE_WEIGHTS = {
        "emergency_marker": 0.4,
        "room_ip_match": 0.3,
        "shape_preference": 0.2,
        "distance": 0.1,
    }

    rows: List[LightingBoqRow] = []

    for assignment in assignments:
        if assignment.loop_id is None:
            # Skip unassigned symbols
            continue

        sym = sym_by_id.get(assignment.symbol_id)
        if sym is None:
            continue

        # Determine spec_code from V3 specs
        # Try to match symbol shape to a spec's shape_hint, fallback to first spec or "unknown"
        spec_code = "unknown"
        if specs:
            # Find spec matching symbol shape
            for spec in specs:
                if spec.shape_hint and spec.shape_hint != "unknown":
                    # Map denoiser shape to legend shape_hint
                    shape_map = {
                        "circle": "downlight",
                        "hexagon": "panel",
                        "nonagon": "strip",
                    }
                    if shape_map.get(sym.shape) == spec.shape_hint:
                        spec_code = spec.code
                        break
            # If no shape match, use first spec code
            if spec_code == "unknown":
                spec_code = specs[0].code

        # Blend confidence from V4 score_breakdown
        breakdown = assignment.score_breakdown or {}
        blended = sum(
            breakdown.get(factor, 0.0) * weight for factor, weight in CONFIDENCE_WEIGHTS.items()
        )
        # Floor at 0.3
        confidence = max(0.3, min(1.0, blended))

        # Each assigned symbol = 1 fixture
        quantity = 1

        row = LightingBoqRow(
            assembly_type="lighting_fixture_panel",
            spec_code=spec_code,
            loop_id=assignment.loop_id,
            quantity=quantity,
            unit_price=None,  # No catalog hardcode
            total_cost=None,
            unpriced=True,
            confidence_status="DERIVED",
            confidence_score=confidence,
            score_breakdown=breakdown,
            marker_label=sym.marker_label,
            symbol_id=sym.id,
        )
        rows.append(row)

    return rows
