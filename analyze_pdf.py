import pymupdf

pdf_path = 'data/samples/P0050-AMC-A-E2-2F-EL-122-02-B, Lighting Layout, 2nd Floor, Part-1.pdf'
doc = pymupdf.open(pdf_path)
page = doc[0]

# Get all drawings/vector content
drawings = page.get_drawings()
print(f'Number of drawings: {len(drawings)}')

# Check for annotations
annots = list(page.annots())
if annots:
    print(f'Annotations: {len(annots)}')
    for a in annots:
        print(f'  {a.type}: {a.info}')

# Analyze drawing types
drawing_types = {}
for d in drawings:
    # d is a dict with keys like 'items', 'color', 'width', 'fill', etc.
    items = d.get('items', [])
    for item in items:
        cmd = item[0] if item else 'unknown'
        drawing_types[cmd] = drawing_types.get(cmd, 0) + 1

print('\nDrawing commands:')
for k, v in sorted(drawing_types.items(), key=lambda x: -x[1]):
    print(f'  {k}: {v}')

# Look for small shapes that could be light fixtures (circles, rects)
# Check for "re" (rectangle) or "c" (circle) or similar
small_shapes = []
for d in drawings:
    items = d.get('items', [])
    for item in items:
        if item[0] in ('re', 'c', 'm', 'l'):
            # Check bbox size
            rect = d.get('rect')
            if rect:
                w = rect.x1 - rect.x0
                h = rect.y1 - rect.y0
                if w < 50 and h < 50:  # small shapes
                    small_shapes.append((item[0], w, h, rect.x0, rect.y0))

print(f'\nSmall shapes (<50x50): {len(small_shapes)}')
# Group by size
from collections import Counter
size_counter = Counter((round(w), round(h)) for _, w, h, _, _ in small_shapes)
for (w, h), count in size_counter.most_common(20):
    print(f'  {w}x{h}: {count}')

doc.close()