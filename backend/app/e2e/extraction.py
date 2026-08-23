"""Frozen extraction interfaces for v3 conformance (spec v3 §8).

Pure dataclasses — no LLM/vision output here ever becomes a final quantity.
Every row traces to a deterministic calculation downstream.
"""

from __future__ import annotations

from dataclasses import dataclass, field

# Length-based assemblies: measured routes only (never point-based symbols).
ROUTE_ASSEMBLIES = {
    "cable_tray",
    "conduit",
    "duct_rectangular",
    "duct_round",
    "pipe_insulated",
}
# Mechanical route assemblies whose cross-section size drives the formulas.
SIZED_ASSEMBLIES = {"duct_rectangular", "duct_round", "pipe_insulated"}


@dataclass
class LayerRow:
    ocg_name: str
    classified_discipline: str  # electrical|mechanical|architectural|envelope|unclassified|...


@dataclass
class ScheduleBlockRow:
    block_type: str  # "legend" | "attribute_schedule"
    page_region: dict  # {x0,y0,x1,y1}
    entries: list[dict]  # [{"cells": [...]}, ...] rows of the block


@dataclass
class TextAnnotationRow:
    text: str
    bbox: tuple[float, float, float, float]
    ocg_layer: str | None = None
    component_index: int | None = None  # index into SheetExtraction.components
    route_index: int | None = None  # index into SheetExtraction.routes


@dataclass
class ComponentRow:
    component_type: str | None  # None ⇒ UNMAPPED
    layer_ocg: str
    x: float
    y: float
    confidence_status: str = "MEASURED"
    confidence_score: float = 1.0
    source_path_ids: list[str] = field(default_factory=list)


@dataclass
class RouteRow:
    route_type: str
    layer_ocg: str
    length_m: float
    confidence_status: str = "MEASURED"
    confidence_score: float = 1.0
    size_json: dict | None = None  # cascade provenance {width_mm..,source,ref}


@dataclass
class SheetExtraction:
    sheet_name: str | None = None
    page_number: int | None = None
    scale: str | None = None
    discipline: str | None = None
    source_quality: str = "layered_vector"
    rule_version: str = "v3c-1"
    layers: list[LayerRow] = field(default_factory=list)
    components: list[ComponentRow] = field(default_factory=list)
    routes: list[RouteRow] = field(default_factory=list)
    schedule_blocks: list[ScheduleBlockRow] = field(default_factory=list)
    text_annotations: list[TextAnnotationRow] = field(default_factory=list)
