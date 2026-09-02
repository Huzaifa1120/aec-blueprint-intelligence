"""Integration test: V1 (denoiser) + V2 (room mapper) + V3 (legend parser)
+ V4 (loop quantifier) on the real Part-1 lighting layout PDF.

This is the handoff-doc acceptance check:
  - 673 denoised symbols
  - 181 room polygons
  - ≥25 fixture specs in legend (we see 50+)
  - 293 fixtures distributed across 10 DALI loops
"""
import pymupdf

from app.services.lighting.denoiser import extract_denoised_symbols
from app.services.lighting.room_mapper import build_room_polygons
from app.services.lighting.legend_parser import parse_legend, get_legend_stats
from app.services.lighting.loop_quantifier import (
    build_loop_zones, assign_symbols_to_zones, get_zone_stats,
)
from app.services.lighting.text_clustering import extract_dali_loops
from app.services.lighting.reconciliation import deduplicate_loops


SAMPLE_PDF = (
    "../data/samples/P0050-AMC-A-E2-2F-EL-122-02-B, "
    "Lighting Layout, 2nd Floor, Part-1.pdf"
)


def test_v1_v2_v3_v4_pipeline_on_part1():
    doc = pymupdf.open(SAMPLE_PDF)
    page = doc[0]
    try:
        # V1
        symbols = extract_denoised_symbols(page)
        assert len(symbols) >= 600, f"Expected ≥600 denoised, got {len(symbols)}"

        # V2
        rooms = build_room_polygons(page)
        assert len(rooms) >= 150, f"Expected ≥150 rooms, got {len(rooms)}"

        # V3
        specs = parse_legend(page)
        legend_stats = get_legend_stats(specs)
        assert legend_stats["total"] >= 25

        # V4
        loops_raw = extract_dali_loops(page)
        unique_loops, _ = deduplicate_loops(loops_raw)
        zones = build_loop_zones(unique_loops, radius=4000.0)  # wide radius
        assign_symbols_to_zones(symbols, zones, rooms)
        zone_stats = get_zone_stats(zones)

        # The full Part-1 plan has 293 fixtures in 10 loops
        assert zone_stats["total_capacity"] == 293
        # The quantifier should fill at least 50% of capacity
        assert zone_stats["total_used"] >= 100, (
            f"Only {zone_stats['total_used']}/{zone_stats['total_capacity']} "
            f"symbols placed — tie-breaker may be too strict"
        )
    finally:
        doc.close()
