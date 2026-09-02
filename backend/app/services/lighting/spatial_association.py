import math
from typing import List
import pymupdf

from .types import (
    FixtureSymbol, Marker, FixtureInstance,
    SYMBOL_SPECS, EMERGENCY_CLASSES
)
from .denoiser import DenoisedSymbol
from .room_mapper import RoomPolygon, assign_symbol_to_room


def colors_match(c1, c2, tol: float = 0.05) -> bool:
    if c1 is None or c2 is None:
        return False
    return all(abs(a - b) <= tol for a, b in zip(c1, c2))


def width_matches(w1, w2, tol: float = 0.1) -> bool:
    if w1 is None or w2 is None:
        return False
    return abs(w1 - w2) <= tol


def extract_all_candidate_symbols(page: pymupdf.Page) -> List[FixtureSymbol]:
    """
    Extract ALL candidate fixture-like symbols from drawing commands.
    Returns symbols with metadata for later filtering.
    """
    drawings = page.get_drawings()
    symbols = []
    
    for d in drawings:
        items = d.get('items', [])
        rect = d.get('rect')
        if not rect or not items:
            continue
        
        w = rect.x1 - rect.x0
        h = rect.y1 - rect.y0
        area = w * h
        aspect = w / h if h > 0 else 0
        
        if area < 30 or area > 500 or aspect < 0.4 or aspect > 2.5:
            continue
        
        cmds = tuple(item[0] for item in items)
        
        # Classify symbol type
        symbol_type = "unknown"
        for spec_name, spec in SYMBOL_SPECS.items():
            if cmds == spec['path_signature']:
                symbol_type = spec_name
                break
        
        cx = (rect.x0 + rect.x1) / 2
        cy = (rect.y0 + rect.y1) / 2
        symbols.append(FixtureSymbol(
            centroid=(cx, cy),
            bbox=(rect.x0, rect.y0, rect.x1, rect.y1),
            symbol_type=symbol_type,
            area=area,
            path_signature=cmds
        ))
    
    return symbols


def extract_markers(page: pymupdf.Page) -> List[Marker]:
    """Extract CB/EM/EMEM text markers from the page."""
    blocks = page.get_text('dict')['blocks']
    markers = []
    marker_id = 0
    
    for b in blocks:
        if 'lines' in b:
            for line in b['lines']:
                for s in line['spans']:
                    text = s['text'].strip()
                    if text in EMERGENCY_CLASSES[:3]:  # CB, EM, EMEM
                        x = s['bbox'][0]
                        y = s['bbox'][1]
                        markers.append(Marker(
                            label=text,
                            position=(x, y),
                            id=marker_id
                        ))
                        marker_id += 1
    
    return markers


def associate_markers_to_symbols(
    markers: List[Marker],
    symbols: List[FixtureSymbol],
    max_radius: float = 30.0
) -> List[FixtureInstance]:
    """
    Associate each marker to its nearest fixture symbol.
    
    Algorithm (marker-centric):
    1. For each marker, find nearest symbol within max_radius
    2. If found, create FixtureInstance with marker's emergency class
    3. If not found, create FixtureInstance at marker position (symbol-less)
    4. Symbols can only be assigned to ONE marker (first match wins)
    5. Unassigned symbols are ignored (not fixtures)
    """
    if not markers or not symbols:
        return []
    
    # Track which symbols are already assigned
    symbol_assigned = [False] * len(symbols)
    instances = []
    
    for m in markers:
        mx, my = m['position']
        best_idx = -1
        best_dist = float('inf')
        
        for i, sym in enumerate(symbols):
            if symbol_assigned[i]:
                continue
            sx, sy = sym['centroid']
            dist = math.hypot(sx - mx, sy - my)
            if dist < best_dist and dist <= max_radius:
                best_dist = dist
                best_idx = i
        
        if best_idx >= 0:
            # Found a symbol for this marker
            sym = symbols[best_idx]
            symbol_assigned[best_idx] = True
            centroid = sym['centroid']
            bbox = sym['bbox']
            symbol_type = sym['symbol_type']
            # Confidence based on distance
            confidence = max(0.5, 1.0 - (best_dist / max_radius))
        else:
            # No symbol found - create instance at marker position
            centroid = (mx, my)
            bbox = (mx - 5, my - 5, mx + 5, my + 5)
            symbol_type = "marker_only"
            best_dist = float('inf')
            confidence = 0.3  # Low confidence, no graphical symbol
        
        instances.append(FixtureInstance(
            centroid=centroid,
            bbox=bbox,
            symbol_type=symbol_type,
            emergency_class=m['label'],
            nearest_marker_dist=best_dist if best_idx >= 0 else float('inf'),
            marker_id=m['id'],
            loop_id="",  # Not assigning loops in this phase
            confidence=confidence
        ))
    
    # Report unassigned symbols (likely not fixtures)
    unassigned = sum(1 for a in symbol_assigned if not a)
    if unassigned > 0:
        print(f"Warning: {unassigned} symbols unassigned (likely non-fixture graphics)")
    
    return instances


def debug_print_association(instances: List[FixtureInstance], markers: List[Marker], symbols: List[FixtureSymbol]) -> None:
    """Print association statistics."""
    from collections import Counter
    
    class_counts = Counter(i['emergency_class'] for i in instances)
    print(f"Total fixtures (from markers): {len(instances)}")
    for cls in EMERGENCY_CLASSES:
        print(f"  {cls}: {class_counts.get(cls, 0)}")
    
    # Symbol assignment rate
    with_symbol = sum(1 for i in instances if i['symbol_type'] != 'marker_only')
    print(f"Fixtures with graphical symbol: {with_symbol}/{len(instances)} ({100*with_symbol/len(instances):.1f}%)")
    
    # Symbol type breakdown
    sym_types = Counter(i['symbol_type'] for i in instances if i['symbol_type'] != 'marker_only')
    for st, cnt in sym_types.most_common():
        print(f"  Symbol type {st}: {cnt}")
    
    # Distance stats
    dists = [i['nearest_marker_dist'] for i in instances if i['nearest_marker_dist'] != float('inf')]
    if dists:
        print(f"Marker-symbol distances: min={min(dists):.1f}, max={max(dists):.1f}, median={sorted(dists)[len(dists)//2]:.1f}")
    
    # Confidence stats
    confs = [i['confidence'] for i in instances]
    print(f"Confidence: min={min(confs):.2f}, max={max(confs):.2f}, avg={sum(confs)/len(confs):.2f}")
    
    # Total candidate symbols
    print(f"Total candidate symbols examined: {len(symbols)}")


def enrich_denoised_symbols(
    symbols: List[DenoisedSymbol],
    page: pymupdf.Page,
    rooms: List[RoomPolygon],
    max_marker_radius: float = 30.0,
) -> List[DenoisedSymbol]:
    """
    Enrich DenoisedSymbols with marker associations and room assignments.
    
    This is the V2 pipeline step that connects V1 symbols to V2 spatial data.
    Updates symbols in-place with:
      - has_marker: bool
      - marker_label: str (CB, EM, EMEM, or None)
      - assigned_room: str (room_id or None)
    
    Returns the same list for chaining.
    """
    # Extract markers from page
    markers = extract_markers(page)
    
    if not markers:
        # Still assign rooms even without markers
        for sym in symbols:
            room = assign_symbol_to_room(sym.centroid, rooms)
            if room:
                sym.assigned_room = room.room_id
        return symbols
    
    # Track which symbols get a marker
    symbol_assigned = [False] * len(symbols)
    
    # Associate each marker to nearest symbol (marker-centric, like associate_markers_to_symbols)
    for m in markers:
        mx, my = m['position']
        best_idx = -1
        best_dist = float('inf')
        
        for i, sym in enumerate(symbols):
            if symbol_assigned[i]:
                continue
            sx, sy = sym.centroid
            dist = math.hypot(sx - mx, sy - my)
            if dist < best_dist and dist <= max_marker_radius:
                best_dist = dist
                best_idx = i
        
        if best_idx >= 0:
            # Found a symbol for this marker
            sym = symbols[best_idx]
            symbol_assigned[best_idx] = True
            sym.has_marker = True
            sym.marker_label = m['label']
    
    # Assign rooms to ALL symbols (not just those with markers)
    for sym in symbols:
        room = assign_symbol_to_room(sym.centroid, rooms)
        if room:
            sym.assigned_room = room.room_id
    
    return symbols