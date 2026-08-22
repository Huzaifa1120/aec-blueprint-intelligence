"""Input Quality Gate — spec v3 §7.2.

Sits between the ingestion router and everything else: a vector-looking PDF
must prove it carries layer data before being parsed as layered vector.
Fail-closed: any scoring error ⇒ degraded_vector, never silent happy-path.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path

import pymupdf  # never fitz

from app.core.config import get_settings

VERDICT_LAYERED = "layered_vector"
VERDICT_DEGRADED = "degraded_vector"
VERDICT_RASTER = "raster"

LOOP_BACK_MESSAGE = (
    "This file has no usable layer data. Re-export with layers included, "
    "or provide the native DWG/DXF."
)


@dataclass(frozen=True)
class LayerRichnessMetrics:
    distinct_ocg_count: int
    tagged_paths: int
    total_paths: int
    tagged_path_fraction: float
    has_extractable_text: bool


def score_layer_richness(doc: pymupdf.Document, page: pymupdf.Page) -> LayerRichnessMetrics:
    ocg_count = len([v for v in doc.get_ocgs().values() if v.get("name")])
    drawings = page.get_drawings()
    total = len(drawings)
    tagged = sum(1 for d in drawings if d.get("layer"))
    fraction = tagged / total if total else 0.0
    has_text = page.get_text("text").strip() != ""
    return LayerRichnessMetrics(
        distinct_ocg_count=ocg_count,
        tagged_paths=tagged,
        total_paths=total,
        tagged_path_fraction=fraction,
        has_extractable_text=has_text,
    )


def _is_raster_like(metrics: LayerRichnessMetrics, drawing_count: int, image_count: int) -> bool:
    return drawing_count < 100 and image_count > 0 and not metrics.has_extractable_text


def assess_quality(file_path: str) -> dict:
    settings = get_settings()
    try:
        doc = pymupdf.open(Path(file_path))
        try:
            page = doc[0]
            metrics = score_layer_richness(doc, page)
            images = page.get_images(full=True)
            if _is_raster_like(metrics, metrics.total_paths, len(images)):
                verdict = VERDICT_RASTER
            elif metrics.distinct_ocg_count < settings.degraded_min_ocgs or (
                metrics.total_paths > 0
                and (1.0 - metrics.tagged_path_fraction) > settings.degraded_max_untagged_fraction
            ):
                verdict = VERDICT_DEGRADED
            else:
                verdict = VERDICT_LAYERED
            return {
                "verdict": verdict,
                "metrics": asdict(metrics),
                "image_count": len(images),
                "loop_back_message": LOOP_BACK_MESSAGE if verdict == VERDICT_DEGRADED else None,
            }
        finally:
            doc.close()
    except Exception:
        return {
            "verdict": VERDICT_DEGRADED,
            "metrics": None,
            "image_count": 0,
            "loop_back_message": LOOP_BACK_MESSAGE,
        }
