# Bun + Playwright E2E Testing — Design Spec

**Date:** 2026-08-25
**Status:** Approved in-session (owner picked: phased scope, Playwright via Bun, all-pages coverage, two-projects-one-config)
**Supersedes:** nothing (first browser-e2e setup for this repo)

---

## 1. Context

The frontend has vitest+RTL unit tests (jsdom, 61 passing) but no browser-level end-to-end
tests. The backend's "e2e" (`/api/e2e/run`, pytest integration suite) exercises the parsing
pipeline, not the UI. Bun 1.4 was adopted as the frontend package manager on 2026-08-25 and
officially supports `@playwright/test` on Windows/Chromium, making a Playwright-under-Bun
setup viable without Node/npm re-entry.

Known constraint carried from Memory.md: upload via the real UI is broken at the backend
contract level (`persist` must be a query param; one-line fix parked on owner approval).
Phase 1 mocks the API layer, so this bug does not block phase-1 tests.

## 2. Goal

Browser e2e coverage of every frontend page, runnable with one command under Bun, structured
so the same specs run against mocked API responses today and against the real backend later
by switching projects — no spec rewrites.

## 3. Non-goals (phase 1)

- Live-backend runs (phase 2; also blocked by the parked `persist` query-param fix)
- Multi-browser matrix (Chromium only; this is a Windows machine)
- CI pipeline integration (repo has no CI today)
- Visual regression testing

## 4. Decisions (owner-approved)

| Question | Ruling |
| --- | --- |
| Scope | Both phases: mocked now, live later via `bun run test:e2e:live` (`--project=live`) |
| Runner | `@playwright/test` installed + run through Bun (`bunx playwright test`) |
| Phase-1 surface | All pages including mocked upload → quality-gate verdict |
| Mock/live wiring | Two projects in one config ("mocked" default, "live" opt-in) |

## 5. Architecture

```
frontend/
  playwright.config.ts          # projects: "mocked" (default), "live" (E2E_LIVE=1)
  e2e/
    fixtures.ts                 # test extend: installs API mocks unless project === 'live'
    mocks/api.ts                # typed route.fulfill handlers mirroring backend contracts
    home-upload.spec.ts         # dropzone + quality-gate verdict UI (mocked)
    estimates.spec.ts           # index list rows → workspace links
    workspace.spec.ts           # BOQ table rows, confidence badges, export menu
    catalog.spec.ts             # catalog browse table
```

- **Deps:** `@playwright/test` as devDependency (bun-managed); Chromium binary via
  `bunx playwright install chromium`.
- **Scripts (package.json):**
  - `test:e2e` → `playwright test` (runs the `mocked` project)
  - `test:e2e:live` → runs the `live` project against a running stack
  - `test:e2e:ui` → `playwright test --ui`
- **Server orchestration:** config `webServer` starts only `next dev` (:3000). The `live`
  project requires uvicorn :8000 to already be running (documented prerequisite); Playwright
  never manages Python. Keeps the venv out of Playwright's concern.
- **Phase switch:** lives in `fixtures.ts` — `if (testInfo.project.name !== 'live')` install
  mocks. Identical specs execute in both modes.

## 6. Mocking rules

- Handlers fulfill **only known `/api/*` routes**, with payloads shaped like the real
  contracts (estimates list `{name, totals}`, BOQ payload items with `confidence_tier`,
  `size_source`, bbox-less per current backend reality, catalog rows, quality verdict,
  health/status).
- Any **unmocked** `/api/*` request fails its test loudly (abort + assertion) so contract
  drift surfaces instead of silently passing.
- Plain `page.route()` interception. No MSW. Zero extra mocking dependencies.

## 7. Coverage matrix (phase 1)

| Page | Assertions |
| --- | --- |
| `/` (upload) | Dropzone renders; mocked upload → quality-gate verdict badge appears |
| `/estimates` | Rows render from mock data; links navigate to workspace |
| `/estimates/[id]` | BOQ table renders mock rows; ConfidenceBadge tiers visible; export control present |
| `/catalog` | Browse table renders mock rows |
| every page | AppShell nav links present + console-error-free check |

## 8. Error handling / determinism

- Default timeouts; retries = 0 locally (deterministic mocks make flake a test smell).
- Unhandled API route → hard fail (see §6).
- Console errors (excluding known-benign dev overlays) fail the spec.

## 9. Verification

- `bun run test:e2e` green locally.
- Full frontend gate still green: eslint, tsc, vitest, prettier, next build.
- Docs updated post-implementation: AGENTS.md commands, docs/Memory.md session row.

## 10. Phase 2 preview (out of scope here)

Flip to `live`: start uvicorn :8000, run `bun run test:e2e:live`. Upload spec then requires
the owner-approved `persist` query-param fix first.
