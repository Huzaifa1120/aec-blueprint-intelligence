# Plan — Spec-v3 Accuracy-Conformance Follow-ups

Date: 2026-08-25 · Branch: `feature/accuracy-conformance-followups` (cut from main @ `43e3ca1`)
Source of requirements: final-review triage recorded in `docs/Memory.md` (commit `e18ce23`) against the merged accuracy-conformance package (`33e6738`). Spec of record: `docs/AEC-Blueprint-System-Design-Spec-v3.md` (§7.12, §7.14, §15).

Excluded (not code work): follow-up (5) `labor_rates` register-or-exclude is an owner ruling — the T12 guard + once-per-process warning already shipped. Nothing here touches quantity arithmetic, prices, or productivity rates.

Execution mode: three PARALLEL streams with disjoint file ownership (owner ruling 2026-08-25: "parallel disjoint streams"). Within a stream, tasks run sequentially.

| Stream | Tasks | Owned files (nobody else touches these) |
| --- | --- | --- |
| CORE | 1 → 4 → 5 | `backend/app/db/models/estimate.py`, `backend/app/e2e/router.py`, `backend/app/e2e/persistence.py`, `backend/app/estimates/payload.py`, `backend/app/exports/*.py`, `backend/app/narration/providers.py`, `backend/alembic/versions/*` (new), `backend/tests/test_source_region_persistence.py`, `backend/tests/test_v3_integration.py`, `backend/tests/test_accuracy_conformance_migration.py` |
| REVIEW | 2 | `backend/app/review/router.py`, `backend/tests/test_review_corrections.py` |
| FE | 3 | `frontend/e2e/mocks/api.ts`, `frontend/e2e/*.spec.ts` (only if an assertion reads the mock scale) |

---

## Task 1 (CORE) — Persist estimate-level `source_quality`; emit per-row in payload

Problem: `SheetExtraction.source_quality` exists and the LIVE `/api/e2e/run` response stamps each BOQ row's quality (via `_boq_line(source_quality=...)` feeding tier/score), but nothing persists it on the Estimate and `payload_from_estimate` emits no per-row `source_quality`. The frontend mapping (T11) — `EstimateClient.tsx` → `BOQTable` → `ConfidenceBadge [R]` raster modifier — is wired and tested (`normalizeBoq.test.ts`) but permanently dormant because served rows never carry the field.

Do:
1. Add `Estimate.source_quality: Mapped[str]` — `String(20)`, default `"layered_vector"` (mirror `SheetExtraction.source_quality`, `app/db/models/extraction.py:30`).
2. New Alembic revision (single parent = current head `b41f7c2da9e3`): batch-add the column to `estimates` with server default `'layered_vector'` so legacy rows backfill honestly.
3. In `app/e2e/persistence.py`, wherever the `Estimate` row is constructed (~line 663 area), persist `source_quality=extraction.source_quality`.
4. In `app/estimates/payload.py::payload_from_estimate`, add `"source_quality": estimate.source_quality` to EVERY row entry (`entry` dict — covers routes and materials), keyed exactly as the live response spells it (verify against `_boq_line`'s row dict in `app/e2e/router.py` and `frontend/src/app/estimates/[id]/EstimateClient.tsx:108,122` which reads `route.source_quality` / `material.source_quality`).
5. Tests (extend `tests/test_source_region_persistence.py`): persisted run → `GET /boq` rows carry `source_quality` equal to the run's verdict; a legacy-style row (column default) reads `"layered_vector"`; JSON export equals `/boq` byte-for-value (existing parity test style). Update the migration-table assertion if it enumerates `estimates` columns.

Verify: `backend/.venv/Scripts/python.exe -m pytest -q` full suite green from `backend/`; `python -m ruff check app tests` clean.

## Task 2 (REVIEW) — Existence-check `boq_item_id` on review actions

Problem: `app/review/router.py::add_action` persists `payload.boq_item_id` verbatim (line 103); SQLite does not enforce the FK, so actions can reference nonexistent BOQ items and silently pollute `corrections_from_estimate` joins.

Do:
1. When `payload.boq_item_id` is not None, `db.get(BoqItem, payload.boq_item_id)`; if None → `HTTPException(status_code=400, detail="Unknown boq_item_id")` (400: the client supplied an invalid reference; 404 stays reserved for the session path). Import `BoqItem` from `app.db.models.estimate`.
2. Test in `tests/test_review_corrections.py`: posting a well-formed but nonexistent UUID → 400 and no `ReviewAction` row created; posting a real BOQ item id → still recorded (existing coverage proves this path — keep green).

Verify: full backend suite + ruff from `backend/`.

## Task 3 (FE) — e2e mock scale block matches real contract

Problem: `frontend/e2e/mocks/api.ts:112` still has `scale: "1:100"` (string) — predates the `{value, status}` block the real `/api/e2e/run` contract now carries (`frontend/src/types/estimate.ts`).

Do:
1. Change to `scale: { value: "1:100", status: "assumed" }` (honest: mirrors the MMC reality — extractable text carries no parseable scale token, ratified assumed-1:100).
2. Grep `frontend/e2e/` for consumers reading `RUN_RESULT.scale` / `scale` off the run result; update any assertion that expects the string form. Do NOT touch production components.

Verify: `bun run lint && bun run typecheck && bun run test:e2e` from `frontend/` all green.

## Task 4 (CORE) — Dedupe duplicated helpers

Problem A: `_source_block` (`app/e2e/router.py:87`) and `_source_region` (`app/e2e/persistence.py:77`) are character-identical normalizers producing `{"page": int, "bbox": [floats]}` | None. Problem B: `_nonzero_counters(data_quality)` is duplicated verbatim in `app/exports/xlsx_export.py:43` and `app/exports/pdf_export.py:77`, with a third inline variant of the same predicate in `app/narration/providers.py:166`.

Do:
1. Extract ONE canonical source-region normalizer (keep the richer docstring; both call sites import it). Pure refactor — zero behavior change; the round-trip property (live row `source` == persisted payload `source`) must hold byte-for-value.
2. Extract ONE `nonzero_counters(data_quality) -> list[tuple[str, int]]` (bool-exclusion + int-check preserved exactly). All three export/narration sites consume it; each site's rendered output must be unchanged (xlsx annex rows, pdf annex lines, narration sentences).
3. Existing export/narration/source-region tests are the safety net — no new tests required unless coverage of the shared helper's edge cases (non-dict input, bool values, non-int values) is absent; add one small focused test only if so.

Verify: full backend suite + ruff.

## Task 5 (CORE) — Unmapped-clustering scale source + stale vocabulary

Problem A: `_unmapped_layer_clusters` (`app/e2e/router.py:322-347`) re-derives its threshold from the LEGACY `_scale_denominator(str(scale or ""))` imported from `app.ingestion.vector` instead of the resolver result the caller already holds (`scale_res = resolve_scale(...)` at line 524, call at line 548). Problem B: stale "parsed" vocabulary — `app/db/models/estimate.py:74` comment says `# parsed | assumed` while runtime writes `detected|assumed` (`ScaleResult.status`); `tests/test_v3_integration.py:538` seeds `scale_status="parsed"`.

Do:
1. Change `_unmapped_layer_clusters` signature to accept the resolved `denominator: float`; caller passes `scale_res.denominator`. Delete the `_scale_denominator` import from `app.e2e.router` (check whether other vector.py imports remain before touching anything else — leave vector.py itself alone).
2. Fix the model comment to `# detected | assumed`.
3. Update the integration seed to a real runtime value (`"detected"` or `"assumed"` — pick what the surrounding fixture asserts; keep the test's meaning intact).

Verify: full backend suite + ruff; unmapped-cluster tests must stay green unchanged (proving denominator equivalence).

---

## Global constraints

- AI proposes, geometry calculates, rules derive — none of these tasks touch quantities/prices; do not introduce any hardcoded price, rate, or default size.
- Import PyMuPDF as `pymupdf`, never `fitz`.
- Backend commands run from `backend/`: `..\.venv\Scripts\python.exe` convention — actually `backend/.venv/Scripts/python.exe -m pytest -q` / `-m ruff check app tests`.
- Frontend commands from `frontend/`: bun only (`bun run lint|typecheck|test:e2e`); lockfile `bun.lock` — never reintroduce package-lock.json.
- Pre-commit gate active (`core.hooksPath .githooks`): ruff on staged .py, eslint+tsc+prettier on staged frontend files — commits will fail on violations; that failing IS the gate working.
- Commit style follows repo history: `fix:`/`feat:`/`refactor:` conventional one-liners.
- Each task = its own commit(s); never mix two tasks in one commit.
