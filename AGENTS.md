# AGENTS.md

AEC Blueprint Intelligence System — construction quantity takeoff (QTO) / cost estimating. Hybrid, vector-first, rules-driven, human-verified architecture.

## Read first

- `docs/Memory.md` — session-state tracker; **read it before starting work and update it at the end of every session**.
- `docs/Architecture.md`, `docs/Rules.md`, `docs/Phases.md` — docs of record. Current phase: 0 (Foundation).
- `docs/Phase-0-Code-Review-Log.md` — Phase 0 code quality analysis; ruff/pytest compliance & trap constraints.
- `docs/Phase-1-Code-Review-Log.md` — Phase 1 code quality analysis; ruff/pytest compliance & trap constraints.
- `docs/Phase-1.5-Code-Review-Log.md` — Phase 1.5 code quality analysis; fallow/rust compliance & trap constraints.
- `docs/Phase-2-Code-Review-Log.md` — Phase 2 code quality analysis; ruff/pytest compliance & trap constraints.
- `docs/Frontend-Code-Review-Log.md` — frontend code quality analysis; code review log from fallow scan.
- `docs/Backend-Code-Review-Log.md` — backend code quality analysis; ruff/pytest compliance & trap constraints.

## Non-negotiable rule

AI proposes. Geometry calculates. Rules derive. Humans approve.

- No LLM/vision model ever outputs a final quantity, length, area, or price. Every BOQ number must trace to a deterministic calculation.
- Import PyMuPDF as `pymupdf`, never the deprecated `fitz` alias.
- Don't build the raster/CV fallback (Phase 1.5) or multi-sheet features before the v1 vector MVP is proven.
- Unit prices / productivity rates live in catalog DB or YAML — never hardcode them in source.

## Layout

- `backend/` — FastAPI (Python ≥3.11; running 3.13.1). Self-contained venv at `backend/.venv`. Entrypoint `app/main.py` (only `/` and `/health` so far).
- `frontend/` — Next.js 16 App Router, React 19, Tailwind v4, TS strict. `@/*` path alias → `./src/*`.
- `data/samples/` — real PDF fixture: `MMC-JVC-CD-ELEC-3902_AC-WIRE-Model.pdf`.
- `docs/` — design docs (PRD, architecture decisions, rules, phases, spec).

## Commands

Backend — run from `backend/` (so `app` is importable), Git Bash on Windows:

```bash
python -m uvicorn app.main:app --reload --port 8000   # dev server
python -m pytest -q                                    # tests
python -m ruff check app tests                         # lint
```

Frontend — run from `frontend/`:

```bash
npm run dev       # Turbopack dev server, http://localhost:3000
npm run lint      # eslint
npm run build     # typechecks (there is no separate typecheck script)
```

Frontend calls the backend at `NEXT_PUBLIC_API_URL` (default `http://127.0.0.1:8000`). The two dev servers run independently.

## Gotchas

- Single git repo at the root (initialized 2026-08-19); `frontend/.git` was removed so backend + frontend + docs share one history.
- `frontend/AGENTS.md` is auto-written by `next dev` and warns that this Next.js major version has breaking changes. Keep that file in diffs and read `node_modules/next/dist/docs/` before writing Next.js code.
- Use `python -m <tool>` instead of `<tool>.exe` — the console-script exes embed an absolute path that breaks after the venv was moved.
- Don't `pip install --upgrade pip` inside the running venv (WinError 32 file lock); recreate the venv instead.
- Pip ignores the `[dependency-groups]` in `pyproject.toml`; dev tools (pytest, ruff) are installed explicitly.