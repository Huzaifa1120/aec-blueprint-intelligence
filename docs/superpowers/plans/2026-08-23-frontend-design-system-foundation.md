# Frontend Design System Foundation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Land the "Technical Daylight" design system foundation in `frontend/` — tokens, fonts, shadcn-based primitives, signature ConfidenceBadge, common states, AppShell, dev-only `/design-system` styleguide — validated by unit tests plus all quality gates.

**Architecture:** Spec of record `docs/AEC-Frontend-Design-System-Spec.md` (§1 tokens, §6 badges, §8 states, §9 conventions). Owner ruling 2026-08-23: **shadcn/ui is adopted** as the component layer, superseding spec §2.1's "No shadcn" decision. Radix primitives arrive via shadcn-generated components (`src/components/ui/*`); icons are lucide-react (shadcn default), replacing the spec's phosphor pick. Signature elements that don't exist in shadcn (ConfidenceBadge, later SourceHighlight) stay hand-built per spec §6. All colors live in `src/styles/tokens.css` as CSS custom properties mapped into Tailwind v4 `@theme inline`; components never hardcode hex values.

**Tech Stack:** Next.js 16 (App Router) · React 19 · TypeScript strict · Tailwind CSS v4 (CSS-first) · shadcn/ui (Radix + CVA) · lucide-react · Vitest + React Testing Library (jsdom)

## Global Constraints

- Stack locked: Next.js 16 App Router, React 19, TypeScript strict, Tailwind v4. Alias `@/*` → `./src/*`.
- Gates green before any task is done: `npm run lint`, `npm run typecheck`, `npm run format:check`, `npm run build`, `npm test`.
- This Next.js major has breaking changes vs training data — read `node_modules/next/dist/docs/` before using framework APIs. Keep auto-written `frontend/AGENTS.md` intact.
- Never hardcode hex values or API URLs in component files. Tokens only, from `src/styles/tokens.css`.
- No dark mode, no auth, no i18n, no mobile-first layouts, no placeholders for them (spec §10).
- Type scale in spec §1.2 matches Tailwind v4 defaults exactly — do NOT redefine `--text-*`.
- Fonts already wired in `layout.tsx` via `next/font/google` (Geist, Geist Mono → `--font-geist-sans`/`--font-geist-mono` variables). Reuse those variables; do not add the `geist` package.
- Working tree contains unrelated uncommitted backend changes (`backend/app/narration/*`, `docs/Traps.md`, deleted `docs/trap.md`). Never stage them. Stage only paths listed per task.
- Commits: conventional messages, on branch `feature/frontend-design-system`. Pre-commit hook runs ruff (none staged) + eslint/tsc/prettier on staged frontend files.
- Windows + Git Bash environment. Use `npx` (Node v24) for CLIs.

## Token ↔ shadcn semantic mapping (locked)

| Spec token (§1.1) | Value | shadcn semantic var | Utility access |
|---|---|---|---|
| canvas `#F2F5F9` | page bg | `--background` | `bg-background` |
| surface `#FFFFFF` | card bg | `--card`, `--popover` | `bg-card` |
| accent `#0072CF` | interactive blue | `--primary`, `--ring` | `bg-primary`, `text-primary` |
| accent-lt `#E0F0FF` | wash/hover/selected | `--secondary`, `--accent` | `bg-secondary` |
| ink-900 `#0B1929` | headings/nav chrome | `--card-foreground` etc. | `text-ink-900` |
| ink-700 `#1A3050` | body text | `--foreground` | `text-foreground` |
| ink-500 `#3E618A` | secondary text | `--muted-foreground` | `text-ink-500` |
| ink-300 `#7A9FBF` | captions/disabled | also unmapped tier | `text-ink-300` |
| ink-100 `#C8D8EA` | dividers/borders | `--border`, `--input` | `border-border` |
| ink-50 `#E8EEF5` | row hover/input bg | `--muted` | `bg-muted` |
| measured `#0DA56A` | tier | — | `text-measured`, `bg-measured` |
| derived `#6B4FF8` | tier | — | `text-derived` |
| assumed `#D97706` | tier (= warning) | — | `text-assumed` |
| raster `#E85D3A` | source-quality `[R]` | — | `text-raster` |
| error `#C41E3A` | destructive | `--destructive` | `text-error`, `bg-destructive` |

`--radius: 0.5rem` (shadcn default; crisp-but-not-square fits drafting identity). Shadows `--shadow-sm/md/lg` overridden with spec §1.4 values. Motion durations exposed as plain vars `--duration-fast/base/slow` + zeroed under `prefers-reduced-motion`.

---

### Task 1: Branch + shadcn scaffold

**Files:**
- Create: `frontend/components.json`, `frontend/src/lib/utils.ts`, `frontend/src/components/ui/*` (generated)
- Modify: `frontend/package.json`, `frontend/src/app/globals.css` (init overwrites; Task 2 rewrites properly)

**Interfaces:**
- Produces: `cn()` helper at `@/lib/utils` used by all later tasks; generated ui components `badge`, `button`, `tooltip`, `skeleton`, `card`.

- [ ] **Step 1: Create isolated branch**

```bash
git checkout -b feature/frontend-design-system
```

- [ ] **Step 2: Init shadcn (non-interactive)**

```bash
cd frontend && npx shadcn@latest init -y -b neutral
```
Expected: `components.json` written, `src/lib/utils.ts` created, `globals.css` rewritten with neutral CSS vars, deps added (clsx, tailwind-merge, class-variance-authority, lucide-react, tw-animate-css). If the CLI prompts despite flags, answer: base color neutral, css variables yes, RSC yes.

- [ ] **Step 3: Add foundation components**

```bash
cd frontend && npx shadcn@latest add badge button tooltip skeleton card
```
Expected: `src/components/ui/{badge,button,tooltip,skeleton,card}.tsx` + their Radix deps in package.json.

- [ ] **Step 4: Verify baseline still builds**

Run: `cd frontend && npm run build`
Expected: compile passes (globals.css is temporarily shadcn-neutral — acceptable).

- [ ] **Step 5: Commit**

```bash
git add frontend/components.json frontend/src/lib/utils.ts frontend/src/components/ui frontend/package.json frontend/package-lock.json frontend/src/app/globals.css
git commit -m "feat(frontend): scaffold shadcn/ui (supersedes spec §2.1 no-shadcn ruling)"
```

---

### Task 2: Tokens + global styles + layout metadata

**Files:**
- Create: `frontend/src/styles/tokens.css`
- Modify: `frontend/src/app/globals.css` (replace init output), `frontend/src/app/layout.tsx` (metadata only)

**Interfaces:**
- Produces: every utility later tasks rely on — `bg-canvas`, `text-ink-*`, `text-measured|derived|assumed|raster|error`, `shadow-md`, `duration-*` vars, `font-sans/font-mono` mapped to Geist variables.

- [ ] **Step 1: Write `src/styles/tokens.css`**

```css
/* Technical Daylight design tokens — single source of truth (spec §1).
   Components must never hardcode hex values. */
:root {
  --ink-900: #0b1929;
  --ink-700: #1a3050;
  --ink-500: #3e618a;
  --ink-300: #7a9fbf;
  --ink-100: #c8d8ea;
  --ink-50: #e8eef5;

  --canvas: #f2f5f9;
  --surface: #ffffff;

  --engineering-blue: #0072cf;
  --accent-wash: #e0f0ff;

  --tier-measured: #0da56a;
  --tier-derived: #6b4ff8;
  --tier-assumed: #d97706;
  --raster-flag: #e85d3a;
  --signal-error: #c41e3a;

  /* Motion (spec §1.5) */
  --duration-fast: 120ms;
  --duration-base: 220ms;
  --duration-slow: 380ms;
}

@theme inline {
  /* shadcn semantics ← Technical Daylight */
  --color-background: var(--canvas);
  --color-foreground: var(--ink-700);
  --color-card: var(--surface);
  --color-card-foreground: var(--ink-900);
  --color-popover: var(--surface);
  --color-popover-foreground: var(--ink-900);
  --color-primary: var(--engineering-blue);
  --color-primary-foreground: #ffffff;
  --color-secondary: var(--accent-wash);
  --color-secondary-foreground: var(--ink-900);
  --color-muted: var(--ink-50);
  --color-muted-foreground: var(--ink-500);
  --color-accent: var(--accent-wash);
  --color-accent-foreground: var(--ink-900);
  --color-destructive: var(--signal-error);
  --color-destructive-foreground: #ffffff;
  --color-border: var(--ink-100);
  --color-input: var(--ink-100);
  --color-ring: var(--engineering-blue);

  /* Extended palette */
  --color-canvas: var(--canvas);
  --color-surface: var(--surface);
  --color-ink-900: var(--ink-900);
  --color-ink-700: var(--ink-700);
  --color-ink-500: var(--ink-500);
  --color-ink-300: var(--ink-300);
  --color-ink-100: var(--ink-100);
  --color-ink-50: var(--ink-50);
  --color-measured: var(--tier-measured);
  --color-derived: var(--tier-derived);
  --color-assumed: var(--tier-assumed);
  --color-unmapped: var(--ink-300);
  --color-raster: var(--raster-flag);
  --color-error: var(--signal-error);

  /* Typography roles (faces come from next/font variables in layout.tsx) */
  --font-sans: var(--font-geist-sans), ui-sans-serif, system-ui, sans-serif;
  --font-mono: var(--font-geist-mono), ui-monospace, "Cascadia Code", monospace;

  /* Shadows (spec §1.4 — three levels only) */
  --shadow-sm: 0 1px 3px 0 rgb(11 25 41 / 0.08);
  --shadow-md: 0 4px 12px 0 rgb(11 25 41 / 0.12);
  --shadow-lg: 0 16px 40px 0 rgb(11 25 41 / 0.18);
}

@media (prefers-reduced-motion: reduce) {
  :root {
    --duration-fast: 0ms;
    --duration-base: 0ms;
    --duration-slow: 0ms;
  }
}
```

Note: `--radius` stays whatever shadcn init wrote into globals (0.5rem) — kept there, not duplicated here.

- [ ] **Step 2: Rewrite `src/app/globals.css`**

Replace entire contents with:

```css
@import "tailwindcss";
@import "tw-animate-css";
@import "../styles/tokens.css";

body {
  background: var(--background);
  color: var(--foreground);
  font-family: var(--font-sans);
}
```

Delete any `.dark` block and leftover neutral palette from init output (no dark mode, spec §10).

- [ ] **Step 3: Update `layout.tsx` metadata only**

Change the metadata export (fonts/body stay as-is):

```typescript
export const metadata: Metadata = {
  title: "AEC Blueprint",
  description: "Traceable quantity takeoff from construction drawings",
}
```

- [ ] **Step 4: Verify gates**

Run: `cd frontend && npm run typecheck && npm run build`
Expected: pass. Sanity: `grep -c "dark" src/app/globals.css` → 0 matches.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/styles/tokens.css frontend/src/app/globals.css frontend/src/app/layout.tsx
git commit -m "feat(frontend): Technical Daylight token system + global styles"
```

---

### Task 3: Vitest harness (dev tooling)

**Files:**
- Create: `frontend/vitest.config.ts`, `frontend/vitest.setup.ts`, `frontend/src/lib/smoke.test.ts`
- Modify: `frontend/package.json` (scripts), `docs/AEC-Frontend-Design-System-Spec.md` (§2.1 dependency table gains dev-tooling rows — required by its own rule)

**Interfaces:**
- Produces: `npm test` (vitest run, jsdom, jest-dom matchers, `@/` alias resolution). All later test files import `{ describe, it, expect }` from `"vitest"` explicitly (keeps `tsc` happy without tsconfig types changes).

- [ ] **Step 1: Install dev dependencies**

```bash
cd frontend && npm i -D vitest @vitejs/plugin-react jsdom @testing-library/react @testing-library/jest-dom @testing-library/dom
```

- [ ] **Step 2: Write `vitest.config.ts`**

```typescript
import { fileURLToPath } from "node:url"
import react from "@vitejs/plugin-react"
import { defineConfig } from "vitest/config"

export default defineConfig({
  plugins: [react()],
  test: {
    environment: "jsdom",
    setupFiles: ["./vitest.setup.ts"],
  },
  resolve: {
    alias: {
      "@": fileURLToPath(new URL("./src", import.meta.url)),
    },
  },
})
```

- [ ] **Step 3: Write `vitest.setup.ts`**

```typescript
import "@testing-library/jest-dom/vitest"
```

- [ ] **Step 4: Add scripts to `package.json`**

```json
"test": "vitest run",
"test:watch": "vitest"
```

- [ ] **Step 5: Write failing smoke test `src/lib/smoke.test.ts`**

```typescript
import { describe, expect, it } from "vitest"

describe("test harness", () => {
  it("runs with jest-dom matchers and alias imports", () => {
    const el = document.createElement("div")
    expect(el).toBeInTheDocument()
    expect(true).toBe(true)
  })
})
```

- [ ] **Step 6: Run** `npm test` → Expected: 1 passed.

- [ ] **Step 7: Amend spec §2.1 dependency table** — append rows:

```markdown
| `vitest` | dev | Unit/render tests for design-system components (owner-approved validation round 2026-08-23) | MIT |
| `@vitejs/plugin-react` | dev | JSX transform inside vitest | MIT |
| `jsdom` | dev | DOM environment for component tests | MIT |
| `@testing-library/react` + `dom` + `jest-dom` | dev | Render/assertion toolkit | MIT |
```

And replace the two "Explicitly not added" bullets for shadcn/Zustand accordingly: shadcn/ui **adopted 2026-08-23 (owner ruling)** — Radix primitives ship via generated `src/components/ui/*`; icons are `lucide-react` (shadcn default), superseding the phosphor row; Zustand/Jotai/framer-motion exclusions unchanged.

- [ ] **Step 8: Commit**

```bash
git add frontend/vitest.config.ts frontend/vitest.setup.ts frontend/src/lib/smoke.test.ts frontend/package.json frontend/package-lock.json docs/AEC-Frontend-Design-System-Spec.md
git commit -m "test(frontend): vitest + RTL harness; record shadcn adoption in spec §2.1"
```

---

### Task 4: Confidence tier logic + types (TDD)

**Files:**
- Create: `frontend/src/types/api.ts`, `frontend/src/lib/confidenceTier.ts`
- Test: `frontend/src/lib/confidenceTier.test.ts`

**Interfaces:**
- Produces:
  - `types/api.ts`: `export type MeasurementStatus = "MEASURED" | "DERIVED" | "ASSUMED"`, `export type SourceQuality = "layered_vector" | "degraded_vector" | "raster"`
  - `confidenceTier.ts`: `export type TierKey = MeasurementStatus | "UNMAPPED"`; `export interface TierMeta { key: TierKey; label: string; colorClass: string; tooltip: string }`; `export function getTierMeta(status: string): TierMeta`; `export const TIER_ORDER: readonly TierKey[]`

- [ ] **Step 1: Write failing test `src/lib/confidenceTier.test.ts`**

```typescript
import { describe, expect, it } from "vitest"
import { TIER_ORDER, getTierMeta } from "./confidenceTier"

describe("getTierMeta", () => {
  it("maps all four tiers with three-signal metadata", () => {
    expect(getTierMeta("MEASURED")).toEqual({
      key: "MEASURED",
      label: "Measured",
      colorClass: "text-measured",
      tooltip: "Read directly from drawing geometry",
    })
    expect(getTierMeta("DERIVED").label).toBe("Derived")
    expect(getTierMeta("ASSUMED").colorClass).toBe("text-assumed")
    expect(getTierMeta("UNMAPPED").label).toBe("No rule")
  })

  it("falls back to UNMAPPED for unknown statuses", () => {
    expect(getTierMeta("SOMETHING_NEW").key).toBe("UNMAPPED")
  })

  it("exposes a stable display order", () => {
    expect(TIER_ORDER).toEqual(["MEASURED", "DERIVED", "ASSUMED", "UNMAPPED"])
  })
})
```

- [ ] **Step 2: Run** `npm test` → Expected: FAIL (module not found).

- [ ] **Step 3: Implement `src/types/api.ts`**

```typescript
export type MeasurementStatus = "MEASURED" | "DERIVED" | "ASSUMED"

export type SourceQuality = "layered_vector" | "degraded_vector" | "raster"
```

- [ ] **Step 4: Implement `src/lib/confidenceTier.ts`** (copy = spec §6 table verbatim)

```typescript
import type { MeasurementStatus } from "@/types/api"

export type TierKey = MeasurementStatus | "UNMAPPED"

export interface TierMeta {
  key: TierKey
  label: string
  colorClass: string
  tooltip: string
}

const TIERS: Record<TierKey, TierMeta> = {
  MEASURED: {
    key: "MEASURED",
    label: "Measured",
    colorClass: "text-measured",
    tooltip: "Read directly from drawing geometry",
  },
  DERIVED: {
    key: "DERIVED",
    label: "Derived",
    colorClass: "text-derived",
    tooltip: "Calculated from an engineering assembly rule",
  },
  ASSUMED: {
    key: "ASSUMED",
    label: "Assumed",
    colorClass: "text-assumed",
    tooltip: "Filled from a default or historical assumption — review required",
  },
  UNMAPPED: {
    key: "UNMAPPED",
    label: "No rule",
    colorClass: "text-unmapped",
    tooltip: "Quantity measured, but no pricing rule exists yet",
  },
}

export const TIER_ORDER: readonly TierKey[] = ["MEASURED", "DERIVED", "ASSUMED", "UNMAPPED"]

export function getTierMeta(status: string): TierMeta {
  return TIERS[status as TierKey] ?? TIERS.UNMAPPED
}
```

- [ ] **Step 5: Run** `npm test` → Expected: PASS (all files).

- [ ] **Step 6: Commit**

```bash
git add frontend/src/types/api.ts frontend/src/lib/confidenceTier.ts frontend/src/lib/confidenceTier.test.ts
git commit -m "feat(frontend): confidence-tier metadata map + api union types"
```

---

### Task 5: ConfidenceBadge (signature component, TDD)

**Files:**
- Create: `frontend/src/components/estimate/ConfidenceBadge.tsx`
- Test: `frontend/src/components/estimate/ConfidenceBadge.test.tsx`

**Interfaces:**
- Consumes: `TierMeta`, `getTierMeta` (Task 4); shadcn `Tooltip*` (Task 1).
- Produces: `export interface ConfidenceBadgeProps { status: TierKey; sourceQuality?: SourceQuality; showLabel?: boolean; className?: string }`; default-export-free named component `ConfidenceBadge`. Test hook: `data-testid="confidence-badge"` on root, `data-testid="confidence-badge-symbol"` on the svg, `data-testid="confidence-badge-raster"` on the `[R]` modifier.

- [ ] **Step 1: Write failing test**

```tsx
import { render, screen } from "@testing-library/react"
import { describe, expect, it } from "vitest"
import { ConfidenceBadge } from "./ConfidenceBadge"

describe("ConfidenceBadge", () => {
  it("renders the filled-circle tier with accessible label", () => {
    render(<ConfidenceBadge status="MEASURED" />)
    const root = screen.getByTestId("confidence-badge")
    expect(root).toHaveTextContent("Measured")
    expect(root.querySelector("[data-testid='confidence-badge-symbol'] svg")).toBeInTheDocument()
  })

  it("switches symbol and color per tier", () => {
    const { rerender } = render(<ConfidenceBadge status="ASSUMED" />)
    expect(screen.getByTestId("confidence-badge")).toHaveClass("text-assumed")
    rerender(<ConfidenceBadge status="DERIVED" />)
    expect(screen.getByTestId("confidence-badge")).toHaveClass("text-derived")
  })

  it("shows the [R] raster modifier only for raster source quality", () => {
    const { rerender } = render(<ConfidenceBadge status="MEASURED" sourceQuality="layered_vector" />)
    expect(screen.queryByTestId("confidence-badge-raster")).not.toBeInTheDocument()
    rerender(<ConfidenceBadge status="MEASURED" sourceQuality="raster" />)
    expect(screen.getByTestId("confidence-badge-raster")).toHaveTextContent("[R]")
  })
})
```

- [ ] **Step 2: Run** `npm test` → Expected: FAIL (component missing).

- [ ] **Step 3: Implement** (SVGs copied verbatim from spec §6)

```tsx
"use client"

import { getTierMeta, type TierKey } from "@/lib/confidenceTier"
import type { SourceQuality } from "@/types/api"
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from "@/components/ui/tooltip"
import { cn } from "@/lib/utils"

export interface ConfidenceBadgeProps {
  status: TierKey
  sourceQuality?: SourceQuality
  showLabel?: boolean
  className?: string
}

function TierSymbol() {
  return (
    <svg
      data-testid="confidence-badge-symbol"
      width="12"
      height="12"
      viewBox="0 0 12 12"
      aria-hidden="true"
    >
      <circle cx="6" cy="6" r="5" />
    </svg>
  )
}

export function ConfidenceBadge({ status, sourceQuality, showLabel = false, className }: ConfidenceBadgeProps) {
  const meta = getTierMeta(status)
  return (
    <TooltipProvider delayDuration={200}>
      <Tooltip>
        <TooltipTrigger asChild>
          <span
            data-testid="confidence-badge"
            className={cn(
              "inline-flex items-center gap-1.5 text-xs font-medium",
              meta.colorClass,
              className,
            )}
          >
            <TierSymbol />
            {(showLabel || true) && null}
            <span className={cn(!showLabel && "sr-only")}>{meta.label}</span>
            {sourceQuality === "raster" && (
              <sup data-testid="confidence-badge-raster" className="font-semibold text-raster">
                [R]
              </sup>
            )}
          </span>
        </TooltipTrigger>
        <TooltipContent>
          <p>{meta.label} — {meta.tooltip}</p>
        </TooltipContent>
      </Tooltip>
    </TooltipProvider>
  )
}
```

Then replace `TierSymbol` body with a per-key switch (keep outer markup identical):

```tsx
function TierSymbol({ status }: { status: TierKey }) {
  if (status === "MEASURED") {
    return (
      <svg data-testid="confidence-badge-symbol" width="12" height="12" viewBox="0 0 12 12" aria-hidden="true">
        <circle cx="6" cy="6" r="5" fill="currentColor" />
      </svg>
    )
  }
  if (status === "DERIVED") {
    return (
      <svg data-testid="confidence-badge-symbol" width="12" height="12" viewBox="0 0 12 12" aria-hidden="true">
        <circle cx="6" cy="6" r="5" stroke="currentColor" strokeWidth="1.5" fill="none" />
        <path d="M6 1 A5 5 0 0 1 6 11 Z" fill="currentColor" />
      </svg>
    )
  }
  if (status === "ASSUMED") {
    return (
      <svg data-testid="confidence-badge-symbol" width="12" height="12" viewBox="0 0 12 12" aria-hidden="true">
        <circle cx="6" cy="6" r="5" stroke="currentColor" strokeWidth="1.5" fill="none" />
      </svg>
    )
  }
  return (
    <svg data-testid="confidence-badge-symbol" width="12" height="12" viewBox="0 0 12 12" aria-hidden="true">
      <line x1="2" y1="6" x2="10" y2="6" stroke="currentColor" strokeWidth="2" strokeLinecap="round" />
    </svg>
  )
}
```

(Write the final file once with the switched `TierSymbol` and `<TierSymbol status={status} />` — do not ship the placeholder version.)

- [ ] **Step 4: Run** `npm test` → Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/components/estimate/ConfidenceBadge.tsx frontend/src/components/estimate/ConfidenceBadge.test.tsx
git commit -m "feat(frontend): ConfidenceBadge — geometric three-signal tier system"
```

---

### Task 6: Common states, PageHeader, AppShell (TDD)

**Files:**
- Create: `frontend/src/components/common/{EmptyState,ErrorState,LoadingSpinner,PageHeader}.tsx`, `frontend/src/components/layout/AppShell.tsx`
- Test: `frontend/src/components/common/states.test.tsx`

**Interfaces:**
- Consumes: shadcn `button`, `skeleton`; `lucide-react` icons.
- Produces:
  - `EmptyStateProps { icon?: ReactNode; title: string; description?: string; action?: ReactNode }`
  - `ErrorStateProps { title?: string; description: string; action?: ReactNode }` (title default "Something went wrong" is NOT allowed by spec §8 — default title: "Couldn't complete this action")
  - `LoadingSpinnerProps { className?: string }`
  - `PageHeaderProps { title: string; description?: string; actions?: ReactNode }`
  - `AppShellProps { children: ReactNode; right?: ReactNode }` — 56px top bar, brand "AEC Blueprint" linking `/`.

- [ ] **Step 1: Write failing test `states.test.tsx`**

```tsx
import { render, screen } from "@testing-library/react"
import { describe, expect, it, vi } from "vitest"
import { EmptyState } from "./EmptyState"
import { ErrorState } from "./ErrorState"
import { LoadingSpinner } from "./LoadingSpinner"
import { PageHeader } from "./PageHeader"
import { AppShell } from "@/components/layout/AppShell"

describe("state components", () => {
  it("EmptyState renders title, description and fires action", async () => {
    const onClick = vi.fn()
    const { user } = renderWithUser(
      <EmptyState
        title="No rates added yet."
        description="Import a CSV to start pricing your estimates."
        action={<button onClick={onClick}>Import CSV</button>}
      />,
    )
    expect(screen.getByText("No rates added yet.")).toBeInTheDocument()
    await user.click(screen.getByRole("button", { name: "Import CSV" }))
    expect(onClick).toHaveBeenCalledOnce()
  })

  it("ErrorState renders named failure copy, never generic", () => {
    render(
      <ErrorState description="Processing stopped during Cluster symbols." />,
    )
    expect(screen.getByText("Processing stopped during Cluster symbols.")).toBeInTheDocument()
  })

  it("LoadingSpinner exposes an aria-labelled busy indicator", () => {
    render(<LoadingSpinner />)
    expect(screen.getByRole("status")).toHaveAttribute("aria-label", "Loading")
  })

  it("PageHeader renders title and action slot", () => {
    render(<PageHeader title="Material & Labor Catalog" actions={<button>Import</button>} />)
    expect(screen.getByRole("heading", { level: 1, name: "Material & Labor Catalog" })).toBeInTheDocument()
    expect(screen.getByRole("button", { name: "Import" })).toBeInTheDocument()
  })

  it("AppShell renders 56px chrome with brand link and right slot", () => {
    render(
      <AppShell right={<span>Export ▾</span>}>
        <main>workspace</main>
      </AppShell>,
    )
    expect(screen.getByRole("link", { name: "AEC Blueprint" })).toHaveAttribute("href", "/")
    expect(screen.getByText("Export ▾")).toBeInTheDocument()
    expect(screen.getByText("workspace")).toBeInTheDocument()
  })
})
```

Plus a tiny helper at top of the test file (user-event needs no extra dep — RTL ships `@testing-library/user-event`? NO it does not — add `npm i -D @testing-library/user-event` first):

```tsx
import userEvent from "@testing-library/user-event"
function renderWithUser(ui: React.ReactElement) {
  const user = userEvent.setup()
  return { user, ...render(ui) }
}
```

- [ ] **Step 2: Run** `npm test` → Expected: FAIL (modules missing).

- [ ] **Step 3: Install user-event** `npm i -D @testing-library/user-event` (append row to spec §2.1 dev table).

- [ ] **Step 4: Implement the four common components + AppShell**

```tsx
// EmptyState.tsx
import type { ReactNode } from "react"

export interface EmptyStateProps {
  icon?: ReactNode
  title: string
  description?: string
  action?: ReactNode
}

export function EmptyState({ icon, title, description, action }: EmptyStateProps) {
  return (
    <div className="flex flex-col items-center justify-center gap-2 rounded-lg border border-dashed border-ink-100 bg-surface p-12 text-center">
      {icon && <div className="text-ink-300">{icon}</div>}
      <p className="text-sm font-medium text-ink-700">{title}</p>
      {description && <p className="max-w-sm text-xs text-ink-500">{description}</p>}
      {action && <div className="mt-2">{action}</div>}
    </div>
  )
}
```

```tsx
// ErrorState.tsx
import type { ReactNode } from "react"
import { TriangleAlert } from "lucide-react"

export interface ErrorStateProps {
  title?: string
  description: string
  action?: ReactNode
}

export function ErrorState({ title = "Couldn't complete this action", description, action }: ErrorStateProps) {
  return (
    <div role="alert" className="flex flex-col items-start gap-2 rounded-lg border border-error/30 bg-surface p-6">
      <div className="flex items-center gap-2 text-error">
        <TriangleAlert className="size-4" aria-hidden="true" />
        <p className="text-sm font-semibold">{title}</p>
      </div>
      <p className="text-sm text-ink-500">{description}</p>
      {action && <div className="mt-1">{action}</div>}
    </div>
  )
}
```

```tsx
// LoadingSpinner.tsx
import { LoaderCircle } from "lucide-react"
import { cn } from "@/lib/utils"

export interface LoadingSpinnerProps {
  className?: string
}

export function LoadingSpinner({ className }: LoadingSpinnerProps) {
  return (
    <span role="status" aria-label="Loading" className={cn("inline-flex text-primary", className)}>
      <LoaderCircle className="size-4 animate-spin" aria-hidden="true" />
    </span>
  )
}
```

```tsx
// PageHeader.tsx
import type { ReactNode } from "react"

export interface PageHeaderProps {
  title: string
  description?: string
  actions?: ReactNode
}

export function PageHeader({ title, description, actions }: PageHeaderProps) {
  return (
    <div className="flex items-start justify-between gap-4 pb-6">
      <div>
        <h1 className="text-2xl font-semibold text-ink-900">{title}</h1>
        {description && <p className="mt-1 text-sm text-ink-500">{description}</p>}
      </div>
      {actions && <div className="flex items-center gap-2">{actions}</div>}
    </div>
  )
}
```

```tsx
// layout/AppShell.tsx
import Link from "next/link"
import type { ReactNode } from "react"

export interface AppShellProps {
  children: ReactNode
  right?: ReactNode
}

export function AppShell({ children, right }: AppShellProps) {
  return (
    <div className="flex min-h-screen flex-col bg-canvas">
      <header className="sticky top-0 z-40 flex h-14 shrink-0 items-center justify-between border-b border-border bg-surface px-4 shadow-sm">
        <Link href="/" className="flex items-center gap-2 text-sm font-semibold text-ink-900">
          <span aria-hidden="true" className="block size-3 bg-primary" />
          AEC Blueprint
        </Link>
        <nav className="flex items-center gap-2">{right}</nav>
      </header>
      <main className="flex-1">{children}</main>
    </div>
  )
}
```

- [ ] **Step 5: Run** `npm test` → Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add frontend/src/components/common frontend/src/components/layout/AppShell.tsx frontend/src/components/common/states.test.tsx frontend/package.json frontend/package-lock.json docs/AEC-Frontend-Design-System-Spec.md
git commit -m "feat(frontend): common states, PageHeader, AppShell"
```

---

### Task 7: `/design-system` styleguide page + cleanup

**Files:**
- Create: `frontend/src/app/design-system/page.tsx`
- Delete: `frontend/src/app/components/ReviewOverlay/ReviewOverlay.tsx` (+ emptied dir)

**Interfaces:**
- Consumes: everything above. Purely presentational reference surface — no tests (visual validation).

- [ ] **Step 1: Write the page** — `'use client'` single file rendering sections: Colors (swatch grid over every token with hex labels pulled from a local constant array mirroring tokens.css), Typography (scale specimen, mono vs sans sample `1,284.50m` vs `999.99m`), Shadows (three cards), Buttons/Badge/Card/Skeleton live samples, ConfidenceBadge all four tiers × both source qualities, States (Empty/Error/Spinner). Route is dev-reference only; pages round supersedes it.

- [ ] **Step 2: Delete ReviewOverlay** `rm -rf "frontend/src/app/components"` (dir holds only that component).

- [ ] **Step 3: Full gate sweep**

```bash
cd frontend
npm run lint && npm run typecheck && npx prettier --write . && npm run format:check && npm test && npm run build
```
Expected: all green.

- [ ] **Step 4: Visual check** — `npm run dev` → open `http://localhost:3000/design-system`: swatches match spec hexes, badge symbols ● ◑ ○ — correct, `[R]` superscript terracotta, tooltips appear on hover.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/app/design-system frontend/src/app/components
git commit -m "feat(frontend): /design-system styleguide; retire ReviewOverlay sketch"
```

---

### Task 8: Session bookkeeping

- [ ] Append progress row to `docs/Memory.md` (foundation landed, gates green, branch name).
- [ ] Update "Open items": frontend foundation ✅; next = pages round (upload/workspace/catalog per spec §5).
- [ ] Commit: `git add docs/Memory.md && git commit -m "docs: memory log for frontend design-system foundation"`

## Self-review notes

- Coverage: spec §1 (tokens/fonts/shadows/motion) → Tasks 2; §2.1 deps → Tasks 1/3/6 + amendment; §6 badges → Tasks 4/5; §8 states → Task 6; §9 conventions/folders/env → structure throughout; §10 out-of-scope respected. Pages (§5) intentionally deferred — next plan.
- Types consistent: `TierKey`/`TierMeta` defined Task 4, consumed Task 5 verbatim; `SourceQuality` defined Task 4, consumed Task 5.
- Known runtime risk flagged for executor: shadcn CLI flag syntax drift — verify against `npx shadcn@latest init --help` output before running; if flags differ, adapt answers (neutral base, cssVariables) rather than hand-rolling `components.json`.
