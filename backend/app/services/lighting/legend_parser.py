"""V3: Legend Parser.

Parses the fixture schedule (legend) at the bottom of the page (Y ≈ 2900-3100).
The legend has symbol codes (R1, R2, C1, S1, W1, L1, EM1, etc.) at Y≈2970,
with their descriptions at Y≈3025 containing IP, wattage, dimensions, DALI driver info.
DITTO AS ABOVE markers indicate inheritance from the previous spec.

Note: Description text is vertical (rotated), so spans have tall bboxes (y0≈3025, y1≈3175+).
Use TOP Y (y0) for matching, not center Y.
"""
import re
from collections import Counter
from dataclasses import dataclass
from typing import List, Optional, Dict, Any

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
    description: str                # Full description text
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


# ---------- Helpers ----------


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


def _find_symbol_anchors(spans: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Find symbol code anchors (R1, C1, S1, W1, L1, EM1, etc.) in the legend."""
    anchors = []
    for s in spans:
        if SYMBOL_CODE_PATTERN.match(s["text"]):
            # Symbol codes are at Y ≈ 2975 (larger font ~4.1pt)
            if abs(s["y0"] - SYMBOL_Y) <= SYMBOL_Y_TOL and s["size"] >= 3.5:
                anchors.append(s)
    # Sort by X position (left to right)
    anchors.sort(key=lambda a: a["cx"])
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


def _match_description_to_symbol(symbol_x: float, descriptions: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    """Match a symbol to its description by closest X position."""
    if not descriptions:
        return None
    best = min(descriptions, key=lambda d: abs(d["cx"] - symbol_x))
    if abs(best["cx"] - symbol_x) <= 50:  # Within 50pt horizontally
        return best
    return None


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


# ---------- Main API ----------


def parse_legend(page: pymupdf.Page) -> List[FixtureSpec]:
    """Parse the fixture schedule (legend) at bottom of page (Y ≈ 2900-3100)."""
    spans = _extract_legend_spans(page)
    anchors = _find_symbol_anchors(spans)
    cb_map = _find_cb_markers(spans)
    descriptions = _find_descriptions(spans)

    specs: List[FixtureSpec] = []
    prev_attrs: Optional[Dict[str, Any]] = None

    for anchor in anchors:
        code = anchor["text"]
        symbol_x = anchor["cx"]
        symbol_y = anchor["y0"]

        # Match to description
        desc_span = _match_description_to_symbol(symbol_x, descriptions)
        if desc_span:
            desc_text = desc_span["text"]
            attrs = _extract_attributes(desc_text)
        else:
            desc_text = ""
            attrs = {"ip_rating": None, "wattage": None, "dimensions": None,
                     "driver": None, "mount": None, "conversion_pct": None, "is_ditto": False}

        # Handle DITTO AS ABOVE - inherit from previous spec
        if attrs["is_ditto"] and prev_attrs is not None:
            # Inherit IP, wattage, dimensions, driver, mount, shape from previous
            for key in ["ip_rating", "wattage", "dimensions", "driver", "mount"]:
                if attrs[key] is None:
                    attrs[key] = prev_attrs.get(key)
            # Keep conversion_pct from DITTO line (e.g., 25% conversion)
            description = desc_text
        else:
            description = desc_text
            prev_attrs = attrs.copy()

        # Shape hint
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
    }