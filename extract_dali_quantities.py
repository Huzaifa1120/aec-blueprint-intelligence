import pymupdf
import re

pdfs = [
    ('Part-1', 'data/samples/P0050-AMC-A-E2-2F-EL-122-02-B, Lighting Layout, 2nd Floor, Part-1.pdf'),
    ('Part-2', 'data/samples/P0050-AMC-A-E2-2F-EL-123-03-B, Lighting Layout, 2nd Floor, Part-2.pdf'),
    ('Part-3', 'data/samples/P0050-AMC-A-E2-2F-EL-123-04-B, Lighting Layout, 2nd Floor, Part-3.pdf'),
]

# Pattern to match: "LCP-L2 /01, PART-1 (26Nos.)" and "DALI LOOP-9"
# These appear as separate text spans but on same Y coordinate
panel_pattern = re.compile(r'LCP-L2\s*/(\d+),\s*PART-(\d+)\s*\((\d+)Nos\.\)')
loop_pattern = re.compile(r'DALI\s*LOOP-(\d+)')

results = []

for part_name, pdf_path in pdfs:
    print(f'\n=== {part_name} ===')
    doc = pymupdf.open(pdf_path)
    page = doc[0]
    
    blocks = page.get_text('dict')['blocks']
    text_items = []
    for b in blocks:
        if 'lines' in b:
            for l in b['lines']:
                for s in l['spans']:
                    text = s['text'].strip()
                    if text:
                        text_items.append({
                            'text': text,
                            'x': s['bbox'][0],
                            'y': s['bbox'][1],
                            'size': s['size']
                        })
    
    # Find panel labels and loop labels
    panel_labels = [t for t in text_items if panel_pattern.search(t['text'])]
    loop_labels = [t for t in text_items if loop_pattern.search(t['text'])]
    
    # Match them by Y coordinate (they're on same line)
    for pl in panel_labels:
        m = panel_pattern.search(pl['text'])
        if m:
            panel_num = m.group(1)
            part_num = m.group(2)
            qty = int(m.group(3))
            
            # Find matching loop label (closest Y)
            best_loop = None
            best_dist = float('inf')
            for ll in loop_labels:
                m2 = loop_pattern.search(ll['text'])
                if m2:
                    dist = abs(ll['y'] - pl['y'])
                    if dist < best_dist:
                        best_dist = dist
                        best_loop = m2.group(1)
            
            loop_num = best_loop if best_loop else '?'
            print(f'  Panel LCP-L2/{panel_num} Part-{part_num} -> DALI LOOP-{loop_num}: {qty} fixtures')
            results.append({
                'part': part_name,
                'panel': f'LCP-L2/{panel_num}',
                'loop': f'DALI LOOP-{loop_num}',
                'quantity': qty
            })
    
    doc.close()

# Summary
print('\n=== SUMMARY ===')
total = 0
for r in results:
    print(f"  {r['part']}: {r['panel']} {r['loop']} = {r['quantity']}")
    total += r['quantity']
print(f'\nTotal fixtures across all parts: {total}')

# By part
print('\n=== BY PART ===')
for part_name in ['Part-1', 'Part-2', 'Part-3']:
    part_total = sum(r['quantity'] for r in results if r['part'] == part_name)
    print(f'  {part_name}: {part_total} fixtures')