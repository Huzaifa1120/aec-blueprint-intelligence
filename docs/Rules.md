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

## 3. What the AI must NEVER do

- Output a quantity, length, area, volume, count, or price as a "result" without a deterministic calculation behind it.
- Train or build a universal cross-company "construction symbol" detector. Use per-document legend matching first, always.
- Assume a scale. Scale must be read from the sheet (title block / scale bar / dimension string) and cross-checked.
- Hardcode price data or productivity rates into source code. They live in the catalog DB / YAML config.
- Ship code that exposes, logs, or commits secrets/API keys.

## 4. Libraries — allowed vs. avoided

### Allowed (per Architecture.md)
| Purpose | Library | Import note |
|---|---|---|
| Vector PDF parsing | `pymupdf` (PyMuPDF) | import `pymupdf`, **not** deprecated `fitz` |
| CAD parsing | `ezdxf` | DWG/DXF path |
| BIM parsing | `ifcopenshell` | later phase only |
| Geometry ops | `shapely` | clustering, polygons, area math |
| Raster CV | `opencv-python`, `ultralytics` (YOLOv8) | fallback path |
| OCR | `paddleocr` (primary), `pytesseract` (fallback) | |
| Backend | `fastapi`, `uvicorn`, `pydantic` | |
| DB | `sqlalchemy`, `alembic` (SQLite file DB, Phase 0); `psycopg` added when moving to PostgreSQL | |
| Queue | `celery`, `redis` | async processing |
| Testing | `pytest`, `pytest-asyncio` | |

### Avoid unless justified in writing
- `fitz` (deprecated PyMuPDF alias).
- Any pure-CV-only "image in → BOQ out" architecture.
- Heavy deep-learning frameworks (PyTorch/Detectron2) anywhere in the **v1 vector path** — they belong only in the raster fallback.

## 5. Error handling rules

- Every pipeline stage must fail loudly and traceably: return a per-stage status, never silently return zeros.
- Unparseable file / missing scale / unknown layer → mark the job `error` or `needs_review` with the reason; never fabricate a value.
- A missing price or productivity rate → BOQ line shows "unpriced" with the gap flagged, not $0.
- Network/3rd-party calls (OCR, LLM) get timeouts + retries + a degradation path (e.g. LLM down → skip narration, still produce numbers).
- All failures logged with enough context to reproduce (file id, stage, error).

## 6. Code quality rules

- No comments in code unless explicitly requested; prefer self-documenting names.
- Quantity & cost engine = pure functions, fully unit-tested, zero AI involvement.
- All derived values record `rule_version` that produced them.
- Follow existing file conventions; check `pyproject.toml` / `package.json` before assuming a library exists.
- After any task: run the project's lint/typecheck/test commands.

## 7. Confidence & honesty rules

- Per-line confidence status: `MEASURED` / `DERIVED` / `ASSUMED` — never one blended "%".
- Raster-derived measurements always have lower base confidence than vector-derived.
- Never claim accuracy publicly without benchmarking against held-out, already-estimated real projects (start with 3–5).

## 8. Scope discipline

- Do not build raster fallback, raw-material estimation, or multi-sheet features before v1 MVP (see `Phases.md`) is done and proven.
- Single-tenant internal deployment first; multi-tenant is a later decision.