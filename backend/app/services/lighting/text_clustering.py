import re
import json
from typing import List, Dict
import pymupdf

from .types import TextSpan, DALILoop, LINE_CLUSTER_TOL


PANEL_PATTERN = re.compile(
    r'LCP-L2\s*/(\d+),\s*PART-(\d+)\s*\((\d+)Nos\.\)',
    re.IGNORECASE
)
LOOP_PATTERN = re.compile(
    r'DALI\s*LOOP-(\d+)',
    re.IGNORECASE
)


def extract_text_spans(page: pymupdf.Page) -> List[TextSpan]:
    """Extract all text spans with position and formatting info."""
    spans = []
    blocks = page.get_text('dict')['blocks']
    for b in blocks:
        if 'lines' in b:
            for l in b['lines']:
                for s in l['spans']:
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


def cluster_text_lines(spans: List[TextSpan], tol: float = LINE_CLUSTER_TOL) -> List[List[TextSpan]]:
    """
    Group text spans into visual lines by Y-coordinate.
    Spans within `tol` points vertically belong to the same line.
    """
    if not spans:
        return []
    
    sorted_spans = sorted(spans, key=lambda s: (s['y'], s['x']))
    
    clusters = []
    current_cluster = [sorted_spans[0]]
    current_y = sorted_spans[0]['y']
    
    for span in sorted_spans[1:]:
        if abs(span['y'] - current_y) <= tol:
            current_cluster.append(span)
        else:
            clusters.append(current_cluster)
            current_cluster = [span]
            current_y = span['y']
    
    clusters.append(current_cluster)
    return clusters


def extract_dali_loops(page: pymupdf.Page) -> List[DALILoop]:
    """
    Extract DALI loop quantities from the lighting layout page.
    
    Algorithm:
    1. Extract all text spans
    2. Cluster into visual lines (Y tolerance 4pt)
    3. Per cluster: find panel label + loop label
    4. Pair them by X-order (panel left, loop right)
    5. Deduplicate: key = (panel, part, loop, cluster_id) to preserve
       visually distinct labels with same loop name but different quantities
    """
    spans = extract_text_spans(page)
    clusters = cluster_text_lines(spans)
    
    raw_pairs = []
    for cluster_id, cluster in enumerate(clusters):
        panel_match = None
        loop_match = None
        panel_span = None
        loop_span = None
        
        for span in cluster:
            if not panel_match:
                m = PANEL_PATTERN.search(span['text'])
                if m:
                    panel_match = m
                    panel_span = span
            if not loop_match:
                m = LOOP_PATTERN.search(span['text'])
                if m:
                    loop_match = m
                    loop_span = span
        
        if panel_match and loop_match:
            panel_num = panel_match.group(1)
            part_num = panel_match.group(2)
            quantity = int(panel_match.group(3))
            loop_num = loop_match.group(1)
            
            raw_pairs.append(DALILoop(
                panel=f"LCP-L2/{panel_num}",
                part=f"PART-{part_num}",
                loop=f"DALI LOOP-{loop_num}",
                quantity=quantity,
                source_y=panel_span['y'],
                line_cluster_id=cluster_id
            ))
    
    # Deduplicate: key includes cluster_id to preserve visually distinct labels
    # But flag conflicts where same (panel, part, loop) appears in multiple clusters
    seen: Dict[tuple, List[DALILoop]] = {}
    for entry in raw_pairs:
        key = (entry['panel'], entry['part'], entry['loop'])
        if key not in seen:
            seen[key] = []
        seen[key].append(entry)
    
    result = []
    for key, entries in seen.items():
        if len(entries) == 1:
            result.append(entries[0])
        else:
            # Multiple clusters for same loop - keep all but flag
            for e in entries:
                e['_duplicate_flag'] = True
                e['_duplicate_count'] = len(entries)
            result.extend(entries)
    
    # Sort by panel, then loop number
    def loop_num_key(loop_str: str) -> int:
        digits = ''.join(filter(str.isdigit, loop_str))
        return int(digits) if digits else 0
    
    result.sort(key=lambda x: (x['panel'], loop_num_key(x['loop']), x['line_cluster_id']))
    
    return result


def save_loops_json(loops: List[DALILoop], output_path: str) -> None:
    """Save loops to JSON, converting TypedDict to regular dict."""
    serializable = []
    for l in loops:
        d = dict(l)
        # Remove internal flags
        d.pop('_duplicate_flag', None)
        d.pop('_duplicate_count', None)
        serializable.append(d)
    
    with open(output_path, 'w') as f:
        json.dump(serializable, f, indent=2)


def debug_print_loops(loops: List[DALILoop]) -> None:
    """Pretty print loop extraction results."""
    print(f"Extracted {len(loops)} DALI loop entries:")
    for l in loops:
        flag = " [DUPLICATE]" if l.get('_duplicate_flag') else ""
        print(f"  {l['panel']} {l['part']} -> {l['loop']}: {l['quantity']} (cluster #{l['line_cluster_id']}, y={l['source_y']:.1f}){flag}")
    total = sum(l['quantity'] for l in loops)
    print(f"  TOTAL: {total} fixtures")