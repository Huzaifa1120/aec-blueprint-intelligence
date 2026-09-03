from app.services.lighting.denoiser import extract_denoised_symbols
from app.services.lighting.room_mapper import build_room_polygons
from app.services.lighting.text_clustering import extract_dali_loops
from app.services.lighting.loop_quantifier import build_loop_zones, _score_symbol, _total_score
import pymupdf

pdf_path = "G:/AEC-software/data/samples/P0050-AMC-A-E2-2F-EL-122-02-B, Lighting Layout, 2nd Floor, Part-1.pdf"

doc = pymupdf.open(pdf_path)
page = doc[0]

symbols = extract_denoised_symbols(page)
rooms = build_room_polygons(page)
loops, _ = extract_dali_loops(page)
zones = build_loop_zones(loops, radius=800.0)

print("All zones:")
for zid, zone in zones.items():
    print(f"  {zid}: loop_id={zone.loop_id}, centroid=({zone.centroid[0]:.1f}, {zone.centroid[1]:.1f}), cap={zone.capacity}")

doc.close()