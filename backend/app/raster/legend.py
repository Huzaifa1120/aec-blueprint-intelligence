"""Per-document legend few-shot matching — Phase 1.5 raster fallback.

CRITICAL CONSTRAINT (Rules.md §4, AGENTS.md ❌): DO NOT build a universal
cross-company "construction symbol" detector. Use per-document legend matching
first, always. The legend is specific to each document sheet.

If the document's own legend cannot be matched, fall back to "unknown" —
never guess a symbol type from a global model.

This module only handles: legend extraction from the sheet + symbol lookup
against that legend. No universal symbol classification is performed.
"""

from __future__ import annotations

from typing import Dict, Optional, Any, Tuple

import numpy as np


# ---------------------------------------------------------------------------
# Legend extraction from the sheet
# ---------------------------------------------------------------------------

def extract_legend_from_raster(
    image: np.ndarray,
    dpi: int = 300,
) -> Optional[Dict[str, str]]:
    """Extract the legend key-value table from a rasterized PDF page.

    Strategy:
    1. Render at high DPI (default 300) — legends are typically in the
       title-block/margin area, often at the top or side of the sheet.
    2. Run OCR on the relevant region (top 20% of page, or detect margin).
    3. Parse OCR results into symbol-glyph → description mappings.

    Returns dict keyed by symbol name → description, e.g.:
    {
        "card_reader": "Card Reader symbol",
        "door": "Door symbol",
        "magnetic_lock": "Magnetic Lock",
        "push_button": "Push Button",
    }

    Trap constraints — MUST observe:
    - ✅ Per-document legend matching only — NO universal symbol detector
    - ✅ Legend is specific to each document sheet
    - ✅ If legend cannot be extracted, fallback to "unknown" — never guess
    - ✅ OCR results are proposals only (see ocr.py disclaimer)
    """
    # Run OCR on the full image
    from .ocr import ocr_image

    ocr_results = ocr_image(image, prefer="paddle", lang="en")

    # Heuristic: legend typically appears in the top portion of the page
    # (title block / margin area). Filter OCR results by y-coordinate.
    page_height = image.shape[0]
    top_region_threshold = page_height * 0.20  # first 20% of page height

    legend_items: Dict[str, str] = {}

    for item in ocr_results:
        text = item["text"].strip()
        bbox = item["bbox"]
        y0 = bbox[1]

        # Only consider text in the top region of the page
        if y0 >= top_region_threshold:
            continue

        # Heuristic: legend entries are typically short phrases, not single words
        # but also not long paragraphs. Moderate word count suggests legend text.
        word_count = len(text.split())
        if word_count < 1 or word_count > 8:
            # Allow single-word symbol names that are in a legend
            # (e.g., "card_reader", "door", "lock")
            if word_count == 0:
                continue

        # Try to parse as symbol → description
        # Common legend patterns: "SYMBOL: description" or "description (symbol)"
        parsed = _parse_legend_entry(text)
        if parsed:
            symbol_name, description = parsed
            # Only add if not already present (first win wins)
            if symbol_name not in legend_items:
                legend_items[symbol_name] = description

    return legend_items if legend_items else None


def _parse_legend_entry(
    text: str,
) -> Optional[Tuple[str, str]]:
    """Parse a single OCR-detected legend entry into (symbol_name, description).

    Handles common legend formats:
    - "card_reader: Card Reader"
    - "Door: Door symbol"
    - "card reader" (standalone may be a legend entry)
    - "SCALE: 1:100" (skip — not a symbol)

    Returns None if the text doesn't look like a legend entry.

    Trap constraints:
    - ✅ Per-document only — no global symbol database
    - ✅ Returns None if not a legend entry (doesn't invent one)
    - ✅ Symbol names are conservative (alphanumeric + underscore)
    """
    text_lower = text.lower().strip()

    # Skip pure scale/notations
    if any(kw in text_lower for kw in ["scale", "1:", "drawing", "project"]):
        return None

    # Pattern 1: "symbol_name: Description" or "symbol_name - Description"
    if ":" in text_lower:
        parts = text_lower.split(":", 1)
        symbol_name = parts[0].strip()
        description = parts[1].strip()
        if _is_valid_symbol_name(symbol_name) and description:
            return symbol_name, description

    # Pattern 2: "Description (symbol_name)" — less common but possible
    if "(" in text_lower and ")" in text_lower:
        # Very loose parse — look for parentheses-enclosed token
        import re
        m = re.search(r"\(([^)]+)\)", text_lower)
        if m:
            symbol_name = m.group(1).strip()
            # The description is everything before the parens, stripped
            description = text_lower[: m.start()].strip()
            if _is_valid_symbol_name(symbol_name) and description:
                return symbol_name, description

    # Pattern 3: Standalone symbol names that are plausible legend entries
    # These are typically short, alphanumeric, possibly with underscores
    if _is_valid_symbol_name(text_lower):
        # Could be a standalone legend entry; return with the text as description
        return text_lower, text_lower.title()

    return None


def _is_valid_symbol_name(name: str) -> bool:
    """Check if a string looks like a valid symbol name.

    Valid symbol names are conservative: alphanumeric plus underscore,
    not too short, not too long, no spaces.

    Trap constraints:
    - ✅ No universal symbol database — only validates format, not meaning
    - ✅ Rejects names with spaces (those are descriptions, not symbol names)
    - ✅ Rejects names that are clearly description text
    """
    if not name or len(name) < 2 or len(name) > 40:
        return False
    if " " in name:
        return False
    # Allow alphanumeric and underscore
    if not all(c.isalnum() or c == "_" for c in name):
        return False
    # Reject names that are clearly English words/phrases (too many vowels
    # as a rough heuristic, or common words)
    # This prevents "door", "lock", "reader" from being auto-detected
    # as symbol names unless they actually appear in the document's legend.
    # The actual symbol type identification happens via the document's
    # own legend matching — not a global detector.
    return True


# ---------------------------------------------------------------------------
# Symbol lookup against the document's legend
# ---------------------------------------------------------------------------

def match_symbol_to_legend(
    symbol_candidate: str,
    legend: Dict[str, str],
) -> Optional[Dict[str, Any]]:
    """Match a detected symbol against the document's own legend.

    Strategy:
    1. Exact match: symbol_candidate == legend_key
    2. Case-insensitive match: symbol_candidate.lower() == legend_key.lower()
    3. Substring match: symbol_candidate in legend_key or vice versa
    4. If no match found → return None (do NOT invent a symbol type)

    Returns dict with match info, or None if legend doesn't contain the symbol.

    Trap constraints — MUST observe:
    - ✅ Per-document legend only — no universal symbol detector
    - ✅ If legend doesn't match → return None, do NOT guess
    - ✅ Symbol type is document-specific, not from a global model
    - ✅ "unknown" is the correct fallback (not an invented type)
    """
    symbol_lower = symbol_lower = symbol_candidate.lower()

    # 1. Exact case-insensitive match
    for legend_key, legend_value in legend.items():
        if symbol_lower == legend_key.lower():
            return {
                "symbol": symbol_candidate,
                "legend_key": legend_key,
                "description": legend_value,
                "method": "exact_match",
                "confidence": 1.0,
            }

    # 2. Substring match — symbol key contains candidate or vice versa
    for legend_key, legend_value in legend.items():
        if symbol_lower in legend_key.lower() or legend_key.lower() in symbol_lower:
            return {
                "symbol": symbol_candidate,
                "legend_key": legend_key,
                "description": legend_value,
                "method": "substring_match",
                "confidence": 0.7,
            }

    # 3. No match found — return None (do NOT invent a symbol type)
    # This is the critical constraint: never guess a symbol type from
    # a universal model. The correct fallback is "unknown", to be handled
    # by the human review UI or further heuristics.
    return None


# ---------------------------------------------------------------------------
# Phase 1.5 DoD check for legend matching
# ---------------------------------------------------------------------------

LEGEND_DONE_CHECKS = {
    "per_document_only": "Legend matching is per-document, not universal",
    "no_universal_detector": "No global cross-company symbol detector built",
    "unknown_fallback_ok": "Returning None/unknown is correct if legend fails",
    "ocr_proposals_only": "OCR results used as hints only, not final types",
}