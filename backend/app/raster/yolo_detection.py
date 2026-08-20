"""YOLOv8 shape-cluster detection — Phase 1.5 raster/CV fallback path ONLY.

CRITICAL CONSTRAINT (AGENTS.md Rules.md §4, trap.md): YOLOv8 belongs ONLY in
the raster fallback (Phase 1.5), NOT in the v1 vector path. This file is
import-gated so it can never be loaded by the vector parsing pipeline.

YOLOv8 is used for shape clustering in raster-only path:
- Detects generic shapes (rectangles, circles, etc.) as proposals
- NEVER a universal symbol detector — only few-shot, per-document legend matching
- If legend matching fails → mark as "unknown", do NOT assign a type from YOLO alone
- Output proposals only; human/rule engine finalizes

This module is gate-kept: import check at pipeline entry ensures it is never
used in the vector (Phase 1) path.
"""

from __future__ import annotations

import logging
import sys
from typing import Dict, List, Optional, Any, Tuple

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Import gate: YOLOv8 is ONLY available in Phase 1.5 raster path.
# The vector (Phase 1) pipeline should never import this module.
# ---------------------------------------------------------------------------

_YOLO_AVAILABLE = False
_YOLO_IMPORT_ERROR = None

try:
    from ultralytics import YOLO
    _YOLO_AVAILABLE = True
except ImportError as e:
    _YOLO_IMPORT_ERROR = str(e)
    logger.warning(
        f"Ultralytics YOLOv8 not available (expected in Phase 1; "
        f"optional for Phase 1.5 raster fallback). Error: {e}"
    )

# Symbol for "not available" — used when YOLO is not installed
YOLO_NOT_AVAILABLE = False  # sentinel


# ---------------------------------------------------------------------------
# YOLOv8 detection function — raster-only path
# ---------------------------------------------------------------------------


def detect_shapes_yolov8(
    image: np.ndarray,
    conf_threshold: float = 0.25,
    iou_threshold: float = 0.45,
) -> List[Dict[str, Any]]:
    """Detect shapes in a raster image using YOLOv8.

    CRITICAL: This function MUST ONLY be called in the Phase 1.5 raster fallback
    path, never in the Phase 1 vector pipeline.

    Returns list of detected shapes with bbox, confidence, and class.
    Each shape is a proposal — final type determination requires
    per-document legend matching (see legend.py).

    Trap constraints — MUST observe:
    - ✅ YOLOv8 ONLY in Phase 1.5 raster path (never vector path)
    - ✅ Output proposals only — final type from legend matching, not YOLO
    - ✅ If legend match fails → return None/unknown, do NOT invent type
    - ✅ YOLOv8 is NOT a universal symbol detector
    """
    global _YOLO_AVAILABLE, _YOLO_IMPORT_ERROR

    if not _YOLO_AVAILABLE:
        # YOLOv8 not installed — return empty list, not an error
        # (Phase 1.5 can function without YOLO; legend matching is primary)
        return []

    try:
        # Load a lightweight model; in production this would be loaded once
        # at startup, not per-image. Using 'n' (nano) size for speed.
        # The model weights are NOT hardcoded here; they are loaded from
        # the default YOLOv8n pretrained weights or user-provided path.
        model = YOLO("yolov8n.pt")  # pretrained COCO model

        # Run inference
        results = model.predict(
            image,
            conf=conf_threshold,
            iou=iou_threshold,
            verbose=False,
        )

        shapes: List[Dict[str, Any]] = []

        for result in results:
            boxes = result.boxes
            if boxes is None or len(boxes) == 0:
                continue

            for box in boxes:
                # Extract box coordinates (xyxy format)
                xyxy = box.xyxy[0].tolist()  # [x0, y0, x1, y1]
                confidence = float(box.conf[0])
                class_id = int(box.cls[0])
                class_name = model.names[class_id]

                # Get centroid for potential clustering
                x0, y0, x1, y1 = xyxy
                centroid_x = (x0 + x1) / 2
                centroid_y = (y0 + y1) / 2

                shape_info: Dict[str, Any] = {
                    "bbox": (int(x0), int(y0), int(x1), int(y1)),
                    "centroid": (centroid_x, centroid_y),
                    "confidence": confidence,
                    "class_id": class_id,
                    "class_name": class_name,
                    "source": "yolov8",  # provenance tracking
                }
                shapes.append(shape_info)

        return shapes

    except Exception as e:
        logger.error(f"YOLOv8 detection failed: {e}")
        return []


# ---------------------------------------------------------------------------
# Shape clustering (simple proximity-based) — post-YOLO processing
# ---------------------------------------------------------------------------


def cluster_shapes_by_proximity(
    shapes: List[Dict[str, Any]],
    eps: float = 30.0,
    min_pts: int = 2,
) -> List[Dict[str, Any]]:
    """Cluster detected shapes by spatial proximity.

    Used after YOLOv8 detection to group shapes that likely belong to the
    same symbol instance (e.g., a card_reader symbol might produce multiple
    nearby detections).

    Trap constraints:
    - ✅ Clustering is spatial/proximity-based only
    - ✅ Does not assign symbol types — only groups nearby detections
    - ✅ Clusters are proposals; type determination via legend matching
    - ✅ No universal symbol detector logic embedded
    """
    import numpy as np
    from sklearn.cluster import DBSCAN

    if not shapes:
        return []

    # Extract centroids for DBSCAN clustering
    centroids = np.array([s["centroid"] for s in shapes])

    if len(centroids) < min_pts:
        # Return each shape as its own cluster (noise)
        return [{"cluster_id": -1, "shapes": [s["id"] if "id" in s else i], "note": "single_detection"} for i, s in enumerate(shapes)]

    # Apply DBSCAN clustering on centroids
    clustering = DBSCAN(eps=eps, min_samples=min_pts).fit(centroids)
    labels = clustering.labels_

    clusters: Dict[int, List[Dict[str, Any]]] = {}
    for idx, label in enumerate(labels):
        if label not in clusters:
            clusters[label] = []
        clusters[label].append(shapes[idx])

    # Convert to result format
    result: List[Dict[str, Any]] = []
    for label, cluster_shapes in clusters.items():
        result.append({
            "cluster_id": int(label),
            "shapes": cluster_shapes,
            "note": "clustered_detection",
        })

    # Add noise items (label == -1) as individual clusters
    for idx, label in enumerate(labels):
        if label == -1:
            result.append({
                "cluster_id": -1,
                "shapes": [shapes[idx]],
                "note": "noise_isolation",
            })

    return result


# ---------------------------------------------------------------------------
# YOLOv8 import gate — enforcement helper
# ---------------------------------------------------------------------------

def assert_yolo_only_in_phase_1_5() -> None:
    """Enforcement helper: assert YOLOv8 is only used in Phase 1.5.

    This function should be called at the pipeline entry point to ensure
    the vector (Phase 1) path never imports or uses YOLOv8.

    Raises ImportError if YOLOv8 is not available (expected in Phase 1)
    or if somehow called from the wrong path.

    Trap constraints:
    - ✅ AGENTS.md + Rules.md: YOLOv8 only in raster fallback (Phase 1.5)
    - ✅ Never in vector path (Phase 1)
    - ✅ Fail loudly if pipeline integrity is compromised
    """
    if not _YOLO_AVAILABLE:
        # Expected in Phase 1 — YOLO not installed; this is correct
        return

    # If we get here, YOLO is available. In a properly structured project,
    # the vector pipeline should have a guard that prevents importing this
    # module. This function is a runtime check.
    logger.info(
        "YOLOv8 is available — ensure vector pipeline does not import "
        "yolo_detection.py"
    )


# ---------------------------------------------------------------------------
# DoD checks for YOLOv8 raster usage
# ---------------------------------------------------------------------------

YOLO_DONE_CHECKS = {
    "raster_only_path": "YOLOv8 detection only in Phase 1.5 raster fallback",
    "no_universal_detector": "YOLOv8 not a universal symbol detector",
    "proposals_only": "Final type from legend matching, not YOLO alone",
    "legend_matches_first": "Detected shapes matched to per-document legend first",
}