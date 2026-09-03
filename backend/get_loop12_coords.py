import pymupdf as fitz

doc = fitz.open('G:/AEC-software/data/samples/P0050-AMC-A-E2-2F-EL-122-02-B, Lighting Layout, 2nd Floor, Part-1.pdf')
page = doc[0]

# Get spans with flags=4
blocks = page.get_text('dict', flags=4)['blocks']
loop12_spans = []
for b in blocks:
    if 'lines' in b:
        for l in b['lines']:
            for s in l['spans']:
                text = s['text'].strip()
                if text and 'LOOP-12' in text and 'DALI' in text:
                    loop12_spans.append({
                        'text': text,
                        'x': s['bbox'][0],
                        'y': s['bbox'][1],
                        'x1': s['bbox'][2],
                        'y1': s['bbox'][3],
                    })

print("=== DALI LOOP-12 spans (with coordinates) ===")
for s in loop12_spans:
    print(f"  Text: '{s['text']}'")
    print(f"  BBox: [{s['x']:.1f}, {s['y']:.1f}, {s['x1']:.1f}, {s['y1']:.1f}]")
    print(f"  Origin: ({s['x']:.1f}, {s['y']:.1f})")
    print()

# Also find the associated panel labels
print("=== Associated panel labels (nearby spans) ===")
for b in blocks:
    if 'lines' in b:
        for l in b['lines']:
            for s in l['spans']:
                text = s['text'].strip()
                if text and 'LCP-L2' in text and 'PART-1' in text and 'Nos' in text:
                    # Check if near any LOOP-12
                    for loop in loop12_spans:
                        if abs(s['bbox'][1] - loop['y']) < 10:
                            print(f"  Near LOOP-12 at y={loop['y']:.1f}:")
                            print(f"    Panel: [{s['bbox'][0]:.1f}, {s['bbox'][1]:.1f}] '{text}'")

doc.close()