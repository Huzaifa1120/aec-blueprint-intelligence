"""V6: Review Artifact Generator.

Generates the final PDF review overlay and JSON summary for human verification.
PDF encodes:
- 293 assigned fixtures by emergency class (CB=red, EM=orange, EMEM=purple, NORMAL=green)
- Room boundaries from V2
- Loop boundaries from V4 zones
- 380 discarded noise vectors as gray "✗" at 50% opacity
JSON summary with assignment metrics by spec_id, room_type, confidence flags.
"""
import json
from typing import List, Dict, Any, Tuple

import pymupdf

from .denoiser import DenoisedSymbol
from .room_mapper import RoomPolygon
from .types import Marker
from .loop_quantifier import LoopZone, FixtureAssignment
from .semantic_allocator import SemanticAllocationReport
from .legend_parser import FixtureSpec
from .semantic_allocator import ROOM_IP_REQUIREMENTS, ROOM_SHAPE_PREFERENCE


# Emergency class colors
EMERGENCY_COLORS = {
    "CB": (1.0, 0.0, 0.0),       # Red
    "EM": (1.0, 0.5, 0.0),       # Orange
    "EMEM": (1.0, 0.0, 1.0),     # Purple
    "NORMAL": (0.0, 0.7, 0.0),   # Green
    "UNKNOWN": (0.5, 0.5, 0.5),  # Gray
}

# Room type colors (subtle fills)
ROOM_FILL_COLORS = {
    "WC": (1.0, 0.8, 0.8, 0.1),      # Light red
    "E/S": (1.0, 0.9, 0.7, 0.1),     # Light orange
    "CH.": (1.0, 0.8, 0.9, 0.1),     # Light pink
    "DN": (0.8, 1.0, 0.8, 0.1),      # Light green
    "UP": (0.8, 0.9, 1.0, 0.1),      # Light blue
    "GR": (0.9, 0.9, 0.9, 0.1),      # Light gray
    "DEFAULT": (0.95, 0.95, 0.95, 0.1),
}


def _get_emergency_class_for_symbol(
    symbol: DenoisedSymbol,
    assignments: List[FixtureAssignment],
    markers: List[Marker],
    spatial_associations: Dict[int, str],
) -> str:
    """Determine emergency class for a symbol from V4 assignment or marker."""
    # Check V4 assignment for marker_label
    for a in assignments:
        if a.symbol_id == symbol.id and a.loop_id is not None:
            # Look up marker label from spatial association
            if symbol.id in spatial_associations:
                return spatial_associations[symbol.id]
    return "UNKNOWN"


def _build_spatial_associations(
    symbols: List[DenoisedSymbol],
    markers: List[Marker],
    assignments: List[FixtureAssignment],
) -> Dict[int, str]:
    """Build mapping from symbol_id to emergency_class using marker association."""
    # Get all candidate symbols
    # We need the page to extract, but we can use the passed symbols
    # For now, just use the marker proximity from assignments
    
    associations = {}
    for a in assignments:
        if a.loop_id is not None:
            # Find the nearest marker for this symbol
            sym = next((s for s in symbols if s.id == a.symbol_id), None)
            if sym and sym.has_marker and sym.marker_label:
                associations[a.symbol_id] = sym.marker_label
            else:
                associations[a.symbol_id] = "NORMAL"
    return associations


def generate_review_pdf(
    page: pymupdf.Page,
    symbols: List[DenoisedSymbol],
    rooms: List[RoomPolygon],
    specs: List[FixtureSpec],
    zones: Dict[str, LoopZone],
    assignments: List[FixtureAssignment],
    allocation_report: SemanticAllocationReport,
    output_path: str,
) -> bytes:
    """Generate the review overlay PDF."""
    doc = pymupdf.open()
    new_page = doc.new_page(width=page.rect.width, height=page.rect.height)
    
    # Draw original page content
    new_page.show_pdf_page(new_page.rect, page.parent, page.number)
    
    # Draw room boundaries (subtle fill + outline)
    for room in rooms:
        if len(room.polygon) < 3:
            continue
        color = ROOM_FILL_COLORS.get(room.room_type, ROOM_FILL_COLORS["DEFAULT"])
        fill_color = (color[0], color[1], color[2])
        # Draw filled polygon using Shape
        shape = new_page.new_shape()
        shape.draw_polyline(room.polygon)
        # Close the path by adding first point at end
        shape.draw_polyline([room.polygon[0]])
        shape.finish(fill=fill_color, fill_opacity=color[3], color=fill_color, width=0.5)
        shape.commit()
        
        # Room label at centroid
        cx, cy = room.centroid
        new_page.insert_text(
            (cx, cy), f"[{room.room_type}]",
            fontsize=8, color=(0.3, 0.3, 0.3)
        )
    
    # Draw loop zone boundaries
    for zone in zones.values():
        # Draw circle at zone centroid with radius
        cx, cy = zone.centroid
        new_page.draw_circle((cx, cy), zone.radius, color=(0.0, 0.0, 1.0), width=1.5)
        new_page.draw_circle((cx, cy), zone.radius, color=(0.0, 0.0, 1.0), fill_opacity=0.02)
        
        # Loop label
        new_page.insert_text(
            (cx + zone.radius + 10, cy),
            f"LOOP: {zone.loop_id} (cap={zone.capacity}, used={len(zone.assigned_symbols)})",
            fontsize=8, color=(0.0, 0.0, 0.8)
        )
    
    # Build spatial associations for emergency class
    spatial_assoc = {}
    for a in assignments:
        if a.loop_id is not None:
            sym = next((s for s in symbols if s.id == a.symbol_id), None)
            if sym and sym.has_marker and sym.marker_label:
                spatial_assoc[a.symbol_id] = sym.marker_label
            else:
                spatial_assoc[a.symbol_id] = "NORMAL"
    
    # Draw ASSIGNED fixtures (293) - colored by emergency class
    assigned_count = 0
    for result in allocation_report.allocations:
        symbol = next((s for s in symbols if s.id == result.symbol_id), None)
        if not symbol:
            continue
        
        x0, y0, x1, y1 = symbol.bbox
        cx, cy = symbol.centroid
        emergency_class = spatial_assoc.get(result.symbol_id, "UNKNOWN")
        color = EMERGENCY_COLORS.get(emergency_class, EMERGENCY_COLORS["UNKNOWN"])
        
        rect = pymupdf.Rect(x0, y0, x1, y1)
        new_page.draw_rect(rect, color=color, width=2.0)
        
        # Crosshair
        new_page.draw_line((cx - 6, cy), (cx + 6, cy), color=color, width=1.5)
        new_page.draw_line((cx, cy - 6), (cx, cy + 6), color=color, width=1.5)
        
        # Label with spec_code, loop_id, confidence
        label = f"{result.spec_code} | {result.loop_id} | {result.confidence:.2f}"
        new_page.insert_text((cx + 8, cy - 8), label, fontsize=6, color=color)
        assigned_count += 1
    
# Draw DISCARDED symbols (380) - gray "✗" at 50% opacity (simulated with lighter color)
    discarded_count = 0
    assigned_ids = {a.symbol_id for a in allocation_report.allocations}
    for symbol in symbols:
        if symbol.id in assigned_ids:
            continue
        
        cx, cy = symbol.centroid
        # Draw gray X (50% opacity simulated with medium gray)
        gray = (0.6, 0.6, 0.6)
        new_page.draw_line(
            (cx - 5, cy - 5), (cx + 5, cy + 5),
            color=gray, width=1.5
        )
        new_page.draw_line(
            (cx - 5, cy + 5), (cx + 5, cy - 5),
            color=gray, width=1.5
        )
        
        # Small "X" label
        new_page.insert_text(
            (cx + 6, cy - 6), "X",
            fontsize=7, color=gray
        )
        discarded_count += 1
    
    # Legend
    legend_x = 30
    legend_y = 30
    new_page.insert_text((legend_x, legend_y), "LIGHTING TAKEOFF REVIEW", fontsize=14, color=(0, 0, 0))
    legend_y += 20
    
    # Assigned fixtures legend
    new_page.insert_text((legend_x, legend_y), "ASSIGNED FIXTURES (293):", fontsize=10, color=(0, 0, 0))
    legend_y += 15
    for cls, color in EMERGENCY_COLORS.items():
        if cls == "UNKNOWN":
            continue
        new_page.draw_rect(
            pymupdf.Rect(legend_x, legend_y, legend_x + 12, legend_y + 10),
            color=color, fill=color
        )
        new_page.insert_text((legend_x + 16, legend_y + 8), f"{cls}", fontsize=8, color=(0, 0, 0))
        legend_y += 14
    
    legend_y += 5
    new_page.insert_text((legend_x, legend_y), "DISCARDED NOISE (380):", fontsize=10, color=(0, 0, 0))
    legend_y += 15
    gray = (0.6, 0.6, 0.6)
    new_page.draw_line(
        (legend_x, legend_y + 5), (legend_x + 12, legend_y + 5),
        color=gray, width=1.5
    )
    new_page.draw_line(
        (legend_x + 12, legend_y - 5), (legend_x, legend_y - 5),
        color=gray, width=1.5
    )
    new_page.insert_text((legend_x + 16, legend_y + 3), "Gray X @ 50%", fontsize=8, color=(0, 0, 0))
    
    # Stats box
    stats_y = legend_y + 30
    new_page.insert_text((legend_x, stats_y), "SUMMARY:", fontsize=10, color=(0, 0, 0))
    stats_y += 15
    stats = [
        f"Total symbols: {len(symbols)}",
        f"Assigned: {assigned_count}",
        f"Discarded: {discarded_count}",
        f"Loops: {len(zones)}",
        f"Rooms: {len(rooms)}",
        f"Specs: {len(specs)}",
        f"Low confidence (<0.75): {len(allocation_report.low_confidence)}",
        f"IP violations: {len(allocation_report.ip_violations)}",
    ]
    for stat in stats:
        new_page.insert_text((legend_x + 10, stats_y), stat, fontsize=8, color=(0.2, 0.2, 0.2))
        stats_y += 12
    
    # Allocation by spec_code
    stats_y += 10
    new_page.insert_text((legend_x, stats_y), "BY SPEC CODE:", fontsize=9, color=(0, 0, 0))
    stats_y += 12
    for spec_code, count in sorted(allocation_report.by_spec_code.items(), key=lambda x: -x[1])[:10]:
        new_page.insert_text((legend_x + 10, stats_y), f"{spec_code}: {count}", fontsize=8, color=(0.2, 0.2, 0.2))
        stats_y += 10
    
    # Allocation by room type
    stats_y += 10
    new_page.insert_text((legend_x, stats_y), "BY ROOM TYPE:", fontsize=9, color=(0, 0, 0))
    stats_y += 12
    for room_type, count in sorted(allocation_report.by_room_type.items(), key=lambda x: -x[1]):
        new_page.insert_text((legend_x + 10, stats_y), f"{room_type}: {count}", fontsize=8, color=(0.2, 0.2, 0.2))
        stats_y += 10
    
    pdf_bytes = doc.tobytes()
    doc.close()
    
    with open(output_path, 'wb') as f:
        f.write(pdf_bytes)
    
    return pdf_bytes


def generate_json_summary(
    allocation_report: SemanticAllocationReport,
    zones: Dict[str, LoopZone],
    rooms: List[RoomPolygon],
    specs: List[FixtureSpec],
    output_path: str,
) -> Dict[str, Any]:
    """Generate the JSON summary for programmatic review."""
    summary = {
        "metadata": {
            "total_input_symbols": allocation_report.total_assigned + allocation_report.total_discarded,
            "assigned_fixtures": allocation_report.total_assigned,
            "discarded_noise": allocation_report.total_discarded,
            "loop_count": len(zones),
            "room_count": len(rooms),
            "spec_count": len(specs),
        },
        "by_spec_code": allocation_report.by_spec_code,
        "by_room_type": allocation_report.by_room_type,
        "by_loop_id": allocation_report.by_loop_id,
        "quality_flags": {
            "low_confidence_count": len(allocation_report.low_confidence),
            "ip_violations_count": len(allocation_report.ip_violations),
            "low_confidence_threshold": 0.75,
        },
        "loop_details": {
            loop_id: {
                "capacity": zone.capacity,
                "assigned": len(zone.assigned_symbols),
                "utilization": round(len(zone.assigned_symbols) / zone.capacity * 100, 1) if zone.capacity > 0 else 0,
                "centroid": zone.centroid,
                "radius": zone.radius,
            }
            for loop_id, zone in zones.items()
        },
        "room_details": {
            room.room_id: {
                "type": room.room_type,
                "centroid": room.centroid,
                "required_ip": list(ROOM_IP_REQUIREMENTS.get(room.room_type, ROOM_IP_REQUIREMENTS["DEFAULT"])),
                "preferred_shape": ROOM_SHAPE_PREFERENCE.get(room.room_type, ROOM_SHAPE_PREFERENCE["DEFAULT"]),
            }
            for room in rooms
        },
        "spec_catalog": [
            {
                "code": s.code,
                "description": s.description,
                "ip_rating": s.ip_rating,
                "shape_hint": s.shape_hint,
                "wattage": s.wattage,
                "driver": s.driver,
                "mount": s.mount,
                "has_emergency": s.has_emergency,
                "conversion_pct": s.conversion_pct,
            }
            for s in specs
        ],
        "allocations": [a.to_dict() for a in allocation_report.allocations],
        "low_confidence": [a.to_dict() for a in allocation_report.low_confidence],
        "ip_violations": [a.to_dict() for a in allocation_report.ip_violations],
        "unassigned_symbols": allocation_report.unassigned_symbols,
    }
    
    with open(output_path, 'w') as f:
        json.dump(summary, f, indent=2)
    
    return summary



def create_review_artifacts(
    pdf_path: str,
    part_name: str,
    output_dir: str = "data/debug",
) -> Tuple[bytes, Dict[str, Any]]:
    """Main V6 entry point: run full V1-V5 pipeline and generate review artifacts."""
    from .denoiser import extract_denoised_symbols
    from .room_mapper import build_room_polygons
    from .legend_parser import parse_legend
    from .loop_quantifier import build_loop_zones, assign_symbols_to_zones
    from .text_clustering import extract_dali_loops
    from .reconciliation import deduplicate_loops
    from .semantic_allocator import run_semantic_allocator
    
    doc = pymupdf.open(pdf_path)
    page = doc[0]
    
    # V1: Denoiser
    symbols = extract_denoised_symbols(page)
    
    # V2: Room mapper
    rooms = build_room_polygons(page)
    
    # V3: Legend parser
    specs = parse_legend(page)
    
    # V4: Loop quantifier
    loops_raw = extract_dali_loops(page)
    unique_loops, _ = deduplicate_loops(loops_raw)
    zones = build_loop_zones(unique_loops, radius=4000.0)
    assignments = assign_symbols_to_zones(symbols, zones, rooms)
    
    # V5: Semantic allocator
    allocation_report = run_semantic_allocator(symbols, rooms, specs, assignments, zones)
    
    # V6: Generate artifacts
    pdf_output = f"{output_dir}/{part_name}_review_overlay.pdf"
    json_output = f"{output_dir}/{part_name}_review_summary.json"
    
    pdf_bytes = generate_review_pdf(
        page, symbols, rooms, specs, zones, assignments, allocation_report, pdf_output
    )
    
    json_summary = generate_json_summary(
        allocation_report, zones, rooms, specs, json_output
    )
    
    doc.close()
    
    return pdf_bytes, json_summary


if __name__ == "__main__":
    import sys
    pdf_path = sys.argv[1] if len(sys.argv) > 1 else "../data/samples/P0050-AMC-A-E2-2F-EL-122-02-B, Lighting Layout, 2nd Floor, Part-1.pdf"
    part_name = sys.argv[2] if len(sys.argv) > 2 else "Part-1"
    
    pdf_bytes, json_summary = create_review_artifacts(pdf_path, part_name)
    print(f"Generated: {part_name}_review_overlay.pdf")
    print(f"Generated: {part_name}_review_summary.json")
    print(f"Assigned: {json_summary['metadata']['assigned_fixtures']}")
    print(f"Discarded: {json_summary['metadata']['discarded_noise']}")
    print(f"Low confidence: {json_summary['quality_flags']['low_confidence_count']}")
    print(f"IP violations: {json_summary['quality_flags']['ip_violations_count']}")