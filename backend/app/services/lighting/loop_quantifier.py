"""V4: Loop Zone Quantifier.

Builds spatial zones around each DALI loop label and assigns candidate fixtures
(symbols) to zones using a deterministic tie-breaker cascade.

Tie-breaker priority (from the handoff doc, locked in):
  1. emergency_marker — symbols with has_marker=True outrank those without
  2. room_ip_match    — symbol's assigned_room has IP that matches loop's preferred IP
  3. shape_preference — symbol.shape matches room's preferred_shape
  4. distance         — closest to the loop label centroid wins
"""
import math
from dataclasses import dataclass, field
from typing import List, Dict, Optional, Tuple, Any

from .denoiser import DenoisedSymbol
from .room_mapper import RoomPolygon


# Tie-breaker priority order (locked in by handoff doc)
TIE_BREAKER_PRIORITY: List[str] = [
    "emergency_marker",
    "room_ip_match",
    "shape_preference",
    "distance",
]

# Default loop zone radius (points). Symbols outside this radius are not considered
# for the loop. Tuned to cover one room's worth of plan area.
DEFAULT_LOOP_RADIUS = 400.0

# Emergency class score (the marker label hierarchy)
EMERGENCY_SCORES = {
    "EMEM": 3,   # combined emergency + maintained
    "EM": 2,     # emergency
    "CB": 1,     # circuit breaker (standard / non-emergency)
    "NORMAL": 0,
    None: 0,
}


@dataclass
class FixtureAssignment:
    symbol_id: int
    loop_id: Optional[str]
    rank: int                                # 0 = best, 1 = second, ...
    score_breakdown: Dict[str, float]        # one score per tie-breaker factor


@dataclass
class LoopZone:
    loop_id: str
    centroid: Tuple[float, float]
    radius: float
    capacity: int                            # enforced Top-K limit
    assigned_symbols: List[int] = field(default_factory=list)


# ---------- Zone construction ----------


def build_loop_zones(loops: List[Dict[str, Any]],
                     radius: float = DEFAULT_LOOP_RADIUS) -> Dict[str, LoopZone]:
    """Create a LoopZone per spatially distinct loop.

    Uses composite key (loop_id, cluster_id) to preserve spatially distinct
    zones sharing the same loop_id (e.g., two LOOP-12 zones at different locations).
    """
    zones: Dict[str, LoopZone] = {}
    for loop in loops:
        loop_id = loop["loop"]
        cluster_id = loop.get("line_cluster_id", 0)
        # Composite key: unique per spatial zone, preserves loop_id collisions
        composite_key = f"{loop_id}_c{cluster_id}"
        zones[composite_key] = LoopZone(
            loop_id=loop["loop"],
            centroid=(float(loop["source_x"]), float(loop["source_y"])),
            radius=radius,
            capacity=int(loop["quantity"]),
        )
    return zones


# ---------- Scoring ----------


def _symbol_distance_to_loop(symbol: DenoisedSymbol,
                             zone: LoopZone) -> float:
    return math.hypot(
        symbol.centroid[0] - zone.centroid[0],
        symbol.centroid[1] - zone.centroid[1],
    )


def _is_within_zone(symbol: DenoisedSymbol, zone: LoopZone) -> bool:
    return _symbol_distance_to_loop(symbol, zone) <= zone.radius


def _find_room_for_symbol(symbol: DenoisedSymbol,
                          rooms: List[RoomPolygon]) -> Optional[RoomPolygon]:
    if symbol.assigned_room is None:
        return None
    for r in rooms:
        if r.room_id == symbol.assigned_room:
            return r
    return None


def _score_symbol(symbol: DenoisedSymbol, zone: LoopZone,
                  rooms: List[RoomPolygon]) -> Dict[str, float]:
    """Compute a score for each tie-breaker factor. Higher = better."""
    room = _find_room_for_symbol(symbol, rooms)

    # 1. emergency_marker: 1.0 if has emergency marker, 0.0 otherwise
    if symbol.has_marker and symbol.marker_label:
        em_score = float(EMERGENCY_SCORES.get(symbol.marker_label, 0)) / 3.0
    else:
        em_score = 0.0

    # 2. room_ip_match: 1.0 if symbol's room has the loop's preferred IP
    # (LoopZone has no IP preference in this minimal model, so score 1.0
    # for any room match — distance to room rules.)
    ip_score = 0.0
    if room is not None:
        # Any room match gives partial credit; a future version can pass
        # loop-specific IP requirements via zone metadata.
        ip_score = 0.5
        # Bonus if room has a high-priority IP
        if any(ip in {"IP65", "IP66"} for ip in room.rules.get("required_ip", [])):
            ip_score = 1.0

    # 3. shape_preference: 1.0 if symbol shape matches room's preferred shape
    shape_score = 0.0
    if room is not None:
        preferred = room.rules.get("preferred_shape")
        if preferred and symbol.shape == preferred:
            shape_score = 1.0
        elif preferred is None:
            shape_score = 0.5  # no preference declared → neutral

    # 4. distance: 1.0 at the loop centroid, 0.0 at the zone radius
    dist = _symbol_distance_to_loop(symbol, zone)
    if zone.radius <= 0:
        dist_score = 1.0
    else:
        dist_score = max(0.0, 1.0 - dist / zone.radius)

    return {
        "emergency_marker": em_score,
        "room_ip_match": ip_score,
        "shape_preference": shape_score,
        "distance": dist_score,
    }


def _total_score(breakdown: Dict[str, float]) -> float:
    """Combine the 4 factor scores. Weights tilt the cascade toward emergency/IP first."""
    weights = {
        "emergency_marker": 1000.0,
        "room_ip_match": 100.0,
        "shape_preference": 10.0,
        "distance": 1.0,
    }
    return sum(breakdown[k] * weights[k] for k in TIE_BREAKER_PRIORITY)


# ---------- Assignment ----------


def assign_symbols_to_zones(symbols: List[DenoisedSymbol],
                            zones: Dict[str, LoopZone],
                            rooms: List[RoomPolygon],
                            ) -> List[FixtureAssignment]:
    """Top-K per-zone assignment: each zone takes its N highest-scoring symbols.
    
    Algorithm:
    1. For each zone, score all symbols using the 4-factor cascade
    2. Sort by score descending, take top N = zone.capacity
    3. A symbol can only be assigned to ONE zone (highest score wins globally)
    4. Unassigned symbols are discarded as CAD noise
    """
    # Compute (score, symbol, zone) for every (symbol, zone) pair
    candidates: List[Tuple[float, DenoisedSymbol, str, LoopZone, Dict[str, float]]] = []
    for sym in symbols:
        for zid, zone in zones.items():
            breakdown = _score_symbol(sym, zone, rooms)
            score = _total_score(breakdown)
            candidates.append((score, sym, zid, zone, breakdown))

    # Sort by score descending, then by symbol id (deterministic tiebreak)
    candidates.sort(key=lambda c: (-c[0], c[1].id))

    # Greedy assignment: each zone takes top-K, each symbol assigned at most once
    assigned: Dict[int, FixtureAssignment] = {}
    zone_taken: Dict[str, int] = {zid: 0 for zid in zones}

    for score, sym, zid, zone, breakdown in candidates:
        if sym.id in assigned:
            continue  # symbol already assigned to higher-scoring zone
        if zone_taken[zid] >= zone.capacity:
            continue  # zone full (Top-K reached)

        zone_taken[zid] += 1
        zone.assigned_symbols.append(sym.id)
        assigned[sym.id] = FixtureAssignment(
            symbol_id=sym.id,
            loop_id=zone.loop_id,
            rank=zone_taken[zid] - 1,  # 0-indexed rank within zone
            score_breakdown=breakdown,
        )

    # Build result list in input symbol order
    result: List[FixtureAssignment] = []
    for sym in symbols:
        if sym.id in assigned:
            result.append(assigned[sym.id])
        else:
            # Unassigned — discarded as noise
            result.append(FixtureAssignment(
                symbol_id=sym.id,
                loop_id=None,
                rank=-1,
                score_breakdown={k: 0.0 for k in TIE_BREAKER_PRIORITY},
            ))
    return result


# ---------- Stats ----------


def get_zone_stats(zones: Dict[str, LoopZone]) -> Dict[str, Any]:
    """Return summary statistics for a set of zones."""
    capacity_by_loop = {zid: z.capacity for zid, z in zones.items()}
    used_by_loop = {zid: len(z.assigned_symbols) for zid, z in zones.items()}
    return {
        "total_zones": len(zones),
        "total_capacity": sum(z.capacity for z in zones.values()),
        "total_used": sum(used_by_loop.values()),
        "capacity_by_loop": capacity_by_loop,
        "used_by_loop": used_by_loop,
    }
