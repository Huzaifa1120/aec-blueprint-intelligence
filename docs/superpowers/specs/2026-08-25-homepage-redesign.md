# Homepage Redesign — Workbench Split

**Date:** 2026-08-25
**Scope:** Frontend only. Route `/` (`frontend/src/app/page.tsx`), `DropZone`, entrance-motion CSS.
**Out of scope:** Header/footer (`AppShell.tsx`) untouched; no backend changes; no new routes or data.

## Goal

Redesign the homepage from a narrow single-column upload utility into a workbench layout that
introduces the product while keeping upload as the centerpiece. Strictly on-system: Safety
Authority palette (ink black / safety amber / paper / steel), Archivo Black headings, IBM Plex Mono
labels, signature components (`HazardStripe`, `GoggleLineDivider`, `ProtocolCard`). All motion uses
existing tokens from `frontend/src/styles/tokens.css`.

## Layout

Single centered column of three stacked bands inside `max-w-5xl`, vertical gap 8:

1. **Hero band** — ink-black rounded panel: hazard stripe across the top edge, mono eyebrow
   `HUZAIFA AEC · TAKEOFF`, headline "Upload a drawing to begin" promoted to display size
   (~40px mobile → ~52px desktop, Archivo Black), supporting line
   "AI proposes · Geometry calculates · Rules derive · Humans approve.", amber goggle divider.
2. **Workbench row** — two columns on `lg+`, stacked on mobile:
   - **Left:** enlarged drop zone (`min-h-64`) inside a bordered paper card. Quality-gate results
     render inline beneath it with today's exact behavior: spinner while checking → quality badge →
     degraded-vector re-export/continue-anyway flow → run button.
   - **Right:** ink-black `ProtocolCard` titled "Pipeline contract" with static rows:
     Verdict rule (`measured > derived > assumed`), Input (`PDF ≤ 50 MB`),
     Scale (`auto · flagged if assumed`), Output (`BOQ → review`).
     Content sourced from project docs; no prices or rates hardcoded.
3. **Steps strip** — three numbered service cards on one row (`sm+`; stacks below):
   `01 Quality gate`, `02 Deterministic takeoff`, `03 Human review`. Paper background, 1px steel
   border, mono labels, amber mini goggle-line under each title.

All existing page state logic is unchanged: phases `idle/checking/ready/running`, correlation-ID
fallback, quality-check failure copy, run-failure error state, navigation to `/estimates/{id}`.

## Component changes

- `DropZone`: add optional `className` prop merged onto the root drop area (backward-compatible).
  Root keeps `data-testid="dropzone"` and aria-label.
- `globals.css`: add `.rise-in` entrance keyframe utility plus stagger delay helpers, built on
  existing motion tokens (`--ease-out-snappy`, `--duration-base`).
- No changes to `AppShell`, any other route, or shared UI primitives beyond `DropZone`'s passthrough.

## Motion spec

| Element | Treatment |
|---|---|
| Page load | Hero → workbench → steps: opacity 0→1 + translateY(12px)→0, `--ease-out-snappy`, 220ms (`--duration-base`), 50ms stagger between bands. CSS animations (run off the main thread). |
| Drag-over | Border + icon color shift and icon translateY(-2px); transitions name exact properties (`transition-colors`, `transition-transform`). |
| Phase change | Incoming blocks (spinner, quality section) reuse `.rise-in`. |
| Step-card hover | Border/color change only — no transform, no hover gating required. |

Rules honored: transform/opacity only; no `scale(0)` entrances; no `ease-in`; nothing
keyboard-initiated animates; durations ≤ 300ms for UI states. Reduced motion: global token zeroing
in `tokens.css` (`prefers-reduced-motion`) makes entrances instant — codebase convention retained.

Purpose tiers: page-load stagger = explanation/delight (rare tier, allowed); drag-over and phase
changes = state indication.

## Compatibility guarantees

- Preserve `id="upload-heading"`, all `aria-label`s, `data-testid="dropzone"` — unit tests and
  Playwright e2e depend on them.
- No copy changes to rejection/error messages (`WRONG_FILE_TYPE_COPY`, etc.).
- `DropZone` remains import-compatible for existing consumers/tests.

## Verification

- `bun run typecheck`, `bun run lint`, `bun run format:check`
- Unit tests (`upload.test.tsx` and full suite) pass unchanged or updated only for added className
- `bun run test:e2e` (mocked API) green
- Manual feel-check of load stagger (DevTools slow-motion) and reduced-motion instant rendering
