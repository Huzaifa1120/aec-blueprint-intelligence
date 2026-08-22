# Memory — Project Progress Tracker

> Created once coding begins. The AI updates this at the end of every working session so a fresh chat/agent can resume without re-reading the codebase.
>
> **Before starting work:** read this file first. If it's stale, skim `docs/` and recent commits.

---

## Project snapshot

- **Project:** AEC Blueprint Intelligence System (construction QTO / cost estimating)
- **Docs of record:** `docs/PRD.md`, `docs/Architecture.md`, `docs/Rules.md`, `docs/Phases.md`, `docs/Design.md`, `docs/AEC-Blueprint-System-Design-Spec-v3.md` (**v3 supersedes v2 and the original spec**)
- **Current phase:** Phase 2.5 — Spec v3 Alignment (✅ done 2026-08-23). **Next: Phase 3 — Mechanical (HVAC)** (ducts, pipes, equipment, units; formula-based derivations traceable to route length) — see `Phases.md`.
- **Status summary:** Phase 2 fully complete (12/12 regression green, merged feature → dev → main). 2026-08-23: Phase 2.5 closed — the v3 deltas ARE implemented in code (Input Quality Gate, union-find clustering, `source_quality` schema + stamping, review-time instrumentation, ultralytics quarantine); raster path re-proof closed as documented dead-end per human ruling A (ORB/SIFT is the successor; see `Phases.md` amendment).
- **Python:** machine-dependent. This machine (user `saada`): venv EXISTS at `backend/.venv` (Python 3.13.1, full deps incl. opencv-python-headless; scikit-learn REMOVED 2026-08-22). Invocation convention: `backend/.venv/Scripts/python.exe -m ...` run from `backend/` — system python lacks project deps. The `C:\Users\Huzaifa\...` path recorded earlier is stale (different machine).

---

## Progress log

| Date       | Phase | What was done                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                             | Verified by                                                                                                                                                                |
| ---------- | ----- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| 2026-08-23 | 2.5   | **Phase 2.5 complete — all six items landed on `feature/phase-2.5-implementation` (HEAD `979a7c5`).** Input Quality Gate + `/drawings/{id}/quality` & `/request-reexport` endpoints + flattened/raster twin fixtures; DBSCAN → deterministic union-find clustering (sklearn removed from deps, numpy declared) with human-approved count re-baseline {door 2 / tray 1 / lighting 26}; raster spike → **human ruling A**: NCC non-discriminative (door 727 vs truth 2 at truth-ceiling 0.903 = 363× false positives), raster stays quarantined, ORB/SIFT named successor per spec v3 §7.7A, revisit on first real degraded upload — expressed as expected-xfail test, artifact `docs/superpowers/reviews/2026-08-22-raster-spike-report.md`; `source_quality` column + Alembic migration + e2e stamping + degraded multiplier (0.8); review-time instrumentation + `GET /projects/{id}/review-metrics` (≤10 min/sheet provisional target in config); ultralytics quarantined behind `ENABLE_LEGACY_YOLO=1`. Bonus correctness fix: route lengths pt→paper-mm→real-m conversion (was physically impossible magnitudes; tray now 0.752 m). | Full pytest suite green (63 passed + 1 expected xfail — raster spike per ruling A); ruff clean |
| 2026-08-22 | 2.5   | **Prerequisites done + quality gates enabled.** Recreated `backend/.venv` (Python 3.13.1) with full deps; declared missing deps in pyproject (`python-multipart`, `scikit-learn`); recreated `backend/.env` from example; `alembic upgrade head` OK. Baseline: pytest 28 passed / 13 failed — ALL 13 traced to the absent sample PDF (owner-supplied, fail-by-design). Fixed 60 pre-existing ruff violations incl. 2 latent F821 bugs (`LRModel` in prices.py, `np` in yolo_detection.py); ruff clean. Frontend: fixed ReviewOverlay.tsx broken JSX/type errors (template-literal className, stray-brace h1, trailing comma, ref-in-render, any-typing, dead handleAccept, axios→fetch); build+lint+typecheck green. Added prettier (+format scripts), `npm run typecheck`, and `.githooks/pre-commit` gate (ruff / eslint+tsc+prettier) enabled via `git config core.hooksPath .githooks`. AGENTS.md commands/gotchas refreshed to match. | pytest 28 passed/13 fixture-blocked; ruff exit=0; npm lint+build+format:check green |
| 2026-08-22 | 2.5   | **Docs synced to Design Spec v3.** Updated `PRD.md`, `Architecture.md`, `Rules.md`, `Phases.md`, `Design.md`, this file. Propagated: Input Quality Gate (§7.2), raster split rewrite — OpenCV legend matching default + Detectron2 only for region segmentation, YOLOv8 removed as default (AGPL Enterprise-License exposure) (§7.7/§9), DBSCAN → deterministic distance-threshold union-find clustering (§7.4), rotation-aware OCR (§7.7C), `source_quality` flag in canonical model/data model/UI, review-time-per-sheet metric (§7.13/§15), three new API endpoints (§10), Stage 1.5 raster spike re-scoped into Phases.md as **Phase 2.5** with DoD. Added implementation-status notes marking every v3 delta not yet in code. Old spec files (v2/original/addendum) removed; v3 committed via `feature/docs-spec-v3-alignment` → dev → main. | Cross-checked each claim against `backend/app/**`, `backend/pyproject.toml`, `data/assemblies/`, frontend tree (validation findings below)                                  |
| 2026-08-21 | 2     | **Phase 2 fully closed.** Executed `docs/superpowers/plans/2026-08-21-phase-2-ep3-yr2-plan.md` (Tasks 1–4 all `[x]`): wrote `test_ep3_e2e_pipeline_validation_on_sample` (gates E1–E9) and `test_yaml_rule_persistence_to_db` (gates Y1–Y5) in `backend/tests/test_phase2_regression.py` (now 12 tests). Fixed 2 new ruff violations in the appended code (E741 `l`, F811 `Material` redefinition) — no new violations vs baseline. Merged `feature/phase2-ep3-yr2` → dev → main (`--no-ff`), pushed both, deleted feature branch. Note: `tests/test_phase1.5_regression.py` has a pre-existing pytest collection error (unrelated, present on baseline). | Phase 2 suite 12/12 green; ruff no new violations; `main` == `origin/main` == `a8120a5`, `dev` == `origin/dev` == `b6b3b53`; working tree clean                            |
| 2026-08-21 | 2     | Phase 2 fully pushed to GitHub (feature → dev → main). EP3 + YR2 remaining plan/spec written to `docs/superpowers/` and committed; plan/spec/review logs reorganized under `docs/superpowers/{plans,specs,reviews}/`. Convention recorded: all future plans/specs go in the superpowers folder.                                                                                                                                                                                                                                                                                                                                                           | Phase 2 tests 10/10 green; branches synced; working tree clean                                                                                                             |
| 2026-08-19 | 0     | Created `.venv` (Python 3.13.1). Backend scaffold: `pyproject.toml` (fastapi, uvicorn, pymupdf, shapely), `app/main.py` (`/` + `/health`), tests, ruff clean. Frontend scaffold: Next.js 16 (TS, Tailwind v4, App Router) at `frontend/`, `page.tsx` calls backend `/health`.                                                                                                                                                                                                                                                                                                                                                                             | pytest 2 passed, ruff clean, `npm run build` green, e2e smoke: frontend rendered backend status `healthy`                                                                  |
| 2026-08-19 | 0     | Phase 0 complete: SQLite DB layer (SQLAlchemy models), Alembic migration for initial schema, env files for both projects, git consolidation into single monorepo, sample fixture registered, `/health` reports DB status.                                                                                                                                                                                                                                                                                                                                                                                                                                 | pytest 11 passed, ruff clean, `alembic upgrade head` applies (15 tables), app boots (`/health` → `{"status":"healthy","db":"ok"}`), `npm run lint` + `npm run build` green |

## Open items / next actions

- [x] ~~**Phase 2.5 — Spec v3 alignment**~~ ✅ complete 2026-08-23 — all six items landed (see `Phases.md` amendment for the raster-spike ruling A closure). ~~declare or drop scikit-learn~~ → removed from deps 2026-08-23.
- [ ] ORB/SIFT raster successor — trigger on first real degraded upload (spec v3 §7.7A; human ruling A).
- [ ] `labor_rates` model drift unmigrated (autogenerate strips it each time) — register or exclude LRModel.
- [ ] `renderer.py` reshape bug (4-channel) — `template_match` shim compensates; one-line upstream fix owed.
- [x] Restore sample PDF to `data/samples/` from the project owner (restored 2026-08-22; suite 63 green).
- [ ] Decide: delete redundant remote branch `feature/phase-2.5-spec-v3-alignment` (zero unique commits; superseded by `feature/phase-2.5-implementation`).
- [ ] Optional: apply `ruff format` across backend (not mass-run yet — avoids churn).
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

- **Code-vs-v3 gaps (updated 2026-08-23 — most closed by Phase 2.5 implementation):** ~~`classify_upload()` binary vector/raster heuristic, no layer-richness scoring~~ → Input Quality Gate landed (flattened-file calibration beyond the one sample still open); ~~`vector.py` sklearn DBSCAN (`eps=5.0, min_pts=2`)~~ → deterministic distance-threshold union-find landed w/ human-approved re-baseline {door 2, tray 1, lighting 26}; ~~no `source_quality` column anywhere in DB models~~ → `source_quality` column + endpoints landed; ~~no review-time logging or `/quality`, `/request-reexport`, `/review-metrics` endpoints~~ → review instrumentation + `/review-metrics` landed; ~~ultralytics importable by default~~ → quarantined behind `ENABLE_LEGACY_YOLO=1`; scikit-learn removed, numpy declared, opencv-python-headless added.
- **Still open from the gap list:** `LAYER`/`SCHEDULE_BLOCK` tables designed but not migrated (`Component.source_layer` is a plain string); Detectron2 Stage-2 scope.
- **Environment (fixed 2026-08-22):** `backend/.venv` recreated with all deps; `python-multipart` + `numpy` declared in `pyproject.toml`, scikit-learn removed and `opencv-python-headless` added (final dep state 2026-08-22); `backend/.env` recreated from `.env.example`. Sample PDF restored to `data/samples/` 2026-08-22 (still a gitignored client drawing by design); suite 63 green. Heavy ML deps (`ultralytics`, `detectron2`, `paddleocr`) are intentionally import-gated optionals — code degrades gracefully without them; ultralytics additionally quarantined behind `ENABLE_LEGACY_YOLO=1`; install ad hoc only for the raster spike.
- Only live API routes: `/`, `/health`, `POST /api/e2e/run`, `POST /api/catalog/import`, `GET /api/catalog/` — everything else in Architecture.md §7 is planned, not built.
- 8 assembly YAML files exist in `data/assemblies/` (Phases.md previously miscounted 9; fixed).
- **All plans, specs, and code-review logs live in `docs/superpowers/{plans,specs,reviews}/`** — written with the superpowers workflow (brainstorming → spec, writing-plans → plan). Never create plan/spec docs elsewhere. Existing plan/spec docs moved there 2026-08-21 (`2026-08-20-phase-2-electrical-plan/spec.md`, `2026-08-21-phase-2-remaining-plan/spec.md`, `2026-08-21-phase-2-ep3-yr2-plan/spec.md`, etc.). File reorganization also 2026-08-21: `implementation_plan.md` moved to `docs/superpowers/plans/`, root `new.md` renamed to `architecture_decision.md`, `GIT_WORKFLOW.md` renamed to `git-workflow.md`, `AEC-Blueprint-System-Design-Spec.md` renamed to `AEC-System-Design-Spec.md`. Orphan placeholder `phase-0-foundation-feature.txt` removed.
- venv lives at `backend/.venv` when present. Use `python -m <tool>` instead of `<tool>.exe` — console-script exes (pytest.exe, ruff.exe) embed the old absolute path and break after a move.
- `pip install --upgrade pip` inside a running venv failed with WinError 32 (file locked). Recreate venv + install instead; skip pip upgrades.
- pip 24.3 ignores PEP 735 `[dependency-groups]`; dev tools (pytest, ruff) installed explicitly.
- Single git repo at the root; the nested `frontend/.git` from `create-next-app` was removed so backend + frontend + docs share one history.
