# Homepage Redesign Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Rebuild route `/` as a workbench-split homepage (hero band → upload + protocol-card row → steps strip) with token-based entrance motion, preserving every existing behavior, selector, and copy string.

**Architecture:** Presentation-only restructure of `frontend/src/app/page.tsx` inside the untouched `AppShell`. One backward-compatible prop added to `DropZone` (`className` passthrough), two small CSS entrance utilities added to `globals.css`, zero backend changes.

**Tech Stack:** Next.js 16 App Router (React 19), Tailwind v4 with `@theme inline` tokens, shadcn-style UI primitives, Vitest + Testing Library (unit), Playwright `--project=mocked` (e2e).

**Spec:** `docs/superpowers/specs/2026-08-25-homepage-redesign.md`

## Global Constraints

- Header/footer live in `frontend/src/components/layout/AppShell.tsx` — **do not modify that file**.
- Preserve exactly: heading text `Upload a drawing to begin`, `id="upload-heading"`, `data-testid="dropzone"`, button label `Run takeoff →`, all rejection/error copy constants in `DropZone.tsx`.
- All colors/fonts/durations via design tokens only (`frontend/src/styles/tokens.css`) — never hardcode hex values. Motion uses `--ease-out-snappy`, `--duration-base` (220ms); stagger = 50ms steps.
- Animate `transform`/`opacity` only. No `transition: all`. No `ease-in`. No entrance longer than 300ms. Nothing keyboard-initiated animates.
- This is NOT the Next.js you know: read `frontend/node_modules/next/dist/docs/` guides before writing Next-specific APIs (this plan touches none beyond what `page.tsx` already uses).
- Package manager is Bun; run frontend commands from `frontend/`.
- No code comments. No emojis.
- Unit tests: `bun run test` (Vitest). E2e mocked (no backend needed): `bun run test:e2e`.

---

### Task 1: DropZone `className` passthrough

**Files:**
- Modify: `frontend/src/components/upload/DropZone.tsx`
- Test: `frontend/src/components/upload/upload.test.tsx` (inside `describe("DropZone", ...)`)

**Interfaces:**
- Consumes: nothing new.
- Produces: `DropZoneProps` gains optional `className?: string`, merged onto the root drop area div (the element carrying `data-testid="dropzone"`). Later tasks pass `className="min-h-64 bg-canvas"`.

- [ ] **Step 1: Write the failing test**

In `upload.test.tsx`, add inside `describe("DropZone", ...)` after the existing two tests:

```tsx
  it("applies a custom className to the drop area", () => {
    const onFile = vi.fn()
    render(<DropZone onFile={onFile} className="min-h-64" />)
    expect(screen.getByTestId("dropzone")).toHaveClass("min-h-64")
  })
```

- [ ] **Step 2: Run test to verify it fails**

Run: `bun run test -- src/components/upload/upload.test.tsx`
Expected: FAIL — `toHaveClass("min-h-64")` does not match because the prop is ignored.

- [ ] **Step 3: Write minimal implementation**

In `DropZone.tsx`: extend the props interface and merge `className` onto the root drop-area `div` (after the base class string, before conditional state classes):

```tsx
export interface DropZoneProps {
  onFile: (file: File) => void
  disabled?: boolean
  className?: string
}

export function DropZone({ onFile, disabled = false, className }: DropZoneProps) {
```

and change the root div call to:

```tsx
        className={cn(
          "flex min-h-48 cursor-pointer flex-col items-center justify-center gap-2 rounded-lg border border-dashed p-8 text-center outline-none transition-colors focus-visible:border-ring focus-visible:ring-3 focus-visible:ring-ring/50",
          className,
          isDragActive && !isDragReject && "border-primary bg-primary/5",
          isDragReject && "border-error bg-error/5",
          disabled && "pointer-events-none opacity-60",
        )}
```

Also give the upload icon its drag-over nudge (transform + opacity properties only, named transitions):

```tsx
        <UploadCloud
          className={cn(
            "size-6 text-ink-300 transition-[color,transform] duration-(--duration-fast)",
            isDragActive && !isDragReject && "-translate-y-0.5 text-primary",
            isDragReject && "text-error",
          )}
          aria-hidden="true"
        />
```

(`duration-(--duration-fast)` binds to the `--duration-fast` token = 120ms, so reduced-motion zeroing applies automatically.)

- [ ] **Step 4: Run test to verify it passes**

Run: `bun run test -- src/components/upload/upload.test.tsx`
Expected: PASS (all tests in file).

- [ ] **Step 5: Commit**

```bash
git add frontend/src/components/upload/DropZone.tsx frontend/src/components/upload/upload.test.tsx
git commit -m "feat(frontend): DropZone className passthrough for homepage sizing"
```

---

### Task 2: Entrance-motion utilities in `globals.css`

**Files:**
- Modify: `frontend/src/app/globals.css`

**Interfaces:**
- Consumes: tokens `--duration-base`, `--ease-out-snappy` from `frontend/src/styles/tokens.css` (already global).
- Produces: three CSS classes used verbatim by Task 3: `.rise-in` (opacity 0→1 + translateY(12px)→0 over `--duration-base`, `--ease-out-snappy`, `animation-fill-mode: both`), `.rise-in-d1` (+50ms delay), `.rise-in-d2` (+100ms delay). Reduced motion needs no extra rules: `tokens.css` zeroes the duration variables under `prefers-reduced-motion`, making entrances instant while keeping final state via `both`.

- [ ] **Step 1: Add keyframes and utilities**

Append to the end of `globals.css`:

```css
@layer components {
  .rise-in {
    animation: rise-in var(--duration-base) var(--ease-out-snappy) both;
  }

  .rise-in-d1 {
    animation-delay: 50ms;
  }

  .rise-in-d2 {
    animation-delay: 100ms;
  }
}

@keyframes rise-in {
  from {
    opacity: 0;
    transform: translateY(12px);
  }
  to {
    opacity: 1;
    transform: translateY(0);
  }
}
```

- [ ] **Step 2: Verify formatting**

Run: `bun run format:check -- src/app/globals.css` (or `bunx prettier --check src/app/globals.css`)
Expected: PASS. Fix with `bunx prettier --write src/app/globals.css` if needed.

Real behavioral validation happens in Task 3's e2e run (page loads without console errors; Playwright asserts visibility after animations complete — `both` fill guarantees final-state opacity 1 even mid-stagger).

- [ ] **Step 3: Commit**

```bash
git add frontend/src/app/globals.css
git commit -m "feat(frontend): rise-in entrance utilities on motion tokens"
```

---

### Task 3: Homepage workbench restructure

**Files:**
- Modify: `frontend/e2e/home-upload.spec.ts` (extend first test's assertions)
- Modify: `frontend/src/app/page.tsx` (JSX return only — all hooks/handlers/state logic stays byte-identical)

**Interfaces:**
- Consumes: `DropZone` with `className` (Task 1); `.rise-in`, `.rise-in-d1`, `.rise-in-d2` (Task 2); existing components `HazardStripe`, `GoggleLineDivider`, `ProtocolCard` (`rows: {label, value, valueTone?}[]`), `QualityGateBadge`, `ReexportRequest`, `ErrorState`, `LoadingSpinner`, `Button`.
- Produces: no exports. E2e relies on new visible strings: `Pipeline contract`, `01`, `02`, `03`, `Quality gate`, `Deterministic takeoff`, `Human review`.

- [ ] **Step 1: Extend the failing e2e assertions**

In `e2e/home-upload.spec.ts`, extend the first test (after the Catalog link assertion):

```ts
  await expect(page.getByText("Pipeline contract")).toBeVisible()
  await expect(page.getByText("Deterministic takeoff")).toBeVisible()
```

Run: `bun run test:e2e -- e2e/home-upload.spec.ts -g "home renders"`
Expected: FAIL — "Pipeline contract" not found.

- [ ] **Step 2: Restructure `page.tsx`**

Replace the entire `return (...)` JSX with the layout below. Do not touch anything above the return statement (imports gain `ProtocolCard`; everything else unchanged):

```tsx
  const STEPS = [
    {
      n: "01",
      title: "Quality gate",
      body: "Layer and text metrics classify the sheet as layered, degraded, or raster before anything runs.",
    },
    {
      n: "02",
      title: "Deterministic takeoff",
      body: "Geometry engines measure; rule assemblies derive quantities. No model ever guesses a number.",
    },
    {
      n: "03",
      title: "Human review",
      body: "Every line item carries provenance and a confidence tier you can accept or correct.",
    },
  ] as const
```

(`STEPS` is module-level, above the component.)

Return JSX:

```tsx
  return (
    <AppShell>
      <div className="mx-auto flex w-full max-w-5xl flex-col gap-8 px-4 py-8">
        <section
          aria-labelledby="upload-heading"
          className="rise-in overflow-hidden rounded-2xl bg-ink-black p-8 pt-0 sm:p-10 sm:pt-0"
        >
          <HazardStripe className="-mx-8 mb-6 sm:-mx-10" />
          <p className="label-mono text-safety-amber">Huzaifa AEC · Takeoff</p>
          <h1
            id="upload-heading"
            className="mt-3 font-heading text-[40px] leading-[44px] tracking-[-0.01em] text-paper md:text-[52px] md:leading-[54px]"
          >
            Upload a drawing to begin
          </h1>
          <p className="mt-4 max-w-xl text-sm leading-6 text-paper/70">
            AI proposes · Geometry calculates · Rules derive · Humans approve. Every quantity traces
            back to a deterministic measurement on your drawing.
          </p>
          <GoggleLineDivider className="mt-5 w-44" />
        </section>

        <div className="rise-in rise-in-d1 grid gap-6 lg:grid-cols-[minmax(0,1fr)_320px]">
          <div className="flex flex-col gap-6">
            <div className="rounded-lg border border-outline-variant bg-surface-container p-4">
              <DropZone
                onFile={checkFile}
                disabled={phase === "checking"}
                className="min-h-64 bg-canvas"
              />
            </div>

            {phase === "checking" && (
              <p className="flex items-center gap-2 text-sm text-ink-500 rise-in">
                <LoadingSpinner />
                Checking drawing structure...
              </p>
            )}

            {(phase === "ready" || phase === "running") && (
              <section aria-label="Quality check" className="flex flex-col gap-6 rise-in">
                <div className="flex items-center gap-3" aria-hidden="true">
                  <GoggleLineDivider className="flex-1 opacity-50" />
                  <span className="label-mono text-steel">Quality check</span>
                  <GoggleLineDivider className="flex-1 scale-x-[-1] opacity-50" />
                </div>

                {checkFailed ? (
                  <ErrorState description={QUALITY_CHECK_FAILED_COPY} />
                ) : (
                  quality && (
                    <>
                      <QualityGateBadge quality={quality} />

                      {isDegraded && drawingId && <ReexportRequest drawingId={drawingId} />}
                      {isDegraded && !continueAnyway && phase === "ready" && (
                        <div>
                          <Button variant="outline" onClick={() => setContinueAnyway(true)}>
                            Continue anyway →
                          </Button>
                        </div>
                      )}

                      {showRunButton && (
                        <div className="flex justify-end">
                          <Button size="lg" onClick={startRun}>
                            Run takeoff →
                          </Button>
                        </div>
                      )}
                    </>
                  )
                )}
              </section>
            )}

            {phase === "running" && (
              <p className="flex items-center gap-2 text-sm text-ink-500 rise-in">
                <LoadingSpinner />
                Running takeoff…
              </p>
            )}

            {runFailureDetail && (
              <ErrorState title="Couldn't complete the takeoff" description={runFailureDetail} />
            )}
          </div>

          <aside>
            <ProtocolCard
              title="Pipeline contract"
              className="rise-in"
              rows={[
                { label: "Verdict rule", value: "measured > derived > assumed" },
                { label: "Input", value: "PDF ≤ 50 MB" },
                { label: "Scale", value: "auto · flagged if assumed" },
                { label: "Output", value: "BOQ → review" },
                { label: "Quantities", value: "deterministic only", valueTone: "verified" },
              ]}
              footer={<p className="label-mono text-paper/50">No model ever outputs a number</p>}
            />
          </aside>
        </div>

        <ol className="rise-in rise-in-d2 grid gap-4 sm:grid-cols-3">
          {STEPS.map((step) => (
            <li
              key={step.n}
              className="rounded-lg border border-outline-variant bg-paper p-5 transition-colors hover:border-safety-amber"
            >
              <p className="label-mono text-steel">Step {step.n}</p>
              <h2 className="mt-1 font-heading text-[17px] leading-[22px] text-ink-black">
                {step.title}
              </h2>
              <GoggleLineDivider className="mt-2 w-16" />
              <p className="mt-2 text-sm leading-[22px] text-ink-500">{step.body}</p>
            </li>
          ))}
        </ol>
      </div>
    </AppShell>
  )
```

Notes:
- The old wrapper classes (`max-w-xl`, `gap-6`, `py-12`) are replaced; hero padding switches to `sm:p-10` with matching negative margins on the stripe.
- `max-w-5xl` replaces `max-w-xl`; the workbench grid stacks below `lg`.
- Step-card hover is border-color only (touch-safe; no hover gating required).

- [ ] **Step 3: Verify e2e passes**

Run: `bun run test:e2e -- e2e/home-upload.spec.ts`
Expected: PASS — both home-render and full upload-flow tests green (upload flow exercises check → badge → run → redirect through the new layout).

- [ ] **Step 4: Verify unit suite unaffected**

Run: `bun run test`
Expected: PASS — full Vitest suite green (63+ tests; DropZone/quality/reexport suites untouched behaviorally).

- [ ] **Step 5: Commit**

```bash
git add frontend/src/app/page.tsx frontend/e2e/home-upload.spec.ts
git commit -m "feat(frontend): homepage workbench redesign — hero, protocol card, steps strip"
```

---

### Task 4: Verification sweep + session memory

**Files:**
- Modify: `docs/Memory.md` (session-state tracker — AGENTS.md requires updating it every session)

**Interfaces:**
- Consumes: completed Tasks 1–3.
- Produces: recorded session state for future sessions.

- [ ] **Step 1: Static gates**

From `frontend/`: `bun run typecheck && bun run lint && bun run format:check`
Expected: all PASS. If prettier flags files, run `bun run format` and re-stage.

- [ ] **Step 2: Full test sweep**

From `frontend/`: `bun run test && bun run test:e2e`
Expected: unit suite + mocked e2e project fully green.

- [ ] **Step 3: Feel-check (manual)**

Start `bun run dev`, load `/`: confirm stagger reads hero → workbench → steps (~300ms total), drag-over feedback fires, and DevTools "Emulate prefers-reduced-motion: reduce" renders everything instantly with no stuck invisible sections.

- [ ] **Step 4: Update docs/Memory.md**

Append/refresh the session entry: homepage workbench redesign shipped (spec `docs/superpowers/specs/2026-08-25-homepage-redesign.md`, this plan), files touched (`page.tsx`, `DropZone.tsx`, `upload.test.tsx`, `globals.css`, `home-upload.spec.ts`), and verification results.

- [ ] **Step 5: Commit**

```bash
git add docs/Memory.md
git commit -m "docs: session memory — homepage redesign shipped"
```
