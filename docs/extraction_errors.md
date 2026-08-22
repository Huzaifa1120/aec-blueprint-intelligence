# PDF Extraction Error Report

**Source:** Raw BOQ data extracted from PDF fixture `MMC-JVC-CD-ELEC-3902_AC-WIRE-Model.pdf`

**Date:** 2026-08-22

## Summary

The PDF extraction produced BOQ data with significant issues requiring normalization, deduplication, and pricing addition before the data can be used for quantity takeoff/cost estimating.

## Critical Issues

### 1. Excessive Duplicate Entries

**Lighting Outlet Items:**
- `lighting_unit`, `lampholder`, and `wiring` assemblies appear with **identical** `source_path_ids` arrays (50+ IDs each)
- Multiple duplicate entries for the same assembly type with no differentiating attributes
- Example: `lighting_unit` appears ~25+ times with `source_path_ids`: `["11f98091-3371-4c31-a87e-6bcfe217d304", "71d5abf1-f8e6-4302-9472-3841ee0d0eed", ...]`

**Impact:** Data inflation and inability to distinguish individual fixtures/fittings

### 2. Inconsistent Quantity Values

**Cable Tray Items:**
- `cable_tray_section`: quantity = 1888.407 (first entry) vs. 1 (subsequent entries)
- `tray_fitting`: quantity = 377.681 (first entry) vs. 0.2 (subsequent entries)
- `support_hanger`: quantity = 188.841 (first entry) vs. 0.1 (subsequent entries)

**Impact:** Quantities not normalized during extraction; need source-based normalization

### 3. All Items Unpriced

- Every BOQ item has: `unit_price: null`, `total_cost: 0`, `unpriced: true`
- No unit prices or total costs extracted from PDF
- Per project rules: "Unit prices / productivity rates live in catalog DB or YAML — never hardcode them in source"

**Impact:** BOQ cannot generate financial totals; pricing must be added from catalog source

### 4. Abnormally Long source_path_ids Arrays

- Most `source_path_ids` arrays contain **50+ UUIDs**
- Example lighting_outlet wiring entry has 55 source path IDs
- Suggests PDF text extraction artifacts or merged text blocks

**Impact:** Unreliable source tracking; likely includes non-essential IDs from PDF structure

### 5. Duplicate cable_tray Entries

- Same assembly types (`cable_tray_section`, `tray_fitting`, `support_hanger`) appear multiple times
- First batch: 4 entries with combined source_path_ids
- Second batch: 3 entries with individual source_path_ids
- Quantities differ between batches (1888.407 vs. 1; 377.681 vs. 0.2)

**Impact:** Data redundancy; need deduplication logic

## Recommended Fixes

1. **Deduplicate entries** - Remove duplicate lighting_outlet items; keep one representative per unique source_path_ids subset

2. **Normalize quantities** - Use source path geometry to determine correct quantities rather than raw extracted values

3. **Add pricing data** - Pull unit prices from catalog DB/YAML; compute total_cost = quantity × unit_price

4. **Trim source_path_ids** - Keep only essential path IDs; remove PDF-internal UUIDs

5. **Classify confidence status** - Items marked `MEASURED` need verification; add `PRELIMINARY` or `ESTIMATED` where appropriate

6. **Implement human verification step** - Per rule: "Humans approve" all BOQ numbers

## Data Sample Issues

```
[ERROR] lighting_outlet × 25+ entries with identical source_path_ids
[ERROR] cable_tray_section quantity: 1888.407 vs 1 (inconsistent)
[ERROR] All items unpriced: unit_price=null, total_cost=0
[ERROR] source_path_ids arrays: 50+ UUIDs per entry (extraction artifact)
[ERROR] cable_tray duplicates: same assembly type, different quantity values
```

## Next Steps

1. Deduplicate and normalize the BOQ data
2. Integrate catalog pricing from YAML/DB
3. Implement human verification step per architecture rules
4. Regenerate BOQ with proper quantities and costs