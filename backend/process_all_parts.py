import pymupdf
import json

def process_part(part_name, pdf_path):
    """Process a single part through the full extraction pipeline."""
    doc = pymupdf.open(pdf_path)
    page = doc[0]
    
    # Full-page TEXTFLAGS_RAW extraction
    text = page.get_text('text', flags=4)
    
    # Save raw text
    with open(f'data/debug/{part_name}_raw_fulltext.txt', 'w', encoding='utf-8') as f:
        f.write(text)
    
    print(f"{part_name}: {len(text)} chars")
    
    # Search for LOOP patterns
    import re
    for match in re.finditer(r'DALI\s*LOOP-\d+', text):
        start = max(0, match.start()-80)
        end = min(len(text), match.end()+80)
        print(f"  {match.group()}: ...{text[start:end]}...")
    
    doc.close()
    return text

# Process all three parts
parts = [
    ("Part-1", "G:/AEC-software/data/samples/P0050-AMC-A-E2-2F-EL-122-02-B, Lighting Layout, 2nd Floor, Part-1.pdf"),
    ("Part-2", "G:/AEC-software/data/samples/P0050-AMC-A-E2-2F-EL-123-03-B, Lighting Layout, 2nd Floor, Part-2.pdf"),
    ("Part-3", "G:/AEC-software/data/samples/P0050-AMC-A-E2-2F-EL-123-04-B, Lighting Layout, 2nd Floor, Part-3.pdf"),
]

for part_name, pdf_path in parts:
    print(f"\n{'='*80}")
    print(f"PROCESSING: {part_name}")
    print(f"{'='*80}")
    process_part(part_name, pdf_path)