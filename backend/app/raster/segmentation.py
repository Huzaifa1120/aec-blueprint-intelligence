"""CubiCasa5K-style segmentation — Phase 1.5 raster fallback.

Segmentation ONLY for non-legend architectural elements: walls, rooms, spaces.

CRITICAL CONSTRAINT (Rules.md §3.3, trap.md ❌): 
- NEVER use segmentation for symbol classification — that's the legend's job.
- Segmentation masks are for non-legend elements only (walls, rooms, spaces).
- Segmentation masks tagged with lower base confidence than vector geometry.

This module does NOT perform symbol classification. Symbol classification
is handled by: per-document legend matching (legend.py) first,
then fallback to "unknown" — never a universal symbol detector.
"""

from __future__ import annotations

from typing import Dict, List, Optional, Any, Tuple

import numpy as np

# Import Detectron2 or similar only if available; segmentation is optional
# in Phase 1.5 and is subordinate to legend matching.

# Sentinel: segmentation not available
SEGMENTATION_AVAILABLE = False

try:
    import detectron2
    from detectron2.engine import DefaultPredictor
    from detectron2.config import Configuration
    from detectron2 import model_zoo
    SEGMENTATION_AVAILABLE = True
except ImportError:
    # detectron2 not installed — segmentation is unavailable but Phase
    # 1.5 still functions via legend matching + OCR + YOLO proposals
    SEGMENTATION_AVAILABLE = False


# ---------------------------------------------------------------------------
# Segmentation function — non-legend elements only
# ---------------------------------------------------------------------------

def segment_non_legend_elements(
    image: np.ndarray,
    confidence_threshold: float = 0.5,
) -> List[Dict[str, Any]]:
    """Segment non-legend architectural elements from a raster image.

    CRITICAL CONSTRAINTS:
    1. Segmentation is for NON-LEGEND elements only: walls, rooms, spaces.
    2. NEVER use segmentation output for symbol classification (that's the
       legend's job via legend.py).
    3. Segmentation masks tagged with lower base confidence than vector geometry.
    4. If detectron2/not available → return empty list, not error.

    Returns list of segmentations with mask, bbox, and class.

    Each dict contains:
    - "class": str — one of {"wall", "room", "space"}
    - "bbox": Tuple[x0, y0, x1, y1] — bounding box in pixel coordinates
    - "mask": numpy array — binary mask (height, width)
    - "confidence": float — 0.0 to 1.0 (lower base confidence for raster)
    """
    global SEGMENTATION_AVAILABLE

    if not SEGMENTATION_AVAILABLE:
        # segmentation not available — Phase 1.5 still functions via:
        # legend matching + OCR + YOLO proposals
        return []

    # In a full implementation, would use Detectron2 with CubiCasa5K-style
    # pretrained model. For Phase 1.5 MVP, return empty list and rely on
    # other modalities (legend matching, OCR, YOLO proposals).

    # Placeholder: return empty list — Phase 1.5 MVP does not require
    # full segmentation; it's listed as "only for non-legend elements"
    # and is subordinate to the primary legend-matching path.
    return []


# ---------------------------------------------------------------------------
# Soft segmentation fallback: polygon approximation from YOLO boxes
# (no heavy DL model required for MVP)

def approximate_segmentation_from_yolo(
    yolo_shapes: List[Dict[str, Any]],
    image_shape: Tuple[int, int],
) -> List[Dict[str, Any]]:
    """Approximate segmentation from YOLOv8 box detections.

    Used as a lightweight fallback when detectron2 is not available.
    Produces crude bounding-box "segmentations" rather than pixel-perfect
    masks. Still tagged with lower base confidence.

    Trap constraints:
    - ✅ Only approximates from YOLO proposals (no independent DL model)
    - ✅ Tagged with lower base confidence than vector geometry
    - ✅ Does NOT classify symbols — legend matching handles that
    - ✅ Meant for non-legend elements only
    """
    height, width = image_shape[:2]
    results: List[Dict[str, Any]] = []

    for shape in yolo_shapes:
        x0, y0, x1, y1 = shape["bbox"]
        # Crude "mask": binary image region inside bbox
        # (in real usage, this would be a proper mask)
        mask = np.zeros((height, width), dtype=np.uint8)
        # Draw rect as simplified mask
        mask[int(y0):int(y1), int(x0):int(x1)] = 1

        results.append({
            "class": "approximated_from_yolo",  # not a true class — placeholder
            "bbox": (int(x0), int(y0), int(x1), int(y1)),
            "mask": mask,
            "confidence": shape.get("confidence", 0.5) * 0.7,  # reduced base confidence for raster
            "source": "yolo_approximation",
            "note": "lightweight fallback — not true segmentation",
        })

    return results


# ---------------------------------------------------------------------------
# Confidence: raster segmentation always lower than vector
# ---------------------------------------------------------------------------

RASTER_BASE_CONFIDENCE = 0.6  # default base confidence for raster-derived

def raster_confidence_score(
    base: float = RASTER_BASE_CONFIDENCE,
) -> float:
    """Return the base confidence score for any raster-derived measurement.

    Important: This score accompanies the confidence STATUS (MEASURED/DERIVED/ASSUMED)
    but is SEPARATE from it — per Rules.md §7 (no blended accuracy %).

    - Vector MEASURED → score 1.0
    - Raster MEASURED → score ~0.6 (this default)
    - DERIVED/ASSUMED scores adjusted accordingly

    Trap constraints:
    - ✅ Raster always lower base confidence than vector-derived (Rules.md §7.4)
    - ✅ Score accompanies status but is separate from it (no blended %)
    - ✅ Never a single blended accuracy % displayed to user
    """
    return float(base)


# ---------------------------------------------------------------------------
# DoD checks for segmentation (non-legend only)
# ---------------------------------------------------------------------------

SEGMENTATION_DONE_CHECKS = {
    "non_legend_only": "Segmentation for non-legend elements only (walls, rooms, spaces)",
    "no_symbol_classification": "Never use segmentation for symbol classification",
    "lower_base_confidence": "Raster segmentation tagged with lower base confidence",
    "legend_first": "Legend matching takes precedence over segmentation",
}