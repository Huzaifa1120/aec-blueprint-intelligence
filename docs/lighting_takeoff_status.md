# Lighting Takeoff Status — Al Murjan Hospital (Electrical/Lighting)

**Project:** Al Murjan Hospital — Lighting Layout Takeoff  
**Discipline:** Electrical / Lighting  
**Drawings:** 3 sheets — Part-1, Part-2, Part-3 (2nd Floor)  
**Date:** 2026-09-01  
**Phase:** Step 2 (Subagent Planning) — **FULLY APPROVED** | Next: V1 + V2 Execution

---

## Completed Milestones

### Phase 1-3: Platform Foundation ✅
- **Backend:** FastAPI (Python ≥3.11) on Supabase PostgreSQL
- **Frontend:** Next.js 16 App Router, React 19, Tailwind v4, TypeScript strict
- **Input Quality Gates:** Vector/raster detection, `degraded_vector` flagging
- **Catalog System:** YAML assembly rules + layer mapping (`data/assemblies/`, `data/layer_mapping.yaml`)
- **Test Suite:** 63 tests passing (pytest + ruff)

### Phase 4: DALI Loop Text Extraction ✅
- **File:** `backend/app/services/lighting/text_clustering.py`
- **Method:** Line-clustering (±4pt Y-tolerance) → panel+loop pairing → deduplication by (panel, part, loop, cluster)
- **Part-1:** 10 unique loops, **293 fixtures** (duplicate LOOP-12 merged: 26+28 → 28)
- **Part-2:** 5 loops, **174 fixtures** (LCP-L2/02)
- **Part-3:** 4 loops, **116 fixtures** (LCP-L2/03)
- **Total:** 19 loops, **583 fixtures** ground-truth quantities

### Phase 5: Emergency Marker Spatial Mapping ✅
- **File:** `backend/app/services/lighting/spatial_association.py`
- **Method:** Marker-centric (CB/EM/EMEM text → nearest symbol within 30pt adaptive radius)
- **Part-1:** 317 markers → 317 fixtures (96.8% with graphical symbol, median dist 7.4pt)
- **Emergency Split (Part-1):** CB=146 (49.8%), EM=143 (48.8%), EMEM=4 (1.4%), NORMAL=0
- **Per-loop ratios** applied via largest-remainder to preserve totals

### Phase 6: Reconciliation & Debug Artifacts ✅
- **File:** `backend/app/services/lighting/reconciliation.py`
- **Outputs per part:**
  - `data/debug/Part-{1,2,3}_loops.json` — extracted DALI quantities
  - `data/debug/Part-{1,2,3}_report.json` — per-loop breakdown + flags
  - `data/debug/Part-{1,2,3}_overlay.pdf` — visual debug (symbols color-coded, markers, legend)

---

## Current Status: Step 2 (Subagent Planning) — FULLY APPROVED

### Layer Audit Results (Part-1) — Locked In

| Layer | Total Drawings | Candidates (30–500 pt², black, thin, Y>600) | Shapes |
|-------|----------------|---------------------------------------------|--------|
| **DALI CONTROL** | 2,562 (1,991 in plan) | **682** | 344 hex, 336 circle, 2 nonagon |
| E-LITE | 1,817 | **0** | hexagons at 0.0–0.5 pt² (construction geometry) |
| E-LITE-EQPM | 339 | **0** | nonagons at 124–227 pt² (non-fixture) |
| G-IMPT | 24,573 | 8 | hexagon |
| Others | — | minimal | — |

### Key Findings — Validated

**Finding 1:** E-LITE layer contains ZERO valid fixture vectors — all physical fixture symbols are on the **DALI CONTROL** layer.

**Finding 2:** Vector noise eliminated by Layer Isolation (`DALI CONTROL`) + Strict Area Boundaries:
- **Circles (downlights):** 45–55 pt² → 336 fixtures
- **Hexagons (panels):** 80–150 pt² → 344 fixtures  
- **Nonagons (strips):** 80–150 pt² → 2 fixtures

**Finding 3:** Overcount source = wiring + control devices on DALI CONTROL layer.

### Architectural Decisions — Locked In

1. **Room-Based Semantic Inference Engine** — Abandoned pure shape-matching; room codes (WC, E/S, CH., etc.) are primary signal
2. **V1 Layer Denoiser** — Hardcoded `DALI CONTROL` layer + area windows (45–55, 80–150)
3. **V2 Room Polygon Builder** — Room codes → spatial polygons (Voronoi/convex hull)
4. **V4 Tie-Breaker Logic** — Priority: emergency marker → room IP match → shape preference → distance to loop label
5. **V6 Review Artifact** — PDF overlay showing 682 candidates: 293 kept (colored by emergency class), 389 discarded (gray X)

### V1–V6 Subagent Plan — Approved

| Subagent | File Target | Key Interface |
|----------|-------------|---------------|
| **V1: Layer Denoiser** | `backend/app/services/lighting/denoiser.py` | `extract_denoised_symbols(page) → List[DenoisedSymbol]` |
| **V2: Room Polygon Builder** | `backend/app/services/lighting/room_mapper.py` | `build_room_polygons(page) → List[RoomPolygon]` |
| **V3: Legend Parser** | `backend/app/services/lighting/legend_parser.py` | `parse_legend(page) → List[FixtureSpec]` (25 specs) |
| **V4: Loop Zone Quantifier** | `backend/app/services/lighting/loop_quantifier.py` | `build_loop_zones(loops, symbols, rooms) → Dict[LoopZone]` + tie-break |
| **V5: Semantic Allocator** | `backend/app/services/lighting/semantic_allocator.py` | `allocate(symbols, rooms, specs, markers, zones) → List[FixtureAssignment]` |
| **V6: Review Artifact** | `backend/app/services/lighting/review_artifact.py` | `generate_review_overlay(...) → bytes (PDF) + dict (summary)` |

---

## Next Action Queued

| Priority | Subagent | Description |
|----------|----------|-------------|
| **1** | **V1: Layer Denoiser** | Implement `DALI CONTROL` filter + area windows (circles 45–55 pt², hex/nonagon 80–150 pt²). Target: 682 denoised symbols on Part-1. |
| **2** | **V2: Room Polygon Builder** | Cluster room codes (WC, E/S, CH., GR, DN, UP, 1R–29B) into spatial polygons. Output: ~15 RoomPolygons with semantic rules attached. |

**NOTE:** User stepping away. **Do not execute V1 or V2 code until explicit resume command.**

---

## Action Items (Updated)

1. [ ] **V1: Layer Denoiser** — Implement `DALI CONTROL` filter + area windows (circles 45–55, hex/nonagon 80–150)
2. [ ] **V2: Room Polygon Builder** — Cluster room codes into spatial polygons (Voronoi/convex hull)
3. [ ] **V3: Legend Parser** — Extract 25 specs with IP, shape_hint, wattage, dimensions, emergency flags
4. [ ] **V4: Loop Zone Quantifier** — Spatial loop zones → distribute 293 qty
5. [ ] **V5: Semantic Allocator** — Room→Spec mapping with confidence scoring
6. [ ] **V6: Review Artifact** — Annotated PDF + JSON for human approval
7. [ ] Execute full pipeline → BOQ export

---

## Files Reference

| File | Purpose |
|------|---------|
| `backend/app/services/lighting/text_clustering.py` | DALI loop extraction |
| `backend/app/services/lighting/spatial_association.py` | Marker→symbol mapping |
| `backend/app/services/lighting/reconciliation.py` | Full pipeline + debug overlay |
| `backend/app/services/lighting/types.py` | Shared type definitions |
| `data/debug/Part-1_loops.json` | Part-1 loop quantities |
| `data/debug/Part-1_report.json` | Part-1 reconciliation |
| `data/debug/Part-1_overlay.pdf` | Part-1 visual debug |
| `data/debug/Part-2_*.json/pdf` | Part-2 outputs |
| `data/debug/Part-3_*.json/pdf` | Part-3 outputs |