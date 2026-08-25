# Design System — huzazifa aecc

**Source:** Stitch Project "Avant-Garde Design System" + `docs/

---

## 1. Brand Identity

// add this
**Visual Persona:** "The Safety Authority" — High-contrast, technical, documented.

---

## 2. Color Palette

| Token            | Hex       | Usage                                                               |
| ---------------- | --------- | ------------------------------------------------------------------- |
| **Ink Black**    | `#12130F` | Primary authority, deep backgrounds, heavy headers, primary text    |
| **Safety Amber** | `#F5A623` | CTAs, active nav states, hazard accents, goggle motifs              |
| **Guard Green**  | `#1F7A53` | "Compliant," "Certified," "Eco-Safe" indicators (never for buttons) |
| **Paper**        | `#FAF9F5` | Warm off-white canvas, mimics technical manual paper                |
| **Steel**        | `#5B6660` | Borders, captions, muted data labels                                |
| **Hazard Red**   | `#C43B2E` | Emergency only — high-risk alerts, incident reporting               |

### Extended Palette (from Stitch)

| Token                  | Hex         | Usage                          |
| ---------------------- | ----------- | ------------------------------ |
| Surface Dim            | `#DBDAD6`   | Subtle backgrounds             |
| Surface Container      | `#EFEEEA`   | Card backgrounds               |
| Surface Container High | `#E9E8E4`   | Elevated surfaces              |
| Outline                | `#777870`   | Borders                        |
| Outline Variant        | `#C7C7BF`   | Light borders                  |
| Green Tint             | `#E7F2EC`   | Badge/chip backgrounds         |
| Ink Muted              | `#5B666033` | Transparent steel for overlays |

### Color Application Rules

- **Primary buttons:** Safety Amber on Ink Black (maximum visibility)
- **Guard Green:** Only for reassurance indicators (certifications, safety status)
- **Hazard Red:** Only for emergency/urgent actions
- **Paper:** Default page background
- **Ink Black:** Hero sections, protocol cards, footer

---

## 3. Typography

### Font Stack

| Role               | Font          | Weight   | Usage                                       |
| ------------------ | ------------- | -------- | ------------------------------------------- |
| **Headlines**      | Archivo Black | 900      | High-impact signage, section headers        |
| **Body**           | Inter         | 400, 500 | Paragraphs, navigation, UI text             |
| **Data/Technical** | IBM Plex Mono | 400, 500 | SKU numbers, specs, EPA data, protocol info |

### Type Scale

| Token                | Font          | Size | Line Height | Letter Spacing |
| -------------------- | ------------- | ---- | ----------- | -------------- |
| `headline-xl`        | Archivo Black | 52px | 54px        | -0.01em        |
| `headline-xl-mobile` | Archivo Black | 38px | 40px        | -0.01em        |
| `headline-lg`        | Archivo Black | 32px | 36px        | -0.01em        |
| `headline-sm`        | Archivo Black | 17px | 22px        | —              |
| `body-lg`            | Inter         | 18px | 28px        | —              |
| `body-md`            | Inter         | 14px | 22px        | —              |
| `label-mono`         | IBM Plex Mono | 12px | 16px        | 0.08em         |
| `data-mono`          | IBM Plex Mono | 13px | 26px        | —              |

### Formatting Rules

- **All-caps** with IBM Plex Mono for eyebrows and section tags
- **Sentence-case** for headlines (not ALL CAPS)
- **No decorative fonts** — only the three specified

---

## 4. Spacing & Layout

### Spacing Tokens

| Token             | Value  |
| ----------------- | ------ |
| Container Max     | 1140px |
| Section V-Padding | 64px   |
| Grid Gap          | 44px   |
| Component Gap     | 22px   |
| Margin SM         | 14px   |
| Safe Area         | 28px   |

### Grid System

- **Columns:** 12-column grid
- **Breakpoints:** Mobile-first (320px → 768px → 1024px → 1280px)
- **Container:** Centered, max-width 1140px, padding 28px mobile / 0 desktop
- **Section separation:** 64px vertical padding

### Responsive Behavior

| Breakpoint     | Behavior                                                   |
| -------------- | ---------------------------------------------------------- |
| < 768px        | Single column, headline-xl-mobile (38px), full-width cards |
| 768px - 1024px | 2-column grid, scaled headlines                            |
| > 1024px       | Full 12-column grid, headline-xl (52px)                    |

---

## 5. Elevation & Depth

| Technique                 | Usage                                                |
| ------------------------- | ---------------------------------------------------- |
| **Color blocking**        | Ink Black sections against Paper background          |
| **Low-contrast outlines** | Steel borders on cards and headers                   |
| **Heavy drop-shadow**     | `0 12px 24px rgba(0,0,0,.4)` for large visuals       |
| **Hazard overlays**       | Diagonal amber/transparent stripes at 10-15% opacity |
| **Tonal layering**        | Surface variants for nested cards                    |

---

## 6. Shape Language

| Element      | Radius      | Notes                      |
| ------------ | ----------- | -------------------------- |
| Buttons      | 0-4px       | Technical, slightly sharp  |
| Cards        | 6-8px       | Differentiate from buttons |
| Status chips | 20px (pill) | Certification badges only  |
| Input fields | 4px max     | Strict, rectangular        |

---

## 7. Signature Components

### Goggle Line Divider

- **Stroke:** 2px solid Safety Amber
- **Shape:** Custom SVG wave mimicking PPE goggle silhouette
- **Usage:** Section separators (replace all `<hr>` tags)

### Protocol Card

- **Background:** Ink Black
- **Text:** IBM Plex Mono, white or Guard Green
- **Rows:** Separated by 1px white border at 10% opacity
- **Usage:** Technical specs, dosage tables, safety data

### Service Card

- **Background:** Paper
- **Border:** 1px Steel
- **Title accent:** Miniature amber goggle-line under title
- **Hover:** Subtle elevation change

### Chip/Badge

- **Style:** Pill-shaped (20px radius)
- **Colors:** Guard Green text on Green Tint background
- **Usage:** "Pet-Safe," "EPA-Approved," "Certified"

---

## 8. Button Variants

| Variant     | Background   | Text      | Border          | Usage             |
| ----------- | ------------ | --------- | --------------- | ----------------- |
| **Primary** | Safety Amber | Ink Black | None            | Main CTAs         |
| **Outline** | Transparent  | Ink Black | 1.5px Ink Black | Secondary actions |
| **Danger**  | Hazard Red   | Paper     | None            | Emergency only    |

---

## 9. Form Inputs

- **Border:** 1px Steel
- **Focus:** 2px Safety Amber ring
- **Border radius:** 4px max
- **Labels:** Always visible (not floating)
- **Error state:** Hazard Red border + message

---

## 10. Image Direction

| Rule                   | Detail                                           |
| ---------------------- | ------------------------------------------------ |
| **Technician-centric** | Focus on process and PPE, not pests              |
| **Industrial macro**   | High-contrast, desaturated equipment photography |
| **No fear marketing**  | Avoid "scary bug" tropes                         |
| **Local context**      | Lahore industrial sectors, Pakistani settings    |

---

## 11. Tone of Voice

- **Direct & Technical:** "Initiate lockdown protocols" not "Click here"
- **Evidence-Based:** Pair claims with data ("99.9% Compliance Rate")
- **Regional:** Reference Lahore industrial sectors (Pharma, Agri-Storage, Logistics)
- **Authoritative:** Not salesy — documented, precise, compliant
