from app.services.lighting.denoiser import extract_denoised_symbols
from app.services.lighting.text_clustering import extract_dali_loops
from app.services.lighting.loop_quantifier import build_loop_zones, _symbol_distance_to_loop
import pymupdf

doc = pymupdf.open('G:/AEC-software/data/samples/P0050-AMC-A-E2-2F-EL-122-02-B, Lighting Layout, 2nd Floor, Part-1.pdf')
page = doc[0]

# Get symbols (candidate fixtures)
symbols = extract_denoised_symbols(page)
print(f"Total symbols: {len(symbols)}")
print(f"Symbol coordinate basis: centroid of path bounding box (rect center)")
print()

# Get loop zones
loops, discrepancies = extract_dali_loops(page)
print(f"Total loop zones: {len(loops)}")
print(f"Loop zone coordinate basis: centroid of text cluster spans (mean of span x,y)")
print()

zones = build_loop_zones(loops, radius=800.0)

# For each zone, check how many symbols are within 800pt, and how many are just outside (800-1000pt)
print("=" * 100)
print("LOOP ZONE ASSIGNMENT ANALYSIS (800pt radius vs 1000pt expanded)")
print("=" * 100)

total_assigned = 0
total_capacity = 0

for zone in zones.values():
    capacity = zone.capacity
    assigned = 0
    nearby_800 = 0
    nearby_1000 = 0
    nearby_1200 = 0
    
    for sym in symbols:
        dist = _symbol_distance_to_loop(sym, zone)
        if dist <= 800.0:
            nearby_800 += 1
        if dist <= 1000.0:
            nearby_1000 += 1
        if dist <= 1200.0:
            nearby_1200 += 1
    
    # Actual assigned is min(capacity, nearby_800) in current logic
    assigned = min(capacity, nearby_800)
    total_assigned += assigned
    total_capacity += capacity
    
    shortfall = capacity - assigned
    status = "FULL" if shortfall == 0 else f"SHORT {shortfall}"
    
    print(f"\n{zone.loop_id}:")
    print(f"  Centroid: ({zone.centroid[0]:.1f}, {zone.centroid[1]:.1f})")
    print(f"  Capacity: {capacity}, Assigned: {assigned}, Shortfall: {shortfall} {status}")
    print(f"  Symbols within 800pt: {nearby_800}")
    print(f"  Symbols within 1000pt: {nearby_1000} (+{nearby_1000 - nearby_800})")
    print(f"  Symbols within 1200pt: {nearby_1200} (+{nearby_1200 - nearby_1000})")
    
    if shortfall > 0:
        # Show the actual unassigned symbols near this zone
        unassigned_nearby = []
        for sym in symbols:
            dist = _symbol_distance_to_loop(sym, zone)
            if 800.0 < dist <= 1200.0:
                unassigned_nearby.append((dist, sym))
        unassigned_nearby.sort(key=lambda x: x[0])
        print(f"  Nearest unassigned symbols (800-1200pt):")
        for dist, sym in unassigned_nearby[:5]:
            print(f"    dist={dist:.1f} symbol_id={sym.id} at ({sym.centroid[0]:.1f}, {sym.centroid[1]:.1f}) shape={sym.shape}")

print(f"\n{'='*100}")
print(f"SUMMARY: Total Capacity={total_capacity}, Assigned={total_assigned}, Gap={total_capacity - total_assigned}")
print(f"Expected assigned from pipeline: 414")
doc.close()