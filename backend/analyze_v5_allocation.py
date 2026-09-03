from app.services.lighting.review_generator import create_review_artifacts
from app.services.lighting.semantic_allocator import run_semantic_allocator
from app.services.lighting.denoiser import extract_denoised_symbols
from app.services.lighting.room_mapper import build_room_polygons
from app.services.lighting.legend_parser import parse_legend
from app.services.lighting.text_clustering import extract_dali_loops
from app.services.lighting.loop_quantifier import build_loop_zones, assign_symbols_to_zones
import pymupdf

pdf_path = "G:/AEC-software/data/samples/P0050-AMC-A-E2-2F-EL-122-02-B, Lighting Layout, 2nd Floor, Part-1.pdf"

doc = pymupdf.open(pdf_path)
page = doc[0]

# Run full pipeline up to V5
symbols = extract_denoised_symbols(page)
rooms = build_room_polygons(page)
specs = parse_legend(page)
loops, discrepancies = extract_dali_loops(page)
zones = build_loop_zones(loops, radius=800.0)
assignments = assign_symbols_to_zones(symbols, zones, rooms)
allocation_report = run_semantic_allocator(symbols, rooms, specs, assignments, zones, page)

# Newly recovered zones (absent from prior runs)
# Note: actual loop IDs have no leading zero for single-digit loops
recovered_zones = {
    "DALI LOOP-4": 37,
    "DALI LOOP-9": 33,
    "DALI LOOP-12": 54,  # both zones combined (28+26)
    "DALI LOOP-13": 37,
    "DALI LOOP-15": 16,
}

print("=" * 100)
print("V5 SEMANTIC ALLOCATION ANALYSIS - NEWLY RECOVERED ZONES (168 fixtures)")
print("=" * 100)

# Get allocations by zone
from collections import defaultdict
zone_allocations = defaultdict(list)
for alloc in allocation_report.allocations:
    zone_allocations[alloc.loop_id].append(alloc)

# Print allocation for each recovered zone
for zone_name, expected_count in recovered_zones.items():
    actual_alloc = zone_allocations.get(zone_name, [])
    print(f"\n{'='*80}")
    print(f"{zone_name} (expected: {expected_count}, actual: {len(actual_alloc)})")
    print(f"{'='*80}")
    
    # Group by room type
    room_types = defaultdict(int)
    spec_codes = defaultdict(int)
    low_conf = 0
    ip_viol = 0
    
    for a in actual_alloc:
        room_types[a.assigned_room_type or "None"] += 1
        spec_codes[a.spec_code] += 1
        if a.confidence < 0.75:
            low_conf += 1
        if not a.ip_compliant:
            ip_viol += 1
    
    print(f"  By room type: {dict(room_types)}")
    print(f"  By spec code: {dict(spec_codes)}")
    print(f"  Low confidence (<0.75): {low_conf}")
    print(f"  IP violations: {ip_viol}")

# Summary stats
print(f"\n{'='*100}")
print("SUMMARY")
print(f"{'='*100}")
print(f"Total IP violations: {len(allocation_report.ip_violations)}")
print(f"Total low confidence (<0.75): {len(allocation_report.low_confidence)}")
print(f"Total assigned: {allocation_report.total_assigned}")
print(f"Total discarded: {allocation_report.total_discarded}")

# Check if any of the recovered zones have IP violations or low confidence
print(f"\nNEWLY RECOVERED ZONES - FLAG CHECK:")
for zone_name in recovered_zones:
    actual_alloc = zone_allocations.get(zone_name, [])
    zone_low_conf = sum(1 for a in actual_alloc if a.confidence < 0.75)
    zone_ip_viol = sum(1 for a in actual_alloc if not a.ip_compliant)
    print(f"  {zone_name}: low_conf={zone_low_conf}, ip_viol={zone_ip_viol}, allocated={len(actual_alloc)}")

doc.close()