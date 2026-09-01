from dataclasses import dataclass
from typing import List, Tuple, Literal, Optional
import pymupdf


@dataclass
class DenoisedSymbol:
    id: int
    centroid: Tuple[float, float]
    bbox: Tuple[float, float, float, float]
    shape: Literal["circle", "hexagon", "nonagon"]
    area: float
    layer: str
    path_signature: Tuple[str, ...]
    has_marker: bool = False
    marker_label: Optional[str] = None
    assigned_room: Optional[str] = None
    loop: Optional[str] = None


TARGET_LAYER = "DALI CONTROL"
AREA_WINDOWS = {
    "circle": (45.0, 55.0),
    "hexagon": (60.0, 75.0),
    "nonagon": (155.0, 185.0),
}
PLAN_Y_MIN = 600.0

VALID_SIGNATURES = {
    ("c", "c", "c", "c"): "circle",
    ("l", "l", "l", "l", "l", "l"): "hexagon",
    ("l", "l", "l", "l", "l", "l", "l", "l", "l"): "nonagon",
}


def extract_denoised_symbols(page: pymupdf.Page) -> List[DenoisedSymbol]:
    symbols: List[DenoisedSymbol] = []
    symbol_id = 0
    
    for d in page.get_drawings():
        if d.get("layer") != TARGET_LAYER:
            continue
        
        items = d.get("items", [])
        rect = d.get("rect")
        if not items or not rect:
            continue
        
        cmds = tuple(item[0] for item in items)
        shape = VALID_SIGNATURES.get(cmds)
        if not shape:
            continue
        
        w = rect.x1 - rect.x0
        h = rect.y1 - rect.y0
        area = w * h
        
        lo, hi = AREA_WINDOWS[shape]
        if not (lo <= area <= hi):
            continue
        
        cy = (rect.y0 + rect.y1) / 2
        if cy <= PLAN_Y_MIN:
            continue
        
        color = d.get("color")
        width = d.get("width")
        if not (color and all(c < 0.1 for c in color)):
            continue
        if width is not None and abs(width) >= 0.01:
            continue
        
        cx = (rect.x0 + rect.x1) / 2
        cy = (rect.y0 + rect.y1) / 2
        
        symbols.append(DenoisedSymbol(
            id=symbol_id,
            centroid=(cx, cy),
            bbox=(rect.x0, rect.y0, rect.x1, rect.y1),
            shape=shape,
            area=area,
            layer=d.get("layer", TARGET_LAYER),
            path_signature=cmds,
        ))
        symbol_id += 1
    
    return symbols


def get_symbol_stats(symbols: List[DenoisedSymbol]) -> dict:
    from collections import Counter
    shape_counts = Counter(s.shape for s in symbols)
    return {
        "total": len(symbols),
        "by_shape": dict(shape_counts),
        "area_ranges": {
            shape: (min(s.area for s in symbols if s.shape == shape),
                    max(s.area for s in symbols if s.shape == shape))
            for shape in shape_counts
        }
    }