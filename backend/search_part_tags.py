import pymupdf
import re

PANEL_PATTERN = re.compile(
    r'LCP-L2\s*/(\d+),\s*PART-(\d+)\s*\((\d+)Nos?\.?\)',
    re.IGNORECASE
)

doc = pymupdf.open('G:/AEC-software/data/samples/P0050-AMC-A-E2-2F-EL-122-02-B, Lighting Layout, 2nd Floor, Part-1.pdf')
page = doc[0]

# Get all spans
blocks = page.get_text('dict')['blocks']
all_spans = []
for b in blocks:
    if 'lines' in b:
        for l in b['lines']:
            for s in l['spans']:
                text = s['text'].strip()
                if text:
                    all_spans.append({
                        'text': text,
                        'x': s['bbox'][0],
                        'y': s['bbox'][1],
                    })

# Search for PART tags in all spans
print("=== All PART tags ===")
for s in all_spans:
    if 'PART' in s['text'].upper():
        print(f"  [{s['x']:.1f}, {s['y']:.1f}] '{s['text']}'")

# Search for capacity patterns (XXNos.)
print("\n=== All capacity patterns (XXNos.) ===")
for s in all_spans:
    if 'NOS' in s['text'].upper() or 'Nos' in s['text']:
        print(f"  [{s['x']:.1f}, {s['y']:.1f}] '{s['text']}'")

# Search for LCP-L2 in all spans
print("\n=== All LCP-L2 ===")
for s in all_spans:
    if 'LCP' in s['text'].upper():
        print(f"  [{s['x']:.1f}, {s['y']:.1f}] '{s['text']}'")

# Search for the full panel pattern in concatenated lines
# Cluster by Y with larger tolerance
from app.services.lighting.text_clustering import cluster_text_lines, extract_text_spans, FLOOR_PLAN_X_MAX

all_spans_typed = extract_text_spans(page)
clusters = cluster_text_lines(all_spans_typed, tol=10.0)  # Larger tolerance

print("\n=== Clusters with PANEL_PATTERN match (tol=10) ===")
for i, cluster in enumerate(clusters):
    if cluster:
        cluster.sort(key=lambda s: s['x'])
        line_text = ' '.join(s['text'] for s in cluster)
        match = PANEL_PATTERN.search(line_text)
        if match:
            avg_y = sum(s['y'] for s in cluster) / len(cluster)
            print(f"  Cluster #{i} (avg_y={avg_y:.1f}): '{line_text}'")
            print(f"    Match: panel={match.group(1)}, part={match.group(2)}, qty={match.group(3)}")

doc.close()