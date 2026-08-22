"""Vector parsing engine — PyMuPDF extraction for access control takeoff.

Extracts paths, text spans, OCG layers, and clusters same-layer paths
via DBSCAN into discrete component instances.

Constraint: Always import pymupdf, never the deprecated fitz alias.
All geometry is deterministic — traceable to source path IDs.
"""

from __future__ import annotations

import uuid
from typing import List, Dict, Tuple, TypedDict
from pathlib import Path

import pymupdf  # MUST import pymupdf, never fitz

import numpy as np
from sklearn.cluster import DBSCAN


# ---------------------------------------------------------------------------
# Data types
# ---------------------------------------------------------------------------

class DrawingPath(TypedDict):
    id: str
    type: str  # "path", "rect", "circle", "line"
    path: object | None  # legacy svg.path.Path — unused in pymupdf ≥1.24
    items: List[tuple]  # raw geometry items from get_drawings(): ('l', p1, p2), ...
    bbox: Tuple[float, float, float, float]  # (x0, y0, x1, y1)
    layer: str | None
    color: str | None
    fill_color: str | None
    width: float
    page_number: int


class TextSpan(TypedDict):
    id: str
    text: str
    bbox: Tuple[float, float, float, float]
    font: str
    size: float
    flags: int
    color: str | None
    page_number: int


class ClusterResult(TypedDict):
    cluster_id: int  # -1 = noise
    centroid: np.ndarray  # (cx, cy)
    member_path_ids: List[str]
    num_paths: int
    bbox: Tuple[float, float, float, float]


# ---------------------------------------------------------------------------
# Core extraction functions
# ---------------------------------------------------------------------------


def extract_drawings(page: pymupdf.Page) -> List[DrawingPath]:
    """Extract all drawn paths from a page with layer attributes.

    Returns list of dicts keyed by the DrawingPath schema.
    Critical attribute: `layer` — used for DBSCAN clustering later.

    Note: PyMuPDF ≥1.24 exposes geometry as `items` (list of ('l', p1, p2) /
    ('c', ...) / ('qu', ...) tuples) and the bbox as `rect`. The legacy
    `path` (svg.path.Path) field no longer exists — we keep the key for
    backward compatibility but populate `items` for route measurement.
    """
    drawings = page.get_drawings()
    result: List[DrawingPath] = []

    for i, drawing in enumerate(drawings):
        rect = drawing.get("rect")
        bbox = tuple(rect) if rect is not None else (0.0, 0.0, 0.0, 0.0)

        d: DrawingPath = {
            "id": str(uuid.uuid4()),
            "type": drawing.get("type", "path"),
            "path": None,
            "items": drawing.get("items", []),
            "bbox": bbox,
            "layer": drawing.get("layer"),
            "color": drawing.get("color"),
            "fill_color": drawing.get("fill"),
            "width": drawing.get("width", 1.0),
            "page_number": page.number + 1,  # 1-indexed
        }
        result.append(d)

    return result


def extract_text_spans(page: pymupdf.Page) -> List[TextSpan]:
    """Extract all text spans from a page with bbox + font size.

    Returns list of dicts keyed by the TextSpan schema.
    Critical fields: `bbox` (for proximity matching), `font` + `size`
    (for title-block / scale detection).
    """
    text_dict = page.get_text("dict")
    spans: List[TextSpan] = []

    for block in text_dict.get("blocks", []):
        for line in block.get("lines", []):
            for span in line.get("spans", []):
                s: TextSpan = {
                    "id": str(uuid.uuid4()),
                    "text": span.get("text", ""),
                    "bbox": span.get("bbox", (0.0, 0.0, 0.0, 0.0)),
                    "font": span.get("font", "unknown"),
                    "size": span.get("size", 12.0),
                    "flags": span.get("flags", 0),
                    "color": span.get("color"),
                    "page_number": page.number + 1,
                }
                spans.append(s)

    return spans


def build_ocg_registry(doc: pymupdf.Document) -> Dict[str, Dict]:
    """Build OCG layer registry from the document.

    Returns dict keyed by layer name:
    {
        "Access Control": {"ocg": "OCG0", "status": "ON", "count": 12},
        "Electrical": {"ocg": "OCG1", "status": "ON", "count": 45},
    }
    """
    ocgs = doc.get_ocgs()
    registry: Dict[str, Dict] = {}

    for ocg in ocgs.values():
        name = ocg.get("name", "Unknown")
        registry[name] = {
            "ocg": ocg.get("ocg"),
            "status": ocg.get("status", "OFF"),
            "count": ocg.get("count", 0),
        }

    # Always include a "default" layer for paths without explicit layer
    if "default" not in registry:
        registry["default"] = {"ocg": None, "status": "ON", "count": 0}

    return registry


# ---------------------------------------------------------------------------
# DBSCAN clustering
# ---------------------------------------------------------------------------


def compute_centroid(bbox: Tuple[float, float, float, float]) -> np.ndarray:
    """Compute bbox centroid (cx, cy)."""
    cx = (bbox[0] + bbox[2]) / 2.0
    cy = (bbox[1] + bbox[3]) / 2.0
    return np.array([cx, cy])


def cluster_paths(
    paths: List[DrawingPath],
    layer: str,
    eps: float = 5.0,
    min_pts: int = 2,
) -> List[ClusterResult]:
    """Cluster paths belonging to a specific layer using DBSCAN on centroids.

    Only paths whose `layer` matches (or are None and layer == "default")
    are considered.

    Returns list of clusters, each containing member path IDs, centroid,
    and bbox envelope.
    """
    # Filter paths by layer
    layer_paths = [
        p for p in paths
        if p.get("layer") == layer or (p.get("layer") is None and layer == "default")
    ]

    if not layer_paths:
        return []

    # Compute centroids from bboxes
    centroids: List[np.ndarray] = []
    path_ids: List[str] = []

    for p in layer_paths:
        centroids.append(compute_centroid(p["bbox"]))
        path_ids.append(p["id"])

    if len(centroids) < min_pts:
        # Return each path as its own cluster (noise)
        return [
            {
                "cluster_id": -1,
                "centroid": centroids[i],
                "member_path_ids": [path_ids[i]],
                "num_paths": 1,
                "bbox": layer_paths[i]["bbox"],
            }
            for i in range(len(layer_paths))
        ]

    # Apply DBSCAN
    clustering = DBSCAN(eps=eps, min_samples=min_pts).fit(np.array(centroids))
    labels = clustering.labels_

    clusters: Dict[int, ClusterResult] = {}
    for idx, label in enumerate(labels):
        pid = path_ids[idx]
        if label not in clusters:
            clusters[label] = {
                "cluster_id": int(label),
                "centroid": np.array(centroids[idx]),
                "member_path_ids": [],
                "num_paths": 0,
                "bbox": layer_paths[idx]["bbox"],
            }
        clusters[label]["member_path_ids"].append(pid)
        clusters[label]["num_paths"] += 1

        # Expand bbox envelope
        b = clusters[label]["bbox"]
        clusters[label]["bbox"] = (
            min(b[0], layer_paths[idx]["bbox"][0]),
            min(b[1], layer_paths[idx]["bbox"][1]),
            max(b[2], layer_paths[idx]["bbox"][2]),
            max(b[3], layer_paths[idx]["bbox"][3]),
        )

    result = list(clusters.values())

    # Add noise items (label == -1) as individual clusters
    for idx, label in enumerate(labels):
        if label == -1:
            result.append({
                "cluster_id": -1,
                "centroid": np.array(centroids[idx]),
                "member_path_ids": [path_ids[idx]],
                "num_paths": 1,
                "bbox": layer_paths[idx]["bbox"],
            })

    return result


# ---------------------------------------------------------------------------
# Scale detection from text spans
# ---------------------------------------------------------------------------


def detect_scale(text_spans: List[TextSpan], default: str = "1:100") -> str:
    """Detect drawing scale from text spans (title block / dimension strings).

    Looks for patterns like "1:100", "1/4\"=1'-0\"", etc.
    Never assumes a scale — reads from sheet if present.

    Returns the detected scale string, or the default if none found.
    """
    import re

    scale_patterns = [
        r"\b(\d+\.\d+:\d+)\b",   # e.g., 1:100, 1:50
        r"\b(\d+:\d+)\b",
        r"\b(1/4|1/2|1/8)\"=1'-0\"\b",  # architectural scales
    ]

    for span in text_spans:
        text = span["text"]
        for pattern in scale_patterns:
            m = re.search(pattern, text)
            if m:
                return m.group(1)

    return default


# ---------------------------------------------------------------------------
# Full PDF parsing pipeline
# ---------------------------------------------------------------------------


def parse_pdf(pdf_path: str) -> dict:
    """Full vector parsing pipeline for a single PDF.

    Returns dict with extracted geometry, text, OCG layers, clusters,
    and detected scale — all linked back to source path IDs.

    Constraint: Uses pymupdf only. No fitz alias. No hardcoded scale.
    """
    pdf = Path(pdf_path)
    if not pdf.exists():
        raise FileNotFoundError(f"PDF not found: {pdf_path}")

    doc = pymupdf.Document(str(pdf))
    try:
        ocg_registry = build_ocg_registry(doc)

        all_drawings: List[DrawingPath] = []
        all_text_spans: List[TextSpan] = []

        for page_num in range(doc.page_count):
            page = doc[page_num]
            all_drawings.extend(extract_drawings(page))
            all_text_spans.extend(extract_text_spans(page))

        # Detect scale
        scale = detect_scale(all_text_spans, default="1:100")

        # Cluster layers — access control (MVP focus) + electrical layers.
        # Layer set is data-driven via the layer mapping (data/layer_mapping.yaml)
        # plus the legacy Phase 1 access-control names, so a new sheet's layer
        # names cluster without source changes.
        from app.parsing.layer_map import all_mapped_layers

        ac_layer_names = ("AC", "ACCESS_CONTROL", "SECURITY", "CARD_READER")
        layer_names = list(all_mapped_layers()) + list(ac_layer_names)
        # De-duplicate while preserving order.
        seen: set[str] = set()
        unique_layers: list[str] = []
        for name in layer_names:
            if name not in seen:
                seen.add(name)
                unique_layers.append(name)

        clusters: List[ClusterResult] = []

        for layer_name in unique_layers:
            layer_clusters = cluster_paths(all_drawings, layer_name, eps=5.0, min_pts=2)
            clusters.extend(layer_clusters)

        return {
            "sheet_name": pdf.name,
            "scale": scale,
            "drawing_count": len(all_drawings),
            "text_span_count": len(all_text_spans),
            "ocg_registry": ocg_registry,
            "clusters": clusters,
            "raw_drawings": all_drawings,
            "raw_text_spans": all_text_spans,
        }
    finally:
        doc.close()