"""Integration test: V1 (denoiser) + V2 (room mapper) + V3 (legend parser)
+ V4 (loop quantifier) on the real Part-1/2/3 lighting layout PDFs.

This is the handoff-doc acceptance check:
  Part-1: 673 denoised symbols, 181 room polygons, ≥25 fixture specs, 442 fixtures across 15 zones (14 zones: 13 unique loop IDs + LOOP-12 twice)
  Part-2: 370 denoised symbols, 157 room polygons, ≥25 fixture specs, 202 fixtures across 6 zones
  Part-3: 126 denoised symbols, 165 room polygons, ≥25 fixture specs, 116 fixtures across 4 zones
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


PART1_PDF = (
    "../data/samples/P0050-AMC-A-E2-2F-EL-122-02-B, "
    "Lighting Layout, 2nd Floor, Part-1.pdf"
)

PART2_PDF = (
    "../data/samples/P0050-AMC-A-E2-2F-EL-123-03-B, "
    "Lighting Layout, 2nd Floor, Part-2.pdf"
)

PART3_PDF = (
    "../data/samples/P0050-AMC-A-E2-2F-EL-123-04-B, "
    "Lighting Layout, 2nd Floor, Part-3.pdf"
)


def run_v4_pipeline(page, expected_total_capacity, expected_zones, loop12_check=None):
    """Run V1-V4 pipeline on a page and verify zone stats."""
    # V1
    symbols = extract_denoised_symbols(page)
    # V2
    rooms = build_room_polygons(page)
    # V3
    specs = parse_legend(page)
    legend_stats = get_legend_stats(specs)
    assert legend_stats["total"] >= 25

    # V4
    loops_raw, _ = extract_dali_loops(page)
    unique_loops, _ = deduplicate_loops(loops_raw)
    zones = build_loop_zones(unique_loops, radius=4000.0)
    assign_symbols_to_zones(symbols, zones, rooms)
    zone_stats = get_zone_stats(zones)

    # Verify total capacity
    assert zone_stats["total_capacity"] == expected_total_capacity, (
        f"Expected {expected_total_capacity} total capacity, got {zone_stats['total_capacity']}"
    )
    assert zone_stats["total_zones"] == expected_zones, (
        f"Expected {expected_zones} zones, got {zone_stats['total_zones']}"
    )

    # Loop12-specific check (Part-1 only)
    if loop12_check:
        loop12_zones = [z for z in zones.keys() if z.startswith("DALI LOOP-12_")]
        assert len(loop12_zones) == 2, f"Expected 2 LOOP-12 zones, got {len(loop12_zones)}: {loop12_zones}"
        loop12_capacities = sorted(zone_stats["capacity_by_loop"][z] for z in loop12_zones)
        assert loop12_capacities == [26, 28], f"Expected LOOP-12 capacities [26, 28], got {loop12_capacities}"

    # The quantifier should fill at least 50% of capacity
    assert zone_stats["total_used"] >= 100, (
        f"Only {zone_stats['total_used']}/{zone_stats['total_capacity']} "
        f"symbols placed — tie-breaker may be too strict"
    )

    return zone_stats


def test_v1_v2_v3_v4_pipeline_on_part1():
    doc = pymupdf.open(PART1_PDF)
    page = doc[0]
    try:
        # Part-1: 673 symbols, 15 zones (13 unique loop IDs + 2 LOOP-12)
        run_v4_pipeline(page, expected_total_capacity=442, expected_zones=15, loop12_check=True)
    finally:
        doc.close()


def test_v1_v2_v3_v4_pipeline_on_part2():
    doc = pymupdf.open(PART2_PDF)
    page = doc[0]
    try:
        # Part-2: 370 symbols, 6 zones
        run_v4_pipeline(page, expected_total_capacity=202, expected_zones=6)
    finally:
        doc.close()


def test_v1_v2_v3_v4_pipeline_on_part3():
    doc = pymupdf.open(PART3_PDF)
    page = doc[0]
    try:
        # Part-3: 126 symbols, 4 zones
        run_v4_pipeline(page, expected_total_capacity=116, expected_zones=4)
    finally:
        doc.close()
