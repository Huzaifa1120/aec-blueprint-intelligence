# Product

<!-- impeccable:product-schema 1 -->

## Platform

web

## Users

Primary user: the owner/estimator at a single AEC/contracting company — an internal, closed tool (explicit non-goal: general-purpose public "upload any blueprint" SaaS; that market is crowded and funded). They read construction drawings daily to produce bids and budgets, supply their own price catalogs and productivity rates, trust a number only when they can see where it came from on the sheet, and will reject any tool that quietly produces wrong quantities. Usage today spans all stages: owner-built under active development, piloted, and in real use on real sheets.

## Product Purpose

Ingests construction blueprints (CAD/BIM exports, vector PDFs, scanned/raster images) and produces structured, priced, traceable construction estimates: geometric quantities (counts, lengths, areas, volumes), raw-material estimates via deterministic engineering formulas, priced estimates (quantity × user-supplied catalog), and scope-of-work/workforce breakdowns. Success means: manually verified counts become regression tests; every output number traces to a highlighted region on the rendered sheet; time-to-estimate drops below the manual baseline; review overhead stays low enough to be the commercial case for the system.

## Positioning

Deterministic, human-verified takeoff in a market of black-box AI estimators: **AI proposes. Geometry calculates. Rules derive. Humans approve.** No LLM/vision model ever outputs a final quantity, length, area, or price — every BOQ number traces through `MEASUREMENT` audit records to sheet + region + method. Input honesty is part of the claim: degraded/flattened uploads are flagged by the Input Quality Gate (`degraded_vector`) and routed back for re-export rather than silently processed.

## Operating Context

- Single-sheet upload → Input Quality Gate → async processing pipeline (job queue, status polling) → human review UI → approved BOQ.
- Review happens on a large monitor next to a real drawing: drawing canvas beside the BOQ table, bidirectional click-to-highlight between row and source geometry.
- Hard product vocabulary: confidence statuses `MEASURED` / `DERIVED` / `ASSUMED` / `UNMAPPED`; source-quality tags `layered_vector` / `degraded_vector` / `raster` riding along as suffix badges.
- Estimator-owned data: assembly rules are YAML (`data/assemblies/`, mapped via `data/layer_mapping.yaml`); unit prices and productivity rates live in the catalog DB/YAML — never hardcoded in source.
- Real client sheets drive regression (5 PDFs, gitignored; see `data/samples/README.md`). Primary fixture: `MMC-JVC-CD-ELEC-3902_AC-WIRE-Model.pdf`.
- Discipline roadmap: v1 access control → full electrical (done through Phase 2.5) → Mechanical/HVAC next → plumbing/fire protection → architectural → structural → multi-sheet/whole-project.

## Capabilities and Constraints

- Backend: FastAPI (Python ≥ 3.11). Routes: `/`, `/health`, `POST /api/e2e/run`, `POST /api/catalog/import`, `GET /api/catalog/`.
- Frontend: Next.js App Router, React 19, Tailwind v4, TS strict (`@/*` → `./src/*`). Frontend calls backend at `NEXT_PUBLIC_API_URL` (default `http://127.0.0.1:8000`); dev servers run independently.
- Vector-first parsing. Raster path (superseded, re-proof pending spike): OpenCV legend matching + Detectron2 + rotation-aware OCR. Ultralytics YOLOv8 removed from default stack — AGPL-3.0 licensing constraint; no detector requiring an unbudgeted commercial license may enter.
- Heavy ML deps stay import-gated optionals, never `pyproject.toml` defaults.
- Corrections logged during review persist as rule-improvement signal; time-on-sheet is instrumented invisibly server-side (never show a visible timer).
- Deliberately undecided (do not invent answers): typical input mix (layer-rich vector vs degraded/flattened); availability of native DWG/DXF/IFC from the target company; whose price catalog seeds the Cost & Labor Catalog; final deployment topology (single-tenant internal recommended).

## Brand Commitments

- **Binding product name: Huzaifa AEC** (user-confirmed 2026-08-25). Legacy strings differ — docs historically said "AEC Blueprint Intelligence System"; future work uses Huzaifa AEC and reconciles legacy strings opportunistically when already touching them.
- **Binding visual system: `docs/DESIGN.md`** — the "Safety Authority" avant-garde technical-manual world (Ink Black/Paper/Safety Amber, Archivo Black + Inter + IBM Plex Mono, goggle-line dividers, hazard stripes). User-pinned 2026-08-25, replacing the prior "Technical Daylight" system; follow the doc as-is, never rewrite it. Implemented across the frontend 2026-08-25 (tokens.css is the single token source).
- Voice follows the product rules: precise, honest about uncertainty, numbers over adjectives, no hype.

## Evidence on Hand

- 5 real client PDFs present locally (gitignored; obtain from project owner on fresh clone) — includes a layer-rich electrical sheet (primary fixture), structural sheets with mechanical layers, an out-of-domain addendum, and a text-less raster highway-lighting plan.
- Approved PRD (`docs/PRD.md`); sole-source-of-truth spec v3 (`docs/AEC-Blueprint-System-Design-Spec-v3.md`); architecture/rules/phases/design docs; incumbent visual system recorded in `docs/DESIGN.md` (dark engineering theme).
- Green test suite (63 tests). No testimonials, case studies, press, pricing pages, or marketing assets exist — none may be fabricated.

## Product Principles

1. Traceability beats automation — any number that can't be clicked back to its geometry is a bug.
2. Honesty about input quality — flag degradation loudly; never guess through it.
3. Human approval is mandatory — the UI optimizes reviewer speed and confidence, not autopilot.
4. Rules are data — estimators own formulas, catalogs, and rates; code never embeds prices.
5. Per-item confidence, never blended — green/amber/red/tan statuses, no single percentage.

## Accessibility & Inclusion

Dense professional data work on large monitors: tabular numerals for aligned BOQ columns, high contrast, minimum 12px text (per incumbent DESIGN.md), keyboard-workable review flows expected. No formal accessibility standard has been committed yet.
