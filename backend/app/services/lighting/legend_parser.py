"""V3: Legend Parser.

Parses the fixture schedule (legend) at the bottom of the page (Y ≈ 2900-3100).
The legend has symbol codes (R1, R2, C1, S1, W1, L1, EM1, etc.) at Y≈2970,
with their descriptions at Y≈3025 containing IP, wattage, dimensions, DALI driver info.
DITTO AS ABOVE markers indicate inheritance from the previous spec in the SAME SERIES.

Note: Description text is vertical (rotated), so spans have tall bboxes (y0≈3025, y1≈3175+).
Use TOP Y (y0) for matching, not center Y.

Layout: The legend is organized in vertical columns by series (R, C, S, W, L from right to left).
Within each column, codes go R7→R1, C5→C1, S3→S1, W3→W1, L2→L1 (descending numbers).
CB variants (R1CB, C1CB, etc.) are DITTO rows that inherit from their base code (R1, C1, etc.).
"""
import re
from collections import defaultdict
from dataclasses import dataclass
from typing import List, Optional, Dict, Any, Tuple

import pymupdf


# Legend region at bottom of page
LEGEND_Y_MIN = 2850.0
LEGEND_Y_MAX = 3100.0

# X range for the fixture legend (right side of sheet)
LEGEND_X_MIN = 1450.0
LEGEND_X_MAX = 2050.0

# Symbol code patterns: R1, R1CB, C1, C1CB, S1, S1CB, W1, W2, W3, L1, L2, EM1, EM2, EM3, EM4
SYMBOL_CODE_PATTERN = re.compile(r'^(R|C|S|W|L)\d+(CB)?$|^EM\d+$')

# Symbol Y position (top of symbol code)
SYMBOL_Y = 2975.0
SYMBOL_Y_TOL = 10.0

# Description Y position (TOP of vertical text block)
DESCRIPTION_Y = 3025.0
DESCRIPTION_Y_TOL = 10.0

# CB marker Y range
CB_Y_MIN = 2990.0
CB_Y_MAX = 3015.0

# IP rating pattern: IP44, IP65, IP20, IP-44, IP-65, etc.
IP_PATTERN = re.compile(r"\bIP[-\s]*(\d{2})\b", re.IGNORECASE)

# Wattage: numeric value followed by 'W' (e.g. "12W", "30W", "36W")
WATTAGE_PATTERN = re.compile(r"\b(\d{1,3})\s*W\b", re.IGNORECASE)

# Dimensions like "600x600", "1800x200", "150x150", "598X598mm"
DIMENSION_PATTERN = re.compile(r"\b(\d{2,4})\s*[xX×]\s*(\d{2,4})", re.IGNORECASE)

# Emergency conversion markers
DITTO_PATTERN = re.compile(r"DITTO\s+AS\s+ABOVE", re.IGNORECASE)
CONVERSION_PATTERN = re.compile(r"(\d+)%\s+TO\s+BE\s+EQUIPPED\s+WITH\s+CONVERSION\s+MODULE", re.IGNORECASE)
CENTRAL_BATTERY_PATTERN = re.compile(r"CONNECTED\s+TO\s+CENTRAL\s+BATTERY\s+PANEL", re.IGNORECASE)

# Driver keywords
DRIVER_KEYWORDS = {"DALI", "0-10V", "1-10V", "NON-DIM", "PHASE", "SWITCH", "ON/OFF"}

# Mount keywords
MOUNT_KEYWORDS = {
    "RECESSED", "SURFACE", "PENDANT", "WALL", "TRACK", "TRUNKING",
    "DOWN", "UP", "SUSPENDED", "GROUND", "POLE", "CEILING", "FALSE CEILING",
}

# Shape hints from description keywords
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
    "coffered": "panel",
    "water proof": "industrial",
    "explosion proof": "industrial",
    "rectangular": "panel",
    "wall lighting": "strip",
    "flex": "strip",
    "cell": "strip",
}


@dataclass
class FixtureSpec:
    code: str                       # e.g. "R1", "C1", "EM1"
    description: str                # Full concatenated description text
    wattage: Optional[int]          # e.g. 36
    dimensions: Optional[str]       # e.g. "600x600"
    ip_rating: Optional[str]        # e.g. "IP65"
    shape_hint: str                 # "panel" | "downlight" | "strip" | "exit" | "industrial" | "unknown"
    driver: Optional[str]           # e.g. "DALI"
    conversion_pct: Optional[float] # 0.0 - 1.0, fraction with emergency conversion
    has_emergency: bool             # True if spec has emergency (CB marker nearby or EM symbol)
    mount: Optional[str]            # e.g. "RECESSED", "SURFACE", "WALL"
    row_y: float                    # Y position of the symbol code

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
            "row_y": self.row_y,
        }


def _extract_legend_spans(page: pymupdf.Page) -> List[Dict[str, Any]]:
    """Extract all text spans in the legend region."""
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
                cx = (x0 + x1) / 2.0
                # Filter to legend region (use y0 for vertical text)
                if LEGEND_Y_MIN <= y0 <= LEGEND_Y_MAX and LEGEND_X_MIN <= cx <= LEGEND_X_MAX:
                    out.append({
                        "text": text,
                        "x0": x0,
                        "x1": x1,
                        "y0": y0,
                        "y1": y1,
                        "cx": cx,
                        "cy": (y0 + y1) / 2.0,
                        "size": span["size"],
                        "font": span["font"],
                    })
    return out


def _parse_symbol_code(code: str) -> Tuple[str, int, bool]:
    """Parse symbol code into (series, number, is_cb_variant).
    e.g. 'R1CB' -> ('R', 1, True), 'S3' -> ('S', 3, False), 'W2' -> ('W', 2, False)
    """
    # Extract series letter
    series = code[0]
    # Extract number
    num_match = re.search(r'(\d+)', code)
    number = int(num_match.group(1)) if num_match else 0
    # Check for CB variant
    is_cb = code.endswith('CB')
    return series, number, is_cb


def _find_symbol_anchors(spans: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Find symbol code anchors (R1, C1, S1, W1, L1, EM1, etc.) in the legend."""
    anchors = []
    for s in spans:
        if SYMBOL_CODE_PATTERN.match(s["text"]):
            # Symbol codes are at Y ≈ 2975 (larger font ~4.1pt)
            if abs(s["y0"] - SYMBOL_Y) <= SYMBOL_Y_TOL and s["size"] >= 3.5:
                series, number, is_cb = _parse_symbol_code(s["text"])
                s["series"] = series
                s["number"] = number
                s["is_cb"] = is_cb
                anchors.append(s)
    return anchors


def _find_cb_markers(spans: List[Dict[str, Any]]) -> Dict[float, str]:
    """Find CB/EX markers near symbol positions. Returns dict of symbol_x -> marker_type."""
    cb_map = {}
    for s in spans:
        if s["text"] in {"CB", "EX"} and CB_Y_MIN <= s["y0"] <= CB_Y_MAX:
            cb_map[round(s["cx"], 1)] = s["text"]
    return cb_map


def _find_descriptions(spans: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Find description spans at Y ≈ 3025 (use TOP Y for vertical text)."""
    descs = []
    for s in spans:
        # Match on y0 (top of vertical text block)
        if abs(s["y0"] - DESCRIPTION_Y) <= DESCRIPTION_Y_TOL and s["size"] >= 3.0:
            descs.append(s)
    descs.sort(key=lambda d: d["cx"])
    return descs


def _group_anchors_by_series(anchors: List[Dict[str, Any]]) -> Dict[str, List[Dict[str, Any]]]:
    """Group anchors by series (R, C, S, W, L) and sort each series by logical order.
    
    Logical order: descending number (R7, R6, R5, R4, R3, R2, R1) with CB variants
    grouped with their base code. For W series: W3, W2, W1. For L: L2, L1.
    """
    by_series = defaultdict(list)
    for a in anchors:
        by_series[a["series"]].append(a)
    
    # Sort each series: primary by number DESC, secondary by is_cb (base before CB)
    for series, items in by_series.items():
        def sort_key(item):
            # Base codes (is_cb=False) come before CB variants of same number
            return (-item["number"], 1 if item["is_cb"] else 0)
        items.sort(key=sort_key)
    
    return by_series


def _compute_2d_bounds(anchors: List[Dict[str, Any]]) -> Dict[str, Dict[str, Tuple[float, float]]]:
    """Compute 2D midpoint bounds for each anchor.
    
    Returns dict mapping code -> {"x": (left, right), "y": (upper, lower)}.
    """
    # Collect all unique X coordinates
    all_x = sorted([a['cx'] for a in anchors])
    # Collect all unique Y coordinates (using y0 rounded to 1 decimal)
    all_y = sorted(list(set(round(a['y0'], 1) for a in anchors)))
    
    bounds = {}
    for a in anchors:
        code = a['text']
        x = a['cx']
        y = round(a['y0'], 1)
        i_x = all_x.index(x)
        i_y = all_y.index(y)
        left = (all_x[i_x-1] + x) / 2 if i_x > 0 else x - 25
        right = (x + all_x[i_x+1]) / 2 if i_x < len(all_x) - 1 else x + 25
        upper = (all_y[i_y-1] + y) / 2 if i_y > 0 else y - 5
        lower = (y + all_y[i_y+1]) / 2 if i_y < len(all_y) - 1 else y + 5
        bounds[code] = {"x": (left, right), "y": (upper, lower)}
    return bounds


def _collect_description_block(
    symbol_x: float,
    symbol_series: str,
    symbol_number: int,
    next_symbol_x: Optional[float],
    descriptions: List[Dict[str, Any]],
    all_anchors: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    """Collect ALL description spans belonging to a symbol's 2D cell.
    
    Uses mathematical midpoints between adjacent symbol anchors in BOTH
    X and Y dimensions to define strict cell boundaries.
    """
    # Compute 2D bounds for all anchors
    bounds_2d = _compute_2d_bounds(all_anchors)
    
    # Find the anchor for this symbol to get its bounds
    anchor = next((a for a in all_anchors if a['text'] == f"{symbol_series}{symbol_number}") or 
                  (a for a in all_anchors if a['text'] == f"{symbol_series}{symbol_number}CB"), None)
    if not anchor:
        # Fallback to old logic if anchor not found
        left_bound = symbol_x - 40
        right_bound = next_symbol_x if next_symbol_x is not None else LEGEND_X_MAX + 50
    else:
        bounds = bounds_2d.get(anchor['text'], {"x": (symbol_x - 40, symbol_x + 40), "y": (2850.0, 3100.0)})
        left_bound, right_bound = bounds["x"]
    
    block = []
    for d in descriptions:
        if left_bound <= d["cx"] <= right_bound:
            block.append(d)
    
    # Sort by reading order: top-to-bottom (y0 ascending for vertical text)
    block.sort(key=lambda d: d["y0"])
    return block


def _extract_attributes(text: str) -> Dict[str, Any]:
    """Extract IP, wattage, dimensions, driver, mount from description text."""
    attrs = {
        "ip_rating": None,
        "wattage": None,
        "dimensions": None,
        "driver": None,
        "mount": None,
        "conversion_pct": None,
        "is_ditto": False,
    }

    # IP rating
    ip_match = IP_PATTERN.search(text)
    if ip_match:
        attrs["ip_rating"] = f"IP{ip_match.group(1)}"

    # Wattage
    watt_match = WATTAGE_PATTERN.search(text)
    if watt_match:
        attrs["wattage"] = int(watt_match.group(1))

    # Dimensions
    dim_match = DIMENSION_PATTERN.search(text)
    if dim_match:
        attrs["dimensions"] = f"{dim_match.group(1)}x{dim_match.group(2)}"

    # Driver
    for kw in DRIVER_KEYWORDS:
        if kw in text.upper():
            attrs["driver"] = kw
            break

    # Mount
    upper = text.upper()
    for kw in MOUNT_KEYWORDS:
        if kw in upper:
            attrs["mount"] = kw
            break

    # DITTO AS ABOVE
    if DITTO_PATTERN.search(text):
        attrs["is_ditto"] = True
        # Extract conversion percentage
        conv_match = CONVERSION_PATTERN.search(text)
        if conv_match:
            attrs["conversion_pct"] = float(conv_match.group(1)) / 100.0

    return attrs


def _infer_shape_hint(text: str) -> str:
    """Map description to a shape_hint."""
    low = text.lower()
    for kw, hint in SHAPE_HINTS_BY_KEYWORD.items():
        if kw in low:
            return hint
    return "unknown"


def _has_emergency(symbol_code: str, symbol_x: float, cb_map: Dict[float, str]) -> bool:
    """Determine if a fixture spec has emergency capability."""
    # EM symbols are emergency by definition
    if symbol_code.startswith("EM"):
        return True
    # Check for CB/EX marker at same X
    for cb_x, marker in cb_map.items():
        if abs(cb_x - symbol_x) <= 30:
            return True
    return False


def parse_legend(page: pymupdf.Page) -> List[FixtureSpec]:
    """Parse the fixture schedule (legend) at bottom of page (Y ≈ 2900-3100).
    
    New logic:
    1. Group symbol anchors by series (R, C, S, W, L)
    2. Sort each series in logical order (descending number, base before CB)
    3. For each series, process in logical order maintaining prev_attrs per series
    4. Collect ALL description spans in each symbol's 2D cell (midpoint-bounded)
    5. Concatenate description lines in reading order (top-to-bottom)
    """
    spans = _extract_legend_spans(page)
    anchors = _find_symbol_anchors(spans)
    cb_map = _find_cb_markers(spans)
    descriptions = _find_descriptions(spans)
    
    # Group by series and sort logically
    by_series = _group_anchors_by_series(anchors)
    
    # Pre-compute 2D bounds for all anchors
    bounds_2d = _compute_2d_bounds(anchors)
    
    specs: List[FixtureSpec] = []
    # prev_attrs per series
    prev_attrs_by_series: Dict[str, Optional[Dict[str, Any]]] = {s: None for s in by_series.keys()}
    
    for series, series_anchors in by_series.items():
        for idx, anchor in enumerate(series_anchors):
            code = anchor["text"]
            symbol_x = anchor["cx"]
            symbol_y = anchor["y0"]
            
            # Get 2D bounds for THIS specific anchor (including CB variants)
            bounds = bounds_2d.get(code, {"x": (symbol_x - 40, symbol_x + 40), "y": (2850.0, 3100.0)})
            left_bound, right_bound = bounds["x"]
            
            # Collect ALL description spans in this symbol's 2D cell
            block = []
            for d in descriptions:
                if left_bound <= d["cx"] <= right_bound:
                    block.append(d)
            
            # Sort by reading order: top-to-bottom (y0 ascending for vertical text)
            block.sort(key=lambda d: d["y0"])
            desc_block = block
            
            # Concatenate description texts in reading order (top-to-bottom)
            if desc_block:
                desc_texts = [d["text"] for d in desc_block]
                full_description = " | ".join(desc_texts)
                # Extract attributes from concatenated text
                combined_text = " ".join(desc_texts)
                attrs = _extract_attributes(combined_text)
            else:
                full_description = ""
                attrs = {"ip_rating": None, "wattage": None, "dimensions": None,
                         "driver": None, "mount": None, "conversion_pct": None, "is_ditto": False}
            
            # Handle DITTO AS ABOVE - inherit from previous spec in SAME SERIES
            if attrs["is_ditto"] and prev_attrs_by_series[series] is not None:
                parent_attrs = prev_attrs_by_series[series]
                # Inherit IP, wattage, dimensions, driver, mount, shape from parent
                for key in ["ip_rating", "wattage", "dimensions", "driver", "mount"]:
                    if attrs[key] is None:
                        attrs[key] = parent_attrs.get(key)
                # Keep conversion_pct from DITTO line
                description = full_description
            else:
                description = full_description
                # Update prev_attrs for this series (only for non-DITTO base codes)
                if not attrs["is_ditto"]:
                    prev_attrs_by_series[series] = attrs.copy()
            
            # Shape hint from concatenated description
            shape_hint = _infer_shape_hint(description)
            
            # Emergency
            has_emergency = _has_emergency(code, symbol_x, cb_map)
            
            spec = FixtureSpec(
                code=code,
                description=description,
                wattage=attrs["wattage"],
                dimensions=attrs["dimensions"],
                ip_rating=attrs["ip_rating"],
                shape_hint=shape_hint,
                driver=attrs["driver"],
                conversion_pct=attrs["conversion_pct"],
                has_emergency=has_emergency,
                mount=attrs["mount"],
                row_y=symbol_y,
            )
            specs.append(spec)
    
    # Sort final specs back to original X-order for consistent output
    specs.sort(key=lambda s: next((a["cx"] for a in anchors if a["text"] == s.code), 0))
    
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
    from collections import Counter
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
    }