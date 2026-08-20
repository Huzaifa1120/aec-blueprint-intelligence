# Memory — Project Progress Tracker

> Created once coding begins. The AI updates this at the end of every working session so a fresh chat/agent can resume without re-reading the codebase.
>
> **Before starting work:** read this file first. If it's stale, skim `docs/` and recent commits.

---

## Project snapshot

- **Project:** AEC Blueprint Intelligence System (construction QTO / cost estimating)
- **Docs of record:** `docs/PRD.md`, `docs/Architecture.md`, `docs/Rules.md`, `docs/Phases.md`, `docs/Design.md`, `docs/AEC-Blueprint-System-Design-Spec.md`
- **Current phase:** Phase 2 — Full Electrical discipline (✅ done, all remaining EP3/YR2 items closed)
- **Status summary:** Phase 2 fully complete. EP3 (E2E pipeline validation on sample) + YR2 (persist_assembly_to_db) tests written, suite now 12/12 green, merged feature → dev → main and pushed. Working tree clean.
- **Python:** `C:\Users\Huzaifa\AppData\Local\Programs\Python\Python313\python.exe` (3.13.15)

---

## Progress log

| Date | Phase | What was done | Verified by |
|---|---|---|---|
| 2026-08-21 | 2 | **Phase 2 fully closed.** Executed `docs/superpowers/plans/2026-08-21-phase-2-ep3-yr2-plan.md` (Tasks 1–4 all `[x]`): wrote `test_ep3_e2e_pipeline_validation_on_sample` (gates E1–E9) and `test_yaml_rule_persistence_to_db` (gates Y1–Y5) in `backend/tests/test_phase2_regression.py` (now 12 tests). Fixed 2 new ruff violations in the appended code (E741 `l`, F811 `Material` redefinition) — no new violations vs baseline. Merged `feature/phase2-ep3-yr2` → dev → main (`--no-ff`), pushed both, deleted feature branch. Note: `tests/test_phase1.5_regression.py` has a pre-existing pytest collection error (unrelated, present on baseline). | Phase 2 suite 12/12 green; ruff no new violations; `main` == `origin/main` == `a8120a5`, `dev` == `origin/dev` == `b6b3b53`; working tree clean |
| 2026-08-21 | 2 | Phase 2 fully pushed to GitHub (feature → dev → main). EP3 + YR2 remaining plan/spec written to `docs/superpowers/` and committed; plan/spec/review logs reorganized under `docs/superpowers/{plans,specs,reviews}/`. Convention recorded: all future plans/specs go in the superpowers folder. | Phase 2 tests 10/10 green; branches synced; working tree clean |
| 2026-08-19 | 0 | Created `.venv` (Python 3.13.1). Backend scaffold: `pyproject.toml` (fastapi, uvicorn, pymupdf, shapely), `app/main.py` (`/` + `/health`), tests, ruff clean. Frontend scaffold: Next.js 16 (TS, Tailwind v4, App Router) at `frontend/`, `page.tsx` calls backend `/health`. | pytest 2 passed, ruff clean, `npm run build` green, e2e smoke: frontend rendered backend status `healthy` |
| 2026-08-19 | 0 | Phase 0 complete: SQLite DB layer (SQLAlchemy models), Alembic migration for initial schema, env files for both projects, git consolidation into single monorepo, sample fixture registered, `/health` reports DB status. | pytest 11 passed, ruff clean, `alembic upgrade head` applies (15 tables), app boots (`/health` → `{"status":"healthy","db":"ok"}`), `npm run lint` + `npm run build` green |

## Open items / next actions

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

- Hybrid, vector-first, rules-driven, human-verified architecture.
- No LLM/vision model ever outputs a final quantity (see `Rules.md`).
- Raster fallback is Phase 1.5, not MVP.
- Closed/internal single-company first; generalization is a later decision.
- Import PyMuPDF as `pymupdf`, never `fitz`.
- SQLite file-based DB for Phase 0 (works serverless + server); PostgreSQL swap later via `DATABASE_URL` (owner decision 2026-08-19).

## Known issues / gotchas

- **All plans, specs, and code-review logs live in `docs/superpowers/{plans,specs,reviews}/`** — written with the superpowers workflow (brainstorming → spec, writing-plans → plan). Never create plan/spec docs elsewhere. Existing plan/spec docs moved there 2026-08-21 (`2026-08-20-phase-2-electrical-plan/spec.md`, `2026-08-21-phase-2-remaining-plan/spec.md`, `2026-08-21-phase-2-ep3-yr2-plan/spec.md`, etc.).
- venv lives at `backend/.venv` (moved 2026-08-19 from repo root so the FastAPI project is self-contained). Use `python -m <tool>` instead of `<tool>.exe` — console-script exes (pytest.exe, ruff.exe) embed the old absolute path and break after a move.
- `pip install --upgrade pip` inside a running venv failed with WinError 32 (file locked). Recreate venv + install instead; skip pip upgrades.
- pip 24.3 ignores PEP 735 `[dependency-groups]`; dev tools (pytest, ruff) installed explicitly.
- Single git repo at the root; the nested `frontend/.git` from `create-next-app` was removed so backend + frontend + docs share one history.

## Environment notes

- Windows (win32), shell: bash.
- Python 3.13.15 at `C:\Users\Huzaifa\AppData\Local\Programs\Python\Python313\python.exe`