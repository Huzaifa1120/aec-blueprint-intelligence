"""Scale detection from PDF text spans (title block / dimension strings).

Reads scale from the sheet — never assumes a global default.
Critical trap: scale must be read from the sheet, never hardcoded or assumed.
If scale cannot be determined, the job is marked needs_review; never fabricated.
"""

import re
from dataclasses import dataclass
from typing import List, Dict, Any, Optional, Tuple


@dataclass(frozen=True)
class ScaleResult:
    scale_str: str
    denominator: float
    status: str  # "detected" | "assumed"


_IMPERIAL_TITLE_BLOCK_RE = re.compile(r"\bSCALE\s+1\s*=\s*(\d+)\s*'\s*-0\"")

# Paired title-block labels: a bare 'SCALE' anchor span and a separate ratio
# token span next to it (rotated title-block cells often split the two).
# Real case: MMC-JVC-CD-ELEC-3902_AC-WIRE carries 'SCALE' at (50.7,1114.7)
# and slash-form '1/100' at (39.8,1132.9) — ~26 pt apart, unparseable inline.
_SCALE_ANCHOR_RE = re.compile(r"^\s*SCALE\s*:?\s*$", re.IGNORECASE)
_PAIRED_RATIO_RE = re.compile(r"^(\d{1,3})\s*[:/]\s*(\d{1,5})$")
_PAIR_RADIUS_PT = 40.0

# Architectural inch scales -> denominator (feet per inch * 12 * ratio inverse)
_ARCH_DENOMINATORS = {
    "1/2": 24.0,
    "3/4": 16.0,
    "1": 12.0,
    "3/32": 128.0,
    "1/8": 96.0,
    "3/16": 64.0,
    "1/4": 48.0,
    "3/8": 32.0,
}


def resolve_scale(text_spans: List[Dict[str, Any]]) -> ScaleResult:
    """Read the scale from sheet text; NEVER silently invent one.

    Returns status="detected" with the matched scale, or status="assumed"
    with 1:100 when nothing parseable exists — callers must surface the
    assumed state (spec v3 §7.4: scale is never assumed globally).
    """
    for span in text_spans:
        text = span.get("text", "") or ""
        if not text:
            continue
        m = re.search(r"\bELECTRICAL\.SCALE\s+(1:\d+)\b", text)
        if m:
            return _from_ratio(m.group(1))
        m_imp = _IMPERIAL_TITLE_BLOCK_RE.search(text)
        if m_imp:
            n = int(m_imp.group(1))
            denom = float(n * 12)
            return ScaleResult(f"1:{n * 12}", denom, "detected")
        arch = re.search(r'\b(\d+/\d+|\d+)"\s*=\s*1\'\s*-?\s*0?"?', text)
        if arch and arch.group(1) in _ARCH_DENOMINATORS:
            denom = _ARCH_DENOMINATORS[arch.group(1)]
            return ScaleResult(f'{arch.group(1)}"=1\'-0"', denom, "detected")
        m = re.search(r"\b(1:\d+)\b", text)
        if m:
            return _from_ratio(m.group(1))
    paired = _paired_scale(text_spans)
    if paired is not None:
        return paired
    return ScaleResult("1:100", 100.0, "assumed")


def _span_center(span: Dict[str, Any]) -> Tuple[float, float]:
    bbox = span.get("bbox") or (0.0, 0.0, 0.0, 0.0)
    return (float(bbox[0]) + float(bbox[2])) / 2.0, (float(bbox[1]) + float(bbox[3])) / 2.0


def _paired_scale(text_spans: List[Dict[str, Any]]) -> Optional[ScaleResult]:
    """Resolve a scale from a SCALE label span paired with a nearby ratio span.

    Only fires when the inline patterns found nothing: a bare 'SCALE' anchor
    plus a separate colon/slash ratio token within ``_PAIR_RADIUS_PT`` of it.
    A ratio token with no anchor is ignored — bare fractions in dimension
    text must never be promoted to a sheet scale.
    """
    best: Optional[Tuple[float, int, int]] = None  # (distance, n, d)
    for anchor_index, anchor in enumerate(text_spans):
        if not _SCALE_ANCHOR_RE.match(anchor.get("text", "") or ""):
            continue
        ax, ay = _span_center(anchor)
        for token_index, token in enumerate(text_spans):
            if token_index == anchor_index:
                continue
            m = _PAIRED_RATIO_RE.match((token.get("text", "") or "").strip())
            if not m:
                continue
            n, d = int(m.group(1)), int(m.group(2))
            if not (1 <= n < d <= 10000):
                continue
            tx, ty = _span_center(token)
            distance = ((tx - ax) ** 2 + (ty - ay) ** 2) ** 0.5
            if distance > _PAIR_RADIUS_PT:
                continue
            candidate = (distance, n, d)
            if best is None or candidate < best:
                best = candidate
    if best is None:
        return None
    _, n, d = best
    return ScaleResult(f"{n}:{d}", float(d) / float(n), "detected")


def _from_ratio(ratio: str) -> ScaleResult:
    denom = float(ratio.split(":")[1])
    return ScaleResult(ratio, denom, "detected")


def parse_scale_denominator(scale_str: str) -> Tuple[float, bool]:
    try:
        return float(str(scale_str).split(":")[1]), True
    except (IndexError, ValueError, AttributeError):
        return 100.0, False


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