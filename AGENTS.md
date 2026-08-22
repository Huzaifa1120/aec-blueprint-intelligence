# AGENTS.md

AEC Blueprint Intelligence System — construction quantity takeoff (QTO) / cost estimating. Hybrid, vector-first, rules-driven, human-verified architecture.

## Read first

- `docs/Memory.md` — session-state tracker; **read it before starting work and update it at the end of every session**.
- `docs/Architecture.md`, `docs/Rules.md`, `docs/Phases.md`, `docs/PRD.md`, `docs/Design.md` — docs of record. Current phase: 2 ✅ complete; **next: Phase 2.5 — Spec v3 Alignment** (`Phases.md`).
- `docs/AEC-Blueprint-System-Design-Spec-v3.md` — **sole source of truth**; supersedes v2, the original spec, and the Phase 3 addendum. If a task conflicts with it, it wins unless explicitly updated.
- `docs/architecture_decision.md` — architecture decision analysis (the "convergence" decision on hybrid vector-first approach).
- `docs/superpowers/reviews/` — code review logs (Phase 0, 1, 1.5, 2, Frontend, Backend); ruff/pytest/fallow compliance & trap constraints.
- `docs/superpowers/plans/`, `docs/superpowers/specs/` — all implementation plans and design specs. Every future plan and spec is written with the superpowers workflow and saved here (brainstorming → `docs/superpowers/specs/YYYY-MM-DD-<topic>.md`, writing-plans → `docs/superpowers/plans/YYYY-MM-DD-<feature>.md`). Do not create plan/spec docs anywhere else.

## Non-negotiable rule

AI proposes. Geometry calculates. Rules derive. Humans approve.

- No LLM/vision model ever outputs a final quantity, length, area, or price. Every BOQ number must trace to a deterministic calculation.
- Never assume an upload is layer-rich vector. Run the Input Quality Gate first (spec v3 §7.2); flag flattened files `degraded_vector` instead of silently parsing them as the happy path.
- No detector requiring an unbudgeted commercial license enters the stack. Ultralytics YOLOv8 (AGPL-3.0) is removed as default even for internal-only use; raster = OpenCV legend matching + Detectron2 (Apache-2.0) + rotation-aware OCR (spec v3 §7.7).
- Import PyMuPDF as `pymupdf`, never the deprecated `fitz` alias.
- Don't build multi-sheet features before the v1 vector MVP scope is exhausted. The raster path's old YOLOv8-based implementation is superseded by spec v3 — re-proof via the Phase 2.5 spike before production reliance.
- Unit prices / productivity rates live in catalog DB or YAML — never hardcode them in source.

## Layout

- `backend/` — FastAPI (Python ≥3.11). Entrypoint `app/main.py`; live routes: `/`, `/health`, `POST /api/e2e/run`, `POST /api/catalog/import`, `GET /api/catalog/`.
- `frontend/` — Next.js 16 App Router, React 19, Tailwind v4, TS strict. `@/*` path alias → `./src/*`.
- `data/samples/` — regression fixture `MMC-JVC-CD-ELEC-3902_AC-WIRE-Model.pdf` is a gitignored client drawing: obtain a copy from the project owner (absent locally as of 2026-08-22).
- `data/assemblies/` — YAML assembly rules (8 files); `data/layer_mapping.yaml` maps OCG layer names → rules.
- `docs/` — design docs (PRD, architecture decisions, rules, phases, design, spec v3). See `docs/architecture_decision.md` for the key architecture convergence decision.

## Commands

Backend — run from `backend/` (so `app` is importable), Git Bash on Windows:

```bash
python -m uvicorn app.main:app --reload --port 8000   # dev server
python -m pytest -q                                    # tests
python -m ruff check app tests                         # lint
python -m ruff format app tests                        # formatter
```

Frontend — run from `frontend/`:

```bash
npm run dev         # Turbopack dev server, http://localhost:3000
npm run lint        # eslint
npm run typecheck   # tsc --noEmit (build also typechecks)
npm run build       # production build = compile + typecheck
npm run format      # prettier write
npm run format:check
```

Frontend calls the backend at `NEXT_PUBLIC_API_URL` (default `http://127.0.0.1:8000`). The two dev servers run independently.

## Gotchas

- **Pre-commit quality gate:** `.githooks/pre-commit` runs ruff (staged `.py`) and eslint+tsc+prettier (staged frontend code). It is NOT active on fresh clones — enable once with `git config core.hooksPath .githooks`.
- Single git repo at the root (initialized 2026-08-19); `frontend/.git` was removed so backend + frontend + docs share one history.
- Sample PDF absent locally → 13 regression tests fail by design until restored (`data/samples/MMC-JVC-CD-ELEC-3902_AC-WIRE-Model.pdf`, obtain from project owner).
- Heavy ML deps (`ultralytics`, `detectron2`, `paddleocr`) are intentionally import-gated optionals — don't add them to `pyproject.toml`; they get installed ad hoc only when the Phase 2.5 raster spike needs them.
- `frontend/AGENTS.md` is auto-written by `next dev` and warns that this Next.js major version has breaking changes. Keep that file in diffs and read `node_modules/next/dist/docs/` before writing Next.js code.
- Use `python -m <tool>` instead of `<tool>.exe` — console-script exes can embed stale absolute paths after a venv move.
- Don't `pip install --upgrade pip` inside a running venv (WinError 32 file lock); recreate the venv instead.
- Pip ignores the `[dependency-groups]` in `pyproject.toml`; dev tools (pytest, ruff) are installed explicitly.