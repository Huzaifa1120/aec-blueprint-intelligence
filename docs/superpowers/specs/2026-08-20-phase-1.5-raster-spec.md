# Phase 1.5 — Raster/CV Fallback Specifications

**Version:** 1.0.0 (next phase after Phase 1 MVP proven)  
**Based on:** `Phases.md` §1.5, `Rules.md` §5, `trap.md`, `AGENTS.md`, `Architecture.md`  
**Trigger:** Phase 1 MVP Definition of Done met (access control takeoff on vector PDF)  
**Note:** Raster fallback is **Phase 1.5, not required for MVP** — do not start until Phase 1 DoD is met.

---

## 1. Overview

Phase 1.5 implements the **raster/CV fallback** for scanned PDFs, photos, and images — the secondary ingestion path when vector PDF parsing is not possible. This is the "preferred fallback" per `Architecture.md` §3.3, fed after the vector-first path (Phase 1).

**Architecture:** Hybrid, vector-first, rules-driven, human-verified.  
**Primary data source:** Raster image rendered from PDF page → OCR (PaddleOCR) + YOLOv8 shape clustering (few-shot, per-document legend).  
**Confidence model:** Per-line `MEASURED` / `DERIVED` / `ASSUMED` — with **lower base confidence** for raster-derived measurements.  
**Critical constraint:** Raster measurements always have lower base confidence than vector-derived (Rules.md §7.4).

---

## 2. File Structure (Phase 1.5 Additions)

```
backend/
├── app/
│   ├── raster/              # NEW — Phase 1.5 raster/CV fallback
│   │   ├── router.py         # PDF → vector/raster decision (extended from Phase 1)
│   │   ├── renderer.py       # PyMuPDF pixmap rendering at high DPI
│   │   ├── ocr.py           # PaddleOCR primary, Tesseract fallback
│   │   └── legend.py         # Per-document legend few-shot matching
│   ├── parsing/             # Extended
│   │   └── confidence_tiering.py  ← already created in Phase 1
│   └── main.py              # + new raster routers
├── data/
│   └── samples/             # Sample fixture (already present)
└── frontend/
    └── src/app/
        └── components/
            └── ReviewOverlay/     ← already created in Phase 1
          # No new UI needed for Phase 1.5 MVP; existing overlay handles raster confidence display

docs/
└── Phase-1.5-MVP-Specs.md   ← this file (just to be created)

---

## 3. API Surface (v1 — Phase 1.5 additions)

| Method | Endpoint | Description |
|---|---|---|
| `POST` | `/api/v1/raster/classify` | Upload scanned PDF/image → vector/raster decision |
| `POST` | `/api/v1/raster/parse` | Raster PDF/image → OCR + legend detection + component extraction |
| `GET` | `/api/v1/drawings/{id}/model` | Canonical drawing model (same as Phase 1 — includes raster items with lower confidence) |

*Note: Existing Phase 1 endpoints remain: `POST /api/v1/ingestion/pdf`, `/review/accept`, etc.*

---

## 4. Core Implementation Tasks

### Task 1 — PDF Raster Rendering at High DPI
**File:** `backend/app/raster/renderer.py`  
**Function:** `render_page_to_pixmap(pdf_path, page_num, dpi=300) → np.ndarray`
- Render PDF page to high-DPI image using PyMuPDF pixmap
- Minimum 300 DPI for OCR accuracy; 600 DPI preferred for detail
- Output: RGB or RGBA image array (numpy)
- Integration: Called when upload classification returns "raster"
- Trap constraints:
  - ✅ `import pymupdf`, never `fitz`
  - ✅ Raster images are lower confidence than vector
  - ✅ No universal symbol detection — per-document legend first

### Task 2 — OCR Integration (PaddleOCR / Tesseract)
**File:** `backend/app/raster/ocr.py`  
**Core functions:**
- `ocr_paddle(image) → list[dict]`: Primary OCR — returns text strings with bbox + confidence
- `ocr_tesseract(image) → list[dict]`: Lightweight fallback
- `detect_legend_text(image) → dict`: Extract legend table from raster image
- Output format: `[{"text": "card reader", "bbox": (x0, y0, x1, y1), "confidence": 0.92}, ...]`
- Integration: Feeds into legend detection and dimension extraction
- Trap constraints:
  - ✅ OCR results are **proposals only**, not final quantities
  - ✅ Raster-derived text has lower base confidence
  - ✅ Never output final dimension/measurement from OCR alone
  - ✅ PaddleOCR imported; Tesseract as fallback only

### Task 3 — Per-Document Legend Few-Shot Matching
**File:** `backend/app/raster/legend.py`  
**Critical trap constraint: ❌ DO NOT build universal cross-company symbol detector**  
**Strategy:**
- Step 1: Extract legend table from the specific document (OCR on raster or vector text)
- Step 2: Build symbol glyph → description mapping from the sheet's own legend
- Step 3: When CV detects a symbol, match against legend first
- Step 4: Only if legend matching fails, use fallback (pretrained model not built in Phase 1.5)
- Output: `{"symbol": "card_reader", "method": "legend_match", "confidence": 0.85}`
- Trap constraints — MUST observe:
  - ✅ Per-document legend matching first, always
  - ✅ No universal symbol detector (AGENTS.md §non-negotiable rule ❌)
  - ✅ Legend is specific to each document sheet
  - ✅ Fallback to "unknown" if legend doesn't match — never guess

### Task 4 — YOLOv8 Shape-Cluster Detection (Raster-Only Path)
**File:** `backend/app/raster/yolo_detection.py` (NEW — requires ultralytics installed)  
**Critical trap constraint: ⚠️ YOLOv8 belongs ONLY in raster fallback (Phase 1.5), NOT v1 vector path**  
**Strategy:**
- Use Ultralytics YOLOv8 for shape clustering in raster path only
- NOT a universal symbol detector — only for few-shot legend matching
- Detect: generic shapes (rectangles, circles, etc.) that may correspond to symbols
- Match detected shapes against per-document legend first
- If legend match fails → mark as "unknown", do NOT assign a type from YOLO alone
- Trap constraints:
  - ✅ YOLOv8 only in Phase 1.5 raster path
  - ✅ Never in vector path (AGENTS.md Rules.md constraints)
  - ✅ Output proposals only — human/rule engine finalizes
  - ✅ YOLO model weights not hardcoded — loaded from config or pretrained
  - ✅ Class names not hardcoded — configurable per-document

### Task 5 — CubiCasa5K-Style Segmentation for Non-Legend Elements
**File:** `backend/app/raster/segmentation.py`  
**Strategy:**
- Use pretrained CubiCasa5K-style segmentation model (or Detectron2 fallback)
- ONLY for non-legend architectural elements: walls, rooms, spaces
- NOT for symbol classification (that's legend matching's job)
- Output: segmentation masks with lower base confidence tag
- Trap constraints:
  - ✅ Only for non-legend elements
  - ✅ Never for symbol classification
  - ✅ Segmentation masks tagged with lower confidence than vector
  - ✅ Not a universal detector — per-document scope

### Task 6 — Confidence Tiering for Raster Measurements
**Integration:** Extend `confidence_tiering.py` (already created in Phase 1) to handle raster
**New status logic:**
- `MEASURED` → vector geometry (score 1.0)
- `MEASURED_RASTER` → raster-derived, **auto-reduced score** (0.6 default)
- `DERIVED` → from assembly rules/formulas (score depends on rule version)
- `ASSUMED` → from defaults (score 0.3, forces review)
- **Display:** Show `MEASURED (raster)` or `MEASURED (vector)` with different colors
- Trap constraints — MUST observe:
  - ✅ Raster always lower confidence than vector-derived (Rules.md §7.4)
  - ✅ Per-line status only, never blended "%"
  - ✅ `ASSUMED` items force review in human UI (Rules.md §3.9)
  - ✅ Score reduction is automatic, not user-controlled

### Task 7 — DoD: Scanned Sample Sheet Produces Same Components with Lower Confidence
**What:** Validate end-to-end raster pipeline against scanned sample
- Upload scanned version of `MMC-JVC-CD-ELEC-3902_AC-WIRE-Model.pdf`
- Compare component counts to vector version
- Verify confidence ratings are lower (reflecting raster source)
- Ensure BOQ numbers still trace to deterministic calculations
- Regression test: `tests/test_phase1.5_regression.py`
- Trap constraints:
  - ✅ This is a **regression test** — if counts are off, pipeline has a bug
  - ✅ All numbers must still trace to deterministic calculations
  - ✅ Confidence ratings must be lower than vector version
  - ✅ Never fabricate values for unparseable elements
  - ✅ DoD note: *"scanned copy of the sample sheet produces the same components with confidence-tiered (lower) ratings"* (Phases.md §1.5 DoD)

---

## 5. Definition of Done for Phase 1.5 MVP

✅ Scanned PDF upload → raster classification path works  
✅ OCR text extraction functional (PaddleOCR primary, Tesseract fallback)  
✅ Per-document legend matching works (legend before YOLO fallback)  
✅ YOLOv8 shape detection only in raster path (never vector)  
✅ CubiCasa5K-style segmentation for non-legend elements only  
✅ Raster measurements have lower base confidence than vector  
✅ All BOQ numbers trace to deterministic calculations (no LLM output)  
✅ Confidence status displayed per line: `MEASURED (raster)` / `MEASURED (vector)` / `DERIVED` / `ASSUMED`  
✅ `pytest` green for all Phase 1.5 tests  
✅ `ruff check` passes on all new files  
✅ DoD met: scanned sample sheet produces same components with lower confidence ratings

---

## 6. Trap File Constraints (must observe)

| # | Constraint | Compliance |
|---|---|---|
| 1 | **No hardcoded values** — no unit prices, productivity rates in source | All from catalog DB or YAML at runtime |
| 2 | **Must use `pymupdf` not `fitz`** — every import must be `import pymupdf` | Lint rule; `import fitz` causes CI failure |
| 3 | **AI proposes, geometry calculates** — classification/proposal only | No LLM/vision model outputs final quantity |
| 4 | **Raster always lower confidence** than vector-derived | Rules.md §7.4 — per-line status with reduced scores |
| 5 | **Per-document legend matching first** — no universal symbol detector | ❌ Critical: AGENTS.md + Rules.md hard constraint |
| 6 | **YOLOv8 only in raster fallback (Phase 1.5)** — never in vector path | AGENTS.md Rules.md §4 — "Avoid in v1 vector path" |
| 7 | **Missing price → "unpriced", not $0** — flag the gap | Rules.md §5.1 |
| 8 | **No blended confidence %** — per-line status only | Rules.md §7.1 |
| 9 | **ASSUMED forces review** in human UI | Rules.md §3.9 |
| 10 | **Run `python -m pytest`** after any task — all tests must pass | Rules.md §6.1 |
| 11 | **Run `python -m ruff check app tests`** — lint must pass | Rules.md §6.1 |
| 12 | **Do not start Phase 1.5 before Phase 1 MVP DoD met** | Phases.md §standing rule; AGENTS.md "Don't build raster/CV fallback before v1 vector MVP is proven" |

---

## 7. Priority & Dependency Order for Phase 1.5

| Order | Task | Depends On | Effort | Note |
|---|---|---|---|---|
| 1 | PDF raster rendering at DPI | None (Phase 1 proven) | Small | PyMuPDF pixmap |
| 2 | OCR integration (PaddleOCR/Tesseract) | Task 1 | Medium | Proposals only |
| 3 | Per-document legend few-shot matching | Tasks 1+2 | High | Critical trap |
| 4 | YOLOv8 shape detection (raster-only) | Task 3 | Medium | Only Phase 1.5 path |
| 5 | CubiCasa5K segmentation (non-legend) | Task 3 | Medium | Element segmentation |
| 6 | Raster confidence tiering | Tasks 1-3 | Small | Lower base scores |
| 7 | DoD: scanned sample validation | All above | Medium | Regression test |

---

## 8. Execution Order Decision

**Option A: Do Phase 1.5 now** (recommended — natural continuation after Phase 1 MVP)
- Start with Task 1 (raster rendering)
- Validate end-to-end before moving to Task 3 (legend matching)
- Full Phase 1.5 DoD before Phase 2

**Option B: Skip Phase 1.5, move to Phase 2**
- Phase 2 (Full Electrical) does not require raster fallback
- Raster support can be added later as needed
- Valid choice if project focus is on vector sheets only

**Decision:** Recommend **Option A** — Phase 1.5 is the natural next step, and the specifications are now in place to begin implementation.

---

*End of Phase 1.5 MVP Specifications.*