"""V3: Legend Parser.

Parses the fixture schedule (legend, Y < 1000 region) of a lighting layout PDF
into a list of FixtureSpec records. The legend is a multi-column schedule:

    +-------+-------+-------+-------+-------+-------+-------+-------+
    |   A   |   B   |   C   |   D   |   E   |   F   |   G   |   H   | ...
    +-------+-------+-------+-------+-------+-------+-------+-------+

Each column has a stack of fixture type rows. A row is anchored by a
"02-XXXX" fixture-type code (small ArialMT, ~3.5pt). Surrounding attributes
(wattage, dimensions, IP, driver, mount) are grouped by Y-cluster around the
anchor.
"""
import re
from collections import Counter
from dataclasses import dataclass
from typing import List, Optional, Tuple, Dict, Any

import pymupdf


# Y bound for the legend region (everything above the floor plan starts ~Y=600,
# but legend can extend further; 1000 is a safe upper bound for the schedule).
LEGEND_Y_MAX = 1000.0

# Anchor pattern: fixture type codes are formatted 02-XXXX.
FIXTURE_CODE_PATTERN = re.compile(r"^\d{2}-\d{4}$")

# Column letter labels sit at the top of the legend (sz ~18 ArialMT).
COLUMN_LETTER_PATTERN = re.compile(r"^[A-Z]$")

# IP rating pattern: IP44, IP65, IP20, etc.
IP_PATTERN = re.compile(r"\bIP\s*(\d{2})\b", re.IGNORECASE)

# Wattage: numeric value followed by 'W' (e.g. "12W", "30W")
WATTAGE_PATTERN = re.compile(r"\b(\d{1,3})\s*W\b", re.IGNORECASE)

# Dimensions like "600x600", "1800x200", "150x150"
DIMENSION_PATTERN = re.compile(r"\b(\d{2,4})\s*[xX×]\s*(\d{2,4})\b")

# Emergency class markers in the legend (CB = circuit breaker / standard,
# EM = emergency, EMEM = combined emergency)
EMERGENCY_LABELS = {"CB", "EM", "EMEM"}

# Driver / mount hints — looked for as keywords in nearby text
DRIVER_KEYWORDS = {"DALI", "0-10V", "1-10V", "NON-DIM", "PHASE", "SWITCH"}
MOUNT_KEYWORDS = {
    "RECESSED", "SURFACE", "PENDANT", "WALL", "TRACK", "TRUNKING",
    "DOWN", "UP", "SUSPENDED", "GROUND", "POLE",
}

# Shape hints — assigned by the shape drawn in the legend (circle/hexagon/etc.)
# Since the legend mostly uses text icons, we use key clues from the description.
SHAPE_HINTS_BY_KEYWORD = {
    "panel": "panel",
    "downlight": "downlight",
    "down light": "downlight",
    "wall washer": "strip",
    "linear": "strip",
    "strip": "strip",
    "exit": "exit",
    "exit sign": "exit",
    "industrial": "industrial",
    "highbay": "industrial",
    "high bay": "industrial",
    "spot": "downlight",
    "spotlight": "downlight",
    "track": "strip",
    "trunking": "strip",
    "coffer": "panel",
    "cofferred": "panel",
}


@dataclass
class FixtureSpec:
    code: str                       # e.g. "02-0318"
    description: str                # e.g. "CRYP BANK" (may be empty)
    wattage: Optional[int]          # e.g. 30
    dimensions: Optional[str]       # e.g. "600x600"
    ip_rating: Optional[str]        # e.g. "IP65"
    shape_hint: str                 # "panel" | "downlight" | "strip" | "exit" | "industrial" | "unknown"
    driver: Optional[str]           # e.g. "DALI"
    conversion_pct: Optional[float] # 0.0 - 1.0, fraction of fixtures with emergency
    has_emergency: bool             # True if spec supports emergency mode
    mount: Optional[str]            # e.g. "RECESSED", "SURFACE", "WALL"
    column: str                     # "A" | "B" | ... source column letter
    row_y: float                    # Y position of the anchor code

    def to_dict(self) -> Dict[str, Any]:
        return {
            "code": self.code,
            "description": self.description,
            "wattage": self.wattage,
            "dimensions": self.dimensions,
            "ip_rating": self.ip_rating,
            "shape_hint": self.shape_hint,
            "driver": self.driver,
            "conversion_pct": self.conversion_pct,
            "has_emergency": self.has_emergency,
            "mount": self.mount,
            "column": self.column,
            "row_y": self.row_y,
        }


# ---------- Helpers ----------


def _extract_spans(page: pymupdf.Page) -> List[Dict[str, Any]]:
    """Return a flat list of all text spans with bbox + formatting."""
    out: List[Dict[str, Any]] = []
    blocks = page.get_text("dict")["blocks"]
    for b in blocks:
        if "lines" not in b:
            continue
        for line in b["lines"]:
            for span in line["spans"]:
                text = span["text"].strip()
                if not text:
                    continue
                x0, y0, x1, y1 = span["bbox"]
                out.append({
                    "text": text,
                    "x0": x0,
                    "x1": x1,
                    "y0": y0,
                    "y1": y1,
                    "cx": (x0 + x1) / 2.0,
                    "cy": (y0 + y1) / 2.0,
                    "size": span["size"],
                    "font": span["font"],
                })
    return out


def _find_column_letters(spans: List[Dict[str, Any]]) -> List[Tuple[str, float]]:
    """Identify the top column letter labels and their x positions."""
    letters: List[Tuple[str, float]] = []
    for s in spans:
        if s["cy"] > 150:  # column headers live near the top
            continue
        if s["size"] < 10:  # bold/18pt is the header size
            continue
        if COLUMN_LETTER_PATTERN.match(s["text"]):
            letters.append((s["text"], s["cx"]))
    letters.sort(key=lambda t: t[1])
    return letters


def _column_for_x(x: float, letters: List[Tuple[str, float]]) -> str:
    """Return the column letter whose center is closest to x, but only if within range."""
    if not letters:
        return "?"
    best_letter, best_dist = letters[0], float("inf")
    for letter, lx in letters:
        dist = abs(x - lx)
        if dist < best_dist:
            best_letter, best_dist = letter, dist
    if best_dist > 200:  # too far away from any column header
        return "?"
    return best_letter


def _infer_shape_hint(text: str) -> str:
    """Map description / nearby text to a shape_hint."""
    low = text.lower()
    for kw, hint in SHAPE_HINTS_BY_KEYWORD.items():
        if kw in low:
            return hint
    return "unknown"


def _build_spec_from_anchor(
    code: str, anchor: Dict[str, Any], nearby: List[Dict[str, Any]],
    column: str,
) -> FixtureSpec:
    """Extract a FixtureSpec from the anchor span and surrounding nearby spans."""
    # Concatenate nearby text for keyword search
    nearby_text = " ".join(s["text"] for s in nearby)

    # IP rating
    ip_match = IP_PATTERN.search(nearby_text)
    ip_rating = f"IP{ip_match.group(1)}" if ip_match else None

    # Wattage
    watt_match = WATTAGE_PATTERN.search(nearby_text)
    wattage = int(watt_match.group(1)) if watt_match else None

    # Dimensions
    dim_match = DIMENSION_PATTERN.search(nearby_text)
    dimensions = f"{dim_match.group(1)}x{dim_match.group(2)}" if dim_match else None

    # Emergency presence
    has_emergency = any(s["text"] in EMERGENCY_LABELS for s in nearby)
    emergency_count = sum(1 for s in nearby if s["text"] in EMERGENCY_LABELS)
    total_markers = emergency_count
    if total_markers > 0:
        # Fraction of nearby labels that are emergency
        em_count = sum(1 for s in nearby if s["text"] in {"EM", "EMEM"})
        conversion_pct = min(1.0, em_count / total_markers)
    else:
        conversion_pct = None

    # Driver
    driver = None
    for kw in DRIVER_KEYWORDS:
        if kw in nearby_text.upper():
            driver = kw
            break

    # Mount
    mount = None
    upper_text = nearby_text.upper()
    for kw in MOUNT_KEYWORDS:
        if kw in upper_text:
            mount = kw
            break

    # Description: pick the most descriptive nearby label (ArialMT 3.5pt, longer text)
    description_candidates = [
        s["text"] for s in nearby
        if s["text"] not in EMERGENCY_LABELS
        and not FIXTURE_CODE_PATTERN.match(s["text"])
        and not WATTAGE_PATTERN.match(s["text"])
        and not re.fullmatch(r"\d{2,4}[xX×]\d{2,4}", s["text"])
        and not re.fullmatch(r"\d+", s["text"])
        and s["text"] not in {"WC", "E/S", "CH.", "DN", "UP", "GR"}
    ]
    description = max(description_candidates, key=len) if description_candidates else ""

    # Shape hint — combine anchor & description heuristics
    shape_hint = _infer_shape_hint(description or nearby_text)

    return FixtureSpec(
        code=code,
        description=description,
        wattage=wattage,
        dimensions=dimensions,
        ip_rating=ip_rating,
        shape_hint=shape_hint,
        driver=driver,
        conversion_pct=conversion_pct,
        has_emergency=has_emergency,
        mount=mount,
        column=column,
        row_y=anchor["y0"],
    )


def parse_legend(page: pymupdf.Page) -> List[FixtureSpec]:
    """Parse the fixture schedule (legend) of a lighting layout page.

    Strategy:
      1. Extract all text spans
      2. Identify column header letters (top of legend)
      3. Find fixture-type anchors (02-XXXX) in legend region
      4. Group nearby spans around each anchor (by Y, then X)
      5. Build a FixtureSpec per anchor
    """
    spans = _extract_spans(page)
    letters = _find_column_letters(spans)

    # Find anchors in legend region
    anchors = [
        s for s in spans
        if FIXTURE_CODE_PATTERN.match(s["text"]) and s["y0"] < LEGEND_Y_MAX
    ]

    specs: List[FixtureSpec] = []
    seen_codes: set = set()

    for anchor in anchors:
        code = anchor["text"]
        if code in seen_codes:
            continue  # dedupe
        seen_codes.add(code)

        # Collect nearby spans: within Y +/- 80pt and X +/- 200pt of anchor.
        nearby = [
            s for s in spans
            if abs(s["y0"] - anchor["y0"]) <= 80
            and abs(s["cx"] - anchor["cx"]) <= 200
            and s is not anchor
        ]

        column = _column_for_x(anchor["cx"], letters)
        spec = _build_spec_from_anchor(code, anchor, nearby, column)
        specs.append(spec)

    # Sort: column letter order, then by Y
    specs.sort(key=lambda s: (s.column, s.row_y))
    return specs


def query_specs(
    specs: List[FixtureSpec],
    required_ip: Optional[str] = None,
    preferred_shape: Optional[str] = None,
    has_emergency: Optional[bool] = None,
) -> List[FixtureSpec]:
    """Filter FixtureSpecs by IP, shape, and emergency requirements."""
    out: List[FixtureSpec] = []
    for s in specs:
        if required_ip is not None and s.ip_rating != required_ip:
            continue
        if preferred_shape is not None:
            if preferred_shape.lower() not in s.shape_hint.lower() and s.shape_hint != preferred_shape:
                continue
        if has_emergency is not None and s.has_emergency != has_emergency:
            continue
        out.append(s)
    return out


def get_legend_stats(specs: List[FixtureSpec]) -> Dict[str, Any]:
    """Return summary statistics for a parsed legend."""
    shape_counts = Counter(s.shape_hint for s in specs)
    ip_counts = Counter(s.ip_rating or "unknown" for s in specs)
    em_counts = Counter(s.has_emergency for s in specs)
    wattages = [s.wattage for s in specs if s.wattage is not None]
    return {
        "total": len(specs),
        "by_shape": dict(shape_counts),
        "by_ip": dict(ip_counts),
        "by_emergency": dict(em_counts),
        "wattage_range": (min(wattages), max(wattages)) if wattages else None,
        "by_column": dict(Counter(s.column for s in specs)),
    }
