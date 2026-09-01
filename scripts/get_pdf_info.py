import pymupdf
import os

files = [
    'ABC-SC03-S101.pdf',
    'ABC-SC05-S202.pdf',
    'Addendum3.pdf',
    'ex2-hwy-lighting-plan.pdf',
    'MMC-JVC-CD-ELEC-3902_AC-WIRE-Model.pdf',
    'P0050-AMC-A-E2-2F-EL-122-02-B, Lighting Layout, 2nd Floor, Part-1.pdf',
    'P0050-AMC-A-E2-2F-EL-123-03-B, Lighting Layout, 2nd Floor, Part-2.pdf',
    'P0050-AMC-A-E2-2F-EL-123-04-B, Lighting Layout, 2nd Floor, Part-3.pdf',
    'P0050-AMC-C-V2-GM-FA-115-01-R0(Fire Alarm System, MF)-GENERAL PLAN.pdf'
]

base = r'C:\Users\saada\Desktop\H-new\aec-blueprint-intelligence\data\samples'

for f in files:
    path = os.path.join(base, f)
    doc = pymupdf.open(path)
    page = doc[0]
    w, h = page.rect.width, page.rect.height
    print(f'{f} | pages={len(doc)} | size={w:.0f}x{h:.0f}pt')
    doc.close()