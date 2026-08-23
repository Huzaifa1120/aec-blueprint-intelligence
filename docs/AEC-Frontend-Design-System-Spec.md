# AEC Blueprint Intelligence — Frontend Design System & Spec

**Document type:** Design system + page-level frontend spec
**Stack locked:** Next.js 16 (App Router) · React 19 · TypeScript strict · Tailwind CSS v4
**Governs:** every visual and interaction decision in `frontend/`
**Read alongside:** `docs/AEC-Blueprint-System-Design-Spec-v3.md` (especially §2 guiding principle, §7.2 Input Quality Gate, §7.12 confidence tiering, §10 API surface)
**Does not cover:** backend changes, assembly rules, cost engine — those are in the v3 spec.

---

## 0. Design Identity

### Subject, audience, single job
Subject: a precision measurement instrument that reads construction drawings and produces an auditable bill of quantities. Audience: estimators, quantity surveyors, project engineers — people who know a drawing set, trust a scale bar, and will immediately spot a number that can't be traced to its source. Single job of every screen: **show where a number came from, and let the human decide whether to trust it.**

### Design direction — "Technical Daylight"

This system lives in a world of drafting tables, blueprint paper, calipers, and surveyors' total stations. The UI should feel like a precision instrument operating in daylight — not a dark terminal, not a marketing page, not a generic admin panel. The palette is a muted, vellum-derived blue-white for surfaces, with deep blueprint navy for structure and carefully rationed accents.

The signature element is **monospaced data everywhere.** Every quantity, measurement, length, area, rate, and total is set in a geometric monospace face — not because it's retro, but because construction quantities are columnar data where 1,284.50m and 999.99m must align digit-for-digit. When a reviewer scans forty BOQ rows, the difference between `1,284.50` and `  999.99` should be readable in one glance. This is a precision instrument; the type treatment says so.

The aesthetic risk: **the confidence-tier badge system uses geometric SVG symbols** drawn from the drafting world — a filled circle (●) for measured, a half-filled circle (◑) for derived, an open circle (○) for assumed, a dash (—) for unmapped — rather than colored text labels or dot-only indicators. Symbol + color + label, three redundant signals, immediately parseable even to someone who doesn't remember which color means what.

---

## 1. Token System

All tokens are CSS custom properties declared in `src/styles/tokens.css` and consumed via Tailwind v4's `@theme` block. Never hardcode hex values in component files.

### 1.1 Color

```css
@theme {
  /* ── Ink scale (blue-navy) ──────────────────── */
  --color-ink-900:   #0B1929;   /* deepest — main headings, nav chrome */
  --color-ink-700:   #1A3050;   /* body text */
  --color-ink-500:   #3E618A;   /* secondary text */
  --color-ink-300:   #7A9FBF;   /* captions, disabled text */
  --color-ink-100:   #C8D8EA;   /* dividers, input borders */
  --color-ink-50:    #E8EEF5;   /* row hover, input background */

  /* ── Canvas (page surfaces) ─────────────────── */
  --color-canvas:    #F2F5F9;   /* page background — muted blue-white, like vellum */
  --color-surface:   #FFFFFF;   /* card / panel background */

  /* ── Accent (interactive) ───────────────────── */
  --color-accent:    #0072CF;   /* primary interactive — engineering blue (Pantone Process Blue adj.) */
  --color-accent-lt: #E0F0FF;   /* accent wash — hover backgrounds, selected row */

  /* ── Confidence tier ────────────────────────── */
  --color-measured:  #0DA56A;   /* emerald — geometry-verified */
  --color-derived:   #6B4FF8;   /* violet — rule-calculated */
  --color-assumed:   #D97706;   /* amber — inferred / default */
  --color-unmapped:  #7A9FBF;   /* ink-300 — no assembly rule yet */

  /* ── Source quality ─────────────────────────── */
  --color-raster:    #E85D3A;   /* terracotta — raster-sourced, lower confidence */

  /* ── Semantic ───────────────────────────────── */
  --color-success:   #0DA56A;   /* = measured (intentional — same green) */
  --color-warning:   #D97706;   /* = assumed (intentional — same amber) */
  --color-error:     #C41E3A;   /* crimson */
  --color-info:      #0072CF;   /* = accent */
}
```

### 1.2 Typography

Two roles, one family, one mono companion:

| Role | Face | Usage |
|---|---|---|
| UI / body | **Geist Sans** (`next/font/google` or `next/font/local`) | All text that is not a number |
| Data / numbers | **Geist Mono** | Every quantity, rate, area, length, price — everywhere in the BOQ table |

**Type scale (Tailwind v4 — add to `@theme`):**
```css
@theme {
  --font-sans: 'Geist', ui-sans-serif, system-ui, sans-serif;
  --font-mono: 'Geist Mono', ui-monospace, 'Cascadia Code', monospace;

  /* Scale */
  --text-xs:   0.75rem;   /* 12px — captions, badges */
  --text-sm:   0.875rem;  /* 14px — table rows, secondary labels */
  --text-base: 1rem;      /* 16px — body */
  --text-lg:   1.125rem;  /* 18px — section headings */
  --text-xl:   1.25rem;   /* 20px — panel headers */
  --text-2xl:  1.5rem;    /* 24px — page titles */
  --text-3xl:  2rem;      /* 32px — upload hero */
}
```

**Usage rules:**
- BOQ quantity column: `font-mono text-sm tabular-nums text-right`
- BOQ rate column: `font-mono text-sm tabular-nums text-right`
- BOQ total column: `font-mono text-sm font-semibold tabular-nums text-right`
- All other table content: `font-sans text-sm`
- Page titles: `font-sans text-2xl font-semibold text-ink-900`

### 1.3 Spacing

Tailwind's 4px base. Key named uses:

| Token | px | Used for |
|---|---|---|
| `spacing-1` | 4 | tight inline gaps |
| `spacing-2` | 8 | badge padding, icon gap |
| `spacing-3` | 12 | table cell padding-y |
| `spacing-4` | 16 | table cell padding-x, card padding |
| `spacing-6` | 24 | section gap, panel gap |
| `spacing-8` | 32 | page section spacing |
| `spacing-12` | 48 | upload zone internal |
| `spacing-16` | 64 | hero spacing |

### 1.4 Shadow

Three levels only — never add more:
```css
@theme {
  --shadow-sm:  0 1px 3px 0 rgb(11 25 41 / 0.08);   /* card resting */
  --shadow-md:  0 4px 12px 0 rgb(11 25 41 / 0.12);   /* overlay, modal */
  --shadow-lg:  0 16px 40px 0 rgb(11 25 41 / 0.18);  /* command palette, drawer */
}
```

### 1.5 Motion

```css
@theme {
  --duration-fast:   120ms;
  --duration-base:   220ms;
  --duration-slow:   380ms;
  --ease-out:        cubic-bezier(0.16, 1, 0.3, 1);   /* snappy — panel opens, row expands */
  --ease-in-out:     cubic-bezier(0.4, 0, 0.2, 1);    /* symmetric — progress bars */
}

/* Source highlight — the signature animation */
/* See §5.3. Total duration 400ms. Respects prefers-reduced-motion. */
@media (prefers-reduced-motion: reduce) {
  * { --duration-fast: 0ms; --duration-base: 0ms; --duration-slow: 0ms; }
}
```

---

## 2. Component Decisions

### 2.1 Libraries — justified list

Every dependency added to `package.json` must appear here first with its justification. No other criteria.

| Package | Version | Why | License |
|---|---|---|---|
| `@radix-ui/react-dialog` | latest | Modal for corrections/confirmations — accessible, zero styling lock-in, Tailwind v4 compatible | MIT |
| `@radix-ui/react-tooltip` | latest | Confidence-tier tooltip on badge hover, provenance on cell hover | MIT |
| `@radix-ui/react-tabs` | latest | Discipline tabs in estimate workspace | MIT |
| `@radix-ui/react-select` | latest | Quality-gate action dropdown, export format picker | MIT |
| `@tanstack/react-table` | ^8 | BOQ table — discipline grouping, virtualized rows, sortable, typesafe | MIT |
| `@tanstack/react-query` | ^5 | Server state: BOQ fetch, pipeline polling, catalog — avoids prop-drilling and manual refetch logic | MIT |
| `@tanstack/react-virtual` | ^3 | Row virtualization inside TanStack Table — BOQ can have 400+ rows | MIT |
| `react-dropzone` | ^14 | Drag-and-drop PDF upload — handles file validation and drag states | MIT |
| `react-resizable-panels` | ^2 | Two-panel workspace (PDF ↔ BOQ) — mouse-draggable divider, persists width in localStorage | MIT |
| `pdfjs-dist` | ^4 | PDF rendering in review overlay — used raw (not `react-pdf`) for canvas control needed by the precision highlight | Apache-2.0 |
| `@phosphor-icons/react` | ^2 | Icons — engineering-adjacent aesthetics, not rounded-consumer-app feel | MIT |

**Explicitly not added:**
- ~~No shadcn/ui~~ — **superseded by owner ruling 2026-08-23 (see amendment above)**.

> **Amendment 2026-08-23 (owner ruling):** shadcn/ui v4 (`radix` base, `nova` preset — Lucide/Geist, matching the locked fonts) is adopted as the component layer. Radix primitives arrive via generated `src/components/ui/*`; `@phosphor-icons/react` is superseded by shadcn's default `lucide-react`. The Radix rows above remain accurate as transitive dependencies of generated components. Additional managed deps: `radix-ui`, `class-variance-authority`, `clsx`, `tailwind-merge`, `tw-animate-css`, `shadcn` (CLI). New dev-tooling rows (validation round): `vitest`, `jsdom`, `@testing-library/react`, `@testing-library/dom`, `@testing-library/jest-dom`, `@testing-library/user-event` (MIT; unit/render tests for design-system components). `@vitejs/plugin-react` deliberately NOT added — vitest's esbuild handles TSX via `jsx: "automatic"`, avoiding a Babel 7/8 peer conflict with shadcn's toolchain.
- No Zustand / Jotai — UI state stays in React `useState`/`useReducer` per component; React Query owns server state. The app isn't complex enough to need a global client store.
- No framer-motion — the signature animation (§5.3) is implemented in CSS transitions; no runtime animation library needed.

### 2.2 Core component inventory

Components built in-house, in `src/components/`:

```
src/components/
  layout/
    AppShell.tsx          — top nav bar + page wrapper
    TwoPanel.tsx          — react-resizable-panels wrapper (PDF + BOQ)
  upload/
    DropZone.tsx          — react-dropzone + visual states
    QualityGateBadge.tsx  — LAYERED_VECTOR | DEGRADED_VECTOR | RASTER verdict display
    ReexportRequest.tsx   — loop-back message form (degraded_vector flow)
  pipeline/
    PipelineProgress.tsx  — stage-by-stage progress (polled via React Query)
  estimate/
    BOQTable.tsx          — TanStack Table wrapper, grouped by discipline
    BOQRow.tsx            — single row: qty + mono numbers + confidence badge + review controls
    ConfidenceBadge.tsx   — the geometric symbol + color + label system (§6)
    ProvenanceTooltip.tsx — hover tooltip: source sheet, layer, calculation method
    UnpricedGap.tsx       — explicit "no rate" display for UNMAPPED rows (never $0)
    ReviewControls.tsx    — per-row Accept / Reject / Edit; ASSUMED rows blocked from bulk-accept
    ReviewProgress.tsx    — session progress bar (N of M reviewed)
  pdf/
    PDFViewer.tsx         — pdfjs-dist canvas renderer (§4)
    SourceHighlight.tsx   — the precision highlight overlay + crosshair animation
  catalog/
    CatalogTable.tsx      — browse existing prices
    CatalogImport.tsx     — drag CSV/Excel + humanised error display
  common/
    PageHeader.tsx
    Badge.tsx             — reusable colored badge (wraps the confidence-tier system)
    EmptyState.tsx
    ErrorState.tsx
    LoadingSpinner.tsx
    Tooltip.tsx           — thin Radix wrapper
```

---

## 3. Application Architecture

### 3.1 Routing (Next.js App Router)

```
src/app/
  layout.tsx                   — RootLayout: font loading, QueryProvider, AppShell wrapper
  page.tsx                     — Upload + Quality Gate
  estimates/
    [id]/
      page.tsx                 — Estimate Workspace (server component shell)
      EstimateClient.tsx       — 'use client' — TwoPanel, BOQTable, PDFViewer, review state
  catalog/
    page.tsx                   — Catalog (server component shell)
    CatalogClient.tsx          — 'use client' — import + browse
  providers.tsx                — 'use client' — QueryClientProvider wrapper
```

No `/estimates` list page in v1 — auth is out of scope, so there's no per-user project list. The upload page acts as the entry point; after processing, the browser navigates to `/estimates/[id]`. If a user bookmarks the estimate URL, the server component fetches and renders it directly.

### 3.2 Server vs Client Component Split

**Rule:** default to server components. Add `'use client'` only when a component uses browser APIs, event handlers, or React hooks. Never mark a component client just because it's "interactive."

| Component | Server or Client | Reason |
|---|---|---|
| `app/page.tsx` | Server | Static shell; children are client |
| `DropZone.tsx` | Client | `react-dropzone` uses browser File API |
| `QualityGateBadge.tsx` | Client | Receives API response as prop, no hooks needed — actually Server is fine if props are passed down |
| `app/estimates/[id]/page.tsx` | Server | Fetches initial BOQ from API via `fetch()` with `cache: 'no-store'` |
| `EstimateClient.tsx` | Client | Panel resize state, selected-row state, pdf.js canvas |
| `PDFViewer.tsx` | Client | Browser canvas API |
| `BOQTable.tsx` | Client | TanStack Table hooks, row click state |
| `PipelineProgress.tsx` | Client | Polling with React Query `refetchInterval` |
| `CatalogClient.tsx` | Client | File drop + import mutation |

### 3.3 Data Fetching

**React Query** for all server state. Configuration:

```typescript
// src/app/providers.tsx
const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 30_000,           // 30s — BOQ data doesn't change under the user
      retry: 2,
      refetchOnWindowFocus: false, // don't surprise a reviewer mid-edit
    },
  },
});
```

Key query keys and shapes (read actual router response shapes before coding — verify against `backend/app/*/router.py`):

```typescript
// BOQ data
queryKey: ['estimate', id, 'boq']
queryFn: () => fetch(`${API}/api/estimates/${id}/boq`).then(r => r.json())

// Pipeline status — polling until complete
queryKey: ['estimate', id, 'status']
queryFn: ...
refetchInterval: (data) => data?.status === 'complete' ? false : 2000

// Drawing quality
queryKey: ['drawing', drawingId, 'quality']
queryFn: () => fetch(`${API}/api/drawings/${drawingId}/quality`).then(r => r.json())

// Catalog
queryKey: ['catalog']
queryFn: () => fetch(`${API}/api/catalog/`).then(r => r.json())
```

**Mutations:**
- Upload + run pipeline: `useMutation` → `POST /api/e2e/run` (multipart)
- Review actions: `useMutation` → `POST /api/review/sessions/{id}/actions`, then `invalidateQueries(['estimate', id, 'boq'])`
- Catalog import: `useMutation` → `POST /api/catalog/import`
- Re-export request: `useMutation` → `POST /api/drawings/{id}/request-reexport`

### 3.4 State Management

No global store. State by locality:

| State | Location | Why |
|---|---|---|
| Server state (BOQ, catalog, pipeline) | React Query | |
| Selected BOQ row (drives PDF highlight) | `EstimateClient` `useState` | Lifted to common parent of both panels |
| PDF current page + zoom | `PDFViewer` `useState` | Local |
| Panel widths | `react-resizable-panels` internal + `localStorage` | Persisted across refreshes |
| Review session ID | `EstimateClient` `useState` | Created on mount via `POST /api/review/sessions` |
| Upload in-progress file | `page.tsx` `useState` | Local |
| Active discipline filter | `EstimateClient` `useState` | Local to the table |

---

## 4. pdf.js Integration

### Why raw `pdfjs-dist`, not `react-pdf`

`react-pdf` uses an older worker setup incompatible with pdf.js v4's `pdf.worker.mjs`. The precision source-highlight animation (§5.3) requires direct canvas access — specifically, drawing a second "overlay canvas" positioned absolutely over the main rendering canvas. `react-pdf` doesn't expose this. Use `pdfjs-dist` directly.

### Setup

```typescript
// src/components/pdf/PDFViewer.tsx
'use client';
import * as pdfjsLib from 'pdfjs-dist';

// Vite/Next.js: use a URL import for the worker.
// Never import the worker directly — it must run in a separate thread.
pdfjsLib.GlobalWorkerOptions.workerSrc = new URL(
  'pdfjs-dist/build/pdf.worker.mjs',
  import.meta.url,
).toString();
```

In `next.config.ts`:
```typescript
// Required: pdf.js uses canvas; exclude from SSR
const nextConfig = {
  experimental: { serverComponentsExternalPackages: ['pdfjs-dist', 'canvas'] },
};
```

`PDFViewer` must be dynamically imported with `ssr: false` in any server component that renders it:
```typescript
const PDFViewer = dynamic(() => import('@/components/pdf/PDFViewer'), { ssr: false });
```

### Canvas architecture for source highlighting

Two canvases, stacked via absolute positioning:
```
┌──────────────────────────────────┐
│  <div style="position:relative"> │
│    <canvas id="pdf-render" />    │ ← pdfjs renders the PDF page here
│    <canvas id="pdf-overlay" />   │ ← highlight is drawn here
│  </div>                          │
└──────────────────────────────────┘
```

The overlay canvas is transparent by default; `SourceHighlight` draws on it when a BOQ row is selected. The PDF canvas is never touched after initial render. This avoids re-rendering the PDF on every row click.

### Coordinate mapping

The API should return highlight geometry in **PDF user space** (points, origin bottom-left, as defined in the PDF spec — this is what PyMuPDF's bboxes use). The viewer maps PDF-space coordinates to canvas-space pixels using the current viewport transform:

```typescript
const viewport = page.getViewport({ scale: zoom });
// bbox from API: { x1, y1, x2, y2 } in PDF user space
// Map to canvas pixels:
const canvasX1 = bbox.x1 * viewport.scale;
const canvasY1 = (pdfHeight - bbox.y2) * viewport.scale; // flip Y axis
const canvasX2 = bbox.x2 * viewport.scale;
const canvasY2 = (pdfHeight - bbox.y1) * viewport.scale;
```

**Important:** confirm the exact coordinate system and units returned by `GET /api/estimates/{id}/boq` before coding — if the API returns page-fraction coordinates (0–1) or pixel coordinates, the mapping changes. Verify against `backend/app/*/router.py`. If highlight geometry is not yet returned by the API, see §5.3 for the smallest proposed backend addition.

---

## 5. Page Designs

### 5.1 Upload + Quality Gate (`/`)

**Layout:**
```
┌─────────────────────────────────────────────────────┐
│  ■ AEC Blueprint                           [Catalog] │  ← AppShell — 56px
├─────────────────────────────────────────────────────┤
│                                                     │
│                                                     │
│         Upload a drawing to begin                   │  ← centered column, max-w-xl
│                                                     │
│   ┌─────────────────────────────────────────────┐   │
│   │                                             │   │
│   │        ↑                                    │   │
│   │   Drop a PDF here, or click to browse       │   │  ← DropZone, min-h-48
│   │                                             │   │
│   │   Accepts: PDF (vector or raster)           │   │
│   └─────────────────────────────────────────────┘   │
│                                                     │
│   ── Quality check ─────────────────────────────── │  ← appears after file is chosen,
│                                                     │     before pipeline is triggered
│   [QualityGateBadge]                               │
│   [ReexportRequest, if DEGRADED_VECTOR]            │
│                                                     │
│                                [Run takeoff →]      │
│                                                     │
└─────────────────────────────────────────────────────┘
```

**States:**

*Idle:* DropZone in default state, no badge visible.

*File selected — checking:*
```
[ Spinner ]  Checking drawing structure...
```
Calls `POST /api/drawings/check` with the file, then `GET /api/drawings/{id}/quality`.

*Quality verdict — LAYERED_VECTOR:*
```
● 46 layers · 88,523 paths               READY
This PDF preserves CAD layer data. Quantities will be measured directly from geometry.

                                [Run takeoff →]
```

*Quality verdict — DEGRADED_VECTOR:*
```
◑ Layer data not found                   LOWER CONFIDENCE
This PDF appears to have been flattened. Measurements will use the CV fallback pipeline
and will be tagged RASTER in the results.

You can continue, or request a re-export from the author.

[Request re-export from author]          [Continue anyway →]
```
The "Request re-export" button opens a small inline form: recipient email + a pre-written message explaining exactly what export settings are needed (checkable, editable, sendable). The message text must never say "our AI" or "our system" — it says "The tool we're using for quantity takeoff requires the PDF to be exported with layers preserved. In AutoCAD: File → Export → PDF → 'Include Layer Information' checked."

*Quality verdict — RASTER:*
```
○ No vector data                         CV PIPELINE
This file is a scanned or rasterised drawing. Symbol detection and measurement
will be visual-only and tagged accordingly in the results.

                                [Run takeoff →]
```

**Badge visual design (QualityGateBadge):**
Three-column layout: symbol + text block + status chip. Border-left in the tier color. Background is `--color-canvas`. No filled background — structured information, not an alert-box.

### 5.2 Pipeline Progress

Triggered immediately after "Run takeoff" button — navigates to `/estimates/[id]` immediately but shows progress before the estimate is ready.

```
┌─────────────────────────────────────────────────────┐
│  ■ AEC Blueprint                           [Catalog] │
├─────────────────────────────────────────────────────┤
│                                                     │
│   Jeddah VIP Clinic — Basement 2                    │
│   MMC-JVC-CD-ELEC-3902_AC-WIRE · REV.00             │
│                                                     │
│   Processing drawing                                │
│                                                     │
│   ✓ Parse layers           (46 layers found)        │
│   ✓ Classify disciplines   (5 disciplines)          │
│   ● Cluster symbols        ████████████░░░░  73%    │  ← in-progress
│   ○ Measure routes                                  │  ← pending
│   ○ Apply assemblies                                │
│   ○ Calculate costs                                 │
│                                                     │
│   This usually takes 15–60 seconds.                 │
│                                                     │
└─────────────────────────────────────────────────────┘
```

**Implementation:** React Query polls `GET /api/estimates/{id}/status` every 2 seconds. Each stage returned by the API maps to one row. When `status === 'complete'`, stop polling and render the full workspace.

**Visual:** ✓ (completed, `--color-measured`), ● (in-progress, spinning, `--color-accent`), ○ (pending, `--color-ink-300`). Progress bar for the current stage only. No animation for completed or pending stages.

### 5.3 Estimate Workspace (`/estimates/[id]`)

This is the product. Every other screen serves this one.

**Layout:**
```
┌──────────────────────────────────────────────────────────────────────┐
│ ■ AEC Blueprint   ← Jeddah VIP Clinic · REV.00  [LAYERED_VECTOR]  [Export ▾] │  56px AppShell
├─────────────────────────────┬────────────────────────────────────────┤
│                             │                                        │
│       PDF VIEWER            │  [All] [Electrical ×] [Arch] [Mech]  │  discipline tabs
│                             ├────────────────────────────────────────┤
│                             │ ITEM                QTY    RATE  TOTAL│
│   (pdfjs canvas)            │ ─── Electrical ─────────────────────  │
│                             │ ● Card Reader         42  ...   ...  ✓│
│  [Source region             │ ● Magnetic Lock        42  ...   ...  ✓│
│   highlighted here          │ ● Push Button          42  ...   ...  ✓│
│   when row selected]        │ ◑ Door Controller      21  ...   ...  ✓│
│                             │ ● Control Cable   1,284m  ...   ...  ↺│  ← pending review
│                             │ ● Cable Trunking    410m  [no rate]   │  ← UNMAPPED
│                             │ ─── Unpriced items ─────────────────  │
│                             │  ⚠  2 items have no rate assigned     │
│                             │     Open catalog to add rates →        │
│                             │                                        │
│                             │ Review: 44 / 47    [Close session]     │
│                             ├────────────────────────────────────────┤
│ ── p.1 of 1 ──  [−] 100% [+]│ Total (priced items):  SAR 128,450.00 │
└─────────────────────────────┴────────────────────────────────────────┘
```

**Two-panel system:**
- Left: PDF viewer — default 40% width, draggable divider, persisted in localStorage.
- Right: BOQ panel — scrollable table, sticky header row with totals at bottom.
- On first load, if no row is selected, the PDF panel shows the first page at fit-width zoom.

**BOQ Table columns:**

| Column | Width | Type | Notes |
|---|---|---|---|
| Confidence | 32px | Badge (symbol only, label in tooltip) | See §6 |
| Item | flex | String | Assembly name + spec, two-line if needed |
| Qty | 96px | `font-mono text-right` | Formatted with commas, unit suffix |
| Unit | 48px | String | m, m², m³, nr, hr |
| Rate | 96px | `font-mono text-right` | Or `[no rate]` in `--color-warning` |
| Total | 104px | `font-mono font-semibold text-right` | Or `—` if no rate |
| Review | 88px | Accept/Reject/Edit controls | |

**Row selection and source highlighting — the precision highlight:**
Clicking anywhere on a row (except the review controls) selects it, sets `selectedRowId` state in `EstimateClient`, and:
1. If the PDF panel is collapsed, it expands to its last saved width (animated, 220ms, `--ease-out`).
2. The PDF navigates to the correct page if the row's source is on a different page.
3. The overlay canvas draws the source highlight using a two-phase animation:
   - Phase 1 (0–160ms): a crosshair radiates outward from the bbox center, drawing four right-angle "surveyor corner" lines outward to each corner of the bbox, using `--color-accent`. Respects `prefers-reduced-motion` — if reduced, draw instantly.
   - Phase 2 (160–400ms): the corner lines connect into a complete rectangle, the fill fades in as a 15% opacity wash of `--color-accent`.
   - Settled state: the rectangle pulses very gently (opacity oscillates 15%↔25%, 2s period) while the row remains selected.
4. A small callout badge appears above the highlight region: `"1,284 m  ·  measured from route"`.

**No source geometry yet — backend addition required:**
The current `GET /api/estimates/{id}/boq` spec does not list a `source_region` field per BOQ line. The click-to-source feature requires each BOQ item to carry:
```json
{
  "id": "...",
  "description": "Control Cable",
  "quantity": 1284,
  "confidence_status": "MEASURED",
  "source": {
    "page": 0,
    "bbox": { "x1": 312.4, "y1": 580.2, "x2": 680.1, "y2": 612.8 },
    "layer": "access control",
    "calculation_method": "route_length × scale_factor"
  }
}
```
This is a backend addition. **Flag this explicitly to the backend developer** — it needs to join `BOQ_ITEM → MEASUREMENT → source_region` on the query. The frontend should degrade gracefully: if a BOQ row has no `source` field, the click still selects the row and the PDF viewer stays on the current page, but shows a message "No source region recorded for this item."

**UNMAPPED / unpriced rows:**
Never rendered as `$0.00`. Instead:
```
● Cable Trunking    410m    [no rate]    —    ↺
```
The `[no rate]` chip links directly to the catalog with that material pre-searched. The `—` total cell uses `--color-ink-300`. A sticky banner at the bottom of the table section counts unpriced items: "2 items have no rate assigned. Open catalog to add rates →"

**Discipline tabs:**
Radix `Tabs` component at the top of the right panel. Tabs: All · Electrical · Architectural · Mechanical · Envelope · Unpriced. Each shows a count badge. "Unpriced" tab shows only `UNMAPPED` rows. Clicking a tab filters the TanStack Table, not fetches new data.

**Review session:**
On `EstimateClient` mount: `POST /api/review/sessions` → store returned session ID in state. On unmount: `POST /api/review/sessions/{id}/close`.

Per-row review controls (three states, cycling):
- Pending (default): `—` in `--color-ink-300`
- Accept: `✓` in `--color-measured` — records via `POST /api/review/sessions/{id}/actions`
- Reject: `✗` in `--color-error` — opens `CorrectionDialog` (Radix Dialog) with a text field for reason + corrected value

`ASSUMED` rows display a warning icon on their review control and cannot be bulk-accepted. If a user attempts to "Accept All" (a button at the top of the table), it accepts only `MEASURED` and `DERIVED` rows; `ASSUMED` rows remain pending and scroll into view with a pulse highlight.

A sticky footer below the table shows: `Review: 44 / 47` progress and a `[Close session]` button. Closing the session calls `POST /api/review/sessions/{id}/close`.

**Export:**
The `[Export ▾]` button in the AppShell opens a Radix Select menu:
- Download as JSON
- Download as XLSX
- Download as PDF

Each calls `GET /api/exports/estimates/{id}/export?format=json|xlsx|pdf` and triggers `window.location.href` for the file download. No special UI needed — the browser handles the download.

### 5.4 Catalog (`/catalog`)

```
┌────────────────────────────────────────────────────┐
│ ■ AEC Blueprint                          [Catalog] │
├────────────────────────────────────────────────────┤
│                                                    │
│ Material & Labor Catalog                           │
│                                                    │
│ ┌─ Import ──────────────────────────────────────┐  │
│ │  Drop a CSV or Excel file, or click to browse │  │
│ │  Template: Download starter CSV               │  │
│ └───────────────────────────────────────────────┘  │
│                                                    │
│ [Filter by category ▾]   [Search...          ]    │
│                                                    │
│ NAME                    UNIT   RATE    EFFECTIVE   │
│ ─────────────────────────────────────────────────  │
│ Control Cable 2×2.5mm   m      420.00  Aug 2026    │
│ Card Reader (HID)       nr   1,850.00  Aug 2026    │
│ Magnetic Lock           nr     680.00  Aug 2026    │
│ ...                                                │
│                                                    │
└────────────────────────────────────────────────────┘
```

**Import error display:**
Do not use a generic "Import failed" toast. Parse and display errors per row:
```
Import complete — 3 errors found

  Row 12:  Unit "sqm" not recognised. Did you mean "m²"?
  Row 17:  Rate is missing. This row was skipped.
  Row 23:  Effective date "2026-13-01" is not a valid date.

43 rows imported successfully.
```
Each error row in the table is highlighted, not removed. The user can fix in place or re-upload a corrected file.

Rates in the catalog table: `font-mono text-right`. Every number in this UI is monospaced — including catalog rates.

---

## 6. Confidence Tier Visual Language

The `ConfidenceBadge` component is the most-repeated element in the system. It must be immediately readable, not require color alone, and work for people with color vision differences.

**Three-signal system: symbol + color + label**

| Status | Symbol | Color | Label | Tooltip |
|---|---|---|---|---|
| `MEASURED` | ● | `--color-measured` (#0DA56A) | Measured | Read directly from drawing geometry |
| `DERIVED` | ◑ | `--color-derived` (#6B4FF8) | Derived | Calculated from an engineering assembly rule |
| `ASSUMED` | ○ | `--color-assumed` (#D97706) | Assumed | Filled from a default or historical assumption — review required |
| `UNMAPPED` | — | `--color-unmapped` (#7A9FBF) | No rule | Quantity measured, but no pricing rule exists yet |

**Source quality modifier:**
When `source_quality === 'raster'` (measurement came from the CV fallback, not vector geometry), add a small superscript badge `[R]` in `--color-raster` after the confidence symbol. This means a row can be `MEASURED [R]` — the geometry was measured, but from a rasterised source rather than precise vector coordinates.

**SVG symbols (inline, not icon font):**
```tsx
// ● MEASURED — filled circle
<svg width="12" height="12" viewBox="0 0 12 12">
  <circle cx="6" cy="6" r="5" fill="currentColor"/>
</svg>

// ◑ DERIVED — half-filled circle
<svg width="12" height="12" viewBox="0 0 12 12">
  <circle cx="6" cy="6" r="5" stroke="currentColor" strokeWidth="1.5" fill="none"/>
  <path d="M6 1 A5 5 0 0 1 6 11 Z" fill="currentColor"/>
</svg>

// ○ ASSUMED — open circle
<svg width="12" height="12" viewBox="0 0 12 12">
  <circle cx="6" cy="6" r="5" stroke="currentColor" strokeWidth="1.5" fill="none"/>
</svg>

// — UNMAPPED — dash
<svg width="12" height="12" viewBox="0 0 12 12">
  <line x1="2" y1="6" x2="10" y2="6" stroke="currentColor" strokeWidth="2" strokeLinecap="round"/>
</svg>
```

In the compact table badge: symbol only, label in Radix Tooltip on hover.
In the provenance drawer (expanded row): symbol + label + full tooltip text as visible body copy.

---

## 7. Review Session Workflow

```
EstimateClient mounts
        ↓
POST /api/review/sessions     → session_id stored in state
        ↓
User clicks a BOQ row         → row selected, PDF highlights source region
        ↓
User clicks Accept (✓)        → POST /api/review/sessions/{id}/actions
                                  { action: "accept", boq_item_id: "..." }
User clicks Reject (✗)        → CorrectionDialog opens
                                  { action: "reject", boq_item_id: "...",
                                    reason: "...", corrected_value: ... }
                                → POST /api/review/sessions/{id}/actions
User clicks Edit (✏)          → CorrectionDialog opens with current value pre-filled
                                → POST /api/review/sessions/{id}/actions
                                  { action: "correct", ... }
        ↓
All 47 items reviewed          → ReviewProgress shows 47/47
                                → Banner: "All items reviewed. Close session?"
        ↓
[Close session]                → POST /api/review/sessions/{id}/close
                                → invalidate estimate BOQ query
                                → BOQ refetches with updated statuses
```

**ASSUMED items — no bulk accept:**
`[Accept All]` button at the table top runs:
```typescript
const acceptableItems = boqItems.filter(
  item => item.confidence_status !== 'ASSUMED' && item.review_status === 'pending'
);
// POST actions for each, in parallel
await Promise.all(acceptableItems.map(item => acceptItem(sessionId, item.id)));
// Scroll to first ASSUMED item still pending
```
After the bulk accept, ASSUMED rows remain pending and a count badge shows: "3 items require individual review — scroll to review."

---

## 8. Error / Loading / Empty States

Write errors from the user's side of the screen. Name what happened and exactly what to do next. Never say "An error occurred."

| State | Copy | Action |
|---|---|---|
| Upload — wrong file type | "Only PDF files are accepted. Select a different file." | — |
| Upload — file too large | "This file is larger than 50 MB. Split the drawing set and upload one sheet at a time." | — |
| Quality check failed | "Couldn't read this PDF's structure. The file may be corrupted. Try re-exporting from your CAD application." | — |
| Pipeline failed | "Processing stopped during [stage name]. View the error log, or try re-uploading." | [View log] / [Try again] |
| BOQ empty | "No components were extracted from this drawing. This may be an unsupported discipline or drawing type." | [Upload a different drawing] |
| Catalog empty | "No rates added yet. Import a CSV to start pricing your estimates." | [Import CSV] |
| No source region | "No source location recorded for this item." | (shown inline in the PDF panel, not as a blocking error) |

**Loading skeletons:** BOQ table rows render as skeleton bars (CSS-animated `bg-ink-50` → `bg-ink-100` pulse) while the BOQ query is fetching. Never show a spinner in the center of a table — the table chrome (headers, discipline groups) renders immediately with skeleton rows inside.

**Error boundary:** wrap `EstimateClient` in a React error boundary that shows `ErrorState` with a "Reload workspace" button rather than crashing the whole page.

---

## 9. File & Folder Conventions

```
frontend/
  src/
    app/                 — Next.js App Router pages and layouts
    components/          — component tree (§2.2)
    hooks/               — custom React hooks
      useEstimateBoq.ts  — React Query wrapper for BOQ fetch
      usePipelineStatus.ts
      useCatalog.ts
      useReviewSession.ts
    lib/
      api.ts             — typed fetch wrappers (base URL from NEXT_PUBLIC_API_URL)
      pdfCoordinates.ts  — PDF ↔ canvas coordinate mapping (§4)
      confidenceTier.ts  — maps confidence_status → symbol + color + label
    styles/
      tokens.css         — CSS custom properties (§1)
      globals.css        — @import tokens, Tailwind base, global resets
    types/
      api.ts             — TypeScript types matching backend response shapes
      drawing.ts
      estimate.ts
      catalog.ts
```

**Naming:** PascalCase for components (`BOQTable.tsx`), camelCase for hooks (`useEstimateBoq.ts`) and lib files, kebab-case for style files.

**Env:**
```
# .env.local
NEXT_PUBLIC_API_URL=http://127.0.0.1:8000
```
Never hardcode `127.0.0.1:8000` in any component file.

---

## 10. Audit of v1 Scope + IA Answers

### Does the minimal scope match what Phases.md demands of the UI?

**Items in scope, confirmed correct:**
1. Upload + Quality Gate — necessary, first interaction.
2. Pipeline trigger + progress — necessary, pipeline is long (15–60s), user needs feedback.
3. Estimate workspace with BOQ + confidence badges + provenance — the core of the product.
4. Click-to-source — necessary; without it the "every number traceable to the drawing" principle is not user-accessible, just architecture.
5. Human review per row — necessary; without it the guiding principle has no UI expression.
6. Catalog browse + import — necessary; without it UNMAPPED items can't be priced.
7. Export — necessary; the output has no value if it can't leave the system.

**Items that could be added without much cost — your call:**
- **Narration** (`GET /api/narration/estimates/{id}`) is already live in the backend. Adding a "Scope of work" tab next to the BOQ table that loads this endpoint is one React Query hook + one `<pre>` — very low cost, high value. Recommend including.
- **Replay** (`GET /api/estimates/{id}/replay`) — not sure what the data shape is. Read the router before deciding. Could be useful for "how did we get here" debugging.

**Confirmed out of scope for v1:**
Auth, multi-user, project dashboards, i18n, dark mode, mobile-first, real-time collaboration. None of these should appear in any component file, not even as a placeholder or comment.

### Estimate-centric IA — one workspace page, not multi-page

A multi-page flow (upload page → progress page → estimate page → review page → export page) adds navigation burden and breaks the mental model. The single workspace page with tab/panel organization is correct. The key is that state transitions happen **within** the workspace page: the progress view transitions into the estimate view in place; the PDF viewer and BOQ table coexist; review controls are inline in the table.

### Where a component library is genuinely needed vs plain Tailwind

**Plain Tailwind is enough for:** badges, buttons, input fields, table rows, loading skeletons, all layout/spacing, the AppShell, the two-panel divider chrome.

**Radix primitives are needed for:** Dialog (correction form — needs focus trap, escape key, aria-modal), Tooltip (confidence badge labels — needs positioning, z-index, keyboard accessible), Tabs (discipline filter — needs aria-tablist), Select (export format picker — needs keyboard navigation). These are the four. Nothing else needs a library.

**TanStack Table is needed for:** the BOQ table specifically — grouping by discipline, sorting, filtering by confidence tier, virtual scrolling for large row counts, and type-safe column definitions. A plain `<table>` would require rebuilding all of this.

### Click-to-source — backend requirement

The backend currently does not expose `source.bbox` coordinates per BOQ item. The frontend cannot implement click-to-source without this field. This is the one required backend addition before v1 is complete. The minimum addition is documented in §5.3. Flag this to the backend developer as a blocking dependency for this feature specifically.

---

## Summary — decisions made in this document

| Decision | Choice |
|---|---|
| Component library | shadcn/ui v4 (radix base, nova preset) — owner ruling 2026-08-23 |
| Table library | TanStack Table v8 + TanStack Virtual v3 (pages round) |
| Server state | TanStack Query v5 (pages round) |
| pdf.js | `pdfjs-dist` raw (not react-pdf), dynamically imported, dual-canvas architecture (pages round) |
| Panel layout | `react-resizable-panels` (pages round) |
| Icon set | `lucide-react` (shadcn default; supersedes phosphor) |
| Upload | `react-dropzone` |
| Global state | None — React Query + React `useState` |
| Type for all numbers in UI | Geist Mono, monospaced |
| Confidence tier badges | SVG geometric symbol + color + label, three-signal redundancy |
| Signature element | Precision surveyor crosshair highlight animation on BOQ row click |
| Routing | Three pages: `/`, `/estimates/[id]`, `/catalog` |
| ASSUMED bulk-accept | Blocked; requires individual review per row |
| UNMAPPED rows | Show `[no rate]`, never `$0.00`; link to catalog |
| Backend dependency | `source.bbox` per BOQ item needed for click-to-source (blocking) |
