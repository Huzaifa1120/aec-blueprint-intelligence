# Lighting Takeoff Status — Al Murjan Hospital (Electrical/Lighting)

**Project:** Al Murjan Hospital — Lighting Layout Takeoff  
**Discipline:** Electrical / Lighting  
**Drawings:** 3 sheets — Part-1, Part-2, Part-3 (2nd Floor)  
**Date:** 2026-09-04  
**Phase:** V1-V6 Subagent Pipeline — Re-verification In Progress | Next: V1/V2/V3 Re-audit  

---

## Completed Milestones

### Phase 1-3: Platform Foundation ✅
- **Backend:** FastAPI (Python ≥3.11) on Supabase PostgreSQL
- **Frontend:** Next.js 16 App Router, React 19, Tailwind v4, TypeScript strict
- **Input Quality Gates:** Vector/raster detection, `degraded_vector` flagging
- **Catalog System:** YAML assembly rules + layer mapping (`data/assemblies/`, `data/layer_mapping.yaml`)
- **Test Suite:** 63 tests passing (pytest + ruff)

### Phase 4: DALI Loop Text Extraction — RE-VERIFIED
- **File:** `backend/app/services/lighting/text_clustering.py`
- **Method:** Full-page TEXTFLAGS_RAW extraction → line-clustering (±4pt Y-tolerance, 100pt X-gap) → panel+loop pairing → spatial deduplication by (centroid_x, centroid_y) with composite keys (loop_id, cluster_id)
- **Part-1:** 15 spatially distinct loop zones, **442 fixtures** (two genuinely separate LOOP-12 zones: 28 + 26 = 54, a real drawing labeling discrepancy flagged for design-team review). Regression test: `tests/test_loop_quantifier.py::test_build_loop_zones_preserves_spatially_distinct_loop_ids`
- **Part-2:** 6 zones, **202 fixtures** (LCP-L2/02, PART-2) — no discrepancies
- **Part-3:** 4 zones, **116 fixtures** (LCP-L2/03, PART-3) — no discrepancies
- **Total:** 25 zones, **760 fixtures** ground-truth quantities

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

## V1-V6 Subagent Pipeline — Status After Re-verification

| Subagent | File | Status | Key Metrics (Part-1) |
|----------|------|--------|---------------------|
| **V1: Layer Denoiser** | `backend/app/services/lighting/denoiser.py` | ✅ Code Done | 673 symbols on `DALI CONTROL` layer (336 hex, 336 circle, 1 nonagon) — **NOT independently audited** |
| **V2: Room Polygon Builder** | `backend/app/services/lighting/room_mapper.py` | ✅ Code Done | 181 RoomPolygons; false codes blacklisted; semantic rules attached — **NOT independently audited** |
| **V3: Legend Parser** | `backend/app/services/lighting/legend_parser.py` | ✅ Code Done | Region Y≈3000; 33 FixtureSpecs with IP, wattage, shape, DITTO — **NOT independently audited** |
| **V4: Loop Zone Quantifier** | `backend/app/services/lighting/loop_quantifier.py` | ✅ Fixed + Verified | **15 zones, 442 capacity, 442 assigned (100%)** — composite key fix prevents LOOP-12 collision; 800pt radius |
| **V5: Semantic Allocator** | `backend/app/services/lighting/semantic_allocator.py` | ⚠️ Re-run Needed | 442 assigned; 0 IP violations; 442 low-confidence (<0.75) — **re-run needed on corrected 442-fixture set** |
| **V6: Review Artifact** | `backend/app/services/lighting/review_generator.py` | ⚠️ Stale | Generated from pre-fix data; **must regenerate after V1-V5 re-verification** |

---

## Known Root-Cause Bugs Fixed

1. **Phase 4 dict-key collision** — `build_loop_zones` previously keyed `LoopZone` by `loop_id` string alone, silently overwriting one zone when two spatially distinct zones shared a duplicate label (LOOP-12 on Part-1). Fixed via composite `(loop_id, cluster_id)` key in `loop_quantifier.py:build_loop_zones`. Regression test: `tests/test_loop_quantifier.py::test_build_loop_zones_preserves_spatially_distinct_loop_ids`.

2. **OCR extraction gap** — default `get_text("dict")` missed 4 loop labels (01, 02, 05, 06 on Part-1) because they resided on hidden OCG layers / non-standard render modes in the AutoCAD-generated PDF. Fixed by switching to `page.get_text("dict", flags=fitz.TEXTFLAGS_RAW)` (flags=4) for full-page extraction including hidden layers.

3. **Lighting unit / lampholder cross-contamination** — on the separate AC-WIRE sheet (`MMC-JVC-CD-ELEC-3902_AC-WIRE-Model.pdf`), wire symbols on the same layer were being picked up as lighting fixtures. Fixed by stricter area-window filters and layer-specific isolation in `denoiser.py`.

---

## Outstanding Verification Gaps

| Component | Status | Gap Description |
|-----------|--------|-----------------|
| **V1: Layer Denoiser** | ❌ Unverified | 673-symbol candidate count for Part-1 not independently audited; area windows / path signatures not cross-checked against ground truth |
| **V2: Room Polygon Builder** | ❌ Unverified | 181 RoomPolygons not independently audited; room code → polygon mapping not validated against visual drawing |
| **V3: Legend Parser** | ❌ Unverified | 33 FixtureSpecs not independently verified against legend text; DITTO-inheritance chains (25%, 50% conversion) not independently verified |
| **V4: Symbol→Zone Assignment** | ⚠️ Partially Fixed | Coordinate-convention mismatch confirmed: loop zones use **text-cluster centroid**; symbols use **path-geometry bounding-box centroid**. Current status: **unresolved** — causes coordinate drift in distance scoring. Must align conventions or compensate. |
| **V5: Semantic Allocator** | ❌ Stale | Still reflects OLD 293-fixture dataset; **re-run required** against corrected 442-fixture set. Specific attention to 168 newly-recovered fixtures (LOOP-04, 09, 12-A, 12-B, 13, 15 = 168 fixtures). |
| **V6: Review Artifact** | ❌ Stale | Generated from pre-fix 293-fixture data; must regenerate after V1-V5 re-verification. |
| **Non-DALI Circuits** | ❌ Scope Gap | Type-A/B/C/D homerun schedules visible on every sheet — **not captured in BOQ pipeline at all**. No parser for circuit schedules; flagged as scope gap. |

---

## Next Action Queued

| Priority | Task | Description |
|----------|------|-------------|
| **1** | **V1/V2/V3 Re-audit** | Independent audit of V1 (673 symbols), V2 (181 rooms), V3 (33 specs) against ground truth |
| **2** | **V4 Coordinate Convention Fix** | Align loop-zone centroid (text-cluster) with symbol centroid (path-geometry) conventions, or add offset compensation in distance scoring |
| **3** | **V5 Re-run on 442-Fixture Set** | Re-run semantic allocator on corrected 442-fixture set; specifically validate 168 newly-recovered fixtures (LOOP-04, 09, 12-A, 12-B, 13, 15) |
| **4** | **V6 Regeneration** | Regenerate `Part-1_review_overlay.pdf` and `Part-1_review_summary.json` from re-verified pipeline |
| **5** | **Non-DALI Circuit Parser** | Scope decision: implement circuit-schedule parser or formally exclude from BOQ scope |
| **6** | **T9: Full Verification Gate** | **BLOCKED** — do not run full verification gate until Outstanding Verification Gaps section is empty |

---

## Action Items (Updated)

1. [x] **V1: Layer Denoiser** — `DALI CONTROL` filter + area windows (code done, **audit pending**)
2. [x] **V2: Room Polygon Builder** — Room code clustering → spatial polygons (code done, **audit pending**)
3. [x] **V3: Legend Parser** — 33 specs with IP, shape_hint, wattage, DITTO handling (region Y≈3000) (code done, **audit pending**)
4. [x] **V4: Loop Zone Quantifier** — Tie-breaker: emergency→IP→shape→distance, composite key fix, 100% utilization on 442 fixtures
5. [ ] **V5: Semantic Allocator** — Re-run on 442-fixture set; validate 168 recovered fixtures
6. [ ] **V6: Review Artifact** — Regenerate after V5 re-run
7. [ ] **T6: Migrate 7 E2E tests** to async poll pattern (`_e2e_async.post_and_wait`)
8. [ ] **T9: Full verification gate** + live smoke test + `docs/Memory.md` update — **BLOCKED**
9. [ ] Execute full pipeline → BOQ export for all 3 parts

---

## Files Reference

| File | Purpose |
|------|---------|
| `backend/app/services/lighting/denoiser.py` | V1: Layer denoising + symbol extraction |
| `backend/app/services/lighting/room_mapper.py` | V2: Room polygon building + semantic rules |
| `backend/app/services/lighting/legend_parser.py` | V3: Legend parsing (Y≈3000 region) |
| `backend/app/services/lighting/loop_quantifier.py` | V4: Loop zones + tie-breaker assignment (composite key fix) |
| `backend/app/services/lighting/semantic_allocator.py` | V5: Room-rule compliant spec allocation |
| `backend/app/services/lighting/review_generator.py` | V6: PDF overlay + JSON summary generation |
| `backend/app/services/lighting/text_clustering.py` | DALI loop text extraction (TEXTFLAGS_RAW, spatial dedup) |
| `backend/app/services/lighting/spatial_association.py` | Marker→symbol enrichment + room assignment |
| `backend/app/services/lighting/reconciliation.py` | Legacy full pipeline + debug artifacts |
| `backend/app/services/lighting/types.py` | Shared type definitions |
| `data/debug/Part-1_loops.json` | Part-1 DALI loop quantities (15 zones, 442 total) |
| `data/debug/Part-1_review_summary.json` | Part-1 V6 JSON summary (stale — pre-fix) |
| `data/debug/Part-1_review_overlay.pdf` | Part-1 V6 PDF overlay (stale — pre-fix) |
| `data/debug/Part-2_loops.json` | Part-2 DALI loop quantities (6 zones, 202 total) |
| `data/debug/Part-3_loops.json` | Part-3 DALI loop quantities (4 zones, 116 total) |
| `tests/test_loop_quantifier.py` | Regression test: `test_build_loop_zones_preserves_spatially_distinct_loop_ids` |