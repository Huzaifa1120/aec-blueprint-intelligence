from app.services.lighting.text_clustering import extract_dali_loops
from app.services.lighting.loop_quantifier import build_loop_zones, assign_symbols_to_zones, get_zone_stats
from app.services.lighting.denoiser import extract_denoised_symbols
from app.services.lighting.room_mapper import build_room_polygons
import pymupdf

def process_part_full(part_name, pdf_path):
    """Process a single part through the full extraction pipeline."""
    doc = pymupdf.open(pdf_path)
    page = doc[0]
    
    # Full extraction pipeline
    loops, discrepancies = extract_dali_loops(page)
    
    print(f"\n{'='*80}")
    print(f"{part_name} - EXTRACTED LOOPS: {len(loops)}")
    print(f"{'='*80}")
    
    total_cap = 0
    for l in loops:
        total_cap += l['quantity']
        print(f"  {l['loop']}: qty={l['quantity']} centroid=({l['source_x']:.1f}, {l['source_y']:.1f})")
        print(f"    raw: {l.get('raw_text', 'N/A')[:120]}...")
    
    print(f"\n  TOTAL CAPACITY: {total_cap}")
    
    if discrepancies:
        print(f"  DISCREPANCIES: {len(discrepancies)}")
        for d in discrepancies:
            print(f"    {d['type']}: {d['message']}")
    
    # Get symbols for V4 assignment
    symbols = extract_denoised_symbols(page)
    rooms = build_room_polygons(page)
    zones = build_loop_zones(loops, radius=800.0)
    assignments = assign_symbols_to_zones(symbols, zones, rooms)
    
    # Count assigned per zone
    from collections import Counter
    assigned_counts = Counter(a.loop_id for a in assignments if a.loop_id is not None)
    
    print(f"\n  V4 ASSIGNMENT:")
    for zone in zones.values():
        cap = zone.capacity
        assigned = assigned_counts.get(zone.loop_id, 0)
        shortfall = cap - assigned
        status = "FULL" if shortfall == 0 else f"SHORT {shortfall}"
        print(f"    {zone.loop_id}: cap={cap}, assigned={assigned}, {status}")
    
    total_assigned = sum(assigned_counts.values())
    total_capacity = sum(z.capacity for z in zones.values())
    print(f"    TOTAL: cap={total_capacity}, assigned={total_assigned}")
    
    doc.close()
    return loops, discrepancies, zones, assignments

# Process all three parts
parts = [
    ("Part-1", "G:/AEC-software/data/samples/P0050-AMC-A-E2-2F-EL-122-02-B, Lighting Layout, 2nd Floor, Part-1.pdf"),
    ("Part-2", "G:/AEC-software/data/samples/P0050-AMC-A-E2-2F-EL-123-03-B, Lighting Layout, 2nd Floor, Part-2.pdf"),
    ("Part-3", "G:/AEC-software/data/samples/P0050-AMC-A-E2-2F-EL-123-04-B, Lighting Layout, 2nd Floor, Part-3.pdf"),
]

for part_name, pdf_path in parts:
    process_part_full(part_name, pdf_path)