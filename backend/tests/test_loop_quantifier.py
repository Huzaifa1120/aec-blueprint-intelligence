"""Tests for V4 Loop Zone Quantifier.

Locks in the interface from the handoff doc:
  - build_loop_zones(loops, symbols, rooms) -> Dict[str, LoopZone]
  - LoopZone: loop_id, centroid, radius, assigned_symbols (≤ text_quantity)
  - Tie-breaker: emergency marker > room IP match > shape preference > distance
"""
import pytest  # noqa: F401  (kept for future test fixtures)

from app.services.lighting.denoiser import DenoisedSymbol
from app.services.lighting.room_mapper import RoomPolygon
from app.services.lighting.loop_quantifier import (
    LoopZone,
    FixtureAssignment,
    build_loop_zones,
    assign_symbols_to_zones,
    get_zone_stats,
    TIE_BREAKER_PRIORITY,
)


SAMPLE_LOOPS = [
    {"panel": "LCP-L2/01", "part": "PART-1", "loop": "DALI LOOP-03",
     "quantity": 36, "source_y": 100.0, "line_cluster_id": 0},
    {"panel": "LCP-L2/01", "part": "PART-1", "loop": "DALI LOOP-4",
     "quantity": 37, "source_y": 200.0, "line_cluster_id": 1},
    {"panel": "LCP-L2/01", "part": "PART-1", "loop": "DALI LOOP-08",
     "quantity": 34, "source_y": 300.0, "line_cluster_id": 2},
]


def make_symbol(id, x, y, shape="circle", has_marker=False, marker_label=None,
                assigned_room=None):
    return DenoisedSymbol(
        id=id,
        centroid=(x, y),
        bbox=(x - 5, y - 5, x + 5, y + 5),
        shape=shape,
        area=50.0,
        layer="DALI CONTROL",
        path_signature=("c", "c", "c", "c"),
        has_marker=has_marker,
        marker_label=marker_label,
        assigned_room=assigned_room,
    )


def make_room(rid, x, y, ip="IP65", preferred_shape="circle", emergency_pct=0.5,
              weight=1.0, radius=200.0):
    """Create a circular room polygon for testing."""
    import math
    poly = [
        (x + radius * math.cos(2 * math.pi * i / 16),
         y + radius * math.sin(2 * math.pi * i / 16))
        for i in range(16)
    ]
    return RoomPolygon(
        room_id=rid,
        room_type=rid.split("_")[0],
        polygon=poly,
        centroid=(x, y),
        rules={
            "required_ip": [ip],
            "preferred_shape": preferred_shape,
            "emergency_pct": emergency_pct,
            "weight": weight,
            "description": rid,
        },
        code_positions=[(x, y)],
    )


# ----- Structural tests -----


def test_loop_zone_has_required_fields():
    required = {"loop_id", "centroid", "radius", "assigned_symbols", "capacity"}
    field_names = {f.name for f in LoopZone.__dataclass_fields__.values()}
    assert required.issubset(field_names), \
        f"LoopZone missing fields: {required - field_names}"


def test_fixture_assignment_has_required_fields():
    required = {"symbol_id", "loop_id", "rank", "score_breakdown"}
    field_names = {f.name for f in FixtureAssignment.__dataclass_fields__.values()}
    assert required.issubset(field_names), \
        f"FixtureAssignment missing fields: {required - field_names}"


def test_tie_breaker_priority_is_documented():
    """The handoff doc locks in the priority order."""
    assert TIE_BREAKER_PRIORITY == [
        "emergency_marker", "room_ip_match", "shape_preference", "distance",
    ]


# ----- build_loop_zones tests -----


def test_build_loop_zones_returns_zone_per_loop():
    zones = build_loop_zones(SAMPLE_LOOPS)
    assert len(zones) == len(SAMPLE_LOOPS)
    for loop in SAMPLE_LOOPS:
        assert loop["loop"] in zones


def test_build_loop_zones_centroid_matches_source_y():
    """Loop label positions are placed at the cluster's source_y."""
    zones = build_loop_zones(SAMPLE_LOOPS)
    for loop in SAMPLE_LOOPS:
        zone = zones[loop["loop"]]
        assert zone.centroid[1] == loop["source_y"]


def test_build_loop_zones_capacity_equals_text_quantity():
    zones = build_loop_zones(SAMPLE_LOOPS)
    for loop in SAMPLE_LOOPS:
        zone = zones[loop["loop"]]
        assert zone.capacity == loop["quantity"]


def test_build_loop_zones_empty_loops():
    zones = build_loop_zones([])
    assert zones == {}


# ----- assign_symbols_to_zones tests (tie-breaker) -----


def test_assign_symbols_to_zones_assigns_at_most_capacity():
    """No zone should receive more symbols than its text_quantity capacity."""
    symbols = [make_symbol(i, x=100 + i * 10, y=200) for i in range(50)]
    zones = build_loop_zones(SAMPLE_LOOPS)
    rooms = [make_room("WC_0", x=500, y=500)]
    assignments = assign_symbols_to_zones(symbols, zones, rooms)
    # Total assigned ≤ sum of capacities
    total_assigned = sum(1 for a in assignments if a.loop_id is not None)
    total_capacity = sum(z.capacity for z in zones.values())
    assert total_assigned <= total_capacity


def test_assign_symbols_to_zones_respects_emergency_marker_priority():
    """A symbol with has_marker=True outranks one without, all else equal."""
    sym_em = make_symbol(0, x=200, y=200, has_marker=True, marker_label="EM")
    sym_normal = make_symbol(1, x=200, y=200, has_marker=False)
    symbols = [sym_normal, sym_em]
    zones = build_loop_zones([
        {"panel": "LCP-L2/01", "part": "PART-1", "loop": "DALI LOOP-03",
         "quantity": 1, "source_y": 200.0, "line_cluster_id": 0},
    ])
    rooms = []
    assignments = assign_symbols_to_zones(symbols, zones, rooms)
    assigned = [a for a in assignments if a.loop_id is not None]
    assert len(assigned) == 1
    assert assigned[0].symbol_id == 0  # emergency symbol wins


def test_assign_symbols_to_zones_respects_room_ip_match():
    """Symbol in a room with matching IP outranks one in non-matching room."""
    # Two rooms: one matches the symbol's room IP, one doesn't
    room_match = make_room("WC_0", x=200, y=200, ip="IP65")
    room_other = make_room("GR_0", x=400, y=400, ip="IP20")
    sym_in_match = make_symbol(0, x=200, y=200, assigned_room="WC_0")
    sym_in_other = make_symbol(1, x=400, y=400, assigned_room="GR_0")
    symbols = [sym_in_other, sym_in_match]
    zones = build_loop_zones([
        {"panel": "LCP-L2/01", "part": "PART-1", "loop": "DALI LOOP-03",
         "quantity": 1, "source_y": 200.0, "line_cluster_id": 0},
    ])
    assignments = assign_symbols_to_zones(symbols, zones, rooms=[room_match, room_other])
    assigned = [a for a in assignments if a.loop_id is not None]
    assert len(assigned) == 1
    # The symbol in the WC room with IP65 (loop's preferred IP) wins
    assert assigned[0].symbol_id == 0


def test_assign_symbols_to_zones_respects_shape_preference():
    """Same room, same IP, no emergency: shape preference breaks the tie."""
    room = make_room("WC_0", x=200, y=200, ip="IP65", preferred_shape="circle")
    sym_circle = make_symbol(0, x=200, y=200, shape="circle", assigned_room="WC_0")
    sym_hex = make_symbol(1, x=200, y=200, shape="hexagon", assigned_room="WC_0")
    symbols = [sym_hex, sym_circle]
    zones = build_loop_zones([
        {"panel": "LCP-L2/01", "part": "PART-1", "loop": "DALI LOOP-03",
         "quantity": 1, "source_y": 200.0, "line_cluster_id": 0},
    ])
    assignments = assign_symbols_to_zones(symbols, zones, rooms=[room])
    assigned = [a for a in assignments if a.loop_id is not None]
    assert len(assigned) == 1
    # Circle (preferred) wins over hexagon
    assert assigned[0].symbol_id == 0


def test_assign_symbols_to_zones_distance_tiebreak():
    """Same room/IP/shape/emergency: closest symbol wins."""
    room = make_room("WC_0", x=200, y=200, ip="IP65", preferred_shape="circle")
    sym_far = make_symbol(0, x=600, y=600, shape="circle", assigned_room="WC_0")
    sym_near = make_symbol(1, x=210, y=210, shape="circle", assigned_room="WC_0")
    symbols = [sym_far, sym_near]
    zones = build_loop_zones([
        {"panel": "LCP-L2/01", "part": "PART-1", "loop": "DALI LOOP-03",
         "quantity": 1, "source_y": 200.0, "line_cluster_id": 0},
    ])
    assignments = assign_symbols_to_zones(symbols, zones, rooms=[room])
    assigned = [a for a in assignments if a.loop_id is not None]
    assert len(assigned) == 1
    # Closer symbol wins
    assert assigned[0].symbol_id == 1


def test_assign_symbols_score_breakdown_is_documented():
    """Each assignment must explain why it was picked (spec v3 §7.12 transparency)."""
    sym = make_symbol(0, x=200, y=200, has_marker=True, marker_label="EM",
                      assigned_room="WC_0")
    room = make_room("WC_0", x=200, y=200, ip="IP65", preferred_shape="circle")
    zones = build_loop_zones([
        {"panel": "LCP-L2/01", "part": "PART-1", "loop": "DALI LOOP-03",
         "quantity": 1, "source_y": 200.0, "line_cluster_id": 0},
    ])
    assignments = assign_symbols_to_zones([sym], zones, rooms=[room])
    a = assignments[0]
    assert "emergency_marker" in a.score_breakdown
    assert "room_ip_match" in a.score_breakdown
    assert "shape_preference" in a.score_breakdown
    assert "distance" in a.score_breakdown


# ----- get_zone_stats -----


def test_get_zone_stats_summarizes_zones():
    zones = build_loop_zones(SAMPLE_LOOPS)
    stats = get_zone_stats(zones)
    assert stats["total_zones"] == len(zones)
    assert stats["total_capacity"] == sum(z.capacity for z in zones.values())
    assert "capacity_by_loop" in stats
