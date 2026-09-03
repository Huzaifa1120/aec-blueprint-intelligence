from app.services.lighting.text_clustering import extract_dali_loops, debug_print_loops
import pymupdf

doc = pymupdf.open('G:/AEC-software/data/samples/P0050-AMC-A-E2-2F-EL-122-02-B, Lighting Layout, 2nd Floor, Part-1.pdf')
page = doc[0]
loops, discrepancies = extract_dali_loops(page)
debug_print_loops(loops, discrepancies)
doc.close()