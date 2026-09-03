import pymupdf as fitz

doc = fitz.open('G:/AEC-software/data/samples/P0050-AMC-A-E2-2F-EL-122-02-B, Lighting Layout, 2nd Floor, Part-1.pdf')
page = doc[0]

print("=== 1. get_text('text') default ===")
text1 = page.get_text("text")
print(f"Length: {len(text1)}")

print("\n=== 2. get_text('text', flags=fitz.TEXTFLAGS_TEXT) ===")
try:
    text2 = page.get_text("text", flags=fitz.TEXTFLAGS_TEXT)
    print(f"Length: {len(text2)}")
except Exception as e:
    print(f"Error: {e}")

print("\n=== 3. get_text('text', flags=0) ===")
text3 = page.get_text("text", flags=0)
print(f"Length: {len(text3)}")

print("\n=== 4. get_text('text', flags=4) (TEXTFLAGS_RAW) ===")
try:
    text4 = page.get_text("text", flags=4)
    print(f"Length: {len(text4)}")
except Exception as e:
    print(f"Error: {e}")

print("\n=== 5. get_text('text', flags=8) ===")
text5 = page.get_text("text", flags=8)
print(f"Length: {len(text5)}")

print("\n=== 6. get_text('text', flags=12) ===")
try:
    text6 = page.get_text("text", flags=12)
    print(f"Length: {len(text6)}")
except Exception as e:
    print(f"Error: {e}")

print("\n=== 7. get_text('dict', flags=4) ===")
try:
    blocks = page.get_text("dict", flags=4)['blocks']
    span_count = 0
    loop_spans = []
    for b in blocks:
        if 'lines' in b:
            for l in b['lines']:
                for s in l['spans']:
                    text = s['text'].strip()
                    if text:
                        span_count += 1
                        if 'loop' in text.lower() and 'dali' in text.lower():
                            loop_spans.append((s['bbox'][0], s['bbox'][1], text))
    print(f"Total spans: {span_count}")
    print(f"DALI LOOP spans: {len(loop_spans)}")
    for x, y, text in loop_spans:
        print(f"  [{x:.1f}, {y:.1f}] '{text}'")
except Exception as e:
    print(f"Error: {e}")

print("\n=== 8. Check OCGs and try extraction with all layers ON ===")
ocgs = doc.get_ocgs()
print(f"Total OCGs: {len(ocgs)}")
if ocgs:
    # Try to set all OCGs to ON
    for ocg in ocgs:
        try:
            ocg.on = True
        except:
            pass
    # Now extract
    text_ocg = page.get_text("text")
    print(f"Length with OCGs forced ON: {len(text_ocg)}")
    for match in ['LOOP-01', 'LOOP-02', 'LOOP-05', 'LOOP-06']:
        if match in text_ocg:
            print(f"  FOUND: {match}")

print("\n=== 9. get_text('rawdict') ===")
try:
    raw = page.get_text("rawdict")
    print(f"Blocks: {len(raw['blocks'])}")
    for b in raw['blocks']:
        if b['type'] == 0:
            for l in b['lines']:
                for s in l['spans']:
                    text = s.get('text', '').strip()
                    if text and 'loop' in text.lower() and 'dali' in text.lower():
                        print(f"  [{s['bbox'][0]:.1f}, {s['bbox'][1]:.1f}] '{text}'")
except Exception as e:
    print(f"Error: {e}")

print("\n=== 10. get_text('blocks') ===")
try:
    blocks = page.get_text("blocks")
    for b in blocks:
        if b[6] == 0:  # text block
            text = b[4].strip()
            if 'LOOP' in text.upper() and 'DALI' in text.upper():
                print(f"  [{b[0]:.1f}, {b[1]:.1f}] '{text[:200]}'")
except Exception as e:
    print(f"Error: {e}")

print("\n=== 11. Check annotations ===")
annots = page.annots()
if annots:
    for annot in annots:
        if annot.info.get('content'):
            print(f"  Annotation: {annot.info['content']}")

print("\n=== 12. Check XObjects / Form XObjects ===")
xrefs = page.get_xobjects()
if xrefs:
    for xref in xrefs:
        print(f"  XObject: {xref}")

doc.close()