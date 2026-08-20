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
| `highlight` | `#7C5CFF` | Selected BOQ line / source-geometry overlay |

Confidence colors are a **hard product rule**: green/amber/red map 1:1 to `MEASURED`/`DERIVED`/`ASSUMED`. Never render confidence as a generic gray or as a single blended % gauge.

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
  - Left: drawing canvas (rendered PDF via `pdf.js`) with overlay highlights.
  - Center/right: BOQ table — each row = quantity, unit, unit price, total, confidence tag.
  - Click row → center highlight jumps to source geometry; click geometry → row selected.
- Top bar: project, sheet name, scale badge, processing status pill, export actions.
- Status pills: `QUEUED` · `PARSING` · `DONE` · `ERROR` — with reason tooltip on error.
- Accept / correct / reject actions inline per row; bulk-accept bar appears when a selection is all `MEASURED`.

## 6. Drawing overlay colors

Overlay strokes must read against any CAD linework:

| Element | Color | Stroke |
|---|---|---|
| Component box | `accent` | 1.5px, filled 8% opacity |
| Route polyline | `#2FC6C0` | 2px |
| Highlight (active) | `highlight` | 2.5px glow |
| Review-needed | `assumed` dashed | 1.5px dashed |

## 7. Empty & error states

- Empty project: "Upload a drawing to begin" + drop zone, never a blank page.
- Processing: sheet thumbnail with progress + current stage label.
- Error: reason + retry button; no dead ends.

## 8. Implementation notes

- Tailwind CSS (v4, matches existing stack) with CSS variables for the tokens above.
- Overlay: SVG positioned over the `pdf.js` canvas (shared coordinate transform).
- Dark theme default; tokens centralized so a light theme can drop in later.