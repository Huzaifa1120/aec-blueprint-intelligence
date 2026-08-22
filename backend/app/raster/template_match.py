"""Classical-CV template matching helpers — Phase 2.5 raster path (spec v3 §7.7A).

Raster symbol detection uses ONLY an Apache-2.0-licensed classical-CV toolchain
(OpenCV contour analysis + normalized cross-correlation template matching).
Detectron2 is explicitly deferred (spec v3 §7.7A); trained neural detectors
remain quarantined (yolo_detection.py behind ENABLE_LEGACY_YOLO=1) and are never
part of the default stack.

Every function here emits PROPOSALS only — quantities, types, and prices are
derived downstream by deterministic rules with human approval (AI proposes,
geometry calculates, rules derive, humans approve).
"""

from __future__ import annotations

import logging
from pathlib import Path

import cv2
import numpy as np

from app.raster.renderer import render_page_to_pixmap

logger = logging.getLogger(__name__)

# Glyph-cell extraction tuning (spec v3 §7.7A legend segmentation)
_MIN_CELL_AREA_PX = 9
_MIN_CELL_DIM_PX = 5
_AREA_PCT_LOW = 5.0
_MAX_CELL_CROP_FRAC = 0.25  # cells larger than this fraction of the crop are container frames
_TEMPLATE_DIFF_THRESHOLD = 18.0  # mean abs-diff (0-255) => "near-identical" cells
_COMPARE_SIZE = (32, 32)

# Legend-region heuristic attempts, tried in order until one qualifies:
#   close_frac      morphology-close kernel size as fraction of min(page_h, page_w)
#   min_cells       distinct ink components required inside the candidate rect
#   min_density     minimum ink-pixel density inside the candidate rect (0-1)
#   min/max_area_frac  candidate rect area bounds as fraction of page area
#   max_area_ratio  component-area uniformity cap: p90/median must not exceed
#   max_dim_frac    no single component may span more than this fraction of the rect
_LEGEND_PARAM_SETS: list[dict[str, float]] = [
    {
        "close_frac": 0.023,
        "min_cells": 30,
        "min_density": 0.03,
        "min_area_frac": 0.005,
        "max_area_frac": 0.20,
        "max_area_ratio": 3.5,
        "max_dim_frac": 0.35,
    },
    {
        "close_frac": 0.030,
        "min_cells": 20,
        "min_density": 0.02,
        "min_area_frac": 0.004,
        "max_area_frac": 0.25,
        "max_area_ratio": 4.0,
        "max_dim_frac": 0.40,
    },
    {
        "close_frac": 0.016,
        "min_cells": 40,
        "min_density": 0.035,
        "min_area_frac": 0.008,
        "max_area_frac": 0.15,
        "max_area_ratio": 3.0,
        "max_dim_frac": 0.30,
    },
    {
        "close_frac": 0.040,
        "min_cells": 10,
        "min_density": 0.015,
        "min_area_frac": 0.003,
        "max_area_frac": 0.30,
        "max_area_ratio": 4.5,
        "max_dim_frac": 0.45,
    },
    {
        "close_frac": 0.010,
        "min_cells": 50,
        "min_density": 0.04,
        "min_area_frac": 0.010,
        "max_area_frac": 0.12,
        "max_area_ratio": 3.0,
        "max_dim_frac": 0.30,
    },
    {
        "close_frac": 0.060,
        "min_cells": 6,
        "min_density": 0.01,
        "min_area_frac": 0.002,
        "max_area_frac": 0.35,
        "max_area_ratio": 5.0,
        "max_dim_frac": 0.50,
    },
]


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _to_gray(image: np.ndarray) -> np.ndarray:
    if image.ndim == 2:
        return image
    return cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)


def _ink_mask(image: np.ndarray) -> np.ndarray:
    """Binarized drawing-ink mask (dark strokes on light paper -> white ink)."""
    gray = _to_gray(image)
    return cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY_INV | cv2.THRESH_OTSU)[1]


def _strip_long_lines(mask: np.ndarray, divisor: int = 25) -> np.ndarray:
    """Remove horizontal/vertical rules longer than maxdim//divisor pixels.

    Sheet border frames otherwise connect every region into one external
    contour, which defeats block detection on real drawings. ``divisor``
    controls aggressiveness: 25 suits full pages (frames span the sheet),
    smaller values protect small features when cropping legends.
    """
    mh, mw = mask.shape[:2]
    horiz = cv2.morphologyEx(mask, cv2.MORPH_OPEN, np.ones((1, max(mw // divisor, 15)), np.uint8))
    vert = cv2.morphologyEx(mask, cv2.MORPH_OPEN, np.ones((max(mh // divisor, 15), 1), np.uint8))
    return cv2.bitwise_and(mask, cv2.bitwise_not(cv2.bitwise_or(horiz, vert)))


def _resolve_source(page: object, page_num: int) -> tuple[str, int]:
    """Map a PDF path or pymupdf.Page onto the (path, page index) the renderer takes."""
    if isinstance(page, (str, Path)):
        return str(page), page_num
    import pymupdf

    if isinstance(page, pymupdf.Page):
        doc_name = str(getattr(page.parent, "name", "") or "")
        if not doc_name:
            raise ValueError("pymupdf.Page has no backing file path; pass a PDF path")
        return doc_name, int(page.number)
    raise TypeError(f"Unsupported page source: {type(page)!r}")


def _decode_pixmap_direct(pdf_path: str, page_num: int, dpi: int) -> np.ndarray:
    """Fallback RGB decode mirroring renderer.render_page_to_pixmap's intent.

    Temporary shim: renderer.py:52 hardcodes a 4-channel pixmap reshape, which
    raises ValueError for pymupdf's default alpha-free (3-channel) pixmaps.
    This decodes the identical pixmap channel-correctly WITHOUT modifying
    renderer.py; flagged for a follow-up one-line fix upstream.
    """
    import pymupdf

    doc = pymupdf.Document(pdf_path)
    try:
        pix = doc[page_num].get_pixmap(dpi=dpi)
        arr = np.frombuffer(pix.samples, dtype=np.uint8).reshape(pix.height, pix.width, pix.n)
        return arr[:, :, :3]
    finally:
        doc.close()


# ---------------------------------------------------------------------------
# Public API (spec v3 §7.7A)
# ---------------------------------------------------------------------------


def render_page_to_array(
    page: object,
    dpi: int = 300,
    page_num: int = 0,
) -> np.ndarray:
    """Render a PDF page to a contiguous BGR ``uint8`` array.

    Adaptation note (Task 7): ``app.raster.renderer.render_page_to_pixmap`` has
    signature ``(pdf_path, page_num=0, dpi=300)`` and ALREADY returns an RGB
    ndarray (not a raw pixmap object), so this wrapper delegates to it and only
    flips RGB->BGR. If that call trips renderer.py's hardcoded 4-channel
    reshape (ValueError), a channel-correct fallback decode is used instead;
    renderer.py itself is untouched. Accepts a PDF filesystem path or a
    ``pymupdf.Page`` (routed through its document's file path).
    """
    source, page_index = _resolve_source(page, page_num)
    try:
        rgb = render_page_to_pixmap(source, page_num=page_index, dpi=dpi)
    except ValueError:
        logger.warning(
            "render_page_to_pixmap raised on its 4-channel reshape assumption "
            "(renderer.py:52); decoding pixmap directly (spec v3 §7.7A path)"
        )
        rgb = _decode_pixmap_direct(source, page_index, dpi)
    return np.ascontiguousarray(rgb[:, :, ::-1])


def detect_legend_region(page_image: np.ndarray) -> tuple[int, int, int, int] | None:
    """Locate the largest dense grid-like region (symbol legend/schedule).

    Heuristic per spec v3 §7.7A: strip long rules (sheet frames), merge nearby
    strokes with a morphological close, then score candidate rectangles by ink
    density and "grid-likeness" — many small components of UNIFORM area packed
    inside (p90/median area ratio capped; no single component may dominate the
    rect). This rejects floor-plan geometry (highly non-uniform strokes) while
    keeping legend/schedule tables. Parameter sets are attempted in order until
    one qualifies.

    Returns:
        (x, y, w, h) in page pixels, or None when no region qualifies (the
        Phase 2.5 spike fails loudly downstream rather than guessing).
    """
    ph, pw = page_image.shape[:2]
    page_area = float(ph * pw)
    ink = _strip_long_lines(_ink_mask(page_image))
    integral = cv2.integral(ink, sdepth=cv2.CV_64F) / 255.0

    n_labels, _, stats, centroids = cv2.connectedComponentsWithStats(ink, connectivity=8)
    ids = [i for i in range(1, n_labels) if stats[i, cv2.CC_STAT_AREA] >= 4]
    comp_x = np.array([stats[i, cv2.CC_STAT_LEFT] for i in ids], dtype=float)
    comp_y = np.array([stats[i, cv2.CC_STAT_TOP] for i in ids], dtype=float)
    comp_w = np.array([stats[i, cv2.CC_STAT_WIDTH] for i in ids], dtype=float)
    comp_h = np.array([stats[i, cv2.CC_STAT_HEIGHT] for i in ids], dtype=float)
    comp_a = np.array([stats[i, cv2.CC_STAT_AREA] for i in ids], dtype=float)

    def _density(x: int, y: int, rw: int, rh: int) -> float:
        s = integral[y + rh, x + rw] - integral[y, x + rw] - integral[y + rh, x] + integral[y, x]
        return float(s / max(rw * rh, 1))

    def _grid_stats(x: int, y: int, rw: int, rh: int) -> tuple[int, float, float]:
        inside = (comp_x >= x) & (comp_x < x + rw) & (comp_y >= y) & (comp_y < y + rh)
        n_cells = int(np.count_nonzero(inside))
        if n_cells == 0:
            return 0, 0.0, 0.0
        areas = comp_a[inside]
        med = max(float(np.median(areas)), 1.0)
        ratio = float(np.percentile(areas, 90)) / med
        dim_frac = float(max(comp_w[inside].max() / rw, comp_h[inside].max() / rh))
        return n_cells, ratio, dim_frac

    for attempt, params in enumerate(_LEGEND_PARAM_SETS, start=1):
        k = max(3, int(round(params["close_frac"] * min(ph, pw))) | 1)
        kernel = np.ones((k, k), dtype=np.uint8)
        closed = cv2.morphologyEx(ink, cv2.MORPH_CLOSE, kernel)
        contours, _ = cv2.findContours(closed, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

        best: tuple[int, int, int, int] | None = None
        best_score = 0.0
        for contour in contours:
            x, y, rw, rh = cv2.boundingRect(contour)
            area = float(rw * rh)
            if (
                not params["min_area_frac"] * page_area
                <= area
                <= params["max_area_frac"] * page_area
            ):
                continue
            density = _density(x, y, rw, rh)
            if density < params["min_density"]:
                continue
            cells, area_ratio, dim_frac = _grid_stats(x, y, rw, rh)
            if cells < params["min_cells"]:
                continue
            if area_ratio > params["max_area_ratio"]:
                continue
            if dim_frac > params["max_dim_frac"]:
                continue
            score = area * density * min(cells, 1000)
            if score > best_score:
                best_score = score
                best = (x, y, rw, rh)

        if best is not None:
            logger.info(
                "detect_legend_region: qualified on attempt %d/%d params=%s bbox=%s",
                attempt,
                len(_LEGEND_PARAM_SETS),
                params,
                best,
            )
            return best

    logger.warning(
        "detect_legend_region: no grid-like legend region found (%d heuristic attempts exhausted)",
        len(_LEGEND_PARAM_SETS),
    )
    return None


def extract_glyph_templates(
    page_image: np.ndarray,
    legend_bbox: tuple[int, int, int, int],
) -> list[dict]:
    """Segment unique glyph cells out of a legend region via contour analysis.

    Pipeline: binarize the legend crop (long table rules stripped) -> external
    contours -> area filter (lower-area percentile drops speckle; cells larger
    than a quarter of the crop are container frames) -> dimension floors reject
    sliver fragments -> reading-order sort (row bands by median cell height,
    then left-to-right) -> dedupe near-identical cells by mean abs-diff on a
    normalized thumbnail, KEEPING the first occurrence's ``origin_px`` (Task 8
    label spatial-join depends on first-cell origins).

    Returns:
        List of ``{"image": np.ndarray (BGR crop), "origin_px": (x, y),
        "size_px": (h, w)}`` where origin_px is absolute page-pixel coords.
    """
    ph, pw = page_image.shape[:2]
    lx, ly, lw, lh = (int(v) for v in legend_bbox)
    lx, ly = max(0, lx), max(0, ly)
    lw, lh = min(lw, pw - lx), min(lh, ph - ly)
    if lw <= 0 or lh <= 0:
        return []

    crop = page_image[ly : ly + lh, lx : lx + lw]
    ink = _strip_long_lines(_ink_mask(crop), divisor=8)
    ink = cv2.morphologyEx(ink, cv2.MORPH_OPEN, np.ones((2, 2), dtype=np.uint8))
    contours, _ = cv2.findContours(ink, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

    cells = [
        {"x": x, "y": y, "w": bw, "h": bh, "area": bw * bh}
        for x, y, bw, bh in (cv2.boundingRect(c) for c in contours)
    ]
    if not cells:
        return []

    areas = np.array([c["area"] for c in cells], dtype=float)
    if len(cells) >= 5:
        lo = float(np.percentile(areas, _AREA_PCT_LOW))
    else:
        lo = float(areas.min())
    hi = _MAX_CELL_CROP_FRAC * float(lw * lh)
    cells = [c for c in cells if c["area"] >= max(lo, _MIN_CELL_AREA_PX) and c["area"] <= hi]
    if not cells:
        return []

    med_w = max(float(np.median([c["w"] for c in cells])), 1.0)
    med_h = max(float(np.median([c["h"] for c in cells])), 1.0)
    cells = [
        c
        for c in cells
        if c["w"] >= _MIN_CELL_DIM_PX
        and c["h"] >= _MIN_CELL_DIM_PX
        and c["w"] >= 0.35 * med_w
        and c["h"] >= 0.5 * med_h
    ]
    if not cells:
        return []

    cells.sort(key=lambda c: (round(c["y"] / med_h), c["x"]))

    templates: list[dict] = []
    kept_features: list[np.ndarray] = []
    for cell in cells:
        image = crop[cell["y"] : cell["y"] + cell["h"], cell["x"] : cell["x"] + cell["w"]].copy()
        feature = _compare_feature(image)
        if any(
            float(np.mean(np.abs(feature - f))) < _TEMPLATE_DIFF_THRESHOLD for f in kept_features
        ):
            continue
        kept_features.append(feature)
        templates.append(
            {
                "image": image,
                "origin_px": (lx + cell["x"], ly + cell["y"]),
                "size_px": (cell["h"], cell["w"]),
            }
        )
    return templates


def find_symbol_locations(
    page_image: np.ndarray,
    template: np.ndarray,
    threshold: float = 0.8,
) -> list[tuple[int, int]]:
    """Find instances of ``template`` on the page (PROPOSALS ONLY).

    ``cv2.matchTemplate`` with TM_CCOEFF_NORMED followed by greedy non-maximum
    suppression: candidates are scanned best-score-first and a candidate is
    suppressed when within ``max(template_h, template_w) / 2`` of an accepted
    center.

    Returns:
        List of (cx, cy) match centers in page pixels, best-first.
    """
    page_gray = _to_gray(page_image)
    tmpl_gray = _to_gray(template)
    th, tw = tmpl_gray.shape[:2]
    ph, pw = page_gray.shape[:2]
    if th > ph or tw > pw or th == 0 or tw == 0:
        return []

    result = cv2.matchTemplate(page_gray, tmpl_gray, cv2.TM_CCOEFF_NORMED)
    ys, xs = np.where(result >= threshold)
    if len(xs) == 0:
        return []

    scores = result[ys, xs]
    order = np.argsort(scores)[::-1]

    radius = max(th, tw) / 2.0
    radius_sq = radius * radius
    centers: list[tuple[int, int]] = []
    for idx in order:
        cx = int(xs[idx]) + tw // 2
        cy = int(ys[idx]) + th // 2
        if all((cx - ax) ** 2 + (cy - ay) ** 2 > radius_sq for ax, ay in centers):
            centers.append((cx, cy))
    return centers


def _compare_feature(image: np.ndarray) -> np.ndarray:
    gray = _to_gray(image)
    resized = cv2.resize(gray, _COMPARE_SIZE, interpolation=cv2.INTER_AREA)
    return resized.astype(np.float32)
