# Sample fixtures

Real drawing PDFs used as regression-test fixtures.

All PDFs in this folder are **gitignored** (`data/samples/*.pdf`) — client-supplied
material that stays local. Only this `README.md` is committed. If the folder is
empty on a fresh clone, obtain copies from the project owner.
The fixture `MMC-JVC-CD-ELEC-3902_AC-WIRE-Model.pdf` was restored 2026-08-22;
the full suite (63 tests) runs green with it present. All 5 PDFs verified
present locally 2026-08-23.

## Files

| File | Size | Pages | Sheet size | Content |
| ---- | ---- | ----- | ---------- | ------- |
| `MMC-JVC-CD-ELEC-3902_AC-WIRE-Model.pdf` | ~1.3 MB | 1 | A3 landscape (1191×842 pt) | Access-control electrical sheet |
| `ABC-SC03-S101.pdf` | ~253 KB | 1 | ARCH D (2592×1728 pt) | Structural sheet S101 — site/foundation plan **with mechanical equipment layers** (`M-EQPT-NEW`, `M-EQPT-FUTR`, xref `M-EQUIP`/`M-Clearances`) — closest thing to a Phase 3 fixture until a dedicated HVAC sheet arrives |
| `ABC-SC05-S202.pdf` | ~391 KB | 1 | ARCH D (2592×1728 pt) | Structural sheet S202 — section details |
| `Addendum3.pdf` | ~1.4 MB | 7 | Mixed: p0 letter portrait (612×792 pt); pp1–6 oversized landscape (3024×2160 pt) | Contract addendum: cover text page + 6 drawing-exhibit pages (7k–13k ops each, embedded images) — out-of-domain / non-takeoff upload test |
| `ex2-hwy-lighting-plan.pdf` | ~73 KB | 1 | Tabloid landscape (1224×792 pt) | Highway lighting plan |

## Details

- **`MMC-JVC-CD-ELEC-3902_AC-WIRE-Model.pdf`** — access-control electrical sheet,
  Jeddah VIP Clinic (basement 2, scale 1:100, AutoCAD export). Layer-rich vector
  (~88k drawing ops/page), text fully extractable, 46 OCG layers. This is the
  primary regression fixture gated by tests E1–E9 / Y1–Y5. Note: its `M_SAUDI_*`
  layers are the Saudi CAD architectural family (stairs, downpipe,
  `VENT_identy`) — *not* NCS mechanical discipline layers despite the `M_` prefix.
- **`ABC-SC03-S101.pdf`** — structural sheet "S101": site plan around a parallel
  gear / generator / cooling-tower yard with spot elevations. Layer-rich vector
  (~7.8k drawing ops/page), extractable text (~3.7k chars), one embedded image.
  45 OCG layers including direct mechanical equipment layers `M-EQPT-NEW` /
  `M-EQPT-FUTR` and xref-borne `X-ABC-SC03-SP|M-EQUIP` / `M-Clearances`, plus
  electrical xref layers (`E-1LNEQP-C`, `E-DEV`). Equipment-count takeoff on
  this sheet is a viable Phase 3 warm-up; duct/pipe route work still needs a
  real HVAC sheet.
- **`ABC-SC05-S202.pdf`** — structural sheet "S202": construction details (curb at
  end walls, 4" slab on grade w/ W.W.F., garage area-separation wall sections at
  3/4"=1'-0"). Very dense vector (~15.5k drawing ops/page), extractable text,
  one embedded image. 28 OCG layers; structural detail layers only (no mech).
- **`Addendum3.pdf`** — UT Health MSB Infill Renovation, Project No. 214-198,
  Addendum 03 dated 8-Mar-16. NOT purely a Word-exported text doc: page 0 is a
  letter-portrait text page, but pages 1–6 are oversized-landscape drawing
  exhibit pages (7k–13.5k vector ops each with embedded images, no OCGs).
  Useful as an out-of-domain upload test; not a takeoff source.
- **`ex2-hwy-lighting-plan.pdf`** — highway lighting plan example. Vector-only
  (~5.8k drawing ops, zero images, zero OCGs); almost no extractable text
  (6 chars — text appears outlined to curves) — exercises the no-text /
  legend-matching path.
