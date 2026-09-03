with open('data/debug/part1_raw_fulltext.txt', 'r', encoding='utf-8') as f:
    text = f.read()

import re
# Search for LOOP-04 and LOOP-09 more broadly
for pattern in ['LOOP-04', 'LOOP-09', 'LOOP 04', 'LOOP 09', 'LOOP-4', 'LOOP-9']:
    matches = list(re.finditer(re.escape(pattern), text, re.IGNORECASE))
    if matches:
        print(f'Found {len(matches)} matches for "{pattern}":')
        for m in matches[:3]:
            start = max(0, m.start()-100)
            end = min(len(text), m.end()+100)
            print(f'  ...{text[start:end]}...')
    else:
        print(f'No matches for "{pattern}"')
    print()

# Also search for DALI LOOP with any number to see all
print("=== All DALI LOOP patterns in raw text ===")
for match in re.finditer(r'DALI\s*LOOP[-\s]?\d+', text, re.IGNORECASE):
    start = max(0, match.start()-60)
    end = min(len(text), match.end()+60)
    print(f'  ...{text[start:end]}...')