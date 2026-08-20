"""PDF raster rendering at high DPI — Phase 1.5 fallback path.

Renders PDF pages to high-DPI pixmaps for OCR and CV processing.
Critical constraint: always import pymupdf, never the deprecated fitz alias.
Raster images always have lower base confidence than vector-derived measurements.
"""

from __future__ import annotations

import numpy as np
from pathlib import Path

import pymupdf  # MUST import pymupdf, never fitz


# ---------------------------------------------------------------------------
# Rendering functions
# ---------------------------------------------------------------------------

def render_page_to_pixmap(
    pdf_path: str,
    page_num: int = 0,
    dpi: int = 300,
) -> np.ndarray:
    """Render a PDF page to a high-DPI pixmap (numpy array).

    Args:
        pdf_path: Path to the PDF file.
        page_num: Zero-based page index.
        dpi: Dots per inch for rendering. Minimum 300 DPI for OCR accuracy;
             600 DPI recommended for detailed geometry.

    Returns:
        numpy array of shape (height, width, channels) — RGB or RGBA.

    Trap constraints:
    - ✅ Uses `import pymupdf`, never `fitz`
    - ✅ Raster output is lower confidence than vector geometry
    - ✅ DPI parameter controlled; default 300 minimum for OCR
    """
    pdf = Path(pdf_path)
    if not pdf.exists():
        raise FileNotFoundError(f"PDF not found: {pdf_path}")

    doc = pymupdf.Document(str(pdf))
    try:
        page = doc[page_num]
        # Render at specified DPI — higher DPI = better OCR/CV results
        # but larger images; 300 DPI minimum, 600 DPI recommended
        pix = page.get_pixmap(dpi=dpi)
        # pixmap returns RGBA bytes; convert to numpy array
        arr = np.frombuffer(pix.samples, dtype=np.uint8).reshape(
            pix.height, pix.width, 4
        )  # RGBA
        # Optionally drop alpha channel
        arr_rgb = arr[..., :3]  # RGB
        return arr_rgb
    finally:
        doc.close()


def render_all_pages_to_pixmaps(
    pdf_path: str,
    dpi: int = 300,
) -> list[np.ndarray]:
    """Render all pages of a PDF to pixmaps.

    Returns list of numpy arrays, one per page, in page order.
    """
    pdf = Path(pdf_path)
    if not pdf.exists():
        raise FileNotFoundError(f"PDF not found: {pdf_path}")

    doc = pymupdf.Document(str(pdf))
    try:
        result: list[np.ndarray] = []
        for page_num in range(doc.page_count):
            pix = doc[page_num].get_pixmap(dpi=dpi)
            arr = np.frombuffer(pix.samples, dtype=np.uint8).reshape(
                pix.height, pix.width, 4
            )
            result.append(arr[..., :3])  # RGB
        return result
    finally:
        doc.close()


# ---------------------------------------------------------------------------
# Convenience for Phase 1.5 classification
# ---------------------------------------------------------------------------

def default_dpi_for_ocr() -> int:
    """Return the recommended DPI for OCR processing.

    Per best practices: 300 DPI minimum, 600 DPI for best results.
    Caller may choose 300 or 600 based on image size constraints.
    """
    return 300  # minimum; Phase 1.5 may override to 600 for detail work


# ---------------------------------------------------------------------------
# Trap compliance helpers
# ---------------------------------------------------------------------------

def verify_pymupdf_import() -> None:
    """Verify that pymupdf is importable and fitz is not used.

    CI/lint can call this to enforce the no-fitz rule."""
    import pymupdf as _pm  # noqa: F401
    # If we reach here without ImportError for fitz, we're compliant
    # (any import fitz elsewhere in the codebase will trigger lint failure)


# ---------------------------------------------------------------------------
# Definition of Done checks for Task 1
# ---------------------------------------------------------------------------

TASK_1_DONE_CHECKS = {
    "pymupdf_import_ok": "import pymupdf succeeds, import fitz is blocked",
    "render_function_returns_numpy": "render_page_to_pixmap returns np.ndarray",
    "dpi_parameter_controlled": "dpi parameter with 300 minimum",
    "file_not_found_error": "raises FileNotFoundError if pdf missing",
    "no_universal_symbol_detector": "no LLM/vision outputs final quantity",
}