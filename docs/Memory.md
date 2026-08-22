# Memory — Project Progress Tracker

> Created once coding begins. The AI updates this at the end of every working session so a fresh chat/agent can resume without re-reading the codebase.
>
> **Before starting work:** read this file first. If it's stale, skim `docs/` and recent commits.

---

## Project snapshot

- **Project:** AEC Blueprint Intelligence System (construction QTO / cost estimating)
- **Docs of record:** `docs/PRD.md`, `docs/Architecture.md`, `docs/Rules.md`, `docs/Phases.md`, `docs/Design.md`, `docs/AEC-Blueprint-System-Design-Spec-v3.md` (**v3 supersedes v2 and the original spec**)
- **Current phase:** Phase 2 — Full Electrical discipline (✅ done). **Next: Phase 2.5 — Spec v3 Alignment** (Input Quality Gate, clustering migration, raster re-proof, `source_quality` schema, review-time metrics) — see `Phases.md`.
- **Status summary:** Phase 2 fully complete (12/12 regression green, merged feature → dev → main). 2026-08-22: all six docs synced to Design Spec v3 — YOLOv8 removed from default stack (AGPL licensing), DBSCAN → distance-threshold clustering (pending code change), Input Quality Gate added to design, `source_quality` provenance flag introduced. Code does NOT yet implement the v3 deltas — that is exactly what Phase 2.5 covers.
- **Python:** machine-dependent. This machine (user `saada`): **no `backend/.venv` present** — recreate it before running anything (`python -m venv backend/.venv`). The `C:\Users\Huzaifa\...` path recorded earlier is stale (different machine).

---

## Progress log

| Date       | Phase | What was done                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                             | Verified by                                                                                                                                                                |
| ---------- | ----- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| 2026-08-22 | 2.5   | **Docs synced to Design Spec v3.** Updated `PRD.md`, `Architecture.md`, `Rules.md`, `Phases.md`, `Design.md`, this file. Propagated: Input Quality Gate (§7.2), raster split rewrite — OpenCV legend matching default + Detectron2 only for region segmentation, YOLOv8 removed as default (AGPL Enterprise-License exposure) (§7.7/§9), DBSCAN → deterministic distance-threshold union-find clustering (§7.4), rotation-aware OCR (§7.7C), `source_quality` flag in canonical model/data model/UI, review-time-per-sheet metric (§7.13/§15), three new API endpoints (§10), Stage 1.5 raster spike re-scoped into Phases.md as **Phase 2.5** with DoD. Added implementation-status notes marking every v3 delta not yet in code. | Cross-checked each claim against `backend/app/**`, `backend/pyproject.toml`, `data/assemblies/`, frontend tree (validation findings below)                                  |
| 2026-08-21 | 2     | **Phase 2 fully closed.** Executed `docs/superpowers/plans/2026-08-21-phase-2-ep3-yr2-plan.md` (Tasks 1–4 all `[x]`): wrote `test_ep3_e2e_pipeline_validation_on_sample` (gates E1–E9) and `test_yaml_rule_persistence_to_db` (gates Y1–Y5) in `backend/tests/test_phase2_regression.py` (now 12 tests). Fixed 2 new ruff violations in the appended code (E741 `l`, F811 `Material` redefinition) — no new violations vs baseline. Merged `feature/phase2-ep3-yr2` → dev → main (`--no-ff`), pushed both, deleted feature branch. Note: `tests/test_phase1.5_regression.py` has a pre-existing pytest collection error (unrelated, present on baseline). | Phase 2 suite 12/12 green; ruff no new violations; `main` == `origin/main` == `a8120a5`, `dev` == `origin/dev` == `b6b3b53`; working tree clean                            |
| 2026-08-21 | 2     | Phase 2 fully pushed to GitHub (feature → dev → main). EP3 + YR2 remaining plan/spec written to `docs/superpowers/` and committed; plan/spec/review logs reorganized under `docs/superpowers/{plans,specs,reviews}/`. Convention recorded: all future plans/specs go in the superpowers folder.                                                                                                                                                                                                                                                                                                                                                           | Phase 2 tests 10/10 green; branches synced; working tree clean                                                                                                             |
| 2026-08-19 | 0     | Created `.venv` (Python 3.13.1). Backend scaffold: `pyproject.toml` (fastapi, uvicorn, pymupdf, shapely), `app/main.py` (`/` + `/health`), tests, ruff clean. Frontend scaffold: Next.js 16 (TS, Tailwind v4, App Router) at `frontend/`, `page.tsx` calls backend `/health`.                                                                                                                                                                                                                                                                                                                                                                             | pytest 2 passed, ruff clean, `npm run build` green, e2e smoke: frontend rendered backend status `healthy`                                                                  |
| 2026-08-19 | 0     | Phase 0 complete: SQLite DB layer (SQLAlchemy models), Alembic migration for initial schema, env files for both projects, git consolidation into single monorepo, sample fixture registered, `/health` reports DB status.                                                                                                                                                                                                                                                                                                                                                                                                                                 | pytest 11 passed, ruff clean, `alembic upgrade head` applies (15 tables), app boots (`/health` → `{"status":"healthy","db":"ok"}`), `npm run lint` + `npm run build` green |

## Open items / next actions

- [ ] **Phase 2.5 — Spec v3 alignment** (see `Phases.md` for full DoD): Input Quality Gate + flattened-sample spike; clustering migration DBSCAN → distance-threshold union-find; raster spike (classical-CV template matching vs vector ground truth); quarantine ultralytics; `source_quality` Alembic migration; review-time instrumentation + `/review-metrics`; declare or drop `scikit-learn` in `pyproject.toml`.
- [ ] **Environment (this machine):** recreate `backend/.venv` and reinstall deps (venv missing as of 2026-08-22); restore sample PDF to `data/samples/` from the project owner (gitignored by design, absent locally).
- [ ] Confirm price catalog source + single-tenant deployment with owner.
- [ ] Post-Phase-0: PostgreSQL migration + object storage.

## Dev commands (Phase 0 baseline)

```bash
# One-time: activate the venv (from repo root, Git Bash)
source backend/.venv/Scripts/activate
# Prompt changes to (venv) ... ; verify: which python → backend/.venv/Scripts/python

# Backend — venv lives INSIDE backend/ (self-contained)
cd backend
#   Option A (recommended — activate first, then plain commands):
python -m uvicorn app.main:app --reload --port 8000
#   Option B (no activation — full path):
backend/.venv/Scripts/python -m uvicorn app.main:app --reload --port 8000
#   --reload = FastAPI "hot reload": file save → auto-restart

# Tests + lint (from backend/)
python -m pytest -q
python -m ruff check app tests

# DB migrations (from backend/, uses DATABASE_URL from .env)
python -m alembic upgrade head          # apply pending migrations
python -m alembic revision --autogenerate -m "describe change"   # new migration

# Deactivate when done (only if you activated)
deactivate

# Frontend (from frontend/) — Turbopack dev server
npm run dev            # http://localhost:3000 — Fast Refresh (HMR): save → instant update, no reload
npm run build && npm start   # production preview
```

The two dev servers run independently; the frontend reaches the backend at `NEXT_PUBLIC_API_URL` (default `http://127.0.0.1:8000`).

## Decisions that must not be re-litigated

- Hybrid, vector-first, rules-driven, human-verified architecture. **Spec v3 framing:** vector-first is the *preferred* path when available, not the *assumed default input* — every upload passes the Input Quality Gate first.
- No LLM/vision model ever outputs a final quantity (see `Rules.md`).
- **Ultralytics YOLOv8 is NOT in the default stack** — AGPL-3.0 requires an Enterprise License even for internal-only proprietary use (vendor-confirmed, spec v3 §7.7/§9). Raster = OpenCV legend matching + Detectron2 (Apache-2.0) + rotation-aware OCR.
- **Clustering target is deterministic distance-threshold union-find**, not DBSCAN (spec v3 §7.4); DBSCAN in `vector.py` is legacy pending Phase 2.5 migration.
- Raster fallback history: Phase 1.5 done with the old technique; v3 re-proofs it via spike before production reliance.
- Closed/internal single-company first; generalization is a later decision (strengthened by spec v3 §5.5: only closed deployment makes the re-export loop-back actionable).
- Import PyMuPDF as `pymupdf`, never `fitz`.
- SQLite file-based DB for Phase 0 (works serverless + server); PostgreSQL swap later via `DATABASE_URL` (owner decision 2026-08-19).

## Known issues / gotchas

- **Code-vs-v3 gaps (as of 2026-08-22, all tracked as Phase 2.5):** `classify_upload()` is a binary vector/raster heuristic with no layer-richness scoring; `vector.py` uses sklearn DBSCAN (`eps=5.0, min_pts=2`); no `source_quality` column anywhere in DB models; `LAYER`/`SCHEDULE_BLOCK` tables designed but not migrated (`Component.source_layer` is a plain string); no review-time logging or `/quality`, `/request-reexport`, `/review-metrics` endpoints.
- **Environment drift on this machine (2026-08-22):** `backend/.venv` is missing — recreate before running backend commands. Sample PDF absent from `data/samples/` (gitignored client drawing; README says obtain from owner). `scikit-learn` is imported by `app/ingestion/vector.py` and `app/raster/yolo_detection.py` but not declared in `pyproject.toml`. Heavy ML deps (`ultralytics`, `detectron2`, `paddleocr`) are intentionally import-gated optionals — code degrades gracefully without them.
- Only live API routes: `/`, `/health`, `POST /api/e2e/run`, `POST /api/catalog/import`, `GET /api/catalog/` — everything else in Architecture.md §7 is planned, not built.
- 8 assembly YAML files exist in `data/assemblies/` (Phases.md previously miscounted 9; fixed).
- **All plans, specs, and code-review logs live in `docs/superpowers/{plans,specs,reviews}/`** — written with the superpowers workflow (brainstorming → spec, writing-plans → plan). Never create plan/spec docs elsewhere. Existing plan/spec docs moved there 2026-08-21 (`2026-08-20-phase-2-electrical-plan/spec.md`, `2026-08-21-phase-2-remaining-plan/spec.md`, `2026-08-21-phase-2-ep3-yr2-plan/spec.md`, etc.). File reorganization also 2026-08-21: `implementation_plan.md` moved to `docs/superpowers/plans/`, root `new.md` renamed to `architecture_decision.md`, `GIT_WORKFLOW.md` renamed to `git-workflow.md`, `AEC-Blueprint-System-Design-Spec.md` renamed to `AEC-System-Design-Spec.md`. Orphan placeholder `phase-0-foundation-feature.txt` removed.
- venv lives at `backend/.venv` when present. Use `python -m <tool>` instead of `<tool>.exe` — console-script exes (pytest.exe, ruff.exe) embed the old absolute path and break after a move.
- `pip install --upgrade pip` inside a running venv failed with WinError 32 (file locked). Recreate venv + install instead; skip pip upgrades.
- pip 24.3 ignores PEP 735 `[dependency-groups]`; dev tools (pytest, ruff) installed explicitly.
- Single git repo at the root; the nested `frontend/.git` from `create-next-app` was removed so backend + frontend + docs share one history.
