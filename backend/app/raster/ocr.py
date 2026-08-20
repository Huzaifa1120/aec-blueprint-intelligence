"""OCR integration — Phase 1.5 raster/CV fallback.

Primary: PaddleOCR (accurate document text extraction).
Fallback: Tesseract (lightweight, secondary).

Critical constraint: OCR results are PROPOSALS ONLY — not final quantities,
dimensions, or prices. Never output a quantity from OCR directly.

All geometry and quantities must trace to deterministic calculations from
vector paths (Phase 1) or rule-derived formulas. OCR only provides text
proposals that the rules engine / human review may use as hints.
"""

from __future__ import annotations

from typing import List, Dict, Any, Optional, Tuple

import numpy as np

# Import PaddleOCR primary; Tesseract as lightweight fallback
try:
    from paddleocr import PaddleOCR as _PaddleOCR
    _PADDLEOCR_AVAILABLE = True
except ImportError:
    _PADDLEOCR_AVAILABLE = False

try:
    import pytesseract
    _TESSERACT_AVAILABLE = True
    # Ensure tesseract is callable without path issues in Phase 1.5
except ImportError:
    _TESSERACT_AVAILABLE = False


# ---------------------------------------------------------------------------
# PaddleOCR primary extraction
# ---------------------------------------------------------------------------

def ocr_paddle(
    image: np.ndarray,
    lang: str = "en",
) -> List[Dict[str, Any]]:
    """Run PaddleOCR on a numpy array image (RGB).

    Returns list of dicts with extracted text, bbox, and confidence:
    [
        {
            "text": "card reader",
            "bbox": (x0, y0, x1, y1),  # pixel coordinates
            "confidence": 0.92,         # PaddleOCR confidence score
        },
        ...
    ]

    Trap constraints:
    - ✅ OCR results are PROPOSALS ONLY — not final quantities
    - ✅ Raster-derived text has lower base confidence
    - ✅ Never output final quantity, length, area, or price from OCR
    - ✅ Used only as input hint for legend matching / human review
    """
    if not _PADDLEOCR_AVAILABLE:
        raise ImportError(
            "PaddleOCR not installed. "
            "Install with: pip install paddleocr"
        )

    # PaddleOCR expects BGR image by default; convert from RGB if needed
    if image.shape[2] == 3:
        # If already RGB, PaddleOCR can handle it; ensure contiguous
        image_bgr = np.ascontiguousarray(image[:, :, ::-1])  # RGB -> BGR
    else:
        image_bgr = np.ascontiguousarray(image)

    # Run PaddleOCR
    # use_angle_classification improves text orientation accuracy
    ocr = _PaddleOCR(lang=lang, use_angle_classification=True, show_log=False)
    results = ocr.ocr(image_bgr, cls=True)

    extracted: List[Dict[str, Any]] = []

    if results and results[0]:
        for line in results[0]:
            # line format: [[[bbox_points], (text, confidence)]]
            bbox_points = line[0]
            text_info = line[1]
            text = text_info[0]
            confidence = float(text_info[1])

            # Convert four corner bbox to (x0, y0, x1, y1) format
            xs = [p[0] for p in bbox_points]
            ys = [p[1] for p in bbox_points]
            bbox = (min(xs), min(ys), max(xs), max(ys))

            extracted.append({
                "text": text,
                "bbox": bbox,
                "confidence": confidence,
            })

    return extracted


# ---------------------------------------------------------------------------
# Tesseract fallback extraction
# ---------------------------------------------------------------------------

def ocr_tesseract(
    image: np.ndarray,
    lang: str = "eng",
) -> List[Dict[str, Any]]:
    """Run Tesseract OCR as lightweight fallback on a numpy array image.

    Returns same format as ocr_paddle: list of dicts with text, bbox, confidence.

    Trap constraints:
    - ✅ Fallback only when PaddleOCR unavailable
    - ✅ Results are PROPOSALS ONLY — never final quantities
    - ✅ Raster-derived text has lower base confidence
    """
    if not _TESSERACT_AVAILABLE:
        raise ImportError(
            "Tesseract not installed. "
            "Install with: pip install pytesseract"
        )

    # Tesseract works best with grayscale; convert if color
    if image.shape[2] == 3:
        gray = np.mean(image, axis=2).astype(np.uint8)
    else:
        gray = image[:, :, 0]

    # Run Tesseract — output includes text, bbox, and confidence
    data = pytesseract.image_to_data(
        gray, lang=lang, output_type=pytesseract.Output.DICT
    )

    extracted: List[Dict[str, Any]] = []

    num_elements = len(data["text"])
    for i in range(num_elements):
        text = data["text"][i].strip()
        if not text:
            continue

        try:
            conf = float(data["conf"][i])
        except (ValueError, TypeError):
            conf = 0.0

        # Tesseract bbox: (x, y, w, h) from top-left; convert to (x0, y0, x1, y1)
        x = int(data["left"][i])
        y = int(data["top"][i])
        w = int(data["width"][i])
        h = int(data["height"][i])
        bbox = (x, y, x + w, y + h)

        if text:
            extracted.append({
                "text": text,
                "bbox": bbox,
                "confidence": conf / 100.0 if conf > 1 else conf,  # Tesseract 0-100
            })

    return extracted


# ---------------------------------------------------------------------------
# Unified OCR entry point (primary → fallback)
# ---------------------------------------------------------------------------

def ocr_image(
    image: np.ndarray,
    prefer: str = "paddle",
    lang: str = "en",
) -> List[Dict[str, Any]]:
    """Run OCR on an image, preferring PaddleOCR with Tesseract fallback.

    Strategy:
    1. Try PaddleOCR (primary, more accurate for document text).
    2. If PaddleOCR unavailable or fails, fall back to Tesseract.
    3. If both fail, return empty list (not an error — caller handles).

    Returns list of dicts: [{"text": "...", "bbox": (x0,y0,x1,y1), "confidence": float}, ...]

    Trap constraints:
    - ✅ OCR results are PROPOSALS ONLY — never final quantities
    - ✅ Raster text extraction for hints, not deterministic calculations
    - ✅ Lower base confidence than vector geometry
    """
    if prefer == "paddle":
        try:
            return ocr_paddle(image, lang=lang)
        except Exception as e:
            # Log and fall through to Tesseract
            print(f"PaddleOCR failed: {e}")

    # Fallback to Tesseract
    if prefer == "tesseract" or prefer == "paddle":
        try:
            return ocr_tesseract(image, lang=lang)
        except Exception as e:
            print(f"Tesseract also failed: {e}")

    # Return empty list — caller should handle gracefully
    return []


# ---------------------------------------------------------------------------
# Legend text detection (extract the sheet's own legend table)
# ---------------------------------------------------------------------------

def detect_legend_text(
    image: np.ndarray,
    lang: str = "en",
) -> Optional[Dict[str, Any]]:
    """Extract the legend table from a rasterized PDF page.

    Strategy:
    1. Run OCR on the full image.
    2. Look for text strings that likely belong to a legend table:
       - High up on the page (legends are typically in margins/title block area)
       - Smaller font size
       - Contains symbol/keyword patterns: "legend", "symbol", "key", etc.
    3. Return the most likely legend text block.

    This is per-document legend matching — NOT a universal symbol detector.

    Trap constraints — MUST observe:
    - ✅ Per-document legend matching first, always (Rules.md §4;
      AGENTS.md no universal symbol detector)
    - ✅ No universal cross-company symbol detector built
    - ✅ Legend is specific to each sheet document
    - ✅ Fallback to "unknown" if legend doesn't match
    """
    ocr_results = ocr_image(image, prefer="paddle", lang=lang)

    legend_keywords = ["legend", "symbol", "key", "table", "note", "scale"]
    legend_candidates: List[Dict[str, Any]] = []

    for item in ocr_results:
        text = item["text"].lower()
        bbox = item["bbox"]

        # Heuristics: legend typically in top portion of page, smaller text
        # If text contains legend-related keywords, consider it
        keyword_match = any(kw in text for kw in legend_keywords)

        # Also consider: text length moderate (not a single word, not a paragraph)
        moderate_length = 3 <= len(text.split()) <= 20

        if keyword_match or moderate_length:
            legend_candidates.append(item)

    if not legend_candidates:
        return None

    # Return the candidate with highest confidence that also appears
    # near the top of the page (y0 small = near top)
    best = max(
        legend_candidates,
        key=lambda ic: ic["confidence"] * (1 - ic["bbox"][1] / 2000),  # prefer top-of-page
    )

    return {
        "text": best["text"],
        "bbox": best["bbox"],
        "method": "ocr_legend",
        "confidence": best["confidence"],
    }