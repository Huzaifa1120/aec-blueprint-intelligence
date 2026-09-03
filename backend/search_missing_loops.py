import pymupdf
import re

doc = pymupdf.open('G:/AEC-software/data/samples/P0050-AMC-A-E2-2F-EL-122-02-B, Lighting Layout, 2nd Floor, Part-1.pdf')
page = doc[0]
plain_text = page.get_text('text')

print(f"Plain text length: {len(plain_text)}")

# Search for each missing loop in various formats
for loop in ['01', '02', '05', '06']:
    print(f'\n=== Searching for LOOP-{loop} ===')
    # Direct search
    if f'LOOP-{loop}' in plain_text:
        print(f'  Found "LOOP-{loop}" directly')
    if f'LOOP {loop}' in plain_text:
        print(f'  Found "LOOP {loop}" with space')
    if f'LOOP{loop}' in plain_text:
        print(f'  Found "LOOP{loop}" no separator')
    # Regex search
    for match in re.finditer(f'LOOP[^\\d]*{loop}', plain_text, re.IGNORECASE):
        start = max(0, match.start()-60)
        end = min(len(plain_text), match.end()+60)
        print(f'  Regex match: ...{plain_text[start:end]}...')
    # Check PART-1 with that loop
    for match in re.finditer(f'PART-1[^\\d]*\\({loop}', plain_text):
        start = max(0, match.start()-60)
        end = min(len(plain_text), match.end()+60)
        print(f'  PART-1 capacity {loop}: ...{plain_text[start:end]}...')

# Also search for "DALI LOOP" with any number
print('\n=== All DALI LOOP occurrences ===')
for match in re.finditer(r'DALI\s*LOOP[^\\d]*\d+', plain_text, re.IGNORECASE):
    start = max(0, match.start()-40)
    end = min(len(plain_text), match.end()+40)
    print(f'  {plain_text[start:end]}')

doc.close()