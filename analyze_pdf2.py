import pymupdf

pdf_path = 'data/samples/P0050-AMC-A-E2-2F-EL-122-02-B, Lighting Layout, 2nd Floor, Part-1.pdf'
doc = pymupdf.open(pdf_path)
page = doc[0]

# Get all text with positions - looking for fixture tags/callouts
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
                        'size': s['size'],
                        'font': s['font']
                    })

# Sort by Y then X
text_items.sort(key=lambda x: (x['y'], x['x']))

# Look for patterns like fixture tags (e.g., "A", "B", "Type A", etc.)
# and numbers that could be counts
print("=== All text items (size > 6) ===")
for t in text_items:
    if t['size'] > 6:
        print(f"  ({t['x']:.0f}, {t['y']:.0f}) size={t['size']:.1f} font={t['font']}: {t['text'][:100]}")

doc.close()