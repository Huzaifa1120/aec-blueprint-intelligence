import json
import math
from typing import List, Dict, Tuple
import pymupdf

from .types import (
    DALILoop, FixtureInstance, LoopReconciliation, ReconciliationReport,
    EMERGENCY_CLASSES, Marker
)
from .text_clustering import extract_dali_loops, save_loops_json
from .spatial_association import (
    extract_all_candidate_symbols, extract_markers, 
    associate_markers_to_symbols
)


# Confidence threshold for quantity mismatch flag (5% as specified)
QUANTITY_MISMATCH_THRESHOLD = 0.05
LOW_COVERAGE_THRESHOLD = 0.80


def compute_emergency_ratios(instances: List[FixtureInstance]) -> Dict[str, float]:
    """Compute emergency class ratios from spatial data."""
    total = len(instances)
    if total == 0:
        return {cls: 0.0 for cls in EMERGENCY_CLASSES}
    
    counts = {cls: 0 for cls in EMERGENCY_CLASSES}
    for inst in instances:
        counts[inst['emergency_class']] += 1
    
    return {cls: counts[cls] / total for cls in EMERGENCY_CLASSES}


def deduplicate_loops(loops: List[DALILoop]) -> Tuple[List[DALILoop], List[Dict]]:
    """
    Merge duplicate loops that are SPATIALLY CLOSE (same panel, part, loop AND 
    centroids within SPATIAL_TOL). Spatially distinct zones sharing the same 
    loop_id (e.g., two LOOP-12 zones at different locations) are preserved as 
    separate zones — this is a drawing labeling error, not a text-extraction 
    duplicate.
    
    Returns (unique_loops, duplicate_info) where duplicate_info tracks merged entries.
    """
    SPATIAL_TOL = 50.0  # points - zones closer than this are text-extraction duplicates
    
    # Group by (panel, part, loop) first
    grouped: Dict[tuple, List[DALILoop]] = {}
    for loop in loops:
        key = (loop['panel'], loop['part'], loop['loop'])
        if key not in grouped:
            grouped[key] = []
        grouped[key].append(loop)
    
    unique = []
    duplicate_info = []
    
    for key, entries in grouped.items():
        if len(entries) == 1:
            unique.append(entries[0])
        else:
            # Multiple entries with same loop_id - deduplicate SPATIALLY
            # Only merge entries whose centroids are within SPATIAL_TOL
            sorted_entries = sorted(entries, key=lambda e: (e['source_x'], e['source_y']))
            
            zones_for_loop = []
            for entry in sorted_entries:
                matched_zone = None
                for zone in zones_for_loop:
                    dx = abs(entry['source_x'] - zone['source_x'])
                    dy = abs(entry['source_y'] - zone['source_y'])
                    if dx <= SPATIAL_TOL and dy <= SPATIAL_TOL:
                        matched_zone = zone
                        break
                
                if matched_zone:
                    # Same location - text-extraction duplicate, keep higher quantity
                    if entry['quantity'] > matched_zone['quantity']:
                        matched_zone.update({
                            'quantity': entry['quantity'],
                            'line_cluster_id': entry['line_cluster_id'],
                        })
                else:
                    zones_for_loop.append(entry)
            
            # Add all spatially distinct zones for this loop_id
            unique.extend(zones_for_loop)
            
            # Flag if this loop_id had multiple SPATIALLY DISTINCT zones (drawing discrepancy)
            if len(zones_for_loop) > 1:
                details = "; ".join(
                    f"at ({z['source_x']:.1f}, {z['source_y']:.1f}) qty={z['quantity']}"
                    for z in zones_for_loop
                )
                duplicate_info.append({
                    'type': 'DRAWING_DISCREPANCY',
                    'loop_id': key[2],
                    'message': f"Loop ID '{key[2]}' appears in {len(zones_for_loop)} spatially distinct zones: {details}",
                    'zones': zones_for_loop
                })
            # If multiple entries merged into one zone, flag as text-extraction duplicate
            elif len(zones_for_loop) < len(entries):
                merged_quantities = [e['quantity'] for e in entries]
                chosen_qty = max(merged_quantities)
                duplicate_info.append({
                    'type': 'TEXT_DUPLICATE_MERGED',
                    'panel': key[0],
                    'part': key[1],
                    'loop': key[2],
                    'quantities': merged_quantities,
                    'chosen_quantity': chosen_qty,
                    'clusters': [e['line_cluster_id'] for e in entries]
                })
    
    # Sort by loop number
    def loop_num_key(loop_str: str) -> int:
        digits = ''.join(filter(str.isdigit, loop_str))
        return int(digits) if digits else 0
    
    unique.sort(key=lambda x: (x['panel'], loop_num_key(x['loop'])))
    
    return unique, duplicate_info


def apply_ratios_to_loops(loops: List[DALILoop], ratios: Dict[str, float]) -> List[LoopReconciliation]:
    """
    Apply emergency split ratios to each DALI loop's text quantity.
    Uses largest remainder method to preserve global totals.
    """
    text_total = sum(loop['quantity'] for loop in loops)
    
    # Global target counts
    global_targets = {}
    for cls in EMERGENCY_CLASSES:
        global_targets[cls] = round(text_total * ratios.get(cls, 0))
    
    # Adjust to match text_total exactly
    allocated = sum(global_targets.values())
    diff = text_total - allocated
    if diff != 0:
        largest_cls = max(global_targets, key=global_targets.get)
        global_targets[largest_cls] += diff
    
    # Distribute to loops using largest remainder method
    loop_allocations = {loop['loop']: {cls: 0 for cls in EMERGENCY_CLASSES} for loop in loops}
    
    for cls in EMERGENCY_CLASSES:
        target = global_targets[cls]
        if target <= 0:
            continue
        
        exact_allocs = []
        for loop in loops:
            exact = loop['quantity'] * ratios.get(cls, 0)
            base = int(math.floor(exact))
            remainder = exact - base
            exact_allocs.append((loop['loop'], base, remainder))
            loop_allocations[loop['loop']][cls] = base
        
        allocated_cls = sum(a[1] for a in exact_allocs)
        remaining = target - allocated_cls
        
        exact_allocs.sort(key=lambda x: x[2], reverse=True)
        for i in range(min(remaining, len(exact_allocs))):
            loop_name = exact_allocs[i][0]
            loop_allocations[loop_name][cls] += 1
    
    # Build results
    results = []
    for loop in loops:
        alloc = loop_allocations[loop['loop']]
        cb = alloc.get('CB', 0)
        em = alloc.get('EM', 0)
        emem = alloc.get('EMEM', 0)
        normal = alloc.get('NORMAL', 0)
        
        spatial_count = cb + em + emem + normal
        delta = loop['quantity'] - spatial_count
        confidence = 1.0 - min(1.0, abs(delta) / max(1, loop['quantity']))
        
        results.append(LoopReconciliation(
            loop=loop['loop'],
            text_quantity=loop['quantity'],
            spatial_count=spatial_count,
            cb_count=cb,
            em_count=em,
            emem_count=emem,
            normal_count=normal,
            delta=delta,
            confidence=confidence
        ))
    
    return results


def generate_reconciliation_report(
    part_name: str,
    original_loops: List[DALILoop],
    unique_loops: List[DALILoop],
    duplicate_info: List[Dict],
    instances: List[FixtureInstance],
    loop_reconciliations: List[LoopReconciliation]
) -> ReconciliationReport:
    """Generate the full reconciliation report."""
    
    text_total = sum(loop['quantity'] for loop in unique_loops)
    spatial_total = sum(lr['spatial_count'] for lr in loop_reconciliations)
    
    totals = {
        'CB': sum(lr['cb_count'] for lr in loop_reconciliations),
        'EM': sum(lr['em_count'] for lr in loop_reconciliations),
        'EMEM': sum(lr['emem_count'] for lr in loop_reconciliations),
        'NORMAL': sum(lr['normal_count'] for lr in loop_reconciliations),
        'TEXT_TOTAL': text_total,
        'SPATIAL_TOTAL': spatial_total
    }
    
    confidences = [lr['confidence'] for lr in loop_reconciliations]
    confidence_summary = {
        'min': min(confidences) if confidences else 1.0,
        'max': max(confidences) if confidences else 1.0,
        'avg': sum(confidences) / len(confidences) if confidences else 1.0
    }
    
    flags = []
    
    for lr in loop_reconciliations:
        if abs(lr['delta']) / max(1, lr['text_quantity']) > QUANTITY_MISMATCH_THRESHOLD:
            flags.append("QUANTITY_MISMATCH: %s delta=%d (%.1f%%)" % (
                lr['loop'], lr['delta'], 100*abs(lr['delta'])/lr['text_quantity']))
    
    marked_fixtures = sum(1 for i in instances if i['emergency_class'] != 'NORMAL')
    marker_coverage = marked_fixtures / len(instances) if instances else 1.0
    if marker_coverage < LOW_COVERAGE_THRESHOLD:
        flags.append("LOW_MARKER_COVERAGE: %.1f%%" % (100*marker_coverage))
    
    for dup in duplicate_info:
        flags.append("DUPLICATE_LOOP_MERGED: %s %s %s quantities=%s chosen=%d" % (
            dup['panel'], dup['part'], dup['loop'], dup['quantities'], dup['chosen_quantity']))
    
    total_delta = text_total - spatial_total
    if abs(total_delta) / max(1, text_total) > QUANTITY_MISMATCH_THRESHOLD:
        flags.append("TOTAL_QUANTITY_MISMATCH: text=%d, spatial=%d, delta=%d" % 
                     (text_total, spatial_total, total_delta))
    
    return ReconciliationReport(
        part=part_name,
        loops=loop_reconciliations,
        totals=totals,
        confidence_summary=confidence_summary,
        flags=flags
    )


def create_debug_overlay(
    page: pymupdf.Page,
    loops: List[DALILoop],
    instances: List[FixtureInstance],
    markers: List[Marker],
    output_path: str
) -> bytes:
    """Create a debug PDF overlay."""
    doc = pymupdf.open()
    new_page = doc.new_page(width=page.rect.width, height=page.rect.height)
    
    # Draw original page content
    new_page.show_pdf_page(new_page.rect, page.parent, page.number)
    
    class_colors = {
        'CB': (1.0, 0.0, 0.0),
        'EM': (1.0, 0.5, 0.0),
        'EMEM': (1.0, 0.0, 1.0),
        'NORMAL': (0.0, 1.0, 0.0),
        'marker_only': (0.5, 0.5, 0.5)
    }
    
    # Draw fixture symbols
    for inst in instances:
        x0, y0, x1, y1 = inst['bbox']
        cx, cy = inst['centroid']
        color = class_colors.get(inst['emergency_class'], (0, 0, 0))
        
        rect = pymupdf.Rect(x0, y0, x1, y1)
        new_page.draw_rect(rect, color=color, width=1.5)
        
        new_page.draw_line((cx - 5, cy), (cx + 5, cy), color=color, width=1)
        new_page.draw_line((cx, cy - 5), (cx, cy + 5), color=color, width=1)
        
        label = "%s (%.2f)" % (inst['emergency_class'], inst['confidence'])
        new_page.insert_text((cx + 8, cy - 8), label, fontsize=6, color=color)
    
    # Draw markers
    for m in markers:
        mx, my = m['position']
        color = class_colors.get(m['label'], (0, 0, 0))
        new_page.draw_circle((mx, my), 4, color=color, width=2)
        new_page.insert_text((mx + 6, my - 6), "M:%s" % m['label'], fontsize=6, color=color)
    
    # Legend
    legend_y = 30
    new_page.insert_text((30, legend_y), "DEBUG OVERLAY LEGEND", fontsize=10, color=(0, 0, 0))
    legend_y += 15
    for cls, color in class_colors.items():
        new_page.draw_rect(pymupdf.Rect(30, legend_y, 45, legend_y + 10), color=color, fill=color)
        new_page.insert_text((50, legend_y + 8), cls, fontsize=8, color=(0, 0, 0))
        legend_y += 15
    
    pdf_bytes = doc.tobytes()
    doc.close()
    
    with open(output_path, 'wb') as f:
        f.write(pdf_bytes)
    
    return pdf_bytes


def process_lighting_pdf(pdf_path: str, part_name: str, output_dir: str = "data/debug") -> ReconciliationReport:
    """Main pipeline entry point."""
    doc = pymupdf.open(pdf_path)
    page = doc[0]
    
    # Step 1: Extract DALI loops (ground truth quantities)
    original_loops, _ = extract_dali_loops(page)
    save_loops_json(original_loops, "%s/%s_loops.json" % (output_dir, part_name))
    
    # Step 1b: Deduplicate loops for ratio application
    unique_loops, duplicate_info = deduplicate_loops(original_loops)
    
    # Step 2: Extract symbols and markers, associate
    symbols = extract_all_candidate_symbols(page)
    markers = extract_markers(page)
    instances = associate_markers_to_symbols(markers, symbols, max_radius=30.0)
    
    # Step 3: Compute emergency ratios from spatial data
    ratios = compute_emergency_ratios(instances)
    
    # Step 4: Apply ratios to UNIQUE loop quantities
    loop_reconciliations = apply_ratios_to_loops(unique_loops, ratios)
    
    # Step 5: Generate report
    report = generate_reconciliation_report(
        part_name, original_loops, unique_loops, duplicate_info,
        instances, loop_reconciliations
    )
    
    # Step 6: Create debug overlay
    create_debug_overlay(page, unique_loops, instances, markers, "%s/%s_overlay.pdf" % (output_dir, part_name))
    
    doc.close()
    return report


def save_report_json(report: ReconciliationReport, output_path: str) -> None:
    """Save reconciliation report to JSON."""
    def convert(obj):
        if isinstance(obj, dict):
            return {k: convert(v) for k, v in obj.items()}
        elif isinstance(obj, list):
            return [convert(v) for v in obj]
        elif hasattr(obj, '__dict__'):
            return convert(obj.__dict__)
        else:
            return obj
    
    with open(output_path, 'w') as f:
        json.dump(convert(report), f, indent=2)