# Design — Visual System

Applies to the web interface (Next.js + TypeScript), primarily the **Human Review UI** — the screen estimators stare at. Aesthetic goal: precision, calm, engineering-grade. Nothing cute; everything legible on a large monitor next to a real drawing.

---

## 1. Design principles

- **The drawing is the star.** UI chrome must never compete with the rendered blueprint (light/dark panels, muted tones).
- **Numbers must be readable at a glance.** Tabular data uses high-contrast mono or tabular numerals.
- **Confidence is communicated, not hidden.** Status is a colored tag, not a footnote.
- **Click → see geometry.** The review overlay is the core screen; design it first.

## 2. Theme: Dark engineering

Default to a dark, low-saturation "drafting room" theme; light theme optional later.

| Token | Value | Usage |
|---|---|---|
| `bg-base` | `#10141A` | App background (dark slate) |
| `bg-panel` | `#161C24` | Panels, cards, sidebar |
| `bg-elevated` | `#1D2530` | Modals, popovers, hover |
| `border-subtle` | `#262F3B` | Borders, dividers |
| `text-primary` | `#E6EAF0` | Body text |
| `text-secondary` | `#9AA7B8` | Labels, meta |
| `text-muted` | `#5B6B7E` | Disabled, placeholders |

## 3. Accent & semantic colors

| Token | Value | Usage |
|---|---|---|
| `accent` | `#3E9BFF` | Primary actions, selection, links |
| `ok` | `#34C77B` | `MEASURED` status |
| `derived` | `#E5A02E` | `DERIVED` status (amber) |
| `assumed` | `#E8554D` | `ASSUMED` status (red — forces review) |
| `unmapped` | `#D2B48C` | `UNMAPPED` status (tan — measured but no rule yet) |
| `highlight` | `#7C5CFF` | Selected BOQ line / source-geometry overlay |

Confidence colors are a **hard product rule**: green/amber/red/tan map 1:1 to `MEASURED`/`DERIVED`/`ASSUMED`/`UNMAPPED`. Never render confidence as a generic gray or as a single blended % gauge.

**Source-quality tagging (spec v3):** every BOQ line also shows its input provenance — `layered_vector`, `degraded_vector`, or `raster`. Render it as a subtle suffix badge on the confidence tag (e.g. `MEASURED · flattened`), never as a second color-coded system and never as a blended score. Rows from `degraded_vector`/`raster` sources get a dashed left border in the row's confidence color and are excluded from bulk-accept preselection regardless of tier. No new accent color is introduced for provenance — reuse `text-secondary`; provenance is context, not alarm.

## 4. Typography

| Role | Font | Notes |
|---|---|---|
| UI / body | Inter | Primary interface font |
| Numeric tables | Inter with `font-feature-settings: "tnum"` (or JetBrains Mono) | Tabular figures so BOQ columns align |
| Monospace / code | JetBrains Mono | Layer names, rule IDs, file paths |
| Blueprint annotations | system mono / blueprint font | only on the drawing overlay, matching sheet style |

Scale: 13px base, 15px table data, 18px section titles, 24px page titles. Never go below 12px. Dense but not cramped — spacing ≥ 4px grid.

## 5. Layout

- **Three-pane review screen** (the flagship view):
  - Left: drawing canvas (rendered PDF via `pdf.js`) with overlay highlights per discipline.
  - Center/right: BOQ table — each row = quantity, unit, unit price, total, confidence tag.
  - Click row → center highlight jumps to source geometry; click geometry → row selected.
  - Top bar: project, sheet name, scale badge, processing status pill, export actions, discipline filter dropdown.
- Status pills: `QUEUED` · `PARSING` · `DONE` · `ERROR` · `DEGRADED_INPUT` (Input Quality Gate flagged the file; tooltip explains, and in closed deployment offers the re-export request action) — with reason tooltip on error.
- Accept / correct / reject actions inline per row; bulk-accept bar appears when a selection is all `MEASURED` **and** all `layered_vector`.
- Discipline filter: filter BOQ items by classified layer discipline (architectural, electrical, envelope, structural, unclassified).
- Layer filter: filter BOQ items by specific layer name within the selected discipline.
- Source-quality filter (spec v3): `layered_vector` / `degraded_vector` / `raster` — composable with discipline and layer filters.
- Review-time instrumentation runs invisibly: time-on-sheet logged server-side per confidence tier (feeds `GET /projects/{id}/review-metrics`). Never show a visible timer to the estimator.
- When multiple disciplines are present, group the BOQ by discipline with collapsible sections.

## 6. Drawing overlay colors

Overlay strokes must read against any CAD linework:

| Element | Color | Stroke |
|---|---|---|
| Component box | `accent` | 1.5px, filled 8% opacity |
| Route polyline | `#2FC6C0` | 2px |
| Highlight (active) | `highlight` | 2.5px glow |
| Review-needed | `assumed` dashed | 1.5px dashed |
| Unmapped overlay | `unmapped` dashed | 1.5px dashed — geometry measured but no assembly rule yet |

## 7. Empty & error states

- Empty project: "Upload a drawing to begin" + drop zone, never a blank page.
- Processing: sheet thumbnail with progress + current stage label.
- Degraded input (spec v3): banner on the sheet view — "This file has no layer data. Re-export with layers included, or upload the native DWG/DXF." with a **Request re-export** action; downstream rows stay visible but carry `degraded_vector` provenance badges and are excluded from bulk-accept.
- Error: reason + retry button; no dead ends.

## 8. Implementation notes

- Tailwind CSS (v4, matches existing stack) with CSS variables for the tokens above.
- Overlay: SVG positioned over the `pdf.js` canvas (shared coordinate transform).
- Dark theme default; tokens centralized so a light theme can drop in later.