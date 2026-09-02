# Lighting Discipline Live Integration — Design

**Date:** 2026-09-02
**Status:** Approved (brainstorming complete)
**Owner:** Saad Ahmad
**Related code:** V1–V4 lighting subagents on `feature/lighting-v3-v4-handoff` (commit `fe6ec87`)
**Defect reference:** the P0050 lighting PDFs return `verdict=layered_vector` at the quality gate but `/api/e2e/run` returns `boq_items: []` + `estimate_id: null`; the frontend surfaces this as the misleading `QUALITY_CHECK_FAILED_COPY` ("Couldn't read this PDF's structure…")

---

## 1. Problem

The user uploaded a P0050 lighting layout PDF and saw "can't read the file, upload any other." Investigation showed three intertwined gaps:

1. **V1–V4 lighting code exists on a feature branch but is not wired into the live `/api/e2e/run` route.** The code lives in `backend/app/services/lighting/` as an offline script (`reconciliation.py`). The live route uses `app/e2e/extraction.py` + `app/parsing/*` + `data/assemblies/*.yaml`. No assembly rule maps the `DALI CONTROL` OCG layer to a `lighting_fixture_*` assembly, so the live pipeline correctly finds 0 BOQ rows.
2. **The e2e run takes ~50 s on a 96k-path P0050 PDF.** The frontend's `fetch` has no timeout; in the browser the user sees a hang, then a misleading "couldn't read" error.
3. **The empty-BOQ result is presented as a generic "pipeline failure."** `app/page.tsx:120-127` treats `boq_items=[]` + `estimate_id=null` as failure with no actionable message.

This spec closes all three gaps in one coherent fix.

---

## 2. Goals (testable)

| # | Goal | Acceptance test |
|---|------|-----------------|
| G1 | The P0050 Part-1 lighting PDF produces a non-empty `boq_items` list with `discipline='lighting'` rows, each carrying `spec_code`, `loop_id`, `confidence_status`, `source_bbox_json`, and `derivation_json`. | `test_e2e_lighting_http.py::test_post_e2e_run_with_lighting_pdf_produces_estimate_with_lighting_boq` |
| G2 | `POST /api/e2e/run` returns in < 500 ms with a `job_id`; the actual work happens in a background thread. | `test_e2e_lighting_http.py::test_post_e2e_run_returns_202_with_job_id` |
| G3 | `GET /api/jobs/{job_id}` returns `status` ∈ {`queued`,`running`,`done`,`failed`} with `progress`, `result`, `error` fields per the contract. | `test_e2e_lighting_http.py::test_get_job_returns_done_with_estimate_id` |
| G4 | The frontend polls the job status with exponential backoff up to 120 s; on timeout it shows a real "still running in background" message, not "couldn't read." | `usePipelineRun.test.tsx::test_usePipelineRun_aborts_on_120s_timeout` |
| G5 | When `boq_items` is empty for a successfully-parsed drawing, the frontend shows a specific message naming the missing discipline, not a generic failure. | `page.test.tsx::test_page_renders_specific_message_on_empty_boq` |
| G6 | The new lighting rule follows the existing YAML-driven assembly framework: `data/assemblies/lighting_fixture_panel.yaml` is the only new rule file. No hardcoded prices, no LLM-derived quantities. | Lint + import audit; `test_e2e_lighting.py::test_build_lighting_boq_emits_unpriced_flag_when_catalog_missing` (asserts `unit_price is None`, never `0`) |
| G7 | The in-memory job queue is thread-safe, bounded to 100 jobs, and jobs expire 5 min after `finished_at`. | `test_job_queue.py` (8 tests) |

---

## 3. Non-goals (explicit)

- Multi-worker / Celery / Redis / Supabase jobs table. Single-tenant internal tool per PRD §2; in-memory queue is enough.
- Job persistence across server restarts. A restart clears the queue; the user re-uploads. We log the event so it's visible.
- Re-spec'ing V1–V4. They stay on the feature branch; this spec imports them as a library and calls them.
- Pricing the new lighting spec codes. If a spec code has no catalog row, the BOQ row is flagged `unpriced` with `unit_price = None`. Per AGENTS.md "Unit prices / productivity rates live in catalog DB or YAML — never hardcode them in source."
- A raster path for lighting. Lighting is vector-only; rasterized lighting PDFs route back to the uploader via the existing quality gate (already shipped).
- Wiring other disciplines (mechanical, plumbing, fire) into the async queue in this spec. The queue is generic; other disciplines can be migrated later, one PR each.

---

## 4. Architecture

```
                  ┌─────────────────────────┐
   POST /api/e2e  │  app/jobs/              │  {job_id, status_url}    < 500ms
   /run (file)    │  - InMemoryJobQueue     │
   ──────────────►│  - run_lighting_e2e()   │  (background thread)
                  │  - persist()            │
                  └────────┬────────────────┘
                           │
                  ┌────────▼────────────────┐
   GET /api/jobs  │  InMemoryJobQueue.get() │  {status, result, error}
   /{job_id}      │  - status: queued/      │
   ──────────────►│    running/done/failed  │
                  └────────┬────────────────┘
                           │
       ┌───────────────────┼─────────────────────┐
       │                   │                     │
┌──────▼────────┐  ┌────────▼──────┐  ┌──────────▼─────────┐
│ V1 denoiser   │  │ V2 rooms      │  │ V3 legend specs    │
│ (existing)    │  │ (existing)    │  │ + V4 loop quant.   │
└──────┬────────┘  └───────┬───────┘  └──────────┬─────────┘
       │                   │                    │
       └───────────────────┼────────────────────┘
                           │
                  ┌────────▼────────────────┐
                  │  new: app/e2e/          │
                  │  lighting.build_        │  Per-DALI-loop rows:
                  │  lighting_boq(...)      │  {loop_id, spec_code, count,
                  └────────┬────────────────┘   confidence, source.bbox}
                           │
                  ┌────────▼────────────────┐
                  │  existing: persistence  │  BoqItem rows tagged
                  │  spine + payload builder│  discipline='lighting'
                  └─────────────────────────┘
```

### Three new files

1. **`backend/app/jobs/__init__.py`** + **`backend/app/jobs/queue.py`** — in-memory FIFO job queue (threading.Lock + daemon worker thread).
2. **`backend/app/jobs/router.py`** — `POST /api/e2e/run` becomes an enqueue; new `GET /api/jobs/{job_id}`.
3. **`backend/app/e2e/lighting.py`** — `build_lighting_boq(symbols, rooms, loops, specs) → List[LightingBoqRow]` — the glue between V1–V4 outputs and the existing `payload.py` BOQ builder.

### Two changed files

1. **`backend/app/e2e/router.py`** — `e2e_run` becomes a thin enqueue wrapper; actual work moves to `app/jobs/queue.py::run_e2e_job()`. `persist=true` becomes part of the job request, not a separate code path.
2. **`frontend/src/app/page.tsx` + `usePipelineRun.ts` + `lib/api.ts`** — `usePipelineRun` POSTs and returns a `job_id`, then polls `GET /api/jobs/{id}` with 2 s → 3 s → 4.5 s backoff (cap 10 s) up to 120 s. Empty-BOQ branch shows a specific message; polling timeout shows a real "still running" message.

### Two new alembic columns (one migration)

- `boq_items.spec_code VARCHAR(32) NULL`
- `boq_items.loop_id VARCHAR(64) NULL`

Both nullable. Existing mechanical/plumbing/fire rows untouched. Single alembic revision file (auto-generated).

### One new YAML rule

`data/assemblies/lighting_fixture_panel.yaml` — uses existing `match.layer_contains: "DALI CONTROL"` + `$variables` substitution + `tier: DERIVED` propagation. No rule engine changes.

---

## 5. Data Model

### BoqItem rows for lighting (no migration for these)

```python
# Reuses existing BoqItem columns
boq_item = {
    "id": uuid,
    "estimate_id": uuid,
    "assembly_type": "lighting_fixture_panel",  # NEW yaml rule key
    "spec_code": "02-0318",                      # NEW column (nullable)
    "loop_id": "DALI LOOP-03",                   # NEW column (nullable)
    "size": None,                                # not length-based
    "unit": "ea",                                # each
    "quantity": 36,                              # V4 tie-breaker output
    "unit_price": None,                          # unpriced flag (no $0 substitution)
    "confidence_status": "DERIVED",              # MEASURED/DERIVED/ASSUMED/UNMAPPED
    "confidence_score": 0.78,                    # V4 score_breakdown['shape_preference'] etc.
    "source_bbox_json": [[x0, y0, x1, y1], ...], # one per assigned symbol
    "derivation_json": {
        "loop_id": "DALI LOOP-03",
        "spec_code": "02-0318",
        "text_quantity": 36,           # ground truth from DALI LOOP label
        "spatial_count": 36,           # V4 actual count
        "delta": 0,                    # text - spatial
        "emergency_split": {           # from V1+V2 marker association
            "CB": 18, "EM": 17, "EMEM": 1, "NORMAL": 0
        },
        "tie_breaker": "v4_documented_4_factor_cascade",
    },
    "review_status": "PENDING",
    "flagged": False,                          # title-block gate from elecfix
}
```

### Job queue data model

```python
# backend/app/jobs/queue.py
from dataclasses import dataclass, field
from typing import Optional, Literal
import time

@dataclass
class Job:
    id: str                              # uuid4
    kind: Literal["e2e_run"]
    status: Literal["queued", "running", "done", "failed"]
    created_at: float                    # time.time()
    started_at: Optional[float]
    finished_at: Optional[float]
    request: dict                        # {"file_path": str, "persist": bool, "project_id": str|None}
    result: Optional[dict]               # full e2e response when done
    error: Optional[str]                 # short error summary when failed
    progress: str                        # "running V4 cascade" / etc.

class InMemoryJobQueue:
    _jobs: dict[str, Job] = field(default_factory=dict)
    _lock: threading.Lock
    _MAX_JOBS = 100
    _JOB_TTL_SEC = 300  # 5 min after finished_at

    def enqueue(self, kind: str, request: dict) -> str: ...
    def get(self, job_id: str) -> Job: ...   # raises KeyError if not found / expired
    def _worker_loop(self) -> None: ...      # daemon thread, picks oldest queued
    def _evict_expired(self) -> None: ...    # called on enqueue and get
```

No DB persistence (per scope decision). Restart = queue cleared; user re-uploads.

---

## 6. API Contracts

### `POST /api/e2e/run` (CHANGED — async)

**Request:** unchanged — `multipart/form-data` with `file` (PDF) + query `persist=true|false` + `project_id=uuid`.

**Success response (202 Accepted):**
```json
{
  "job_id": "9c1f...",
  "status": "queued",
  "status_url": "/api/jobs/9c1f...",
  "poll_after_ms": 2000
}
```

**Synchronous failure modes** (still return non-202):
| Cause | Status | Body `detail` |
|---|---|---|
| File not a PDF | 400 | "Only PDF files are accepted" |
| File > 50 MB | 413 | "File exceeds 50 MB limit" |
| Queue full (100 jobs in flight) | 503 | "Server busy, retry in 30s" |

### `GET /api/jobs/{job_id}` (NEW)

**Success response (200):**
```json
{
  "id": "9c1f...",
  "status": "running",                    // queued | running | done | failed
  "progress": "running V4 tie-breaker",   // human-readable, updated by worker
  "created_at": 1756800000.0,
  "started_at": 1756800000.1,
  "finished_at": null,
  "result": null,                         // populated when status=done
  "error": null                           // populated when status=failed
}
```

When `status=done`, `result` carries the **same shape the synchronous e2e/run used to return**:
```json
{
  "status": "ok",
  "scale": {"value": "1:100", "status": "detected"},
  "boq_items": [...],
  "estimate_id": "uuid",
  "layers_count": 103,
  "data_quality": {...},
  ...
}
```
so the frontend redirect logic (`/estimates/{estimate_id}`) just keeps working.

When `status=failed`, `error` is a short summary (first line of traceback + exception class name). Full traceback goes to backend log only.

**Failure modes:**
| Cause | Status | Body `detail` |
|---|---|---|
| Job not found / expired (TTL = 5 min after `finished_at`) | 404 | "Job not found or expired; re-upload the file." |
| Job in flight, transient | 200 with `status: running` (not a failure) |

---

## 7. Error handling — the contract (no more "couldn't read")

| Real cause | Frontend message | Source |
|---|---|---|
| Backend unreachable (network/CORS) | "Can't reach the server. Check your connection." | new |
| 400 invalid file type | "Only PDF files are accepted." | backend `detail` |
| 413 file too large | "File exceeds 50 MB. Split the drawing set." | backend `detail` |
| Quality gate `degraded_vector` | "Layer data not found. Re-export with layers included, or request a re-export." | existing (correct) |
| Quality gate `raster` | "This drawing is a raster image. Re-export as vector PDF." | existing (correct) |
| `boq_items: []` + `estimate_id: null` (no rule matches) | "Drawing parsed (N layers, M paths), but no assembly rule matches the lighting discipline yet. Add a rule in `data/assemblies/` to count fixtures." | **new — specific to symptom** |
| Job polling timeout (120 s) | "Pipeline still running in the background. Refresh the estimates list to see it when it finishes." | **new** |
| Job `failed` | `result.error` (real backend error) | **new — no more generic** |
| Unknown | backend `detail` if present, else "Upload failed. Try again or pick a different file." | **new — no more "couldn't read"** |

The misleading `QUALITY_CHECK_FAILED_COPY` ("Couldn't read this PDF's structure…") is shown **only** for true network failures to `/api/drawings/check` — never for empty-BOQ, never for slow-pipeline, never for backend job failures.

---

## 8. Frontend polling

```typescript
// frontend/src/hooks/usePipelineRun.ts (new shape)
const POLL_INTERVAL_MS = 2000
const POLL_BACKOFF_MAX_MS = 10000
const POLL_TOTAL_TIMEOUT_MS = 120000

async function pollUntilDone(jobId: string, signal: AbortSignal) {
  let interval = POLL_INTERVAL_MS
  const deadline = Date.now() + POLL_TOTAL_TIMEOUT_MS
  while (Date.now() < deadline) {
    if (signal.aborted) throw new DOMException('aborted', 'AbortError')
    const job = await apiGet<Job>(`/api/jobs/${jobId}`, signal)
    if (job.status === 'done') return job.result
    if (job.status === 'failed') throw new Error(job.error ?? 'Pipeline failed')
    await sleep(interval, signal)
    interval = Math.min(interval * 1.5, POLL_BACKOFF_MAX_MS)  // 2s → 3s → 4.5s → 6.75s → 10s cap
  }
  throw new Error('Pipeline still running after 120s. The job continues in the background — refresh the estimates list.')
}
```

---

## 9. Testing strategy (TDD — every test fails before its code is written)

### 9.1 Backend tests (20 new, all RED first)

| File | Test | Verifies |
|---|---|---|
| `tests/test_job_queue.py` | `test_enqueue_returns_job_id` | enqueue contract |
| `tests/test_job_queue.py` | `test_get_returns_queued_job` | get contract |
| `tests/test_job_queue.py` | `test_worker_marks_status_running` | daemon thread lifecycle |
| `tests/test_job_queue.py` | `test_worker_marks_status_done_on_success` | happy path |
| `tests/test_job_queue.py` | `test_worker_marks_status_failed_on_exception` | error capture |
| `tests/test_job_queue.py` | `test_job_ttl_expires_after_5_min` | 5-min eviction |
| `tests/test_job_queue.py` | `test_queue_bounds_to_100_jobs` | FIFO eviction |
| `tests/test_job_queue.py` | `test_concurrent_enqueue_is_thread_safe` | lock discipline |
| `tests/test_e2e_lighting.py` | `test_build_lighting_boq_with_v1_v2_v3_v4_outputs` | integration of V1–V4 |
| `tests/test_e2e_lighting.py` | `test_build_lighting_boq_respects_loop_capacity` | tie-breaker constraint |
| `tests/test_e2e_lighting.py` | `test_build_lighting_boq_emits_unpriced_flag_when_catalog_missing` | no hardcoded $0 |
| `tests/test_e2e_lighting.py` | `test_build_lighting_boq_derives_confidence_from_v4_breakdown` | confidence in [0.3, 1.0] |
| `tests/test_e2e_lighting.py` | `test_build_lighting_boq_returns_empty_when_no_dali_loops` | degenerate input |
| `tests/test_e2e_lighting.py` | `test_build_lighting_boq_persists_to_boq_items_table` | persistence to Supabase |
| `tests/test_lighting_boq_columns.py` | `test_spec_code_column_nullable` | migration round-trip |
| `tests/test_lighting_boq_columns.py` | `test_loop_id_column_nullable` | migration round-trip |
| `tests/test_e2e_lighting_http.py` | `test_post_e2e_run_returns_202_with_job_id` | < 500 ms enqueue |
| `tests/test_e2e_lighting_http.py` | `test_get_job_returns_done_with_estimate_id` | full async round-trip |
| `tests/test_e2e_lighting_http.py` | `test_get_job_returns_failed_with_real_error_message` | error contract |
| `tests/test_e2e_lighting_http.py` | `test_post_e2e_run_with_lighting_pdf_produces_estimate_with_lighting_boq` | **G1 acceptance** |

### 9.2 Frontend tests (4 new tests)

| File | Test | Verifies |
|---|---|---|
| `frontend/src/hooks/usePipelineRun.test.tsx` | `test_usePipelineRun_polls_job_status` | polling loop, done/failed branches |
| `frontend/src/hooks/usePipelineRun.test.tsx` | `test_usePipelineRun_aborts_on_120s_timeout` | timeout throws real message |
| `frontend/src/app/page.test.tsx` | `test_page_renders_specific_message_on_empty_boq` | no more generic "couldn't read" |
| `frontend/src/app/page.test.tsx` | `test_page_shows_real_backend_error_not_generic` | shows `result.detail`/`result.error` |

### 9.3 Verification gate (proof the fix actually works)

```bash
# Backend (from backend/)
python -m pytest tests/test_job_queue.py tests/test_e2e_lighting.py \
                 tests/test_lighting_boq_columns.py tests/test_e2e_lighting_http.py \
                 -v
# expected: 20 passed

python -m pytest -q
# expected: 411 passed (391 existing + 20 new), 0 fail, 1 xfail (raster spike)

python -m ruff check app tests
# expected: clean on new code; pre-existing V0/V1 errors untouched

# Frontend (from frontend/)
bun run typecheck && bun run lint && bun run test
# expected: clean

# Live smoke (against running backend on :8000)
curl -F "file=@data/samples/P0050-AMC-A-E2-2F-EL-122-02-B, Lighting Layout, 2nd Floor, Part-1.pdf" \
     "http://127.0.0.1:8000/api/e2e/run?persist=true"
# expected: {"job_id": "...", "status": "queued", ...}  in < 500ms

curl http://127.0.0.1:8000/api/jobs/{id}
# expected: status=done, result.estimate_id is not None, result.boq_items contains lighting rows
```

---

## 10. Migration

Single alembic revision, two `op.add_column` calls:

```python
# alembic/versions/<rev>_add_lighting_spec_columns.py
def upgrade() -> None:
    op.add_column("boq_items", sa.Column("spec_code", sa.String(32), nullable=True))
    op.add_column("boq_items", sa.Column("loop_id", sa.String(64), nullable=True))
    op.create_index("ix_boq_items_spec_code", "boq_items", ["spec_code"], unique=False)
    op.create_index("ix_boq_items_loop_id", "boq_items", ["loop_id"], unique=False)

def downgrade() -> None:
    op.drop_index("ix_boq_items_loop_id", table_name="boq_items")
    op.drop_index("ix_boq_items_spec_code", table_name="boq_items")
    op.drop_column("boq_items", "loop_id")
    op.drop_column("boq_items", "spec_code")
```

Supabase has all 22 tables at head `ee9f02b769f0` (verified 2026-09-02). The new revision will be applied during the SDD execution step.

---

## 11. Files touched (summary)

**New (8 files):**
- `backend/app/jobs/__init__.py`
- `backend/app/jobs/queue.py`
- `backend/app/jobs/router.py`
- `backend/app/e2e/lighting.py`
- `backend/app/e2e/lighting_rules.py` (helper for `match.layer_contains` / spec→assembly wiring)
- `backend/alembic/versions/<rev>_add_lighting_spec_columns.py`
- `data/assemblies/lighting_fixture_panel.yaml`
- `docs/superpowers/specs/2026-09-02-lighting-e2e-integration.md` ← this file

**Modified (5 files):**
- `backend/app/e2e/router.py` (split into enqueue + worker)
- `backend/app/main.py` (include jobs router)
- `frontend/src/lib/api.ts` (add `apiPostFormWithTimeout` or accept `signal`)
- `frontend/src/hooks/usePipelineRun.ts` (poll + 120 s timeout)
- `frontend/src/app/page.tsx` (use new hook; specific empty-BOQ message)

**Tests (4 new + 1 modified):**
- `backend/tests/test_job_queue.py` (8 tests, new)
- `backend/tests/test_e2e_lighting.py` (6 tests, new)
- `backend/tests/test_lighting_boq_columns.py` (2 tests, new)
- `backend/tests/test_e2e_lighting_http.py` (4 tests, new)
- `frontend/src/hooks/usePipelineRun.test.tsx` (extend with 2 new tests)
- `frontend/src/app/page.test.tsx` (extend with 2 new tests)

**Total: 8 new files, 5 modified, 4 new test files + 2 test files extended. 24 new tests.**

---

## 12. Risks and mitigations

| Risk | Mitigation |
|---|---|
| In-memory queue lost on server restart | Log "queue cleared by restart" event; user re-uploads. Acceptable for v2 single-tenant internal tool (PRD §2). |
| Background thread crashes silently | `try/except` around the whole `_run_job` body; `status=failed` + `error=traceback summary` on any exception. Worker thread never dies — it logs and re-enters the loop. |
| V1–V4 import path from a feature branch into main | **Prerequisite:** `feature/lighting-v3-v4-handoff` (commit `fe6ec87`) MUST be merged to `main` before this spec's SDD execution. The SDD plan's first task is the merge. The lighting-v3-v4-handoff branch is local-only and unmerged (the previous session ran `--no-verify` due to pre-existing V0/V1 lint errors). After merge, the import path is `from app.services.lighting.XXX import YYY`. |
| `POST /api/e2e/run` changing from sync to async is a breaking change to any test or caller that reads the response body directly | The implementation plan's T2 will update every existing e2e HTTP test to do `POST → assert 202 → poll job → assert done → use result`. The 4 existing e2e HTTP tests that read the body are: `test_e2e_run_persists_estimate.py`, `test_e2e_run_replay.py`, `test_quality_endpoints.py` (e2e portion), `test_data_quality.py`. Total expected churn: ~20–30 LOC of test plumbing. |
| Polling 2 s × 60 = 120 HTTP requests in 2 min on a busy day | In-memory queue, jobs auto-expire after 5 min. 120 req/min from a single user is negligible. |
| New `spec_code`/`loop_id` columns increase BoqItem row size by ~100 bytes | Negligible. BoqItem is already a wide table (JSON provenance, bbox, derivation). |
| `lighting_fixture_panel.yaml` rule could be too greedy (matches non-lighting DALI CONTROL) | V1 layer isolation already filters to `DALI CONTROL` only; the rule is keyed on the same layer, so the selectivity is correct. Backed by V1's 673-symbol / 96k-path test fixture. |
| V4 tie-breaker is heuristic, not exact | Per spec v3 §7.4, all lighting quantities land at `DERIVED` confidence (not `MEASURED`). The `confidence_score` is the V4 score. This is honest and the user can review/correct. |

---

## 13. Out of scope for future specs (cataloged, not built)

- Migrating other disciplines (mechanical, plumbing, fire) to the async job queue. The queue is generic; each discipline gets its own SDD.
- Job persistence across restarts (would need a `jobs` table + alembic migration + worker restart semantics).
- Progress streaming (SSE / WebSocket). Polling is enough at v2's user count.
- Auto-catalog-match for the new spec codes. Out of scope — user imports their catalog via the existing `/api/catalog/import` endpoint.
- Re-rendering lighting overlay PDFs. V6 review artifact is a separate subagent (per `docs/lighting_takeoff_status.md`); it's a downstream consumer of the new BoqItem rows, not a blocker for this spec.

---

## 14. Acceptance summary (the one-line test)

> **Uploading `P0050-AMC-A-E2-2F-EL-122-02-B, Lighting Layout, 2nd Floor, Part-1.pdf` through the live UI results in: POST returns 202 in < 500 ms, the polling indicator spins, after 30–60 s the user lands on `/estimates/{id}` showing a BOQ with at least one row tagged `discipline=lighting`, `assembly_type=lighting_fixture_panel`, with a real `spec_code` (one of the 50+ codes from V3), a real `loop_id` (one of the 10 DALI LOOPs from text_clustering), and `unit_price=null` with a clear "unpriced — add to catalog" affordance.**
