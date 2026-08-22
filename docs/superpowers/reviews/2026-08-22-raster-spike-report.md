# Phase 2.5 — Raster Spike Report

Gate: per-type ±10%
Templates extracted: 72 (unmapped: 71)
Verdict: CONVERTED FINDING: per-type gate unmet while truth-ceiling 0.903 >= 0.75 — detection succeeds at true locations but the matcher cannot discriminate (overcount) and label coverage is incomplete; human review required

Columns: page-best = peak correlation outside legend across all swept
configs; truth-ceiling = peak correlation near vector-truth locations
(diagnostic only — never used for counts).

| symbol type | vector truth | template match | deviation | status | page-best | truth-ceiling |
|---|---|---|---|---|---|---|
| access_control_door | 2 | 727 | 36250% | FAIL | 0.914 | 0.903 |
| cable_tray | 1 | — | — | UNMAPPED | 0.000 | n/a |
| lighting_outlet | 26 | — | — | UNMAPPED | 0.000 | n/a |

## Transfer-ceiling evidence
- Best-at-truth-location correlation: access_control_door:0.903.
- Swept scales: 0.4, 0.55, 0.7, 0.85, 1, 1.15, 1.35, 1.6, 1.9, 2.25; rotations: 0°, 90°, 180°, 270°.
- Root causes documented in tests/test_spike_raster_reproof.py module docstring (rotation-coordinate mismatch, outlined legend text, legend-cell ground-truth quirk, simplified plan depictions).
