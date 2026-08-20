# Memory — Project Progress Tracker

> Created once coding begins. The AI updates this at the end of every working session so a fresh chat/agent can resume without re-reading the codebase.
>
> **Before starting work:** read this file first. If it's stale, skim `docs/` and recent commits.

---

## Project snapshot

- **Project:** AEC Blueprint Intelligence System (construction QTO / cost estimating)
- **Docs of record:** `docs/PRD.md`, `docs/Architecture.md`, `docs/Rules.md`, `docs/Phases.md`, `docs/Design.md`, `docs/AEC-Blueprint-System-Design-Spec.md`
- **Current phase:** Phase 0 — Foundation (✅ done)
- **Status summary:** Phase 0 — Foundation (✅ done). Backend + frontend scaffolded; SQLite DB layer with SQLAlchemy + Alembic migration; fixture registered; all DoD gates green.
- **Python:** `C:\Users\Huzaifa\AppData\Local\Programs\Python\Python313\python.exe` (3.13.15)

---

## Progress log

| Date | Phase | What was done | Verified by |
|---|---|---|---|
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

- venv lives at `backend/.venv` (moved 2026-08-19 from repo root so the FastAPI project is self-contained). Use `python -m <tool>` instead of `<tool>.exe` — console-script exes (pytest.exe, ruff.exe) embed the old absolute path and break after a move.
- `pip install --upgrade pip` inside a running venv failed with WinError 32 (file locked). Recreate venv + install instead; skip pip upgrades.
- pip 24.3 ignores PEP 735 `[dependency-groups]`; dev tools (pytest, ruff) installed explicitly.
- Single git repo at the root; the nested `frontend/.git` from `create-next-app` was removed so backend + frontend + docs share one history.

## Environment notes

- Windows (win32), shell: bash.
- Python 3.13.15 at `C:\Users\Huzaifa\AppData\Local\Programs\Python\Python313\python.exe`