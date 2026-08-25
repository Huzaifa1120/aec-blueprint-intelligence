"""E2E pipeline endpoint — PDF upload → BOQ.

Exposes ``POST /api/e2e/run`` which runs the full vector pipeline:

1. ``classify_upload`` → decides vector/raster
2. ``parse_pdf`` → extract drawings, text spans, build OCG registry
3. ``resolve_scale`` → read scale from title block (or stamp assumed 1:100)
4. ``measure_routes`` → CONDUIT / CABLE_TRAY lengths at detected scale
5. ``count_components`` → discrete symbols (lighting, switches, trays, …);
   clusters on OCG layers that map to no assembly rule are surfaced as
   UNMAPPED entries (never priced) per spec v3 §7.9
6. ``apply_assembly`` → per‑component BOM & labor hours from YAML rules
7. ``compute_boq_item`` → catalog price lookup, ``unpriced`` flag, total cost

A full ``SheetExtraction`` bundle (classified layers, detected legend/schedule
blocks, text–layer annotations, routes/components incl. UNMAPPED) is built on
every run; when ``persist=true`` it is written through the persistence spine
and the response carries an ``estimate_id`` replayable via
``GET /api/estimates/{id}/replay``.

Returns BOQ items with ``confidence_status`` (DERIVED/ASSUMED at BOQ level —
rows stay MEASURED) and ``source_path_ids`` for frontend click‑through.

Trap compliance:
- No price is hardcoded in source. If the catalog has no price, the item is
  flagged ``unpriced`` (never $0 substitution) for human review.
- Layer→assembly resolution is YAML‑driven (``data/layer_mapping.yaml``).
- Unmapped measured elements are surfaced and persisted as UNMAPPED — never
  priced (spec v3 §7.9).
"""

from __future__ import annotations

import logging
import os
import tempfile
import uuid
from typing import Any, Dict, List, Optional, Tuple, TYPE_CHECKING

import pymupdf  # MUST import pymupdf, never fitz
from fastapi import APIRouter, File, UploadFile
from sqlalchemy.orm import Session as OrmSession

from app.core.config import get_settings
from app.db.session import get_engine
from app.e2e.extraction import (
    ROUTE_ASSEMBLIES,
    SIZED_ASSEMBLIES,
    ComponentRow,
    RouteRow,
    SheetExtraction,
)
from app.e2e.data_quality import DataQuality
from app.e2e.persistence import live_confidence_tier, persist_extraction
from app.ingestion.router import classify_upload
from app.ingestion.vector import SYMBOL_CUTOFF_FACTOR, _scale_denominator, parse_pdf
from app.parsing.scale import resolve_scale
from app.parsing.clustering import cluster_paths_threshold, derive_threshold_px
from app.parsing.layer_registry import classify_layers, discipline_of
from app.parsing.routes import measure_routes
from app.parsing.schedules import detect_blocks
from app.parsing.sizes import detect_schedule_rows, resolve_route_size
from app.parsing.components import count_components
from app.parsing.layer_map import layer_to_assembly, route_layers
from app.parsing.text_walker import associate_text, probe_span_ocgs
from app.assembly.formulas import FormulaValidationError
from app.assembly.rules import apply_assembly, load_assembly_rule
from app.catalog.prices import compute_boq_item

if TYPE_CHECKING:
    from app.core.config import Settings


logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/e2e", tags=["e2e"])


# ---------------------------------------------------------------------------
# Helper: compute BOQ line from a material + quantity
# ---------------------------------------------------------------------------
def _source_block(page: Any, bbox: Any) -> Optional[Dict[str, Any]]:
    """Normalized click-through region for one BOQ row (spec v3 §7.12).

    ``{"page": int, "bbox": [x0, y0, x1, y1]}`` in PDF points, or None when
    no usable region exists — persistence stores exactly this shape.
    """
    if not bbox:
        return None
    try:
        corners = [float(v) for v in bbox]
    except (TypeError, ValueError):
        return None
    if len(corners) < 4:
        return None
    return {"page": int(page or 0), "bbox": corners}


def _boq_line(
    assembly_type: str,
    material_name: str,
    quantity: float,
    measurement_status: str,
    source_path_ids: List[str],
    db: OrmSession,
    *,
    source_quality: str = "layered_vector",
    derivation: Any = None,
    size_source: Optional[str] = None,
    rule_version: Optional[str] = None,
    scale_assumed: bool = False,
    source: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Build one BOQ line with its live confidence tier (spec v3 §7.12).

    BOQ lines are never MEASURED — the row-level ``measurement_status``
    stays on the Measurement/RouteRow/ComponentRow; the priced line is
    DERIVED by default (calculated via assembly rule from measured input)
    and downgraded to ASSUMED when the size cascade assumed it or the sheet
    scale was assumed.
    """
    boq = compute_boq_item(quantity, material_name, db)

    # Shared with the persistence spine so a replayed estimate reads exactly
    # these tiers (T3-review ruling).
    tier, score = live_confidence_tier(
        size_source=size_source,
        scale_assumed=scale_assumed,
        source_quality=source_quality,
        rule_version=rule_version,
    )
    return {
        "assembly_type": assembly_type,
        "material_name": material_name,
        "quantity": round(quantity, 3),
        "unit_price": boq.get("unit_price"),
        "total_cost": boq.get("total_cost"),
        "unpriced": boq.get("unpriced", False),
        "confidence_status": tier,
        "confidence_score": score,
        "source_quality": source_quality,
        "source_path_ids": source_path_ids,
        "source": source,
        "derivation": derivation,
        "size_source": size_source,
    }


def _adapt_spans_for_cascade(raw_text_spans: List[Dict]) -> List[Dict]:
    """Map PyMuPDF span dicts ({text, bbox}) to the cascade's x0..y1 shape."""
    adapted: List[Dict] = []
    for span in raw_text_spans:
        bbox = span.get("bbox")
        if not bbox or len(bbox) < 4:
            continue
        adapted.append({
            "text": span.get("text", ""),
            "x0": float(bbox[0]),
            "y0": float(bbox[1]),
            "x1": float(bbox[2]),
            "y1": float(bbox[3]),
        })
    return adapted


def _build_sheet_extraction(
    sheet_name: str | None,
    scale: Any,
    scale_status: str | None,
    scale_str: str | None,
    source_quality: str,
    routes: List[Dict],
    route_sizes: List[Dict | None],
    components: List[Dict],
    ocg_registry: Dict[str, Dict],
    cascade_spans: List[Dict],
    raw_text_spans: List[Dict],
    pdf_path: str,
    data_quality: Dict[str, int] | None = None,
) -> SheetExtraction:
    """Build the full SheetExtraction bundle for one sheet.

    Pure projection: classified layers from the OCG registry (spec v3 §7.3),
    legend/schedule blocks from cascade spans (§7.6), text annotations joined
    to component centroids / route polylines (§7.5), and every counted
    symbol — mapped assemblies AND ``component_type=None`` UNMAPPED entries.
    Persistence re-derives the BOQ from the same deterministic YAML rules;
    nothing here invents a quantity.
    """
    layers = classify_layers(ocg_registry or {})
    schedule_blocks = detect_blocks(cascade_spans)
    component_centroids = [
        (float(comp.get("x", 0.0)), float(comp.get("y", 0.0))) for comp in components
    ]
    route_polylines = [
        [(float(x), float(y)) for x, y in (route.get("polyline") or [])]
        for route in routes
    ]
    annotations = associate_text(
        cascade_spans,
        component_centroids,
        route_polylines,
        ocg_by_span=_span_ocg_map(pdf_path, raw_text_spans),
    )

    return SheetExtraction(
        sheet_name=sheet_name,
        page_number=None,
        scale=str(scale) if scale else None,
        scale_status=scale_status,
        scale_str=scale_str,
        discipline=None,
        source_quality=source_quality,
        data_quality=data_quality,
        layers=layers,
        routes=[
            RouteRow(
                route_type=str(route.get("type") or ""),
                layer_ocg=route.get("layer", ""),
                length_m=float(route.get("length_m") or 0.0),
                confidence_status=route.get("confidence_status", "MEASURED"),
                confidence_score=float(route.get("confidence_score", 1.0)),
                size_json=route_sizes[index],
                page=int(route.get("page") or 0),
                bbox=(
                    _source_block(route.get("page"), route.get("bbox")) or {}
                ).get("bbox"),
            )
            for index, route in enumerate(routes)
        ],
        components=[
            ComponentRow(
                component_type=comp.get("assembly_type"),
                layer_ocg=comp.get("layer", ""),
                x=float(comp.get("x", 0.0)),
                y=float(comp.get("y", 0.0)),
                confidence_status=(
                    "UNMAPPED" if comp.get("assembly_type") is None else "MEASURED"
                ),
                confidence_score=float(comp.get("confidence_score", 1.0)),
                source_path_ids=list(comp.get("source_path_ids", [])),
                page=int(comp.get("page") or 0),
                bbox=(
                    _source_block(comp.get("page"), comp.get("bbox")) or {}
                ).get("bbox"),
            )
            for comp in components
        ],
        schedule_blocks=schedule_blocks,
        text_annotations=annotations,
    )


def _span_ocg_map(pdf_path: str, raw_text_spans: List[Dict]) -> dict[int, str]:
    """Span-index → OCG name aligned with extract_text_spans' flat order.

    ``probe_span_ocgs`` indexes spans per page; raw spans are flattened across
    pages in page order, so each page's probe result is shifted by the count
    of preceding pages' spans. Degrades to {} on any engine that does not
    expose per-span OCG membership.
    """
    try:
        doc = pymupdf.open(pdf_path)
    except Exception:
        return {}
    try:
        counts = [0] * max(doc.page_count, 0)
        for span in raw_text_spans:
            page_index = int(span.get("page_number", 1)) - 1
            if 0 <= page_index < len(counts):
                counts[page_index] += 1
        merged: dict[int, str] = {}
        offset = 0
        for page_index in range(doc.page_count):
            for span_index, name in probe_span_ocgs(doc[page_index]).items():
                merged[offset + span_index] = name
            offset += counts[page_index] if page_index < len(counts) else 0
        return merged
    except Exception:
        return {}
    finally:
        doc.close()


def _unmapped_layer_clusters(
    ocg_registry: Dict[str, Dict],
    raw_drawings: List[Dict],
    scale: Any,
) -> List[Dict]:
    """Cluster symbol-scale paths on OCG layers that map to no assembly rule.

    Uses the same fallback threshold parse_pdf clusters mapped layers with
    (no legend-derived mm threshold exists yet), so unmapped clustering stays
    consistent with the mapped pipeline (spec v3 §7.4/§7.9).
    """
    threshold_px = derive_threshold_px(None, _scale_denominator(str(scale or "")))
    max_symbol_diagonal_px = threshold_px * SYMBOL_CUTOFF_FACTOR
    clusters: List[Dict] = []
    for layer_name in ocg_registry or {}:
        if layer_to_assembly(layer_name) is not None:
            continue
        clusters.extend(
            cluster_paths_threshold(
                raw_drawings,
                layer_name,
                threshold_px=threshold_px,
                max_symbol_diagonal_px=max_symbol_diagonal_px,
            )
        )
    return clusters


def _aggregate_unmapped(components: List[Dict]) -> List[Dict]:
    """Aggregate unmapped component dicts by layer for the response payload."""
    aggregated: Dict[str, Dict[str, Any]] = {}
    order: List[str] = []
    for comp in components:
        layer = str(comp.get("layer") or "")
        if layer not in aggregated:
            aggregated[layer] = {
                "layer": layer,
                "count": 0,
                "source_path_ids": list(comp.get("source_path_ids", [])[:3]),
            }
            order.append(layer)
        aggregated[layer]["count"] += 1
    return [aggregated[layer] for layer in order]


def resolve_route_context(
    assembly_type: str,
    route: Dict,
    cascade_spans: List[Dict],
    scale: str,
    schedule_rows: List[Dict],
    components: List[Dict],
    all_routes: List[Dict],
    route_index: int,
    *,
    settings: "Settings",
    stats: Optional[Dict[str, int]] = None,
) -> Optional[Tuple[Dict, Optional[str], Optional[Dict]]]:
    """Cascade + fittings + FU for one sized route.

    Returns (variables, size_source, size) or None if the route must be
    dropped (fail-honest). `size` is the raw cascade dict including any
    fu_total/ref provenance keys. Sibling routes feed junction (tee)
    detection: a foreign vertex landing on this route's interior is a tee.
    """
    from app.parsing.fittings import derive_fittings
    from app.parsing.fixture_units import accumulate_fixture_units, resolve_size_from_fixture_units

    mech_rule = load_assembly_rule(assembly_type) or {}
    fu_size = None
    if assembly_type == "water_supply":
        polyline = [(float(x), float(y)) for x, y in route.get("polyline") or []]
        # Adapt extraction rows (assembly_type/x/y + positional key) at the
        # boundary — never mutate the extraction dicts themselves.
        fu_comps = [
            {
                "key": f"{idx}@{c.get('source_path_ids', [''])[0] or idx}",
                "component_type": c.get("assembly_type"),
                "x": float(c.get("x", 0.0)),
                "y": float(c.get("y", 0.0)),
            }
            for idx, c in enumerate(components)
            if c.get("assembly_type")
        ]
        fu_total, breakdown = accumulate_fixture_units(
            polyline, fu_comps, corridor_pt=settings.fu_corridor_pt, stats=stats
        )
        gauge = mech_rule.get("fixture_unit_gauge") or {}
        if fu_total > 0.0 and gauge:
            size = resolve_size_from_fixture_units(fu_total, gauge.get("rows") or {})
            if size:
                fu_size = {
                    **size,
                    "fu_total": fu_total,
                    "ref": [f"{b['component_type']}@{b['key']}" for b in breakdown],
                }

    size = resolve_route_size(
        route,
        cascade_spans,
        scale,
        schedule_rows=schedule_rows,
        default_size=mech_rule.get("defaults") or None,
        fixture_unit_size=fu_size,
    )
    if size is None:
        return None
    size_source = size.get("source")
    required_size_vars = set(mech_rule.get("variables") or []) - {
        "length_m", "max_mm", "elbows_90", "tees",
    }
    if any(var not in size for var in required_size_vars):
        size_source = "assumed"

    # Tee candidates must classify into the SAME discipline as the target
    # route (spec §4): an electrical tray crossing a water pipe is a visual
    # overlap, never a junction. Elbows derive from the route's own polyline
    # and are unaffected by the filter.
    target_discipline = discipline_of(str(route.get("layer") or ""))
    fittings = derive_fittings(
        route,
        [
            r
            for i, r in enumerate(all_routes)
            if i != route_index and discipline_of(str(r.get("layer") or "")) == target_discipline
        ],
        bend_angle_deg=settings.fitting_bend_angle_deg,
        min_segment_pt=settings.fitting_min_segment_pt,
        junction_tol_pt=settings.fitting_junction_tol_pt,
    )
    variables = {
        "length_m": route["length_m"],
        "elbows_90": float(fittings["elbows_90"]),
        "tees": float(fittings["tees"]),
        **{k: v for k, v in size.items() if k in ("width_mm", "height_mm", "diameter_mm")},
    }
    # Persisted-route parity: only stamp fitting counts onto the size dict
    # when the rule actually declares them (mechanical rules don't — their
    # size_json stays byte-compatible).
    if {"elbows_90", "tees"} <= set(mech_rule.get("variables") or []):
        size = {
            **size,
            "elbows_90": float(fittings["elbows_90"]),
            "tees": float(fittings["tees"]),
        }
    return variables, size_source, size


# ---------------------------------------------------------------------------
# Endpoint
# ---------------------------------------------------------------------------
@router.post(
    "/run",
    summary="Run the full E2E vector pipeline on an uploaded PDF",
)
def e2e_run(
    file: UploadFile = File(...,
        description="PDF file to process (vector preferred)."),
    persist: bool = False,
    project_id: uuid.UUID | None = None,
) -> Dict[str, Any]:
    """Run the complete PDF → BOQ pipeline and return BOQ items.

    When ``persist`` is true the extraction is written to the database
    (idempotently replacing any prior rows for the same sheet under the
    project) and the response gains an ``estimate_id``.
    """

    # Save the uploaded PDF to a temporary file so that the path‑based
    # helpers (classify_upload, parse_pdf) can receive a real file path.
    with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
        tmp.write(file.file.read())
        tmp_path = tmp.name

    try:
        dq = DataQuality()

        # 1️⃣ Classify
        try:
            classify_result = classify_upload(tmp_path)
        except Exception:
            dq.classifier_errors += 1
            logger.exception(
                "classify_upload failed; degrading upload to the raster path"
            )
            classify_result = {"status": "raster"}

        if classify_result.get("status") != "vector":
            # Raster path: no parsed text spans exist, so the run carries the
            # explicit assumed-scale stamp (spec v3 §7.4) like every vector run.
            assumed = resolve_scale([])
            return {
                "status": "raster",
                "detail": "PDF classified as raster; vector pipeline skipped.",
                "scale": {"value": assumed.scale_str, "status": assumed.status},
                "data_quality": dq.as_dict(),
            }

        source_quality = classify_result.get("source_quality", "layered_vector")

        # 2️⃣ Parse PDF
        parsed = parse_pdf(tmp_path)
        scale_res = resolve_scale(parsed.get("raw_text_spans", []))
        scale = scale_res.scale_str
        # Assumed-scale honesty: when no parseable scale token exists, every
        # length-driven BOQ line downgrades to ASSUMED (spec v3 §7.4/§7.12).
        scale_status = scale_res.status
        clusters = parsed.get("clusters", [])
        raw_drawings = parsed.get("raw_drawings", [])
        cascade_spans = _adapt_spans_for_cascade(parsed.get("raw_text_spans", []))
        schedule_rows = detect_schedule_rows(cascade_spans)

        # 3️⃣ Measure routes (length-based assemblies: tray, conduit, ducts, pipes)
        route_layer_names = tuple(route_layers())
        route_stats: Dict[str, int] = {}
        routes = measure_routes(
            clusters, raw_drawings, scale, route_layer_names, stats=route_stats
        )
        dq.degenerate_skipped += route_stats.get("degenerate_skipped", 0)
        # Resolved cross-section sizes aligned with `routes` by index —
        # reused when projecting a SheetExtraction for persistence.
        route_sizes: List[Dict | None] = [None] * len(routes)

        # 4️⃣ Count discrete components (symbol-based assemblies). Clusters on
        # OCG layers that map to no rule are surfaced as UNMAPPED entries —
        # reported and persisted, never priced (spec v3 §7.9).
        unmapped_clusters = _unmapped_layer_clusters(
            parsed.get("ocg_registry") or {}, raw_drawings, scale
        )
        all_components = count_components(
            clusters + unmapped_clusters, raw_drawings, include_unmapped=True
        )
        components = [c for c in all_components if c["assembly_type"] is not None]
        unmapped_components = [c for c in all_components if c["assembly_type"] is None]
        dq.unmapped_count += len(unmapped_components)
        # Extraction order: mapped first, then UNMAPPED appended — text
        # annotation component_index values refer into this combined list.
        extraction_components = components + unmapped_components

        # 5️⃣ Apply assembly rules & compute BOQ
        boq_items: List[Dict[str, Any]] = []
        with OrmSession(get_engine()) as db:
            # Route BOQ: quantity scales with measured length
            # Routes must ONLY evaluate against route-based assembly rules
            for route_index, route in enumerate(routes):
                layer = route.get("layer", "")
                resolved_assembly = layer_to_assembly(layer)
                # Use resolved layer assembly if available, fall back to route type
                assembly_type = resolved_assembly if resolved_assembly else route.get("type", "")
                if assembly_type not in ROUTE_ASSEMBLIES:
                    dq.dropped_routes += 1
                    continue

                variables = None
                size_source = None
                if assembly_type in SIZED_ASSEMBLIES:
                    fu_stats: Dict[str, int] = {}
                    ctx = resolve_route_context(
                        assembly_type, route, cascade_spans, scale,
                        schedule_rows, extraction_components, routes,
                        route_index, settings=get_settings(), stats=fu_stats,
                    )
                    dq.fu_corridor_excluded += fu_stats.get("fu_corridor_excluded", 0)
                    if ctx is None:
                        dq.dropped_routes += 1
                        logger.warning(
                            "dropping %s route (%.3f m): no resolvable "
                            "cross-section size and no configured default",
                            assembly_type, route["length_m"],
                        )
                        continue
                    variables, size_source, resolved_size = ctx
                    # Persist the EFFECTIVE tier exactly as before the
                    # refactor; FU provenance rides along inside size.
                    route_sizes[route_index] = {**resolved_size, "source": size_source}

                # Fail-closed like persistence: one broken rule drops that
                # route with a warning — it must never 500 the whole run
                # (fix-wave F6).
                try:
                    applied = apply_assembly(assembly_type, variables=variables)
                except FormulaValidationError as exc:
                    dq.dropped_routes += 1
                    logger.warning(
                        "dropping %s route (%.3f m): assembly rule failed (%s)",
                        assembly_type,
                        route["length_m"],
                        exc,
                    )
                    continue
                for mat in applied.get("materials", []):
                    quantity = mat["quantity"]
                    # Legacy electrical path (variables=None): constants are
                    # per-unit-length multipliers scaled here. Mechanical
                    # rules with bound variables already scale their constant
                    # lines by length_m inside rules.py — scaling again would
                    # square every fitting length (0.2 * L^2).
                    if variables is None and "formula" not in (
                        mat.get("derivation") or {}
                    ):
                        quantity *= route["length_m"]
                    boq_items.append(
                        _boq_line(
                            assembly_type,
                            mat["material_name"],
                            quantity,
                            route.get("confidence_status", "MEASURED"),
                            route.get("source_path_ids", []),
                            db,
                            source_quality=source_quality,
                            derivation=mat.get("derivation"),
                            size_source=size_source,
                            rule_version=applied.get("rule_version"),
                            scale_assumed=(scale_status == "assumed"),
                            source=_source_block(
                                route.get("page"), route.get("bbox")
                            ),
                        )
                    )

            # Component BOQ: one assembly instance per counted symbol
            # Enforce strict 1-to-1 layer-to-assembly matching (Phase 2 rule).
            for comp in components:
                resolved_type = comp.get("assembly_type")

                # Sized route assemblies are quantified by the ROUTE loop
                # (formula needs per-route size variables); a duct/pipe
                # cluster surfacing here is geometry, not a countable symbol.
                if resolved_type in SIZED_ASSEMBLIES:
                    dq.dropped_symbols += 1
                    continue

                rule = load_assembly_rule(resolved_type)
                if rule is None or resolved_type != rule.get("name", resolved_type):
                    # STRICT SKIP: never apply an unrelated rule to a component
                    dq.dropped_symbols += 1
                    continue

                # Fail-closed like persistence: one broken rule drops that
                # symbol type with a warning — never a 500 (fix-wave F6).
                try:
                    applied = apply_assembly(resolved_type)
                except FormulaValidationError as exc:
                    dq.dropped_symbols += 1
                    logger.warning(
                        "dropping %s symbols (count path): assembly rule "
                        "failed (%s)",
                        resolved_type,
                        exc,
                    )
                    continue
                for mat in applied.get("materials", []):
                    quantity = mat["quantity"] * comp["count"]
                    boq_items.append(
                        _boq_line(
                            resolved_type,
                            mat["material_name"],
                            quantity,
                            comp.get("confidence_status", "MEASURED"),
                            comp.get("source_path_ids", []),
                            db,
                            source_quality=source_quality,
                            derivation=mat.get("derivation"),
                            size_source=None,
                            rule_version=rule.get("rule_version"),
                            source=_source_block(
                                comp.get("page"), comp.get("bbox")
                            ),
                        )
                    )

        # Full SheetExtraction bundle — built AFTER the BOQ loop so
        # route_sizes carries every cascade-resolved cross-section: the
        # persisted rows must reflect exactly the provenance that drove the
        # response math, never re-derived defaults (F1).
        filename = file.filename or ""
        sheet_name = os.path.splitext(filename)[0] or None
        extraction = _build_sheet_extraction(
            sheet_name=sheet_name,
            scale=scale,
            scale_status=scale_res.status,
            scale_str=scale_res.scale_str,
            source_quality=source_quality,
            routes=routes,
            route_sizes=route_sizes,
            components=extraction_components,
            ocg_registry=parsed.get("ocg_registry") or {},
            cascade_spans=cascade_spans,
            raw_text_spans=parsed.get("raw_text_spans", []),
            pdf_path=tmp_path,
            data_quality=dq.as_dict(),
        )

        # Optional persistence (default-off): write the full extraction
        # bundle through the persistence spine in its own committing session.
        estimate_id: uuid.UUID | None = None
        if persist:
            with OrmSession(get_engine()) as persist_db:
                estimate_id = persist_extraction(persist_db, project_id, extraction)

        response: Dict[str, Any] = {
            "status": "ok",
            "scale": {"value": scale_res.scale_str, "status": scale_res.status},
            "routes_measured": len(routes),
            "components_found": len(components),
            "boq_items": boq_items,
            "layers_count": len(extraction.layers),
            "schedule_blocks_count": len(extraction.schedule_blocks),
            "text_annotations_count": len(extraction.text_annotations),
            "unmapped_items": _aggregate_unmapped(unmapped_components),
            "data_quality": dq.as_dict(),
        }
        if persist and estimate_id is not None:
            response["estimate_id"] = str(estimate_id)
        return response

    finally:
        # Clean up the temporary PDF file – runs even if we returned early.
        try:
            os.unlink(tmp_path)
        except OSError:
            pass