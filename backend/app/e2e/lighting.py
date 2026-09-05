"""Task 4: build_lighting_boq — V1-V5 → LightingBoqRow glue.

Pure function: takes V1 denoised symbols, V2 rooms, V3 specs, V4 zones, V5 allocations →
returns LightingBoqRow list ready for persistence. Every row carries spec_code
(V3 from V5 semantic allocator), loop_id (V4), quantity (V4), DERIVED tier,
blended confidence in [0.3, 1.0], and unpriced flag (no catalog hardcode).
"""

from dataclasses import dataclass
from typing import List, Dict, Optional

from app.services.lighting.denoiser import DenoisedSymbol
from app.services.lighting.room_mapper import RoomPolygon
from app.services.lighting.legend_parser import FixtureSpec
from app.services.lighting.loop_quantifier import LoopZone
from app.services.lighting.semantic_allocator import SemanticAllocationReport


@dataclass
class LightingBoqRow:
    """BOQ row for lighting fixtures (assembly_type='lighting_fixture_panel')."""

    assembly_type: str = "lighting_fixture_panel"
    spec_code: str = "unknown"
    loop_id: Optional[str] = None
    quantity: int = 0
    unit: str = "each"
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
    allocation_report: Optional[SemanticAllocationReport] = None,
) -> List[LightingBoqRow]:
    """
    Build lighting BOQ rows from V1-V5 pipeline outputs.

    Pure function — no DB I/O, no global state.
    Uses V5 semantic allocator's per-fixture spec_code for correct spec matching.
    """
    if not symbols or not zones or not allocation_report:
        return []

    # Map symbols by ID for quick lookup
    sym_by_id = {s.id: s for s in symbols}

    # Confidence blending weights (per spec: emergency=0.4, ip=0.3, shape=0.2, distance=0.1)
    CONFIDENCE_WEIGHTS = {
        "emergency_marker": 0.4,
        "room_ip_match": 0.3,
        "shape_preference": 0.2,
        "distance": 0.1,
    }

    rows: List[LightingBoqRow] = []

    # Use V5 semantic allocator's allocations directly (they have spec_code, loop_id, confidence, etc.)
    for alloc in allocation_report.allocations:
        sym = sym_by_id.get(alloc.symbol_id)
        if sym is None:
            continue

        # Get spec_code from V5 semantic allocator
        spec_code = alloc.spec_code

        # Blend confidence from V5 allocation (already has confidence)
        confidence = alloc.confidence
        # Also blend with V4 score_breakdown if available
        breakdown = alloc.derivation.get("v4_score_breakdown", {})
        blended = sum(
            breakdown.get(factor, 0.0) * weight for factor, weight in CONFIDENCE_WEIGHTS.items()
        )
        # Use V5 confidence if available, else blended
        confidence = max(0.3, min(1.0, alloc.confidence if alloc.confidence > 0 else blended))

        # Each allocated symbol = 1 fixture
        quantity = 1

        row = LightingBoqRow(
            assembly_type="lighting_fixture_panel",
            spec_code=spec_code,
            loop_id=alloc.loop_id,
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
