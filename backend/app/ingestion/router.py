from pathlib import Path
import pymupdf  # always import pymupdf, never fitz


# Electrical layer names (OCG-controlled layers in PDFs)
ELECTRICAL_LAYER_NAMES = (
    "LIGHTING",
    "POWER",
    "SWITCHES",
    "CONDUIT",
    "CABLE_TRAY",
    "DISTRIBUTION_BOARD",
    "AC",
    "GROUND",
)


def classify_upload(file_path: str) -> dict:
    """
    PDF upload classification: vector vs raster decision.

    On upload, inspect the file using PyMuPDF:
    - High vector count + extractable text → vector path
    - Dominated by full-page raster images → raster path (Phase 1.5)
    - Electrical layer detection for downstream parsing branch selection

    Returns dict with status and diagnostic info for downstream branches.
    """
    pdf_path = Path(file_path)
    if not pdf_path.exists():
        return {"status": "error", "reason": f"File not found: {file_path}"}

    doc = pymupdf.open(file_path)
    try:
        page = doc[0]

        drawings = page.get_drawings()
        images = page.get_images(full=True)
        ocgs = doc.get_ocgs()
        ocg_names = [v.get("name", "") for v in ocgs.values()]
        has_text = page.get_text("text").strip() != ""

        # Detect electrical layers from OCG registry
        detected_electrical_layers = [
            name for name in ocg_names if name in ELECTRICAL_LAYER_NAMES
        ]

        # Vector path: substantial drawing content + extractable text
        # Heuristic: > 10000 drawing elements indicates vector CAD output
        # (sample sheet has ~10000+ drawings for access control layer)
        vector_score = len(drawings)
        image_score = len(images)

        if vector_score > 10000 and has_text:
            return {
                "status": "vector",
                "page_count": doc.page_count,
                "drawing_count": vector_score,
                "image_count": image_score,
                "has_text": has_text,
                "detected_electrical_layers": detected_electrical_layers,
                "reason": "High vector count + extractable text — proceed with vector parsing",
            }
        elif vector_score < 100 and image_score > 0 and not has_text:
            return {
                "status": "raster",
                "page_count": doc.page_count,
                "drawing_count": vector_score,
                "image_count": image_score,
                "has_text": has_text,
                "reason": "Dominantly raster — defer to Phase 1.5 CV fallback",
            }
        else:
            # Ambiguous: log and default to vector for MVP; can be reviewed later
            return {
                "status": "vector",
                "page_count": doc.page_count,
                "drawing_count": vector_score,
                "image_count": image_score,
                "has_text": has_text,
                "detected_electrical_layers": detected_electrical_layers,
                "reason": "Ambiguous classification — defaulting to vector path for MVP",
            }
    finally:
        doc.close()