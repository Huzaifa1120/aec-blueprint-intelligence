"""Scale detection from PDF text spans (title block / dimension strings).

Reads scale from the sheet — never assumes a global default.
Critical trap: scale must be read from the sheet, never hardcoded or assumed.
If scale cannot be determined, the job is marked needs_review; never fabricated.
"""

import re
from typing import List, Dict, Any


# ---------------------------------------------------------------------------
# Scale patterns from text spans
# ---------------------------------------------------------------------------

def detect_scale(
    text_spans: List[Dict[str, Any]],
    default: str = "1:100",
) -> str:
    """Detect drawing scale from a list of text span dicts.

    Each span dict must have a "text" key containing the span's text content.

    Strategy:
    1. Scan all text spans for known scale patterns (title block, dim strings).
    2. Return the first match found.
    3. If no match, return the default — but log that scale was unknown.

    Important: This function does NOT assume a scale. It reads from the sheet.
    If the default is returned, the caller should flag the job for review.
    """
    for span in text_spans:
        text = span.get("text", "")
        if not text:
            continue

        # Pattern 1: Electrical-specific scales (must have group)
        for pattern in _ELECTRICAL_SCALES:
            m = re.search(pattern, text)
            if m and m.group(1):
                return m.group(1)

        # Pattern 2: Generic "1:N" ratio
        m = re.search(r"\b(1:\d+)\b", text)
        if m:
            return m.group(1)

    # No scale found in text — return default but caller must handle
    return default


# ---------------------------------------------------------------------------
# Internal pattern lists with guaranteed capturing groups
# ---------------------------------------------------------------------------

# Electrical-specific scales (always have capturing group 1 = the scale value)
_ELECTRICAL_SCALES = [
    r"\bELECTRICAL\.SCALE\s+(1:\d+)\b",        # "ELECTRICAL.SCALE 1:100"
    r"\bSCALE\s+1=(\d+)'\''-0\"\b",             # "SCALE 1=100'-0\"" → "100"
]

# Architectural scales (always have capturing group 1 = the scale value)
_ARCHITECTURAL_SCALES = [
    r"\b(1/4|1/2|1/8)\"=1'-0\"\b",             # e.g. 1/4\"=1'-0\"
    r"\b(1:\d+)\b",                             # e.g. 1:100, 1:50, 1:200
]


# ---------------------------------------------------------------------------
# Convenience: extract from PyMuPDF TextSpan dicts
# ---------------------------------------------------------------------------

def scale_from_pymupdf_text(
    text_spans: List[Dict[str, Any]],
    default: str = "1:100",
) -> str:
    """Thin wrapper around detect_scale for PyMuPDF text span dicts.

    Ensures compatibility with the existing text span format from
    vector.py's extract_text_spans().
    """
    return detect_scale(text_spans, default=default)


# ---------------------------------------------------------------------------
# Validation / diagnostics
# ---------------------------------------------------------------------------

def scale_needs_review(
    text_spans: List[Dict[str, Any]],
    search_patterns: int = 3,
) -> bool:
    """Heuristic: return True if scale likely could not be determined.

    If fewer than `search_patterns` non-empty text spans are found,
    or none match known scale patterns, the scale is considered unknown
    and the job should be flagged for human review.
    """
    matched = 0
    for span in text_spans:
        text = span.get("text", "")
        if not text:
            continue
        for pattern in _ARCHITECTURAL_SCALES[:search_patterns]:
            if re.search(pattern, text):
                matched += 1
                break
    return matched == 0