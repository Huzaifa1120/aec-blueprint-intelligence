# Bun + Playwright E2E Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Browser e2e coverage of every frontend page via `@playwright/test` run through Bun, with a "mocked" project (default, zero backend needed) and a "live" project (same specs against the real stack) selected by `--project`.

**Architecture:** One `playwright.config.ts` with two projects sharing one spec suite. An auto-fixture installs `page.route("**/api/**")` mock handlers unless the project is `live`; unmocked API calls throw. Config's `webServer` starts only `next dev` (:3000); the live project documents uvicorn :8000 as a manual prerequisite.

**Tech Stack:** Bun 1.4 (package manager + script runner), `@playwright/test` (devDep), Chromium, Next.js 16 dev server.

**Spec:** `docs/superpowers/specs/2026-08-25-bun-playwright-e2e-design.md`

## Global Constraints

- Package manager is Bun ≥1.4 — every command uses `bun` / `bunx`, never `npm` / `npx`.
- Only new dependency allowed: `@playwright/test` (devDependencies).
- Chromium only (`devices["Desktop Chrome"]`); no WebKit/Firefox projects.
- Platform: Windows x64, Git Bash. Repo root: `aec-blueprint-intelligence/`; all FE commands run from `frontend/`.
- TypeScript strict mode applies to `e2e/` (tsconfig covers `**/*.ts`); `@/*` alias → `./src/*`.
- Match repo prettier style (double quotes, no semicolons — verify with `bun run format:check`).
- Do NOT touch unrelated working-tree changes (design-system WIP files, docs/Design.md).
- Never modify app source under `src/` except: adding `exclude` for e2e in vitest config if needed.
- Commit after every task; pre-commit hook runs eslint+tsc+prettier via bun (already migrated).

## Verified UI contract (from source, 2026-08-25)

- Routes: `/` (upload), `/estimates`, `/estimates/[id]`, `/catalog`.
- API base: `NEXT_PUBLIC_API_URL ?? "http://127.0.0.1:8000"` (cross-origin from :3000 — `page.route("**/api/**")` intercepts it fine).
- Endpoints hit by UI: `POST /api/drawings/check` (multipart) → `DrawingQualityCheck & {drawing_id?}`; `GET /api/drawings/{id}/quality`; `POST /api/e2e/run?persist=true` (multipart) → `E2eRunResult`; `GET /api/estimates?page=&per_page=` → `EstimateListResponse`; `GET /api/estimates/{id}/boq` → `EstimateBoq`; `GET /api/catalog/` → `CatalogEntry[]`; `POST /api/review/sessions` → `{session_id}`; `POST /api/review/sessions/{id}/close|actions`; `GET /api/narration/estimates/{id}` (only when Scope-of-work tab opened).
- Types of record: `src/types/drawing.ts`, `src/types/estimate.ts`, `src/types/api.ts` (`MeasurementStatus = "MEASURED" | "DERIVED" | "ASSUMED"`).
- Selectors of record: `[data-testid="dropzone"]`, `[data-testid="quality-gate-badge"]`, `[data-testid="boq-table"]`, `[data-testid="boq-row"]`, `[data-testid="accept-all"]`, `[data-testid="discipline-tabs"]`, `input[type="file"]` (dropzone), `[aria-label="Upload drawing PDF"]`, `[aria-label="Export format"]`, `[aria-label="Search catalog"]`, `[data-testid="catalog-table"]`, nav links "Estimates"/"Catalog", headings "Upload a drawing to begin"/"Estimates"/"Takeoff workspace".

---

### Task 1: Install Playwright under Bun

**Files:**
- Modify: `frontend/package.json` (devDependency + 3 scripts)

**Interfaces:**
- Produces: scripts `test:e2e`, `test:e2e:live`, `test:e2e:ui`; binary via `bunx playwright`.

- [ ] **Step 1: Add dependency and scripts**

```bash
cd frontend
bun add -d @playwright/test
```

Then edit `package.json` scripts, adding:

```json
"test:e2e": "playwright test --project=mocked",
"test:e2e:live": "playwright test --project=live",
"test:e2e:ui": "playwright test --ui"
```

- [ ] **Step 2: Install the Chromium browser**

```bash
bunx playwright install chromium
```

Expected: "Chromium … downloaded to …" (skip if already cached).

- [ ] **Step 3: Verify runner**

```bash
bunx playwright --version
```

Expected: prints `Version 1.x`.

- [ ] **Step 4: Commit**

```bash
git add frontend/package.json frontend/bun.lock
git commit -m "feat(e2e): add @playwright/test under bun with test:e2e scripts"
```

---

### Task 2: Config + fixtures + mocks + first smoke spec (make one spec green)

**Files:**
- Create: `frontend/playwright.config.ts`
- Create: `frontend/e2e/fixtures.ts`
- Create: `frontend/e2e/mocks/api.ts`
- Test: `frontend/e2e/home-upload.spec.ts`
- Modify (conditional): `frontend/vitest.config.ts` — exclude `e2e/**` so vitest never collects `*.spec.ts` from `e2e/`

**Interfaces:**
- Consumes: nothing.
- Produces:
  - `test`/`expect` exported from `e2e/fixtures.ts`; fixtures `mockApi: void` (auto) and `consoleErrors: string[]` (auto).
  - `installApiMocks(page: Page): Promise<void>` from `e2e/mocks/api.ts` (Tasks 3–4 extend its route table).
  - Shared constant `ESTIMATE_ID = "est-e2e-1"` exported from `e2e/mocks/api.ts`.

- [ ] **Step 1: Write the failing smoke spec** (`e2e/home-upload.spec.ts`)

```ts
import { expect, test } from "./fixtures"

test("home renders shell, heading and nav", async ({ page, consoleErrors }) => {
  await page.goto("/")
  await expect(page.getByRole("heading", { name: "Upload a drawing to begin" })).toBeVisible()
  await expect(page.getByRole("link", { name: "Estimates" })).toBeVisible()
  await expect(page.getByRole("link", { name: "Catalog" })).toBeVisible()
  expect(consoleErrors.filter((line) => !line.includes("favicon"))).toEqual([])
})
```

- [ ] **Step 2: Run it to verify it fails**

```bash
bun run test:e2e
```

Expected: FAIL — "playwright.config.ts" missing / cannot find `./fixtures`.

- [ ] **Step 3: Write `playwright.config.ts`**

```ts
import { defineConfig, devices } from "@playwright/test"

const port = Number(process.env.PORT ?? 3000)
const baseURL = `http://localhost:${port}`

export default defineConfig({
  testDir: "./e2e",
  fullyParallel: true,
  forbidOnly: !!process.env.CI,
  retries: 0,
  reporter: [["list"]],
  use: {
    baseURL,
    trace: "retain-on-failure",
    ...devices["Desktop Chrome"],
  },
  projects: [
    { name: "mocked" },
    { name: "live" },
  ],
  webServer: {
    command: "bun run dev",
    url: baseURL,
    reuseExistingServer: !process.env.CI,
    timeout: 180_000,
  },
})
```

- [ ] **Step 4: Write `e2e/fixtures.ts`**

```ts
import { test as base, expect } from "@playwright/test"

import { installApiMocks } from "./mocks/api"

export const test = base.extend<{
  mockApi: void
  consoleErrors: string[]
}>({
  mockApi: [
    async ({ page }, use, testInfo) => {
      // Phase switch: identical specs run against mocks ("mocked") or the
      // real stack ("live"); only the project decides.
      if (testInfo.project.name !== "live") {
        await installApiMocks(page)
      }
      await use()
    },
    { auto: true },
  ],
  consoleErrors: [
    async ({ page }, use) => {
      const errors: string[] = []
      page.on("console", (message) => {
        if (message.type() === "error") errors.push(message.text())
      })
      page.on("pageerror", (error) => errors.push(String(error)))
      await use(errors)
    },
    { auto: true },
  ],
})

export { expect }
```

- [ ] **Step 5: Write `e2e/mocks/api.ts`** (full initial route table — later tasks extend, never rewrite)

```ts
import type { Page } from "@playwright/test"

import type { DrawingQualityCheck } from "@/types/drawing"
import type { EstimateBoq, EstimateListResponse, NarrationResponse } from "@/types/estimate"
import type { CatalogEntry } from "@/types/catalog"

export const ESTIMATE_ID = "est-e2e-1"

const QUALITY_CHECK: DrawingQualityCheck & { drawing_id: string } = {
  verdict: "layered_vector",
  metrics: {
    distinct_ocg_count: 45,
    tagged_paths: 1188,
    total_paths: 3417,
    tagged_path_fraction: 0.3474,
    has_extractable_text: true,
  },
  image_count: 0,
  loop_back_message: null,
  drawing_id: "draw-e2e-1",
}

const ESTIMATE_LIST: EstimateListResponse = {
  items: [
    {
      estimate_id: ESTIMATE_ID,
      project_name: "MMC-JVC Tower — Electrical Takeoff",
      total_material_cost: 1553.0,
      total_labor_cost: 420.0,
      total_cost: 1973.0,
    },
  ],
  total: 1,
  page: 1,
  per_page: 20,
}

const BOQ: EstimateBoq = {
  estimate_id: ESTIMATE_ID,
  totals: { materials: 1553.0, labor: 420.0, grand: 1973.0 },
  routes: [
    {
      material_name: "Cable Tray 600 mm",
      quantity: 12.5,
      unit: "m",
      unit_cost: 45.2,
      unit_price: 45.2,
      total_cost: 565.0,
      unpriced: false,
      confidence_status: "MEASURED",
      size_source: "schedule",
      route_type: "tray",
      length_m: 12.5,
      size_json: null,
    },
  ],
  materials: [
    {
      material_name: "LED Floodlight 150 W",
      quantity: 26,
      unit: "each",
      unit_cost: 38.0,
      unit_price: 38.0,
      total_cost: 988.0,
      unpriced: false,
      confidence_status: "MEASURED",
      size_source: null,
    },
    {
      material_name: "Junction Box 100x100",
      quantity: 14,
      unit: "each",
      unit_cost: 12.0,
      unit_price: null,
      total_cost: null,
      unpriced: true,
      confidence_status: "ASSUMED",
      size_source: "assumed_default",
    },
  ],
}

const CATALOG: CatalogEntry[] = [
  {
    id: 1,
    name: "LED Floodlight 150 W",
    unit: "each",
    category: "Electrical",
    latest_unit_price: 38.0,
    effective_from: "2026-01-01",
  },
]

const NARRATION: NarrationResponse = {
  estimate_id: ESTIMATE_ID,
  provider: "template",
  narrative: "Scope of work placeholder narrative for e2e.",
}

const RUN_RESULT = {
  status: "vector",
  scale: "1:100",
  routes_measured: 1,
  components_found: 27,
  estimate_id: ESTIMATE_ID,
  boq_items: [],
  unmapped_items: [],
}

function fulfill(data: unknown, status = 200) {
  return { status, contentType: "application/json", body: JSON.stringify(data) }
}

export async function installApiMocks(page: Page): Promise<void> {
  await page.route("**/api/**", async (route) => {
    const request = route.request()
    const url = new URL(request.url())
    const method = request.method()

    if (method === "POST" && url.pathname === "/api/drawings/check") {
      return route.fulfill(fulfill(QUALITY_CHECK))
    }
    if (method === "GET" && /^\/api\/drawings\/[^/]+\/quality$/.test(url.pathname)) {
      return route.fulfill(fulfill(QUALITY_CHECK))
    }
    if (method === "POST" && url.pathname === "/api/e2e/run") {
      return route.fulfill(fulfill(RUN_RESULT))
    }
    if (method === "GET" && url.pathname === "/api/estimates") {
      return route.fulfill(fulfill(ESTIMATE_LIST))
    }
    if (method === "GET" && url.pathname === `/api/estimates/${ESTIMATE_ID}/boq`) {
      return route.fulfill(fulfill(BOQ))
    }
    if (method === "GET" && url.pathname === `/api/narration/estimates/${ESTIMATE_ID}`) {
      return route.fulfill(fulfill(NARRATION))
    }
    if (method === "GET" && url.pathname === "/api/catalog/") {
      return route.fulfill(fulfill(CATALOG))
    }
    if (method === "POST" && url.pathname === "/api/review/sessions") {
      return route.fulfill(fulfill({ session_id: "sess-e2e-1" }))
    }
    if (method === "POST" && /^\/api\/review\/sessions\/[^/]+\/(close|actions)$/.test(url.pathname)) {
      return route.fulfill(fulfill({}))
    }

    throw new Error(`Unmocked API call in mocked mode: ${method} ${url.toString()}`)
  })
}
```

If `CatalogEntry` requires different field names, align with `src/types/catalog.ts` (fields used by CatalogTable: `id`, `name`, `unit`, `category?`, `latest_unit_price`, `effective_from`).

- [ ] **Step 6: Guard vitest collection** — read `vitest.config.ts`; if its `include` can match `e2e/*.spec.ts` (default `**/*.{test,spec}.?(c|m)[jt]s?(x)` does), add `exclude: [...defaults, "e2e/**"]`; otherwise leave untouched and note why.

- [ ] **Step 7: Run the smoke spec until green**

```bash
bun run test:e2e
```

Expected: 1 passed (mocked project only). If the dev server races startup, re-run once before debugging.

- [ ] **Step 8: Commit**

```bash
git add frontend/playwright.config.ts frontend/e2e frontend/vitest.config.ts
git commit -m "feat(e2e): playwright config, mock fixtures, home smoke spec (green)"
```

---

### Task 3: Estimates list + workspace + catalog specs

**Files:**
- Test: `frontend/e2e/estimates.spec.ts`
- Test: `frontend/e2e/catalog.spec.ts`

**Interfaces:**
- Consumes: `test`, `expect` from `./fixtures`; mock data already routed (no mock changes expected).

- [ ] **Step 1: Write failing specs**

`e2e/estimates.spec.ts`:

```ts
import { expect, test } from "./fixtures"
import { ESTIMATE_ID } from "./mocks/api"

test("estimates index lists takeoffs and links to workspace", async ({
  page,
  consoleErrors,
}) => {
  await page.goto("/estimates")
  await expect(page.getByRole("heading", { name: "Estimates" })).toBeVisible()

  const rowLink = page.getByRole("link", { name: "MMC-JVC Tower — Electrical Takeoff" })
  await expect(rowLink).toBeVisible()
  await expect(page.getByText("1,973.00")).toBeVisible() // Total cost column

  await rowLink.click()
  await expect(page).toHaveURL(new RegExp(`/estimates/${ESTIMATE_ID}$`))
  expect(consoleErrors.filter((line) => !line.includes("favicon"))).toEqual([])
})

test("workspace shows BOQ rows, discipline tabs and export menu", async ({
  page,
  consoleErrors,
}) => {
  await page.goto(`/estimates/${ESTIMATE_ID}`)
  await expect(page.getByRole("heading", { name: "Takeoff workspace" })).toBeVisible()
  await expect(page.getByTestId("boq-table")).toBeVisible()
  await expect(page.getByTestId("boq-row").first()).toBeVisible()
  await expect(page.getByText("Cable Tray 600 mm")).toBeVisible()
  await expect(page.getByText("ASSUMED").first()).toBeVisible()
  await expect(page.getByTestId("discipline-tabs")).toBeVisible()
  await expect(page.getByLabel("Export format")).toBeVisible()
  expect(consoleErrors.filter((line) => !line.includes("favicon"))).toEqual([])
})
```

`e2e/catalog.spec.ts`:

```ts
import { expect, test } from "./fixtures"

test("catalog lists rates and search filters them", async ({ page, consoleErrors }) => {
  await page.goto("/catalog")
  await expect(page.getByTestId("catalog-table")).toBeVisible()
  await expect(page.getByRole("cell", { name: "LED Floodlight 150 W" })).toBeVisible()

  await page.getByLabel("Search catalog").fill("nothing-matches-this")
  await expect(page.getByText("No rates match your filters.")).toBeVisible()
  expect(consoleErrors.filter((line) => !line.includes("favicon"))).toEqual([])
})
```

- [ ] **Step 2: Run to verify they fail or reveal selector drift**

```bash
bun run test:e2e
```

Expected: previously-green smoke stays green; new specs either PASS (selectors correct) or fail on a specific mismatch. Fix ONLY selector/mock mismatches revealed (adjust spec selectors to actual DOM; extend mocks only if a genuinely missing endpoint appears — record any such addition in the commit message).

- [ ] **Step 3: Run full mocked suite green**

```bash
bun run test:e2e
```

Expected: 4 passed.

- [ ] **Step 4: Commit**

```bash
git add frontend/e2e
git commit -m "feat(e2e): estimates list, workspace BOQ and catalog specs (green)"
```

---

### Task 4: Upload interaction spec (dropzone → verdict → run → redirect)

**Files:**
- Test: `frontend/e2e/home-upload.spec.ts` (append second test)

**Interfaces:**
- Consumes: existing mocks (`/api/drawings/check`, `/api/drawings/{id}/quality`, `/api/e2e/run`, workspace endpoints after redirect).

- [ ] **Step 1: Append failing test** to `e2e/home-upload.spec.ts`

```ts
test("upload flow: check → quality verdict → run takeoff → workspace", async ({
  page,
  consoleErrors,
}) => {
  await page.goto("/")
  await page.locator('input[type="file"]').setInputFiles({
    name: "MMC-JVC-CD-ELEC-3902.pdf",
    mimeType: "application/pdf",
    buffer: Buffer.from("%PDF-1.4\n%e2e-fixture\n"),
  })

  await expect(page.getByTestId("quality-gate-badge")).toContainText(/layered/i)
  await page.getByRole("button", { name: "Run takeoff →" }).click()

  await expect(page).toHaveURL(new RegExp(`/estimates/${ESTIMATE_ID}$`))
  await expect(page.getByTestId("boq-table")).toBeVisible()
  expect(consoleErrors.filter((line) => !line.includes("favicon"))).toEqual([]),
})
```

(Import `ESTIMATE_ID` from `./mocks/api`; fix the trailing comma typo if introduced.)

- [ ] **Step 2: Run to verify it fails or passes; fix selector drift only**

```bash
bun run test:e2e -- home-upload
```

Expected: PASS. Known-risk spots: QualityGateBadge copy (does it contain "layered"?), dropzone file input visibility. Adjust the locator/assertion to actual DOM — never weaken the flow itself.

- [ ] **Step 3: Full suite green**

```bash
bun run test:e2e
```

Expected: 5 passed.

- [ ] **Step 4: Commit**

```bash
git add frontend/e2e/home-upload.spec.ts
git commit -m "feat(e2e): full mocked upload->takeoff->workspace flow spec"
```

---

### Task 5: Whole-repo gate + docs sync

**Files:**
- Modify: `AGENTS.md` (Frontend commands block — add `test:e2e` lines)
- Modify: `docs/Memory.md` (progress-log row + dev-commands block)

- [ ] **Step 1: Frontend gate**

```bash
bun run lint && bun run typecheck && bun run test && bun run format:check && bun run build
```

Expected: all green (vitest must NOT pick up e2e specs — confirms Task 2 Step 6).

- [ ] **Step 2: Full e2e suite once more**

```bash
bun run test:e2e
```

Expected: 5 passed.

- [ ] **Step 3: Update AGENTS.md frontend commands** — append inside the frontend bash block:

```bash
bun run test:e2e     # Playwright e2e, mocked API (no backend needed)
bun run test:e2e:live # same specs vs real backend — start uvicorn :8000 first
```

- [ ] **Step 4: Update docs/Memory.md** — add progress-log row: Bun+Playwright e2e landed (spec `docs/superpowers/specs/2026-08-25-bun-playwright-e2e-design.md`, plan `docs/superpowers/plans/2026-08-25-bun-playwright-e2e.md`), 5 specs green mocked, live project ready pending owner `persist` query-param fix; update dev-commands block.

- [ ] **Step 5: Commit**

```bash
git add AGENTS.md docs/Memory.md
git commit -m "docs: e2e commands + memory row for bun-playwright setup"
```

---

## Self-review notes

- Spec coverage: §5 layout → Tasks 1–4 files; §6 mocking rules → Task 2 Step 5 (unmocked throws); §7 coverage matrix → smoke+nav (Task 2), estimates/workspace/catalog (Task 3), upload verdict (Task 4), console-guard everywhere; §9 verification → Task 5. Phase-2 preview needs no task (documented behavior of `--project=live`).
- Placeholder scan: none — all code blocks concrete.
- Type consistency: `ESTIMATE_ID` defined once in `e2e/mocks/api.ts`, imported by fixtures? No — fixtures re-declares it. FIX APPLIED IN PLAN: fixtures exports nothing for it; specs import from `./mocks/api` (Task 3/4 use `./mocks/api`). Remove the duplicate export from fixtures if written — keep single source in `mocks/api.ts`.
