# Frontend Pages Round Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development. Steps use checkbox (`- [ ]`) syntax.

**Goal:** Implement the three v1 pages from spec §5 — Upload+Quality Gate (`/`), Estimate Workspace (`/estimates/[id]`), Catalog (`/catalog`) — on top of the landed design-system foundation, with graceful degradation where backend endpoints are missing.

**Architecture:** React Query owns server state (provider at root, plus the mandated root-level `TooltipProvider`); TanStack Table+Virtual render the BOQ; raw `pdfjs-dist` dual-canvas viewer per spec §4; resizable two-panel workspace. Server components fetch nothing initially — client components drive everything (upload/poll/mutate flows).

**Tech Stack:** existing foundation + new deps installed upfront by controller: `@tanstack/react-query`, `@tanstack/react-table`, `@tanstack/react-virtual`, `react-dropzone`, `react-resizable-panels`, `pdfjs-dist`.

## Global Constraints

- Work ONLY under `frontend/src/**` (+ package.json/lock via controller). Never touch `backend/`, `docs/`, git.
- Tokens only — zero hardcoded hex/API URLs. `NEXT_PUBLIC_API_URL` accessed solely via `src/lib/api.ts`.
- Every number renders mono: `font-mono tabular-nums`; unpriced rows show `[no rate]` chip — NEVER `$0.00`.
- ASSUMED rows cannot be bulk-accepted; `[R]` raster modifier wherever confidence badges render with `source_quality === 'raster'`.
- Missing-backend policy (FROZEN): `GET /api/estimates/{id}/status` does NOT exist → PipelineProgress polls BOQ readiness instead (indeterminate stage list); BOQ `source.bbox` does NOT exist → row click selects + PDF stays put with inline "No source region recorded for this item." Both surfaced as parked backend-gaps, not errors.
- Builders MUST read real response shapes from `backend/app/*/router.py` before typing endpoints (reading backend is required; writing it is forbidden).
- Gates per task: `npm run lint && npm run typecheck && npm test`; controller runs full sweep incl. build.

## Frozen Interfaces (all tasks bind to these)

```ts
// src/lib/api.ts
export const API_BASE = process.env.NEXT_PUBLIC_API_URL ?? "http://127.0.0.1:8000"
export async function apiGet<T>(path: string, signal?: AbortSignal): Promise<T>
export async function apiPost<T>(path: string, body?: unknown): Promise<T>
export async function apiPostForm<T>(path: string, form: FormData): Promise<T>
// src/app/providers.tsx  ('use client')
export default function Providers({ children }: { children: React.ReactNode })
// wraps <QueryClientProvider> + <TooltipProvider> (single root instance)
// src/hooks/useEstimateBoq.ts
export function useEstimateBoq(id: string): UseQueryResult<BoqItem[], Error>   // ['estimate', id, 'boq'], staleTime 30_000, refetchOnWindowFocus false
// src/hooks/usePipelineRun.ts
export function usePipelineRun():UseMutationError-first wrapper of apiPostForm('/api/e2e/run')
// src/hooks/useReviewSession.ts
export function useReviewSession(estimateId?: string): { sessionId: string | null; logAction: (a: ReviewAction) => Promise<void>; closeSession: () => Promise<void>; progress: { reviewed: number; total: number } }
```

---

### Task A: Wiring — providers, api lib, hooks, types (controller-implemented, serial)

Files: `src/app/providers.tsx` (new; mounted in `layout.tsx` replacing direct children), `src/lib/api.ts`, `src/types/{drawing,estimate,catalog}.ts`, `src/hooks/{useEstimateBoq,usePipelineRun,useCatalog,useReviewSession}.ts`. Types mirror router pydantic models (builders read routers; corrections to types allowed in their tasks). Root layout gains `<Providers>` + satisfies final-review mandate (root TooltipProvider lives here).

- [x] Deps installed by controller before dispatch
- [ ] Smoke: `npm run typecheck`

### Task B: Upload page `/` (parallel builder B)

Replace `src/app/page.tsx` shell with AppShell + centered column (spec §5.1): DropZone (react-dropzone, PDF-only ≤50MB, states idle/checking), calls `POST /api/drawings/check` then `GET /api/drawings/{id}/quality` (shape from `backend/app/drawings/router.py`); QualityGateBadge (●/◑/○ symbol + verdict chip + border-left tier color, canvas bg, no alert-box); DEGRADED flow renders ReexportRequest inline form (recipient email + editable pre-written layer-preservation message — copy text verbatim from spec §5.1); RASTER flow continues with CV note; `[Run takeoff →]` triggers usePipelineRun → on success `router.push(/estimates/${id})`. Components in `src/components/upload/`. Test: badge renders per verdict; wrong-file-type error copy exact per spec §8.

### Task C: Catalog page `/catalog` (parallel builder C)

AppShell + PageHeader + import card (react-dropzone CSV/XLSX → `POST /api/catalog/import`) with per-row humanised error display (spec §5.4 example format verbatim structure); browse table from `GET /api/catalog/` (rates `font-mono text-right`); empty state per §8; filter input client-side. Components in `src/components/catalog/`. Test: error-list rendering + rate cell classes.

### Task D: Estimate Workspace `/estimates/[id]` (parallel builder D — largest)

Server `page.tsx` shells `<WorkspaceClient estimateId>` ('use client'): react-resizable-panels TwoPanel (PDF 40% default, persisted via auto-save); left PDFViewer (dynamic ssr:false; worker via `public/pdf.worker.min.mjs` copied from node_modules by controller; dual-canvas per spec §4; zoom ± controls + page label); right panel: discipline Tabs filter (client-side), BOQTable (@tanstack/react-table grouping by discipline + @tanstack/react-virtual), columns exactly per spec §5.3 table (Confidence 32px badge-only+tooltip, Item flex, Qty 96px mono right w/ commas+unit, Unit 48px, Rate 96px `[no rate]` warning chip→links /catalog, Total 104px semibold or `—` ink-300, Review 88px accept✓/reject✗/edit✏ cycling pending→accepted/rejected); row click sets selectedRowId → PDF attempts source highlight → bbox-missing fallback message per Global Constraints; sticky footer ReviewProgress N/M + Close session (useReviewSession lifecycle mount/unmount); Accept-All filters out ASSUMED then scrolls-to-first-assumed pulse (spec §7 code contract); Export Radix Select → window.location.href to `/api/exports/estimates/{id}/export?format=`; narration tab low-cost add (GET /api/narration/estimates/{id} into `<pre>`, spec §10 recommendation). CorrectionDialog = shadcn Dialog… NOT generated yet — builder adds `npx shadcn@latest add dialog select tabs` (allowed package.json consumer: controller pre-installs radix bits via same CLI before dispatch). Tests: table renders grouped mock rows w/ mono classes; ASSUMED excluded from bulk-accept logic (pure fn exported from `src/lib/bulkAccept.ts`: `pickBulkAcceptable(items)`).

### Task E: Drift guard + polish (parallel builder E — tiny)

Test asserting every hex literal in `src/app/design-system/page.tsx` COLOR data appears in `src/styles/tokens.css` (read fs in vitest via node). Plus delete `frontend/src/app/page.tsx` legacy `bg-[#...]` remnants if any survive Task B (they won't — B replaces file; then E is just the test).

## Integration & Review (controller)

Serial after all builders: prettier sweep → lint/typecheck/test → `npm run build` → fix-ups → single combined task-reviewer dispatch (briefs+diff) → fix loop → ledger → Memory.md row. No push/merge (owner deferred).
