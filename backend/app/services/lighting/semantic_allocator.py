"""V5: Semantic Allocator.

Maps V4-assigned symbols to V3 FixtureSpecs using room rules (V2 RoomPolygons).
Enforces IP rating constraints per room type (e.g., WC/CH. require IP65/IP66).
Outputs allocation with confidence scores and rule-violation flags.
"""
from dataclasses import dataclass, field
from typing import List, Dict, Optional, Tuple, Any
from collections import defaultdict

import pymupdf

from .denoiser import DenoisedSymbol
from .room_mapper import RoomPolygon
from .legend_parser import FixtureSpec
from .loop_quantifier import LoopZone, FixtureAssignment


# Room type -> required IP ratings (from ROOM_RULES in room_mapper.py)
ROOM_IP_REQUIREMENTS = {
    "WC": {"IP65", "IP66"},
    "E/S": {"IP44", "IP65"},
    "CH.": {"IP65"},
    "DN": {"IP44"},
    "UP": {"IP44"},
    "GR": {"IP20", "IP40"},
    "DEFAULT": {"IP20", "IP40"},
}

# Room type -> preferred shape
ROOM_SHAPE_PREFERENCE = {
    "WC": "circle",       # Downlights typical for WCs
    "E/S": "panel",
    "CH.": "panel",
    "DN": "downlight",
    "UP": "downlight",
    "GR": "panel",
    "DEFAULT": "panel",
}


@dataclass
class AllocationResult:
    """Result of allocating one symbol to a fixture spec."""
    symbol_id: int
    loop_id: str
    assigned_room_id: Optional[str]
    assigned_room_type: Optional[str]
    spec: FixtureSpec
    spec_code: str
    ip_compliant: bool
    shape_match: bool
    confidence: float
    flags: List[str] = field(default_factory=list)
    derivation: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "symbol_id": self.symbol_id,
            "loop_id": self.loop_id,
            "assigned_room_id": self.assigned_room_id,
            "assigned_room_type": self.assigned_room_type,
            "spec_code": self.spec_code,
            "spec_description": self.spec.description,
            "ip_rating": self.spec.ip_rating,
            "shape_hint": self.spec.shape_hint,
            "wattage": self.spec.wattage,
            "driver": self.spec.driver,
            "mount": self.spec.mount,
            "has_emergency": self.spec.has_emergency,
            "ip_compliant": self.ip_compliant,
            "shape_match": self.shape_match,
            "confidence": round(self.confidence, 3),
            "flags": self.flags,
            "derivation": self.derivation,
        }


@dataclass
class SemanticAllocationReport:
    """Full report of semantic allocation across all loops."""
    allocations: List[AllocationResult]
    total_assigned: int
    total_discarded: int
    by_spec_code: Dict[str, int]
    by_room_type: Dict[str, int]
    by_loop_id: Dict[str, int]
    low_confidence: List[AllocationResult]
    ip_violations: List[AllocationResult]
    unassigned_symbols: List[int]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "total_assigned": self.total_assigned,
            "total_discarded": self.total_discarded,
            "by_spec_code": self.by_spec_code,
            "by_room_type": self.by_room_type,
            "by_loop_id": self.by_loop_id,
            "low_confidence_count": len(self.low_confidence),
            "ip_violations_count": len(self.ip_violations),
            "allocations": [a.to_dict() for a in self.allocations],
            "low_confidence": [a.to_dict() for a in self.low_confidence],
            "ip_violations": [a.to_dict() for a in self.ip_violations],
            "unassigned_symbols": self.unassigned_symbols,
        }


def _get_room_for_symbol(symbol: DenoisedSymbol, rooms: List[RoomPolygon]) -> Optional[RoomPolygon]:
    """Find the room polygon containing this symbol."""
    if symbol.assigned_room is None:
        # Use room_mapper's assign_symbol_to_room
        from .room_mapper import assign_symbol_to_room
        return assign_symbol_to_room(symbol.centroid, rooms)
    
    for room in rooms:
        if room.room_id == symbol.assigned_room:
            return room
    return None


def _get_room_ip_requirements(room_type: str) -> set:
    """Get required IP ratings for a room type."""
    return ROOM_IP_REQUIREMENTS.get(room_type, ROOM_IP_REQUIREMENTS["DEFAULT"])


def _get_room_shape_preference(room_type: str) -> str:
    """Get preferred shape for a room type."""
    return ROOM_SHAPE_PREFERENCE.get(room_type, ROOM_SHAPE_PREFERENCE["DEFAULT"])


def _match_spec_to_room(spec: FixtureSpec, room: RoomPolygon) -> Tuple[bool, bool, List[str]]:
    """
    Check if a FixtureSpec complies with room rules.
    Returns (ip_compliant, shape_match, flags).
    """
    flags = []
    
    # IP compliance
    required_ips = _get_room_ip_requirements(room.room_type)
    ip_compliant = spec.ip_rating in required_ips if spec.ip_rating else False
    if not ip_compliant and spec.ip_rating:
        flags.append(f"IP_VIOLATION: room {room.room_type} requires {required_ips}, got {spec.ip_rating}")
    elif not spec.ip_rating:
        flags.append(f"IP_UNKNOWN: room {room.room_type} requires {required_ips}")
    
    # Shape match
    preferred_shape = _get_room_shape_preference(room.room_type)
    shape_match = spec.shape_hint == preferred_shape
    if not shape_match and spec.shape_hint != "unknown":
        flags.append(f"SHAPE_MISMATCH: room prefers {preferred_shape}, spec is {spec.shape_hint}")
    
    return ip_compliant, shape_match, flags


def _find_best_spec(
    symbol: DenoisedSymbol,
    room: Optional[RoomPolygon],
    specs: List[FixtureSpec],
    assignment: FixtureAssignment,
) -> Tuple[FixtureSpec, float, List[str]]:
    """
    Find the best matching FixtureSpec for a symbol.
    Returns (best_spec, confidence, flags).
    """
    if not specs:
        # Fallback spec
        fallback = FixtureSpec(
            code="unknown",
            description="No spec available",
            wattage=None,
            dimensions=None,
            ip_rating=None,
            shape_hint="unknown",
            driver=None,
            conversion_pct=None,
            has_emergency=False,
            mount=None,
            row_y=0,
        )
        return fallback, 0.3, ["NO_SPECS_AVAILABLE"]
    
    # Score each spec
    scored = []
    for spec in specs:
        score = 0.0
        flags = []
        
        # Base score from V4 assignment
        score += assignment.score_breakdown.get("emergency_marker", 0) * 0.4
        score += assignment.score_breakdown.get("room_ip_match", 0) * 0.3
        score += assignment.score_breakdown.get("shape_preference", 0) * 0.2
        score += assignment.score_breakdown.get("distance", 0) * 0.1
        
        # Room rule compliance bonus/penalty
        if room:
            ip_compliant, shape_match, rule_flags = _match_spec_to_room(spec, room)
            flags.extend(rule_flags)
            if ip_compliant:
                score += 0.15  # Bonus for IP compliance
            else:
                score -= 0.20  # Penalty for IP violation
            if shape_match:
                score += 0.05  # Bonus for shape match
        else:
            flags.append("NO_ROOM_ASSIGNED")
        
        # Emergency class alignment
        if room and spec.has_emergency:
            # Room requires some emergency (from ROOM_RULES emergency_pct)
            req_emergency_pct = room.rules.get("emergency_pct", 0.5)
            if req_emergency_pct > 0.5:
                score += 0.05
        
        scored.append((score, spec, flags))
    
    # Sort by score descending
    scored.sort(key=lambda x: x[0], reverse=True)
    best_score, best_spec, best_flags = scored[0]
    
    # Confidence: normalized score, floored at 0.3
    confidence = max(0.3, min(1.0, best_score))
    
    return best_spec, confidence, best_flags


def run_semantic_allocator(
    symbols: List[DenoisedSymbol],
    rooms: List[RoomPolygon],
    specs: List[FixtureSpec],
    assignments: List[FixtureAssignment],
    zones: Dict[str, LoopZone],
    page: pymupdf.Page = None,
) -> SemanticAllocationReport:
    """
    Main V5 entry point: allocate V4-assigned symbols to V3 specs using V2 room rules.
    
    Args:
        symbols: V1 denoised symbols (673 total, 293 assigned)
        rooms: V2 RoomPolygons (181 rooms)
        specs: V3 FixtureSpecs (33 specs from legend)
        assignments: V4 FixtureAssignments (293 with loop_id, 380 None)
        zones: V4 LoopZones (10 zones)
        page: PDF page for V2 enrichment (markers + rooms)
    
    Returns:
        SemanticAllocationReport with all allocations and metrics
    """
    # V2 Enrichment: populate has_marker, marker_label, assigned_room on symbols
    if page is not None:
        from .spatial_association import enrich_denoised_symbols
        enrich_denoised_symbols(symbols, page, rooms)
    # Map symbols by ID
    sym_by_id = {s.id: s for s in symbols}
    
    # Get assigned symbols (those with loop_id from V4)
    unassigned_symbol_ids = [a.symbol_id for a in assignments if a.loop_id is None]
    
    allocations: List[AllocationResult] = []
    
    for assignment in assignments:
        if assignment.loop_id is None:
            continue  # Skip unassigned
        
        symbol = sym_by_id.get(assignment.symbol_id)
        if symbol is None:
            continue
        
        # Find room for this symbol
        room = _get_room_for_symbol(symbol, rooms)
        assigned_room_id = room.room_id if room else None
        assigned_room_type = room.room_type if room else None
        
        # Find best matching spec
        best_spec, confidence, flags = _find_best_spec(symbol, room, specs, assignment)
        
        # Check IP compliance
        ip_compliant = True
        if room and best_spec.ip_rating:
            required_ips = _get_room_ip_requirements(room.room_type)
            ip_compliant = best_spec.ip_rating in required_ips
        elif room and not best_spec.ip_rating:
            ip_compliant = False
        
        # Check shape match
        shape_match = False
        if room and best_spec.shape_hint != "unknown":
            preferred_shape = _get_room_shape_preference(room.room_type)
            shape_match = best_spec.shape_hint == preferred_shape
        
        # Build derivation info
        derivation = {
            "v4_score_breakdown": assignment.score_breakdown,
            "v4_rank": assignment.rank,
            "room_rules": room.rules if room else {},
            "spec_attributes": {
                "ip_rating": best_spec.ip_rating,
                "shape_hint": best_spec.shape_hint,
                "wattage": best_spec.wattage,
                "driver": best_spec.driver,
                "has_emergency": best_spec.has_emergency,
            }
        }
        
        # Add IP violation flag if applicable
        if room and best_spec.ip_rating:
            required_ips = _get_room_ip_requirements(room.room_type)
            if best_spec.ip_rating not in required_ips:
                flags.append(f"IP_VIOLATION: {best_spec.ip_rating} not in {required_ips}")
        elif room and not best_spec.ip_rating:
            flags.append("IP_UNKNOWN: spec has no IP rating")
        
        result = AllocationResult(
            symbol_id=symbol.id,
            loop_id=assignment.loop_id,
            assigned_room_id=assigned_room_id,
            assigned_room_type=assigned_room_type,
            spec=best_spec,
            spec_code=best_spec.code,
            ip_compliant=ip_compliant,
            shape_match=shape_match,
            confidence=confidence,
            flags=flags,
            derivation=derivation,
        )
        allocations.append(result)
    
    # Compute summary statistics
    by_spec_code: Dict[str, int] = defaultdict(int)
    by_room_type: Dict[str, int] = defaultdict(int)
    by_loop_id: Dict[str, int] = defaultdict(int)
    low_confidence = []
    ip_violations = []
    
    for a in allocations:
        by_spec_code[a.spec_code] += 1
        if a.assigned_room_type:
            by_room_type[a.assigned_room_type] += 1
        by_loop_id[a.loop_id] += 1
        if a.confidence < 0.75:
            low_confidence.append(a)
        if not a.ip_compliant:
            ip_violations.append(a)
    
    return SemanticAllocationReport(
        allocations=allocations,
        total_assigned=len(allocations),
        total_discarded=len(unassigned_symbol_ids),
        by_spec_code=dict(by_spec_code),
        by_room_type=dict(by_room_type),
        by_loop_id=dict(by_loop_id),
        low_confidence=low_confidence,
        ip_violations=ip_violations,
        unassigned_symbols=unassigned_symbol_ids,
    )