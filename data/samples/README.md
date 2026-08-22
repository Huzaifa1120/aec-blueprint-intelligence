# Sample fixtures

Real drawing PDFs used as regression-test fixtures.

All PDFs in this folder are **gitignored** (`data/samples/*.pdf`) — client-supplied
material that stays local. Only this `README.md` is committed. If the folder is
empty on a fresh clone, obtain copies from the project owner.
The fixture `MMC-JVC-CD-ELEC-3902_AC-WIRE-Model.pdf` was restored 2026-08-22;
the full suite (63 tests) runs green with it present.

## Files

| File | Size | Pages | Sheet size | Content |
| ---- | ---- | ----- | ---------- | ------- |
| `MMC-JVC-CD-ELEC-3902_AC-WIRE-Model.pdf` | ~1.3 MB | 1 | A3 landscape (1191×842 pt) | Access-control electrical sheet |
| `ABC-SC03-S101.pdf` | ~253 KB | 1 | ARCH D (2592×1728 pt) | Structural sheet S101 — site/foundation plan |
| `ABC-SC05-S202.pdf` | ~391 KB | 1 | ARCH D (2592×1728 pt) | Structural sheet S202 — section details |
| `Addendum3.pdf` | ~1.4 MB | 7 | Letter portrait (612×792 pt) | Contract addendum document (not a drawing) |
| `ex2-hwy-lighting-plan.pdf` | ~73 KB | 1 | Tabloid landscape (1224×792 pt) | Highway lighting plan |

## Details

- **`MMC-JVC-CD-ELEC-3902_AC-WIRE-Model.pdf`** — access-control electrical sheet,
  Jeddah VIP Clinic (basement 2, scale 1:100, AutoCAD export). Layer-rich vector
  (~88k drawing ops/page), text fully extractable. This is the primary regression
  fixture gated by tests E1–E9 / Y1–Y5.
- **`ABC-SC03-S101.pdf`** — structural sheet "S101": site plan around a parallel
  gear / generator / cooling-tower yard with spot elevations. Layer-rich vector
  (~7.8k drawing ops/page), extractable text, one embedded image.
- **`ABC-SC05-S202.pdf`** — structural sheet "S202": construction details (curb at
  end walls, 4" slab on grade w/ W.W.F., garage area-separation wall sections at
  3/4"=1'-0"). Very dense vector (~15.5k drawing ops/page), extractable text.
- **`Addendum3.pdf`** — UT Health MSB Infill Renovation, Project No. 214-198,
  Addendum 03 dated 8-Mar-16. Word-exported contract document (7 letter-size
  pages of spec/QA text) — useful as an out-of-domain / non-drawing upload test,
  not a takeoff source.
- **`ex2-hwy-lighting-plan.pdf`** — highway lighting plan example. Vector-only
  (~5.8k drawing ops, zero images); almost no extractable text (text appears
  outlined to curves) — exercises the no-text / legend-matching path.
