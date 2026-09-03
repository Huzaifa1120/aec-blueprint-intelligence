import re
import json
from typing import List, Dict
import pymupdf

from .types import TextSpan, DALILoop, LINE_CLUSTER_TOL


PANEL_PATTERN = re.compile(
    r'LCP-L2\s*/(\d+),\s*PART-(\d+)\s*\((\d+)Nos?\.?\)',
    re.IGNORECASE
)
LOOP_PATTERN = re.compile(
    r'DALI\s*LOOP-(\d+)',
    re.IGNORECASE
)

# Spatial tolerance for considering two zones "at the same location"
SPATIAL_TOL = 50.0


def extract_text_spans(page: pymupdf.Page) -> List[TextSpan]:
    """Extract all text spans with position and formatting info.
    
    Uses TEXTFLAGS_RAW (flags=4) to capture text from hidden layers/OCGs
    and non-standard render modes that default extraction skips.
    """
    spans = []
    # Use flags=4 (TEXTFLAGS_RAW) to get complete text including hidden layers
    blocks = page.get_text('dict', flags=4)['blocks']
    for b in blocks:
        if 'lines' in b:
            for line in b['lines']:
                for s in line['spans']:
                    text = s['text'].strip()
                    if text:
                        spans.append(TextSpan(
                            text=text,
                            x=s['bbox'][0],
                            y=s['bbox'][1],
                            size=s['size'],
                            font=s['font']
                        ))
    return spans


def cluster_text_lines(spans: List[TextSpan], tol: float = LINE_CLUSTER_TOL, x_gap: float = 100.0) -> List[List[TextSpan]]:
    """
    Group text spans into visual lines by Y-coordinate.
    Spans within `tol` points vertically belong to the same line.
    Additionally, splits clusters if horizontal gap exceeds `x_gap` points.
    """
    if not spans:
        return []
    
    sorted_spans = sorted(spans, key=lambda s: (s['y'], s['x']))
    
    clusters = []
    current_cluster = [sorted_spans[0]]
    current_y = sorted_spans[0]['y']
    current_x_max = sorted_spans[0]['x']
    
    for span in sorted_spans[1:]:
        y_diff = abs(span['y'] - current_y)
        x_gap_from_cluster = span['x'] - current_x_max if span['x'] > current_x_max else 0
        
        # Same line if Y is close AND no large X gap
        if y_diff <= tol and x_gap_from_cluster <= x_gap:
            current_cluster.append(span)
            current_y = (current_y * (len(current_cluster) - 1) + span['y']) / len(current_cluster)
            current_x_max = max(current_x_max, span['x'])
        else:
            clusters.append(current_cluster)
            current_cluster = [span]
            current_y = span['y']
            current_x_max = span['x']
    
    clusters.append(current_cluster)
    return clusters


def _extract_raw_loop_candidates(spans: List[TextSpan]) -> List[Dict]:
    """
    Extract all raw loop candidates from text spans.
    Returns list of dicts with: loop_id, panel, part, quantity, centroid_x, centroid_y, cluster_id, raw_text
    """
    clusters = cluster_text_lines(spans)
    
    candidates = []
    for cluster_id, cluster in enumerate(clusters):
        # Concatenate all spans in cluster (sorted by X) to reconstruct fragmented text
        cluster.sort(key=lambda s: s['x'])
        line_text = ' '.join(s['text'] for s in cluster)
        
        panel_match = PANEL_PATTERN.search(line_text)
        loop_match = LOOP_PATTERN.search(line_text)
        
        if panel_match and loop_match:
            panel_num = panel_match.group(1)
            part_num = panel_match.group(2)
            quantity = int(panel_match.group(3))
            loop_num = loop_match.group(1)
            
            # Compute cluster centroid
            centroid_x = sum(s['x'] for s in cluster) / len(cluster)
            centroid_y = sum(s['y'] for s in cluster) / len(cluster)
            
            candidates.append({
                'loop_id': f"DALI LOOP-{loop_num}",
                'panel': f"LCP-L2/{panel_num}",
                'part': f"PART-{part_num}",
                'quantity': quantity,
                'centroid_x': centroid_x,
                'centroid_y': centroid_y,
                'cluster_id': cluster_id,
                'raw_text': line_text
            })
    
    return candidates


def _deduplicate_by_spatial_key(candidates: List[Dict]) -> tuple[List[DALILoop], List[Dict]]:
    """
    Deduplicate by spatial proximity WITHIN each loop_id group.
    Returns (unique_zones, discrepancy_flags).
    
    Process:
    1. Group candidates by loop_id
    2. Within each loop_id group, merge candidates that are spatially close (same location duplicates)
    3. Each resulting zone is a unique spatial location for that loop_id
    4. Flag DRAWING DISCREPANCY if a loop_id has zones at multiple spatial locations
    """
    if not candidates:
        return [], []
    
    discrepancies = []
    all_zones = []
    
    # Group candidates by loop_id
    from collections import defaultdict
    by_loop_id: Dict[str, List[Dict]] = defaultdict(list)
    for cand in candidates:
        by_loop_id[cand['loop_id']].append(cand)
    
    # For each loop_id, deduplicate spatially
    for loop_id, group in by_loop_id.items():
        if len(group) == 1:
            # Single candidate for this loop_id
            cand = group[0]
            all_zones.append({
                'loop_id': cand['loop_id'],
                'panel': cand['panel'],
                'part': cand['part'],
                'quantity': cand['quantity'],
                'centroid_x': cand['centroid_x'],
                'centroid_y': cand['centroid_y'],
                'cluster_id': cand['cluster_id'],
                'raw_text': cand['raw_text'],
            })
        else:
            # Multiple candidates with same loop_id - deduplicate spatially
            sorted_group = sorted(group, key=lambda c: (c['centroid_x'], c['centroid_y']))
            
            zones_for_loop = []
            for cand in sorted_group:
                matched_zone = None
                for zone in zones_for_loop:
                    dx = abs(cand['centroid_x'] - zone['centroid_x'])
                    dy = abs(cand['centroid_y'] - zone['centroid_y'])
                    if dx <= SPATIAL_TOL and dy <= SPATIAL_TOL:
                        matched_zone = zone
                        break
                
                if matched_zone:
                    # Same location - keep higher quantity
                    if cand['quantity'] > matched_zone['quantity']:
                        matched_zone.update({
                            'quantity': cand['quantity'],
                            'raw_text': cand['raw_text'],
                            'cluster_id': cand['cluster_id'],
                        })
                else:
                    zones_for_loop.append({
                        'loop_id': cand['loop_id'],
                        'panel': cand['panel'],
                        'part': cand['part'],
                        'quantity': cand['quantity'],
                        'centroid_x': cand['centroid_x'],
                        'centroid_y': cand['centroid_y'],
                        'cluster_id': cand['cluster_id'],
                        'raw_text': cand['raw_text'],
                    })
            
            # If this loop_id has multiple spatial zones, flag discrepancy
            if len(zones_for_loop) > 1:
                details = "; ".join(
                    f"at ({z['centroid_x']:.1f}, {z['centroid_y']:.1f}) qty={z['quantity']}"
                    for z in zones_for_loop
                )
                discrepancies.append({
                    'type': 'DRAWING_DISCREPANCY',
                    'loop_id': loop_id,
                    'message': f"Loop ID '{loop_id}' appears in {len(zones_for_loop)} spatially distinct zones: {details}",
                    'zones': zones_for_loop
                })
            
            all_zones.extend(zones_for_loop)
    
    # Convert to DALILoop format
    result = []
    for zone in all_zones:
        result.append(DALILoop(
            panel=zone['panel'],
            part=zone['part'],
            loop=zone['loop_id'],
            quantity=zone['quantity'],
            source_x=zone['centroid_x'],
            source_y=zone['centroid_y'],
            line_cluster_id=zone['cluster_id']
        ))
    
    return result, discrepancies


def extract_dali_loops(page: pymupdf.Page) -> tuple[List[DALILoop], List[Dict]]:
    """
    Full-page TEXTFLAGS_RAW extraction with spatial primary keys.
    
    1. Extract all text spans from full page (no X-filtering)
    2. Find all clusters containing PART-1 capacity tags + DALI LOOP labels
    3. Deduplicate by spatial centroid (not by loop ID string)
    4. Flag drawing discrepancies (same loop ID at different locations)
    
    Returns (unique_zones, discrepancy_list)
    """
    all_spans = extract_text_spans(page)
    
    # Extract all raw candidates with PART-1 tags
    candidates = _extract_raw_loop_candidates(all_spans)
    
    # Deduplicate by spatial key
    unique_zones, discrepancies = _deduplicate_by_spatial_key(candidates)
    
    return unique_zones, discrepancies


def save_loops_json(loops: List[DALILoop], output_path: str) -> None:
    """Save loops to JSON, converting TypedDict to regular dict."""
    serializable = []
    for loop in loops:
        d = dict(loop)
        d.pop('_duplicate_flag', None)
        d.pop('_duplicate_count', None)
        serializable.append(d)
    
    with open(output_path, 'w') as f:
        json.dump(serializable, f, indent=2)


def save_discrepancies_json(discrepancies: List[Dict], output_path: str) -> None:
    """Save discrepancy report to JSON."""
    with open(output_path, 'w') as f:
        json.dump(discrepancies, f, indent=2)


def debug_print_loops(loops: List[DALILoop], discrepancies: List[Dict] = None) -> None:
    """Pretty print loop extraction results."""
    print(f"Extracted {len(loops)} spatially distinct DALI loop zones:")
    for loop in loops:
        print(f"  {loop['panel']} {loop['part']} -> {loop['loop']}: {loop['quantity']} (centroid x={loop['source_x']:.1f}, y={loop['source_y']:.1f})")
    total = sum(loop['quantity'] for loop in loops)
    print(f"  TOTAL capacity: {total} fixtures")
    
    if discrepancies:
        print(f"\n  DRAWING DISCREPANCIES ({len(discrepancies)}):")
        for d in discrepancies:
            print(f"    [{d['type']}] {d['message']}")