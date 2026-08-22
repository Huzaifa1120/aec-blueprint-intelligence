# Rules — AI & Engineering Boundaries

These are hard constraints for the coding agent and for the system itself. If a task conflicts with these rules, the rules win unless explicitly updated.

---

## 1. The one rule that cannot be violated

> **AI proposes. Geometry calculates. Engineering rules derive. Humans approve.**

- ✅ A vision model or LLM may *propose* "this is probably a card reader" or *interpret* an ambiguous legend entry.
- ✅ A geometry engine *measures* distances, areas, counts from real coordinates.
- ✅ A rules engine *derives* materials/labor from measured quantities using deterministic formulas.
- ❌ **No LLM or vision model ever outputs a final quantity, length, or price directly.**
- ❌ **Never present a model's guess as a measured value.**

Any number that appears in a BOQ must be traceable to a deterministic calculation. This is non-negotiable and is the difference between a system professionals trust and a demo.

## 2. What the AI is allowed to do

- Classify ambiguous symbol clusters (proposal only, human/rule-confirmed).
- Interpret the sheet's own legend table (symbol glyph → description).
- Generate the natural-language **scope of work** — but *narrating from already-computed structured data only*. It may never compute the numbers it narrates.
- Write code, refactor, explain, fix bugs, run tests.
- **Classify layers into disciplines (architectural, electrical, envelope, structural, unclassified) using human-editable regex config.**
- **Perform text-layer association walker to tag text spans with their controlling OCG via BDC/EMC nesting.**
- **Parse generic schedule/attribute blocks using config-driven regex patterns, with LLM fallback.**

## 3. What the AI must NEVER do

- Output a quantity, length, area, volume, count, or price as a "result" without a deterministic calculation behind it.
- Train or build a universal cross-company "construction symbol" detector. Use per-document legend matching first, always.
- Assume a scale. Scale must be read from the sheet (title block / scale bar / dimension string) and cross-checked.
- Hardcode price data or productivity rates into source code. They live in the catalog DB / YAML config.
- Ship code that exposes, logs, or commits secrets/API keys.
- **Silently drop or ignore any CAD layer without classification/record.** Every layer must be either classified, logged as `unclassified`, or flagged for human review in the LAYER table.
- **Assume an uploaded file is layer-rich vector.** Always run the Input Quality Gate first: score layer richness and flag flattened exports `degraded_vector` — never silently parse them as the happy path (spec v3 §7.2, §5.5).
- **Default to any detector requiring an unbudgeted commercial license.** Ultralytics YOLOv8 (AGPL-3.0) requires an Enterprise License even for internal-only proprietary use (vendor-confirmed) — it is removed from the default stack; classical CV + Detectron2 cover the raster path without one.

## 4. Libraries — allowed vs. avoided

### Allowed (per Architecture.md)
| Purpose | Library | Import note |
|---|---|---|
| Vector PDF parsing | `pymupdf` (PyMuPDF) | import `pymupdf`, **not** deprecated `fitz` |
| PDF cross-validation | `pikepdf`, `pdfminer.six` | dev-time verification only |
| CAD parsing | `ezdxf` | DWG/DXF path |
| BIM parsing | `ifcopenshell` | later phase only |
| Geometry ops | `shapely` | clustering, polygons, area math (`polygonize`); `networkx` conditional fallback only if polygonize proves insufficient |
| Raster CV — legend matching | `opencv-python` | **default raster technique**: `matchTemplate` / ORB-SIFT against the sheet's own legend glyphs; no training, no license cost |
| Raster CV — region segmentation | `detectron2` (Apache-2.0) | sole trained-model dependency; raster path only |
| OCR | `paddleocr` (primary), `pytesseract` (fallback) | + rotation-aware preprocessing (spec v3 §7.7C) |
| Backend | `fastapi`, `uvicorn`, `pydantic` | |
| DB | `sqlalchemy`, `alembic` (SQLite file DB, Phase 0); `psycopg` added when moving to PostgreSQL | |
| Queue | `celery`, `redis` | async processing |
| Testing | `pytest`, `pytest-asyncio` | |

### Avoid unless justified in writing
- `fitz` (deprecated PyMuPDF alias).
- `ultralytics` / YOLOv8 — AGPL-3.0 requires an Enterprise License even for internal proprietary use (vendor-confirmed). Removed as default (spec v3 §7.7, §9); revisit only if classical CV + Detectron2 prove insufficient on real degraded files, as a deliberate budgeted licensing decision.
- Any pure-CV-only "image in → BOQ out" architecture.
- Heavy deep-learning frameworks anywhere in the **vector path** — they belong only in the raster fallback, where Detectron2 is the sanctioned choice.

## 5. Error handling rules

- Every pipeline stage must fail loudly and traceably: return a per-stage status, never silently return zeros.
- Unparseable file / missing scale / unknown layer → mark the job `error` or `needs_review` with the reason; never fabricate a value.
- A missing price or productivity rate → BOQ line shows "unpriced" with the gap flagged, not $0.
- Network/3rd-party calls (OCR, LLM) get timeouts + retries + a degradation path (e.g. LLM down → skip narration, still produce numbers).
- All failures logged with enough context to reproduce (file id, stage, error).
- **Unknown layer → mark items as `UNMAPPED`; human can confirm classification in review.**
- **Incomplete assembly → item left `UNMAPPED` instead of forced into `ASSUMED`; rule gap flagged for human improvement.**
- **Degraded input (flattened / no-layer vector PDF) → flag `degraded_vector`, request re-export in closed deployment, or route to raster with lower base confidence.** Never process silently as if layered; never guess through a bad file.

## 6. Code quality rules

- No comments in code unless explicitly requested; prefer self-documenting names.
- Quantity & cost engine = pure functions, fully unit-tested, zero AI involvement.
- All derived values record `rule_version` that produced them.
- Follow existing file conventions; check `pyproject.toml` / `package.json` before assuming a library exists.
- After any task: run the project's lint/typecheck/test commands.

## 7. Confidence & honesty rules

- Per-line confidence status: `MEASURED` / `DERIVED` / `ASSUMED` / `UNMAPPED` — never one blended "%".
- Every measurement also carries a **`source_quality` flag**: `layered_vector` / `degraded_vector` / `raster`. A `MEASURED` count from a flattened or raster source is not the same claim as one from layered vector — accuracy is tracked and reported per tier, never blended (spec v3 §7.12, §15).
- Raster-derived measurements always have lower base confidence than vector-derived.
- **Human review time per sheet and per confidence tier is logged from Stage 0 onward.** If it exceeds the threshold agreed with the business stakeholder, treat that as a blocking product issue — recalibrate confidence/bulk-accept rules before expanding coverage.
- **`UNMAPPED`** : geometry/text was measured successfully but no assembly rule exists yet to turn it into a costed BOQ line. Decouples "did we look" from "can we price it yet."
- Never claim accuracy publicly without benchmarking against held-out, already-estimated real projects (start with 3–5).

## 8. Scope discipline

- Do not build raster fallback, raw-material estimation, or multi-sheet features before v1 MVP (see `Phases.md`) is done and proven.
- Single-tenant internal deployment first; multi-tenant is a later decision.