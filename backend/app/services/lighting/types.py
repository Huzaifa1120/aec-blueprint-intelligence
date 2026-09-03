from typing import TypedDict, List, Tuple


class TextSpan(TypedDict):
    text: str
    x: float
    y: float
    size: float
    font: str


class DALILoop(TypedDict):
    panel: str
    part: str
    loop: str
    quantity: int
    source_x: float
    source_y: float
    line_cluster_id: int


class FixtureSymbol(TypedDict):
    centroid: Tuple[float, float]
    bbox: Tuple[float, float, float, float]
    symbol_type: str
    area: float
    path_signature: Tuple[str, ...]


class Marker(TypedDict):
    label: str
    position: Tuple[float, float]
    id: int


class FixtureInstance(TypedDict):
    centroid: Tuple[float, float]
    bbox: Tuple[float, float, float, float]
    symbol_type: str
    emergency_class: str
    nearest_marker_dist: float
    marker_id: int
    loop_id: str
    confidence: float


class LoopReconciliation(TypedDict):
    loop: str
    text_quantity: int
    spatial_count: int
    cb_count: int
    em_count: int
    emem_count: int
    normal_count: int
    delta: int
    confidence: float


class ReconciliationReport(TypedDict):
    part: str
    loops: List[LoopReconciliation]
    totals: dict
    confidence_summary: dict
    flags: List[str]


# Constants
EMERGENCY_CLASSES = ["CB", "EM", "EMEM", "NORMAL"]
LINE_CLUSTER_TOL = 4.0

# Empirically derived from Part-1 analysis
SYMBOL_SPECS = {
    "poly6_black": {
        "path_signature": ("l", "l", "l", "l", "l", "l"),
        "area_range": (80, 150),
        "color": (0.0, 0.0, 0.0),
        "width": 0.48,
    },
    "circ4_cyan": {
        "path_signature": ("c", "c", "c", "c"),
        "area_range": (80, 150),
        "color": (0.0, 1.0, 1.0),
        "width": 0.96,
    },
    "poly9_green": {
        "path_signature": ("l", "l", "l", "l", "l", "l", "l", "l", "l"),
        "area_range": (80, 150),
        "color": (0.0, 1.0, 0.0),
        "width": 0.24,
    },
}