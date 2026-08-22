# AEC Blueprint Intelligence System — Phase 3 Addendum: Multi-Domain Extraction Upgrade

**Status:** Proposed addendum to `AEC-Blueprint-System-Design-Spec.md`
**Trigger:** Current implementation extracts one domain only (`access control`). Goal: extract the maximum recoverable data across *every* domain present in a sheet, not just the domain the sheet is titled after.
**Relationship to existing docs:** This does not replace `AEC-Blueprint-System-Design-Spec.md` — the architecture decision (hybrid, vector-first, rules-driven, human-verified), the guiding principle in Section 2, and the tech stack in Section 9 all still hold. This addendum modifies Sections 7.1, 7.2, 7.4, 7.8, 8, and 12 specifically, based on a fresh, direct inspection of the actual sample file rather than a re-read of the prior analysis.

---

## 1. New ground truth — re-verified directly against the sample PDF

The existing spec's Section 5 numbers were re-derived independently (not copied) by opening `MMC-JVC-CD-ELEC-3902_AC-WIRE-Model.pdf` with `pikepdf` and `pdfminer.six` and walking the actual content stream. They check out — **and walking the content stream surfaced something the original analysis didn't capture: which layer owns *how much* of the drawing.**

- 1 page, 842×1191pt. 2 embedded raster images (both title-block logos — confirmed by XObject inspection, not estimated).
- 46 Optional Content Groups (CAD layers), full list enumerated (the original analysis sampled ~10 of them). They span five distinct disciplines, not one:
  - **Architectural:** `M_SAUDI_WALL_PRHT`, `M_SAUDI_DOOR`, `M_SAUDI_DOOR_HIDEN`, `M_SAUDI_STAIRS`, `M_SAUDI_STAIRS_HIDDEN`, `M_SAUDI_STAIRS_PARAPET`, `M_SAUDI_AREAS`, `M_SAUDI_ROOM-area`, `M_SAUDI_ROOM-nametr`, `M-PART-GLZW_identy` (glazing), `M_SAUDI_FURNITURE_LIGHTING`, `A-ELEV-0301`
  - **Electrical (multiple subsystems, not just access control):** `access control`, `FIRE ALARM`, `NORMAL TRAY`, `E-PWER-CABL-TRAY-HATCH`, `E-lt-fix-nm-clg` (ceiling lighting fixtures), `ADO CCTV LEADER`
  - **MEP-adjacent / envelope:** `M_SAUDI_WATER_INSULATING`, `M_SAUDI_VENT_identy`, `M_SAUDI_RAIN DOWNPIPE`, `M_SAUDI_INSULATING`
  - **Structural/material metadata:** `M_SAUDI_METAL`, `M_SAUDI_METAL_PROFILE`, `M_SAUDI_METAL_SEC`, `M_SAUDI_MAT`, `M_SAUDI_PATT`, `M_SAUDI_NPLT`, `M_SAUDI_PRPT`, `M_SAUDI_AGRAF`, `M_SAUDI_DOT`, `M_SAUDI_ACCESSORY`, `M_SAUDI_ACCESSORY_AXIS`, `M_SAUDI_HIDDEN`
  - **Annotation:** `A-ANNO-SYMB`, `A-ANNO-TITL`, `M_SAUDI_TEXT_50`, `M_SAUDI_TEXT_GENERAL`, `M_SAUDI_SHEET`, `M_SAUDI_SIMBOL`
- **89,337 vector path-painting operations total** (76,991 lines, 12,175 curves, 171 rects — matches the ~88,523 figure).

**The number that changes the plan:** attributing every paint operation to the OCG that was active when it was drawn gives an exact per-layer breakdown. `access control` — the *only* layer the current pipeline reads — accounts for **296 operations, 0.3% of the sheet's vector content.** The other 99.7% is sitting in the same file, already layer-separated, completely unread by the current implementation:

| Layer | Paint ops | % of sheet | Domain |
|---|---|---|---|
| `M_SAUDI_AREAS` | 59,112 | 66.8% | Architectural — room/space polygons |
| `M_SAUDI_NPLT` | 11,675 | 13.2% | Material/hatch pattern |
| `M_SAUDI_DOT` | 4,828 | 5.5% | Grid/dimension markers |
| `E-PWER-CABL-TRAY-HATCH` | 3,453 | 3.9% | Electrical — power cable tray |
| `M_SAUDI_WATER_INSULATING` | 2,839 | 3.2% | Envelope — waterproofing |
| `M_SAUDI_STAIRS_HIDDEN` | 1,190 | 1.3% | Architectural — stairs |
| `E-lt-fix-nm-clg` | 1,093 | 1.2% | Electrical — ceiling lighting |
| `M_SAUDI_METAL_SEC` | 706 | 0.8% | Structural — metal sections |
| `M_SAUDI_DOOR_HIDEN` | 537 | 0.6% | Architectural — doors |
| `access control` | 296 | 0.3% | Electrical — access control (current MVP scope) |
| `ADO CCTV LEADER` | 230 | 0.3% | Electrical — CCTV |
| *(35 more layers)* | ~1,600 | ~1.8% | Mixed |

- **Text is also layer-tagged, independently of geometry.** Walking `Tj`/`TJ` operators through the same `BDC /OC … EMC` nesting shows room *names* and room *areas* are drawn on their own dedicated layers — `M_SAUDI_ROOM-nametr` (41 text-show ops) and `M_SAUDI_ROOM-area` (82 ops) — separate from the room *polygon* layer (`M_SAUDI_AREAS`). All three are siblings, not nested inside each other, so associating a room's name+area text to its polygon is a **spatial join, not a stream-nesting relationship.** This is a small but real technical detail the current design doesn't address anywhere, because it never needed to for a single symbol-heavy layer like `access control`.
- Free-floating schedule text — the elevator specification block (`Max Transport Weight (kg):513`, `Device Weight (kg):687`, `Load per machine foot 1.7 kN`, etc.), ramp slope callouts (`DECLINE RAMP SLOPE %15.2 - 2100cm`), and parking bay IDs (`B2-V01` … `B2-V19`) visible in the raw sheet — is **largely untagged by OCG** (it fell almost entirely into the "no layer / base" or generic `0` bucket in the content-stream walk). This is a structurally different extraction problem from everything else on the sheet: it can't be reached by layer-filtering at all. It needs spatial clustering of nearby text runs into "blocks," then pattern-matching against known AEC schedule formats.

This single sheet — nominally an electrical access-control drawing — is actually proof that **one CAD-exported PDF already contains architectural, electrical (multiple subsystems), envelope, and structural-metadata information, cleanly separated by layer**, plus a smaller amount of schedule/dimension data that isn't layer-separated and needs a different technique. That's the concrete basis for the plan below.

---

## 2. Maximum data retrieval — strategy

The current design's ingestion engine (Spec §7.2) does one thing: filter to a named layer, cluster, classify against a legend. To get "everything," that needs to become three explicit strategies, applied per-layer according to what kind of layer it is — not one strategy applied to one hardcoded layer name.

**A. Symbol-instance clustering** (what you already have, generalized)
Point-like devices where a cluster of short line segments = one instance: access-control devices, lighting fixtures, CCTV cameras, fire alarm devices. Same DBSCAN-on-bbox-centroid approach already built for `access control`; the only change is that it needs to run once per *classified* layer instead of once against a hardcoded string.

**B. Polygon/region reconstruction** (new — needed for the 66.8% you're currently missing)
`M_SAUDI_AREAS` is not symbol instances, it's room boundaries made of many short line segments that need to be reassembled into closed polygons. This is a different geometric operation:
```python
from shapely.ops import polygonize
from shapely.geometry import LineString

segments = [LineString([(p['p1']), (p['p2'])]) for p in layer_paths]
rooms = list(polygonize(segments))   # closed faces = candidate rooms
```
Not every polygon `polygonize` returns will be a room (hatch fills, dimension boxes will also close) — filter by area threshold and cross-check against the paired name/area text (see C) before accepting a polygon as a `Space`. If `polygonize` leaves gaps on messier sheets, budget a fallback using `networkx` for planar-graph face detection — cheap to try, not worth building until a sheet actually breaks the simple approach.

**C. Text–layer association walker** (new — required for B to be trustworthy, and for schedules)
PyMuPDF's `get_drawings()` returns a `layer` key per path (confirmed reliable), but its high-level `get_text('dict')` does not carry OCG membership the same way. Verify this against your actual PyMuPDF version before building around it — if it doesn't, the fallback is a content-stream walker tracking `BDC /OC … EMC` nesting around `Tj`/`TJ` operators (prototyped and validated against this sample using `pikepdf.parse_content_stream` — it correctly separated all 388 text-show operations by controlling layer). Once each text span has a layer, join `M_SAUDI_ROOM-nametr` + `M_SAUDI_ROOM-area` text to the nearest `M_SAUDI_AREAS` polygon centroid to get a labeled, area-verified `Space` row — geometry measures the area, text confirms the label, no model involved, in keeping with the guiding principle.

**D. Schedule/attribute-block parser** (new — for the untagged text)
Elevator specs, ramp slopes, parking counts aren't layer-taggable, so they need: spatial clustering of nearby text runs (a tight bbox of many short lines is probably one schedule block) → run a small library of regex patterns for known AEC field formats (`"<label> \(<unit>\):<value>"`, `"%<slope> - <run>cm"`, `"<block-prefix>-<letter><NN>"`) → anything the regex library doesn't match falls through to the LLM interpretation tier for a proposed classification, which a human confirms. This is the same "AI proposes, geometry/rules decide" pattern the spec already uses for legend interpretation — it just needs a second, generic implementation instead of one hardcoded to the access-control legend table.

**E. Legend/schedule-table generalization**
The spec's legend-matching step (§7.3, §7.9) is currently written around *one* legend table. Generalize it to detect *any* tabular symbol-key block on a sheet (this file alone has the access-control legend in the title block *and* a de-facto elevator schedule in the drawing body) and match cluster counts against whichever table is present, rather than assuming exactly one legend per sheet.

---

## 3. Gap analysis against the current design spec

| # | Gap | Where it shows up in the current spec | Why it blocks "extract everything" |
|---|---|---|---|
| 1 | No layer classification/taxonomy step exists | §7.1 (router only decides vector vs. raster vs. CAD), §7.2 (assumes you already know which layer to filter) | Nothing in the pipeline decides *which* of the 46 layers matter or what discipline they belong to — that decision is currently hardcoded to one string, `"access control"` |
| 2 | Canonical model schema is domain-agnostic but nothing populates most of it | §7.4 already defines `Component`, `Route`, `Space`, `Structural element`, `Annotation` — the schema was built for this | `Space` has existed in the design since day one and has never been populated; the gap is entirely in ingestion coverage, not data modeling |
| 3 | Text extraction is layer-blind | §7.2 lists `page.get_text('dict')` with no mention of OCG association | Can't cleanly label a `Space` polygon with its room name/area without this |
| 4 | Only one clustering strategy is specified | §7.2, single DBSCAN-on-symbol-cluster approach | Room polygons and cable/route polylines need different reconstruction logic, not just a different layer name plugged into the same function |
| 5 | Only one legend-parsing implementation is specified | §7.3, §7.9 — legend-matching described in the singular | This sheet alone has two schedule-like tables; a generalized implementation is needed even before adding new disciplines |
| 6 | Confidence tiering has no status for "measured but not yet costed" | §7.8 — three statuses: `MEASURED`/`DERIVED`/`ASSUMED` | If a `Space` gets its area measured but no room-finish assembly rule exists yet, current tiering has no honest way to represent that — it either gets forced into `ASSUMED` (wrong) or silently dropped |
| 7 | No spatial-conflict handling across layers | Not addressed anywhere in current spec | A wall from `M_SAUDI_WALL_PRHT` and a room boundary from `M_SAUDI_AREAS` will geometrically overlap; extracting one domain in isolation never surfaces this, extracting all of them will |
| 8 | Review UI granularity assumes ~single-legend-sized review batches | §7.9 — "click a BOQ line → highlight source" | Fine at one-layer scale (a few dozen access-control devices); at 46-layer scale needs filtering/grouping by discipline and by layer-classification confidence, or a human reviewer is stuck scrolling one flat list |
| 9 | Roadmap sequences disciplines serially | §12 — Phase 2 Electrical, Phase 3 Mechanical, Phase 4 Plumbing… | This directly conflicts with the "extract everything present" goal: a mechanical drawing you haven't reached yet in the roadmap may still contain architectural or electrical data worth extracting *today*. Extraction breadth and assembly-rule depth should be decoupled (see §6 below) |

---

## 4. Technical requirements for Phase 3

### New component: Layer Registry & Domain Classifier
Sits right after ingestion routing (§7.1), before clustering (§7.2).
- Enumerate every OCG on every sheet (`doc.get_ocgs()` or equivalent).
- Classify each by regex against a human-editable config, e.g.:
```yaml
layer_classification_rules:
  - pattern: '^(M_SAUDI_(WALL|DOOR|STAIRS|ROOM|AREAS)|M-PART-GLZW)'
    discipline: architectural
  - pattern: '^(E-|ADO |FIRE ALARM|NORMAL TRAY|access control)'
    discipline: electrical
  - pattern: '^M_SAUDI_(WATER_INSULATING|VENT_identy|RAIN)'
    discipline: envelope
  - pattern: '.*'
    discipline: unclassified   # always fall through here, never silently drop
```
- Persist the classification per sheet (new `LAYER` table, see §5), human-correctable, so a misclassified or ambiguous layer surfaces in review rather than being silently skipped.

### Modified component: Vector parsing engine (§7.2)
Branch by the layer's classified *geometry type*, not by a hardcoded layer name — run strategy A, B, or C from §2 depending on whether the classifier tags the layer as symbol/region/route.

### New component: Text–Layer Association Walker
Implements strategy C from §2. First check whether your installed PyMuPDF version exposes OCG membership on text spans directly; if not, fall back to a `BDC/EMC`-tracking content-stream walker as prototyped. Output: every text span tagged with its controlling layer (or "untagged" if none), ready for the spatial join in the next component.

### New component: Generic Schedule & Attribute-Block Parser
Implements strategy D from §2. Config-driven regex pattern library (new file, same spirit as the assembly YAML in §7.5) for common AEC schedule field shapes, with LLM fallback for anything unmatched — matches the existing guiding principle without adding a new exception to it.

### Extended component: Confidence tiering (§7.8)
Add a fourth status:

| Status | Meaning |
|---|---|
| `UNMAPPED` | Geometry/text was measured successfully but no assembly rule exists yet to turn it into a costed BOQ line |

This decouples "did we look" from "can we price it yet" — the two are currently conflated because MVP scope made them the same thing by accident.

---

## 5. Data model changes (extends Spec §8)

```
LAYER {
  uuid id PK
  uuid sheet_id FK
  string ocg_name
  string discipline_classification
  float classification_confidence
  bool human_confirmed
}
```
`COMPONENT.source_layer`, `ROUTE.source_layer`, and `SPACE` (currently has no source-layer field at all in §8 — add one) become foreign keys into `LAYER` instead of free strings. This is what makes discipline-level filtering possible in the review UI (gap #8) and per-layer accuracy tracking possible (extending §14's per-tier tracking to per-layer).

```
SCHEDULE_BLOCK {
  uuid id PK
  uuid sheet_id FK
  string block_type        -- e.g. "elevator_spec", "legend_table"
  json parsed_fields        -- key: value pairs, each with its own confidence
  string source_region
}
```
Handles the elevator-spec-style free text and generalizes the existing legend table handling into the same structure.

No changes needed to `MEASUREMENT`, `BOQ_ITEM`, `ASSEMBLY`, `MATERIAL`, or `PRICE` — the audit-trail design in §8 already generalizes cleanly across domains, it just needs more upstream data feeding it.

---

## 6. Step-by-step continuation plan (from your current pre-Phase 3 state)

1. **Layer Registry spike.** Enumerate + classify all 46 layers on the sample sheet (the classification table in §1 above is your starting fixture and expected output). Confirm the config-driven approach before writing anything downstream.
2. **Space extraction as the second proof case, after access control.** Highest value, lowest cost: 66.8% of the sheet's geometry, cleanly separable, with paired name/area text already on its own layers. Implement strategy B + C from §2 end-to-end against `M_SAUDI_AREAS` / `M_SAUDI_ROOM-area` / `M_SAUDI_ROOM-nametr` and get real `Space` rows out.
3. **Generalize clustering** so strategy (A/B/C) is selected by the Layer Registry's classification, not by which function you happened to call.
4. **Build the text–layer association walker**, validate it two ways: it should still correctly resolve `access control` legend text (regression) *and* correctly pair room name/area text to room polygons (new).
5. **Build the generic schedule-block parser**, validated against the elevator spec block as its first real test fixture (structurally different from a legend table — good coverage).
6. **Migrate the data model** — add `LAYER` and `SCHEDULE_BLOCK`, backfill existing access-control MVP output into the new schema so nothing already built is lost.
7. **Add the `UNMAPPED` confidence status** and wire the assembly engine to leave un-costed rows visible instead of dropping them.
8. **Extend the review UI** to filter/group by discipline and by layer-classification confidence — needed once there are 46 layers' worth of output instead of one.
9. **New Definition of Done for this stage:** every one of the 46 layers on the sample sheet is either (a) classified, extracted, and clustered, or (b) explicitly flagged `unclassified` for human labeling. Zero layers silently ignored. This replaces/extends the narrower one in Spec §11.
10. **Only then resume the serial roadmap** in Spec §12 — but reframed. Extraction is now discipline-agnostic after step 9, so "Phase 3 Mechanical," "Phase 4 Plumbing," etc. stop meaning "which domain do we look at next" and start meaning **"which domain gets assembly/costing rules next."** Geometry for a domain can sit in `Space`/`Component`/`Route` tagged `UNMAPPED` long before its rules are written — which is exactly the "maximum data retrieval" outcome you're asking for, decoupled from how fast rule-writing can keep up.
