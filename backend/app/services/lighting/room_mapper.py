from dataclasses import dataclass
from typing import List, Tuple, Dict, Any, Optional
from collections import defaultdict
import pymupdf
import math
import re


@dataclass
class RoomPolygon:
    room_id: str
    room_type: str
    polygon: List[Tuple[float, float]]
    centroid: Tuple[float, float]
    rules: Dict[str, Any]
    code_positions: List[Tuple[float, float]]


ROOM_RULES = {
    "WC": {
        "required_ip": ["IP65", "IP66"],
        "preferred_shape": "circle",
        "emergency_pct": 1.0,
        "weight": 3.0,
        "description": "Water Closet / Toilet"
    },
    "E/S": {
        "required_ip": ["IP44", "IP65"],
        "preferred_shape": "hexagon",
        "emergency_pct": 0.5,
        "weight": 2.0,
        "description": "Electrical / Store"
    },
    "CH.": {
        "required_ip": ["IP65"],
        "preferred_shape": "hexagon",
        "emergency_pct": 0.3,
        "weight": 2.0,
        "description": "Chiller Room"
    },
    "DN": {
        "required_ip": ["IP44"],
        "preferred_shape": "nonagon",
        "emergency_pct": 0.8,
        "weight": 2.0,
        "description": "Corridor / Down"
    },
    "UP": {
        "required_ip": ["IP44"],
        "preferred_shape": "nonagon",
        "emergency_pct": 0.8,
        "weight": 1.5,
        "description": "Stair / Up"
    },
    "GR": {
        "required_ip": ["IP20", "IP40"],
        "preferred_shape": "hexagon",
        "emergency_pct": 0.5,
        "weight": 1.0,
        "description": "Grid / General Area"
    },
    "DEFAULT": {
        "required_ip": ["IP20", "IP40"],
        "preferred_shape": "hexagon",
        "emergency_pct": 0.5,
        "weight": 1.0,
        "description": "Default / Patient Room / Office"
    },
}


SPECIAL_CODES = {"WC", "E/S", "CH.", "DN", "UP", "GR"}
ALPHANUMERIC_PATTERN = re.compile(r'^\d{1,2}[A-Z]$')
KNOWN_ROOM_PREFIXES = set(str(i) for i in range(1, 32))

# False positive alphanumeric codes to exclude
BLACKLIST_CODES = {"2F", "E2"}  # "2nd Floor", "E2" (electrical)


def is_valid_room_code(text: str) -> bool:
    text = text.strip()
    if text in SPECIAL_CODES:
        return True
    if ALPHANUMERIC_PATTERN.match(text):
        if text in BLACKLIST_CODES:
            return False
        prefix = text[:-1]
        return prefix in KNOWN_ROOM_PREFIXES
    return False


def extract_room_codes(page: pymupdf.Page) -> List[Dict[str, Any]]:
    blocks = page.get_text('dict')['blocks']
    codes = []
    code_idx = 0
    
    for b in blocks:
        if 'lines' not in b:
            continue
        for line in b['lines']:
            for s in line['spans']:
                text = s['text'].strip()
                if not text:
                    continue
                
                if is_valid_room_code(text):
                    codes.append({
                        "code": text,
                        "x": s['bbox'][0],
                        "y": s['bbox'][1],
                        "idx": code_idx
                    })
                    code_idx += 1
    
    return codes


def cluster_positions(points: List[Tuple[float, float]], eps: float = 150.0) -> List[List[Tuple[float, float]]]:
    if not points:
        return []
    
    clusters = []
    used = set()
    
    for i, p1 in enumerate(points):
        if i in used:
            continue
        
        cluster = [p1]
        used.add(i)
        
        for j, p2 in enumerate(points):
            if j in used:
                continue
            dist = math.hypot(p2[0] - p1[0], p2[1] - p1[1])
            if dist <= eps:
                cluster.append(p2)
                used.add(j)
        
        clusters.append(cluster)
    
    return clusters


def convex_hull(points: List[Tuple[float, float]]) -> List[Tuple[float, float]]:
    if len(points) <= 1:
        return points
    
    def cross(o, a, b):
        return (a[0] - o[0]) * (b[1] - o[1]) - (a[1] - o[1]) * (b[0] - o[0])
    
    points = sorted(set(points))
    if len(points) <= 1:
        return points
    
    lower = []
    for p in points:
        while len(lower) >= 2 and cross(lower[-2], lower[-1], p) <= 0:
            lower.pop()
        lower.append(p)
    
    upper = []
    for p in reversed(points):
        while len(upper) >= 2 and cross(upper[-2], upper[-1], p) <= 0:
            upper.pop()
        upper.append(p)
    
    return lower[:-1] + upper[:-1]


def make_circle_polygon(cx: float, cy: float, radius: float = 200.0, n: int = 16) -> List[Tuple[float, float]]:
    return [
        (cx + radius * math.cos(2 * math.pi * i / n),
         cy + radius * math.sin(2 * math.pi * i / n))
        for i in range(n)
    ]


def build_room_polygons(page: pymupdf.Page) -> List[RoomPolygon]:
    codes = extract_room_codes(page)
    
    groups = defaultdict(list)
    for c in codes:
        groups[c["code"]].append(c)
    
    polygons = []
    
    for code_type, items in groups.items():
        positions = [(c["x"], c["y"]) for c in items]
        
        if code_type in SPECIAL_CODES:
            clusters = cluster_positions(positions, eps=150.0)
            for cluster_idx, cluster in enumerate(clusters):
                if len(cluster) == 1:
                    poly = make_circle_polygon(cluster[0][0], cluster[0][1], radius=200.0)
                else:
                    hull = convex_hull(cluster)
                    cx = sum(p[0] for p in hull) / len(hull)
                    cy = sum(p[1] for p in hull) / len(hull)
                    poly = [(cx + 1.1 * (x - cx), cy + 1.1 * (y - cy)) for x, y in hull]
                
                cx = sum(p[0] for p in poly) / len(poly)
                cy = sum(p[1] for p in poly) / len(poly)
                
                rules = ROOM_RULES.get(code_type, ROOM_RULES["DEFAULT"])
                
                polygons.append(RoomPolygon(
                    room_id=f"{code_type}_{cluster_idx}",
                    room_type=code_type,
                    polygon=poly,
                    centroid=(cx, cy),
                    rules=rules,
                    code_positions=cluster
                ))
        
        else:
            for item in items:
                poly = make_circle_polygon(item["x"], item["y"], radius=120.0)
                cx = item["x"]
                cy = item["y"]
                
                polygons.append(RoomPolygon(
                    room_id=f"{code_type}_{item['idx']}",
                    room_type=code_type,
                    polygon=poly,
                    centroid=(cx, cy),
                    rules=ROOM_RULES["DEFAULT"],
                    code_positions=[(item["x"], item["y"])]
                ))
    
    return polygons


def point_in_polygon(point: Tuple[float, float], polygon: List[Tuple[float, float]]) -> bool:
    x, y = point
    inside = False
    n = len(polygon)
    for i in range(n):
        j = (i + 1) % n
        xi, yi = polygon[i]
        xj, yj = polygon[j]
        if ((yi > y) != (yj > y)) and (x < (xj - xi) * (y - yi) / (yj - yi) + xi):
            inside = not inside
    return inside


def assign_symbol_to_room(symbol_centroid: Tuple[float, float], 
                          rooms: List[RoomPolygon]) -> Optional[RoomPolygon]:
    for room in rooms:
        if point_in_polygon(symbol_centroid, room.polygon):
            return room
    
    if rooms:
        best_room = min(rooms, key=lambda r: math.hypot(
            symbol_centroid[0] - r.centroid[0],
            symbol_centroid[1] - r.centroid[1]
        ))
        return best_room
    
    return None


def get_room_stats(rooms: List[RoomPolygon]) -> dict:
    from collections import Counter
    type_counts = Counter(r.room_type for r in rooms)
    return {
        "total_polygons": len(rooms),
        "by_type": dict(type_counts),
        "total_codes": sum(len(r.code_positions) for r in rooms)
    }